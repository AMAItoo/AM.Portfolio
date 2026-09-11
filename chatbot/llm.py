"""LLM layer: multi-provider chain with per-provider circuit breaker.

Chain (first healthy provider wins):
  1. Cerebras  (CEREBRAS_API_KEY)  - fastest open-model inference
  2. NVIDIA NIM (NVIDIA_API_KEY)   - build.nvidia.com models (kimi-k3 etc.)
  3. HF Router (HF_TOKEN)          - Inference Providers (needs fine-grained
                                     token with "Inference Providers" perms)
  4. Groq      (GROQ_API_KEY)      - legacy
  5. Gemini    (GEMINI_API_KEY)    - legacy
  6. Guarded fallback message (WhatsApp redirect)

Circuit breaker: a provider that raises is benched for PROVIDER_COOLDOWN_S
seconds so dead providers never slow down live traffic. Success un-benches.
A 402/429 (quota/rate limit) also benches the provider until the window
passes, so quota resets are picked up automatically without redeploy.

Security posture:
- API keys read ONLY from environment variables (never from code/git).
- System prompt enforces strict grounding: answer ONLY from the provided
  portfolio context; never invent facts, prices or services.
- Language mirroring: reply in the visitor's language.
"""
import os
import time

PROVIDER_COOLDOWN_S = 600

SYSTEM_PROMPT = (
    "أنت مساعد أحمد، مساعد موقع البورتفوليو لخدمات التصميم والكتابة والأبحاث والفيديو. "
    "أجب حصراً من المعلومات المرفقة (Context). لا تخترع أية خدمة أو سعر أو رقم غير موجود. "
    "إن لم تجد المعلومة في السياق، ارفض بأدب ووجّه الزائر للواتساب: +201553851517. "
    "ردّك 100 كلمة كحد أقصى، بلغة رسالة الزائر، بدون اعتراف بأنك مساعد آلي Zero-shots."
    "\n\n"
    "You are Ahmed's portfolio assistant. Answer ONLY from the provided Context. "
    "Never invent services, prices, or numbers. If the answer isn't in context, "
    "politely redirect to WhatsApp: +201553851517. Reply in the visitor's language, "
    "max 100 words."
)

# name -> epoch ts when the provider may be retried
_benched: dict[str, float] = {}


def _is_healthy(name: str) -> bool:
    return time.time() >= _benched.get(name, 0)


def _bench(name: str) -> None:
    _benched[name] = time.time() + PROVIDER_COOLDOWN_S


def _unbench(name: str) -> None:
    _benched.pop(name, None)


def _context_block(chunks):
    return "\n\n".join(chunks) if chunks else "بدون سياق. (No context.)"


def _build_messages(query: str, context_chunks: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Context:\n{_context_block(context_chunks)}"},
        {"role": "user", "content": query},
    ]


def _openai_chat(base_url: str, api_key: str, model: str, messages: list[dict],
                 user_agent: str = "PortfolioChatbot/1.0", timeout: int = 60) -> str:
    """Minimal OpenAI-compatible chat completion via httpx (no SDK deps)."""
    import httpx

    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json={"model": model, "messages": messages,
              "max_tokens": 400, "temperature": 0.4},
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "User-Agent": user_agent},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def answer_cerebras(messages: list[dict]) -> str:
    return _openai_chat(
        "https://api.cerebras.ai/v1",
        os.environ["CEREBRAS_API_KEY"],
        os.environ.get("CEREBRAS_MODEL", "qwen-3.8-27b"),
        messages,
    )


def answer_nvidia(messages: list[dict]) -> str:
    return _openai_chat(
        "https://integrate.api.nvidia.com/v1",
        os.environ["NVIDIA_API_KEY"],
        os.environ.get("NVIDIA_MODEL", "moonshotai/kimi-k3"),
        messages,
    )


def answer_hf_router(messages: list[dict]) -> str:
    model = os.environ.get("HF_MODEL", "openai/gpt-oss-120b:fastest")
    return _openai_chat(
        "https://router.huggingface.co/v1",
        os.environ["HF_TOKEN"],
        model,
        messages,
    )


def answer_groq(messages: list[dict]) -> str:
    from groq import Groq  # lazy import
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.environ.get("GROQ_MODEL", "gemma-7b-it")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=400,
        temperature=0.4,
    )
    return (resp.choices[0].message.content or "").strip()


def answer_gemini(messages: list[dict]) -> str:
    import httpx

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "system_instruction": {"parts": [{"text": "\n\n".join(
            m["content"] for m in messages if m["role"] == "system")}]},
        "contents": [{"role": "user", "parts": [{"text": "\n".join(
            m["content"] for m in messages if m["role"] == "user")}]}],
    }
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    resp = httpx.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates") or []
    return (candidates[0]["content"]["parts"][0].get("text") or "").strip()


_PROVIDERS = (
    ("cerebras", "CEREBRAS_API_KEY", answer_cerebras),
    ("nvidia", "NVIDIA_API_KEY", answer_nvidia),
    ("hf_router", "HF_TOKEN", answer_hf_router),
    ("groq", "GROQ_API_KEY", answer_groq),
    ("gemini", "GEMINI_API_KEY", answer_gemini),
)


def answer(query: str, context_chunks: list[str], lang: str) -> str:
    """Try providers in order; bench failures for PROVIDER_COOLDOWN_S."""
    messages = _build_messages(query, context_chunks)
    for name, env_key, fn in _PROVIDERS:
        if not os.environ.get(env_key):
            continue
        if not _is_healthy(name):
            continue
        try:
            text = fn(messages)
            if text:
                _unbench(name)
                return text
        except Exception:
            _bench(name)
            continue

    # Guarded fallback: no keys configured, all benched, or all failed.
    ar = "يسعدني إجابتك عن خدماتي ومشاريعي — اضغط زر واتساب واستقبل إجابة مختصصة بشكل مباشر."
    en = "I'd love to answer about my services and projects — tap the WhatsApp button for a direct personal reply."
    return ar if lang == "ar" else en