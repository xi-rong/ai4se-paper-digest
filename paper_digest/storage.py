"""A JSON document with local atomic replace or GitHub Contents API CAS.

CAS conflict aborts the run; callers MUST reload and recompute, never overwrite.
"""
import base64
import copy
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import quote
from .http import request, RequestError


def empty():
    return {"schema": 1, "revision": 0, "papers": {}, "aliases": {}, "reviews": {},
            "outbox": {}, "runs": [], "cursors": {}}


class Conflict(RuntimeError):
    pass


class LocalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        raw = self.path.read_bytes() if self.path.exists() else None
        return (json.loads(raw) if raw else empty()), raw

    def save(self, state, expected):
        import fcntl
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            raw = self.path.read_bytes() if self.path.exists() else None
            if raw != expected:
                raise Conflict("state changed; reload and recompute")
            doc = copy.deepcopy(state)
            doc["revision"] += 1
            payload = json.dumps(doc, ensure_ascii=False, indent=2).encode()
            fd, name = tempfile.mkstemp(dir=self.path.parent)
            try:
                with os.fdopen(fd, "wb") as out:
                    out.write(payload)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        return doc, payload


class GitHubStore:
    def __init__(self, config):
        self.config = config
        self.base = (f"https://api.github.com/repos/{config['repository']}/contents/"
                     + quote(config["path"]))

    def headers(self):
        token = os.environ.get(self.config["token_env"])
        if not token:
            raise ValueError("missing GitHub credential in environment/vault")
        return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"}

    def load(self):
        # The branch must exist. A missing file may be initialized, a missing branch may not.
        branch = quote(self.config["branch"], safe="")
        request(f"https://api.github.com/repos/{self.config['repository']}/git/ref/heads/{branch}", headers=self.headers())
        try:
            data = json.loads(request(self.base + "?ref=" + branch, headers=self.headers())[0])
        except RequestError as e:
            if e.status == 404:
                return empty(), None
            raise
        return json.loads(base64.b64decode(data["content"])), data["sha"]

    def save(self, state, expected):
        doc = copy.deepcopy(state)
        doc["revision"] += 1
        body = {"message": "digest: checkpoint state", "branch": self.config["branch"],
                "content": base64.b64encode(json.dumps(doc, ensure_ascii=False, indent=2).encode()).decode()}
        if expected:
            body["sha"] = expected
        try:
            result = json.loads(request(self.base, method="PUT", body=json.dumps(body).encode(),
                                        headers=self.headers(), attempts=1)[0])
        except RequestError as e:
            if e.status in (409, 422):
                raise Conflict("GitHub CAS rejected: reload and recompute") from None
            raise
        return doc, result["content"]["sha"]
