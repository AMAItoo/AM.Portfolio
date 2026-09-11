"""Static contract checks for the vanilla JS/CSS chatbot widget.

These test the *files* (chatbot.js / chatbot.css) via regex, since the
widget is plain vanilla JS with no bundler/test-runner in the repo.
"""
import os
import re
import pytest

WIDGET_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "chat")
JS_PATH = os.path.join(WIDGET_DIR, "chatbot.js")
CSS_PATH = os.path.join(WIDGET_DIR, "chatbot.css")


@pytest.fixture(scope="module")
def js_source():
    assert os.path.isfile(JS_PATH), f"chatbot.js missing: {JS_PATH}"
    with open(JS_PATH, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def css_source():
    assert os.path.isfile(CSS_PATH), f"chatbot.css missing: {CSS_PATH}"
    with open(CSS_PATH, encoding="utf-8") as f:
        return f.read()


def test_has_init_config_block(js_source):
    assert re.search(r"window\.PortfolioChat\s*=\s*\{", js_source)
    assert re.search(r"init\s*[:=]\s*(function|\({)", js_source)
    assert re.search(r"apiUrl", js_source)
    assert re.search(r"'201553851517'", js_source)


def test_posts_to_chat_endpoint(js_source):
    assert re.search(r"fetch\s*\(", js_source)
    assert re.search(r"/gradio_api/call/chat", js_source)
    assert re.search(r"method\s*:\s*['\"]POST['\"]", js_source)
    assert re.search(r"JSON\.stringify", js_source)
    assert re.search(r"event_id", js_source)


def test_renders_quick_replies_as_buttons(js_source):
    assert "quick_replies" in js_source
    assert "createElement" in js_source
    assert re.search(r"createElement\s*\(\s*['\"]button['\"]", js_source) or "createElement(tag)" in js_source


def test_whatsapp_link_built_client_side(js_source):
    assert "whatsapp" in js_source
    assert re.search(r"wa\.me", js_source)
    assert re.search(r"encodeURIComponent", js_source)


def test_lead_hint_on_offer_whatsapp(js_source, css_source):
    assert "offer_whatsapp" in js_source
    assert "pf-lead-hint" in js_source
    assert "pf-lead-hint" in css_source


def test_no_external_scripts(js_source):
    bad = [u for u in re.findall(r"https?://[^'\"\\s]+", js_source)
           if not u.startswith("https://wa.me/")]
    assert bad == [], f"external http(s) references leak into widget: {bad}"


def test_rtl_mirroring_in_css(css_source):
    assert re.search(r"\.pf-chat(?:-panel|-(fab|bubble))?\s*\{[^}]*position\s*:\s*fixed", css_source, re.S)
    assert re.search(r"\[dir=[\"']rtl[\"']\]", css_source) or \
        re.search(r"\[dir\s*=\s*['\"]rtl['\"]\].*\.pf-chat", css_source, re.S)


def test_no_external_assets_in_css(css_source):
    bad = re.findall(r"url\(\s*['\"]?https?://", css_source)
    assert bad == [], f"external urls in CSS: {bad}"
    assert "@import" not in css_source


def test_site_tokens_used_in_css(css_source):
    assert re.search(r"--accent|#0E7C5A|#0e7c5a", css_source)
    assert re.search(r"#25D366", css_source)  # WhatsApp green


def test_pages_include_widget():
    """index.html / index-ar.html wire the widget before </body>."""
    repo = os.path.abspath(os.path.join(WIDGET_DIR, "..", ".."))
    for page in ("index.html", "index-ar.html"):
        path = os.path.join(repo, page)
        assert os.path.isfile(path), f"page missing: {page}"
        html = open(path, encoding="utf-8").read()
        assert "assets/chat/chatbot.css" in html, f"{page} missing CSS link"
        assert "assets/chat/chatbot.js" in html, f"{page} missing JS script"
        assert "PortfolioChat" in html, f"{page} missing init call"