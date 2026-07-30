"""
Central configuration for the RAG Intelligence backend.

All tunables live here so the pipeline modules stay free of magic numbers.
The Groq API key is read from the environment (optionally via a .env file) and
is NEVER hardcoded in source.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load variables from backend/.env if present (does not override real env vars).
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


def require_api_key() -> str:
    """Return the Groq API key or raise a helpful error."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise ConfigError(
            "GROQ_API_KEY is not set.\n"
            "  - Create backend/.env from backend/.env.example and paste your key, or\n"
            "  - export GROQ_API_KEY=your-key-here      (macOS/Linux)\n"
            "  - setx   GROQ_API_KEY your-key-here       (Windows, new shell)\n"
            "Get a free key at https://console.groq.com\n"
            "Never hardcode API keys in source — leaked keys get scraped within hours."
        )
    return key


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings for the pipeline."""

    # ── Models (overridable via MODEL_FAST / MODEL_QUALITY env vars) ──
    model_fast: str = field(
        default_factory=lambda: os.environ.get("MODEL_FAST") or "llama-3.1-8b-instant"
    )   # baseline + hallucinating panels
    model_quality: str = field(
        default_factory=lambda: os.environ.get("MODEL_QUALITY") or "llama-3.3-70b-versatile"
    )   # grounded RAG answer + judges
    embedding_model: str = "all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    max_tokens: int = 512

    # ── Retrieval ─────────────────────────────────────────────
    docs_per_query: int = 3
    top_docs: int = 5
    rerank_pool: int = 12          # candidates the cross-encoder scores before truncation
    min_doc_words: int = 12
    max_retries: int = 2

    # ── Metric thresholds ─────────────────────────────────────
    precision_k: int = 3
    relevance_threshold: float = 0.30
    semantic_support_threshold: float = 0.55   # cosine; below this a sentence is "unsupported"
    semantic_entity_threshold: float = 0.60

    # ── Concurrency ───────────────────────────────────────────
    max_workers: int = 6

    # ── Auth / tokens ─────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24 * 7   # one week

    # ── Meta ──────────────────────────────────────────────────
    version: str = "v9-modular"

    # Words dropped when scoring lexical overlap / extracting entities.
    stopwords: frozenset[str] = field(default_factory=lambda: frozenset({
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to',
        'for', 'of', 'and', 'or', 'but', 'it', 'its', 'this', 'that', 'with',
        'as', 'by', 'from', 'have', 'has', 'had', 'be', 'been', 'not', 'no',
        'who', 'what', 'when', 'where', 'how', 'which', 'i', 'you', 'we', 'they',
        'their', 'our', 'your', 'his', 'her', 'also', 'just', 'more', 'than',
        'then', 'so', 'if', 'do', 'did', 'does', 'will', 'would', 'could', 'after',
        'before', 'during', 'over', 'under', 'about', 'into', 'through', 'between',
        'each', 'such', 'only', 'other', 'some', 'these', 'those', 'very', 'can',
        'get', 'got', 'may', 'might', 'must', 'shall', 'being', 'am',
        'said', 'says', 'according', 'per', 'via', 'like', 'new', 'one', 'two',
    }))

    # Phrases that signal the model dodged the question (used to trigger a retry).
    evasion_phrases: tuple[str, ...] = (
        "not mentioned", "does not mention", "not provided", "not available",
        "i don't know", "cannot find", "no information", "not stated",
        "not found", "information provided does not", "cannot determine",
        "not explicitly", "unable to", "no specific", "does not contain",
        "no results", "not specified", "as of my knowledge cutoff",
        "as of my last update", "my training data", "i cannot confirm",
        "i do not have", "outside my", "beyond my", "i'm not sure",
        "i am not sure", "no data", "insufficient",
    )


settings = Settings()

# ── Database location ──────────────────────────────────────────
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "app.db"


def get_jwt_secret() -> str:
    """Signing key for auth tokens. Set JWT_SECRET in prod; dev has a fallback."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        print("  [WARN] JWT_SECRET not set — using an insecure dev secret. "
              "Set JWT_SECRET in backend/.env before deploying.")
        secret = "dev-insecure-jwt-secret-change-me"
    return secret


def get_google_client_id() -> str | None:
    """OAuth client id for 'Sign in with Google'. When unset, Google auth is off."""
    cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    return cid or None
