#!/usr/bin/env python3
"""Build or preview the complete Pantheon Blueprint documentation set."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
ROOT_DOCUMENTS = ("README.md", "CONTRIBUTING.md", "SECURITY.md")


def stage_sources(destination: Path) -> None:
    """Copy public documentation into an isolated MkDocs source tree."""
    for name in ROOT_DOCUMENTS:
        source = (REPOSITORY_ROOT / name).read_text(encoding="utf-8")
        (destination / name).write_text(
            source.replace("](LICENSE)", "](LICENSE.md)"),
            encoding="utf-8",
        )

    shutil.copy2(REPOSITORY_ROOT / "LICENSE", destination / "LICENSE.md")
    shutil.copytree(REPOSITORY_ROOT / "docs", destination / "docs")


def write_overlay(destination: Path, source_dir: Path, site_dir: Path) -> Path:
    """Create a temporary config that supplies staged input and output paths."""
    config = destination / "mkdocs.overlay.yml"
    config.write_text(
        "\n".join(
            (
                f"INHERIT: {json.dumps(str(REPOSITORY_ROOT / 'mkdocs.yml'))}",
                f"docs_dir: {json.dumps(str(source_dir))}",
                f"site_dir: {json.dumps(str(site_dir))}",
                "",
            )
        ),
        encoding="utf-8",
    )
    return config


def run_mkdocs(command: str, site_dir: Path | None) -> int:
    """Stage sources and invoke MkDocs with strict validation."""
    with tempfile.TemporaryDirectory(prefix="pantheon-docs-stage-") as temporary:
        work_dir = Path(temporary)
        source_dir = work_dir / "source"
        source_dir.mkdir()
        stage_sources(source_dir)

        if site_dir is None:
            site_dir = Path(tempfile.mkdtemp(prefix="pantheon-docs-site-"))
        else:
            site_dir = site_dir.expanduser().resolve()

        config = write_overlay(work_dir, source_dir, site_dir)
        arguments = [
            sys.executable,
            "-m",
            "mkdocs",
            command,
            "--config-file",
            str(config),
            "--strict",
        ]
        if command == "serve":
            arguments.extend(("--dev-addr", "127.0.0.1:8000"))

        print(f"Documentation output: {site_dir}")
        return subprocess.call(arguments, cwd=REPOSITORY_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build the production site")
    build.add_argument(
        "--site-dir",
        type=Path,
        help="output directory (default: a new temporary directory)",
    )

    serve = subparsers.add_parser("serve", help="preview on 127.0.0.1:8000")
    serve.add_argument(
        "--site-dir",
        type=Path,
        help="output directory (default: a new temporary directory)",
    )

    arguments = parser.parse_args()
    return run_mkdocs(arguments.command, arguments.site_dir)


if __name__ == "__main__":
    raise SystemExit(main())
