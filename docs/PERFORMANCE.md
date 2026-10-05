# Performance notes

## Hot path

`ClickEngine._click_loop` → `_perform_burst` → `_perform_click` (one `pyautogui.click(x, y, ...)` call with `PAUSE=0`; the target is passed on every click so a mouse moved mid-run never drags the clicks with it, #62).

## Running statistics

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

## Pixel condition

Reading one screen pixel (`GetPixel`, or a 1x1 `BitBlt`) waits for the next composed frame: about 17 ms at 60 Hz on the dev machine. Doing that on the click thread would stall every click, so the watched pixel is polled on its own `PixelWatch` thread every 50 ms and the click loop only reads the latest result. Clicks may therefore act on a reading up to about 70 ms old.

## Image target

The `ImageWatch` thread grabs the search region and looks for the captured image every 100 ms (`_IMAGE_POLL_SECONDS`). Measured on a 3840x1080 two-monitor desktop with a 60x30 capture:

| Search margin | Region searched | Screen grab | Search |
|---------------|-----------------|-------------|--------|
| 150 px (default) | 360 x 330 | about 49 ms | about 1 ms |
| 2,000 px (maximum) | 2560 x 1080 | about 55 ms | about 14 ms |

The grab dominates because Pillow's `ImageGrab.grab(all_screens=True)` captures the whole virtual desktop and then crops it, so its cost follows the desktop size, not the margin. Grabbing only the region is tracked in #97. The search itself is cheap: each row is scanned for the template's first row with `bytes.find`, and only those hits are compared in full.

## Targets

- Status polling at 1 Hz should not scale with click history length.
- UI CPS is the run's `click_count / runtime`. The runaway guard uses a sliding 1-second window.
- Interval floor still dominated by OS scheduler + pyautogui; use ms intervals ≥ 1 for stable CPS.
