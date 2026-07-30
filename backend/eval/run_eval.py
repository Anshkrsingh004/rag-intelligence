"""
run_eval.py — frozen benchmark harness for RAG Intelligence.

Hits a running server's /api/query endpoint for every question in
eval_set.json, records the RAG panel's metrics, and writes a results file
plus a summary. Two runs (e.g. before/after a change) can be diffed with
compare_eval.py to produce a real, reproducible hallucination-rate delta.

Usage:
    # terminal 1
    cd backend && python run.py
    # terminal 2
    cd backend/eval && python run_eval.py --out results_v9.json --label v9
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def call_server(base_url: str, query: str, timeout: int = 90) -> dict:
    url = f"{base_url}/api/query"
    data = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval_set", default=str(HERE / "eval_set.json"))
    ap.add_argument("--base_url", default="http://localhost:8000")
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--label", default="run")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="Seconds to pause between questions (avoids search rate-limiting).")
    args = ap.parse_args()

    with open(args.eval_set, encoding="utf-8") as f:
        questions = json.load(f)

    results = []
    print(f"Running {len(questions)} eval questions against {args.base_url} ...")
    for i, q in enumerate(questions):
        if i and args.delay:
            time.sleep(args.delay)
        print(f"  [{q['id']:>2}/{len(questions)}] {q['query']}")
        t0 = time.time()
        try:
            resp = call_server(args.base_url, q["query"])
            m = resp.get("rag_metrics", {})
            base_m = resp.get("baseline_metrics", {})
            hallu_m = resp.get("hallu_metrics", {})
            results.append({
                "id": q["id"], "query": q["query"], "category": q.get("category", "general"),
                "rag_answer": resp.get("rag_answer", ""),
                # Hallucination rate of each panel, scored vs the same retrieved evidence.
                "rag_hallucination": m.get("hallucination_rate"),
                "baseline_hallucination": base_m.get("hallucination_rate"),
                "hallu_hallucination": hallu_m.get("hallucination_rate"),
                "hallucination_rate": m.get("hallucination_rate"),  # kept for compare_eval
                "faithfulness_score": m.get("faithfulness_score"),
                "consistency_score": m.get("consistency_score"),
                "entity_grounding": m.get("entity_grounding"),
                "context_utilization": m.get("context_utilization"),
                "confidence_score": m.get("confidence_score"),
                "unsupported_sentences": m.get("unsupported_sentences", []),
                "latency": m.get("latency"),
                "wall_time": round(time.time() - t0, 2),
                "error": None,
            })
        except Exception as e:  # noqa: BLE001
            print(f"      [!] Error: {e}")
            results.append({"id": q["id"], "query": q["query"], "error": str(e)})

    out_path = args.out if Path(args.out).is_absolute() else str(HERE / args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"label": args.label, "results": results}, f, indent=2)

    valid = [r for r in results if r.get("error") is None]
    if valid:
        def avg(key: str) -> float:
            vals = [r[key] for r in valid if r.get(key) is not None]
            return sum(vals) / len(vals) if vals else 0.0

        base_h = avg("baseline_hallucination")
        hallu_h = avg("hallu_hallucination")
        rag_h = avg("rag_hallucination")
        reduction = (1 - rag_h / base_h) * 100 if base_h else 0.0

        print("\n" + "=" * 60)
        print(f"  SUMMARY - {args.label}  ({len(valid)}/{len(questions)} succeeded)")
        print("  " + "-" * 56)
        print("  Avg hallucination rate (vs the same retrieved evidence):")
        print(f"     Hallucinating AI : {hallu_h:.3f}")
        print(f"     Baseline LLM     : {base_h:.3f}   (ungrounded)")
        print(f"     RAG pipeline     : {rag_h:.3f}   (grounded)")
        print(f"  -> RAG cuts hallucination {base_h:.3f} -> {rag_h:.3f}  "
              f"({reduction:.0f}% lower than ungrounded)")
        print("  " + "-" * 56)
        print(f"  Avg RAG faithfulness   : {avg('faithfulness_score'):.3f}")
        print(f"  Avg RAG confidence     : {avg('confidence_score'):.1f} / 100")
        print(f"  Avg latency (s)        : {avg('latency'):.2f}")
        print("=" * 60)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
