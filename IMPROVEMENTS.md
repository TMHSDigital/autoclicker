# Deep dive improvements (1.1.0 → 1.2.0)

## Tests

| Metric | Before (hardening baseline) | After 1.2.0 |
|--------|----------------------------|-------------|
| pytest results | 28 passed, 15 failed | **86 passed, 0 failed** |
| `click_engine.py` coverage | ~0% | **~88%** (module gate ≥60%) |

## Correctness

- Queue mode no longer inflates `click_count` without executing clicks.
- Queue processor executes via `from_queue` path.
- Settings coercion, interval unit validation, exception API alignment.
- Picker hook handle + ESC cancel; quit saves UI fields.

## Performance

- Welford running stats for timing aggregates (see `PERFORMANCE.md`).
- Win32 `SendInput` path deferred (no measured win vs `PAUSE=0` pyautogui).

## Safety

- Failsafe **on** by default (GUI toggle).
- Runaway CPS guard (default ceiling 50).
- Optional pause when foreground window changes.
- Session log under `%APPDATA%/WindowsAutoclicker/sessions.log`.

## Architecture

- `app/controller.py` + `gui/sections/*` split from monolithic `main_window.py`.

## CI

- `continue-on-error` removed from test/coverage steps.
- Production ruff/mypy blanket ignores removed; narrowed rules remain for tkinter stubs and metrics dict typing.

## Deferred

- Project-wide coverage floor >60% (only `click_engine` gated today).
- Full mypy strictness on `click_engine` metrics without overrides.
- Win32 hot-path click injection if profiling shows clear win.
