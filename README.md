# RAG Chatbot (SWS AI Assistant)

Local Retrieval-Augmented Generation (RAG) chatbot for answering company-policy questions from PDF documents.

## What this project does

- Ingests PDF files, extracts text, chunks content, and stores embeddings in ChromaDB.
- Retrieves relevant chunks for each user question.
- Generates grounded answers with Ollama (`phi3` by default).
- Streams token-by-token responses to a lightweight frontend.
- Supports dynamic PDF upload from the UI.

## Architecture

- **Backend:** FastAPI (`backend/app`)
  - `api/routes.py`: chat, ingest, upload, and health endpoints
  - `services/rag_service.py`: retrieval + generation orchestration
  - `services/embedding_service.py`: SentenceTransformer embeddings
  - `services/llm_service.py`: Ollama API client
  - `ingestion/ingest.py`: PDF extraction/chunking/indexing pipeline
- **Frontend:** Static HTML/CSS/JS (`frontend`)
  - Chat interface with streaming rendering
  - Local chat history in `localStorage`
  - Drag-and-drop PDF upload
- **Vector DB:** Local persistent ChromaDB (`./chroma_db` by default)

## Prerequisites

- Python 3.10+
- Ollama installed and running
- Ollama model pulled (default: `phi3`)

Example:

```bash
ollama serve
ollama pull phi3
```

## Setup

1. Install backend dependencies:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. (Optional) Configure environment variables via `backend/.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3
CHROMA_DB_PATH=./chroma_db
CHROMA_COLLECTION_NAME=sws_documents
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K=5
SIMILARITY_THRESHOLD=1.2
DOCS_PATH=./docs
LOG_LEVEL=INFO
LOG_FILE=./logs/rag_chatbot.log
```

3. Start backend:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Start frontend (any static server), for example:

```bash
cd frontend
python -m http.server 5500
```

Then open `http://localhost:5500`.

## Ingestion flow

You can ingest documents in two ways:

1. **Bulk ingest** from backend `docs` folder:
   - Add PDFs to `backend/docs` (or your configured `DOCS_PATH`)
   - Call `POST /api/ingest`
2. **UI upload**:
   - Use the **Upload Documents** tab in the frontend
   - Files are sent to `POST /api/upload` and ingested immediately

The ingestion pipeline is idempotent via deterministic chunk IDs, so existing chunks are skipped.

## API overview

Base URL: `http://localhost:8000`

- `GET /` — service metadata
- `GET /api/health` — Ollama + collection health
- `POST /api/chat` — ask a question
  - Request: `{ "question": "...", "stream": true|false }`
  - Streaming mode emits newline-delimited JSON events:
    - `{"type":"sources","sources":[...]}`
    - `{"type":"token","content":"..."}`
    - `{"type":"complete","content":"...","sources":[...]}`
- `POST /api/ingest` — ingest all PDFs in docs path
- `POST /api/upload` — upload and ingest a single PDF (`multipart/form-data`)

## Notes

- The assistant is designed to answer from retrieved document context only.
- If no relevant chunks are found, it returns:  
  `I don't have that information in the company documents.`
- CORS is currently open for development (`allow_origins=["*"]`).
