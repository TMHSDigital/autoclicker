#!/usr/bin/env python
# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Write the CHANGELOG.md section for one version as GitHub release notes.

Usage:
    python scripts/release_notes.py v1.5.0 --output release-notes.md

Exits non-zero if the tag does not match autoclicker/__init__.py's
__version__ or the version has no CHANGELOG section, so a mistagged or
undocumented release fails instead of publishing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
INIT = ROOT / "autoclicker" / "__init__.py"
REPO_URL = "https://github.com/TMHSDigital/autoclicker"


def extract_section(changelog: str, version: str) -> str | None:
    """Body of the ``## [version]`` section (without its heading), or None."""
    version = version.lstrip("v")
    heading = re.compile(rf"^## \[{re.escape(version)}\][^\n]*\n", re.MULTILINE)
    match = heading.search(changelog)
    if match is None:
        return None
    rest = changelog[match.end() :]
    # Section ends at the next version heading or the link reference block.
    end = re.search(r"^(## \[|\[[^\]]+\]: )", rest, re.MULTILINE)
    body = rest[: end.start()] if end else rest
    return body.strip()


def release_notes(changelog: str, version: str) -> str | None:
    body = extract_section(changelog, version)
    if body is None:
        return None
    tag = f"v{version.lstrip('v')}"
    footer = (
        "\n\n---\n\n"
        "**Verify the download:** compare `certutil -hashfile WindowsAutoclicker.exe SHA256` "
        "with `WindowsAutoclicker.exe.sha256`, or check the build provenance with "
        "`gh attestation verify WindowsAutoclicker.exe --repo TMHSDigital/autoclicker`.\n\n"
        f"Full changelog: {REPO_URL}/blob/{tag}/CHANGELOG.md"
    )
    return body + footer


def package_version(init_text: str) -> str | None:
    match = re.search(r'^__version__ = "([^"]+)"', init_text, re.MULTILINE)
    return match.group(1) if match else None


def main(argv: list[str]) -> int:
    output: Path | None = None
    if "--output" in argv:
        index = argv.index("--output")
        output = Path(argv[index + 1])
        argv = argv[:index] + argv[index + 2 :]
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    tag = argv[0]
    version = package_version(INIT.read_text(encoding="utf-8"))
    if version != tag.lstrip("v"):
        print(f"Tag {tag} does not match package version {version}", file=sys.stderr)
        return 1
    notes = release_notes(CHANGELOG.read_text(encoding="utf-8"), tag)
    if notes is None:
        print(f"No CHANGELOG section for {tag}", file=sys.stderr)
        return 1
    if output is not None:
        output.write_text(notes + "\n", encoding="utf-8")
    else:
        sys.stdout.buffer.write((notes + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
