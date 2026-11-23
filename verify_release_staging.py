#!/usr/bin/env python3
"""Read-only, best-effort local GitHub review of CargoFlow tracked files.

This is not a guarantee that a public push is safe. Review source and Git
history manually before publishing.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DENY_PARTS = {
    '.venv', 'venv', '.cargoflow_backups', '__pycache__',
    'node_modules', 'media', 'uploads', 'exports', 'release_reports',
    'payload', 'stage2_files', 'stage3_files', 'stage4_files', 'stage5_files',
    'stage6_files', 'stage7_files', 'stage8_files', 'stage9_files', 'stage10_files',
    'release_files',
}
DENY_SUFFIXES = (
    '.sqlite3', '.sqlite3-shm', '.sqlite3-wal', '.db', '.db-shm',
    '.db-wal', '.db-journal', '.zip', '.csv', '.xlsx', '.xls', '.log',
    '.pem', '.key', '.p12', '.pfx', '.pyc', '.bak', '.sql', '.dump',
)
SAFE_TEXT_SUFFIXES = {'.py', '.html', '.htm', '.css', '.js', '.svg', '.md', '.txt', '.yml', '.yaml', '.cfg', '.ini', '.toml'}
SECRET_REGEXES = {
    'private key block': re.compile(r'-----BEGIN\s+(?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'GitHub access token': re.compile(r'gh[pousr]_[A-Za-z0-9_]{30,}'),
    'AWS access key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'OpenAI-style access token': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{28,}\b'),
    'possibly hardcoded secret': re.compile(
        r'(?im)^\s*(?:DJANGO_SECRET_KEY|PGPASSWORD|DATABASE_URL|GITHUB_TOKEN|AWS_SECRET_ACCESS_KEY)\s*=\s*[\'\"][^\'\"]{12,}[\'\"]'
    ),
}


def bad_path(path: str) -> str | None:
    normalized = path.replace('\\', '/').lower().removeprefix('./')
    parts = normalized.split('/')
    leaf = parts[-1]
    if set(parts) & DENY_PARTS:
        return 'temporary/local/private folder'
    if leaf == '.cargoflow-secret' or leaf == '.env' or leaf.startswith('.env.') and leaf != '.env.example':
        return 'secret environment file'
    if leaf.startswith('install_cargoflow_stage'):
        return 'local stage installer (not release source)'
    if leaf.startswith('cargoflow_stage') and leaf.endswith('.zip'):
        return 'installer ZIP archive'
    if leaf.endswith(DENY_SUFFIXES):
        return 'database, data export, key, or build artifact'
    return None


def main() -> int:
    print('CargoFlow release Git safety scan (local/read-only)')
    try:
        result = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'], capture_output=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print('NOT VERIFIED: Git is missing or unresponsive.')
        return 2
    if result.returncode:
        print('NOT VERIFIED: Run this from the CargoFlow project root after git init.')
        return 2

    files = [p.decode('utf-8', errors='replace') for p in result.stdout.split(b'\0') if p]
    if len(files) < 15:
        print(f'NOT VERIFIED: only {len(files)} tracked files; expected more CargoFlow source files.')
        return 2

    findings: list[tuple[str, str]] = []
    for relative in files:
        reason = bad_path(relative)
        if reason:
            findings.append((relative, reason))
            continue
        file = ROOT / relative
        if not file.is_file() or file.is_symlink():
            findings.append((relative, 'tracked file missing or symlink'))
            continue
        if file.stat().st_size > 1_000_000:
            findings.append((relative, 'file larger than 1 MB: manual review required'))
            continue
        if file.suffix.lower() in SAFE_TEXT_SUFFIXES or file.name == '.env.example':
            data = file.read_text(encoding='utf-8', errors='replace')
            for label, pattern in SECRET_REGEXES.items():
                if pattern.search(data):
                    findings.append((relative, label))

    if findings:
        print('STOP: Review these tracked files BEFORE committing or pushing:')
        for path, reason in findings:
            print(' -', path, ':', reason)
        print('The scanner made no changes. Do not push until every issue is resolved.')
        return 1

    print(f'PASS: {len(files)} tracked files checked; no common risky paths or secret patterns detected.')
    print('This is NOT a comprehensive security audit. Manually review source, screenshots, and Git history.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
