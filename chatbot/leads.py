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
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

try:
    from huggingface_hub import HfApi
    _HF_OK = True
except Exception:                       # pragma: no cover - fallback offline
    _HF_OK = False


# --- Email alert (optional, via SMTP env vars) --------------------------------
# Enable by setting:  ALERT_SMTP_HOST, ALERT_SMTP_PORT, ALERT_EMAIL_FROM,
#   ALERT_EMAIL_TO, ALERT_SMTP_USER, ALERT_SMTP_PASSWORD   (Gmail works directly).
def _email_config() -> dict:
    return {
        "host": os.environ.get("ALERT_SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.environ.get("ALERT_SMTP_PORT", "587")),
        "from_": os.environ.get("ALERT_EMAIL_FROM", "").strip(),
        "to": os.environ.get("ALERT_EMAIL_TO", "").strip(),
        "user": os.environ.get("ALERT_SMTP_USER", "").strip(),
        "password": os.environ.get("ALERT_SMTP_PASSWORD", "").strip(),
        "site": os.environ.get("ALERT_SITE_NAME", "AM.Portfolio").strip(),
    }


def _smtp_configured(cfg: dict) -> bool:
    return bool(cfg["host"] and cfg["to"] and cfg["from_"] and cfg["user"] and cfg["password"])


def _send_email(subject: str, body: str) -> bool:
    """Send via SMTP (STARTTLS). Returns True on success; raises on failure."""
    cfg = _email_config()
    if not _smtp_configured(cfg):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{cfg['site']} <{cfg['from_']}>"
    msg["To"] = cfg["to"]
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    return True


def notify_new_lead(lead: dict) -> None:
    """Fire-and-forget email alert in a daemon thread; logs the outcome.

    Never blocks the caller and never raises: the network send happens off
    the request path, and failures are printed to stdout (visible in Space
    logs) instead of breaking the chat reply. No secrets are ever logged.
    """
    cfg = _email_config()
    site = cfg["site"]
    name = lead.get("name", "")
    service = lead.get("service", "")
    contact = lead.get("contact", "")
    lang = lead.get("lang", "")
    if lang == "ar":
        subject = f"🔔 {site} — مشترك جديد: {name or 'زائر'}"
        lang_label = "العربية"
        body = (
            f"📣 مشترك جديد عبر الشات بوت في {site}\n\n"
            f"• الاسم: {name}\n"
            f"• الخدمة المطلوبة: {service}\n"
            f"• طريقة التواصل: {contact}\n"
            f"• اللغة: {lang_label}\n"
            f"• الوقت: {lead.get('ts', '')}\n"
            f"• الجلسة: {lead.get('session_id', '')}\n"
        )
    else:
        subject = f"🔔 {site} — New subscriber: {name or 'Visitor'}"
        lang_label = "English"
        body = (
            f"📣 A new visitor subscribed via the chat bot on {site}\n\n"
            f"• Name: {name}\n"
            f"• Service requested: {service}\n"
            f"• Contact method: {contact}\n"
            f"• Language: {lang_label}\n"
            f"• Time: {lead.get('ts', '')}\n"
            f"• Session: {lead.get('session_id', '')}\n"
        )
    if not _smtp_configured(_email_config()):
        print("[lead-alert] skipped (SMTP not configured)")
        return

    def _run() -> None:
        try:
            ok = _send_email(subject, body)
        except Exception as e:  # network/auth/timeout — never break the reply
            print(f"[lead-alert] FAILED session={lead.get('session_id', '')} "
                  f"err={type(e).__name__}: {e}")
            return
        print(f"[lead-alert] {'sent' if ok else 'FAILED'} "
              f"session={lead.get('session_id', '')}")

    threading.Thread(target=_run, daemon=True).start()


def append_lead(lead: dict, path: str = "data/leads.jsonl", notify: bool = True) -> None:
    """Append a single lead as a JSON line. Creates parent dirs as needed."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    line = json.dumps(lead, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if notify:
        try:
            notify_new_lead(lead)
        except Exception:
            pass


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