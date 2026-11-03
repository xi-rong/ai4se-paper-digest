"""Bounded HTTPS requests; never log headers, placeholders or response error bodies."""
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


class RequestError(RuntimeError):
    def __init__(self, status=None, uncertain=False):
        self.status, self.uncertain = status, uncertain
        super().__init__(f"HTTPS request failed (status={status}, uncertain={uncertain})")


def request(url, *, method="GET", body=None, headers=None, attempts=3, timeout=25):
    if not url.startswith("https://"):
        raise ValueError("HTTPS required")
    # macOS Python distributions may lack their own CA bundle. Keep TLS validation.
    cafile = os.environ.get("SSL_CERT_FILE")
    if not cafile and os.path.exists("/etc/ssl/cert.pem"):
        cafile = "/etc/ssl/cert.pem"
    context = ssl.create_default_context(cafile=cafile)
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
                data = response.read(15_000_001)
                if len(data) > 15_000_000:
                    raise ValueError("response exceeds 15 MB limit")
                return data, dict(response.headers)
        except urllib.error.HTTPError as exc:
            retryable = exc.code in (408, 429, 500, 502, 503, 504)
            if not retryable or attempt == attempts - 1:
                raise RequestError(exc.code, method != "GET" and retryable) from None
            retry = exc.headers.get("Retry-After", "")
            try:
                delay = float(retry)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError):
                    delay = 2 ** (attempt + 1)
            # Preserve long server backoffs for the next run; don't retry earlier.
            if delay > 45:
                raise RequestError(exc.code, method != "GET") from None
            time.sleep(max(3.1, delay))
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == attempts - 1:
                raise RequestError(None, method != "GET") from None
            time.sleep(max(3.1, 2 ** (attempt + 1)))


def get_json(url, headers=None):
    return json.loads(request(url, headers=headers)[0])
