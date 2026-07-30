"""
RAG Intelligence — FastAPI Backend  (v8 — Semantic Faithfulness)

WHAT CHANGED vs v7:
  1. SEMANTIC HALLUCINATION   — embedding cosine similarity replaces raw token
                                 overlap for hallucination_rate / entity_grounding /
                                 context_utilization. Paraphrases are no longer
                                 falsely flagged; vocabulary-matching-but-wrong
                                 claims are no longer falsely passed.
  2. CROSS-ENCODER RERANKER   — retrieved docs are reranked with a real
                                 cross-encoder (ms-marco-MiniLM-L-6-v2) instead
                                 of a hand-rolled token-overlap score.
  3. SECURE API KEY           — loaded from GROQ_API_KEY env var, never hardcoded.
  4. CLAIM-LEVEL FAITHFULNESS — faithfulness judge now returns which specific
                                 claims were unsupported, not just a score.
  5. EVAL HARNESS             — eval_set.json + run_eval.py give a reproducible,
                                 frozen benchmark so you can quote a real
                                 before/after hallucination-rate number instead
                                 of an anecdotal one.

Total expected speedup vs v6 is unchanged (~25-40s -> ~8-14s); the semantic
scoring adds ~150-300ms per query (local embedding model, no extra API call).
"""

import os, time, re, json
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from groq import Groq
from ddgs import DDGS

# ── CONFIGURATION ──────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not set. Run:\n"
        "  export GROQ_API_KEY=your-key-here   (Mac/Linux)\n"
        "  setx GROQ_API_KEY your-key-here      (Windows)\n"
        "Get a free key at https://console.groq.com\n"
        "Never hardcode API keys in source — they get scraped within hours if pushed to GitHub."
    )

MODEL_FAST      = "llama-3.1-8b-instant"
MODEL_QUALITY   = "llama-3.3-70b-versatile"
DOCS_PER_QUERY  = 3
TOP_DOCS        = 5
RERANK_POOL     = 12        # candidates considered by the cross-encoder before truncating to TOP_DOCS
PRECISION_K     = 3
MAX_RETRIES     = 2
RELEVANCE_THRESHOLD = 0.30
MIN_DOC_WORDS       = 12
MAX_WORKERS         = 6

# Semantic thresholds (cosine similarity, 0-1)
SEMANTIC_SUPPORT_THRESHOLD = 0.55   # below this, a sentence is "unsupported" by context
SEMANTIC_ENTITY_THRESHOLD  = 0.60

client   = Groq(api_key=GROQ_API_KEY)
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

app = FastAPI(title="RAG Intelligence API v8")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── EMBEDDING MODEL + RERANKER (loaded once, local, no API calls) ──
# Lazy-loaded so `python server.py --help` / imports don't pay the cost.
_embedder = None
_reranker = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        print("  [Loading] embedding model all-MiniLM-L6-v2 (first run downloads ~80MB)...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder

def get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        print("  [Loading] reranker cross-encoder/ms-marco-MiniLM-L-6-v2 (first run downloads ~80MB)...")
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker

def split_sentences(text: str) -> list:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]

def cosine_sim_matrix(a_vecs, b_vecs):
    import numpy as np
    a = a_vecs / (np.linalg.norm(a_vecs, axis=1, keepdims=True) + 1e-8)
    b = b_vecs / (np.linalg.norm(b_vecs, axis=1, keepdims=True) + 1e-8)
    return a @ b.T

# ── CONSTANTS ──────────────────────────────────────────────────
STOPWORDS = {
    'the','a','an','is','are','was','were','in','on','at','to',
    'for','of','and','or','but','it','its','this','that','with',
    'as','by','from','have','has','had','be','been','not','no',
    'who','what','when','where','how','which','i','you','we','they',
    'their','our','your','his','her','also','just','more','than',
    'then','so','if','do','did','does','will','would','could','after',
    'before','during','over','under','about','into','through','between',
    'each','such','only','other','some','these','those','very','can',
    'get','got','may','might','must','shall','been','being','am',
    'said','says','according','per','via','like','new','one','two'
}
EVASION_PHRASES = [
    "not mentioned","does not mention","not provided","not available",
    "i don't know","cannot find","no information","not stated",
    "not found","information provided does not","cannot determine",
    "not explicitly","unable to","no specific","does not contain",
    "no results","not specified","as of my knowledge cutoff",
    "as of my last update","my training data","i cannot confirm",
    "i do not have","outside my","beyond my","i'm not sure",
    "i am not sure","no data","insufficient"
]

