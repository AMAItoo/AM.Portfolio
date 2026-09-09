# Portfolio Chatbot — Ops

Bilingual (AR/EN) assistant for the portfolio site. FastAPI + RAG (ChromaDB) backend
on HF Spaces, Groq LLM with Gemini fallback, vanilla JS widget embedded in the site.

## Local dev

```powershell
python -m venv .venv; .venv\Scripts\activate
pip install -r chatbot\requirements.txt
$env:GROQ_API_KEY = "gsk_..."          # optional for tests; required for live LLM
python -m uvicorn chatbot.app:app --host 127.0.0.1 --port 7862
```

Smoke test: `Invoke-WebRequest http://127.0.0.1:7862/health` → `{"status":"ok","kb_chunks":28}`.

## Tests

```powershell
python -m pytest chatbot/tests/ -q   # 35 tests: rag, engine, app, security, widget contract
```

## Secrets (never commit)

- Git-ignored: `.secrets/groq_api_key.txt`, `GEMINI_API_KEY` (set env at runtime).
- HF Space: set `GROQ_API_KEY` and `GEMINI_API_KEY` in **Settings → Variables and secrets**.

## Deploy (HF Space)

1. `docker build -t pf-chatbot -f chatbot/Dockerfile .` (context = repo root).
2. Create a Space with Docker SDK; push this context; port `7860` (Dockerfile exposes it).
3. First boot downloads the embedding model (~470 MB) → `/health` lags up to ~90s. Normal.

## Leads

- Every visitor message is scanned for a contact; on interest, `name`, `service`, contact are
  appended to `data/leads.jsonl` inside the Space (one JSON object per line).
- Read them: Space **Files → data/leads.jsonl** (or download via HF API).
- Lead capture is passive and only stores contact info the visitor volunteered.

## Updating the knowledge base

- Edit `chatbot/knowledge/*.md` (keep the `ar:` / `en:` line format, `##`-grouped).
- Restart the Space → startup reindexes ChromaDB (upsert keyed by chunk hash; no growth).

## Security posture

- CORS allowlist: `https://amaitoo.github.io` only.
- Rate limit: 20 req/min per IP (returns 429).
- Input cap 1000 chars, control chars stripped, session cap 40 turns / 2h TTL.
- LLM grounded to KB context only; off-topic / prompt-injection keywords → WhatsApp referral,
  no LLM call (no cost, no hallucination).
- Widget is XSS-safe (textContent only; no innerHTML for user/LLM strings).

## Rotate Groq key

The key was shared once in plaintext chat. Revoke it at console.groq.com and set the new value
in `.secrets` + HF Space settings