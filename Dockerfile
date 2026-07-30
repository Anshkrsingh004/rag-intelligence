# ─────────────────────────────────────────────────────────────
# RAG Intelligence — single-container production image.
# FastAPI serves the built React SPA + the API. ML models are baked
# in at build time so the first request is fast.
# ─────────────────────────────────────────────────────────────

# ── Stage 1: build the React frontend ────────────────────────
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build                       # emits /app/frontend/dist

# ── Stage 2: Python runtime ──────────────────────────────────
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    PORT=7860 \
    WARM_UP_MODELS=1
WORKDIR /app

# Install the CPU-only build of torch FIRST so sentence-transformers reuses it
# (keeps the image ~2GB instead of pulling the multi-GB CUDA build).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Backend code + the built SPA (main.py serves ../frontend/dist).
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Bake the embedding + reranker models into the image (no runtime download).
RUN cd backend && python -c "from app.ml_models import warm_up; warm_up()"

EXPOSE 7860
WORKDIR /app/backend
# Honour the platform's $PORT (Render/HF/Fly all differ); default 7860 for HF Spaces.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
