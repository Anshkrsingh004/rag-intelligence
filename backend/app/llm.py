"""Thin wrapper around the Groq chat API."""

from __future__ import annotations

from functools import lru_cache

from groq import Groq

from .config import require_api_key, settings


@lru_cache(maxsize=1)
def get_client() -> Groq:
    """Lazily construct a single shared Groq client (validates the key on first use)."""
    return Groq(api_key=require_api_key())


def ask_ai(
    prompt: str,
    system: str = "You are a helpful assistant.",
    temp: float = 0.1,
    model: str | None = None,
) -> str:
    """Send a single-turn chat completion and return the stripped text."""
    resp = get_client().chat.completions.create(
        model=model or settings.model_quality,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temp,
        max_tokens=settings.max_tokens,
    )
    return resp.choices[0].message.content.strip()
