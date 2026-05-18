# Pre-audit notes

Handoff document for the deep dive. Factual observations only.

## 1. Lint violations in autoclicker/

(To be populated in phase 3.)

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

- `run_tests.py` uses unittest discovery on `tests/` only (31 tests reported).
- `pytest` with `testpaths = [".", "tests"]` can collect root `test_autoclicker.py` functions named `test_*` (bool-returning, not assert-based); baseline pytest run aborted at collection before full comparison.
- CI runs smoke script and pytest separately (`.github/workflows/ci.yml`).

## 4. Discrepancies between documentation and code

(To be populated in phase 6.)

## 5. Discrepancies between configuration files

(To be populated during hardening.)

## 6. Anything else worth remembering

(To be populated throughout.)
