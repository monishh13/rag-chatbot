"""
PDF Document Ingestion Pipeline.
Extracts text from PDFs, chunks it semantically, generates embeddings,
and stores everything in ChromaDB with metadata.
Supports idempotent ingestion (no duplicates).
"""

import os
import hashlib
import time
import fitz  # PyMuPDF
import chromadb
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.services.embedding_service import EmbeddingService


def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract text from a PDF file using PyMuPDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of dicts with 'text', 'page_number', 'source' keys.
    """
    logger = get_logger()
    pages = []

    try:
        doc = fitz.open(pdf_path)
        filename = os.path.basename(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()

            if text:
                pages.append({
                    "text": text,
                    "page_number": page_num + 1,
                    "source": filename,
                })

        doc.close()
        logger.info(
            f"Extracted {len(pages)} pages from: {filename}"
        )

    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
        raise

    return pages


def chunk_text(
    pages: List[Dict[str, Any]],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[Dict[str, Any]]:
    """
    Split extracted page text into semantic chunks.

    Args:
        pages: List of page dicts from extract_text_from_pdf.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        List of chunk dicts with 'text', 'metadata' keys.
    """
    logger = get_logger()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    chunks = []
    chunk_index = 0

    for page in pages:
        page_chunks = splitter.split_text(page["text"])

        for chunk_text_content in page_chunks:
            if chunk_text_content.strip():
                chunks.append({
                    "text": chunk_text_content.strip(),
                    "metadata": {
                        "source": page["source"],
                        "page_number": page["page_number"],
                        "chunk_index": chunk_index,
                    },
                })
                chunk_index += 1

    logger.info(
        f"Created {len(chunks)} chunks from {len(pages)} pages "
        f"(chunk_size={chunk_size}, overlap={chunk_overlap})"
    )

    return chunks


def generate_chunk_id(source: str, chunk_index: int, text: str) -> str:
    """
    Generate a unique, deterministic ID for a chunk.
    Uses source + chunk_index + text hash for idempotency.
    """
    content = f"{source}_{chunk_index}_{text[:100]}"
    return hashlib.md5(content.encode()).hexdigest()


def ingest_documents(docs_path: str = None) -> Dict[str, Any]:
    """
    Run the full ingestion pipeline:
    1. Find all PDFs in docs_path
    2. Extract text from each PDF
    3. Chunk the text
    4. Generate embeddings
    5. Store in ChromaDB (idempotent)

    Args:
        docs_path: Path to directory containing PDF files.

    Returns:
        Dict with ingestion statistics.
    """
    settings = get_settings()
    logger = get_logger()

    if docs_path is None:
        docs_path = settings.docs_path

    logger.info(f"Starting document ingestion from: {docs_path}")
    total_start = time.time()

    # Validate docs directory
    if not os.path.exists(docs_path):
        raise FileNotFoundError(f"Documents directory not found: {docs_path}")

    # Find all PDF files
    pdf_files = [
        os.path.join(docs_path, f)
        for f in os.listdir(docs_path)
        if f.lower().endswith(".pdf")
    ]

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {docs_path}")

    logger.info(f"Found {len(pdf_files)} PDF files")

    # Initialize services
    embedding_service = EmbeddingService()

    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(path=settings.chroma_db_path)
    collection = chroma_client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"description": "SWS AI company documents"},
    )

    # Track statistics
    stats = {
        "files_processed": 0,
        "total_pages": 0,
        "total_chunks": 0,
        "new_chunks": 0,
        "skipped_chunks": 0,
        "errors": [],
    }

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        logger.info(f"Processing: {filename}")

        try:
            # Step 1: Extract text
            pages = extract_text_from_pdf(pdf_path)
            if not pages:
                logger.warning(f"No text extracted from: {filename}")
                stats["errors"].append(f"No text in: {filename}")
                continue

            stats["total_pages"] += len(pages)

            # Step 2: Chunk the text
            chunks = chunk_text(
                pages,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            stats["total_chunks"] += len(chunks)

            # Step 3: Build all candidate IDs and text up front
            candidate_ids = []
            candidate_texts = []
            candidate_metadatas = []

            for chunk in chunks:
                chunk_id = generate_chunk_id(
                    chunk["metadata"]["source"],
                    chunk["metadata"]["chunk_index"],
                    chunk["text"],
                )
                candidate_ids.append(chunk_id)
                candidate_texts.append(chunk["text"])
                candidate_metadatas.append(chunk["metadata"])

            # Step 4: Single batched duplicate check — ONE query instead of N
            existing_result = collection.get(ids=candidate_ids)
            existing_ids = set(existing_result["ids"])

            new_ids = []
            new_texts = []
            new_metadatas = []

            for chunk_id, text, metadata in zip(
                candidate_ids, candidate_texts, candidate_metadatas
            ):
                if chunk_id in existing_ids:
                    stats["skipped_chunks"] += 1
                else:
                    new_ids.append(chunk_id)
                    new_texts.append(text)
                    new_metadatas.append(metadata)

            if new_ids:
                # Step 5: Generate embeddings (batched)
                embeddings = embedding_service.encode(new_texts)

                # Step 6: Store in ChromaDB
                collection.add(
                    ids=new_ids,
                    documents=new_texts,
                    embeddings=embeddings,
                    metadatas=new_metadatas,
                )

                stats["new_chunks"] += len(new_ids)
                logger.info(
                    f"Stored {len(new_ids)} new chunks from: {filename}"
                )
            else:
                logger.info(f"All chunks already exist for: {filename}")

            stats["files_processed"] += 1

        except Exception as e:
            logger.error(f"Error processing {filename}: {str(e)}")
            stats["errors"].append(f"Error in {filename}: {str(e)}")

    total_elapsed = time.time() - total_start
    stats["total_time_seconds"] = round(total_elapsed, 2)

    logger.info(
        f"Ingestion complete in {total_elapsed:.2f}s | "
        f"Files: {stats['files_processed']} | "
        f"New chunks: {stats['new_chunks']} | "
        f"Skipped: {stats['skipped_chunks']}"
    )

    return stats


def ingest_single_document(pdf_path: str) -> Dict[str, Any]:
    """
    Ingest a single PDF document.
    Extracts, chunks, embeds, and stores in ChromaDB.
    """
    settings = get_settings()
    logger = get_logger()
    filename = os.path.basename(pdf_path)

    logger.info(f"Starting single document ingestion for: {filename}")
    start_time = time.time()

    # Initialize services
    embedding_service = EmbeddingService()

    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(path=settings.chroma_db_path)
    collection = chroma_client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"description": "SWS AI company documents"},
    )

    stats = {
        "filename": filename,
        "pages": 0,
        "chunks": 0,
        "new_chunks": 0,
        "skipped_chunks": 0,
        "elapsed_seconds": 0,
    }

    # Step 1: Extract text
    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        raise ValueError(f"No text could be extracted from: {filename}")

    stats["pages"] = len(pages)

    # Step 2: Chunk the text
    chunks = chunk_text(
        pages,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    stats["chunks"] = len(chunks)

    # Step 3: Build candidate IDs
    candidate_ids = []
    candidate_texts = []
    candidate_metadatas = []

    for chunk in chunks:
        chunk_id = generate_chunk_id(
            chunk["metadata"]["source"],
            chunk["metadata"]["chunk_index"],
            chunk["text"],
        )
        candidate_ids.append(chunk_id)
        candidate_texts.append(chunk["text"])
        candidate_metadatas.append(chunk["metadata"])

    # Step 4: Duplicate Check
    existing_result = collection.get(ids=candidate_ids)
    existing_ids = set(existing_result["ids"])

    new_ids = []
    new_texts = []
    new_metadatas = []

    for chunk_id, text, metadata in zip(
        candidate_ids, candidate_texts, candidate_metadatas
    ):
        if chunk_id in existing_ids:
            stats["skipped_chunks"] += 1
        else:
            new_ids.append(chunk_id)
            new_texts.append(text)
            new_metadatas.append(metadata)

    # Step 5: Embed & Store
    if new_ids:
        embeddings = embedding_service.encode(new_texts)
        collection.add(
            ids=new_ids,
            documents=new_texts,
            embeddings=embeddings,
            metadatas=new_metadatas,
        )
        stats["new_chunks"] = len(new_ids)

    stats["elapsed_seconds"] = round(time.time() - start_time, 2)
    logger.info(f"Ingested {filename} in {stats['elapsed_seconds']}s. New chunks: {stats['new_chunks']}")
    return stats

