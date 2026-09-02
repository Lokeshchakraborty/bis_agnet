# BIS Agentic RAG Assistant (Voice & Text)

A high-performance, modular conversational AI assistant for the **Bureau of Indian Standards (BIS)** built on **LangGraph**, **ChromaDB**, **Hybrid BM25 Retrieval**, and **Google Gemini / Mistral Embeddings**.

---

## 🏗 Project Architecture

```
c:\python\BIS_AGENT\
├── main.py                     # High-level CLI & Voice REPL entry point
├── app.py                      # FastAPI REST application definition & endpoints
├── server.py                   # Uvicorn REST API server launcher
├── test_api.py                 # Automated integration test suite for REST API
├── requirements.txt            # Project dependencies
├── .env                        # Environment credentials (API keys)
├── data/
│   ├── cache.json              # SHA-256 persistent response cache
│   ├── chroma_db/              # Chroma vector database collections
│   └── procedures/             # BIS procedure documents (PDFs & TXTs)
└── src/
    ├── __init__.py             # Root package exports
    ├── config.py               # Centralized configuration & environment validation
    ├── schemas.py              # Pydantic schemas (Intent, BISResponse, AgentState, TokenTracker)
    ├── agent/                  # LangGraph workflow, nodes, and session management
    ├── audio/                  # Whisper STT & Pyttsx3 TTS handlers
    ├── tools/                  # Hybrid retriever, cache, scraper
    └── ingestion/              # Document ingest & database builder
```

---

## 🚀 Quick Start

### 1. Configure Environment
Create or edit your `.env` file in the project root:
```ini
GOOGLE_API_KEY="your-google-gemini-api-key"
MISTRAL_API_KEY="your-mistral-api-key"

# Optional overrides
BIS_LLM_MODEL="gemini-3.5-flash-lite"
BIS_EMBEDDING_PROVIDER="MistralAIEmbeddings"
BIS_CACHE_ENABLED="true"
```

### 2. Ingest BIS Documents
To build or update the Chroma vector collections:
```powershell
python src/ingestion/build_vectordb.py --clean
```

### 3. Run via CLI
```powershell
# Interactive CLI mode (type question or press Enter for microphone voice input)
python main.py

# Text-only CLI mode (disables audio recording)
python main.py --mode text
```

### 4. Run REST API Server
```powershell
# Launch FastAPI server on http://127.0.0.1:8000
python server.py

# Launch on custom host/port with auto-reload
python server.py --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger documentation is available at **http://127.0.0.1:8000/docs** and ReDoc at **http://127.0.0.1:8000/redoc**.

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Check API health, model configurations, and DB status |
| `POST` | `/api/v1/query` | Process a text turn using LangGraph RAG + session history |
| `POST` | `/api/v1/voice-query` | Upload audio clip (`.wav`, `.mp3`, `.m4a`), transcribe via Whisper, and process turn |
| `GET` | `/api/v1/sessions` | List active in-memory conversation sessions |
| `DELETE` | `/api/v1/sessions/{session_id}` | Reset/delete specific session history |
| `POST` | `/api/v1/cache/clear` | Purge persistent SHA-256 response cache |

### Example Query Request (`POST /api/v1/query`)
```json
{
  "query": "What is the procedure for getting a Gold Hallmarking license under BIS?",
  "session_id": "user-session-101"
}
```

---

## ⚡ Key Optimizations & Features
- **FastAPI REST Service**: Production-ready web API with OpenAPI spec, Swagger interactive UI, CORS middleware, and structured Pydantic models.
- **0-Token Cache Bypass**: Repeated queries are served instantly from the SHA-256 persistent cache with 0 LLM API calls.
- **Hybrid Retrieval**: Combines BM25 sparse keyword search with dense embeddings and cosine similarity reranking for maximum context precision.
- **Multilingual & Hinglish Support**: Responds in English, Hindi (Devanagari), or natural Hinglish matching the user's input style.
- **Voice-Ready**: Offline Whisper speech-to-text transcription for voice audio uploads and local audio processing.
