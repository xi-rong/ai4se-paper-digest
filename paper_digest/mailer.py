"""HTTPS mail adapter with durable outbox and bounded provider idempotency."""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from .collectors import iso
from .http import request, RequestError
from .reports import new_daily_paper


def send(store, config, message_id, *, recipient):
    state, revision = store.load()
    message = state["outbox"][message_id]
    if message["status"] == "sent":
        return "already_sent"
    if message["kind"] == "daily":
        now = datetime.now(timezone.utc)
        for key in message["event_keys"]:
            paper = state["papers"].get(key.rsplit(":v", 1)[0])
            if paper is None or not new_daily_paper(paper, now):
                raise ValueError("daily outbox contains a paper outside the three-day window; reconcile before sending")
    cfg = config["mail"]
    if not cfg["recipient"] or recipient != cfg["recipient"]:
        raise ValueError("recipient must exactly match the user-confirmed fixed address")
    provider = cfg["provider"]
    if provider not in ("resend", "brevo"):
        raise ValueError("mail provider is not configured/tested")
    if not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+", recipient):
        raise ValueError("invalid fixed recipient")
    expected_url = {"resend": "https://api.resend.com/emails", "brevo": "https://api.brevo.com/v3/smtp/email"}[provider]
    if cfg["api_url"] != expected_url:
        raise ValueError("mail credential destination must match the selected provider endpoint")
    token = os.environ.get(cfg["token_env"])
    if not token or not cfg["sender"]:
        raise ValueError("mail sender/credential missing")
    now = datetime.now(timezone.utc)
    if message.get("first_attempt_at"):
        elapsed = now - datetime.fromisoformat(message["first_attempt_at"])
        limit = timedelta(minutes=14) if provider == "brevo" else timedelta(hours=cfg["max_idempotency_hours"])
        if elapsed > limit:
            raise ValueError("provider deduplication window expired: reconcile provider logs before retry")
    if message["status"] == "sending" and datetime.fromisoformat(message["lease_until"]) > now:
        raise ValueError("another sender holds the lease")
    if message["status"] not in ("pending", "retry", "sending"):
        raise ValueError("unknown delivery state")
    if provider == "brevo":
        payload = {"sender": {"email": cfg["sender"]}, "to": [{"email": recipient}],
                   "subject": message["subject"], "htmlContent": message["html"],
                   "textContent": message["markdown"], "headers": {
                       "idempotencyKey": str(uuid.UUID(bytes=hashlib.sha256(message_id.encode()).digest()[:16], version=4))}}
        headers = {"api-key": token, "Content-Type": "application/json"}
    else:
        payload = {"from": cfg["sender"], "to": [recipient], "subject": message["subject"],
                   "html": message["html"], "text": message["markdown"]}
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
                   "Idempotency-Key": "ai4se-" + message_id}
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    if message.get("payload_hash") and message["payload_hash"] != payload_hash:
        raise ValueError("delivery payload changed: reconcile original send before changing recipient/content")
    owner = uuid.uuid4().hex
    message.update(status="sending", lease_owner=owner,
                   lease_until=(now + timedelta(minutes=10)).isoformat(),
                   first_attempt_at=message.get("first_attempt_at", iso()), payload_hash=payload_hash)
    state, revision = store.save(state, revision)  # durable claim BEFORE external side effect
    try:
        result = json.loads(request(cfg["api_url"], method="POST", body=json.dumps(payload).encode(),
                                    headers=headers, attempts=1)[0])
        response_id = result.get("messageId") if provider == "brevo" else result.get("id")
        if not response_id:
            raise RequestError(None, True)
        outcome, provider_id = "sent", response_id
    except (ValueError, AttributeError):
        outcome, provider_id = "retry", None
        error = {"type": "invalid_response", "status": None, "uncertain": True}
    except RequestError as exc:
        outcome, provider_id = "retry", None
        error = {"type": "RequestError", "status": exc.status, "uncertain": exc.uncertain}
    # Reload to retain concurrent collectors' state; verify the sending lease.
    state, revision = store.load()
    current = state["outbox"][message_id]
    if current.get("lease_owner") != owner:
        raise ValueError("delivery lease lost: reconcile provider logs")
    current.update(status=outcome, provider_id=provider_id)
    if outcome == "sent":
        current["sent_at"] = iso()  # API accepted, not proof of inbox delivery
        if current["kind"] != "weekly":
            for key in current["event_keys"]:
                pid = key.rsplit(":v", 1)[0]
                state["papers"][pid]["send_status"] = "sent"
    else:
        current["last_error"] = error
    store.save(state, revision)
    return outcome
