# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Click engine for the autoclicker
Handles mouse clicking operations with safety checks
"""

import logging
import random
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

import pyautogui

from .exceptions import (
    ClickEngineError,
    CoordinateError,
    SafetyError,
    create_user_friendly_error,
)
from .safety import apply_failsafe, get_foreground_window_handle, is_foreground_window
from .screen import ScreenBounds, virtual_screen_bounds

# Default PAUSE is 0.1s between every PyAutoGUI call — caps CPS at ~5–10/s
pyautogui.PAUSE = 0
apply_failsafe(True)

_log = logging.getLogger(__name__)

# Why a run ended. Exactly one is reported per run via RunOutcome.
STOP_COMPLETED = "completed"  # max clicks or auto-stop limit reached
STOP_USER = "user_stop"
STOP_EMERGENCY = "emergency"
STOP_SAFETY = "safety"  # failsafe corner or runaway guard
STOP_ERROR = "error"


@dataclass(frozen=True)
class RunOutcome:
    """How a click run ended, reported once from the click thread."""

    reason: str
    message: str
    clicks: int
    error: BaseException | None = None


class ClickEngine:
    """Handles mouse clicking operations with threading and safety features"""

    def __init__(self, enable_performance_monitoring: bool = True):
        self.is_running = False
        self.click_thread: threading.Thread | None = None
        self.click_count = 0
        self.start_time = 0
        self._stop_event = threading.Event()

        # Performance monitoring
        self.enable_performance_monitoring = enable_performance_monitoring
        self.performance_metrics = {
            "click_timings": deque(maxlen=1000),  # Recent samples for debugging
            "click_success_count": 0,
            "click_error_count": 0,
            "average_click_time": 0.0,
            "min_click_time": float("inf"),
            "max_click_time": 0.0,
            "total_click_time": 0.0,
            # Welford running stats (avoid O(n) statistics.* on every status read)
            "_timing_count": 0,
            "_timing_mean": 0.0,
            "_timing_m2": 0.0,
        }

        self._last_click_xy: tuple[int, int] | None = None

        # Windowed CPS tracking (timestamps of recent successful clicks).
        # 1024 samples ≈ 10 s at the 100 cps ceiling we cap at; bounded so a
        # multi-day session never grows this deque.
        self._recent_click_ts: deque = deque(maxlen=1024)

        # Cached desktop bounds (all monitors); refreshed on start. Querying per
        # click is a Win32 syscall and noticeably hot at high CPS.
        self._screen_bounds: ScreenBounds | None = None

        self.failsafe_enabled = True
        self.max_cps_ceiling = 50
        self.pause_when_unfocused = False
        self._foreground_hwnd: int | None = None
        self._safety_fired = False
        # First stop source wins; reset on every start.
        self._stop_reason: tuple[str, str] | None = None
        self._stop_lock = threading.Lock()

    def configure_safety(
        self,
        *,
        failsafe: bool = True,
        max_cps: int = 50,
        pause_when_unfocused: bool = False,
    ) -> None:
        """Apply safety limits before starting."""
        self.failsafe_enabled = failsafe
        self.max_cps_ceiling = max(0, int(max_cps))
        self.pause_when_unfocused = pause_when_unfocused
        apply_failsafe(failsafe)

    def start_clicking(
        self,
        x: int | None,
        y: int | None,
        interval: float,
        variation: int,
        burst_clicks: int,
        burst_pause: float,
        max_clicks: int,
        auto_stop_minutes: int,
        mouse_button: str,
        click_type: str,
        on_finished: Callable[[RunOutcome], None] | None = None,
    ) -> bool:
        """
        Start the clicking process

        Args:
            x, y: Target coordinates, or None for both to click wherever the
                cursor is (cursor mode)
            interval: Base interval between clicks (ms)
            variation: Random variation range (±ms)
            burst_clicks: Number of clicks per burst
            burst_pause: Pause between bursts (seconds)
            max_clicks: Maximum clicks (0 = unlimited)
            auto_stop_minutes: Auto-stop after minutes (0 = disabled)
            mouse_button: 'left', 'right', or 'middle'
            click_type: 'single' or 'double'
            on_finished: Called exactly once, from the click thread, when the
                run ends for any reason (see RunOutcome)

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            return False
        if self.click_thread is not None and self.click_thread.is_alive():
            return False

        if self.pause_when_unfocused:
            hwnd = get_foreground_window_handle()
            if hwnd is None:
                return False
            self._foreground_hwnd = hwnd
        else:
            self._foreground_hwnd = None

        # Reset state
        self.is_running = True
        self._safety_fired = False
        self._stop_reason = None
        self.click_count = 0
        self.start_time = time.monotonic()
        self._stop_event.clear()
        self._last_click_xy = None
        self._recent_click_ts.clear()
        self._screen_bounds = virtual_screen_bounds(pyautogui.size)

        self.click_thread = threading.Thread(
            target=self._click_loop,
            args=(
                x,
                y,
                interval,
                variation,
                burst_clicks,
                burst_pause,
                max_clicks,
                auto_stop_minutes,
                mouse_button,
                click_type,
                on_finished,
            ),
            daemon=True,
            name="ClickLoop",
        )
        self.click_thread.start()

        return True

    def get_performance_metrics(self) -> dict:
        """Get current performance metrics"""
        metrics = self.performance_metrics.copy()

        # Calculate additional metrics
        total_clicks = metrics["click_success_count"] + metrics["click_error_count"]
        if total_clicks > 0:
            metrics["success_rate"] = (metrics["click_success_count"] / total_clicks) * 100
        else:
            metrics["success_rate"] = 0.0

        count = metrics.get("_timing_count", 0)
        if count > 0:
            mean = metrics["_timing_mean"]
            metrics["average_click_time"] = mean
            if count > 1:
                metrics["click_time_std_dev"] = (metrics["_timing_m2"] / (count - 1)) ** 0.5
            else:
                metrics["click_time_std_dev"] = 0.0

        # Calculate clicks per second if running
        if self.start_time > 0 and self.click_count > 0:
            runtime = time.monotonic() - self.start_time
            metrics["clicks_per_second"] = self.click_count / runtime if runtime > 0 else 0.0

        return metrics

    def reset_performance_metrics(self) -> None:
        """Reset all performance metrics"""
        self.performance_metrics = {
            "click_timings": deque(maxlen=1000),
            "click_success_count": 0,
            "click_error_count": 0,
            "average_click_time": 0.0,
            "min_click_time": float("inf"),
            "max_click_time": 0.0,
            "total_click_time": 0.0,
            "_timing_count": 0,
            "_timing_mean": 0.0,
            "_timing_m2": 0.0,
        }

    def _set_stop_reason(self, reason: str, message: str) -> None:
        """Record why the run is ending; only the first reason sticks."""
        with self._stop_lock:
            if self._stop_reason is None:
                self._stop_reason = (reason, message)

    def _request_stop(self) -> None:
        """Signal the click loop to exit without joining threads."""
        self.is_running = False
        self._stop_event.set()

    def _join_click_thread(self) -> None:
        """Join the click loop if it is a different, still-alive thread."""
        thread = self.click_thread
        if thread is None:
            return
        if thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=1.0)
        if thread is not threading.current_thread():
            self.click_thread = None

    def stop_clicking(self) -> None:
        """Stop the clicking process (joins the click thread unless called from it)."""
        if self.is_running:
            self._set_stop_reason(STOP_USER, "Stopped")
        self._request_stop()
        self._join_click_thread()

    def emergency_stop(self) -> None:
        """Emergency stop: signal the loop to halt without joining (safe from any thread)."""
        if self.is_running:
            self._set_stop_reason(STOP_EMERGENCY, "Emergency stop")
        self._request_stop()

    def _click_loop(
        self,
        x: int | None,
        y: int | None,
        interval: float,
        variation: int,
        burst_clicks: int,
        burst_pause: float,
        max_clicks: int,
        auto_stop_minutes: int,
        mouse_button: str,
        click_type: str,
        on_finished: Callable[[RunOutcome], None] | None,
    ) -> None:
        """Main clicking loop. Reports exactly one RunOutcome via on_finished."""
        error: BaseException | None = None
        try:
            while self.is_running and not self._stop_event.is_set():
                if self._should_pause_for_foreground():
                    self._stop_event.wait(timeout=0.1)
                    continue

                if self._check_runaway_cps():
                    self._trigger_safety_stop(
                        f"Runaway guard: over {self.max_cps_ceiling} clicks per second"
                    )
                    break

                # Check auto-stop conditions
                limit_message = self._limit_reached(max_clicks, auto_stop_minutes)
                if limit_message:
                    self._set_stop_reason(STOP_COMPLETED, limit_message)
                    break

                # Perform clicks
                self._perform_burst(x, y, burst_clicks, burst_pause, mouse_button, click_type)
                if self._safety_fired:
                    break

                # Wait for next burst
                if self.is_running and not self._stop_event.is_set():
                    self._wait_with_variation(interval, variation)

        except (SafetyError, pyautogui.FailSafeException):
            self._trigger_safety_stop("Failsafe: mouse moved to a screen corner")
        except Exception as e:
            _log.exception("Click loop error")
            error = e
            self._set_stop_reason(STOP_ERROR, create_user_friendly_error(e))
        finally:
            self._request_stop()
            self._set_stop_reason(STOP_COMPLETED, "Finished")
            reason, message = self._stop_reason or (STOP_COMPLETED, "Finished")
            if on_finished:
                try:
                    on_finished(RunOutcome(reason, message, self.click_count, error))
                except Exception:
                    _log.exception("on_finished callback failed")

    def _should_pause_for_foreground(self) -> bool:
        if not self.pause_when_unfocused:
            return False
        return not is_foreground_window(self._foreground_hwnd)

    def _check_runaway_cps(self) -> bool:
        """Detect runaway click rate using a sliding 1-second window.

        The previous implementation used a lifetime average, which is useless
        for long sessions: a sustained slow run dilutes any future spike.
        """
        if self.max_cps_ceiling <= 0 or self.start_time <= 0:
            return False
        elapsed = time.monotonic() - self.start_time
        if elapsed < 0.25:
            return False
        now = time.monotonic()
        # Drop timestamps older than 1s so the window slides
        ts = self._recent_click_ts
        cutoff = now - 1.0
        while ts and ts[0] < cutoff:
            ts.popleft()
        # Need a minimum sample to avoid flapping at startup
        if len(ts) < 8:
            return False
        return len(ts) > self.max_cps_ceiling

    def _trigger_safety_stop(self, message: str) -> None:
        self._safety_fired = True
        self._set_stop_reason(STOP_SAFETY, message)
        self._request_stop()

    def _limit_reached(self, max_clicks: int, auto_stop_minutes: int) -> str | None:
        """Return a completion message if a click or time limit was reached."""
        if max_clicks > 0 and self.click_count >= max_clicks:
            return f"Done: reached {max_clicks:,} clicks"

        if auto_stop_minutes > 0:
            elapsed_minutes = (time.monotonic() - self.start_time) / 60
            if elapsed_minutes >= auto_stop_minutes:
                unit = "minute" if auto_stop_minutes == 1 else "minutes"
                return f"Done: auto-stopped after {auto_stop_minutes} {unit}"

        return None

    def _should_stop(self, max_clicks: int, auto_stop_minutes: int) -> bool:
        """Check if clicking should stop based on limits"""
        return self._limit_reached(max_clicks, auto_stop_minutes) is not None

    def _perform_burst(
        self,
        x: int | None,
        y: int | None,
        burst_clicks: int,
        burst_pause: float,
        mouse_button: str,
        click_type: str,
    ) -> None:
        """Perform a burst of clicks"""
        for i in range(burst_clicks):
            if not self.is_running or self._stop_event.is_set():
                break

            self._perform_click(x, y, mouse_button, click_type)

            if self._check_runaway_cps():
                self._trigger_safety_stop(
                    f"Runaway guard: over {self.max_cps_ceiling} clicks per second"
                )
                break

            # Wait between clicks in burst (except for last click)
            if burst_clicks > 1 and i < burst_clicks - 1 and burst_pause > 0:
                self._stop_event.wait(timeout=burst_pause)

    def _perform_click(
        self,
        x: int | None,
        y: int | None,
        mouse_button: str,
        click_type: str,
    ) -> None:
        """Perform a single click at coordinates with performance monitoring"""
        click_start_time = time.perf_counter() if self.enable_performance_monitoring else None

        try:
            # Cursor mode (x and y are None): click wherever the cursor is.
            if x is not None and y is not None:
                # Validate against the cached desktop bounds; query live only if
                # the cache is empty (e.g. direct unit-test calls).
                if self._screen_bounds is None:
                    self._screen_bounds = virtual_screen_bounds(pyautogui.size)
                bounds = self._screen_bounds
                if not bounds.contains(x, y):
                    raise CoordinateError(
                        x,
                        y,
                        f"Coordinates ({x}, {y}) are off screen (valid: {bounds.describe()})",
                    )

                # Instant move; skip if already at target (avoids moveTo overhead each click)
                if self._last_click_xy != (x, y):
                    pyautogui.moveTo(x, y, duration=0)
                    self._last_click_xy = (x, y)

            if mouse_button not in ("left", "right", "middle"):
                raise ClickEngineError("perform_click", f"Unsupported mouse button: {mouse_button}")

            # One call for every button; a double click counts as one click toward
            # max_clicks and the runaway guard.
            try:
                pyautogui.click(button=mouse_button, clicks=2 if click_type == "double" else 1)
                # Record performance metrics
                if self.enable_performance_monitoring:
                    total_time = time.perf_counter() - click_start_time
                    self.performance_metrics["click_timings"].append(total_time)
                    self._record_timing_sample(total_time)
                    self.performance_metrics["click_success_count"] += 1
                    self.performance_metrics["total_click_time"] += total_time
                    self.performance_metrics["min_click_time"] = min(
                        self.performance_metrics["min_click_time"], total_time
                    )
                    self.performance_metrics["max_click_time"] = max(
                        self.performance_metrics["max_click_time"], total_time
                    )

                self.click_count += 1
                self._recent_click_ts.append(time.monotonic())

            except pyautogui.FailSafeException:
                if self.enable_performance_monitoring:
                    self.performance_metrics["click_error_count"] += 1
                raise SafetyError(
                    "fail_safe", "detected", "User moved mouse to corner during operation"
                )
            except pyautogui.PyAutoGUIException as e:
                if self.enable_performance_monitoring:
                    self.performance_metrics["click_error_count"] += 1
                raise ClickEngineError("perform_click", f"PyAutoGUI error: {e}")

        except (CoordinateError, ClickEngineError, SafetyError):
            # Record error metrics
            if self.enable_performance_monitoring:
                self.performance_metrics["click_error_count"] += 1
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Record error metrics for unexpected errors
            if self.enable_performance_monitoring:
                self.performance_metrics["click_error_count"] += 1
            # Wrap unexpected errors
            raise ClickEngineError("perform_click", f"Unexpected error: {e}") from e

    def _record_timing_sample(self, sample: float) -> None:
        """Update Welford running mean/variance for click timings."""
        metrics = self.performance_metrics
        count = metrics["_timing_count"] + 1
        delta = sample - metrics["_timing_mean"]
        mean = metrics["_timing_mean"] + delta / count
        delta2 = sample - mean
        m2 = metrics["_timing_m2"] + delta * delta2
        metrics["_timing_count"] = count
        metrics["_timing_mean"] = mean
        metrics["_timing_m2"] = m2

    def _wait_with_variation(self, interval: float, variation: int) -> None:
        """Wait for the specified interval with random variation (ms). Zero = no sleep."""
        if variation > 0:
            actual_interval = interval + random.randint(-variation, variation)
        else:
            actual_interval = interval

        wait_time = max(0.0, actual_interval / 1000)
        if wait_time > 0:
            self._stop_event.wait(timeout=wait_time)

    def get_status(self) -> dict:
        """Get current clicking status"""
        elapsed = int(time.monotonic() - self.start_time) if self.start_time > 0 else 0
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60

        status = {
            "is_running": self.is_running,
            "click_count": self.click_count,
            "runtime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "thread_alive": self.click_thread.is_alive() if self.click_thread else False,
        }

        # Add performance metrics if enabled
        if self.enable_performance_monitoring:
            metrics = self.get_performance_metrics()
            status["performance"] = {
                "clicks_per_second": round(metrics.get("clicks_per_second", 0), 2),
                "success_rate": round(metrics.get("success_rate", 0), 1),
                "average_click_time": round(
                    metrics.get("average_click_time", 0) * 1000, 2
                ),  # Convert to ms
                "total_errors": metrics.get("click_error_count", 0),
            }

        return status
