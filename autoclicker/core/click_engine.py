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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import pyautogui

from .exceptions import (
    ClickEngineError,
    CoordinateError,
    SafetyError,
    create_user_friendly_error,
)
from .image_match import ImageTarget
from .safety import (
    apply_failsafe,
    get_foreground_window_handle,
    is_foreground_window,
    is_own_window,
    root_window_at,
)
from .screen import (
    ScreenBounds,
    cursor_position,
    failsafe_corners,
    monitor_rects,
    virtual_screen_bounds,
)
from .settings_manager import MAX_CPS_CEILING

# Default PAUSE is 0.1s between every PyAutoGUI call, which caps CPS at about 5 to 10
pyautogui.PAUSE = 0
apply_failsafe(True)

_log = logging.getLogger(__name__)

# How close (in pixels) to a monitor corner counts as "in the corner".
_CORNER_MARGIN = 2
# During a Hold, how often the corner failsafe is checked.
_HOLD_CHECK_SECONDS = 0.05

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


@dataclass(frozen=True)
class ClickStep:
    """One step of a click sequence: click here, then wait before the next step."""

    x: int
    y: int
    button: str = "left"
    click_type: str = "single"
    delay_ms: float = 0.0


@dataclass(frozen=True)
class PixelCondition:
    """Click only while the pixel at (x, y) is within ``tolerance`` of ``rgb``.

    ``on_mismatch`` is "wait" (pause until it matches again) or "stop".
    """

    x: int
    y: int
    rgb: tuple[int, int, int]
    tolerance: int = 16
    on_mismatch: str = "wait"

    def matches(self, rgb: tuple[int, int, int]) -> bool:
        return all(abs(a - b) <= self.tolerance for a, b in zip(rgb, self.rgb, strict=True))


# A screen read waits for the next composed frame (~17 ms at 60 Hz), so the
# watched pixel is polled on its own thread at this interval instead of on the
# click thread; the click loop only reads the latest result.
_CONDITION_POLL_SECONDS = 0.05
# How often a run waiting on the pixel re-checks it.
_CONDITION_WAIT_SECONDS = 0.02
PAUSE_FOCUS = "the target window to be in front"
PAUSE_PIXEL = "the watched pixel to match"
PAUSE_IMAGE = "the captured image to appear"
# How often an image target is searched for, on its own thread.
_IMAGE_POLL_SECONDS = 0.1


@dataclass
class ClickStats:
    """Per-run click outcomes and timing, updated in O(1) per click.

    Timing uses Welford's running mean/variance so the 1 Hz status poll never
    scans a history.
    """

    successes: int = 0
    errors: int = 0
    timing_count: int = 0
    timing_mean: float = 0.0
    timing_m2: float = 0.0

    def record_success(self, seconds: float) -> None:
        self.successes += 1
        self.timing_count += 1
        delta = seconds - self.timing_mean
        self.timing_mean += delta / self.timing_count
        self.timing_m2 += delta * (seconds - self.timing_mean)

    @property
    def success_rate(self) -> float:
        """Percentage of attempted clicks that succeeded (0 before any attempt)."""
        attempts = self.successes + self.errors
        return self.successes / attempts * 100 if attempts else 0.0

    @property
    def timing_std_dev(self) -> float:
        if self.timing_count < 2:
            return 0.0
        return float((self.timing_m2 / (self.timing_count - 1)) ** 0.5)


