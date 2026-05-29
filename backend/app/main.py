"""
FastAPI Application Entry Point.
Configures CORS, includes routers, and sets up startup events.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    logger = setup_logging()
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("SWS AI RAG Chatbot — Starting Up")
    logger.info(f"  Model: {settings.ollama_model}")
    logger.info(f"  Ollama URL: {settings.ollama_base_url}")
    logger.info(f"  ChromaDB: {settings.chroma_db_path}")
    logger.info(f"  Embedding: {settings.embedding_model}")
    logger.info(f"  Top-K: {settings.top_k}")
    logger.info(f"  Threshold: {settings.similarity_threshold}")
    logger.info("=" * 60)

    # Pre-load the embedding model on startup (run in thread — it's blocking I/O)
    try:
        from app.services.embedding_service import EmbeddingService
        await asyncio.to_thread(EmbeddingService)
        logger.info("Embedding model pre-loaded successfully")
    except Exception as e:
        logger.warning(f"Could not pre-load embedding model: {e}")

    yield

    logger.info("SWS AI RAG Chatbot — Shutting Down")


# Create FastAPI application
app = FastAPI(
    title="SWS AI RAG Chatbot",
    description=(
        "A Retrieval-Augmented Generation chatbot for answering "
        "employee questions using internal company PDF documents. "
        "Powered by Phi-3 via Ollama (fully local)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS — allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — redirects to API documentation."""
    return {
        "name": "SWS AI RAG Chatbot",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
