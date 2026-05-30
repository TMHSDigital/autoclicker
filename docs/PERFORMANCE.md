# Performance notes (deep dive phase 4)

## Hot path

`ClickEngine._click_loop` → `_perform_burst` → `_perform_click` (pyautogui with `PAUSE=0`, skip redundant `moveTo` via `_last_click_xy`).

## Changes in phase 4

| Change | Rationale |
|--------|-----------|
| Welford running mean/variance for timings | `get_status()` / `get_performance_metrics()` no longer call `statistics.mean/median/stdev` over up to 1000 deque entries on every poll |
| Keep bounded `click_timings` deque | Debug/history only; status UI uses O(1) aggregates |

## Profiling (local, Windows)

```bat
.venv\Scripts\python.exe scripts\profile_click_engine.py --seconds 5 --interval-ms 10
```

The script prints `cProfile` top functions before/after for comparison.

## Experiments not shipped

| Idea | Result |
|------|--------|
| Win32 `SendInput` click-at-point | Deferred: needs guarded fallback and measurable win vs pyautogui with `PAUSE=0`; risk on multi-monitor DPI |
| Remove click queue | Kept: optional high-frequency path; no default-on regression |

## Targets

- Status polling at 1 Hz should not scale with click history length.
- Interval floor still dominated by OS scheduler + pyautogui; use ms intervals ≥ 1 for stable CPS.
