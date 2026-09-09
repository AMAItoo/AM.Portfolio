import os
import pytest
from chatbot.kb_loader import load_knowledge_base
from chatbot.rag import build_index, retrieve


@pytest.fixture
def tiny_kb(tmp_path):
    """Create a minimal bilingual KB with 2 files for testing."""
    services = tmp_path / "services.md"
    services.write_text(
        "## تصميم البانرات والإعلانات | Banner & Ad Design\n"
        "\n"
        "ar: بانرات وسائل التواصل، إعلانات العرض، أغلفة وصور رئيسية — بأحجام دقيقة ومتوافقة مع الهوية البصرية.\n"
        "en: Social media banners, display ads, covers and heroes — sized precisely, brand-compliant.\n"
        "\n"
        "## إنتاج الفيديو ويوتيوب | Video Production & YouTube\n"
        "\n"
        "ar: حوّل الأفكار إلى فيديوهات يوتيوب مُحسّنة ومصقولة — سيناريو، مرئيات ذكاء اصطناعي، صوت.\n"
        "en: Turn ideas into polished, SEO-optimized YouTube videos — script, AI visuals, voice.\n",
        encoding="utf-8",
    )
    about = tmp_path / "about.md"
    about.write_text(
        "ar: أحمد — مصمم ومطور فريلانس بخبرة تزيد عن 40 عاماً.\n"
        "en: Ahmed — a freelance designer and developer with over 40 years of experience.\n",
        encoding="utf-8",
    )
    return tmp_path


def test_index_builds_and_retrieves_ar(tiny_kb):
    """Arabic query 'تصميم بانرات' should hit the banner service chunk."""
    persist = str(tiny_kb / "chroma_db")
    chunks = load_knowledge_base(str(tiny_kb))
    assert len(chunks) > 0
    collection = build_index(chunks, persist)
    results = retrieve(collection, "تصميم بانرات")
    assert len(results) > 0
    assert any("بانرات" in r for r in results), f"Expected banner chunk, got: {results}"


def test_retrieve_en(tiny_kb):
    """English query 'video production' should hit the video service chunk."""
    persist = str(tiny_kb / "chroma_db")
    chunks = load_knowledge_base(str(tiny_kb))
    collection = build_index(chunks, persist)
    results = retrieve(collection, "video production")
    assert len(results) > 0
    assert any("video" in r.lower() for r in results), f"Expected video chunk, got: {results}"


def test_top_k_respected(tiny_kb):
    """k=2 should return at most 2 chunks."""
    persist = str(tiny_kb / "chroma_db")
    chunks = load_knowledge_base(str(tiny_kb))
    collection = build_index(chunks, persist)
    results = retrieve(collection, "تصميم", k=2)
    assert len(results) <= 2


def test_empty_query_returns_empty(tiny_kb):
    """Empty query should return empty list."""
    persist = str(tiny_kb / "chroma_db")
    chunks = load_knowledge_base(str(tiny_kb))
    collection = build_index(chunks, persist)
    results = retrieve(collection, "")
    assert results == []


def test_load_knowledge_base_counts_chunks():
    """Real knowledge base should produce meaningful number of chunks."""
    kb_dir = os.path.join(os.path.dirname(__file__), "..", "knowledge")
    if not os.path.isdir(kb_dir):
        pytest.skip("Real KB not found")
    chunks = load_knowledge_base(kb_dir)
    assert len(chunks) >= 10, f"Expected >=10 chunks, got {len(chunks)}"