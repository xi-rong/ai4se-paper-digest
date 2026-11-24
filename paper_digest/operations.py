"""Read-only configuration checks and compact, sanitized operational status."""
import re
from collections import Counter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def check_config(config, mode):
    errors, notes = [], []
    try:
        ZoneInfo(config.get("timezone", ""))
    except (ValueError, TypeError, KeyError, ZoneInfoNotFoundError):
        errors.append("invalid timezone")
    schedule = config.get("schedule", {})
    clock = r"(?:[01]\d|2[0-3]):[0-5]\d"
    for kind in ("daily", "weekly"):
        interval = schedule.get(kind + "_interval_days")
        if kind + "_interval_days" in schedule and (type(interval) is not int or interval < 1):
            errors.append("invalid " + kind + " interval")
        pattern = clock
        if kind == "weekly" and interval is None:
            # Accept configurations from the former weekday-based schedule.
            pattern = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) " + clock
        if not re.fullmatch(pattern, str(schedule.get(kind, ""))):
            errors.append("invalid " + kind + " schedule")
    notes.append("schedule is configuration intent; inspect cloud scheduler separately")
    if mode == "local":
        notes.append("local state is not shared across cloud tasks")
    if mode not in ("local", "git", "github"):
        errors.append("invalid storage mode")
    storage = config.get("storage", {})
    if mode in ("git", "github") and storage.get("branch") in (None, "", "main", "master"):
        errors.append("remote state needs a dedicated branch")
    mail = config.get("mail", {})
    endpoints = {"brevo": "https://api.brevo.com/v3/smtp/email", "resend": "https://api.resend.com/emails"}
    if mail.get("provider") not in endpoints or endpoints.get(mail.get("provider")) != mail.get("api_url"):
        errors.append("mail provider endpoint mismatch")
    for field in ("recipient", "sender"):
        if not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+", str(mail.get(field, ""))):
            errors.append("invalid mail " + field)
    if not mail.get("token_env"):
        errors.append("mail credential environment name missing")
    for field in ("initial_days", "overlap_days", "max_papers"):
        value = config.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append("invalid " + field)
    return {"status": "invalid" if errors else "ok", "errors": errors, "notes": notes,
            "storage_mode": mode, "schedule_config": schedule, "timezone": config.get("timezone")}


def status_summary(state):
    counts = Counter(m.get("status", "unknown") for m in state.get("outbox", {}).values())
    last = next((r for r in reversed(state.get("runs", [])) if r.get("type") == "collect"), None)
    summary = None
    if last:
        # Do not print candidate abstracts, raw payloads, request bodies, or credentials.
        keys = ("source", "status", "count", "pages", "error", "http_status", "retry_at")
        summary = {k: last.get(k) for k in ("id", "at", "type", "status", "from", "to", "new_versions")}
        summary["coverage"] = [{k: c[k] for k in keys if k in c} for c in last.get("coverage", [])]
    return {"revision": state.get("revision", 0), "papers": len(state.get("papers", {})),
            "reviews": len(state.get("reviews", {})), "outbox_counts": dict(counts),
            "outbox": {k: v.get("status", "unknown") for k, v in state.get("outbox", {}).items()},
            "last_run": summary, "arxiv_cursor": state.get("cursors", {}).get("arxiv"),
            "note": "delivery status sent means provider accepted, not confirmed inbox delivery"}
