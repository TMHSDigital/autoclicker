# Performance notes (deep dive phase 4)

## Hot path

`ClickEngine._click_loop` → `_perform_burst` → `_perform_click` (one `pyautogui.click(x, y, ...)` call with `PAUSE=0`; the target is passed on every click so a mouse moved mid-run never drags the clicks with it, #62).

## Changes in phase 4

| Change | Rationale |
|--------|-----------|
| Welford running mean/variance for timings | `get_status()` / `get_performance_metrics()` no longer call `statistics.mean/stdev` over up to 1000 deque entries on every poll |
| Per-run `ClickStats` dataclass | Replaced the untyped metrics dict and the unused 1000-sample timing deque; reset on every start so the status bar's success rate is per run (#68) |

## Profiling (local, Windows)

```bat
.venv\Scripts\python.exe scripts\profile_click_engine.py --seconds 5 --interval-ms 10
```

The script prints `cProfile` top functions before/after for comparison.

## Experiments not shipped

| Idea | Result |
|------|--------|
| Win32 `SendInput` click-at-point | Deferred: needs guarded fallback and measurable win vs pyautogui with `PAUSE=0`; risk on multi-monitor DPI |
| Click queue | Removed in 1.5.0: added latency and let clicks continue after Stop (#38) without a measurable throughput win |

## Targets

- Status polling at 1 Hz should not scale with click history length.
- UI CPS is the run's `click_count / runtime`. The runaway guard uses a sliding 1-second window.
- Interval floor still dominated by OS scheduler + pyautogui; use ms intervals ≥ 1 for stable CPS.
