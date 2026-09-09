"""Tests for the conversation engine (state machine + lead capture + guards)."""
import json
import os
from chatbot.engine import Engine, Session, classify_language, extract_contact
from chatbot.leads import append_lead


class FakeCollection:
    """Stub for retrieve(); canned chunks per query."""

    def __init__(self):
        self.documents = {
            "video": "ar: حوّل الأفكار إلى فيديوهات يوتيوب مُحسّنة ومصقولة.\nen: Turn ideas into polished, SEO-optimized YouTube videos — script, AI visuals, voice.",
            "banners": "ar: بانرات وسائل التواصل، إعلانات العرض.\nen: Social media banners, display ads sized precisely.",
            "default": "ar: خدمات متنوعة في التصميم والتطوير.\nen: Various services in design and development.",
        }

    def retrieve(self, query, k=4):
        q = query.lower()
        if "video" in q or "يوتيوب" in q or "فيديو" in q:
            return [self.documents["video"]]
        if "بانر" in q or "banner" in q:
            return [self.documents["banners"]]
        return [self.documents["default"]]


def make_engine(tmp_path, tracking=None):
    return Engine(
        collection=FakeCollection(),
        retrieve_fn=lambda col, q, k=4: col.retrieve(q, k),
        leads_path=str(tmp_path / "leads.jsonl"),
        llm_fn=tracking,
    )


def test_ar_detected():
    assert classify_language("أهلاً كيف حالك") == "ar"


def test_en_detected():
    assert classify_language("how are you doing") == "en"


def test_contact_extracted_email_and_phone():
    assert extract_contact("أنا أحمد im@example.com") == "im@example.com"
    assert extract_contact("رقمي 01012345678") == "01012345678"
    assert extract_contact("مرحباً لا شيء هنا") is None


def test_append_lead_writes_file(tmp_path):
    lead = {"name": "أحمد", "service": "web", "contact": "a@b.com"}
    append_lead(lead, str(tmp_path / "leads.jsonl"))
    append_lead(lead, str(tmp_path / "leads.jsonl"))
    lines = open(os.path.join(tmp_path, "leads.jsonl"), encoding="utf-8").read().splitlines()
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert parsed["name"] == "أحمد"


def test_flow_greeting_asks_name(tmp_path):
    engine = make_engine(tmp_path)
    s = Session("s1", "ar")
    reply = engine.handle(s, "")
    assert s.state == "ask_name"
    assert len(reply.messages) > 0
    assert any("اسم" in m for m in reply.messages)


def test_service_buttons_shown(tmp_path):
    engine = make_engine(tmp_path)
    s = Session("s2", "ar")
    engine.handle(s, "")  # greeting
    reply = engine.handle(s, "اسمي محمد")
    assert s.name == "محمد"
    assert reply.quick_replies, "expected service buttons"
    labels = " ".join(reply.quick_replies)
    assert "فيديو" in labels and "هوية" in labels


def test_service_detail_from_rag(tmp_path):
    engine = make_engine(tmp_path)
    s = Session("s3", "ar")
    engine.handle(s, "")
    engine.handle(s, "اسمي سارة")
    reply = engine.handle(s, "فيديو يوتيوب")
    assert s.state == "service_detail"
    assert s.service == "video"
    assert "يوتيوب" in " ".join(reply.messages)
    assert reply.whatsapp is None


def test_whatsapp_payload_contains_name_and_service(tmp_path):
    from urllib.parse import unquote
    engine = make_engine(tmp_path)
    s = Session("s4", "ar")
    engine.handle(s, "")
    engine.handle(s, "أنا خالد")
    engine.handle(s, "بانرات")
    reply = engine.handle(s, "واتساب")
    assert reply.whatsapp is not None
    link = reply.whatsapp["link"]
    assert "201553851517" in link
    decoded = unquote(link)
    assert "خالد" in decoded  # visitor name
    assert "بانر" in decoded  # service label


def test_guard_refuses_offtopic_no_llm(tmp_path):
    calls = []
    engine = make_engine(tmp_path, tracking=lambda *a, **k: calls.append(a))
    s = Session("s5", "ar")
    engine.handle(s, "")
    engine.handle(s, "اسمي علي")
    engine.handle(s, "فيديو")
    reply = engine.handle(s, "اكتب لي قصيدة")
    assert calls == [], f"LLM should NOT be called for off-topic, got {calls}"
    assert "واتساب" in " ".join(reply.messages)


def test_freetext_question_calls_llm(tmp_path):
    calls = []

    def fake_llm(query, context, lang):
        calls.append(1)
        return "خدمة الفيديو تغطي السيناريو والبصريات."

    engine = make_engine(tmp_path, tracking=fake_llm)
    s = Session("s6", "ar")
    engine.handle(s, "")
    engine.handle(s, "اسمي نور")
    engine.handle(s, "فيديو")
    reply = engine.handle(s, "هل تغطي خدمة الفيديو كتابة السيناريو؟")
    assert calls, "LLM should be called for in-scope question"
    assert "السيناريو" in " ".join(reply.messages)


def test_lead_captured_when_contact_in_message(tmp_path):
    engine = make_engine(tmp_path)
    s = Session("s7", "ar")
    engine.handle(s, "")
    engine.handle(s, "اسمي عمر im.official@site.com")
    engine.handle(s, "مواقع")
    assert os.path.exists(engine.leads_path)
    lines = open(engine.leads_path, encoding="utf-8").read().splitlines()
    parsed = json.loads(lines[-1])
    assert parsed["name"] == "عمر"
    assert parsed["contact"] == "im.official@site.com"
    assert parsed["service"] == "web"