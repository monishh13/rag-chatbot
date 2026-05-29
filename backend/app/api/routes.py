"""
API Routes for the RAG Chatbot.
Provides endpoints for chat, document ingestion, and health checks.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import asyncio

from app.services.rag_service import RAGService
from app.services.llm_service import LLMService
from app.ingestion.ingest import ingest_documents
from app.core.config import get_settings
from app.core.logging_config import get_logger

router = APIRouter(prefix="/api", tags=["RAG Chatbot"])


# ─── Request / Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Chat request payload."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question to answer from company documents.",
        examples=["What is the annual leave policy at SWS AI?"],
    )
    stream: Optional[bool] = Field(
        default=True,
        description="Whether to stream the response.",
    )


class ChatResponse(BaseModel):
    """Chat response payload (non-streaming)."""
    answer: str
    sources: list[str]
    retrieval_info: Optional[dict] = None


class IngestResponse(BaseModel):
    """Document ingestion response."""
    status: str
    stats: dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    ollama_connected: bool
    model: str
    collection_count: int


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/chat", summary="Chat with RAG Chatbot")
async def chat(request: ChatRequest):
    """
    Send a question and get a grounded answer from company documents.

    The endpoint:
    1. Embeds the question
    2. Retrieves top-k relevant document chunks
    3. Filters by similarity threshold
    4. Generates a grounded answer using Phi-3 via Ollama

    If streaming is enabled (default), returns a StreamingResponse
    with newline-delimited JSON events.
    """
    logger = get_logger()

    # Validate input
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    logger.info(f"Chat request: {question[:100]}...")

    try:
        rag_service = RAGService()

        if request.stream:
            # Streaming response
            return StreamingResponse(
                rag_service.query_stream(question),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            # Non-streaming response
            result = await rag_service.query(question)
            return ChatResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post(
    "/ingest",
    response_model=IngestResponse,
    summary="Ingest PDF Documents",
)
async def ingest():
    """
    Trigger ingestion of all PDF documents in the docs/ directory.

    This will:
    1. Extract text from all PDFs
    2. Split into semantic chunks
    3. Generate embeddings
    4. Store in ChromaDB (idempotent — no duplicates)
    """
    logger = get_logger()
    logger.info("Ingestion triggered via API")

    try:
        # Run the synchronous ingestion pipeline in a thread so the event loop
        # stays free to handle other requests during what can be a long operation.
        stats = await asyncio.to_thread(ingest_documents)
        return IngestResponse(status="success", stats=stats)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
)
async def health():
    """Check the health of the RAG system components."""
    settings = get_settings()
    llm_service = LLMService()

    # Check Ollama connectivity
    ollama_ok = await llm_service.check_health()

    # Check ChromaDB collection
    try:
        import chromadb
        client = chromadb.PersistentClient(path=settings.chroma_db_path)
        collection = client.get_collection(name=settings.chroma_collection_name)
        count = collection.count()
    except Exception:
        count = 0

    status = "healthy" if ollama_ok else "degraded"

    return HealthResponse(
        status=status,
        ollama_connected=ollama_ok,
        model=settings.ollama_model,
        collection_count=count,
    )
