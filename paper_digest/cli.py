import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .collectors import Arxiv, iso, rss, weekly, upsert, shortlist
from .storage import LocalStore, GitHubStore
from .review import add_reviews
from .reports import render
from .mailer import send


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI4SE paper digest; no scheduler or credentials bundled")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--state", default="var/state.json")
    parser.add_argument("--storage", choices=["local", "github"], default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    ids = sub.add_parser("seed")
    ids.add_argument("--ids", nargs="+", default=["2609.33382"])
    collect = sub.add_parser("collect")
    collect.add_argument("--weekly", action="store_true")
    collect.add_argument("--rss", action="store_true")
    collect.add_argument("--days", type=int)
    collect.add_argument("--out", default="var/candidates.json")
    review = sub.add_parser("review")
    review.add_argument("path")
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
    store = GitHubStore(cfg["storage"]) if mode == "github" else LocalStore(args.state)
    state, revision = store.load()
    if args.command == "status":
        print(json.dumps({"revision": state["revision"], "papers": len(state["papers"]),
                          "reviews": len(state["reviews"]), "outbox": {k: v["status"] for k, v in state["outbox"].items()},
                          "last_run": state["runs"][-1] if state["runs"] else None}, ensure_ascii=False, indent=2))
    elif args.command == "seed":
        rows = Arxiv(cfg).ids(args.ids)
        count = upsert(state, rows)
        state["runs"].append({"id": uuid.uuid4().hex, "at": iso(), "type": "seed", "coverage": [
            {"source": "arxiv-id-lookup", "status": "ok", "count": len(rows)}]})
        store.save(state, revision)
        print(json.dumps({"records": len(rows), "new_versions": count}))
    elif args.command == "collect":
        now = datetime.now(timezone.utc)
        cursor = state["cursors"].get("arxiv")
        start = (datetime.fromisoformat(cursor) - timedelta(days=cfg["overlap_days"]) if cursor else now - timedelta(days=cfg["initial_days"]))
        if args.days is not None:
            if args.days < 1:
                raise ValueError("days must be positive")
            # Explicit backfills may widen, never narrow the uncovered interval.
            start = min(start, now - timedelta(days=args.days))
        records, coverage = Arxiv(cfg).collect(start, now)
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
        output = {"run": run, "papers": [p for p in state["papers"].values()
                  if shortlist(p) and p["processing_status"] in ("unreviewed", "version_needs_review")],
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
    elif args.command == "preview":
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