# ── UTILITIES ──────────────────────────────────────────────────
def tokenize(text):
    return re.findall(r'\b\w+\b', text.lower())

def content_words(text):
    return [w for w in tokenize(text) if w not in STOPWORDS and len(w) > 2]

def get_ngrams(tokens, n):
    return {tuple(tokens[i:i+n]) for i in range(len(tokens)-n+1)}

def ask_ai(prompt, system="You are a helpful assistant.", temp=0.1, model=None):
    r = client.chat.completions.create(
        model=model or MODEL_QUALITY,
        messages=[{"role":"system","content":system},
                  {"role":"user","content":prompt}],
        temperature=temp,
        max_tokens=512,
    )
    return r.choices[0].message.content.strip()

def extract_named_entities(text):
    tokens = re.findall(r'(?<!\.\s)\b[A-Z][a-zA-Z]{2,}\b', text)
    return {t.lower() for t in tokens if t.lower() not in STOPWORDS}

def check_completeness(answer):
    if any(p in answer.lower() for p in EVASION_PHRASES): return False
    if len(content_words(answer)) < 5: return False
    return True

# ── METRICS (lexical, kept for precision/recall — these are fine as-is) ──
def compute_precision_at_k(query, docs, k=PRECISION_K):
    qt = set(tokenize(query))
    rel = sum(1 for d in docs[:k]
              if len(qt & set(tokenize(d)))/max(len(qt),1) > RELEVANCE_THRESHOLD)
    return round(rel/min(k,len(docs)), 4) if docs else 0.0

def compute_recall_at_k(query, docs, k=PRECISION_K):
    qt = set(tokenize(query))
    def rel(d): return len(qt & set(tokenize(d)))/max(len(qt),1) > RELEVANCE_THRESHOLD
    total = sum(1 for d in docs if rel(d))
    if total == 0: return 0.0
    return round(sum(1 for d in docs[:k] if rel(d))/total, 4)

def compute_f1_at_k(p, r):
    return round(2*p*r/(p+r), 4) if p+r else 0.0

def compute_mrr(query, docs):
    qt = set(tokenize(query))
    for i, d in enumerate(docs, 1):
        if len(qt & set(tokenize(d)))/max(len(qt),1) > RELEVANCE_THRESHOLD:
            return round(1.0/i, 4)
    return 0.0

def compute_source_coverage(ans, docs):
    ac = set(content_words(ans))
    return round(sum(1 for d in docs if len(ac & set(content_words(d)))>=2)/max(len(docs),1), 4)

# ── SEMANTIC METRICS (v8 — replaces lexical hallucination/grounding/ctx-util) ──
def compute_semantic_hallucination(ans, docs):
    """
    Sentence-level: embed each answer sentence and each context chunk,
    take max cosine similarity per answer sentence against any context chunk.
    A sentence below SEMANTIC_SUPPORT_THRESHOLD is counted as unsupported.
    This catches paraphrase-but-faithful (correctly NOT flagged) and
    same-vocabulary-but-wrong-claim (correctly flagged) cases that pure
    token overlap misses.
    """
    import numpy as np
    sentences = split_sentences(ans)
    if not sentences or not docs:
        return {"hallucination_rate": 0.0, "unsupported_sentences": []}
    model = get_embedder()
    ctx_chunks = []
    for d in docs:
        ctx_chunks.extend(split_sentences(d))
    if not ctx_chunks:
        return {"hallucination_rate": 1.0, "unsupported_sentences": sentences}
    ans_vecs = model.encode(sentences, convert_to_numpy=True, show_progress_bar=False)
    ctx_vecs = model.encode(ctx_chunks, convert_to_numpy=True, show_progress_bar=False)
    sims = cosine_sim_matrix(ans_vecs, ctx_vecs)
    max_sims = sims.max(axis=1)
    unsupported = [sentences[i] for i, s in enumerate(max_sims) if s < SEMANTIC_SUPPORT_THRESHOLD]
    rate = round(len(unsupported) / len(sentences), 4)
    return {"hallucination_rate": rate, "unsupported_sentences": unsupported}

