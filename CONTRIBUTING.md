# Contributing

Thank you for your interest in this project. This repository is public. Please do not open pull requests that include secrets, credentials, or personal data.

## License

This project is licensed under [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](LICENSE).

- You may contribute non-commercial improvements aligned with the license.
- Commercial use or commercial pull requests require prior coordination with the maintainers at info@tmhsdigital.com.
- By opening a pull request you agree that your contribution is licensed under the same CC BY-NC 4.0 terms as the rest of the project (inbound = outbound).

The license was reviewed in October 2026 (#71) against PolyForm Noncommercial, MIT and a GPL-3.0 plus commercial dual license, and kept as CC BY-NC 4.0 to preserve the non-commercial terms and the existing commercial-licensing arrangement. Known trade-offs: it isn't an OSI license, so free open-source code signing (SignPath) and some open-source-only directories aren't available, and the project is described as source-available rather than open source.

## Development setup

Requirements: Windows and Python 3.11 to 3.14 (3.11 recommended; see `.python-version`).

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
make snapshots      # PNGs of the main window in set states, in build/ui-snapshots/
```

Every target exists in `tasks.bat` too. To run a single test without the coverage gate:

```bash
python -m pytest tests/test_click_engine.py::TestRunOutcome::test_user_stop --no-cov
```

Tests never start a real Tk window: GUI tests build the app with `AutoclickerApp.__new__` and mocks (see `_bare_app()` in `tests/test_gui_callbacks.py`), and engine tests patch `autoclicker.core.click_engine.pyautogui`.

## Lock files

| File | Contents | Regenerate |
| :-- | :-- | :-- |
| `requirements-lock.txt` | Runtime dependencies from `requirements.txt`, compiled with [uv](https://docs.astral.sh/uv/) for Windows and Python 3.11 (works from any venv or Python) | `make lock` (keeps pins), `python tools/refresh_lock.py --upgrade` (newest allowed) |
| `requirements-dev-lock.txt` | Dev and build tools from `requirements-dev.in`, one lock for Python 3.11+ (needs [uv](https://docs.astral.sh/uv/)) | `make lock`, or `python tools/refresh_lock.py --dev` |

Commit the updated lock files. When the ruff or mypy version in the dev lock changes, update the matching `rev` in `.pre-commit-config.yaml` so pre-commit and CI run the same versions.

Dependency updates are done by hand: bump the pin, run `make lock`, and keep the ruff and mypy versions in the dev lock and `.pre-commit-config.yaml` in step. Action updates are also manual; keep each action pinned to a commit SHA, and bump `github/codeql-action/init` and `analyze` together. The `audit` step in CI (`pip-audit` on both lock files) flags known vulnerabilities, which is the signal to update.

The exe leaves out `mouseinfo`, `pymsgbox` and `pyperclip`: pyautogui imports them optionally, the app never uses them, and the first two are GPLv3+. The `excludes` list in `WindowsAutoclicker.spec` and `NOT_BUNDLED` in `tools/third_party_notices.py` must match (a test checks), and the CI build fails if one of them ends up in the exe. Every build also writes `build/THIRD_PARTY_NOTICES.txt` (`tools/third_party_notices.py`, run by the spec) with the license of each bundled package, read from the installed runtime lock; it ships inside the exe, in the portable zip and with each release.

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

## Checking UI changes by eye

The tests run without a window, so they cannot tell you that a label sits on
the wrong color, a font did not apply or text is cut off. Every change that
touches what the window shows (anything in `autoclicker/gui/`, the theme, or
text the window displays) needs a look at the result before it is done:

1. Run `make snapshots` (or `tasks.bat snapshots`). It renders the main window
   in each scenario in `tools/ui_snapshots.py` (default, panels open, image,
   sequence, running, High Contrast) to `build/ui-snapshots/*.png`. Each one
   uses a throwaway `%APPDATA%`, registers no hotkeys or tray icon, clicks
   nothing, and its window is transparent and never takes focus, so it is safe
   to run while you work.
2. Open the PNGs and check the part you changed and the views around it:
   alignment, text cut off, colors (including High Contrast), disabled states.
3. If your change adds a view or state that no scenario shows, add a scenario
   to `SCENARIOS` so the next person sees it too.

Native popup menus (the sequence step menu) cannot be captured; their entries
are written to `build/ui-snapshots/menus.txt`. Dialogs and the tray menu still
need a manual look in the running app.

## Pull requests

1. Fork and branch from `main`.
2. Run `make check` (or `tasks.bat check`), and for UI changes `make snapshots`
   and look at the results (see above).
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
