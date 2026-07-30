"""
LLM-as-judge scorers, the query-analysis planner, and title generation.

  * faithfulness  — strict judge, returns a score AND the specific unsupported claims.
  * consistency   — compares the primary answer against an independent verification answer.
  * analyse_query — turns a question into a retrieval strategy (cached per query).
  * generate_title — a short conversation title from its first message.
"""

from __future__ import annotations

import re

from .config import settings
from .llm import ask_ai
from .text_utils import derive_title

_SCORE_RE = re.compile(r"SCORE:\s*([0-9.]+)")
_PRIMARY_RE = re.compile(r"PRIMARY_QUERY_\d+:")
_TITLE_PREFIX_RE = re.compile(r"^(chat\s+)?title\s*[:\-]\s*", re.IGNORECASE)
_VERIFY_RE = re.compile(r"VERIFY_QUERY_\d+:")


def faithfulness(answer: str, ctx: str, answer_type: str = "factual answer") -> tuple[float, list[str]]:
    prompt = f"""Evaluate faithfulness. Answer type: {answer_type}
CONTEXT: {ctx[:2000]}
ANSWER: {answer}
List each distinct claim in the answer on its own line as "CLAIM: <claim> | SUPPORTED: yes/no".
Then on a final line give:
SCORE: [0.00 to 1.00]"""
    result = ask_ai(prompt, "You are a strict faithfulness evaluator.", temp=0.0)
    m = _SCORE_RE.search(result)
    score = round(min(float(m.group(1)) if m else 0.5, 1.0), 4)

    unsupported: list[str] = []
    for line in result.splitlines():
        upper = line.strip().upper()
        if upper.startswith("CLAIM:") and "SUPPORTED: NO" in upper:
            claim = line.split("|")[0].replace("CLAIM:", "").replace("claim:", "").strip()
            if claim:
                unsupported.append(claim)
    return score, unsupported


def consistency(a1: str, a2: str, answer_type: str = "factual answer") -> float:
    prompt = f"""Compare two answers. Type: {answer_type}
Different {answer_type}s = none = 0.0
A: {a1}
B: {a2}
SCORE: [1.0 / 0.6 / 0.0]"""
    result = ask_ai(prompt, "You are a strict consistency judge.", temp=0.0)
    m = _SCORE_RE.search(result)
    return round(min(float(m.group(1)) if m else 0.5, 1.0), 4)


# ── Title generation ───────────────────────────────────────────────
def generate_title(first_message: str) -> str:
    """A concise LLM-generated conversation title from its first message.

    Uses the fast model; on any failure or empty result, falls back to a
    truncated version of the message so a title is always returned.
    """
    prompt = (
        "Write a concise 3-6 word title summarizing a chat that starts with the "
        "message below. Reply with ONLY the title — no quotes, no punctuation, no prefix.\n\n"
        f"MESSAGE: {first_message.strip()[:400]}"
    )
    try:
        raw = ask_ai(prompt, "You generate short, specific chat titles.",
                     temp=0.2, model=settings.model_fast)
        title = raw.strip().strip('"\'').splitlines()[0].strip()
        title = _TITLE_PREFIX_RE.sub("", title).strip().rstrip(".")
        if title:
            return derive_title(title, 60)  # clamp length, collapse whitespace
    except Exception as e:  # noqa: BLE001 - titling must never break saving a message
        print(f"    [!] Title generation failed: {e}")
    return derive_title(first_message)


# ── Query analysis (planner) with an in-process cache ──────────────
_analysis_cache: dict[str, dict] = {}


def analyse_query(query: str) -> dict:
    key = query.strip().lower()
    if key in _analysis_cache:
        print("  [Cache HIT] query analysis reused")
        return _analysis_cache[key]

    prompt = f"""Analyse and produce a search strategy.
QUESTION: {query}
INTENT: [one word]
ANSWER_TYPE: [what kind of answer]
ANSWER_FORMAT: [how to phrase the answer]
PRIMARY_QUERY_1: [direct search]
PRIMARY_QUERY_2: [official source angle]
PRIMARY_QUERY_3: [recent news angle]
PRIMARY_QUERY_4: [alternate phrasing]
PRIMARY_QUERY_5: [key entities + latest]
VERIFY_QUERY_1: [independent check 1]
VERIFY_QUERY_2: [independent check 2]
VERIFY_QUERY_3: [independent check 3]"""
    raw = ask_ai(prompt, "Output ONLY the structured format. No extra text.", temp=0.0)

    result = {
        "intent_label": "general",
        "answer_type": "factual answer",
        "answer_format": "Direct factual statement",
        "primary_queries": [],
        "verify_queries": [],
    }
    for line in raw.strip().splitlines():
        line = line.strip()
        if line.startswith("INTENT:"):
            result["intent_label"] = line.split(":", 1)[1].strip().lower()
        elif line.startswith("ANSWER_TYPE:"):
            result["answer_type"] = line.split(":", 1)[1].strip()
        elif line.startswith("ANSWER_FORMAT:"):
            result["answer_format"] = line.split(":", 1)[1].strip()
        elif _PRIMARY_RE.match(line):
            q = line.split(":", 1)[1].strip()
            if q:
                result["primary_queries"].append(q)
        elif _VERIFY_RE.match(line):
            q = line.split(":", 1)[1].strip()
            if q:
                result["verify_queries"].append(q)

    if not result["primary_queries"]:
        result["primary_queries"] = [query, f"{query} latest", f"{query} official",
                                     f"{query} current", f"{query} facts"]
    if not result["verify_queries"]:
        result["verify_queries"] = [f"{query} verified", f"{query} news", f"latest {query}"]

    _analysis_cache[key] = result
    return result
