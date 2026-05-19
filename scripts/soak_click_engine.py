#!/usr/bin/env python
# SPDX-License-Identifier: CC-BY-NC-4.0
r"""
Long-duration soak for ClickEngine. Opt-in; not run by CI.

Runs the engine for a wall-clock duration at a target rate using a no-op
mocked click implementation, then reports timing distribution, heap delta,
and queue/dropped counters. Use this before shipping changes that touch the
click loop or performance metrics.

Usage (PowerShell):
    .\.venv\Scripts\python.exe scripts\soak_click_engine.py --seconds 600 --cps 50

For a real-mouse soak (will actually move and click), pass --real. Move the
mouse to a safe corner first; failsafe is left enabled.
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time
import tracemalloc
from contextlib import contextmanager
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autoclicker.core.click_engine import ClickEngine


@contextmanager
def mocked_pyautogui():
    """Replace pyautogui calls with no-ops while keeping the FailSafeException."""
    import pyautogui

    with patch("autoclicker.core.click_engine.pyautogui") as m:
        m.size.return_value = (1920, 1080)
        m.click.return_value = None
        m.doubleClick.return_value = None
        m.rightClick.return_value = None
        m.middleClick.return_value = None
        m.moveTo.return_value = None
        m.PAUSE = 0
        m.FAILSAFE = False
        m.FailSafeException = pyautogui.FailSafeException
        m.PyAutoGUIException = pyautogui.PyAutoGUIException
        yield m


def run_soak(duration_s: float, target_cps: int, real: bool) -> int:
    interval_ms = max(1.0, 1000.0 / target_cps)
    print(f"Soak: duration={duration_s}s, target_cps={target_cps}, interval={interval_ms:.2f}ms")
    print(f"Mode: {'REAL pyautogui (will click!)' if real else 'mocked'}")

    gc.collect()
    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    def _run(engine: ClickEngine) -> None:
        engine.configure_safety(failsafe=real, max_cps=target_cps * 2, pause_when_unfocused=False)
        engine.start_clicking(
            x=100,
            y=100,
            interval=interval_ms,
            variation=0,
            burst_clicks=1,
            burst_pause=0,
            max_clicks=0,
            auto_stop_minutes=0,
            mouse_button="left",
            click_type="single",
        )

        start = time.time()
        last_report = start
        while time.time() - start < duration_s:
            time.sleep(0.5)
            if time.time() - last_report >= 5.0:
                s = engine.get_status()
                print(
                    f"  t={int(time.time() - start):4d}s  "
                    f"clicks={s['click_count']:>8}  "
                    f"queue={s['queue_size']:>4}  "
                    f"dropped={s['dropped_click_count']:>4}  "
                    f"cps={s['performance']['clicks_per_second']:.2f}"
                )
                last_report = time.time()
        engine.stop_clicking()

    engine = ClickEngine(enable_performance_monitoring=True)
    if real:
        _run(engine)
    else:
        with mocked_pyautogui():
            _run(engine)

    gc.collect()
    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    diff = snap_after.compare_to(snap_before, "filename")
    delta = sum(stat.size_diff for stat in diff)

    status = engine.get_status()
    perf = status["performance"]
    print()
    print("===== Soak summary =====")
    print(f"Total clicks:         {status['click_count']}")
    print(f"Dropped (queue full): {status['dropped_click_count']}")
    print(f"Runtime:              {status['runtime']}")
    print(f"Avg cps:              {perf['clicks_per_second']}")
    print(f"Success rate:         {perf['success_rate']}%")
    print(f"Mean click time (ms): {perf['average_click_time']}")
    print(f"Error count:          {perf['total_errors']}")
    print(f"Heap delta:           {delta:+d} bytes ({delta / 1024:+.1f} KiB)")
    print(f"Timings deque size:   {len(engine.performance_metrics['click_timings'])}")
    print(f"Recent ts deque size: {len(engine._recent_click_ts)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seconds", type=float, default=60.0, help="soak duration in seconds")
    p.add_argument("--cps", type=int, default=20, help="target clicks per second")
    p.add_argument("--real", action="store_true", help="use REAL pyautogui (will click)")
    args = p.parse_args()
    return run_soak(args.seconds, args.cps, args.real)


if __name__ == "__main__":
    raise SystemExit(main())
