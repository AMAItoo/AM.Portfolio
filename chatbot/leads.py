"""Lead capture: append JSONL lines to a local file + optional HF Dataset mirror.

Storage is honest and minimal: only what the visitor volunteered (name, service,
contact) plus a timestamp and language. No cookie tracking or fingerprinting.

The local JSONL file is the source of truth (fast, no network). A background
thread mirrors every line to a free Hugging Face dataset repo so leads survive
container restarts on ZeroGPU. Enable it by setting:

    HF_DATASET_REPO = "your_user/portfolio-leads"   (dataset repo id)
    HF_TOKEN       = a token with dataset write perms
"""
import json
import os
import threading
import time

try:
    from huggingface_hub import HfApi
    _HF_OK = True
except Exception:                       # pragma: no cover - fallback offline
    _HF_OK = False


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


class LeadBackup:
    """Idempotent mirror of a local JSONL file to a HF dataset repo.

    Every tick it re-uploads the whole local file as `leads.jsonl` in the repo
    (leads.jsonl is small at free-tier volume, so full-replace is simple and
    reliable). Failures are swallowed and retried on the next tick.
    """

    def __init__(self, path: str = "data/leads.jsonl", repo: str = "",
                 token: str = "", interval: int = 60):
        self.path = path
        self.repo = repo or os.environ.get("HF_DATASET_REPO", "").strip()
        self.token = token or os.environ.get("HF_TOKEN", "").strip()
        self.interval = max(10, int(interval))
        self._last_size = 0
        self._lock = threading.Lock()
        self._enabled = bool(_HF_OK and self.repo and self.token)
        if self._enabled:
            self._ensure_repo()
            threading.Thread(target=self._loop, daemon=True).start()

    def _ensure_repo(self) -> None:
        try:
            HfApi().create_repo(repo_id=self.repo, repo_type="dataset",
                                token=self.token, exist_ok=True)
        except Exception:
            pass

    def sync(self) -> bool:
        """Upload the local file if it grew. Returns True if a push happened."""
        if not self._enabled or not os.path.exists(self.path):
            return False
        try:
            size = os.path.getsize(self.path)
            with self._lock:
                if size == self._last_size:
                    return False
                self._last_size = size
            HfApi().upload_file(
                path_or_fileobj=self.path,
                path_in_repo="leads.jsonl",
                repo_id=self.repo,
                repo_type="dataset",
                token=self.token,
            )
            return True
        except Exception:
            return False

    def _loop(self) -> None:
        while True:
            try:
                self.sync()
            except Exception:
                pass
            time.sleep(self.interval)


_backup = None


def init_backup(path: str = "data/leads.jsonl", repo: str = "",
                token: str = "", interval: int = 60) -> LeadBackup | None:
    """Start the global background mirror (idempotent)."""
    global _backup
    if _backup is None:
        _backup = LeadBackup(path=path, repo=repo, token=token, interval=interval)
    return _backup