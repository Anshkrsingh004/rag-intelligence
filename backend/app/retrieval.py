"""
Web retrieval: parallel DuckDuckGo search, a cheap lexical pre-filter, and a
real cross-encoder reranker for the final ordering.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ddgs import DDGS

from .config import settings
from .ml_models import get_reranker
from .text_utils import content_words, extract_named_entities, tokenize


def _fetch_one_query(query: str, max_results: int) -> list[dict]:
    results: list[dict] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "url": r["href"],
                    "content": r["body"],
                    "title": r.get("title", ""),
                    "query": query,
                })
    except Exception as e:  # noqa: BLE001 - search failures shouldn't crash a query
        print(f"    [!] Search error '{query}': {e}")
    return results


def _lexical_score(result: dict, q_words: set[str], q_ner: set[str]) -> float:
    content_tokens = set(tokenize(result["content"]))
    title_tokens = set(tokenize(result["title"]))
    doc_ner = extract_named_entities(result["content"] + " " + result["title"])
    # Title matches and named-entity matches are weighted more heavily.
    return len(q_words & content_tokens) + len(q_words & title_tokens) * 2 + len(q_ner & doc_ner) * 5


def retrieve_docs(
    queries: list[str],
    executor: ThreadPoolExecutor,
    max_per_query: int | None = None,
    use_reranker: bool = True,
) -> tuple[str, list[str]]:
    """
    Run every query in parallel, dedupe by URL, filter thin docs, then rank.

    Returns (context_string_for_prompt, raw_docs_for_scoring).
    """
    max_per_query = max_per_query or settings.docs_per_query
    seen: set[str] = set()
    all_results: list[dict] = []

    futures = {executor.submit(_fetch_one_query, q, max_per_query): q for q in queries}
    for future in as_completed(futures):
        for r in future.result():
            if r["url"] not in seen:
                seen.add(r["url"])
                all_results.append(r)

    all_results = [r for r in all_results
                   if len(content_words(r["content"])) >= settings.min_doc_words]
    if not all_results:
        return "", []

    main_query = queries[0]
    q_words = set(tokenize(main_query))
    q_ner = extract_named_entities(main_query)

    if use_reranker and len(all_results) > 1:
        # Coarse lexical pre-filter (cheap) -> cross-encoder rerank (accurate).
        for r in all_results:
            r["_prefilter"] = _lexical_score(r, q_words, q_ner)
        all_results.sort(key=lambda x: x["_prefilter"], reverse=True)
        pool = all_results[:settings.rerank_pool]
        try:
            reranker = get_reranker()
            scores = reranker.predict([(main_query, r["content"][:512]) for r in pool])
            for r, s in zip(pool, scores):
                r["score"] = float(s)
            pool.sort(key=lambda x: x["score"], reverse=True)
            top = pool[:settings.top_docs]
        except Exception as e:  # noqa: BLE001 - fall back to lexical if reranker fails
            print(f"    [!] Reranker unavailable ({e}); falling back to lexical scoring")
            top = pool[:settings.top_docs]
    else:
        for r in all_results:
            r["score"] = _lexical_score(r, q_words, q_ner)
        all_results.sort(key=lambda x: x["score"], reverse=True)
        top = all_results[:settings.top_docs]

    ctx_parts, raw_docs = [], []
    for i, r in enumerate(top, 1):
        ctx_parts.append(f"[Source {i}] {r['url']}\nTitle: {r['title']}\nContent: {r['content']}\n")
        raw_docs.append(r["content"] + " " + r["title"])
    return "\n".join(ctx_parts), raw_docs
