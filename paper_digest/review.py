"""Validated evidence records authored by the running Codex Agent; no paid model API."""
from .collectors import iso

TASKS = {"multi_repo_coordinated", "external_repo_context", "single_repo_cross_file",
         "multi_repo_dataset_single_target", "single_repo_other", "unknown"}
REQUIRED = ("paper_id", "version", "priority", "task_type", "summary_zh", "relevance_reason",
            "task_setting", "method", "evidence", "research_use", "reading_advice",
            "basis", "evidence_urls", "publication_status", "links")


def add_reviews(state, reviews):
    for review in reviews:
        missing = [k for k in REQUIRED if k not in review]
        if missing:
            raise ValueError("missing review fields: " + ", ".join(missing))
        pid = state["aliases"].get(review["paper_id"], review["paper_id"])
        if pid not in state["papers"]:
            raise ValueError("unknown paper: " + pid)
        paper = state["papers"][pid]
        if review["version"] != paper.get("version"):
            raise ValueError("review version must match collected version")
        if review["priority"] not in ("P1", "P2", "P3", "exclude"):
            raise ValueError("invalid priority")
        if review["task_type"] not in TASKS:
            raise ValueError("invalid task_type")
        if review["basis"] not in ("abstract", "fulltext"):
            raise ValueError("invalid evidence basis")
        if not review["evidence_urls"]:
            raise ValueError("at least one evidence URL required")
        for url in review["evidence_urls"]:
            if not url.startswith("https://"):
                raise ValueError("invalid evidence URL")
        for link in review["links"]:
            if not all(link.get(k) for k in ("url", "kind", "verified_at", "evidence_url")):
                raise ValueError("code/data links require provenance and verification time")
            if not link["url"].startswith("https://"):
                raise ValueError("HTTPS links required")
        record = dict(review, paper_id=pid, reviewed_at=iso())
        state["reviews"][pid + ":v" + str(review["version"])] = record
        paper["processing_status"] = "excluded" if review["priority"] == "exclude" else "reviewed"


def review_for(state, paper):
    return state["reviews"].get(paper["id"] + ":v" + str(paper.get("version")))
