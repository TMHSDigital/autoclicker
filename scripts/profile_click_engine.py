#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-NC-4.0
"""Profile ClickEngine hot path; write audit/perf summary."""

from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoclicker.core.click_engine import ClickEngine  # noqa: E402


def run_profile(seconds: float, interval_ms: float, label: str) -> str:
    engine = ClickEngine(enable_performance_monitoring=True)
    engine.is_running = True

    def burst_loop() -> None:
        end = time.perf_counter() + seconds
        while time.perf_counter() < end and engine.is_running:
            engine._perform_burst(100, 100, 1, 0, "left", "single")
            engine._wait_with_variation(interval_ms, 0)

    with patch("autoclicker.core.click_engine.pyautogui") as mock_gui:
        mock_gui.size.return_value = (1920, 1080)
        prof = cProfile.Profile()
        prof.enable()
        burst_loop()
        prof.disable()

    buf = StringIO()
    stats = pstats.Stats(prof, stream=buf).sort_stats("cumulative")
    stats.print_stats(25)
    header = (
        f"# {label}\n# seconds={seconds} interval_ms={interval_ms} clicks={engine.click_count}\n\n"
    )
    return header + buf.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile ClickEngine")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--interval-ms", type=float, default=10.0)
    parser.add_argument("--label", default="profile")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "audit" / "perf" / "after.txt",
    )
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = run_profile(args.seconds, args.interval_ms, args.label)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote {args.out} ({len(report)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
