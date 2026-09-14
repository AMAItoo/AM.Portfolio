"""Conversation engine: deterministic sales state machine + guarded LLM.

Rule-first routing drives the sales scenario (greet -> name -> service ->
detail -> WhatsApp), and only free-form in-scope questions reach the LLM,
grounded by RAG. Replies are bilingual and follow the visitor's language.
"""
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from chatbot.leads import append_lead, new_lead, notify_new_lead
from chatbot import rag
from chatbot import llm as llm_api

WHATSAPP = "201553851517"

# --- Services ---------------------------------------------------------------
SERVICES = {
    "banner": {"ar": "تصميم البانرات والإعلانات", "en": "Banner & Ad Design",
               "ar_short": "بانرات وإعلانات", "en_short": "Banners & Ads"},
    "brand": {"ar": "الهوية البصرية", "en": "Brand Identity",
              "ar_short": "هوية بصرية", "en_short": "Brand Identity"},
    "web": {"ar": "تصميم وتطوير المواقع", "en": "Web Design & Development",
            "ar_short": "مواقع وتطوير", "en_short": "Web & Apps"},
    "content": {"ar": "المحتوى والكتابة الإبداعية", "en": "Content & Copywriting",
                "ar_short": "كتابة محتوى", "en_short": "Content Writing"},
    "video": {"ar": "إنتاج الفيديو ويوتيوب", "en": "Video Production & YouTube",
              "ar_short": "فيديو يوتيوب", "en_short": "Video & YouTube"},
    "seo": {"ar": "تحسين محركات البحث والأداء", "en": "SEO & Performance",
            "ar_short": "SEO وأداء", "en_short": "SEO & Performance"},
    "research": {"ar": "الأبحاث والبيانات", "en": "Research & Data",
                 "ar_short": "أبحاث وبيانات", "en_short": "Research & Data"},
    "chatbot": {"ar": "تصميم وتطوير الشات بوت", "en": "Chatbot Design & Development",
                "ar_short": "شات بوت ذكي", "en_short": "AI Chatbot"},
}

DEMO_LINKS = {
    "banner": "projects/terra-grow.html",
    "brand": "projects/terra-grow.html",
    "web": "projects/analytics-dashboard.html",
    "video": "projects/youtube-video-production.html",
    "seo": "projects/youtube-video-production.html",
    "research": "projects/analytics-dashboard.html",
    "content": "projects/content-writing.html",
    "chatbot": "https://mazag00-portfolio-chatbot.hf.space/",
}

# --- Language & contact detection -------------------------------------------
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d{7,15})(?!\d)")


def classify_language(text: str) -> str:
    return "ar" if ARABIC_RE.search(text) else "en"


def extract_contact(text: str) -> str | None:
    """Return the first contact (email preferred over phone) found in text."""
    email = EMAIL_RE.search(text)
    if email:
        return email.group(0)
    phone = PHONE_RE.search(text)
    if phone:
        return phone.group(0)
    return None


def _extract_name(msg: str) -> str:
    """Extract a clean name from common phrasings (name is / i am / i'm)."""
    text = msg.strip()
    prefixes = ("اسمي", "اسمى", "انا ", "أنا ", "اسمي هو", "my name is",
                "call me", "i am ", "i'm ", "انا اسمي", "أنا اسمي")
    lowered = text.lower()
    for p in prefixes:
        if lowered.startswith(p):
            rest = text[len(p):].strip(" :،,:،.،.")
            if rest:
                # strip any contact (email/phone) that may follow the name
                return re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+|\+?\d{7,15}", "", rest).strip(" ,،").strip() or rest
    # fallback: last word of message if it's a plausible name
    words = [w for w in re.split(r"[\s.,،:؛]+", text) if w]
    if words:
        return words[-1]
    return text


def match_service(text: str) -> str | None:
    """Return service key if the message selects a service; else None.

    Tries exact, directional, and normalized (Arabic-determiner-insensitive)
    matching against every service name variant plus common aliases.
    """
    lowered = text.strip().lower()
    if not lowered:
        return None

    aliases = {
        "banner": ("banner", "ad design", "advertising", "ads", "social ads", "display ads", "baner", "بانرات", "بانر"),
        "brand": ("brand", "logo", "identity", "هوية", "لوغو", "لوجو", "branding"),
        "web": ("web", "website", "site", "frontend", "front-end", "fullstack", "full-stack", "development", "app", "موقع", "مواقع", "تطوير"),
        "content": ("content", "copywriting", "copy", "writing", "blog", "محتوى"),
        "video": ("video", "youtube", "editing", "motion", "فيديو", "يوتيوب"),
        "seo": ("seo", "search engine", "performance", "optimization", "سرعة", "تهيئة"),
        "research": ("research", "data", "analysis", "بانر"),
        "chatbot": ("chatbot", "chat bot", "chat-bot", "شات", "شات بوت", "بوت", "bot", "assistant"),
    }

    for key, s in SERVICES.items():
        variants = (s["ar"], s["en"], s["ar_short"], s["en_short"], *aliases[key])
        for variant in variants:
            v = variant.lower()
            if v in lowered or lowered in v:
                return key
    return None


