# Portfolio AI Chatbot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bilingual (AR-default) AI assistant for the portfolio site: answers ONLY from portfolio knowledge, walks visitors through services with quick-reply buttons, captures leads (name/service + any contact found in messages), and hands off to WhatsApp — free, open-source, always-on.

**Architecture:** Static widget (vanilla JS/CSS) on GitHub Pages → FastAPI app on Hugging Face Spaces (CPU free, never sleeps). Hybrid engine: deterministic state machine (sales scenario) + Groq llama-3.3-70b with RAG (ChromaDB + multilingual MiniLM) for free-form questions; Gemini 2.0 Flash automatic fallback. Lead capture: passive regex extraction from every message + saved-on-exit intent state → `data/leads.jsonl`.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, chromadb, sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2), groq SDK, google-genai (fallback), pytest; vanilla JS/CSS widget; Docker on HF Spaces.

## Global Constraints

- Arabic is the DEFAULT language; reply language = visitor's last message language.
- Secrets ONLY as env vars (GROQ_API_KEY, GEMINI_API_KEY) or HF Space secrets — never in code/git. `.secrets/` is git-ignored.
- Reply content strictly from knowledge base (guard: unsupported claims → WhatsApp referral).
- WhatsApp number verbatim: `201553851517`.
- CORS: allow `https://amaitoo.github.io` only. Rate limit: 20 req/min/IP (token bucket, in-memory).
- All requests ≤20s server-side; LLM max_tokens 400; temperature 0.4.
- No external JS/CSS libraries in the widget (site convention: self-hosted).
- Widget visual tokens match site: `--ink:#12231B`, `--accent:#0E7C5A`, `--paper:#F7F4EE`, WhatsApp `#25D366`, radius 18px, Poppins/Cairo.
- pytest must pass at every task boundary; commits after each task.

---

### Task 1: Knowledge base (bilingual markdown)

**Files:**
- Create: `chatbot/knowledge/about.md`, `chatbot/knowledge/services.md`, `chatbot/knowledge/projects.md`, `chatbot/knowledge/faq.md`

**Interfaces:**
- Produces: 4 markdown files with line-prefixed language tags (`ar: ...` / `en: ...`), consumed by Task 2 chunker. Facts sourced verbatim from the site: 7 services, 6 projects with demo paths, WhatsApp `201553851517`, email `cd3alaa@yahoo.com`.

- [x] **Step 1: Write `services.md`** — each service as `## <icon> <AR name> | <EN name>` heading + 2 bilingual lines (what you get + differentiator) + demo path when applicable. Services: تصميم البانرات والإعلانات/Banner & Ad Design · الهوية البصرية/Brand Identity · تصميم وتطوير المواقع/Web Design & Development · المحتوى والكتابة الإبداعية/Content & Copywriting · إنتاج الفيديو ويوتيوب/Video Production & YouTube · تحسين محركات البحث والأداء/SEO & Performance · الأبحاث والبيانات/Research & Data.

- [x] **Step 2: Write `projects.md`** — 6 projects (Adidas US Sales dashboard → `dashboards/analytics-dashboard/index.html`, Cafe dashboard → `dashboards/cafe-dashboard/index.html`, Quranic values video → `presentations/quranic-values.html`, TerraGrow banner, YouTube documentary, Content writing → `samples/article-data-analytics.html`): bilingual result-oriented line each + "شاهد الديمو" path.

- [x] **Step 3: Write `about.md`** (skills summary, tools: Excel/Power BI/Python/ECharts/Remotion/ffmpeg, bilingual intro) and `faq.md` (pricing=custom quote via WhatsApp, timelines, revision policy, response time, contact channels — bilingual).

- [x] **Step 4: Verify all facts against site pages** (grep services/projects/contact in `index.html`, `index-ar.html`) then commit: `git add chatbot/knowledge && git commit -m "feat(chatbot): bilingual knowledge base from portfolio facts"`

### Task 2: RAG engine (chunk → embed → Chroma)

**Files:**
- Create: `chatbot/rag.py`, `chatbot/kb_loader.py`
- Test: `chatbot/tests/test_rag.py`

