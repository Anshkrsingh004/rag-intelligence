"""
run_eval.py — Frozen benchmark harness for RAG Intelligence

Hits your running server's /query endpoint for every question in eval_set.json,
collects the RAG pipeline's metrics, and writes a results file + summary report.

Usage:
    1. Start your server in one terminal:   python server.py
    2. Run this in another terminal:        python run_eval.py --out results_v8.json --label v8

To get the before/after number for your resume/interviews:
    1. Run this against server_v7_original.py -> results_v7.json
    2. Run this against server.py (v8)         -> results_v8.json
    3. Run:  python compare_eval.py results_v7.json results_v8.json
"""

import json, time, argparse, sys
import urllib.request

def call_server(base_url: str, query: str) -> dict:
    url = f"{base_url}/query"
    data = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval_set", default="eval_set.json")
    ap.add_argument("--base_url", default="http://localhost:8000")
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--label", default="run")
    args = ap.parse_args()

    with open(args.eval_set) as f:
        questions = json.load(f)

    results = []
    print(f"Running {len(questions)} eval questions against {args.base_url} ...")
    for q in questions:
        print(f"  [{q['id']}/{len(questions)}] {q['query']}")
        t0 = time.time()
        try:
            resp = call_server(args.base_url, q["query"])
            rag_metrics = resp.get("rag_metrics", {})
            results.append({
                "id": q["id"], "query": q["query"], "category": q.get("category", "general"),
                "rag_answer": resp.get("rag_answer", ""),
                "hallucination_rate": rag_metrics.get("hallucination_rate"),
                "faithfulness_score": rag_metrics.get("faithfulness_score"),
                "consistency_score": rag_metrics.get("consistency_score"),
                "entity_grounding": rag_metrics.get("entity_grounding"),
                "context_utilization": rag_metrics.get("context_utilization"),
                "confidence_score": rag_metrics.get("confidence_score"),
                "unsupported_sentences": rag_metrics.get("unsupported_sentences", []),
                "latency": rag_metrics.get("latency"),
                "wall_time": round(time.time() - t0, 2),
                "error": None,
            })
        except Exception as e:
            print(f"    [!] Error: {e}")
            results.append({"id": q["id"], "query": q["query"], "error": str(e)})

    with open(args.out, "w") as f:
        json.dump({"label": args.label, "results": results}, f, indent=2)

    valid = [r for r in results if r.get("error") is None]
    if valid:
        avg_hallu  = sum(r["hallucination_rate"] for r in valid) / len(valid)
        avg_faith  = sum(r["faithfulness_score"] for r in valid) / len(valid)
        avg_conf   = sum(r["confidence_score"] for r in valid) / len(valid)
        avg_lat    = sum(r["latency"] for r in valid) / len(valid)
        print("\n" + "="*50)
        print(f"  SUMMARY — {args.label}  ({len(valid)}/{len(questions)} succeeded)")
        print(f"  Avg hallucination rate : {avg_hallu:.3f}")
        print(f"  Avg faithfulness score : {avg_faith:.3f}")
        print(f"  Avg confidence score   : {avg_conf:.1f}")
        print(f"  Avg latency (s)        : {avg_lat:.2f}")
        print("="*50)
    print(f"\nSaved -> {args.out}")

if __name__ == "__main__":
    main()