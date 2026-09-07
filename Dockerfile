# =============================================================================
# Bureau of Indian Standards (BIS) Agentic RAG Assistant - Production Dockerfile
# Multi-Stage Build: Builds Vite React Frontend + Serves via Python FastAPI Backend
# =============================================================================

# --- Stage 1: Build React Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python Backend Environment ---
FROM python:3.11-slim AS runner
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Install system dependencies (build-essential, libpq for psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . .

# Copy built frontend dist from Stage 1 into /app/frontend/dist
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose default port
EXPOSE 8000

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Command to run production FastAPI server
CMD ["sh", "-c", "python server.py --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
