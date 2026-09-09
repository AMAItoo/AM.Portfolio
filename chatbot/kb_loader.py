"""Load and chunk bilingual markdown knowledge base files."""
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


HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)
LANG_LINE_RE = re.compile(r"^(ar|en):\s*(.+)$", re.IGNORECASE | re.MULTILINE)


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
    """Parse all .md files in kb_dir into chunks (split by ## headings).

    Each chunk gets both ar and en content merged, plus source/heading metadata.
    Single pass per file: no duplicate chunks.
    """
    chunks: list[Chunk] = []
    seen_ids: set[str] = set()

    for fname in sorted(os.listdir(kb_dir)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(kb_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        parts = re.split(r"(?=^## )", content, flags=re.MULTILINE)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            heading_match = HEADING_RE.match(part)
            if heading_match:
                heading = heading_match.group(1)
                body = part[heading_match.end():].strip()
            else:
                heading = ""  # preamble (content before first ##)
                body = part

            ar_text, en_text = _lang_lines(body)
            merged = f"{ar_text}\n{en_text}".strip()
            if not merged:
                continue

            chunk_id = _make_chunk_id(merged, fname)
            if chunk_id in seen_ids:
                continue

            seen_ids.add(chunk_id)
            chunks.append(Chunk(
                text=merged,
                source=fname,
                heading=heading,
                chunk_id=chunk_id,
            ))

    return chunks