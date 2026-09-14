"""Alert timing + non-blocking guarantees for the new-lead email alert.

Contract:
1. The alert fires exactly once per session, at contact capture
   (_do_ask_contact), even if the visitor never picks a service.
2. Later lead saves (service select / whatsapp offer) stay silent.
3. notify_new_lead never blocks the caller (daemon thread).
"""
import time

import chatbot.engine as E
import chatbot.leads as L


def _engine(tmp_path):
    return E.Engine(collection=None,
                    retrieve_fn=lambda *a, **k: [],
                    leads_path=str(tmp_path / "leads.jsonl"))


def test_notify_fires_at_contact_and_not_again_at_service(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(E, "notify_new_lead", lambda lead: calls.append(lead))
    eng = _engine(tmp_path)
    s = E.Session("s1", lang="ar")
    eng.handle(s, "")                 # greet -> ask_name
    eng.handle(s, "ليلى")             # ask_name -> ask_contact
    assert calls == []
    eng.handle(s, "laila@mail.com")   # ask_contact -> ask_service + notify
    assert len(calls) == 1
    assert calls[0]["contact"] == "laila@mail.com"
    assert calls[0]["last_state"] == "ask_contact"
    assert s.notified is True
    eng.handle(s, "شات بوت ذكي")      # service_detail: row saved, still 1 notify
    assert len(calls) == 1


def test_notify_returns_immediately(tmp_path, monkeypatch):
    def slow_send(subject, body):
        time.sleep(3)
        return True
    monkeypatch.setattr(L, "_send_email", slow_send)
    t0 = time.time()
    L.notify_new_lead({"name": "x", "session_id": "s"})
    assert time.time() - t0 < 1.0
