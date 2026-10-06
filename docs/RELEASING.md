# Releasing and verifying downloads

## How a release is built

Before tagging, the `chore(release): X.Y.Z` commit sets the version in `pyproject.toml`, `autoclicker/__init__.py` and the website (`docs/index.html`: the `softwareVersion` in the JSON-LD and the `data-version` text next to Download, plus the size if it changed), and moves the `[Unreleased]` notes under the new version in `CHANGELOG.md`. Start that section with a sentence or two of highlights before the first `###` heading: `scripts/release_notes.py` puts an install line, then those highlights, at the top of the GitHub release. `tests/test_project_metadata.py` fails if any of these versions disagree.

Pushing a `vX.Y.Z` tag runs the CI workflow on GitHub Actions:

1. Lint, type check, dependency audit and tests on Python 3.10 to 3.14.
2. PyInstaller builds `WindowsAutoclicker.exe` from `WindowsAutoclicker.spec` (no UPX, with a Windows version resource), launches it once as a smoke test, and writes `WindowsAutoclicker.exe.sha256`.
3. The release job checks that the tag matches `autoclicker/__init__.py`, takes the release notes from that version's section of `CHANGELOG.md` (`scripts/release_notes.py`), records a [build provenance attestation](https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations) for the exe, and publishes the exe and its checksum.

Maintainer steps are in [CONTRIBUTING.md](../CONTRIBUTING.md#releases).

**Policy:** when a fix labelled `safety` lands on `main`, cut a patch release promptly. The README download button always serves the latest release, so a safety fix only reaches most users once it is released.

## Verifying a download

Checksum (Command Prompt or PowerShell), compared with `WindowsAutoclicker.exe.sha256` from the same release:

```bat
certutil -hashfile WindowsAutoclicker.exe SHA256
```

Provenance (needs GitHub CLI 2.60 or newer; older versions fail with an "unsupported tlog public key type" error), which proves the file was built by this repository's workflow from a specific commit (needs the [GitHub CLI](https://cli.github.com/)):

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

### Turning signing on

The release build already contains the signing steps; they run on `v*` tags once these **repository variables** (Settings, Secrets and variables, Actions, Variables) exist. No secrets are needed: the workflow logs in to Azure with OpenID Connect.

1. In Azure, create an Artifact Signing (Trusted Signing) account, complete identity validation, and create a public-trust certificate profile.
2. Create an app registration (or user-assigned managed identity), give it the *Artifact Signing Certificate Profile Signer* role on the account, and add a federated credential for this repository with subject `repo:TMHSDigital/autoclicker:ref:refs/tags/*`.
3. Set the variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `SIGNING_ENDPOINT` (for example `https://eus.codesigning.azure.net/`), `SIGNING_ACCOUNT_NAME` and `SIGNING_CERTIFICATE_PROFILE`.
4. Push the next tag. The build signs `WindowsAutoclicker.exe` before the checksum is computed and fails if `Get-AuthenticodeSignature` doesn't report a valid signature.

After the first signed release, drop the SmartScreen note from the README and the website FAQ.

## Package managers

The release job runs `tools/package_manifests.py` with the published checksum, which checks what it wrote (version, download URL and hash) before anything is committed, and then pushes the result to `main`, rebasing and retrying if `main` moved in the meantime. That bot commit does not trigger CI. If the step fails after the release is already published, run the **Package manifests** workflow (Actions tab) with the tag: by default it is a dry run that uploads the manifests as an artifact, and with **commit** checked it commits them. The push uses the workflow token, so protecting `main` later means switching this step to a GitHub App token or to opening a pull request.

- **Scoop:** `bucket/windows-autoclicker.json`, so this repository is itself a bucket (`scoop bucket add tmhs https://github.com/TMHSDigital/autoclicker`). Its `checkver` and `autoupdate` entries also let other buckets track new releases.
- **winget:** `packaging/winget/manifests/t/TMHSDigital/WindowsAutoclicker/<version>/`, in the layout of [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs). Check it with `winget validate --manifest <dir>`, then copy the directory into a fork of winget-pkgs and open a pull request (or use `wingetcreate submit <dir>`). After the first version is accepted, later versions can be submitted the same way.
