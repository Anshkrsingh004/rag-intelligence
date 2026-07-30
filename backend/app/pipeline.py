"""
Orchestration: the three AI panels and the metric assembly for the RAG panel.

  * Baseline      — fast model, parametric knowledge, admits uncertainty.
  * Hallucinating — fast model, high temperature, never admits uncertainty.
  * RAG           — retrieve -> generate (with retries) -> verify -> score.

Everything that can run concurrently does, via a shared thread pool.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from . import judges, metrics
from .config import settings
from .llm import ask_ai
from .retrieval import retrieve_docs
from .text_utils import is_complete_answer

executor = ThreadPoolExecutor(max_workers=settings.max_workers)


# ── Answer generation ──────────────────────────────────────────────
def _gen_answer(query: str, ctx: str, fmt: str = "Direct factual statement", pass_num: int = 1) -> str:
    system = ("You are a precise factual assistant. Use ONLY the provided context. "
              "NEVER invent names, numbers, or facts. Cite as [Source N].")
    if pass_num == 1:
        prompt = (f"Answer ONLY from sources below.\nExpected format: {fmt}\n"
                  f"SOURCES:\n{ctx}\nQUESTION: {query}\nANSWER:")
    elif pass_num == 2:
        prompt = (f"Scan all sources. Extract answer.\nFormat: {fmt}\n"
                  f"SOURCES:\n{ctx}\nQUESTION: {query}\nANSWER:")
    else:
        prompt = (f"Last attempt. If insufficient prefix with "
                  f"'⚠️ Training knowledge (VERIFY ONLINE):'\n"
                  f"SOURCES:\n{ctx}\nQUESTION: {query}\nANSWER:")
    return ask_ai(prompt, system, temp=0.0 if pass_num > 1 else 0.05)


# ── Panel runners ──────────────────────────────────────────────────
def run_baseline(query: str) -> tuple[str, dict]:
    t0 = time.time()
    ans = ask_ai(
        query,
        "You are a helpful assistant. Answer from training knowledge. Admit uncertainty.",
        temp=0.1, model=settings.model_fast,
    )
    return ans, {
        "length": metrics.answer_length(ans),
        "lexical_diversity": metrics.lexical_diversity(ans),
        "latency": round(time.time() - t0, 2),
    }


def run_hallucinating(query: str) -> tuple[str, dict]:
    t0 = time.time()
    ans = ask_ai(
        query,
        "You are an overconfident bot. Never admit uncertainty. "
        "Always give a specific confident answer.",
        temp=0.9, model=settings.model_fast,
    )
    return ans, {
        "length": metrics.answer_length(ans),
        "lexical_diversity": metrics.lexical_diversity(ans),
        "latency": round(time.time() - t0, 2),
    }


def run_rag(query: str, analysis: dict) -> tuple[str, dict, list[str]]:
    t0 = time.time()

    # Primary + verification retrieval in parallel.
    f_primary = executor.submit(retrieve_docs, analysis["primary_queries"], executor,
                                settings.docs_per_query, True)
    f_verify = executor.submit(retrieve_docs, analysis["verify_queries"], executor, 2, False)
    ctx, raw = f_primary.result()
    vctx, vdocs = f_verify.result()

    # Generate the grounded answer, retrying if it dodges the question.
    ans, passes = None, 0
    for p in range(1, settings.max_retries + 1):
        candidate = _gen_answer(query, ctx, analysis["answer_format"], p)
        passes = p
        if is_complete_answer(candidate):
            ans = candidate
            break
    if ans is None:
        ans = candidate
    v_ans = _gen_answer(query, vctx, analysis["answer_format"], 1)

    # Scoring — LLM judges and semantic grounding run concurrently.
    f_faith = executor.submit(judges.faithfulness, ans, ctx, analysis["answer_type"])
    f_consist = executor.submit(judges.consistency, ans, v_ans, analysis["answer_type"])
    f_ground = executor.submit(metrics.semantic_grounding, ans, raw)
    f_entity = executor.submit(metrics.semantic_entity_grounding, ans, raw)

    faith, unsupported_claims = f_faith.result()
    consist = f_consist.result()
    ground = f_ground.result()
    entity_g = f_entity.result()

    hallu = ground["hallucination_rate"]
    ctx_util = ground["context_utilization"]

    p_k = metrics.precision_at_k(query, raw)
    r_k = metrics.recall_at_k(query, raw)
    tf1, tp, tr = metrics.token_f1(ans, v_ans)

    result_metrics = {
        "precision_at_k": p_k,
        "recall_at_k": r_k,
        "f1_at_k": metrics.f1_at_k(p_k, r_k),
        "mrr": metrics.mrr(query, raw),
        "source_coverage": metrics.source_coverage(ans, raw),
        "context_utilization": ctx_util,
        "hallucination_rate": hallu,
        "unsupported_sentences": ground["unsupported_sentences"],
        "unsupported_claims": unsupported_claims,
        "entity_grounding": entity_g,
        "rouge_l_vs_context": metrics.rouge_l_vs_context(ans, ctx),
        "token_f1": tf1, "token_precision": tp, "token_recall": tr,
        "lexical_diversity": metrics.lexical_diversity(ans),
        "answer_length": metrics.answer_length(ans),
        "faithfulness_score": faith,
        "consistency_score": consist,
        "confidence_score": metrics.confidence_score(faith, consist, entity_g, ctx_util, hallu),
        "docs_primary": len(raw),
        "docs_verify": len(vdocs),
        "passes_used": passes,
        "latency": round(time.time() - t0, 2),
        "intent": analysis["intent_label"],
        "answer_type": analysis["answer_type"],
        "scoring_method": "semantic_v9",
    }
    return ans, result_metrics, raw


def run_all(query: str) -> dict:
    """Run all three panels concurrently and return the combined payload."""
    t_total = time.time()
    analysis = judges.analyse_query(query)

    f_base = executor.submit(run_baseline, query)
    f_hallu = executor.submit(run_hallucinating, query)
    f_rag = executor.submit(run_rag, query, analysis)

    base_ans, base_met = f_base.result()
    hallu_ans, hallu_met = f_hallu.result()
    rag_ans, rag_met, raw = f_rag.result()

    # Fair grounding comparison: score the ungrounded answers (baseline +
    # hallucinating) against the SAME retrieved evidence the RAG answer used.
    # This is what makes the "ungrounded vs grounded" hallucination number honest.
    base_met["hallucination_rate"] = (
        metrics.semantic_grounding(base_ans, raw)["hallucination_rate"] if raw else None
    )
    hallu_met["hallucination_rate"] = (
        metrics.semantic_grounding(hallu_ans, raw)["hallucination_rate"] if raw else None
    )

    print(f"  [Total wall time] {round(time.time() - t_total, 2)}s")
    return {
        "baseline_answer": base_ans, "baseline_metrics": base_met,
        "hallu_answer": hallu_ans, "hallu_metrics": hallu_met,
        "rag_answer": rag_ans, "rag_metrics": rag_met,
    }
