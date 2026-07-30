"""
Pure text helpers: tokenizing, stopword filtering, sentence splitting, and
lightweight named-entity extraction. No external services, no side effects.
"""

from __future__ import annotations

import re

from .config import settings

_WORD_RE = re.compile(r"\b\w+\b")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
# Capitalized tokens not immediately following a sentence-ending period.
_ENTITY_RE = re.compile(r"(?<!\.\s)\b[A-Z][a-zA-Z]{2,}\b")


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def content_words(text: str) -> list[str]:
    return [w for w in tokenize(text) if w not in settings.stopwords and len(w) > 2]


def get_ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]


def extract_named_entities(text: str) -> set[str]:
    tokens = _ENTITY_RE.findall(text)
    return {t.lower() for t in tokens if t.lower() not in settings.stopwords}


def derive_title(text: str, limit: int = 60) -> str:
    """A conversation title from its first user message: collapsed whitespace,
    truncated at a word boundary with an ellipsis."""
    collapsed = " ".join(text.strip().split())
    if not collapsed:
        return "New chat"
    if len(collapsed) <= limit:
        return collapsed
    cut = collapsed[:limit].rsplit(" ", 1)[0].rstrip()
    return (cut or collapsed[:limit].rstrip()) + "…"


def is_complete_answer(answer: str) -> bool:
    """False when the answer dodges the question or is too thin — triggers a retry."""
    lowered = answer.lower()
    if any(p in lowered for p in settings.evasion_phrases):
        return False
    if len(content_words(answer)) < 5:
        return False
    return True