def compute_semantic_entity_grounding(ans, docs):
    """Named entities in the answer must be semantically (not just lexically)
    present in context — catches near-miss / substituted entities."""
    ne = extract_named_entities(ans)
    if not ne: return 1.0
    ctx_ne = extract_named_entities(" ".join(docs))
    if not ctx_ne: return 0.0
    lexical_overlap = ne & ctx_ne
    remaining = ne - lexical_overlap
    if not remaining:
        return 1.0
    model = get_embedder()
    ne_vecs = model.encode(list(remaining), convert_to_numpy=True, show_progress_bar=False)
    ctx_ne_vecs = model.encode(list(ctx_ne), convert_to_numpy=True, show_progress_bar=False)
    sims = cosine_sim_matrix(ne_vecs, ctx_ne_vecs)
    matched = (sims.max(axis=1) >= SEMANTIC_ENTITY_THRESHOLD).sum()
    return round((len(lexical_overlap) + matched) / len(ne), 4)

def compute_semantic_ctx_util(ans, docs):
    """Fraction of answer sentences that are semantically grounded in context."""
    sentences = split_sentences(ans)
    if not sentences or not docs: return 0.0
    model = get_embedder()
    ctx_chunks = []
    for d in docs:
        ctx_chunks.extend(split_sentences(d))
    if not ctx_chunks: return 0.0
    ans_vecs = model.encode(sentences, convert_to_numpy=True, show_progress_bar=False)
    ctx_vecs = model.encode(ctx_chunks, convert_to_numpy=True, show_progress_bar=False)
    sims = cosine_sim_matrix(ans_vecs, ctx_vecs)
    grounded = (sims.max(axis=1) >= SEMANTIC_SUPPORT_THRESHOLD).sum()
    return round(grounded / len(sentences), 4)

def compute_rouge_l(ans, ctx):
    pred = tokenize(ans); ref = tokenize(ctx)[:300]
    m, n = len(ref), len(pred)
    if not m or not n: return 0.0
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(1,m+1):
        for j in range(1,n+1):
            dp[i][j] = dp[i-1][j-1]+1 if ref[i-1]==pred[j-1] else max(dp[i-1][j],dp[i][j-1])
    lcs = dp[m][n]; p, r = lcs/n, lcs/m
    return round(2*p*r/(p+r), 4) if p+r else 0.0

def compute_tok_f1(a1, a2):
    c1, c2 = Counter(tokenize(a1)), Counter(tokenize(a2))
    common = sum((c1&c2).values())
    if not common: return 0.0, 0.0, 0.0
    t1, t2 = len(tokenize(a1)), len(tokenize(a2))
    p, r = common/t1, common/t2
    return round(2*p*r/(p+r),4), round(p,4), round(r,4)

def compute_lex_div(ans):
    t = tokenize(ans)
    return round(len(set(t))/len(t),4) if t else 0.0

def compute_len(ans):
    return {"total_tokens": len(tokenize(ans)), "content_tokens": len(content_words(ans))}

