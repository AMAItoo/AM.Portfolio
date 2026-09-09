"""Lead capture: append JSONL lines to a local file.

Simple, honest storage: only what the visitor volunteered (name, service,
contact) plus a timestamp and language. No cookie tracking or fingerprinting.
"""
import json
import os
import time


def append_lead(lead: dict, path: str = "data/leads.jsonl") -> None:
    """Append a single lead as a JSON line. Creates parent dirs as needed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    line = json.dumps(lead, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def new_lead(session_id: str, name: str, service: str, contact: str,
             lang: str, last_state: str) -> dict:
    """Build a lead dict with an ISO timestamp."""
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": session_id,
        "name": name,
        "service": service,
        "contact": contact,
        "lang": lang,
        "last_state": last_state,
    }