"""Check tracked CargoFlow files for common accidental data/secret exposure.

Run from CargoFlow root using: python check_github_safety.py
No changes are made to your project or Git repository.
"""
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parent


def prohibited(name):
    normalized = name.replace("\\", "/").lower()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = normalized.split("/")
    leaf = parts[-1]
    if any(x in parts for x in (".venv", "venv", ".cargoflow_backups", "__pycache__", "node_modules")):
        return True
    if leaf == ".cargoflow-secret" or leaf == ".env" or (leaf.startswith(".env.") and leaf != ".env.example"):
        return True
    if leaf.endswith((".sqlite3", ".sqlite3-shm", ".sqlite3-wal", ".db", ".db-shm", ".db-wal", ".pem", ".key", ".p12", ".log", ".zip", ".pyc")):
        return True
    return False


def tracked_files():
    try:
        result = subprocess.run(
            ["git", "-C", str(BASE), "ls-files", "--cached", "-z"],
            capture_output=True, timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print("Git unavailable or timed out:", type(exc).__name__)
        return None
    if result.returncode != 0:
        print("No Git repository detected. Initialize Git, then rerun this check BEFORE publishing.")
        return None
    return [x.decode("utf-8", errors="replace") for x in result.stdout.split(b"\0") if x]


def scan_file(name):
    # Scan text files that Git will commit; skip binary and large files.
    ext = Path(name).suffix.lower()
    if ext not in {".py", ".txt", ".md", ".json", ".yaml", ".yml", ".ini", ".toml", ".cfg", ".sh", ".ps1"}:
        return []
    path = BASE / name
    if not path.is_file() or path.stat().st_size > 1_000_000:
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", text):
        findings.append("private key material")
    if re.search(r"(?im)^\s*(?:DJANGO_SECRET_KEY|PGPASSWORD|DATABASE_URL)\s*=\s*['\"][^'\"]{10,}['\"]", text):
        findings.append("possible hard-coded credential")
    return findings


def main():
    print("CARGOFLOW - GITHUB SAFETY SCAN (read-only)")
    tracked = tracked_files()
    if tracked is None:
        print("Status: NOT VERIFIED. This is expected before 'git init'.")
        return 2
    problems = []
    for name in tracked:
        if prohibited(name):
            problems.append((name, "private data, binary archive, or build artifact"))
        else:
            for category in scan_file(name):
                problems.append((name, category))
    if problems:
        print("\nSTOP: Potentially sensitive or unnecessary tracked files:")
        for file_name, reason in problems:
            print(f" - {file_name}: {reason}")
        print("Remove files from Git's index safely before pushing. Do not delete your local database.")
        return 1
    print(f"PASS: No common risky files found in {len(tracked)} tracked files.")
    print("Manual review is still required. This scan cannot guarantee there are no secrets or personal records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
