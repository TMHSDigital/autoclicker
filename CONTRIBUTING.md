# Contributing

Thank you for your interest in this project. This repository is public. Please do not open pull requests that include secrets, credentials, or personal data.

## License

This project is licensed under [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](LICENSE).

- You may contribute non-commercial improvements aligned with the license.
- Commercial use or commercial pull requests require prior coordination with the maintainers at info@tmhsdigital.com.
- By opening a pull request you agree that your contribution is licensed under the same CC BY-NC 4.0 terms as the rest of the project (inbound = outbound).

The license was reviewed in October 2026 (#71) against PolyForm Noncommercial, MIT and a GPL-3.0 plus commercial dual license, and kept as CC BY-NC 4.0 to preserve the non-commercial terms and the existing commercial-licensing arrangement. Known trade-offs: it isn't an OSI license, so free open-source code signing (SignPath) and some open-source-only directories aren't available, and the project is described as source-available rather than open source.

## Development setup

Requirements: Windows and Python 3.10 to 3.14 (3.11 recommended; see `.python-version`).

```bash
# Git Bash
make install

# Windows cmd
tasks.bat install
```

`install` creates `.venv`, installs the pinned runtime dependencies (`requirements-lock.txt`) and the pinned dev and build tools (`requirements-dev-lock.txt`), then installs the package in editable mode.

End users who run from source install `requirements-lock.txt` as described in the README. `requirements.txt` only lists the unpinned runtime dependencies that `tools/refresh_lock.py` locks.

## Running checks

Run `make check` (or `tasks.bat check`) before calling a change done.

```bash
make check          # ruff lint + format check, mypy, pytest
make test
make lint
make typecheck
make coverage
make audit          # pip-audit on both lock files
make smoke          # scripts/smoke_check.py (not pytest)
```

Every target exists in `tasks.bat` too. To run a single test without the coverage gate:

```bash
python -m pytest tests/test_click_engine.py::TestRunOutcome::test_user_stop --no-cov
```

Tests never start a real Tk window: GUI tests build the app with `AutoclickerApp.__new__` and mocks (see `_bare_app()` in `tests/test_gui_callbacks.py`), and engine tests patch `autoclicker.core.click_engine.pyautogui`.

## Lock files

| File | Contents | Regenerate |
| :-- | :-- | :-- |
| `requirements-lock.txt` | Runtime dependencies, frozen on Python 3.11 | `make lock` |
| `requirements-dev-lock.txt` | Dev and build tools from `requirements-dev.in`, one lock for Python 3.10+ (needs [uv](https://docs.astral.sh/uv/)) | `make lock`, or `python tools/refresh_lock.py --dev` |

Commit the updated lock files. When the ruff or mypy version in the dev lock changes, update the matching `rev` in `.pre-commit-config.yaml` so pre-commit and CI run the same versions.

## Pre-commit (optional)

```bash
pre-commit install
pre-commit run --all-files
```

The hooks run standard file hygiene checks, ruff (lint and format) on all Python files, and mypy on `autoclicker/`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) with an optional scope:

- `feat:` new user-facing behavior, e.g. `feat(gui): ...`
- `fix:` bug fixes
- `perf:`, `refactor:`, `test:`, `docs:`, `build:`, `ci:`, `chore:`
- `chore(release): X.Y.Z` for release commits

Reference the issue in the body (`Closes #123`).

## Pull requests

1. Fork and branch from `main`.
2. Run `make check` (or `tasks.bat check`).
3. Add user-visible changes to `CHANGELOG.md` under `[Unreleased]`.
4. Do not commit `autoclicker_settings.json`, `htmlcov/`, `.coverage`, `*.egg-info/`, `.env`, keys, or tokens.

## Releases

Releases are created when a version tag is pushed, not on every merge to `main`.

1. Set the version in both `pyproject.toml` and `autoclicker/__init__.py`.
2. Move the `[Unreleased]` notes into a new version section in `CHANGELOG.md`.
3. Commit as `chore(release): X.Y.Z`, then tag and push:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

CI tests the tag, builds and smoke-launches `WindowsAutoclicker.exe`, and publishes it with a SHA-256 checksum, a provenance attestation, and release notes taken from that version's CHANGELOG section. The release fails if the tag and `__version__` differ or the section is missing. Details: [docs/RELEASING.md](docs/RELEASING.md).

## Security

See [SECURITY.md](SECURITY.md). Report concerns by email; do not file public issues for undisclosed vulnerabilities.