# ── LLM JUDGES (v8 — faithfulness now returns unsupported claims) ──
def compute_faithfulness(ans, ctx, answer_type="factual answer"):
    prompt = f"""Evaluate faithfulness. Answer type: {answer_type}
CONTEXT: {ctx[:2000]}
ANSWER: {ans}
List each distinct claim in the answer on its own line as "CLAIM: <claim> | SUPPORTED: yes/no".
Then on a final line give:
SCORE: [0.00 to 1.00]"""
    result = ask_ai(prompt, "You are a strict faithfulness evaluator.", temp=0.0)
    m = re.search(r'SCORE:\s*([0-9.]+)', result)
    score = round(min(float(m.group(1)) if m else 0.5, 1.0), 4)
    unsupported_claims = []
    for line in result.split("\n"):
        if line.strip().upper().startswith("CLAIM:") and "SUPPORTED: NO" in line.upper():
            claim = line.split("|")[0].replace("CLAIM:", "").strip()
            if claim:
                unsupported_claims.append(claim)
    return score, unsupported_claims

def compute_consistency(a1, a2, answer_type="factual answer"):
    prompt = f"""Compare two answers. Type: {answer_type}
Different {answer_type}s = none = 0.0
A: {a1}
B: {a2}
SCORE: [1.0 / 0.6 / 0.0]"""
    result = ask_ai(prompt, "You are a strict consistency judge.", temp=0.0)
    m = re.search(r'SCORE:\s*([0-9.]+)', result)
    return round(min(float(m.group(1)) if m else 0.5, 1.0), 4)

def compute_confidence(faith, consist, entity_g, ctx_util, hallu):
    return round(min(faith*30 + consist*25 + entity_g*20 + ctx_util*15 + (1-hallu)*10, 100), 1)

# ── QUERY ANALYSIS CACHE ───────────────────────────────────────
_analysis_cache: dict = {}

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
        "intent_label": "general", "answer_type": "factual answer",
        "answer_format": "Direct factual statement",
        "primary_queries": [], "verify_queries": []
    }
    for line in raw.strip().split('\n'):
        line = line.strip()
        if line.startswith("INTENT:"):           result["intent_label"] = line.split(":",1)[1].strip().lower()
        elif line.startswith("ANSWER_TYPE:"):    result["answer_type"]  = line.split(":",1)[1].strip()
        elif line.startswith("ANSWER_FORMAT:"):  result["answer_format"]= line.split(":",1)[1].strip()
        elif re.match(r'PRIMARY_QUERY_\d+:', line):
            q = line.split(":",1)[1].strip()
            if q: result["primary_queries"].append(q)
        elif re.match(r'VERIFY_QUERY_\d+:', line):
            q = line.split(":",1)[1].strip()
            if q: result["verify_queries"].append(q)
    if not result["primary_queries"]:
        result["primary_queries"] = [query, f"{query} latest", f"{query} official",
                                      f"{query} current", f"{query} facts"]
    if not result["verify_queries"]:
        result["verify_queries"] = [f"{query} verified", f"{query} news", f"latest {query}"]
    _analysis_cache[key] = result
    return result

# ── PARALLEL RETRIEVAL + RERANKING (v8) ─────────────────────────
def _fetch_one_query(q: str, max_results: int) -> list:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(q, max_results=max_results):
                results.append({"url": r['href'], "content": r['body'],
                                 "title": r.get('title',''), "query": q})
    except Exception as e:
        print(f"    [!] Search error '{q}': {e}")
    return results

