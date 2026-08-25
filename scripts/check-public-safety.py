#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Fail closed on private identifiers in public software.

Diagnostics deliberately report only rule name, path, and line number. They do
not echo the matched value.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


TEXT_SUFFIXES = {
    "",
    ".conf",
    ".css",
    ".dockerfile",
    ".go",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

RULES = {
    "private-repository-name": re.compile(r"(?i)\basgard-private\b"),
    "secret-manager-reference": re.compile(r"(?i)\bop://"),
    "private-environment-domain": re.compile(
        r"(?i)(?:[a-z0-9-]+\.)*wan0\.cloud\b"
    ),
    "private-data-path": re.compile(r"(?i)(?:/data|/opt)/asgard(?:/|\b)"),
    "rfc1918-ipv4": re.compile(
        r"(?<![0-9])(?:10\.(?:[0-9]{1,3}\.){2}[0-9]{1,3}"
        r"|192\.168\.(?:[0-9]{1,3}\.)[0-9]{1,3}"
        r"|172\.(?:1[6-9]|2[0-9]|3[01])\.(?:[0-9]{1,3}\.)[0-9]{1,3})(?![0-9])"
    ),
    "uuid-like-identifier": re.compile(
        r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
        r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
    ),
    "credential-bearing-url": re.compile(
        r"(?i)https?://[^\s]+(?:token|secret|api[_-]?key|password)=[^\s&]+"
    ),
}

ALLOW_MARKER = re.compile(r"public-safety:\s*allow=([a-z0-9-]+)")
EMAIL_ADDRESS = re.compile(
    r"(?i)\b[A-Z0-9._%+-]+@(?P<domain>[A-Z0-9.-]+\.[A-Z]{2,})\b"
)
EXAMPLE_EMAIL_DOMAINS = {
    "example.com",
    "example.invalid",
    "example.test",
    "pantheon.example.com",
}


def is_example_email_domain(domain: str) -> bool:
    normalized = domain.lower()
    return normalized in EXAMPLE_EMAIL_DOMAINS or normalized.endswith(
        (".example", ".invalid", ".test")
    )

BLOCKED_FILENAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
}
BLOCKED_SUFFIXES = {".key", ".p12", ".pfx", ".pem"}


def candidate_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*") if path.is_file())


def read_denylist(path: Path | None) -> list[re.Pattern[str]]:
    if path is None:
        return []
    patterns = []
    for value in path.read_text(encoding="utf-8").splitlines():
        value = value.strip()
        if value and not value.startswith("#"):
            patterns.append(re.compile(re.escape(value)))
    return patterns


def scan(paths: list[Path], denylist: list[re.Pattern[str]]) -> int:
    findings = 0
    for root in paths:
        for path in candidate_files(root):
            relative = path.as_posix()
            if path.name in BLOCKED_FILENAMES or path.suffix.lower() in BLOCKED_SUFFIXES:
                print(f"blocked-file:{relative}:0")
                findings += 1
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "Dockerfile":
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                marker = ALLOW_MARKER.search(line)
                allowed_rule = marker.group(1) if marker else None
                for rule_name, pattern in RULES.items():
                    if rule_name != allowed_rule and pattern.search(line):
                        print(f"{rule_name}:{relative}:{line_number}")
                        findings += 1
                if allowed_rule != "non-example-email":
                    for match in EMAIL_ADDRESS.finditer(line):
                        if not is_example_email_domain(match.group("domain")):
                            print(f"non-example-email:{relative}:{line_number}")
                            findings += 1
                for index, pattern in enumerate(denylist, start=1):
                    if pattern.search(line):
                        print(f"private-identifier-{index}:{relative}:{line_number}")
                        findings += 1
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("software")])
    parser.add_argument("--denylist", type=Path)
    args = parser.parse_args()
    findings = scan(args.paths, read_denylist(args.denylist))
    if findings:
        print(f"public-safety scan failed with {findings} finding(s)", file=sys.stderr)
        return 1
    print("public-safety scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
