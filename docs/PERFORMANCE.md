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
| 150 px (default) | 360 x 330 | about 17 ms (was 49 to 67 ms) | about 1 ms |
| 2,000 px (maximum) | 2560 x 1080 | about 17 ms (was 55 ms) | about 14 ms |

`image_match.grab` copies only the region with `BitBlt` from the screen DC (#97). Pillow's `ImageGrab.grab(all_screens=True)`, still the fallback if that fails, copies the whole virtual desktop and then crops it, so its cost follows the desktop size rather than the margin. The remaining ~17 ms is one display frame at 60 Hz: with desktop composition on, a screen `BitBlt` waits for the compositor. The wait happens inside a ctypes call, which releases the GIL, so the click thread keeps its timing.

The template's rows, its anchor row (the one with the most distinct colors) and up to four probe pixels are prepared with Pillow's C code (`getcolors`), and the result is cached while the image file is unchanged, so later Starts skip it (#162). Preparing a full-screen 1920x1080 capture takes about 0.1 s (it was about 1 to 2 s, on the Tk thread at every Start). The exact search scans each region row for the anchor with `bytes.find` and compares the full template only at those hits.

With a **Tolerance** above 0 the search builds, per probe color, a mask of the places within tolerance (three band lookups and two `darker` passes in C), intersects the masks shifted to template positions, and compares the full template only at the surviving candidates. The rarest probe goes first and the remaining probes are skipped once fewer than 64 candidates are left (#161). Synthetic benchmark, 60x30 template, 2560 x 1080 region (the maximum margin):

| Haystack | Tolerance 0 | Tolerance 8 or 32 |
|----------|-------------|-------------------|
| Random noise | about 7 ms | 45 to 57 ms (was 70 ms) |
| UI-like (flat panels) | about 7 ms | 50 to 65 ms (was 70 ms) |
| 700 x 400 region, noise | | about 4 ms (was 7 ms) |

A wide margin with tolerance is still the costliest setting, so the watcher waits at least as long as its last search took before searching again: it never keeps a core busy, and the match it acts on is at most about two searches old.

## Targets

- Status polling at 1 Hz should not scale with click history length.
- UI CPS is the run's `click_count / runtime`. The runaway guard uses a sliding 1-second window.
- Interval floor still dominated by OS scheduler + pyautogui; use ms intervals ≥ 1 for stable CPS.