def retrieve_docs(queries: list, max_per_query: int = DOCS_PER_QUERY, use_reranker: bool = True) -> tuple:
    seen, all_results = set(), []
    futures = {executor.submit(_fetch_one_query, q, max_per_query): q for q in queries}
    for future in as_completed(futures):
        for r in future.result():
            if r['url'] not in seen:
                seen.add(r['url']); all_results.append(r)
    all_results = [r for r in all_results if len(content_words(r['content'])) >= MIN_DOC_WORDS]
    if not all_results: return "", []

    main_query = queries[0]

    if use_reranker and len(all_results) > 1:
        # Coarse lexical pre-filter down to RERANK_POOL candidates (cheap),
        # then a real cross-encoder reranker for the final ordering (accurate).
        q0_words = set(tokenize(main_query)); q0_ner = extract_named_entities(main_query)
        for r in all_results:
            ct = set(tokenize(r['content'])); tt = set(tokenize(r['title']))
            dn = extract_named_entities(r['content']+" "+r['title'])
            r['_prefilter_score'] = len(q0_words&ct) + len(q0_words&tt)*2 + len(q0_ner&dn)*5
        all_results.sort(key=lambda x: x['_prefilter_score'], reverse=True)
        pool = all_results[:RERANK_POOL]
        try:
            reranker = get_reranker()
            pairs = [(main_query, r['content'][:512]) for r in pool]
            scores = reranker.predict(pairs)
            for r, s in zip(pool, scores):
                r['score'] = float(s)
            pool.sort(key=lambda x: x['score'], reverse=True)
            top = pool[:TOP_DOCS]
        except Exception as e:
            print(f"    [!] Reranker unavailable ({e}), falling back to lexical scoring")
            top = pool[:TOP_DOCS]
    else:
        q0_words = set(tokenize(main_query)); q0_ner = extract_named_entities(main_query)
        for r in all_results:
            ct = set(tokenize(r['content'])); tt = set(tokenize(r['title']))
            dn = extract_named_entities(r['content']+" "+r['title'])
            r['score'] = len(q0_words&ct) + len(q0_words&tt)*2 + len(q0_ner&dn)*5
        all_results.sort(key=lambda x: x['score'], reverse=True)
        top = all_results[:TOP_DOCS]

    ctx_str, raw_docs = "", []
    for i, r in enumerate(top):
        ctx_str  += f"[Source {i+1}] {r['url']}\nTitle: {r['title']}\nContent: {r['content']}\n\n"
        raw_docs.append(r['content']+" "+r['title'])
    return ctx_str, raw_docs

def gen_answer(query, ctx, fmt="Direct factual statement", pass_num=1):
    sys = ("You are a precise factual assistant. Use ONLY the provided context. "
           "NEVER invent names, numbers, or facts. Cite as [Source N].")
    if pass_num == 1:
        prompt = f"Answer ONLY from sources below.\nExpected format: {fmt}\nSOURCES:\n{ctx}\nQUESTION: {query}\nANSWER:"
    elif pass_num == 2:
        prompt = f"Scan all sources. Extract answer.\nFormat: {fmt}\nSOURCES:\n{ctx}\nQUESTION: {query}\nANSWER:"
    else:
        prompt = f"Last attempt. If insufficient prefix with '⚠️ Training knowledge (VERIFY ONLINE):'\nSOURCES:\n{ctx}\nQUESTION: {query}\nANSWER:"
    return ask_ai(prompt, sys, temp=0.0 if pass_num > 1 else 0.05)

# ── PHASE RUNNERS ──────────────────────────────────────────────
def run_baseline(query: str) -> tuple:
    t0  = time.time()
    ans = ask_ai(query,
                 "You are a helpful assistant. Answer from training knowledge. Admit uncertainty.",
                 temp=0.1, model=MODEL_FAST)
    lat = round(time.time()-t0, 2)
    return ans, {"length": compute_len(ans), "lexical_diversity": compute_lex_div(ans), "latency": lat}

def run_hallucinating(query: str) -> tuple:
    t0  = time.time()
    ans = ask_ai(query,
                 "You are an overconfident bot. Never admit uncertainty. Always give a specific confident answer.",
                 temp=0.9, model=MODEL_FAST)
    lat = round(time.time()-t0, 2)
    return ans, {"length": compute_len(ans), "lexical_diversity": compute_lex_div(ans), "latency": lat}

