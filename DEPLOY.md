# Deploying RAG Intelligence

The whole app ships as **one Docker container**: FastAPI serves the built React
SPA *and* the API on a single port. Models are baked into the image at build
time, so the first request is fast.

## Memory reality check

The pipeline loads `torch` + two sentence-transformers models → it needs
**~1–1.5 GB RAM**. That rules out 512 MB free tiers (Render free, etc.). The
sweet spot for a **free** deploy is **Hugging Face Spaces** (2 vCPU / 16 GB RAM,
Docker-native, built for ML).

---

## Option A — Hugging Face Spaces (recommended, free)

1. Create a Space: <https://huggingface.co/new-space> → **SDK: Docker** → blank template.
2. Add this YAML block at the very top of the Space's `README.md` (HF reads it to
   configure the Space):
   ```yaml
   ---
   title: RAG Intelligence
   emoji: 🔬
   colorFrom: blue
   colorTo: green
   sdk: docker
   app_port: 7860
   pinned: false
   ---
   ```
3. Push this repo to the Space's git remote (HF gives you the URL):
   ```bash
   git remote add space https://huggingface.co/spaces/<you>/rag-intelligence
   git push space main
   ```
4. In the Space → **Settings → Variables and secrets**, add:
   - `GROQ_API_KEY`  (secret)
   - `JWT_SECRET`    (secret — `python -c "import secrets;print(secrets.token_hex(32))"`)
   - `GOOGLE_CLIENT_ID` (optional, for Google sign-in)
5. The Space builds (~5–10 min the first time) and serves at
   `https://<you>-rag-intelligence.hf.space`.

> After deploy, add your Space URL to the Google OAuth **Authorized JavaScript
> origins** so "Sign in with Google" works in production.

---

## Option B — Render / Fly.io / Railway (nicer URL, ~$5–7/mo for 1 GB)

The same Dockerfile works. Create a **Docker web service** and set the secrets
above as env vars.

- **Render:** New → Web Service → *Docker*, instance ≥ 1 GB (Starter/Standard). It
  injects `$PORT`; the container already honours it.
- **Fly.io:** `fly launch --dockerfile Dockerfile` → set VM memory to 1 GB
  (`fly scale memory 1024`) → `fly secrets set GROQ_API_KEY=… JWT_SECRET=…`.
- **Railway:** New → Deploy from repo (Docker) → add the variables.

---

## Test the image locally first

```bash
docker compose up --build          # reads secrets from backend/.env
# open http://localhost:8000
```

---

## Caveats to know (and to mention in an interview)

- **SQLite is ephemeral** on free tiers — accounts/conversations reset on
  rebuild. For durability, attach a persistent volume (HF Spaces persistent
  storage, Fly volume, Render disk) mounted at `/app/backend/data`, or point
  SQLAlchemy at a managed Postgres (`db.py` needs only the URL changed).
- **DuckDuckGo may rate-limit from datacenter IPs** more aggressively than from a
  laptop, so retrieval can fail more often in the cloud. A production version
  would swap `ddgs` for a paid search API (Serper/Brave/Tavily) or a vector DB.
- **Rotate the Groq key** before making the repo public, and keep real values only
  in platform secrets / `backend/.env` (git-ignored) — never in `.env.example`.

---

## First-time git setup (this folder isn't a repo yet)

```bash
git init
git add .
git commit -m "RAG Intelligence — deploy-ready"
git branch -M main
# then push to GitHub and/or the HF Space remote above
```

`.gitignore` already excludes `.env`, `backend/data/`, `node_modules/`, build
output, and eval results, so no secrets or data get committed.
