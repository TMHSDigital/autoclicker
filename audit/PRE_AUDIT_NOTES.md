# Pre-audit notes

Handoff document for the deep dive. Factual observations only.

## 1. Lint violations in autoclicker/

Ruff (`select = E,F,W,I,UP,B,SIM,RUF`) before per-file ignores:

| File | Rule | Line | Observation |
|------|------|------|---------------|
| `autoclicker/core/settings_manager.py` | F401 | 8 | Unused import `Optional` |
| `autoclicker/core/settings_manager.py` | F541 | 90 | f-string without placeholders |
| `autoclicker/core/settings_manager.py` | F841 | 195 | Local variable `sanitized` assigned but never used |
| `autoclicker/gui/main_window.py` | F401 | 9 | Unused import `time` |
| `autoclicker/utils/coordinate_picker.py` | F401 | 6 | Unused import `threading` |

Mypy (37 errors in 4 files before `ignore_errors` override): `exceptions.py` (missing `reason` on subclasses), `settings_manager.py` (var-annotated), `click_engine.py` (typing on metrics deque), `main_window.py` (`sticky` tuple vs str stubs).

Per-file `ALL` ignores added under `[tool.ruff.lint.per-file-ignores]` for `autoclicker/**` and `autoclicker.py`. Mypy `ignore_errors = true` for `autoclicker.*` until deep dive.

## 2. Test failures or skips in the baseline

### Hardening baseline (pre deep dive)

Captured 2026-05-18 on Windows, Python 3.13.3 (see `audit/baseline_env.txt`). With deps installed post-hardening: **28 passed, 15 failed** (`audit/post_hardening_check.txt`).

### After phase 1 audit (current)

**22 failed, 28 passed** (50 tests). Added 7 failing repro tests in `tests/test_audit_regressions.py` (see [AUDIT.md](../AUDIT.md)).

| New failure | Reason |
|-------------|--------|
| `test_queue_mode_increments_count_without_executing_clicks` | Queue mode inflates `click_count` without pyautogui clicks (C1) |
| `test_queue_processor_does_not_execute_clicks` | Queued clicks never executed (C2) |
| `test_stop_picking_unhooks_by_handle_not_callback` | `mouse.unhook` passed callback not handle (C7) |
| `test_no_keyboard_cancel_handler_registered` | No ESC cancel hook on picker (C8) |
| `test_quit_application_persists_ui_values_not_empty_update` | `quit_application` calls `update({})` (C9) |
| `test_invalid_interval_unit_reported_in_validate_all` | Bad unit sanitized before validation (C11) |
| `test_coordinate_error_user_message` | `create_user_friendly_error` uses missing `.reason` (C10) |

The original **15 failures** remain unchanged (exceptions API, settings validation TypeError/tuple misuse).

## 3. Discrepancies between test runners

**Baseline (pre phase 2):**
- `run_tests.py` used unittest discovery on `tests/` only (31 tests reported).
- `pytest` with `testpaths = [".", "tests"]` could collect root `test_autoclicker.py` functions named `test_*` (bool-returning, not assert-based).
- CI ran smoke script and pytest separately (`.github/workflows/ci.yml`).

**After phase 2:**
- `run_tests.py` delegates to `python -m pytest` with the same exit code.
- Smoke script moved to `scripts/smoke_check.py` (not matched by `test_*.py`); check functions renamed `check_*`.
- `testpaths = ["tests"]` only; `filterwarnings = ["error::DeprecationWarning"]` added.
- Post-change: `run_tests.py` and `pytest` both exit 2 with the same collection error when `mouse` is missing (aligned).

## 4. Discrepancies between documentation and code

| Source | Claim | Observation |
|--------|-------|---------------|
| `README.md` Test Coverage | Lists Click Engine and GUI Integration tests | `tests/` only contains `test_settings_manager.py`, `test_exceptions.py`, `test_coordinate_picker.py` |
| `README.md` (historical) | Implied `test_autoclicker.py` in test flow | Moved to `scripts/smoke_check.py`; not part of pytest |
| `run_autoclicker.bat` line 13 | Python 3.8+ | `pyproject.toml` and README require Python 3.10+ |
| `README.md` Contributing (pre-hardening) | Manual venv + `pip install -r requirements.txt` only | Replaced by pointer to `CONTRIBUTING.md` and `tasks.bat` / `make` targets |

## 5. Discrepancies between configuration files

| Item | Location A | Location B | Observation |
|------|------------|------------|---------------|
| License classifier | `pyproject.toml` `Other/Proprietary License` | `LICENSE` CC BY-NC 4.0 | `license = {text = "CC-BY-NC-4.0"}` added; classifier unchanged (no PyPI trove for CC-BY-NC) |
| Runtime pins | `requirements.txt` (`>=`) | `requirements-lock.txt` (exact) | Lock generated locally on Python 3.13.3 (3.11 unavailable on capture machine); CI targets 3.11 |
| Coverage source | `[tool.coverage.run] source = ["."]` | pytest `--cov=autoclicker` | Different scope between legacy coverage config and current runner |
| Dev linters | Was flake8/black in CI | ruff in `pyproject.toml` | CI migrated in hardening pass |

## 6. Anything else worth remembering

- CI `test` job uses `continue-on-error: true` on unit tests and coverage until baseline failures are fixed in the deep dive (lint/typecheck must pass).

- `pyautogui.FAILSAFE = False` set in `autoclicker/core/click_engine.py` at import time.
- Root `test_autoclicker.py` defined `test_*` functions returning `bool`; pytest would treat failures as passes if collected.
- `autoclicker_settings.json` is gitignored; tests may emit "Could not load settings file" warnings when the file exists but is empty.
- Public repo: do not commit secrets; `SECURITY.md` and `CONTRIBUTING.md` document email reporting and license constraints.
- Git tag `pre-hardening-baseline` is local only (do not push unless intentional).