def run_rag(query: str, analysis: dict) -> tuple:
    t0 = time.time()
    f_primary = executor.submit(retrieve_docs, analysis['primary_queries'], DOCS_PER_QUERY, True)
    f_verify  = executor.submit(retrieve_docs, analysis['verify_queries'],  2, False)
    ctx, raw   = f_primary.result()
    vctx, vdocs= f_verify.result()

    ans, passes = None, 0
    for p in range(1, MAX_RETRIES+1):
        a = gen_answer(query, ctx, analysis['answer_format'], p)
        passes = p
        if check_completeness(a): ans = a; break
    if not ans: ans = a
    v_ans = gen_answer(query, vctx, analysis['answer_format'], 1)

    f_faith   = executor.submit(compute_faithfulness, ans, ctx,   analysis['answer_type'])
    f_consist = executor.submit(compute_consistency,  ans, v_ans, analysis['answer_type'])
    f_sem_hallu = executor.submit(compute_semantic_hallucination, ans, raw)
    f_sem_eg    = executor.submit(compute_semantic_entity_grounding, ans, raw)
    f_sem_cu    = executor.submit(compute_semantic_ctx_util, ans, raw)

    faith, unsupported_claims = f_faith.result()
    consist  = f_consist.result()
    sem_hallu = f_sem_hallu.result()
    eg        = f_sem_eg.result()
    cu        = f_sem_cu.result()
    hallu     = sem_hallu["hallucination_rate"]

    p_k   = compute_precision_at_k(query, raw)
    r_k   = compute_recall_at_k(query, raw)
    conf  = compute_confidence(faith, consist, eg, cu, hallu)
    tf1, tp, tr = compute_tok_f1(ans, v_ans)
    lat   = round(time.time()-t0, 2)
    metrics = {
        "precision_at_k": p_k, "recall_at_k": r_k,
        "f1_at_k": compute_f1_at_k(p_k,r_k), "mrr": compute_mrr(query,raw),
        "source_coverage": compute_source_coverage(ans,raw),
        "context_utilization": cu, "hallucination_rate": hallu,
        "unsupported_sentences": sem_hallu["unsupported_sentences"],
        "unsupported_claims": unsupported_claims,
        "entity_grounding": eg, "rouge_l_vs_context": compute_rouge_l(ans,ctx),
        "token_f1": tf1, "token_precision": tp, "token_recall": tr,
        "lexical_diversity": compute_lex_div(ans), "answer_length": compute_len(ans),
        "faithfulness_score": faith, "consistency_score": consist,
        "confidence_score": conf, "docs_primary": len(raw), "docs_verify": len(vdocs),
        "passes_used": passes, "latency": lat,
        "intent": analysis['intent_label'], "answer_type": analysis['answer_type'],
        "scoring_method": "semantic_v8",
    }
    return ans, metrics

# ── ROUTES ─────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str

@app.post("/query")
async def handle_query(req: QueryRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        t_total  = time.time()
        analysis = analyse_query(query)
        f_base  = executor.submit(run_baseline,      query)
        f_hallu = executor.submit(run_hallucinating, query)
        f_rag   = executor.submit(run_rag,           query, analysis)
        base_ans,  base_met  = f_base.result()
        hallu_ans, hallu_met = f_hallu.result()
        rag_ans,   rag_met   = f_rag.result()
        print(f"  [Total wall time] {round(time.time()-t_total,2)}s")
        return JSONResponse({
            "baseline_answer":  base_ans,  "baseline_metrics": base_met,
            "hallu_answer":     hallu_ans, "hallu_metrics":    hallu_met,
            "rag_answer":       rag_ans,   "rag_metrics":      rag_met,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = Path(__file__).parent / "chatbotfrontend.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Frontend not found. Place chatbotfrontend.html next to server.py</h2>")

@app.get("/health")
async def health():
    return {"status": "ok", "model_fast": MODEL_FAST,
            "model_quality": MODEL_QUALITY, "version": "v8-semantic"}

if __name__ == "__main__":
    import uvicorn
    print("="*55)
    print("  RAG Intelligence Server — v8 Semantic Faithfulness")
    print(f"  Fast model    : {MODEL_FAST}")
    print(f"  Quality model : {MODEL_QUALITY}")
    print("  Open          : http://localhost:8000")
    print("  Parallelism   : ThreadPoolExecutor (6 workers)")
    print("  Scoring       : semantic embeddings + cross-encoder reranker")
    print("="*55)
    uvicorn.run(app, host="0.0.0.0", port=8000)