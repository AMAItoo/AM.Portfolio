"""Load and chunk bilingual markdown knowledge base files.

Two content styles are supported:

1. `ar:` / `en:` prefixed lines (about.md, projects.md, faq.md) — extracted
   and merged per heading.
2. Plain bilingual markdown (services.md) — the whole body of a heading is
   kept as the chunk, so pricing tables, packages and prose all go to RAG.

Sections split on both `##` and `###` headings so each service stays a
self-contained chunk.
"""
import os
import hashlib
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    source: str  # filename
    heading: str  # section heading
    chunk_id: str  # content hash


HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
LANG_LINE_RE = re.compile(r"^(ar|en):\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _split_sections(content: str) -> list[tuple[str, str]]:
    """Split content by `## ` / `### ` headings into [(heading, body)]."""
    parts = re.split(r"(?=^#{2,3} )", content, flags=re.MULTILINE)
    sections: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = HEADING_RE.match(part)
        if m:
            heading = m.group(2).strip()
            body = part[m.end():].strip()
        else:
            heading = ""  # preamble before the first heading
            body = part
        sections.append((heading, body))
    return sections


def _lang_lines(text: str) -> tuple[str, str]:
    """Extract ar: and en: lines from a text block."""
    ar_lines = []
    en_lines = []
    for m in LANG_LINE_RE.finditer(text):
        lang, content = m.group(1).lower(), m.group(2).strip()
        if lang == "ar":
            ar_lines.append(content)
        else:
            en_lines.append(content)
    return "\n".join(ar_lines), "\n".join(en_lines)


def _make_chunk_id(text: str, source: str) -> str:
    return hashlib.sha256(f"{source}::{text}".encode()).hexdigest()[:16]


def load_knowledge_base(kb_dir: str) -> list[Chunk]:
    """Parse all .md files in kb_dir into chunks.

    Each chunk is either the merged ar/en extraction (prefixed style) or the
    full section body (plain style). Single pass per file, deduplicated.
    """
    chunks: list[Chunk] = []
    seen_ids: set[str] = set()

    for fname in sorted(os.listdir(kb_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(kb_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        for heading, body in _split_sections(content):
            ar_text, en_text = _lang_lines(body)
            merged = f"{ar_text}\n{en_text}".strip()
            if not merged:
                # Plain bilingual markdown: keep the whole section body.
                merged = body
            if not merged:
                continue

            chunk_id = _make_chunk_id(merged, fname)
            if chunk_id in seen_ids:
                continue

            seen_ids.add(chunk_id)
            # Prepend the section heading so queries match on the service name
            # even when the body only lists packages and prices.
            header = f"{heading}\n" if heading else ""
            chunks.append(Chunk(
                text=header + merged,
                source=fname,
                heading=heading,
                chunk_id=chunk_id,
            ))

    return chunks