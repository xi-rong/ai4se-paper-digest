"""Official API/RSS collectors. Failure and truncation are explicit coverage states."""
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from .http import request, get_json

NS = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/",
      "x": "http://arxiv.org/schemas/atom"}


def iso():
    return datetime.now(timezone.utc).isoformat()


def parse_atom(data):
    root = ET.fromstring(data)
    rows = []
    for e in root.findall("a:entry", NS):
        url = e.findtext("a:id", "", NS)
        if "/abs/" not in url:
            raise ValueError("arXiv returned an error entry")
        identifier = url.split("/abs/")[-1]
        base = re.sub(r"v\d+$", "", identifier)
        match = re.search(r"v(\d+)$", identifier)
        version = int(match.group(1)) if match else None
        rows.append({"id": "arxiv:" + base, "arxiv_id": base, "version": version,
                     "title": " ".join(e.findtext("a:title", "", NS).split()),
                     "abstract": " ".join(e.findtext("a:summary", "", NS).split()),
                     "authors": [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)],
                     "submitted_at": e.findtext("a:published", "", NS),
                     "updated_at": e.findtext("a:updated", "", NS),
                     "public_batch_at": None,
                     "categories": [c.attrib["term"] for c in e.findall("a:category", NS)],
                     "primary_category": (e.find("x:primary_category", NS).attrib.get("term")
                                          if e.find("x:primary_category", NS) is not None else None),
                     "doi": e.findtext("x:doi", "", NS).lower() or None,
                     "journal_ref": e.findtext("x:journal_ref", "", NS) or None,
                     "url": "https://arxiv.org/abs/" + base,
                     "sources": ["arxiv-api"], "discovered_at": iso(),
                     "processing_status": "unreviewed", "send_status": "unsent"})
    return rows, int(root.findtext("o:totalResults", "0", NS))


