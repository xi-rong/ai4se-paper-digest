#!/usr/bin/env python3
"""Read-only bridge check. No credentials, AUTH or mail delivery; stdout JSON only."""
import json
import os
import platform
import shutil
import smtplib
import ssl
import subprocess
from datetime import datetime, timezone


def run(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, ""


def main():
    result = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "execution": {"system": platform.system(), "architecture": platform.machine(),
                      "python": platform.python_version(), "cpu_count": os.cpu_count(),
                      "root_disk_free_gib": round(shutil.disk_usage('/').free / 2**30, 2)},
        "changes_made": False,
        "credentials_read": False,
        "smtp_auth_attempted": False,
        "email_sent": False,
    }
    tailscale = shutil.which("tailscale")
    result["tailscale"] = {"installed": bool(tailscale)}
    if tailscale:
        code, raw = run([tailscale, "status", "--json"])
        result["tailscale"]["status_exit_code"] = code
        try:
            status = json.loads(raw)
            # Never print peers, usernames, keys, auth URLs or complete status output.
            result["tailscale"].update(backend_state=status.get("BackendState"),
                                      self_online=status.get("Self", {}).get("Online"),
                                      self_ips=status.get("TailscaleIPs", []))
        except (ValueError, TypeError, AttributeError):
            result["tailscale"]["status_readable"] = False
    result["tcp_forwarder"] = {"socat_installed": bool(shutil.which("socat"))}
    smtp = {"host": "smtp.126.com", "port": 465, "timeout_seconds": 15,
            "stage": "tcp_or_tls", "tls_verified": False}
    result["smtp"] = smtp
    try:
        cafile = os.environ.get("SSL_CERT_FILE")
        if not cafile and os.path.exists("/etc/ssl/cert.pem"):
            cafile = "/etc/ssl/cert.pem"
        context = ssl.create_default_context(cafile=cafile)
        with smtplib.SMTP_SSL("smtp.126.com", 465, local_hostname="digest-probe.invalid",
                              timeout=15, context=context) as client:
            smtp.update(stage="ehlo", tls_verified=True, tls_version=client.sock.version())
            code, _ = client.ehlo()
            smtp.update(ehlo_code=code, auth_mechanisms=client.esmtp_features.get("auth", "").split())
        smtp["stage"] = "complete"
    except (OSError, ssl.SSLError, smtplib.SMTPException) as exc:
        smtp.update(error_type=type(exc).__name__, errno=getattr(exc, "errno", None),
                    smtp_code=getattr(exc, "smtp_code", None))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if smtp.get("ehlo_code") == 250 else 2


if __name__ == "__main__":
    raise SystemExit(main())
