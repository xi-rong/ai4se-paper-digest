"""Validated evidence records authored by the running Codex Agent; no paid model API."""
from .collectors import iso

TASKS = {"multi_repo_coordinated", "external_repo_context", "single_repo_cross_file",
         "multi_repo_dataset_single_target", "single_repo_other", "unknown"}
REQUIRED = ("paper_id", "version", "priority", "task_type", "summary_zh", "relevance_reason",
            "task_setting", "method", "evidence", "research_use", "reading_advice",
            "basis", "evidence_urls", "publication_status", "links")


def add_reviews(state, reviews):
    if not isinstance(reviews, list):
        raise ValueError("reviews must be a list")
    prepared = []
    for review in reviews:
        if not isinstance(review, dict):
            raise ValueError("each review must be an object")
        missing = [k for k in REQUIRED if k not in review]
        if missing:
            raise ValueError("missing review fields: " + ", ".join(missing))
        for field in ("paper_id", "summary_zh", "relevance_reason", "task_setting", "method",
                      "evidence", "research_use", "reading_advice", "publication_status"):
            if not isinstance(review[field], str) or not review[field].strip():
                raise ValueError("review field must be nonempty text: " + field)
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
        if not isinstance(review["evidence_urls"], list) or not review["evidence_urls"]:
            raise ValueError("at least one evidence URL required")
        for url in review["evidence_urls"]:
            if not isinstance(url, str) or not url.startswith("https://"):
                raise ValueError("invalid evidence URL")
        if not isinstance(review["links"], list):
            raise ValueError("links must be a list")
        for link in review["links"]:
            if not isinstance(link, dict) or not all(isinstance(link.get(k), str) and link[k].strip() for k in ("url", "kind", "verified_at", "evidence_url")):
                raise ValueError("code/data links require provenance and verification time")
            if not link["url"].startswith("https://") or not link["evidence_url"].startswith("https://"):
                raise ValueError("HTTPS links required")
        prepared.append((pid, paper, review))
    # Validate the whole batch before mutating any paper or review.
    for pid, paper, review in prepared:
        previous = review_for(state, paper) or {}
        saved_translations = {k: previous[k] for k in ("title_zh", "abstract_zh") if k in previous}
        record = dict(saved_translations)
        record.update(review, paper_id=pid, reviewed_at=iso())
        state["reviews"][pid + ":v" + str(review["version"])] = record
        paper["processing_status"] = "excluded" if review["priority"] == "exclude" else "reviewed"


def review_for(state, paper):
    return state["reviews"].get(paper["id"] + ":v" + str(paper.get("version")))


def add_translations(state, translations):
    """Attach agent translations to an exact reviewed paper version, atomically."""
    if not isinstance(translations, list):
        raise ValueError("translations must be a list")
    prepared = []
    for item in translations:
        if not isinstance(item, dict):
            raise ValueError("translation must be an object")
        pid = state["aliases"].get(item.get("paper_id"), item.get("paper_id"))
        paper = state["papers"].get(pid)
        if not paper or item.get("version") != paper.get("version"):
            raise ValueError("translation requires the current paper version")
        review = review_for(state, paper)
        if review is None or not paper.get("abstract", "").strip():
            raise ValueError("translation requires a reviewed paper and original abstract")
        if any(not isinstance(item.get(field), str) or not item[field].strip() for field in ("title_zh", "abstract_zh")):
            raise ValueError("title_zh and abstract_zh must be nonempty")
        prepared.append((review, item))
    for review, item in prepared:
        review.update(title_zh=item["title_zh"].strip(), abstract_zh=item["abstract_zh"].strip())
