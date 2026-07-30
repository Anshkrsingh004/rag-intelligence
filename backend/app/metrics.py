"""
Answer-quality metrics.

Two families:
  * Lexical (precision@k, recall@k, MRR, ROUGE-L, token-F1, ...) — cheap, kept
    for retrieval quality and diversity numbers.
  * Semantic (hallucination rate, context utilization, entity grounding) —
    embedding cosine similarity, so paraphrases are not falsely flagged and
    same-vocabulary-but-wrong claims are not falsely passed.

The semantic hallucination rate and context utilization share one embedding
pass (they use the same answer/context vectors) instead of encoding twice.
"""

from __future__ import annotations

from collections import Counter
from typing import TypedDict

from .config import settings
from .ml_models import cosine_sim_matrix, embed
from .text_utils import (
    content_words,
    extract_named_entities,
    split_sentences,
    tokenize,
)


# ── Lexical retrieval metrics ──────────────────────────────────────
def _relevant(query_tokens: set[str], doc: str) -> bool:
    overlap = len(query_tokens & set(tokenize(doc))) / max(len(query_tokens), 1)
    return overlap > settings.relevance_threshold


def precision_at_k(query: str, docs: list[str], k: int | None = None) -> float:
    k = k or settings.precision_k
    if not docs:
        return 0.0
    qt = set(tokenize(query))
    rel = sum(1 for d in docs[:k] if _relevant(qt, d))
    return round(rel / min(k, len(docs)), 4)


def recall_at_k(query: str, docs: list[str], k: int | None = None) -> float:
    k = k or settings.precision_k
    qt = set(tokenize(query))
    total = sum(1 for d in docs if _relevant(qt, d))
    if total == 0:
        return 0.0
    return round(sum(1 for d in docs[:k] if _relevant(qt, d)) / total, 4)


def f1_at_k(p: float, r: float) -> float:
    return round(2 * p * r / (p + r), 4) if p + r else 0.0


def mrr(query: str, docs: list[str]) -> float:
    qt = set(tokenize(query))
    for i, d in enumerate(docs, 1):
        if _relevant(qt, d):
            return round(1.0 / i, 4)
    return 0.0


def source_coverage(answer: str, docs: list[str]) -> float:
    ac = set(content_words(answer))
    hits = sum(1 for d in docs if len(ac & set(content_words(d))) >= 2)
    return round(hits / max(len(docs), 1), 4)


def rouge_l_vs_context(answer: str, ctx: str) -> float:
    pred, ref = tokenize(answer), tokenize(ctx)[:300]
    m, n = len(ref), len(pred)
    if not m or not n:
        return 0.0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            dp[i][j] = dp[i - 1][j - 1] + 1 if ref[i - 1] == pred[j - 1] \
                else max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[m][n]
    p, r = lcs / n, lcs / m
    return round(2 * p * r / (p + r), 4) if p + r else 0.0


def token_f1(a1: str, a2: str) -> tuple[float, float, float]:
    c1, c2 = Counter(tokenize(a1)), Counter(tokenize(a2))
    common = sum((c1 & c2).values())
    if not common:
        return 0.0, 0.0, 0.0
    p, r = common / len(tokenize(a1)), common / len(tokenize(a2))
    return round(2 * p * r / (p + r), 4), round(p, 4), round(r, 4)


def lexical_diversity(answer: str) -> float:
    t = tokenize(answer)
    return round(len(set(t)) / len(t), 4) if t else 0.0


def answer_length(answer: str) -> dict[str, int]:
    return {"total_tokens": len(tokenize(answer)),
            "content_tokens": len(content_words(answer))}


# ── Semantic grounding metrics ─────────────────────────────────────
class GroundingResult(TypedDict):
    hallucination_rate: float
    unsupported_sentences: list[str]
    context_utilization: float


def semantic_grounding(answer: str, docs: list[str]) -> GroundingResult:
    """
    Sentence-level grounding in a single embedding pass.

    For each answer sentence, take the max cosine similarity to any context
    sentence. Sentences below the support threshold are "unsupported"
    (hallucination); the fraction at/above it is context utilization.
    """
    sentences = split_sentences(answer)
    if not sentences or not docs:
        return {"hallucination_rate": 0.0, "unsupported_sentences": [],
                "context_utilization": 0.0}

    ctx_chunks: list[str] = []
    for d in docs:
        ctx_chunks.extend(split_sentences(d))
    if not ctx_chunks:
        return {"hallucination_rate": 1.0, "unsupported_sentences": sentences,
                "context_utilization": 0.0}

    sims = cosine_sim_matrix(embed(sentences), embed(ctx_chunks))
    max_sims = sims.max(axis=1)
    thr = settings.semantic_support_threshold
    unsupported = [sentences[i] for i, s in enumerate(max_sims) if s < thr]
    grounded = len(sentences) - len(unsupported)
    return {
        "hallucination_rate": round(len(unsupported) / len(sentences), 4),
        "unsupported_sentences": unsupported,
        "context_utilization": round(grounded / len(sentences), 4),
    }


def semantic_entity_grounding(answer: str, docs: list[str]) -> float:
    """Named entities in the answer must be semantically present in the context.

    Exact string matches count immediately; the rest fall back to embedding
    similarity so near-misses (e.g. "Modi" vs "Narendra Modi") still ground.
    """
    ne = extract_named_entities(answer)
    if not ne:
        return 1.0
    ctx_ne = extract_named_entities(" ".join(docs))
    if not ctx_ne:
        return 0.0
    lexical = ne & ctx_ne
    remaining = ne - lexical
    if not remaining:
        return 1.0
    sims = cosine_sim_matrix(embed(list(remaining)), embed(list(ctx_ne)))
    matched = int((sims.max(axis=1) >= settings.semantic_entity_threshold).sum())
    return round((len(lexical) + matched) / len(ne), 4)


# ── Composite ──────────────────────────────────────────────────────
def confidence_score(faith: float, consist: float, entity_g: float,
                     ctx_util: float, hallu: float) -> float:
    """Weighted composite in [0, 100]."""
    return round(min(
        faith * 30 + consist * 25 + entity_g * 20 + ctx_util * 15 + (1 - hallu) * 10,
        100,
    ), 1)
