#!/usr/bin/env python3
"""Write the Scoop and winget manifests for a release.

    python tools/package_manifests.py 1.5.0 <sha256 of WindowsAutoclicker.exe>

Scoop: bucket/windows-autoclicker.json, so this repository works as a bucket:
    scoop bucket add tmhs https://github.com/TMHSDigital/autoclicker
    scoop install tmhs/windows-autoclicker

winget: packaging/winget/manifests/t/TMHSDigital/WindowsAutoclicker/<version>/,
the layout microsoft/winget-pkgs expects. Check with ``winget validate <dir>``
and submit that directory to winget-pkgs (see docs/RELEASING.md).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "TMHSDigital/autoclicker"
PACKAGE_ID = "TMHSDigital.WindowsAutoclicker"
EXE = "WindowsAutoclicker.exe"
DESCRIPTION = (
    "A fast, careful autoclicker for Windows: fixed points, sequences, hold and key actions, "
    "profiles and a command line, with safety stops on by default."
)


def download_url(version: str) -> str:
    return f"https://github.com/{REPO}/releases/download/v{version}/{EXE}"


def scoop_manifest(version: str, sha256: str) -> dict:
    return {
        "version": version,
        "description": DESCRIPTION,
        "homepage": "https://tmhsdigital.github.io/autoclicker/",
        "license": "CC-BY-NC-4.0",
        "url": download_url(version),
        "hash": sha256,
        "bin": [[EXE, "autoclicker"]],
        "shortcuts": [[EXE, "Windows Autoclicker"]],
        "checkver": "github",
        "autoupdate": {
            "url": f"https://github.com/{REPO}/releases/download/v$version/{EXE}",
            "hash": {"url": "$url.sha256"},
        },
    }


def winget_manifests(version: str, sha256: str) -> dict[str, str]:
    schema = "https://aka.ms/winget-manifest.{kind}.1.9.0.schema.json"
    header = "# yaml-language-server: $schema=" + schema
    base = f"PackageIdentifier: {PACKAGE_ID}\nPackageVersion: {version}\n"
    return {
        f"{PACKAGE_ID}.yaml": (
            f"{header.format(kind='version')}\n{base}"
            "DefaultLocale: en-US\nManifestType: version\nManifestVersion: 1.9.0\n"
        ),
        f"{PACKAGE_ID}.installer.yaml": (
            f"{header.format(kind='installer')}\n{base}"
            "InstallerType: portable\n"
            "Commands:\n- autoclicker\n"
            "Installers:\n"
            "- Architecture: x64\n"
            f"  InstallerUrl: {download_url(version)}\n"
            f"  InstallerSha256: {sha256.upper()}\n"
            "ManifestType: installer\nManifestVersion: 1.9.0\n"
        ),
        f"{PACKAGE_ID}.locale.en-US.yaml": (
            f"{header.format(kind='defaultLocale')}\n{base}"
            "PackageLocale: en-US\n"
            "Publisher: TM Hospitality Strategies\n"
            f"PublisherUrl: https://github.com/{REPO.split('/')[0]}\n"
            f"PublisherSupportUrl: https://github.com/{REPO}/issues\n"
            "PackageName: Windows Autoclicker\n"
            "PackageUrl: https://tmhsdigital.github.io/autoclicker/\n"
            "License: CC BY-NC 4.0\n"
            f"LicenseUrl: https://github.com/{REPO}/blob/main/LICENSE\n"
            "ShortDescription: A fast, careful autoclicker with safety stops on by default.\n"
            f"Description: {json.dumps(DESCRIPTION)}\n"
            "Tags:\n- autoclicker\n- automation\n- clicker\n- mouse\n- productivity\n"
            f"ReleaseNotesUrl: https://github.com/{REPO}/releases/tag/v{version}\n"
            "ManifestType: defaultLocale\nManifestVersion: 1.9.0\n"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version")
    parser.add_argument("sha256")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        parser.error("version must look like 1.5.0")
    sha256 = args.sha256.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        parser.error("sha256 must be 64 hex characters")

    scoop = ROOT / "bucket" / "windows-autoclicker.json"
    scoop.parent.mkdir(parents=True, exist_ok=True)
    scoop.write_text(json.dumps(scoop_manifest(args.version, sha256), indent=4) + "\n", "utf-8")
    print(f"Wrote {scoop.relative_to(ROOT)}")

    winget = ROOT / "packaging/winget/manifests/t/TMHSDigital/WindowsAutoclicker" / args.version
    winget.mkdir(parents=True, exist_ok=True)
    for name, text in winget_manifests(args.version, sha256).items():
        (winget / name).write_text(text, "utf-8")
    print(f"Wrote {winget.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
