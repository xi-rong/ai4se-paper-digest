"""A JSON document with local atomic replace or GitHub Contents API CAS.

CAS conflict aborts the run; callers MUST reload and recompute, never overwrite.
"""
import base64
import copy
import json
import os
import tempfile
import subprocess
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
        sha = data["sha"]
        if data.get("encoding") == "none" or not data.get("content"):
            # Contents responses omit bodies above 1 MB; Git blobs retain base64 bodies.
            data = json.loads(request(f"https://api.github.com/repos/{self.config['repository']}/git/blobs/{sha}",
                                      headers=self.headers())[0])
        return json.loads(base64.b64decode(data["content"])), sha

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


class GitStore:
    """Reuse native Cloud Git auth, with a branch-head lease and no worktree checkout.

    This backend edits only Git objects and a temporary index; source working files stay
    untouched. Network authentication remains entirely with the environment's Git helper.
    """
    def __init__(self, config, cwd=".", remote="origin"):
        self.config, self.cwd, self.remote = config, cwd, remote
        branch = config["branch"]
        if branch == "main" or branch == "master":
            raise ValueError("state must use a dedicated branch")
        self.git("check-ref-format", "refs/heads/" + branch)
        self.cached_head = None

    def git(self, *args, data=None, extra_env=None):
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(["git", *args], cwd=self.cwd, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, timeout=90)
        if result.returncode:
            # Git may include credential-bearing URLs in diagnostics; never emit stderr.
            raise RuntimeError("Git operation failed; inspect sanitized environment diagnostics")
        return result.stdout

    def load(self):
        # Read FETCH_HEAD immediately into an immutable hash. Always use explicit ref.
        self.git("fetch", "--no-tags", self.remote, "refs/heads/" + self.config["branch"])
        head = self.git("rev-parse", "FETCH_HEAD").decode().strip()
        self.cached_head = head
        raw = self.git("show", head + ":" + self.config["path"])
        return json.loads(raw), head

    def save(self, state, expected):
        if not expected or expected != self.cached_head:
            raise Conflict("load the current remote state before writing")
        doc = copy.deepcopy(state)
        doc["revision"] += 1
        payload = json.dumps(doc, ensure_ascii=False, indent=2).encode()
        blob = self.git("hash-object", "-w", "--stdin", data=payload).decode().strip()
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
            self.git("read-tree", expected, extra_env=env)
            self.git("update-index", "--add", "--cacheinfo", "100644", blob, self.config["path"], extra_env=env)
            tree = self.git("write-tree", extra_env=env).decode().strip()
        identity = {"GIT_AUTHOR_NAME": "AI4SE Digest", "GIT_AUTHOR_EMAIL": "digest@users.noreply.github.com",
                    "GIT_COMMITTER_NAME": "AI4SE Digest", "GIT_COMMITTER_EMAIL": "digest@users.noreply.github.com"}
        commit = self.git("commit-tree", tree, "-p", expected, "-m", "digest: checkpoint state",
                          extra_env=identity).decode().strip()
        # --force-with-lease is a compare-and-swap, not an unconditional force push.
        # The new commit has expected as parent. Any concurrent branch update rejects it.
        ref = "refs/heads/" + self.config["branch"]
        try:
            self.git("push", "--porcelain", f"--force-with-lease={ref}:{expected}", self.remote, commit + ":" + ref)
        except RuntimeError:
            raise Conflict("remote push not confirmed (conflict/auth/network); reload and reconcile before retry") from None
        self.cached_head = commit
        return doc, commit
