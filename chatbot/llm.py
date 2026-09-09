"""LLM layer: Groq llama-3.3-70b primary, Gemini 2.0 Flash fallback.

Security posture:
- API keys read ONLY from environment variables (never from code/git).
- System prompt enforces strict grounding: answer ONLY from the provided
  portfolio context; never invent facts, prices or services.
- Language mirroring: reply in the visitor's language.
- Max tokens and temperature are pinned by global constraints.
"""
import os

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


def _context_block(chunks):
    return "\n\n".join(chunks) if chunks else "بدون سياق. (No context.)"


def _build_messages(query: str, context_chunks: list[str]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Context:\n{_context_block(context_chunks)}"},
        {"role": "user", "content": query},
    ]


def answer_groq(messages: list[dict]) -> str:
    from groq import Groq  # lazy import
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=400,
        temperature=0.4,
    )
    return (resp.choices[0].message.content or "").strip()


def answer_gemini(messages: list[dict]) -> str:
    from google import genai  # lazy import

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    system = [m["content"] for m in messages if m["role"] == "system"]
    user = [m["content"] for m in messages if m["role"] == "user"]
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="\n".join(user),
        config={"system_instruction": "\n\n".join(system)},
    )
    return (resp.text or "").strip()


def answer(query: str, context_chunks: list[str], lang: str) -> str:
    """Full answer pipeline: Groq primary, Gemini fallback, guarded fallback."""
    messages = _build_messages(query, context_chunks)
    try:
        if os.environ.get("GROQ_API_KEY"):
            return answer_groq(messages)
    except Exception:
        pass  # fall through to Gemini
    try:
        if os.environ.get("GEMINI_API_KEY"):
            return answer_gemini(messages)
    except Exception:
        pass  # fall through to guarded generic

    # Guarded fallback: no secrets configured or both providers failed.
    ar = "يسعدني إجابتك عن خدماتي ومشاريعي — اضغط زر واتساب واستقبل إجابة مختصصة بشكل مباشر."
    en = "I'd love to answer about my services and projects — tap the WhatsApp button for a direct personal reply."
    return ar if lang == "ar" else en