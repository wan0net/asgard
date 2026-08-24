#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Validate explicit BSD-3-Clause declarations in public software."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


SPDX = "SPDX-License-Identifier: BSD-3-Clause"
CODE_SUFFIXES = {".go", ".js", ".mjs", ".py", ".sh", ".ts"}
CODE_NAMES = {"Dockerfile", "go.mod"}


def code_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and (path.name in CODE_NAMES or path.suffix.lower() in CODE_SUFFIXES)
    )


def validate(root: Path) -> list[str]:
    findings: list[str] = []
    component_directories: set[Path] = set()
    for path in code_files(root):
        component_directories.add(path.parent)
        header = "\n".join(path.read_text(encoding="utf-8").splitlines()[:3])
        if SPDX not in header:
            findings.append(f"missing-spdx:{path.as_posix()}")
    for directory in sorted(component_directories):
        readme = directory / "README.md"
        if not readme.is_file() or "BSD-3-Clause" not in readme.read_text(
            encoding="utf-8"
        ):
            findings.append(f"missing-component-license:{directory.as_posix()}")
    for path in sorted(root.rglob("*")):
        if path.is_file() and "LicenseRef-Internal" in path.read_text(
            encoding="utf-8", errors="ignore"
        ):
            findings.append(f"internal-license-reference:{path.as_posix()}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path("software"))
    args = parser.parse_args()
    findings = validate(args.root)
    if findings:
        print("\n".join(findings))
        print(f"software licence check failed with {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("software licence check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