**Interfaces:**
- Produces: `build_index(kb_dir: str, persist_dir: str) -> Chroma collection` and `retrieve(collection, query: str, k: int = 4) -> list[str]`. Chunks keep language tags; embedder `paraphrase-multilingual-MiniLM-L12-v2`.

- [x] **Step 1: Failing tests** — `test_index_builds_and_retrieves_ar`: build on tmp dir with 2 tiny bilingual md files; retrieve("تصميم بانرات") hits services chunk; `test_retrieve_en`: "video production" hits video service chunk; `test_top_k_respected` (k=2 → 2 chunks).

- [x] **Step 2: Run** `pytest chatbot/tests/test_rag.py -v` → FAIL (ModuleNotFoundError).

- [x] **Step 3: Implement** `kb_loader.py`: parse md → chunks by `##` heading, attach file name + language tags. `rag.py`: lazy-load embedder (HF Spaces startup ok), `build_index` uses `chromadb.PersistentClient`, cosine space, upsert by chunk hash; `retrieve` returns chunk texts.

- [x] **Step 4: Run tests** → PASS. Requirements pinned in `chatbot/requirements.txt` (chromadb, sentence-transformers==2.7.0, pytest) and commit.

### Task 3: Conversation engine (state machine + guarded LLM + lead capture)

**Files:**
- Create: `chatbot/engine.py`, `chatbot/leads.py`
- Test: `chatbot/tests/test_engine.py`

**Interfaces:**
- Consumes: `retrieve()` (Task 2), `GROQ_API_KEY`/`GEMINI_API_KEY` env.
- Produces: `class Session` (state: greet/ask_name/ask_service/service_detail/offer_whatsapp; fields: name, service, lang, awaiting_contact) · `handle(session, user_msg, buttons: list|None) -> Reply{messages: list[str], quick_replies: list[str], whatsapp: dict|None}` · `classify_language(text) -> "ar"|"en"` · `extract_contact(text) -> str|None` (email regex + phone regex 7-15 digits) · `leads.append_lead(lead: dict)` writing `data/leads.jsonl` (ts, session_id, name, service, contact, lang, last_state).

- [x] **Step 1: Failing tests** — `test_ar_detected` / `test_en_detected`; `test_flow_greeting_asks_name` (handle on fresh session returns ask-name message); `test_service_buttons_shown` (quick_replies == 7 service short names); `test_service_detail_from_rag` (engine returns service text + demo link for "video production"); `test_whatsapp_payload_contains_name_and_service` (wa.me URL contains URL-encoded name+service); `test_contact_extracted_from_msg` ("أنا أحمد im@gmail.com" → contact saved, lead file line count +1); `test_guard_refuses_offtopic` ("اكتب لي قصيدة" → polite referral message, no LLM hallucination — mocked LLM NOT called).

- [x] **Step 2: Run** → FAIL. **Step 3: Implement** engine with rule-first routing (state machine), LLM only for free-form in-scope questions: system prompt (bilingual persona "مساعد أحمد", strict-grounding rules, ≤80 words, language mirror), context = top-4 RAG chunks; Groq `llama-3.3-70b-versatile` via `groq.Client(api_key=os.environ["GROQ_API_KEY"])`; on `RateLimitError`/any Groq exception → Gemini `gemini-2.0-flash` via `google.genai` (same prompt). `extract_contact` + `append_lead` on every user message when contact found or service selected. **Step 4: tests PASS** (LLM paths mocked with fake responses). **Step 5: commit.**

### Task 4: FastAPI app (chat endpoint + security hardening)

**Files:**
- Create: `chatbot/app.py`, `chatbot/security.py`, `chatbot/Dockerfile`, `chatbot/README.md`
- Test: `chatbot/tests/test_app.py`

**Interfaces:**
- Consumes: `handle()` (Task 3), `build_index/retrieve` (Task 2).
- Produces: `POST /chat {session_id, message, page_lang} -> {messages, quick_replies, whatsapp, state}` (sessions in-memory TTL 2h, max 40 turns); `GET /health -> {status:"ok", kb_chunks:int}`; `GET /leads/count -> {count:int}` (simple check endpoint). Security: CORSMiddleware allow_origins=["https://amaitoo.github.io"]; RateLimiter 20/min/IP 429; input max 1000 chars; per-request 20s timeout guard; startup builds index.

