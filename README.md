# SWS AI RAG Chatbot

A privacy-focused, local **Retrieval-Augmented Generation (RAG)** system built to answer questions grounded in internal company PDF documents. Powered by **FastAPI**, **ChromaDB**, **Sentence Transformers**, and **Ollama (Phi-3)**.

---

## 🌟 Key Features

- 🔒 **100% Local & Private**: No external API calls. Runs locally with Ollama (`phi3`) and local embedding models.
- 📄 **PDF Processing & Ingestion**: Extract, split, and embed text from PDF documents using PyMuPDF and LangChain Text Splitters.
- ⚡ **Vector Search**: Fast semantic search using ChromaDB vector database with custom similarity threshold filtering.
- 💬 **Streaming Responses**: Real-time response streaming over Server-Sent Events (SSE).
- 📤 **Dynamic Document Upload**: Upload new PDF files directly via the API or frontend interface for instant document indexing.
- 🎨 **Modern Frontend Interface**: Sleek UI with dark mode support, source document citations, and live health status indicators.

---

## 🏗️ Architecture & Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+) |
| **LLM Engine** | [Ollama](https://ollama.com/) running `phi3` |
| **Vector Database** | [ChromaDB](https://www.trychroma.com/) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` |
| **PDF Extraction & Chunking** | PyMuPDF (fitz) & LangChain Text Splitters |
| **Frontend UI** | HTML5, CSS3 (Vanilla), JavaScript (ES6+) |

---

## 📁 Project Structure

```text
rag-chatbot/
├── backend/
│   ├── app/
│   │   ├── api/             # API Router & request/response schemas
│   │   ├── core/            # Configuration management & logging setup
│   │   ├── ingestion/       # PDF parsing and vector indexing pipelines
│   │   ├── services/        # RAG pipeline, Ollama LLM integration, & Embeddings
│   │   └── main.py          # FastAPI application entry point
│   └── requirements.txt     # Backend Python dependencies
├── frontend/
│   ├── index.html           # Main web interface layout
│   ├── style.css            # Custom CSS styles and UI theme
│   └── script.js            # Client-side chat logic & streaming handlers
└── README.md                # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites

1. **Python**: Python 3.10 or higher installed.
2. **Ollama**: Download and install [Ollama](https://ollama.com/).
3. **Pull Phi-3 Model**:
   ```bash
   ollama pull phi3
   ```
   Ensure Ollama service is running on `http://localhost:11434`.

---

### Backend Setup

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. *(Optional)* **Configuration**:
   You can create a `.env` file in the `backend/` directory to customize default settings:
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
   ```

5. **Start the Backend Server**:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   The API will be available at `http://127.0.0.1:8000`. Interactive API documentation is accessible at `http://127.0.0.1:8000/docs`.

---

### Frontend Setup

1. Open `frontend/index.html` in your web browser, or serve it using any HTTP server (e.g. VS Code Live Server or Python's `http.server`):
   ```bash
   cd frontend
   python -m http.server 3000
   ```
2. Open `http://localhost:3000` in your browser.

---

## 📡 API Endpoints Summary

- **`POST /api/chat`**: Send a user question and receive a grounded answer with source document references (supports streaming).
- **`POST /api/upload`**: Upload a new `.pdf` document to dynamically ingest into ChromaDB.
- **`POST /api/ingest`**: Bulk ingest all PDF files placed inside the configured `docs/` directory.
- **`GET /api/health`**: Check system health, Ollama connection status, and ChromaDB document chunk count.

---

## 📄 License

This project is open-source and intended for internal document Q&A application reference.
