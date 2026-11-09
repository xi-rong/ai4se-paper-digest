import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .collectors import Arxiv, iso, rss, weekly, upsert, review_queue
from .storage import LocalStore, GitHubStore, GitStore, Conflict
from .review import add_reviews, add_translations
from .reports import render, selected
from .mailer import send
from .operations import check_config, status_summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI4SE paper digest; no scheduler or credentials bundled")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--state", default="var/state.json")
    parser.add_argument("--storage", choices=["local", "github", "git"], default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("check-config", help="validate configuration without credentials, network or state writes")
    sub.add_parser("pending", help="list durable unsent messages before starting a new report")
    ids = sub.add_parser("seed")
    ids.add_argument("--ids", nargs="+", default=["2609.33382"])
    collect = sub.add_parser("collect")
    collect.add_argument("--weekly", action="store_true")
    collect.add_argument("--rss", action="store_true")
    collect.add_argument("--days", type=int)
    collect.add_argument("--out", default="var/candidates.json")
    review = sub.add_parser("review")
    review.add_argument("path")
    translations = sub.add_parser("translations")
    translations.add_argument("path")
    needs = sub.add_parser("translation-needed")
    needs.add_argument("--kind", choices=["daily", "weekly", "history"], default="daily")
    needs.add_argument("--out", default="var/translations-needed.json")
    preview = sub.add_parser("preview")
    preview.add_argument("--kind", choices=["daily", "weekly", "history"], default="daily")
    preview.add_argument("--out", default="var/preview")
    preview.add_argument("--enqueue", action="store_true", help="explicitly create durable pending outbox entry")
    delivery = sub.add_parser("send")
    delivery.add_argument("id")
    delivery.add_argument("--to", required=True, help="must equal confirmed recipient in config")
    args = parser.parse_args(argv)
    cfg = json.loads(Path(args.config).read_text())
    mode = args.storage or cfg["storage"]["mode"]
    if args.command == "check-config":
        result = check_config(cfg, mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1
    store = (GitHubStore(cfg["storage"]) if mode == "github" else
             GitStore(cfg["storage"]) if mode == "git" else LocalStore(args.state))
    state, revision = store.load()
    if args.command == "status":
        print(json.dumps(status_summary(state), ensure_ascii=False, indent=2))
    elif args.command == "pending":
        pending = [{"id": mid, "kind": message.get("kind"), "status": message.get("status"),
                    "lease_until": message.get("lease_until"), "first_attempt_at": message.get("first_attempt_at"),
                    "last_error": message.get("last_error")} for mid, message in state["outbox"].items()
                   if message.get("status") not in ("sent", "superseded")]
        print(json.dumps({"pending": pending}, ensure_ascii=False, indent=2))
    elif args.command == "seed":
        rows = Arxiv(cfg).ids(args.ids)
        count = upsert(state, rows)
        state["runs"].append({"id": uuid.uuid4().hex, "at": iso(), "type": "seed", "coverage": [
            {"source": "arxiv-id-lookup", "status": "ok", "count": len(rows)}]})
        store.save(state, revision)
        print(json.dumps({"records": len(rows), "new_versions": count}))
    elif args.command == "collect":
        if args.days is not None and args.days < 1:
            raise ValueError("days must be positive")
        now = datetime.now(timezone.utc)
        # Coordinate the two Monday cloud jobs through the durable shared state.
        # A competing run continues with other sources but never duplicates arXiv calls.
        owner = uuid.uuid4().hex
        acquired = False
        last_collect = next((r for r in reversed(state["runs"]) if r.get("type") == "collect" and
                             any(c.get("source") == "arxiv-api" and c.get("status") != "deferred"
                                 for c in r.get("coverage", []))), {})
        last_at = last_collect.get("at")
        cooling = bool(last_at and now - datetime.fromisoformat(last_at) < timedelta(minutes=30) and
                       any(c.get("source") == "arxiv-api" and c.get("http_status") == 429
                           for c in last_collect.get("coverage", [])))
        for attempt in range(3):
            if cooling:
                break
            lease = state.get("arxiv_collection_lease") or {}
            if lease.get("until") and datetime.fromisoformat(lease["until"]) > now:
                break
            state["arxiv_collection_lease"] = {"owner": owner, "until": (now + timedelta(minutes=30)).isoformat()}
            try:
                state, revision = store.save(state, revision)
                acquired = True
                break
            except Conflict:
                state, revision = store.load()
        if not acquired:
            state, revision = store.load()
        cursor = state["cursors"].get("arxiv")
        start = (datetime.fromisoformat(cursor) - timedelta(days=cfg["overlap_days"]) if cursor else now - timedelta(days=cfg["initial_days"]))
        if args.days is not None:
            # Explicit backfills may widen, never narrow the uncovered interval.
            start = min(start, now - timedelta(days=args.days))
        if acquired:
            records, coverage = Arxiv(cfg).collect(start, now)
            # A second task may have saved other sources while the API was running.
            state, revision = store.load()
            lease = state.get("arxiv_collection_lease") or {}
            if lease.get("owner") != owner:
                raise Conflict("arXiv collection lease lost; reload and retry")
            state.pop("arxiv_collection_lease", None)
        else:
            records, coverage = [], [{"source": "arxiv-api", "status": "deferred",
                                      "error": "rate-limit cooldown" if cooling else "another collection is running; cursor retained"}]
        count = upsert(state, records)
        if all(c["status"] == "ok" for c in coverage):
            state["cursors"]["arxiv"] = now.isoformat()
        extra = []
        if args.rss:
            observations, rss_coverage = rss(cfg)
            coverage += rss_coverage
            known = [r for r in observations if r["id"] in state["papers"]]
            extra += [r for r in observations if r["id"] not in state["papers"]]
            upsert(state, known)
        if args.weekly:
            other, other_coverage = weekly(cfg)
            extra += other
            coverage += other_coverage
        run = {"id": uuid.uuid4().hex, "at": iso(), "type": "collect", "from": start.isoformat(),
               "to": now.isoformat(), "coverage": coverage, "new_versions": count,
               "status": "ok" if all(c["status"] == "ok" for c in coverage) else "partial"}
        # Persist raw weekly discoveries and RSS-only IDs for later enrichment.
        run["discovery_candidates"] = extra
        state["runs"].append(run)
        store.save(state, revision)
        output = {"run": run, "papers": review_queue(state["papers"].values()),
                  "additional_candidates": extra}
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(json.dumps({"status": run["status"], "new_versions": count, "review_queue": len(output["papers"]),
                          "coverage": coverage}, ensure_ascii=False, indent=2))
        return 0 if run["status"] == "ok" else 2
    elif args.command == "review":
        reviews = json.loads(Path(args.path).read_text())
        add_reviews(state, reviews)
        store.save(state, revision)
        print(json.dumps({"reviews": len(reviews)}))
    elif args.command == "translation-needed":
        items = [{"paper_id": p["id"], "version": p.get("version"), "title": p["title"],
                  "abstract": p.get("abstract", "")} for p, r in selected(state, args.kind, cfg["max_papers"])
                 if not r.get("title_zh") or not r.get("abstract_zh") or not p.get("abstract")]
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2))
        print(json.dumps({"status": "translation_needed" if items else "ready", "count": len(items), "path": str(path)}))
    elif args.command == "translations":
        translations = json.loads(Path(args.path).read_text())
        add_translations(state, translations)
        store.save(state, revision)
        print(json.dumps({"translations": len(translations)}))
    elif args.command == "preview":
        if args.enqueue:
            missing = [p["id"] for p, r in selected(state, args.kind, cfg["max_papers"])
                       if not r.get("title_zh") or not r.get("abstract_zh") or not p.get("abstract")]
            if missing:
                raise ValueError("translation or original abstract missing; run translation-needed: " + ", ".join(missing))
        message = render(state, args.kind, max_papers=cfg["max_papers"])
        if message is None:
            print(json.dumps({"status": "no_reviewed_unsent_papers", "queued": False}))
            return 0
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".md").write_text(message["markdown"])
        out.with_suffix(".html").write_text(message["html"])
        out.with_suffix(".json").write_text(json.dumps(message, ensure_ascii=False, indent=2))
        if args.enqueue:
            # An immutable message with the same event set retains original delivery state.
            # Reject overlapping daily/history messages before they can be queued twice.
            existing = state["outbox"].get(message["id"])
            if existing is None:
                for old in state["outbox"].values():
                    if old["kind"] != "weekly" and message["kind"] != "weekly" and set(old["event_keys"]) & set(message["event_keys"]):
                        raise ValueError("papers already reserved by another outbox message: deliver/reconcile it first")
                state["outbox"][message["id"]] = message
                store.save(state, revision)
        print(json.dumps({"id": message["id"], "papers": len(message["event_keys"]), "queued": args.enqueue,
                          "html": str(out.with_suffix('.html'))}, ensure_ascii=False))
    elif args.command == "send":
        print(json.dumps({"status": send(store, cfg, args.id, recipient=args.to)}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Avoid credential/HTTP response leakage, while retaining useful exception class.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "detail": str(exc) if isinstance(exc, ValueError) else "see recorded source status; inspect secure service logs"}), file=sys.stderr)
        sys.exit(1)