- [x] **Step 1: Failing tests** (TestClient, monkeypatched engine to avoid LLM): `test_health_ok`; `test_chat_rejects_empty`; `test_chat_rejects_too_long` (1001 chars → 422); `test_cors_only_portfolio` (OPTIONS from allowed origin → `access-control-allow-origin` set; from `https://evil.com` → absent); `test_rate_limit_429` (21 fast calls from same IP → last status 429); `test_session_ttl_and_cap` (41st turn → polite reset).

- [x] **Step 2: Run** → FAIL. **Step 3: Implement** app + security module (token bucket per IP dict, origin check, length guard). **Step 4: PASS. Step 5: commit.**

### Task 5: Dockerfile + deployment config

**Files:**
- Create: `chatbot/Dockerfile` (if not in Task 4), `chatbot/.dockerignore`
- Modify: none (HF Space created via web UI later)

- [x] **Step 1: Dockerfile** — `FROM python:3.11-slim`, install requirements (torch CPU wheel index), `COPY chatbot/ /app/`, `EXPOSE 7860`, `CMD uvicorn app:app --host 0.0.0.0 --port 7860`. Healthcheck hits `/health`.
- [x] **Step 2: Build locally** `docker build -t pf-chatbot .` → succeeds. (If Docker unavailable: `pip install -r requirements.txt && python -m uvicorn app:app --port 7860` smoke test instead.)
- [x] **Step 3: Commit + document** exact HF Space creation steps in README (create Space → SDK=Docker → upload `chatbot/` → Settings→Secrets: GROQ_API_KEY, GEMINI_API_KEY → verify `/health`).

### Task 6: Widget (vanilla JS/CSS) + site wiring

**Files:**
- Create: `assets/chat/chatbot.js`, `assets/chat/chatbot.css`
- Modify: `index.html`, `index-ar.html`, every `projects/*-ar.html`/`projects/*.html` (footer include), `dashboards/*/index.html` optional
- Test: `chatbot/tests/test_widget_contract.py` (static checks via regex: config block, endpoints, RTL class handling, no external <script src>)

**Interfaces:**
- Consumes: `/chat` contract (Task 4).
- Produces: `window.PortfolioChat.init({apiUrl, whatsapp:'201553851517', lang})`; floating button bottom-left (LTR) / bottom-right (RTL, `dir=rtl` on html); panel 380px, header with avatar + "مساعد أحمد | Ahmed Assistant", bubbles, typing dots, quick replies, WhatsApp green button when `whatsapp` present; lead hint bubble "اترك رقم/إيميل لو تحب أرجع لك" when state=offer_whatsapp.

- [x] **Step 1: Widget contract tests** (fail first) — checks: fetch to `/chat` with JSON body; renders quick_replies as buttons; WhatsApp link built client-side from response; `.pf-chat-panel{position:fixed}` and `[dir="rtl"] .pf-chat-panel{...}` mirrored; zero `http` asset references.
- [x] **Step 2: Implement** JS (IIFE, no deps; XSS-safe: textContent only, never innerHTML for user/LLM strings; auto-lang detect mirrors main.js `isArabic` pattern) + CSS using site tokens.
- [x] **Step 3: Wire into pages** — one `<script>` + `<link>` line before `</body>` with config; EN pages: `lang:'en'`, AR: `lang:'ar'`.
- [x] **Step 4: Local end-to-end smoke** — run uvicorn locally, open `index-ar.html`, full scenario: greeting→name→service→detail→whatsapp button with encoded payload. PASS → commit.

### Task 7: QA, security review, docs, deploy support

**Files:**
- Modify: `docs/strategy/post-publish-checklist.md` (Portfolio repo — new chatbot ops section)

- [x] **Step 1: Full pytest suite** green. **Step 2: Security self-review checklist** executed (secrets scan `git log -p | grep -i gsk_` clean; CORS; rate limit; input caps; no PII storage beyond lead contact volunteered by user; dependency versions pinned; `docker build` clean). **Step 3: README ops** (rotate Groq key, read leads from Space files tab `data/leads.jsonl`, update KB → auto reindex on restart). **Step 4: Commit + push** → user creates HF Space + adds secrets → widget `apiUrl` set to Space URL → final live test both languages.