class ClickEngine:
    """Handles mouse clicking operations with threading and safety features"""

    def __init__(self, enable_performance_monitoring: bool = True):
        self.is_running = False
        self.click_thread: threading.Thread | None = None
        self.click_count = 0
        self.start_time = 0.0
        self._stop_event = threading.Event()

        # Performance monitoring; reset at every start so the numbers are per run.
        self.enable_performance_monitoring = enable_performance_monitoring
        self.stats = ClickStats()

        # Windowed CPS tracking (timestamps of recent button presses). Must hold
        # one more sample than the highest ceiling or the guard could never trip;
        # bounded so a multi-day session with the guard off never grows it.
        self._recent_click_ts: deque[float] = deque(maxlen=MAX_CPS_CEILING + 1)

        # Cached desktop bounds (all monitors); refreshed on start. Querying per
        # click is a Win32 syscall and noticeably hot at high CPS.
        self._screen_bounds: ScreenBounds | None = None

        self.failsafe_enabled = True
        # Corner pixels of every monitor that abort a run (PyAutoGUI's own
        # failsafe only watches the primary monitor). Empty = not checked.
        self._failsafe_corners: frozenset[tuple[int, int]] = frozenset()
        self.max_cps_ceiling = 50
        self.pause_when_unfocused = False
        # Window that must stay in front while pause_when_unfocused is on.
        # None during a run means "adopt the next window in front that isn't ours".
        self._foreground_hwnd: int | None = None
        # Sequence mode: windows under the step points, any of which may be in front.
        self._step_hwnds: frozenset[int] = frozenset()
        self._point_target = False  # the run clicks known points (fixed or sequence)
        self._target_seen = False  # a target window has been in front during this run
        # Windows treated like our own for pause_when_unfocused, such as the console
        # a headless run was started from (#94): never adopted as the target.
        self.launcher_windows: frozenset[int] = frozenset()
        self.is_paused = False
        self.pause_reason = ""  # what a paused run waits for (PAUSE_FOCUS / PAUSE_PIXEL)
        self._condition: PixelCondition | None = None
        # Latest pixel reading for this run: True/False, or None before the first read.
        self._condition_state: bool | None = None
        # Image target mode: where the captured image was last found (None = not found).
        self._image: ImageTarget | None = None
        self._image_pos: tuple[int, int] | None = None
        self._run_id = 0  # lets a stale pixel watcher from an earlier run notice and exit
        self._safety_fired = False
        # Sequence mode: the steps of one round and how many rounds to run
        # (0 = until stopped). Empty means a normal single-target run.
        self._steps: tuple[ClickStep, ...] = ()
        self._repeat = 0
        # What each "click" does: "click", "hold" (press the button for
        # _hold_ms, then release) or "key" (press _key, e.g. "f5" or "ctrl+r").
        self._action = "click"
        self._hold_ms = 0.0
        self._key = ""
        self.current_step = 0  # 1-based step being clicked, for error messages
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
        self._refresh_failsafe_corners()

    def _refresh_failsafe_corners(self) -> None:
        self._failsafe_corners = (
            failsafe_corners(monitor_rects()) if self.failsafe_enabled else frozenset()
        )

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
        *,
        steps: Sequence[ClickStep] | None = None,
        repeat: int = 0,
        action: str = "click",
        hold_ms: float = 0.0,
        key: str = "",
        condition: PixelCondition | None = None,
        image: ImageTarget | None = None,
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
            steps: Sequence mode. Each round clicks every step in order (x, y,
                mouse_button, click_type and burst settings are ignored), then
                waits ``interval`` before the next round
            repeat: Rounds to run in sequence mode (0 = until stopped)
            action: "click", "hold" (press mouse_button for ``hold_ms``, then
                release; released on every stop path) or "key" (press ``key``,
                such as "f5" or "ctrl+r", wherever the focus is)
            condition: Only click while this pixel condition holds
            image: Image target mode: click the center of this image wherever it
                is found in its search region (x and y are ignored); wait while
                it isn't there

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            return False
        if self.click_thread is not None and self.click_thread.is_alive():
            return False

        if action not in ("click", "hold", "key"):
            raise ClickEngineError("start_clicking", f"Unsupported action: {action}")
        self._steps = tuple(steps or ())
        self._repeat = max(0, int(repeat))
        self._action = "click" if self._steps else action
        self._hold_ms = max(0.0, float(hold_ms))
        self._key = key
        self._condition = condition
        self._condition_state = None
        self._image = image
        self._image_pos = None
        self.current_step = 0
        if self.pause_when_unfocused:
            hwnd = get_foreground_window_handle()
            if hwnd is None:
                return False
            if self._steps:
                x, y = self._steps[0].x, self._steps[0].y
            self._foreground_hwnd = self._pick_focus_window(hwnd, x, y)
            # A sequence may click into several windows; any of them counts as in front.
            self._step_hwnds = self._windows_under_steps()
            self._point_target = x is not None and y is not None and self._action != "key"
            self._target_seen = False
        else:
            self._foreground_hwnd = None
            self._step_hwnds = frozenset()
        self.is_paused = False

        # Reset state
        self.is_running = True
        self._safety_fired = False
        self._stop_reason = None
        self.click_count = 0
        self.stats = ClickStats()
        self.start_time = time.monotonic()
        self._stop_event.clear()
        self._recent_click_ts.clear()
        self._screen_bounds = virtual_screen_bounds(pyautogui.size)
        self._refresh_failsafe_corners()  # the monitor layout may have changed
        self._run_id += 1
        if condition is not None:
            threading.Thread(
                target=self._watch_condition,
                args=(condition, self._run_id),
                daemon=True,
                name="PixelWatch",
            ).start()
        if image is not None:
            threading.Thread(
                target=self._watch_image,
                args=(image, self._run_id),
                daemon=True,
                name="ImageWatch",
            ).start()

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

    def get_performance_metrics(self) -> dict[str, float]:
        """Performance numbers for the current (or last) run."""
        stats = self.stats
        clicks_per_second = 0.0
        if self.start_time > 0 and self.click_count > 0:
            runtime = time.monotonic() - self.start_time
            clicks_per_second = self.click_count / runtime if runtime > 0 else 0.0
        return {
            "click_success_count": stats.successes,
            "click_error_count": stats.errors,
            "success_rate": stats.success_rate,
            "average_click_time": stats.timing_mean,
            "click_time_std_dev": stats.timing_std_dev,
            "clicks_per_second": clicks_per_second,
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
        rounds = 0
        try:
            while self.is_running and not self._stop_event.is_set():
                if self._should_pause_for_foreground():
                    # A run paused for focus still ends on time (#94).
                    limit_message = self._limit_reached(max_clicks, auto_stop_minutes)
                    if limit_message:
                        self._set_stop_reason(STOP_COMPLETED, limit_message)
                        break
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

                verdict = self._check_condition()
                if verdict == "stop":
                    break
                if verdict == "wait":
                    self._stop_event.wait(timeout=_CONDITION_WAIT_SECONDS)
                    continue

                if self._image is not None:
                    found = self._image_pos
                    if found is None:
                        self.is_paused = True
                        self.pause_reason = PAUSE_IMAGE
                        self._stop_event.wait(timeout=_CONDITION_WAIT_SECONDS)
                        continue
                    self.is_paused = False
                    x, y = found

                # Perform clicks
                if self._steps:
                    if not self._perform_sequence(max_clicks, auto_stop_minutes):
                        break
                    rounds += 1
                    if self._repeat and rounds >= self._repeat:
                        times = "time" if self._repeat == 1 else "times"
                        self._set_stop_reason(
                            STOP_COMPLETED, f"Done: ran the sequence {self._repeat:,} {times}"
                        )
                        break
                else:
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
            message = create_user_friendly_error(e)
            if self._steps and self.current_step:
                message = f"Step {self.current_step}: {message}"
            self._set_stop_reason(STOP_ERROR, message)
        finally:
            self.is_paused = False
            self._request_stop()
            self._set_stop_reason(STOP_COMPLETED, "Finished")
            reason, message = self._stop_reason or (STOP_COMPLETED, "Finished")
            if on_finished:
                try:
                    on_finished(RunOutcome(reason, message, self.click_count, error))
                except Exception:
                    _log.exception("on_finished callback failed")

    def _is_ours(self, hwnd: int) -> bool:
        """Our own window, or one we were launched from (fails closed like is_own_window)."""
        return hwnd in self.launcher_windows or is_own_window(hwnd)

    def _pick_focus_window(self, foreground: int, x: int | None, y: int | None) -> int | None:
        """Choose the window that must stay in front for pause_when_unfocused.

        Started from a hotkey, the window in front is the user's target. Started
        from our own Start button or tray menu it is the autoclicker itself, so
        use the window under a fixed target instead, or (cursor mode, or our
        window covers the target) return None to adopt the next window that
        comes to the front.
        """
        if not self._is_ours(foreground):
            return foreground
        if x is not None and y is not None:
            under = root_window_at(x, y)
            if under is not None and not self._is_ours(under):
                return under
        return None

    def _own_window_ok(self) -> bool:
        """True while our own window may be in front without pausing.

        Started from the Start button, the autoclicker itself is in front, and
        the run's first click is what activates the target. That is allowed for
        a fixed point or a sequence (whose points were checked to be on other
        windows) until a target window has been in front once; after that, the
        user switching to the autoclicker pauses as usual. Never in cursor mode,
        where the cursor may be over our own buttons.
        """
        if self._target_seen or not self._point_target:
            return False
        current = get_foreground_window_handle()
        return current is not None and self._is_ours(current)

    def _windows_under_steps(self) -> frozenset[int]:
        """Top-level windows (not ours) under the sequence's step points."""
        windows = set()
        for step in self._steps:
            hwnd = root_window_at(step.x, step.y)
            if hwnd is not None and not self._is_ours(hwnd):
                windows.add(hwnd)
        return frozenset(windows)

    def _should_pause_for_foreground(self) -> bool:
        if not self.pause_when_unfocused:
            self.is_paused = False
            return False
        if self._step_hwnds:
            # Sequence mode: in front means any window a step clicks into.
            allowed = set(self._step_hwnds)
            if self._foreground_hwnd is not None:
                allowed.add(self._foreground_hwnd)
            current = get_foreground_window_handle()
            paused = current is None or current not in allowed  # fail closed
        else:
            if self._foreground_hwnd is None:
                current = get_foreground_window_handle()
                if current is not None and not self._is_ours(current):
                    self._foreground_hwnd = current
            if self._foreground_hwnd is None:
                paused = True  # still waiting for a target window (fail closed)
            else:
                paused = not is_foreground_window(self._foreground_hwnd)
        if paused and self._own_window_ok():
            paused = False  # the first click brings the target window forward
        elif not paused:
            self._target_seen = True
        self.is_paused = paused
        if paused:
            self.pause_reason = PAUSE_FOCUS
        return paused

    def _check_condition(self) -> str:
        """Return "go", "wait" or "stop" for the pixel condition (records a stop reason).

        Before the first reading arrives the run waits, whatever the mode.
        """
        condition = self._condition
        if condition is None:
            return "go"
        state = self._condition_state
        if state is True:
            self.is_paused = False
            return "go"
        if state is False and condition.on_mismatch == "stop":
            self._set_stop_reason(STOP_COMPLETED, "Stopped: the watched pixel changed")
            return "stop"
        self.is_paused = True
        self.pause_reason = PAUSE_PIXEL
        return "wait"

    def _watch_image(self, image: ImageTarget, run_id: int) -> None:
        """(ImageWatch thread) keep _image_pos current until this run ends."""
        while run_id == self._run_id and self.is_running and not self._stop_event.is_set():
            try:
                found = image.locate()
            except Exception:
                _log.debug("Image search failed", exc_info=True)
                found = None
            if run_id != self._run_id:
                return
            self._image_pos = found
            self._stop_event.wait(timeout=_IMAGE_POLL_SECONDS)

    def _watch_condition(self, condition: PixelCondition, run_id: int) -> None:
        """(PixelWatch thread) keep _condition_state current until this run ends."""
        while run_id == self._run_id and self.is_running and not self._stop_event.is_set():
            state = self._read_condition(condition)
            if run_id != self._run_id:
                return
            self._condition_state = state
            self._stop_event.wait(timeout=_CONDITION_POLL_SECONDS)

    @staticmethod
    def _read_condition(condition: PixelCondition) -> bool:
        try:
            rgb = tuple(pyautogui.pixel(condition.x, condition.y))[:3]
            return condition.matches((int(rgb[0]), int(rgb[1]), int(rgb[2])))
        except Exception:
            return False  # can't read the screen: don't click (fail closed)

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

    def _perform_sequence(self, max_clicks: int, auto_stop_minutes: int) -> bool:
        """Click every step once, in order. Returns False if the run should end.

        Stop requests, limits, pause when unfocused and the runaway guard are
        checked before every step, not just once per round. The wait after
        the last step is the main interval, applied by the caller.
        """
        last = len(self._steps)
        for index, step in enumerate(self._steps, start=1):
            while self._should_pause_for_foreground():
                if self._stop_event.wait(timeout=0.1):
                    return False
                limit_message = self._limit_reached(max_clicks, auto_stop_minutes)
                if limit_message:
                    self._set_stop_reason(STOP_COMPLETED, limit_message)
                    return False
            if not self.is_running or self._stop_event.is_set():
                return False
            limit_message = self._limit_reached(max_clicks, auto_stop_minutes)
            if limit_message:
                self._set_stop_reason(STOP_COMPLETED, limit_message)
                return False
            while (verdict := self._check_condition()) == "wait":
                if self._stop_event.wait(timeout=_CONDITION_WAIT_SECONDS):
                    return False
                limit_message = self._limit_reached(max_clicks, auto_stop_minutes)
                if limit_message:
                    self._set_stop_reason(STOP_COMPLETED, limit_message)
                    return False
            if verdict == "stop":
                return False

            self.current_step = index
            self._perform_click(step.x, step.y, step.button, step.click_type)

            if self._check_runaway_cps():
                self._trigger_safety_stop(
                    f"Runaway guard: over {self.max_cps_ceiling} clicks per second"
                )
                return False
            if index < last and step.delay_ms > 0:
                self._stop_event.wait(timeout=step.delay_ms / 1000)
        return True

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
        click_start_time = time.perf_counter()

        try:
            if self._cursor_in_failsafe_corner(x, y):
                raise SafetyError("fail_safe", "detected", "Mouse moved to a screen corner")

            # Cursor mode (x and y are None): click wherever the cursor is.
            position: dict[str, int] = {}
            if x is not None and y is not None and self._action != "key":
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

                # Pass the target on every click: the user may have moved the
                # mouse since the last one, and the click must not follow it.
                position = {"x": x, "y": y}

            if mouse_button not in ("left", "right", "middle"):
                raise ClickEngineError("perform_click", f"Unsupported mouse button: {mouse_button}")

            # One call for every button. A double click counts as one click toward
            # max_clicks, but as two presses for the runaway guard.
            presses = 2 if click_type == "double" and self._action == "click" else 1
            try:
                if self._action == "key":
                    keys = self._key.split("+")
                    if len(keys) == 1:
                        pyautogui.press(keys[0])
                    else:
                        pyautogui.hotkey(*keys)
                elif self._action == "hold":
                    self._hold(position, mouse_button)
                else:
                    pyautogui.click(**position, button=mouse_button, clicks=presses)
                if self.enable_performance_monitoring:
                    self.stats.record_success(time.perf_counter() - click_start_time)

                self.click_count += 1
                now = time.monotonic()
                for _ in range(presses):
                    self._recent_click_ts.append(now)

            except pyautogui.FailSafeException:
                raise SafetyError(
                    "fail_safe", "detected", "User moved mouse to corner during operation"
                )
            except pyautogui.PyAutoGUIException as e:
                raise ClickEngineError("perform_click", f"PyAutoGUI error: {e}")

        except (CoordinateError, ClickEngineError, SafetyError):
            # Counted once here, whichever check raised it
            self.stats.errors += 1
            raise
        except Exception as e:
            self.stats.errors += 1
            raise ClickEngineError("perform_click", f"Unexpected error: {e}") from e

    def _hold(self, position: dict[str, int], button: str) -> None:
        """Press ``button`` for the hold time; always release it, even when stopping."""
        pyautogui.mouseDown(**position, button=button)
        try:
            # Wait in short slices so a stop request or the corner failsafe ends
            # the hold early; the button is released either way.
            deadline = time.monotonic() + self._hold_ms / 1000
            x, y = position.get("x"), position.get("y")
            while (remaining := deadline - time.monotonic()) > 0:
                if self._stop_event.wait(timeout=min(remaining, _HOLD_CHECK_SECONDS)):
                    return
                if self._cursor_in_failsafe_corner(x, y):
                    raise SafetyError("fail_safe", "detected", "Mouse moved to a screen corner")
        finally:
            self._release(button)

    @staticmethod
    def _release(button: str) -> None:
        try:
            pyautogui.mouseUp(button=button)
        except pyautogui.FailSafeException:
            # The cursor is in a failsafe corner. Release anyway so the button is
            # never left pressed, then let the failsafe stop the run.
            previous = pyautogui.FAILSAFE
            pyautogui.FAILSAFE = False
            try:
                pyautogui.mouseUp(button=button)
            finally:
                pyautogui.FAILSAFE = previous
            raise

    def _cursor_in_failsafe_corner(self, x: int | None, y: int | None) -> bool:
        """True if the user has moved the cursor into a failsafe corner of any monitor."""
        if not self.failsafe_enabled or not self._failsafe_corners:
            return False
        position = cursor_position()
        # Resting on a fixed target that happens to be a corner is not a request to stop.
        if position is None or position == (x, y):
            return False
        px, py = position
        return any(
            abs(px - cx) <= _CORNER_MARGIN and abs(py - cy) <= _CORNER_MARGIN
            for cx, cy in self._failsafe_corners
        )

    def _wait_with_variation(self, interval: float, variation: int) -> None:
        """Wait for the specified interval with random variation (ms). Zero = no sleep."""
        if variation > 0:
            actual_interval = interval + random.randint(-variation, variation)
        else:
            actual_interval = interval

        wait_time = max(0.0, actual_interval / 1000)
        if wait_time > 0:
            self._stop_event.wait(timeout=wait_time)

    def get_status(self) -> dict[str, Any]:
        """Get current clicking status"""
        elapsed = int(time.monotonic() - self.start_time) if self.start_time > 0 else 0
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60

        status: dict[str, Any] = {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
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
                "total_errors": int(metrics["click_error_count"]),
            }

        return status
