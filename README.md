# RAG Intelligence — Anti-Hallucination Engine

Ask any question and watch **three AI systems answer it at once**, side by side —
so the difference between hallucination and grounded, source-cited intelligence is
impossible to miss.

> 📊 **On a reproducible 20-question benchmark, the RAG pipeline cut hallucination
> 44% versus an ungrounded LLM — and to 0.00 on current-events and medical
> questions.** ([details ↓](#benchmark--does-grounding-actually-reduce-hallucination))

| Panel | Model | What it shows |
|-------|-------|---------------|
| 🎭 **Hallucinating AI** | `llama-3.1-8b-instant` (temp 0.9) | Overconfident, ungrounded — what bad AI looks like |
| 🧩 **Baseline LLM** | `llama-3.1-8b-instant` | Parametric memory only, no retrieval |
| 🔬 **RAG Pipeline** | `llama-3.3-70b-versatile` | Live retrieval → cross-encoder rerank → grounded answer → semantic faithfulness scoring + confidence 0–100 |

This is a fresh rebuild: a modular FastAPI backend and an elegant Vite + React +
TypeScript frontend with a validated, colorblind-safe palette and light/dark themes.

---

## Architecture

```
                    ┌─────────────────────────────┐
   React + Vite ───▶│  /api/query   (FastAPI)     │
   (frontend/)      │                             │
                    │  ├─ analyse query (LLM)     │
                    │  ├─ Baseline    ─┐          │
                    │  ├─ Hallucinat. ─┼ parallel │──▶ Groq (Llama)
                    │  └─ RAG          ─┘          │──▶ DuckDuckGo search
                    │       ├─ retrieve + rerank  │──▶ MiniLM embed + cross-encoder
                    │       ├─ generate (+retry)  │
                    │       ├─ verify (2nd answer)│
                    │       └─ score              │
                    └─────────────────────────────┘
```

### Backend (`backend/app/`) — one responsibility per module

| Module | Role |
|--------|------|
| `config.py` | Settings + `.env` loading (key never hardcoded) |
| `text_utils.py` | Tokenizing, sentence splitting, entity extraction |
| `llm.py` | Groq chat wrapper |
| `ml_models.py` | Lazy MiniLM embedder + cross-encoder reranker + cosine |
| `metrics.py` | Lexical + semantic metrics (one embed pass for grounding) |
| `judges.py` | LLM faithfulness/consistency judges + query planner |
| `retrieval.py` | Parallel DDG search → lexical prefilter → rerank |
| `pipeline.py` | Orchestrates the three panels concurrently |
| `main.py` | FastAPI app, `/api/*` routes, serves the built SPA |

### Frontend (`frontend/src/`)

Componentized React: `Header`, `Welcome`, `QueryInput`, `ComparisonBlock`,
`AnswerCard`, `RagMetricsPanel` (confidence ring + meters + retrieval stats),
`BasicMetricsPanel`. Colors come from a palette validated for colorblind safety
in both light and dark modes.

---

## Quick start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt         # first run downloads two ~80MB local models
cp .env.example .env                     # then paste your Groq key into .env
python run.py                            # http://localhost:8000
```

Get a free Groq key at <https://console.groq.com>.

### 2. Frontend (development)

```bash
cd frontend
npm install
npm run dev                              # http://localhost:5173 (proxies /api → :8000)
```

Open **http://localhost:5173**. The header badge reads **Live** when it can reach
the backend.

### 3. Production (single server)

```bash
cd frontend && npm run build             # emits frontend/dist/
cd ../backend && python run.py           # now also serves the UI at http://localhost:8000
```

> Build the frontend **before** starting the backend — the backend serves
> `frontend/dist/` only if it exists at startup.

---

## Metrics explained

| Metric | Measures | Good |
|--------|----------|------|
| **Confidence** | Composite [0–100] | ≥ 72 (High) |
| Faithfulness | LLM-judged share of claims supported by sources | ≥ 0.80 |
| Consistency | Agreement vs an independent verification answer | ≥ 0.75 |
| Entity grounding | Named entities semantically present in context | ≥ 0.85 |
| Context use | Answer sentences grounded in context | ≥ 0.70 |
| Hallucination ↓ | Answer sentences below the semantic-support threshold | ≤ 0.15 |
| Precision@K / Recall@K / MRR | Retrieval quality | higher |

**Verdict:** High ≥ 72 · Medium 45–71 · Low < 45.

Hallucination and grounding are **semantic** (embedding cosine similarity), so
faithful paraphrases are not flagged and same-vocabulary-but-wrong claims are.

---

## API

`POST /api/query` → `{ "query": "..." }`

```jsonc
{
  "hallu_answer": "...",     "hallu_metrics":    { "length": {...}, "lexical_diversity": 0.9, "latency": 0.2 },
  "baseline_answer": "...",  "baseline_metrics": { ... },
  "rag_answer": "...",       "rag_metrics": {
    "confidence_score": 84.5, "faithfulness_score": 0.91, "consistency_score": 0.85,
    "entity_grounding": 0.94, "context_utilization": 0.9, "hallucination_rate": 0.07,
    "unsupported_claims": [], "precision_at_k": 1.0, "mrr": 1.0, "latency": 12.2, ...
  }
}
```

`GET /api/health` → `{ "status": "ok", "version": "v9-modular", "model_fast": ..., "model_quality": ... }`

### Auth & saved history

Accounts are optional — the demo works fully signed-out (an ephemeral in-memory
session). Sign in and your chats are saved server-side as **conversations**
(ChatGPT-style), so they survive a refresh and can be reopened or deleted.

Data model: `User 1──< Conversation 1──< Message`. A conversation is one chat
session; a message is one exchange (the query + the full three-panel response
payload). The sidebar lists conversations ordered by `updated_at DESC`; the title
is generated by the LLM (fast model) from the first message — e.g. "Who won the
Nobel Prize in Physics in 2023?" → *"2023 Nobel Physics Prize Winner"* — and
falls back to a truncated message if the model call fails.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/auth/register` `{email, password}` | Create an account → `{token, user}` |
| `POST /api/auth/login` `{email, password}` | Sign in → `{token, user}` |
| `POST /api/auth/google` `{credential}` | Sign in with a Google ID token → `{token, user}` |
| `GET /api/auth/config` | Whether Google sign-in is enabled (`{google_client_id}`) |
| `GET /api/auth/me` | Current user (send `Authorization: Bearer <token>`) |
| `GET /api/conversations` | Sidebar list — summaries, `updated_at DESC` |
| `POST /api/conversations` `{first_message?}` | New conversation (title from first message) |
| `GET /api/conversations/{id}` | Open — conversation **with** its `messages[]` |
| `POST /api/conversations/{id}/messages` `{query, payload}` | Append a turn |
| `PATCH /api/conversations/{id}` `{title}` | Rename |
| `DELETE /api/conversations/{id}` | Delete conversation + its messages |

Passwords are hashed with **bcrypt**; sessions are stateless **JWTs** signed with
`JWT_SECRET`. Every conversation route is scoped to the token's user, so accounts
are fully isolated. Users, conversations, and messages live in a local SQLite file
at `backend/data/app.db` (git-ignored) — delete it to reset all accounts.

### Enabling "Sign in with Google" (optional)

Google sign-in is **off until you add a client id** — the button only appears once
it's configured. To turn it on:

1. Go to <https://console.cloud.google.com/apis/credentials> and create an
   **OAuth 2.0 Client ID** of type **Web application**.
2. Under **Authorized JavaScript origins**, add your app origin — for local dev
   that's `http://localhost:5173` (and `http://localhost:8000` if you serve the
   production build). No redirect URI is needed for this flow.
3. Copy the client id (looks like `1234-abc.apps.googleusercontent.com`) into
   `backend/.env`:
   ```
   GOOGLE_CLIENT_ID=1234-abc.apps.googleusercontent.com
   ```
4. Restart the backend. The **Continue with Google** button now appears in the
   sign-in dialog.

The browser gets a Google ID token, sends it to `POST /api/auth/google`, and the
backend verifies it (signature, audience, issuer, verified email) with
`google-auth` before finding-or-creating the user and issuing an app JWT. Signing
in with Google on an email that already has a password account links the two.

---

## Benchmark — does grounding actually reduce hallucination?

`run_eval.py` runs a frozen 20-question set and, for every question, measures the
**semantic hallucination rate of all three panels against the same retrieved
evidence** — a fair, apples-to-apples grounded-vs-ungrounded comparison. The
metric is computed locally (embeddings), independent of which model wrote the
answer.

**Result (20/20 questions, Llama-3.1-8B):**

| | Hallucinating AI | Baseline LLM *(ungrounded)* | RAG *(grounded)* |
|---|---|---|---|
| **Overall** | 0.456 | **0.284** | **0.160** |

**→ The RAG pipeline cut the hallucination rate 44% versus an ungrounded LLM**
(0.284 → 0.160), at 0.86 avg faithfulness and 69/100 avg confidence.

The effect is strongest exactly where grounding should matter — current and
factual-lookup questions — and negligible on facts the model already knows:

| Category | n | Baseline | RAG | |
|---|---|---|---|---|
| current facts | 5 | 0.370 | **0.000** | 100% ↓ |
| medical | 2 | 0.405 | **0.000** | 100% ↓ |
| historical facts | 3 | 0.444 | 0.233 | 48% ↓ |
| static science | 4 | 0.000 | 0.000 | already grounded |
| static facts | 4 | 0.188 | 0.375 | ↑ (retrieval adds verbosity) |
| legal | 2 | 0.472 | 0.500 | ↑ (noisy legal text) |

Honest caveats: the numbers above were produced on **Llama-3.1-8B** (the 70B
free-tier daily token quota can't cover a 20-question run); a 70B run would likely
match or beat these. Live DuckDuckGo retrieval rate-limits under rapid batches, so
pass `--delay` to pace the eval.

### Reproduce it

```bash
cd backend && python run.py                                   # terminal 1
cd backend/eval                                               # terminal 2
python run_eval.py --out results.json --label v9 --delay 6
```

The summary prints the grounded-vs-ungrounded table above. `compare_eval.py
results_a.json results_b.json` diffs two runs for a before/after delta.

---

## Security

The Groq key is read only from `backend/.env` (git-ignored) or the environment —
never from source. **The key that shipped in the original `serverv7.py` (now under
`legacy/`) is compromised and should be rotated** at <https://console.groq.com>;
keep `.env.example` a placeholder.

Set a strong `JWT_SECRET` in `backend/.env` for auth (generate one with
`python -c "import secrets; print(secrets.token_hex(32))"`). Without it the server
falls back to an insecure dev secret and warns on startup.

---

## Tech stack

**Backend** FastAPI · Groq (Llama 3.1-8B / 3.3-70B) · DuckDuckGo (`ddgs`) ·
sentence-transformers (`all-MiniLM-L6-v2` + `ms-marco-MiniLM-L-6-v2`) · NumPy ·
SQLAlchemy + SQLite · bcrypt · PyJWT
**Frontend** Vite 6 · React 19 · TypeScript · Tailwind CSS 4

The original single-file version is preserved under `legacy/`.

## License

MIT.
