# Deploy: Frontend → Vercel · Backend → Google Cloud Run (+ Cloud SQL Postgres)

This is the split-deployment path: the React SPA runs on Vercel, the FastAPI
backend runs as a container on Cloud Run, and accounts + chat history persist in
a managed Cloud SQL Postgres database.

Fill in these placeholders as you go:

| Placeholder | Meaning | Example |
|---|---|---|
| `PROJECT_ID` | your GCP project id | `rag-intelligence-2026` |
| `REGION` | GCP region | `us-central1` |
| `DB_PASSWORD` | Postgres password you pick (use letters+digits only, no URL-special chars) | `Rag9xPq2Km7v` |
| `INSTANCE_CONNECTION_NAME` | Cloud SQL connection name (step 3) | `PROJECT_ID:us-central1:rag-db` |
| `CLOUD_RUN_URL` | backend URL (step 5) | `https://rag-backend-xxxx-uc.a.run.app` |
| `VERCEL_URL` | frontend URL (step 6) | `https://rag-intelligence.vercel.app` |

---

## 0. Rotate the Groq key (do this FIRST — security)

The key currently in `backend/.env` is compromised. Go to
<https://console.groq.com> → **API Keys** → delete the old key → create a new one.
You'll paste the new value into Secret Manager in step 4 (never into git).

---

## 1. Install & authenticate the gcloud CLI

Windows (PowerShell) — download and run the installer:
```powershell
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:TEMP\gcloud.exe"); & "$env:TEMP\gcloud.exe"
```
Then, in a **new** terminal:
```bash
gcloud init            # log in + pick/create a config
gcloud auth login      # if not already done by init
```

---

## 2. Create the project & enable APIs

```bash
gcloud projects create PROJECT_ID --name="RAG Intelligence"
gcloud config set project PROJECT_ID

# Link your billing account (this is where the credits live):
gcloud billing accounts list
gcloud billing projects link PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX

# Enable everything we need:
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com
```

---

## 3. Create the Cloud SQL Postgres database

```bash
gcloud sql instances create rag-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=REGION \
  --storage-size=10GB \
  --storage-auto-increase

gcloud sql databases create ragdb --instance=rag-db
gcloud sql users create raguser --instance=rag-db --password='DB_PASSWORD'

# Grab the connection name — you need it below:
gcloud sql instances describe rag-db --format='value(connectionName)'
#   -> PROJECT_ID:REGION:rag-db   (this is INSTANCE_CONNECTION_NAME)
```
> `db-f1-micro` is the cheapest shared-core tier — fine for a demo. Delete the
> instance when you're done to conserve credits (see Cleanup).

---

## 4. Store secrets in Secret Manager

```bash
# New Groq key from step 0:
printf '%s' 'NEW_GROQ_KEY_HERE' | gcloud secrets create GROQ_API_KEY --data-file=-

# A fresh JWT signing secret:
python -c "import secrets;print(secrets.token_hex(32))" | tr -d '\n' | gcloud secrets create JWT_SECRET --data-file=-

# The full SQLAlchemy URL (Cloud Run reaches Cloud SQL over a unix socket):
printf '%s' 'postgresql+psycopg2://raguser:DB_PASSWORD@/ragdb?host=/cloudsql/INSTANCE_CONNECTION_NAME' \
  | gcloud secrets create DATABASE_URL --data-file=-

# Let Cloud Run's runtime service account read them:
PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format='value(projectNumber)')
for S in GROQ_API_KEY JWT_SECRET DATABASE_URL; do
  gcloud secrets add-iam-policy-binding $S \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

## 5. Deploy the backend to Cloud Run

The heavy image (torch + baked-in ML models) can take 10–15 min to build, so
raise the Cloud Build timeout first:
```bash
gcloud config set builds/timeout 1800
```

Deploy (run from the repo root — `--source backend` uses `backend/Dockerfile`):
```bash
gcloud run deploy rag-backend \
  --source backend \
  --region REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --cpu-boost \
  --timeout 300 \
  --min-instances 1 \
  --max-instances 3 \
  --concurrency 4 \
  --add-cloudsql-instances INSTANCE_CONNECTION_NAME \
  --set-secrets "GROQ_API_KEY=GROQ_API_KEY:latest,JWT_SECRET=JWT_SECRET:latest,DATABASE_URL=DATABASE_URL:latest" \
  --set-env-vars "GOOGLE_CLIENT_ID=<your GOOGLE_CLIENT_ID from backend/.env>"
```
Why these flags:
- **`--memory 2Gi --cpu 2`** — torch + two sentence-transformers models need ~1.5 GB and are CPU-bound.
- **`--min-instances 1 --cpu-boost`** — keeps one instance warm so you don't pay the ~50 s model-load cold start on every request.
- **`--concurrency 4`** — each query is CPU-heavy (reranking); don't overload one instance.
- **`--add-cloudsql-instances`** — mounts the Cloud SQL socket at `/cloudsql/...`.

Get the URL:
```bash
gcloud run services describe rag-backend --region REGION --format='value(status.url)'
#   -> CLOUD_RUN_URL
```
Smoke-test it:
```bash
curl CLOUD_RUN_URL/api/health
```

---

## 6. Deploy the frontend to Vercel (GitHub integration)

1. Commit & push these changes to GitHub (`main`).
2. <https://vercel.com/new> → **Import** `Anshkrsingh004/rag-intelligence`.
3. **Root Directory** → set to **`frontend`**. (Framework auto-detects as Vite.)
4. **Environment Variables** → add:
   - `VITE_API_BASE_URL` = `CLOUD_RUN_URL`  (Production **and** Preview)
5. **Deploy** → you get `VERCEL_URL`.

> If you change `VITE_API_BASE_URL` later, you must **redeploy** — Vite bakes env
> vars in at build time.

---

## 7. Wire up Google sign-in (+ optional CORS tightening)

- Google Cloud Console → **APIs & Services → Credentials** → your OAuth 2.0
  Client ID → **Authorized JavaScript origins** → add `VERCEL_URL`
  (and keep `http://localhost:5173` for local dev). Save.
- CORS: the backend already allows all origins, so cross-origin calls work out of
  the box. To tighten it to just your site later, restrict `allow_origins` in
  `backend/app/main.py` to `VERCEL_URL`.

---

## 8. Test

Open `VERCEL_URL` → run a query (all three panels should populate) → sign in →
confirm a conversation shows in the sidebar, then reload: it should persist
(it's in Postgres now).

---

## Caveats & troubleshooting

- **First query after a cold start is slow (~50 s)** while models load. `min-instances 1` keeps this rare.
- **DuckDuckGo may rate-limit datacenter IPs** more than your laptop, so the RAG panel can occasionally fail retrieval — just retry. A production version would swap `ddgs` for a paid search API (Serper/Brave/Tavily).
- **Backend logs:** `gcloud run services logs read rag-backend --region REGION`
- **Build failed on timeout?** Re-run after `gcloud config set builds/timeout 1800`.
- **DB connection errors?** Re-check `INSTANCE_CONNECTION_NAME` in `DATABASE_URL`, that `--add-cloudsql-instances` matches it, and that `DB_PASSWORD` has no URL-special characters (`@ : / ?`).

## Cleanup (to stop spending credits)

```bash
gcloud run services delete rag-backend --region REGION
gcloud sql instances delete rag-db
```
(Delete the Vercel project from its dashboard.)
