"""Run local release checks without accessing cloud state or sending email."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ("configuration", [sys.executable, "-m", "paper_digest.cli", "--storage", "git", "check-config"]),
    ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
]


def main():
    for name, command in CHECKS:
        print(f"Checking {name}...", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            print(f"{name} failed (exit {result.returncode})", file=sys.stderr)
            return result.returncode
    print("Local checks passed. Cloud execution and delivery require separate verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
