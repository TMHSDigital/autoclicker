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

Captured 2026-05-18 on Windows, Python 3.13.3 (see `audit/baseline_env.txt`). Runtime deps from `requirements.txt` were not installed in the capture environment; many failures are `ModuleNotFoundError: No module named 'mouse'`.

| Runner | Exit code | Summary |
|--------|-----------|---------|
| `python run_tests.py` | 1 | 31 run, 3 failures, 13 errors (`audit/baseline_run_tests.txt`) |
| `python -m pytest` | 2 | Collection error in `tests/test_coordinate_picker.py` (missing `mouse`); 30 items collected before error (`audit/baseline_pytest.txt`) |
| `python run_tests.py --coverage` | 1 | Same failure set as unittest runner (`audit/baseline_coverage.txt`) |
| `python test_autoclicker.py` | 1 | Import failures for pyautogui/mouse; file structure checks passed (`audit/baseline_smoke.txt`) |

Smoke script output uses Unicode symbols (checkmark/cross emojis) in print strings; violates project no-emoji rule.

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

(To be populated in phase 6.)

## 5. Discrepancies between configuration files

(To be populated during hardening.)

## 6. Anything else worth remembering

(To be populated throughout.)
