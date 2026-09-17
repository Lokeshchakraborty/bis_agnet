# Production Deployment & Operations Guide

This guide provides step-by-step instructions for deploying the **Bureau of Indian Standards (BIS) Agentic RAG Assistant (BIS SATHI)** across various production environments.

---

## 🏗 Architecture Overview

The system can be deployed in two configurations:

1. **Unified Single-Service (Recommended)**:
   - React frontend is built into static assets (`frontend/dist`) via a multi-stage Docker build.
   - FastAPI serves both the REST API endpoints (`/api/v1/...`) and the React UI (`/`) on a single port (e.g., `8000`).
   - Zero CORS overhead and zero domain mismatch.

2. **Decoupled Architecture**:
   - **Frontend**: Hosted on **Vercel** / **Netlify** / **Cloudflare Pages**.
   - **Backend**: Hosted on **Render** / **Railway** / **AWS ECS** / **Fly.io**.
   - Connected via `VITE_API_BASE_URL` or Vercel rewrites (`vercel.json`).

---

## 🚀 Option 1: Deploy on Render (Docker Blueprint)

Render allows one-click continuous deployment using the included `render.yaml` and `Dockerfile`.

### Steps:
1. Push your repository to **GitHub** or **GitLab**.
2. Log into [Render Dashboard](https://dashboard.render.com).
3. Click **New +** → **Blueprint**.
4. Select your repository. Render will automatically detect `render.yaml`.
5. Configure your secret environment variables in the Render dashboard:
   - `GOOGLE_API_KEY`: Your Google Gemini API Key.
   - `MISTRAL_API_KEY`: Your Mistral AI API Key.
   - `DATABASE_URL`: Your Supabase PostgreSQL Connection URI.
   - `SUPABASE_URL`: Your Supabase Project URL (`https://xxxx.supabase.co`).
   - `SUPABASE_KEY`: Your Supabase Anon or Service Key.
6. Click **Apply**. Render will:
   - Build the React frontend in Stage 1.
   - Build the Python environment in Stage 2.
   - Verify health at `/health`.
   - Serve the complete application on HTTPS.

### ⏰ Render Free Tier Anti-Idle (Keep-Alive)
Render's free tier automatically spins down web services after 15 minutes of inactivity. To prevent this, **BIS SATHI** includes a built-in automated background keep-alive service:
- **Self-Pinging Loop**: The server automatically pings `/health` every 10 minutes (600s).
- **Public Router Ping**: It automatically detects `RENDER_EXTERNAL_URL` (injected by Render) and pings the public HTTPS address, ensuring Render's proxy records active traffic.
- **Diagnostics Endpoint**: Inspect status and metrics anytime at `GET /api/v1/keep-alive` or trigger an immediate ping with `POST /api/v1/keep-alive/trigger`.

---

## 🐳 Option 2: Deploy with Docker & Docker Compose (Self-Hosted VPS)

Deploy on any Linux (Ubuntu/Debian) or Windows VPS with Docker installed.

### 1. Clone & Configure Environment
```bash
git clone https://github.com/your-org/BIS_AGENT.git
cd BIS_AGENT
cp .env.example .env
# Edit .env with your production credentials
nano .env
```

### 2. Build & Launch Containers
```bash
docker compose up -d --build
```

### 3. Verify Container Status
```bash
docker compose ps
docker compose logs -f bis-agent
```

### 4. Test Health Endpoint
```bash
curl -f http://localhost:8000/health
```

The app will be accessible at `http://your-server-ip:8000`.

---

## ⚡ Option 3: Decoupled Deployment (Vercel Frontend + Render Backend)

### 1. Deploy Backend (Render / Railway / Fly.io)
- Deploy using the root `Dockerfile` or `Procfile`.
- Note down your backend URL (e.g., `https://bis-backend.onrender.com`).

### 2. Deploy Frontend on Vercel
- Import repository into Vercel.
- Set **Root Directory** to `frontend`.
- Add Environment Variable:
  ```env
  VITE_API_BASE_URL=https://bis-backend.onrender.com
  ```
- Deploy! Vercel will build Vite and rewrite `/api/*` requests to your backend.

---

## 🗄 Database Initialization (Supabase PGVector)

If utilizing **Supabase PostgreSQL** for vector search and user sessions:

1. Open your [Supabase SQL Editor](https://app.supabase.com).
2. Open `backend/db/schema.sql` from this repository.
3. Run the SQL script to provision:
   - `vector` and `uuid-ossp` extensions.
   - `users` table with password hashing and token tracking.
   - `sessions` table for persistent conversation states.
   - `audit_logs` table for immutable legal audit trails.
   - `response_cache` table for cross-session 0-token caching.
4. Copy your connection URI into `DATABASE_URL` in `.env`.

---

## ⚙ Production Environment Variables Reference

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `GOOGLE_API_KEY` | **Yes** | — | Google Gemini API key for LLM responses. |
| `MISTRAL_API_KEY` | **Yes** | — | Mistral AI API key for embeddings. |
| `DATABASE_URL` | Optional | — | PostgreSQL connection URI for Supabase PGVector. |
| `SUPABASE_URL` | Optional | — | Supabase REST URL. |
| `SUPABASE_KEY` | Optional | — | Supabase API key. |
| `BIS_LLM_MODEL` / `LLM_MODEL` | No | `gemini-3.5-flash` | Production LLM model name. |
| `BIS_EMBEDDING_PROVIDER` | No | `MistralAIEmbeddings` | Embedding provider (`MistralAIEmbeddings`, `fastembed`, `google`). |
| `BIS_CACHE_ENABLED` | No | `true` | Persistent SHA-256 cache toggle. |
| `HOST` | No | `0.0.0.0` | Network binding host. |
| `PORT` | No | `8000` | Port to expose. |
| `WORKERS` | No | `1` | Number of Uvicorn worker processes. |

---

## 🛡 Health Checks & Monitoring

- **Health Check Endpoint**: `GET /health`
  Returns JSON status with model provider, database status, and active sessions:
  ```json
  {
    "status": "ok",
    "service": "BIS Agentic RAG Assistant REST API",
    "llm_model": "gemini-3.5-flash",
    "embedding_provider": "MistralAIEmbeddings",
    "cache_enabled": true,
    "chroma_db_exists": true,
    "active_sessions_count": 0,
    "supabase_connected": true
  }
  ```
- **Interactive OpenAPI Documentation**: `GET /docs`
- **ReDoc Documentation**: `GET /redoc`
- **Audit Logs API**: `GET /api/v1/audit-logs`
