# Hardening summary

Pre-audit repository hardening pass. Compare to git tag `pre-hardening-baseline` (local only).

## What changed (repo level)

- **Baseline capture:** `audit/baseline_*.txt`, `audit/baseline_htmlcov/`, `audit/PRE_AUDIT_NOTES.md`
- **Tests:** pytest canonical; `run_tests.py` wraps pytest; smoke script at `scripts/smoke_check.py`
- **Tooling:** `.editorconfig`, `Makefile`, `tasks.bat`, ruff, optional `.pre-commit-config.yaml`
- **CI:** SHA-pinned actions, concurrency, least-privilege permissions, separate `lint` job, `tasks.bat check` on Windows, releases on `v*.*.*` tags only, Dependabot
- **Reproducibility:** `requirements-lock.txt`, `tools/refresh_lock.py`, `.python-version` (3.11)
- **Docs:** `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, README testing/contributing updates

## What did not change

- **Production logic** under `autoclicker/` (except one-line SPDX headers in each module file)
- **Runtime behavior** of the application
- **End-user install path:** `requirements.txt` in README

Verify production diff:

```bash
git diff pre-hardening-baseline -- autoclicker/
```

Expected: SPDX header lines only.

## Baseline test results (phase 1)

Environment: Windows, Python 3.13.3; runtime deps not installed for initial unittest capture.

| Metric | Value |
|--------|-------|
| `run_tests.py` exit code | 1 |
| Tests run (unittest) | 31 |
| Failures | 3 |
| Errors | 13 |
| `pytest` exit code | 2 (collection error without `mouse`) |
| Smoke script exit code | 1 |
| Coverage (autoclicker, baseline capture) | 27% (869 statements, 637 missed) |

## Post-hardening check (phase 8)

With `tasks.bat install` (lock file + editable dev install): **28 passed, 15 failed** (see `audit/post_hardening_check.txt`). Same failing areas as baseline (exception subclasses, several settings validations). Coordinate picker tests pass when dependencies are installed.

## Lock file

| Field | Value |
|-------|-------|
| File | `requirements-lock.txt` |
| Packages | 14 pinned runtime packages |
| Generated on | Python 3.13.3 locally (3.11 recommended for regeneration; see CONTRIBUTING) |

## Handoff

Read **`audit/PRE_AUDIT_NOTES.md`** first on day one of the deep dive.

## Next pass should start here

1. Read `audit/PRE_AUDIT_NOTES.md` (lint list, test failures, doc/config drift).
2. `git diff pre-hardening-baseline` for full repo delta; confirm `autoclicker/` is SPDX-only.
3. Remove `per-file-ignores` / mypy `ignore_errors` for `autoclicker.*` incrementally while fixing findings.
4. Align failing tests with current exception APIs and validation behavior (do not change behavior until tests encode intended contracts).
5. Regenerate `requirements-lock.txt` on Python 3.11 before the next CI-heavy release.
