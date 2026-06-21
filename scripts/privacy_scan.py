#!/usr/bin/env python3
"""Block publication when a repository appears to contain secrets or private runtime data."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
PRIVATE_DIR_NAMES = {"data", "private", "runtime", "scan-results", "people", "evidence", "opportunities"}
SECRET_PATTERNS = {
    "Feishu App Secret": re.compile(
        r"(?:APP_SECRET\s*=\s*(?!\.\.\.|example|your[-_])[A-Za-z0-9_-]{12,}|"
        r"(?i:app[_ -]?secret)\s*[:=]\s*[\"'](?!\.\.\.|example|your[-_])[A-Za-z0-9_-]{12,}[\"'])"
    ),
    "Access token": re.compile(
        r"(?:ACCESS_TOKEN\s*=\s*(?!\.\.\.|example|your-)[A-Za-z0-9._-]{16,}|"
        r"(?i:access[_ -]?token)\s*[:=]\s*[\"'](?!\.\.\.|example|your-)[A-Za-z0-9._-]{16,}[\"'])"
    ),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Real Feishu App ID": re.compile(r"\bcli_[A-Za-z0-9]{12,}\b"),
    "Real Feishu Chat ID": re.compile(r"\boc_[A-Za-z0-9]{16,}\b"),
    "Real Feishu Open ID": re.compile(r"\bou_[A-Za-z0-9]{16,}\b"),
    "Local user absolute path": re.compile(r"(?:" + "/Us" + r"ers/|/ho" + r"me/)[^/\s\"']+/"),
    "Private instance path": re.compile(
        r"(?:" + "/Us" + r"ers/|/ho" + r"me/)[^\s\"']+/(?:晓儿-private|personal-network-data(?:-backup|-noisy|-validation)?)"
    ),
}
ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".py", ".yaml", ".yml", ".toml", ".env", ""}


def scan(root: Path) -> list[str]:
    findings = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_dir() and path.name in PRIVATE_DIR_NAMES:
            findings.append(f"私有运行目录不应发布：{path}")
            continue
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label} 疑似泄露：{path}")
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    findings = scan(Path(args.root).resolve())
    if findings:
        print("\n".join(findings))
        return 1
    print("隐私扫描通过：未发现阻断项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
