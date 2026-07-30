# RAG Intelligence — Anti-Hallucination Chatbot (v8 — Semantic Faithfulness)

A domain-agnostic RAG chatbot comparing three AI systems side-by-side — Baseline LLM,
Hallucinating AI, and a grounded RAG pipeline — with live web search, **semantic**
hallucination detection, a cross-encoder reranker, faithfulness scoring, and a
confidence score out of 100. Built with Groq (LLaMA 3.3 70B), FastAPI & DuckDuckGo.

---

## What's new in v8

| v7 (lexical) | v8 (semantic) |
|---|---|
| Hallucination = % of answer words not appearing in retrieved text | Hallucination = % of answer **sentences** whose embedding has low cosine similarity to any context sentence — catches paraphrases (no longer falsely flagged) and wrong-but-same-vocabulary claims (no longer falsely passed) |
| Entity grounding = exact string match of capitalized words | Entity grounding = embedding similarity fallback for non-exact matches (e.g. "Modi" vs "Narendra Modi") |
| Doc reranking = hand-rolled token-overlap score | Doc reranking = real cross-encoder (`ms-marco-MiniLM-L-6-v2`) over a lexically pre-filtered candidate pool |
| Faithfulness score only | Faithfulness score **+ list of specific unsupported claims**, surfaced in the API response |
| API key hardcoded in source | API key loaded from `GROQ_API_KEY` environment variable |
| No reproducible benchmark | `eval_set.json` + `run_eval.py` + `compare_eval.py` give a frozen, reproducible before/after number |

---

## 📁 Project Files

```
your-project/
├── server.py               ← FastAPI backend (v8 — semantic scoring)
├── chatbotfrontend.html    ← Chatbot UI (open via http://localhost:8000)
├── eval_set.json           ← Frozen 20-question benchmark
├── run_eval.py             ← Hits the running server and logs metrics per question
├── compare_eval.py         ← Diffs two eval runs (e.g. v7 vs v8) for a before/after table
├── requirements.txt
└── README.md
```

---

## ⚡ Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```
First run downloads two small local models (~80MB each, cached after): the
embedding model (`all-MiniLM-L6-v2`) and the reranker (`ms-marco-MiniLM-L-6-v2`).
No extra API calls or cost — these run locally on CPU.

### 2. Set your Groq API key (never hardcode this)
```bash
export GROQ_API_KEY=your-groq-api-key-here     # Mac/Linux
setx GROQ_API_KEY your-groq-api-key-here        # Windows
```
Get a free key at: https://console.groq.com

### 3. Run the server
```bash
python server.py
```

### 4. Open in browser
```
http://localhost:8000
```

> ⚠️ Always open via http://localhost:8000 — NOT by double-clicking the HTML file.

---

## 📊 Getting your before/after hallucination-rate number

This is the part worth having ready for interviews — a real, reproducible number
instead of an anecdotal claim.

```bash
# 1. Run the eval against the old lexical pipeline
cp server.py server_v8_backup.py
cp server_v7_original.py server.py
GROQ_API_KEY=your-key python server.py &
python run_eval.py --out results_v7.json --label "v7-lexical"
kill %1

# 2. Run the eval against the new semantic pipeline
cp server_v8_backup.py server.py
GROQ_API_KEY=your-key python server.py &
python run_eval.py --out results_v8.json --label "v8-semantic"
kill %1

# 3. Compare
python compare_eval.py results_v7.json results_v8.json
```

`compare_eval.py` prints a metric-by-metric delta table plus the 5 questions
where hallucination rate moved the most — good concrete examples to walk an
interviewer through.

---

## 🤖 Three AI Panels

| Panel | Model | Description |
|-------|-------|-------------|
| 🎭 Hallucinating AI | llama-3.1-8b-instant | Overconfident, no grounding — shows what bad AI looks like |
| 🤖 Baseline LLM | llama-3.1-8b-instant | Parametric knowledge only, no live data |
| 🔬 RAG v8 Semantic | llama-3.3-70b-versatile | Live retrieval + cross-encoder reranking + embedding-based faithfulness scoring |

