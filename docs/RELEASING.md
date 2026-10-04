# Releasing and verifying downloads

## How a release is built

Pushing a `vX.Y.Z` tag runs the CI workflow on GitHub Actions:

1. Lint, type check, dependency audit and tests on Python 3.10 to 3.14.
2. PyInstaller builds `WindowsAutoclicker.exe` from `WindowsAutoclicker.spec` (no UPX, with a Windows version resource), launches it once as a smoke test, and writes `WindowsAutoclicker.exe.sha256`.
3. The release job checks that the tag matches `autoclicker/__init__.py`, takes the release notes from that version's section of `CHANGELOG.md` (`scripts/release_notes.py`), records a [build provenance attestation](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations) for the exe, and publishes the exe and its checksum.

Maintainer steps are in [CONTRIBUTING.md](../CONTRIBUTING.md#releases).

## Verifying a download

Checksum (Command Prompt or PowerShell), compared with `WindowsAutoclicker.exe.sha256` from the same release:

```bat
certutil -hashfile WindowsAutoclicker.exe SHA256
```

Provenance, which proves the file was built by this repository's workflow from a specific commit (needs the [GitHub CLI](https://cli.github.com/)):

```bash
gh attestation verify WindowsAutoclicker.exe --repo TMHSDigital/autoclicker
```

## Code signing

The executable is **not code-signed**, so Windows SmartScreen may warn on first run ("More info, Run anyway"). The checksum and the provenance attestation above are the current way to confirm a download is genuine.

Options considered:

| Option | Status |
| :-- | :-- |
| Microsoft Trusted Signing (Azure) | Viable: a paid monthly subscription plus identity validation; integrates with GitHub Actions. Best fit if SmartScreen warnings become a problem. |
| SignPath Foundation (free for open source) | Not available: it requires an OSI-approved license, and this project uses CC BY-NC 4.0. |
| Traditional OV or EV certificate | Possible but the most expensive and needs a hardware token or cloud HSM for the key. |

Decision: deferred. Revisit if download volume grows or users report blocked installs; Trusted Signing would be the first choice.
