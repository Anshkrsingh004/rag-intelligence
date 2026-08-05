# ─────────────────────────────────────────────────────────────
# RAG Intelligence — backend-only image for Google Cloud Run.
# The React frontend deploys separately (Vercel); this image serves
# ONLY the FastAPI /api. ML models are baked in at build time so a
# warm instance answers the first query fast.
#
# Build context is the backend/ directory:
#   gcloud run deploy rag-backend --source backend ...
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    WARM_UP_MODELS=1 \
    PORT=8080
WORKDIR /app

# CPU-only torch FIRST so sentence-transformers reuses it (image ~2 GB, not the
# multi-GB CUDA build).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Backend source (build context = backend/).
COPY . ./

# Bake the embedding + reranker models into the image (no runtime download).
RUN python -c "from app.ml_models import warm_up; warm_up()"

EXPOSE 8080
# Cloud Run injects $PORT (8080). Honour it.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
