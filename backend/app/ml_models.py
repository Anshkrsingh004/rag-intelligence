"""
Local, CPU-only ML models used for semantic scoring and reranking.

Both models are lazy-loaded (first use downloads ~80MB each, then cached by
sentence-transformers) so imports and `--help` stay fast and cost nothing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from .config import settings

if TYPE_CHECKING:  # pragma: no cover - hints only
    from sentence_transformers import CrossEncoder, SentenceTransformer


@lru_cache(maxsize=1)
def get_embedder() -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer

    print(f"  [Loading] embedding model {settings.embedding_model} (first run downloads ~80MB)...")
    return SentenceTransformer(settings.embedding_model)


@lru_cache(maxsize=1)
def get_reranker() -> "CrossEncoder":
    from sentence_transformers import CrossEncoder

    print(f"  [Loading] reranker {settings.reranker_model} (first run downloads ~80MB)...")
    return CrossEncoder(settings.reranker_model)


def embed(texts: list[str]) -> np.ndarray:
    """Encode a list of strings into an (n, dim) numpy matrix."""
    return get_embedder().encode(texts, convert_to_numpy=True, show_progress_bar=False)


def cosine_sim_matrix(a_vecs: np.ndarray, b_vecs: np.ndarray) -> np.ndarray:
    """Row-wise cosine similarity between every vector in a and every vector in b."""
    a = a_vecs / (np.linalg.norm(a_vecs, axis=1, keepdims=True) + 1e-8)
    b = b_vecs / (np.linalg.norm(b_vecs, axis=1, keepdims=True) + 1e-8)
    return a @ b.T


def warm_up() -> None:
    """Eagerly load both models (used at server startup to avoid a slow first query)."""
    get_embedder()
    get_reranker()
