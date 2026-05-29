"""
RAG Service — Orchestrates retrieval and generation.
Embeds the user query, retrieves relevant chunks from ChromaDB,
filters by similarity threshold, and generates a grounded answer.
"""

import time
import chromadb
from typing import Dict, List, Any, AsyncGenerator

from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService


class RAGService:
    """Orchestrates the full RAG pipeline: embed → retrieve → generate."""

    def __init__(self):
        self.settings = get_settings()
        self.logger = get_logger()
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()

        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(
            path=self.settings.chroma_db_path
        )

    def _get_collection(self):
        """Get the ChromaDB collection."""
        try:
            return self.chroma_client.get_collection(
                name=self.settings.chroma_collection_name
            )
        except Exception as e:
            self.logger.error(f"Collection not found: {e}")
            raise ValueError(
                "Document collection not found. "
                "Please ingest documents first via POST /api/ingest"
            )

    def _retrieve(self, query: str) -> Dict[str, Any]:
        """
        Retrieve the most relevant document chunks for a query.

        Args:
            query: The user's question.

        Returns:
            Dict with 'chunks', 'sources', 'distances'.
        """
        start = time.time()

        # Embed the query
        query_embedding = self.embedding_service.encode_query(query)

        # Query ChromaDB for top-k results
        collection = self._get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=self.settings.top_k,
            include=["documents", "metadatas", "distances"],
        )

        elapsed = time.time() - start
        self.logger.info(f"Retrieval completed in {elapsed:.2f}s")

        # Extract results
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        # Filter by similarity threshold
        filtered_chunks = []
        filtered_sources = []
        filtered_distances = []

        for doc, meta, dist in zip(documents, metadatas, distances):
            if dist <= self.settings.similarity_threshold:
                filtered_chunks.append(doc)
                filtered_sources.append(meta)
                filtered_distances.append(dist)
                self.logger.info(
                    f"  ✓ Retrieved chunk (distance={dist:.4f}) "
                    f"from: {meta.get('source', 'unknown')}"
                )
            else:
                self.logger.info(
                    f"  ✗ Filtered chunk (distance={dist:.4f}) — "
                    f"exceeds threshold {self.settings.similarity_threshold}"
                )

        return {
            "chunks": filtered_chunks,
            "sources": filtered_sources,
            "distances": filtered_distances,
        }

    def _build_context(self, chunks: List[str]) -> str:
        """Compile retrieved chunks into a context string."""
        if not chunks:
            return ""
        return "\n\n---\n\n".join(chunks)

    def _extract_unique_sources(self, sources: List[Dict]) -> List[str]:
        """Extract unique source document names."""
        seen = set()
        unique = []
        for meta in sources:
            source = meta.get("source", "Unknown")
            if source not in seen:
                seen.add(source)
                unique.append(source)
        return unique

    async def query(self, question: str) -> Dict[str, Any]:
        """
        Process a user question through the full RAG pipeline (non-streaming).

        Args:
            question: The user's question.

        Returns:
            Dict with 'answer', 'sources', 'retrieval_info'.
        """
        self.logger.info(f"Processing query: {question}")
        total_start = time.time()

        # Step 1: Retrieve relevant chunks
        retrieval = self._retrieve(question)

        if not retrieval["chunks"]:
            self.logger.info("No relevant chunks found above threshold")
            return {
                "answer": "I don't have that information in the company documents.",
                "sources": [],
                "retrieval_info": {
                    "chunks_retrieved": 0,
                    "chunks_used": 0,
                },
            }

        # Step 2: Build context
        context = self._build_context(retrieval["chunks"])

        # Step 3: Generate answer
        answer = await self.llm_service.generate(question, context)

        # Step 4: Extract sources
        unique_sources = self._extract_unique_sources(retrieval["sources"])

        total_elapsed = time.time() - total_start
        self.logger.info(
            f"Query completed in {total_elapsed:.2f}s | "
            f"Sources: {unique_sources}"
        )

        return {
            "answer": answer,
            "sources": unique_sources,
            "retrieval_info": {
                "chunks_retrieved": len(retrieval["chunks"]),
                "distances": retrieval["distances"],
            },
        }

    async def query_stream(
        self, question: str
    ) -> AsyncGenerator[str, None]:
        """
        Process a user question with streaming response.
        Yields JSON-encoded events for the frontend.

        Args:
            question: The user's question.

        Yields:
            JSON strings with 'type' and 'content' fields.
        """
        import json

        self.logger.info(f"Processing streaming query: {question}")

        # Step 1: Retrieve relevant chunks
        retrieval = self._retrieve(question)

        if not retrieval["chunks"]:
            self.logger.info("No relevant chunks found above threshold")
            yield json.dumps({
                "type": "complete",
                "content": "I don't have that information in the company documents.",
                "sources": [],
            }) + "\n"
            return

        # Step 2: Build context
        context = self._build_context(retrieval["chunks"])
        unique_sources = self._extract_unique_sources(retrieval["sources"])

        # Send sources first
        yield json.dumps({
            "type": "sources",
            "sources": unique_sources,
        }) + "\n"

        # Step 3: Stream the answer
        full_answer = ""
        async for token in self.llm_service.generate_stream(question, context):
            full_answer += token
            yield json.dumps({
                "type": "token",
                "content": token,
            }) + "\n"

        # Send completion signal
        yield json.dumps({
            "type": "complete",
            "content": full_answer,
            "sources": unique_sources,
        }) + "\n"

        self.logger.info(f"Streaming query completed | Sources: {unique_sources}")