class Arxiv:
    def __init__(self, config):
        self.config = config
        self.last = 0

    def fetch(self, params):
        time.sleep(max(0, self.config["arxiv"]["interval_seconds"] - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        return request("https://export.arxiv.org/api/query?" + urlencode(params),
                       headers={"User-Agent": self.config["user_agent"]})[0]

    def ids(self, ids):
        return parse_atom(self.fetch({"id_list": ",".join(ids)}))[0]

    def collect(self, start, end):
        rows, coverage = [], []
        dates = f"lastUpdatedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]"
        cfg = self.config["arxiv"]
        for query in cfg["queries"]:
            status = {"source": "arxiv-api", "query": query, "from": start.isoformat(),
                      "to": end.isoformat(), "pages": 0, "status": "running", "count": 0}
            try:
                offset = 0
                for _ in range(cfg["max_pages"]):
                    batch, total = parse_atom(self.fetch({"search_query": f"({query}) AND {dates}",
                                                         "start": offset, "max_results": cfg["page_size"],
                                                         "sortBy": "lastUpdatedDate", "sortOrder": "ascending"}))
                    status["pages"] += 1
                    status["total"] = total
                    rows.extend(batch)
                    offset += len(batch)
                    status["count"] = offset
                    if offset >= total:
                        status["status"] = "ok"
                        break
                    if not batch:
                        raise ValueError("empty page before totalResults")
                else:
                    status["status"] = "partial"
                    status["error"] = "page budget exhausted; cursor not advanced"
            except Exception as exc:
                status["status"] = "partial" if status["count"] else "failed"
                status["error"] = type(exc).__name__
            coverage.append(status)
        return rows, coverage


def parse_rss(data, category):
    root = ET.fromstring(data)
    # arXiv uses RSS 2.0 with an arxiv extension; batch time is not submission time.
    ns = {"arxiv": "http://arxiv.org/schemas/atom", "dc": "http://purl.org/dc/elements/1.1/"}
    batch = root.findtext("channel/pubDate")
    result = []
    for item in root.findall("channel/item"):
        link = item.findtext("link", "")
        m = re.search(r"arxiv.org/abs/([^?#]+)", link)
        if not m:
            continue
        identifier = re.sub(r"v\d+$", "", m.group(1))
        result.append({"id": "arxiv:" + identifier, "arxiv_id": identifier,
                       "rss_category": category, "public_batch_at": batch,
                       "announce_type": item.findtext("arxiv:announce_type", "unknown", ns),
                       "sources": ["arxiv-rss"]})
    return result


def rss(config):
    records, coverage = [], []
    for category in config["arxiv"]["categories"]:
        try:
            data = request("https://rss.arxiv.org/rss/" + category,
                           headers={"User-Agent": config["user_agent"]})[0]
            entries = parse_rss(data, category)
            records.extend(entries)
            coverage.append({"source": "arxiv-rss:" + category, "status": "ok", "count": len(entries)})
        except Exception as e:
            coverage.append({"source": "arxiv-rss:" + category, "status": "failed", "error": type(e).__name__})
        time.sleep(config["arxiv"]["interval_seconds"])
    return records, coverage


def weekly(config):
    """Return discovery candidates, NOT automatically reviewed paper records."""
    candidates, coverage = [], []

    def paged(source, url, key, limit=100, max_pages=100):
        offset = 0
        count = 0
        try:
            for _ in range(max_pages):
                data = get_json(url + ("&" if "?" in url else "?") + urlencode({"offset": offset, "limit": limit}))
                batch = data.get("data", [])
                candidates.extend({"source": source, "record": r.get(key, r)} for r in batch)
                count += len(batch)
                if data.get("next") is None:
                    coverage.append({"source": source, "status": "ok", "count": count})
                    return
                offset = data["next"]
                time.sleep(3.1)
            coverage.append({"source": source, "status": "partial", "count": count})
        except Exception as e:
            coverage.append({"source": source, "status": "partial" if count else "failed", "count": count,
                             "error": type(e).__name__})

    if config["semantic_scholar"]["enabled"]:
        seed = config["semantic_scholar"]["seed"]
        fields = "title,authors,year,publicationDate,externalIds,url,abstract"
        paged("s2-citations", f"https://api.semanticscholar.org/graph/v1/paper/{seed}/citations?fields=" + fields, "citingPaper")
        for author in config["semantic_scholar"]["authors"]:
            paged("s2-author:" + author, f"https://api.semanticscholar.org/graph/v1/author/{author}/papers?fields=" + fields, "paper")
        if not config["semantic_scholar"]["authors"]:
            coverage.append({"source": "s2-authors", "status": "unconfigured"})
        try:
            data = get_json(f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{seed}?limit=100&fields=" + fields)
            candidates.extend({"source": "s2-recommendations", "record": r} for r in data.get("recommendedPapers", []))
            coverage.append({"source": "s2-recommendations", "status": "ok", "bounded": 100})
        except Exception as e:
            coverage.append({"source": "s2-recommendations", "status": "failed", "error": type(e).__name__})
    if config["dblp"]["enabled"]:
        for query in config["dblp"]["queries"]:
            count = 0
            try:
                for offset in range(0, 10000, 100):
                    data = get_json("https://dblp.org/search/publ/api?" + urlencode({"q": query, "format": "json", "h": 100, "f": offset}))
                    hits = data["result"]["hits"]
                    batch = hits.get("hit", [])
                    if isinstance(batch, dict):
                        batch = [batch]
                    candidates.extend({"source": "dblp", "record": r["info"]} for r in batch)
                    count += len(batch)
                    if count >= int(hits["@total"]):
                        coverage.append({"source": "dblp:" + query, "status": "ok", "count": count})
                        break
                    if not batch:
                        raise ValueError("unexpected empty DBLP page")
                    time.sleep(3.1)
                else:
                    coverage.append({"source": "dblp:" + query, "status": "partial", "count": count})
            except Exception as e:
                coverage.append({"source": "dblp:" + query, "status": "failed", "count": count, "error": type(e).__name__})
    for repo in config["github_releases"]:
        try:
            data = get_json(f"https://api.github.com/repos/{repo}/releases?per_page=30")
            candidates.extend({"source": "github-release:" + repo, "record": r} for r in data)
            coverage.append({"source": "github-release:" + repo, "status": "partial" if len(data) == 30 else "ok", "count": len(data)})
        except Exception as e:
            coverage.append({"source": "github-release:" + repo, "status": "failed", "error": type(e).__name__})
    for venue in ["ICSE", "FSE", "ASE", "ISSTA", "AI venues", *config["journals"]]:
        coverage.append({"source": venue, "status": "unconfigured", "note": "specific official paper-list adapter required"})
    return candidates, coverage


def upsert(state, records):
    """Only exact DOI/arXiv identifiers merge automatically; title similarity never does."""
    changed = 0
    for record in records:
        rid = record["id"]
        doi = record.get("doi")
        alias = ("doi:" + doi.lower()) if doi else None
        canonical = state["aliases"].get(rid, state["aliases"].get(alias, rid))
        old = state["papers"].get(canonical)
        new = dict(old or {})
        # RSS observations must not wipe out API metadata or reviewed states.
        new.update({k: v for k, v in record.items() if k not in ("sources", "processing_status", "send_status") and v is not None})
        new["id"] = canonical
        new["sources"] = sorted(set((old or {}).get("sources", []) + record.get("sources", [])))
        new["first_discovered_at"] = (old or {}).get("first_discovered_at", record.get("discovered_at", iso()))
        new["last_seen_at"] = iso()
        new["processing_status"] = (old or {}).get("processing_status", "unreviewed")
        new["send_status"] = (old or {}).get("send_status", "unsent")
        if old and record.get("version") and record["version"] != old.get("version"):
            new["processing_status"] = "version_needs_review"
        if not old or old.get("version") != new.get("version"):
            changed += 1
        state["papers"][canonical] = new
        state["aliases"][rid] = canonical
        if alias:
            state["aliases"][alias] = canonical
    return changed


def shortlist(paper):
    """A high-recall review queue only; no final relevance or task-type inference."""
    text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
    se = any(w in text for w in ("software", "repository", "repositories", "program repair", "bug", "coding agent", "swe-bench", "fault localization", "regression test"))
    method = any(w in text for w in ("agent", "repair", "fix", "test", "dependency", "dependencies", "retrieval", "change propagation", "localization", "benchmark"))
    return se and method