---

## 🔬 How It Works

```
User Query
    │
    ├── Query Analysis (LLM detects intent, generates search queries)
    │
    ├──► [PARALLEL] Hallucinating AI   → fast answer, no sources
    ├──► [PARALLEL] Baseline LLM       → parametric answer, no sources
    └──► [PARALLEL] RAG v8 Pipeline
              │
              ├── [PARALLEL] Primary retrieval (DuckDuckGo, 5 queries)
              │     └── Lexical pre-filter → cross-encoder reranker → top 5 docs
              ├── [PARALLEL] Verify retrieval (3 independent queries)
              ├── Answer generation (up to 2 retry passes)
              ├── [PARALLEL] Faithfulness judge (LLM, returns unsupported claims)
              ├── [PARALLEL] Consistency judge (LLM)
              ├── [PARALLEL] Semantic hallucination (local embeddings)
              ├── [PARALLEL] Semantic entity grounding (local embeddings)
              ├── [PARALLEL] Semantic context utilization (local embeddings)
              └── Confidence Score [0–100]
```

---

## 📊 Metrics Explained

| Metric | What it measures | Good score |
|--------|-----------------|------------|
| Confidence Score | Composite [0–100] | ≥ 72 (HIGH) |
| Faithfulness | LLM-judged claims supported by sources | ≥ 0.80 |
| Entity Grounding | Named entities semantically matched in context | ≥ 0.85 |
| Hallucination Rate ↓ | % of answer sentences below semantic-similarity threshold to context | ≤ 0.15 |
| Semantic Consistency | Primary vs verification agreement | ≥ 0.75 |
| Context Utilization | % of answer sentences semantically grounded in context | ≥ 0.70 |
| Precision@K | Top-K docs relevant to query | ≥ 0.70 |
| MRR | First relevant doc rank | ≥ 0.50 |

**Verdict thresholds:**
- ✅ HIGH CONFIDENCE   → score ≥ 72
- ⚠️ MEDIUM CONFIDENCE → score 45–71
- ❌ LOW CONFIDENCE    → score < 45

---

## 🌐 API Reference

**POST** `/query`
```json
{ "query": "Who is the current CM of Maharashtra?" }
```

Response (v8 adds `unsupported_sentences` / `unsupported_claims`):
```json
{
  "hallu_answer":     "...",
  "hallu_metrics":    { "length": {...}, "lexical_diversity": 0.79, "latency": 0.8 },
  "baseline_answer":  "...",
  "baseline_metrics": { "length": {...}, "lexical_diversity": 0.84, "latency": 0.9 },
  "rag_answer":       "...",
  "rag_metrics": {
    "confidence_score": 84.5,
    "hallucination_rate": 0.07,
    "unsupported_sentences": [],
    "unsupported_claims": [],
    "entity_grounding": 0.94,
    "faithfulness_score": 0.91,
    "consistency_score": 0.85,
    "scoring_method": "semantic_v8",
    "latency": 11.4,
    ...
  }
}
```

**GET** `/health`
```json
{ "status": "ok", "model_fast": "llama-3.1-8b-instant",
  "model_quality": "llama-3.3-70b-versatile", "version": "v8-semantic" }
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| `RuntimeError: GROQ_API_KEY not set` | Run `export GROQ_API_KEY=your-key` before starting the server |
| First query is slow (~10-15s extra) | Embedding + reranker models are downloading on first use; cached after that |
| Cards show "Backend Not Connected" | Backend is not running — run `python server.py` first |
| Groq API error | Check your API key at https://console.groq.com |

---

## 📚 Key References

- Lewis et al. (2020) — Retrieval-Augmented Generation (RAG)
- Es et al. (2023) — RAGAS evaluation framework
- Manakul et al. (2023) — SelfCheckGPT consistency scoring
- Asai et al. (2023) — Self-RAG
- Liu et al. (2023) — Lost in the Middle
- Reimers & Gurevych (2019) — Sentence-BERT (semantic similarity scoring basis)

---

## 📄 License
MIT — free to use, modify, and distribute.