# --- Off-topic / injection guard --------------------------------------------
REFUSE_KEYWORDS = (
    "قصيدة", "شعر", "أغنية", "song", "poem", "story",
    "تجاهل", "ignore", "تعليمات النظام", "system prompt",
    "اكتب لي", "write a poem", "ألِّف",
)


def is_off_topic(text: str) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in REFUSE_KEYWORDS)


# --- Reply & Session ---------------------------------------------------------
@dataclass
class Reply:
    messages: list[str]
    quick_replies: list[str] = field(default_factory=list)
    whatsapp: dict | None = None


@dataclass
class Session:
    session_id: str
    lang: str = "ar"
    state: str = "greet"
    name: str | None = None
    service: str | None = None
    contact: str | None = None
    notified: bool = False  # email alert already fired for this session


class Engine:
    def __init__(self, collection, retrieve_fn=None, leads_path="data/leads.jsonl",
                 llm_fn=None):
        self.collection = collection
        self.retrieve_fn = retrieve_fn or rag.retrieve
        self.leads_path = leads_path
        self.llm_fn = llm_fn or llm_api.answer

    # --- helpers -------------------------------------------------------------
    def _tr(self, session: Session, ar: str, en: str) -> str:
        return ar if session.lang == "ar" else en

    def _record_contact(self, session: Session, message: str) -> None:
        contact = extract_contact(message)
        if contact and session.contact is None:
            session.contact = contact

    def _save_lead(self, session: Session) -> None:
        append_lead(new_lead(
            session_id=session.session_id,
            name=session.name or "",
            service=session.service or "",
            contact=session.contact or "",
            lang=session.lang,
            last_state=session.state,
        ), self.leads_path, notify=not session.notified)
        session.notified = True

    def _service_detail_text(self, key: str, lang: str) -> str:
        s = SERVICES[key]
        query = s["ar"] if lang == "ar" else s["en"]
        chunks = self.retrieve_fn(self.collection, query, k=2)
        text = "\n".join(chunks) if chunks else ""
        demo = DEMO_LINKS.get(key)
        if demo:
            text += f"\nشاهد الديمو → {demo}\nView the demo → {demo}"
        return text

    def _whatsapp_link(self, session: Session) -> str:
        name = session.name or ""
        service = session.service
        if service:
            service = SERVICES[service]["ar"] if session.lang == "ar" else SERVICES[service]["en"]
        else:
            service = ""
        if session.lang == "ar":
            text = f"مرحبًا {name}، أنا مهتم بالخدمة: {service}. هل يمكننا التواصل؟"
        else:
            text = f"Hi {name}, I'm interested in: {service}. Can we talk?"
        return f"https://wa.me/{WHATSAPP}?text={quote(text)}"

    # --- state handlers ------------------------------------------------------
    def _do_greet(self, session: Session) -> Reply:
        session.state = "ask_name"
        return Reply(messages=[self._tr(
            session,
            "أهلاً وسهلاً! 👋 ممكن أتعرّف عليك؟\n\n`1) اكتب اسمك`\nبعدها سأطلب منك الإيميل أو رقم الهاتف حتى نتابع الشات معاً.",
            "Welcome! 👋 May I get to know you?\n\n`1) Tell me your name`\nThen I'll ask for your email or phone so we can continue the chat.",
        )])

    def _do_ask_name(self, session: Session, msg: str) -> Reply:
        session.lang = classify_language(msg) if msg.strip() else session.lang
        name = _extract_name(msg) if msg.strip() else None
        if not name:
            name = "عميلنا العزيز" if session.lang == "ar" else "friend"
        session.name = name[:40]
        session.state = "ask_contact"
        return Reply(messages=[self._tr(
            session,
            f"تشرفت بمعرفتك يا {session.name}! 😊\n\n`2) للإيميل أو رقم الهاتف:`\nاكتب بريدك الإلكتروني أو رقم هاتفك حتى أتمكن من التواصل معك بخصوص مشروعك.",
            f"Nice to meet you {session.name}! 😊\n\n`2) For email or phone:`\nShare your email or phone so I can reach you about your project.",
        )])

    def _do_ask_contact(self, session: Session, msg: str) -> Reply:
        contact = extract_contact(msg)
        if contact:
            session.contact = contact
        if not session.contact:
            session.contact = "لم يُذكر"
        # Visitor just shared contact details: alert immediately (fire-and-forget,
        # never blocks the reply). Later saves stay silent (single email/session).
        notify_new_lead(new_lead(
            session_id=session.session_id,
            name=session.name or "",
            service="",
            contact=session.contact or "",
            lang=session.lang,
            last_state="ask_contact",
        ))
        session.notified = True
        session.state = "ask_service"
        labels = self._tr(
            session,
            [s["ar_short"] for s in SERVICES.values()],
            [s["en_short"] for s in SERVICES.values()],
        )
        return Reply(messages=[self._tr(
            session,
            f"تم التسجيل ✅ متاحة لك هذه الخدمات — اختر ما يناسبك:",
            f"Got it ✅ Here's what I can deliver — pick the one that fits:",
        )], quick_replies=labels)

    def _do_ask_service(self, session: Session, msg: str) -> Reply:
        key = match_service(msg)
        if key:
            return self._enter_service(session, key)
        if is_off_topic(msg):
            return self._refuse(session)
        return self._freetext(session, msg)

    def _enter_service(self, session: Session, key: str) -> Reply:
        session.service = key
        session.state = "service_detail"
        text = self._service_detail_text(key, session.lang)
        self._save_lead(session)
        return Reply(
            messages=[self._tr(session,
                               f"ممتاز! إليك تفاصيل {SERVICES[key]['ar']}:\n\n{text}\n\nتحب نشوف التفاصيل على واتساب؟",
                               f"Great! Here's what {SERVICES[key]['en']} includes:\n\n{text}\n\nWant to continue on WhatsApp?")],
            quick_replies=self._tr(session, ["نعم، واتساب", "شاهد مشاريع أخرى"], ["Yes, WhatsApp", "Show other projects"]),
        )

    def _do_service_detail(self, session: Session, msg: str) -> Reply:
        key = match_service(msg)
        if key and key != session.service:
            return self._enter_service(session, key)
        if self._is_whatsapp_intent(msg):
            return self._offer_whatsapp(session)
        if is_off_topic(msg):
            return self._refuse(session)
        return self._freetext(session, msg)

    def _offer_whatsapp(self, session: Session) -> Reply:
        session.state = "offer_whatsapp"
        self._save_lead(session)
        link = self._whatsapp_link(session)
        return Reply(
            messages=[self._tr(session,
                               "تمام! اضغط الزر الأخضر للانتقال إلى واتساب مباشرة بكلام جاهز لخدمتك. 🌟",
                               "Perfect! Tap the green button to continue on WhatsApp — your message is pre-filled.")],
            quick_replies=[],
            whatsapp={"link": link, "number": WHATSAPP},
        )

    def _refuse(self, session: Session) -> Reply:
        return Reply(messages=[self._tr(
            session,
            "هذا خارج نطاق استفسارات الخدمات، لكن يسعدني توجيهك لخدماتي على واتساب مباشرة! 😊",
            "That's outside my scope, but I'd be happy to continue about my services on WhatsApp! 😊",
        )], quick_replies=self._tr(session, ["نعم، واتساب"], ["Yes, WhatsApp"]))

    def _freetext(self, session: Session, msg: str) -> Reply:
        session.lang = classify_language(msg)
        context = self.retrieve_fn(self.collection, msg, k=4)
        answer = self.llm_fn(msg, context, session.lang)
        return Reply(messages=[answer])

    @staticmethod
    def _is_whatsapp_intent(msg: str) -> bool:
        m = msg.strip().lower()
        return any(k in m for k in (
            "واتساب", "whatsapp", "نعم", "yes", "تواصل", "contact",
            "ابدأ", "start", "الى واتساب", "هاتف", "رقم", "phone",
        ))

    # --- whatsapp helper -----------------------------------------------------
    def _ensure_whatsapp(self, reply: Reply, session: Session) -> None:
        """Attach a WhatsApp link to any reply that lacks one."""
        if reply.whatsapp:
            return
        name = session.name or ""
        service = SERVICES[session.service]["ar"] if (session.service and session.lang == "ar") else (
            SERVICES[session.service]["en"] if session.service else "")
        if session.lang == "ar":
            text = f"مرحبًا {name}، أنا مهتم بالخدمة: {service}. هل يمكننا التواصل؟" if service else f"مرحبًا {name}، أود الاستفسار."
        else:
            text = f"Hi {name}, I'm interested in: {service}. Can we talk?" if service else f"Hi {name}, I'd like to ask."
        reply.whatsapp = {"link": f"https://wa.me/{WHATSAPP}?text={quote(text)}", "number": WHATSAPP}

    # --- main entry ----------------------------------------------------------
    def handle(self, session: Session, user_msg: str, buttons=None) -> Reply:
        msg = (user_msg or "").strip()
        if buttons and not msg:
            msg = buttons[0] if buttons else msg

        self._record_contact(session, msg)

        if session.state == "greet":
            reply = self._do_greet(session)
        elif session.state == "ask_name":
            reply = self._do_ask_name(session, msg)
        elif session.state == "ask_contact":
            reply = self._do_ask_contact(session, msg)
        elif session.state == "ask_service":
            reply = self._do_ask_service(session, msg)
        elif session.state == "service_detail":
            reply = self._do_service_detail(session, msg)
        else:
            reply = self._offer_whatsapp(session)

        self._ensure_whatsapp(reply, session)
        return reply