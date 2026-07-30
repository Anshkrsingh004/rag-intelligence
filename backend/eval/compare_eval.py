"""
compare_eval.py — diff two eval runs and print before/after deltas.

Usage:
    python compare_eval.py results_before.json results_after.json
"""

from __future__ import annotations

import json
import sys


def load(path: str):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d["label"], {r["id"]: r for r in d["results"] if r.get("error") is None}


def avg(rows: list[dict], key: str) -> float:
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else 0.0


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python compare_eval.py results_before.json results_after.json")
        sys.exit(1)

    label_a, results_a = load(sys.argv[1])
    label_b, results_b = load(sys.argv[2])
    common = sorted(set(results_a) & set(results_b))
    rows_a = [results_a[i] for i in common]
    rows_b = [results_b[i] for i in common]

    metrics = ["hallucination_rate", "faithfulness_score", "consistency_score",
               "entity_grounding", "context_utilization", "confidence_score", "latency"]

    print(f"\nComparing '{label_a}' -> '{label_b}'  on {len(common)} shared questions\n")
    print(f"{'Metric':<22}{label_a:>12}{label_b:>12}{'Delta':>12}")
    print("-" * 58)
    for m in metrics:
        a, b = avg(rows_a, m), avg(rows_b, m)
        delta = b - a
        improved = (m == "hallucination_rate" and delta < 0) or (m != "hallucination_rate" and delta > 0)
        arrow = "improved" if improved and delta else ("worse" if delta else "same")
        print(f"{m:<22}{a:>12.3f}{b:>12.3f}{delta:>+12.3f}  {arrow}")

    print("\nBiggest per-question hallucination-rate changes:")
    diffs = []
    for i in common:
        ha, hb = results_a[i].get("hallucination_rate"), results_b[i].get("hallucination_rate")
        if ha is not None and hb is not None:
            diffs.append((abs(hb - ha), i, results_a[i]["query"], ha, hb))
    diffs.sort(reverse=True)
    for _, i, q, ha, hb in diffs[:5]:
        print(f"  [{i}] {q}\n        {label_a}={ha:.3f}  ->  {label_b}={hb:.3f}")


if __name__ == "__main__":
    main()
