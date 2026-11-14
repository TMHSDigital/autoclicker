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
from dataclasses import dataclass, field
from typing import Any

from .exceptions import (
    ClickEngineError,
    CoordinateError,
    SafetyError,
    create_user_friendly_error,
)
from .image_match import ImageTarget
from .lazy_pyautogui import pyautogui
from .safety import (
    DEFAULT_MAX_CPS,
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
    """One step of a sequence, then a wait of ``delay_ms`` before the next step (#119).

    ``type`` is one of:

    - "click" (the default, as in every sequence saved before #119);
    - "hold": press ``button`` at the point for ``hold_ms``;
    - "key": press ``key`` into the window in front (no point);
    - "wait_image": wait until ``image`` is on screen, then click its center
      with ``button`` and ``click_type`` if ``click`` is set;
    - "wait_pixel": wait until the pixel at (x, y) is within ``tolerance`` of ``rgb``.

    A wait gives up after ``timeout_ms`` (0 = never) and then either ends the
    run (``on_timeout`` "stop") or goes on to the next step ("skip").
    """

    x: int | None = None
    y: int | None = None
    button: str = "left"
    click_type: str = "single"
    delay_ms: float = 0.0
    type: str = "click"
    hold_ms: float = 0.0
    key: str = ""
    timeout_ms: float = 0.0
    on_timeout: str = "stop"
    click: bool = False
    rgb: tuple[int, int, int] | None = None
    tolerance: int = 16
    image: ImageTarget | None = field(default=None, repr=False, compare=False)

    @property
    def point(self) -> tuple[int, int] | None:
        """The point the step clicks or holds, or None when it has none.

        A wait_pixel step watches a point but never clicks it, so it adds no
        window for Pause when unfocused either.
        """
        if self.type not in ("click", "hold") or self.x is None or self.y is None:
            return None
        return self.x, self.y


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
# A match is clicked only if its screenshot was taken at least this long after
# the previous click, so a click that closes the image is never repeated on
# whatever is underneath (#96). Gives the clicked window time to repaint.
_IMAGE_SETTLE_SECONDS = 0.05
# Consecutive failed screen grabs (not "not found") that end an image run (#100).
_IMAGE_MAX_FAILURES = 20
# How often a wait step in a sequence looks for its image or pixel (#119).
_STEP_WAIT_POLL_SECONDS = 0.1


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


@dataclass(frozen=True)
class RunConfig:
    """Everything one run needs (#171). Times are in milliseconds unless named otherwise.

    x, y: the target point, or None for both to click wherever the cursor is.
    interval_ms, variation_ms: wait between bursts (or rounds) and its random +/- range.
    burst_clicks, burst_pause_ms: clicks per burst and the wait between them.
    max_clicks, auto_stop_minutes: limits (0 = none); stop_at is a
        ``(time.monotonic() deadline, "HH:MM")`` for Stop at (#177).
    steps, repeat: sequence mode (x, y, button, click type and burst are then
        per step or ignored) and its rounds (0 = until stopped).
    action: "click", "hold" (press mouse_button for hold_ms; released on every
        stop path) or "key" (press ``key``, such as "f5" or "ctrl+r").
    condition: only click while this pixel condition holds.
    image: click the center of this image wherever it is found (x, y ignored).
    spread: land each click up to this many px from the target, at random.
    """

    x: int | None
    y: int | None
    interval_ms: float
    variation_ms: int = 0
    burst_clicks: int = 1
    burst_pause_ms: float = 0.0
    max_clicks: int = 0
    auto_stop_minutes: float = 0.0
    mouse_button: str = "left"
    click_type: str = "single"
    steps: tuple[ClickStep, ...] = ()
    repeat: int = 0
    action: str = "click"
    hold_ms: float = 0.0
    key: str = ""
    condition: PixelCondition | None = None
    image: ImageTarget | None = None
    spread: int = 0
    stop_at: tuple[float, str] | None = None


class ClickEngine:
    """Handles mouse clicking operations with threading and safety features"""

    def __init__(self, enable_performance_monitoring: bool = True):
        self.is_running = False
        self.click_thread: threading.Thread | None = None
        self.click_count = 0
        self.start_time = 0.0
        # Stop at a time of day: (monotonic deadline, "HH:MM"), or None (#177).
        self._stop_at: tuple[float, str] | None = None
        # The run's (max_clicks, auto_stop_minutes), for progress readouts (#173).
        self._limits: tuple[int, float] = (0, 0.0)
        # When the image target was first missed in a row (0 = seen or not yet searched).
        self._image_missing_since = 0.0
        # When the last run's loop ended (0 while running), so idle readouts
        # keep that run's runtime and rate instead of counting on (#148).
        self.end_time = 0.0
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
        self.max_cps_ceiling = DEFAULT_MAX_CPS
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
        # Image target mode: where the captured image was last found (None = not
        # found) and when that search began; and when it was last clicked.
        self._image: ImageTarget | None = None
        self._image_match: tuple[tuple[int, int] | None, float] = (None, 0.0)
        self._image_clicked_at = float("-inf")
        # Click spread (#120): each click lands up to this many px from the target.
        self._spread = 0
        # Where the last click actually went, so the corner failsafe knows the
        # cursor resting there was put there by us.
        self._last_click_pos: tuple[int, int] | None = None
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
        max_cps: int = DEFAULT_MAX_CPS,
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
        auto_stop_minutes: float,
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
        spread: int = 0,
        stop_at: tuple[float, str] | None = None,
    ) -> bool:
        """Start a run from loose arguments; see RunConfig. ``burst_pause`` is in seconds.

        Kept for callers and tests that predate RunConfig; new code uses start().
        """
        config = RunConfig(
            x=x,
            y=y,
            interval_ms=interval,
            variation_ms=variation,
            burst_clicks=burst_clicks,
            burst_pause_ms=burst_pause * 1000,
            max_clicks=max_clicks,
            auto_stop_minutes=auto_stop_minutes,
            mouse_button=mouse_button,
            click_type=click_type,
            steps=tuple(steps or ()),
            repeat=repeat,
            action=action,
            hold_ms=hold_ms,
            key=key,
            condition=condition,
            image=image,
            spread=spread,
            stop_at=stop_at,
        )
        return self.start(config, on_finished)

    def start(
        self, config: RunConfig, on_finished: Callable[[RunOutcome], None] | None = None
    ) -> bool:
        """Start a run. True if it started; False if one is still running or shutting down.

        ``on_finished`` is called exactly once, from the click thread, when the
        run ends for any reason (see RunOutcome).
        """
        x, y = config.x, config.y
        steps, repeat, action = config.steps, config.repeat, config.action
        condition, image = config.condition, config.image
        if self.is_running:
            return False
        if self.click_thread is not None and self.click_thread.is_alive():
            return False

        if action not in ("click", "hold", "key"):
            raise ClickEngineError("start_clicking", f"Unsupported action: {action}")
        self._steps = tuple(steps or ())
        self._repeat = max(0, int(repeat))
        self._action = "click" if self._steps else action
        self._hold_ms = max(0.0, float(config.hold_ms))
        self._key = config.key
        self._condition = condition
        self._condition_state = None
        self._image = image
        self._image_match = (None, 0.0)
        self._image_clicked_at = float("-inf")
        self._spread = max(0, int(config.spread))
        self._last_click_pos = None
        self.current_step = 0
        if self.pause_when_unfocused:
            hwnd = get_foreground_window_handle()
            if hwnd is None:
                return False
            if self._steps:
                points = [step.point for step in self._steps if step.point is not None]
                x, y = points[0] if points else (None, None)
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
        self.end_time = 0.0
        self._stop_at = config.stop_at
        self._limits = (max(0, int(config.max_clicks)), max(0.0, float(config.auto_stop_minutes)))
        self._image_missing_since = 0.0
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
            args=(config, on_finished),
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
            runtime = self.run_seconds()
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
        """Join the click loop if it is a different, still-alive thread.

        The reference is only dropped once the thread has exited, so a join
        that timed out still counts as busy in ``start_clicking`` (#145).
        """
        thread = self.click_thread
        if thread is None or thread is threading.current_thread():
            return
        if thread.is_alive():
            thread.join(timeout=1.0)
        if not thread.is_alive():
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
        self, config: RunConfig, on_finished: Callable[[RunOutcome], None] | None
    ) -> None:
        """Main clicking loop. Reports exactly one RunOutcome via on_finished."""
        x, y = config.x, config.y
        error: BaseException | None = None
        rounds = 0
        try:
            while self.is_running and not self._stop_event.is_set():
                if self._should_pause_for_foreground():
                    # A run paused for focus still ends on time (#94).
                    if self._check_limits():
                        break
                    self._stop_event.wait(timeout=0.1)
                    continue

                if self._runaway_tripped() or self._check_limits():
                    break

                verdict = self._check_condition()
                if verdict == "stop":
                    break
                if verdict == "wait":
                    self._stop_event.wait(timeout=_CONDITION_WAIT_SECONDS)
                    continue

                if self._image is not None:
                    found, searched_at = self._image_match
                    if found is None:
                        gone = self._image_gone_message()
                        if gone:
                            self._set_stop_reason(STOP_COMPLETED, gone)
                            break
                        self.is_paused = True
                        self.pause_reason = PAUSE_IMAGE
                        self._stop_event.wait(timeout=_CONDITION_WAIT_SECONDS)
                        continue
                    self._image_missing_since = 0.0
                    self.is_paused = False
                    if searched_at < self._image_clicked_at + _IMAGE_SETTLE_SECONDS:
                        # Seen before the last click took effect: it may be gone now.
                        self._stop_event.wait(timeout=_CONDITION_WAIT_SECONDS)
                        continue
                    x, y = found

                # Perform clicks
                if self._steps:
                    if not self._perform_sequence():
                        break
                    rounds += 1
                    if self._repeat and rounds >= self._repeat:
                        times = "time" if self._repeat == 1 else "times"
                        self._set_stop_reason(
                            STOP_COMPLETED, f"Done: ran the sequence {self._repeat:,} {times}"
                        )
                        break
                else:
                    self._perform_burst(
                        x,
                        y,
                        config.burst_clicks,
                        config.burst_pause_ms / 1000,
                        config.mouse_button,
                        config.click_type,
                    )
                    if self._image is not None:
                        self._image_clicked_at = time.monotonic()
                if self._safety_fired:
                    break

                # Wait for next burst
                if self.is_running and not self._stop_event.is_set():
                    self._wait_with_variation(config.interval_ms, config.variation_ms)

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
            self.end_time = time.monotonic()
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
            if step.point is None:
                continue  # a key step goes to whatever window is in front
            hwnd = root_window_at(*step.point)
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
        """(ImageWatch thread) keep _image_match current until this run ends."""
        failures = 0
        while run_id == self._run_id and self.is_running and not self._stop_event.is_set():
            searched_at = time.monotonic()
            try:
                found = image.locate()
                failures = 0
            except Exception as e:
                failures += 1
                if failures == 1:
                    _log.warning("Image search failed: %s", e, exc_info=True)
                if failures >= _IMAGE_MAX_FAILURES and run_id == self._run_id:
                    # Waiting forever on a screen that can't be read helps no one.
                    self._set_stop_reason(STOP_ERROR, f"Could not read the screen: {e}")
                    self._request_stop()
                    return
                found = None
            if run_id != self._run_id:
                return
            self._image_match = (found, searched_at)
            # A slow search (wide margin with tolerance) waits as long as it took,
            # so the watcher never keeps a core busy (#161, #195).
            took = time.monotonic() - searched_at
            self._stop_event.wait(timeout=max(_IMAGE_POLL_SECONDS, took))

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
        # Need a minimum sample to avoid flapping at startup, but never more
        # than the ceiling allows: a limit of 2 must trip at the 3rd press (#149).
        if len(ts) < min(8, self.max_cps_ceiling + 1):
            return False
        return len(ts) > self.max_cps_ceiling

    def _trigger_safety_stop(self, message: str) -> None:
        self._safety_fired = True
        self._set_stop_reason(STOP_SAFETY, message)
        self._request_stop()

    def _image_gone_message(self) -> str | None:
        """The stop message once the image has been missing too long, else None (#174).

        The clock starts at the first search that misses it and resets
        whenever it is found again.
        """
        limit = getattr(self._image, "missing_stop_seconds", 0)
        if not isinstance(limit, (int, float)) or limit <= 0:
            return None
        now = time.monotonic()
        if not self._image_missing_since:
            self._image_missing_since = now
        if now - self._image_missing_since < limit:
            return None
        seconds = f"{limit:g}"
        return f"Stopped: image not seen for {seconds} s"

    def _check_limits(self) -> bool:
        """End the run (completed) if one of its limits is reached; True if so (#171)."""
        message = self._limit_reached(*self._limits)
        if message:
            self._set_stop_reason(STOP_COMPLETED, message)
        return message is not None

    def _runaway_tripped(self) -> bool:
        """Fire the runaway guard if the recent click rate is over the ceiling (#171)."""
        if not self._check_runaway_cps():
            return False
        self._trigger_safety_stop(f"Runaway guard: over {self.max_cps_ceiling} clicks per second")
        return True

    def _limit_reached(self, max_clicks: int, auto_stop_minutes: float) -> str | None:
        """Return a completion message if a click or time limit was reached."""
        if max_clicks > 0 and self.click_count >= max_clicks:
            return f"Done: reached {max_clicks:,} click{'s' * (max_clicks != 1)}"

        if auto_stop_minutes > 0:
            elapsed_minutes = (time.monotonic() - self.start_time) / 60
            if elapsed_minutes >= auto_stop_minutes:
                unit = "minute" if auto_stop_minutes == 1 else "minutes"
                return f"Done: auto-stopped after {auto_stop_minutes:g} {unit}"

        if self._stop_at is not None and time.monotonic() >= self._stop_at[0]:
            return f"Done: stopped at {self._stop_at[1]}"

        return None

    def _perform_sequence(self) -> bool:
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
                if self._check_limits():
                    return False
            if not self.is_running or self._stop_event.is_set():
                return False
            if self._check_limits():
                return False
            while (verdict := self._check_condition()) == "wait":
                if self._stop_event.wait(timeout=_CONDITION_WAIT_SECONDS):
                    return False
                if self._check_limits():
                    return False
            if verdict == "stop":
                return False

            self.current_step = index
            if step.type in ("wait_image", "wait_pixel"):
                go_on, found = self._wait_for_step(index, step)
                if not go_on:
                    return False
                if found is not None and step.click:
                    self._perform_click(*found, step.button, step.click_type, action="click")
            else:
                self._perform_click(
                    step.x,
                    step.y,
                    step.button,
                    step.click_type,
                    action=step.type,
                    key=step.key,
                    hold_ms=step.hold_ms,
                )

            if self._runaway_tripped():
                return False
            if index < last and step.delay_ms > 0:
                self._stop_event.wait(timeout=step.delay_ms / 1000)
        return True

    def _wait_for_step(self, index: int, step: ClickStep) -> tuple[bool, tuple[int, int] | None]:
        """Wait until a wait step's image or pixel is on screen (#119).

        Returns ``(go_on, where)``: where it was found, or None when it timed
        out and the step is skipped. ``go_on`` is False if the run must end (a
        stop, a limit, the timeout with on_timeout "stop", or a screen that
        can't be read). Every poll
        re-checks stop requests, limits, pause when unfocused and the failsafe
        corner, so each stop path holds mid-wait. The timeout keeps counting
        while the run is paused for focus.
        """
        what = "image" if step.type == "wait_image" else "pixel"
        deadline = time.monotonic() + step.timeout_ms / 1000 if step.timeout_ms > 0 else None
        failures = 0
        try:
            while True:
                if not self.is_running or self._stop_event.is_set() or self._check_limits():
                    return False, None
                if self._cursor_in_failsafe_corner(None, None):
                    raise SafetyError("fail_safe", "detected", "Mouse moved to a screen corner")
                polled_at = time.monotonic()
                if self._should_pause_for_foreground():
                    found = None
                else:
                    try:
                        found = self._poll_wait_step(step)
                        failures = 0
                    except Exception as e:
                        failures += 1
                        if failures == 1:
                            _log.warning("Step %d screen read failed: %s", index, e, exc_info=True)
                        if failures >= _IMAGE_MAX_FAILURES:
                            self._set_stop_reason(STOP_ERROR, f"Could not read the screen: {e}")
                            return False, None
                        found = None
                    if found is not None:
                        return True, found
                    self.is_paused = True
                    self.pause_reason = (
                        f"the image in step {index}"
                        if what == "image"
                        else f"the pixel in step {index} to match"
                    )
                if deadline is not None and time.monotonic() >= deadline:
                    if step.on_timeout == "skip":
                        return True, None
                    seconds = f"{step.timeout_ms / 1000:g}"
                    verb = "didn't appear" if what == "image" else "didn't match"
                    self._set_stop_reason(
                        STOP_COMPLETED, f"Step {index}: the {what} {verb} within {seconds} s"
                    )
                    return False, None
                # A slow image search waits as long as it took (#161, #195).
                took = time.monotonic() - polled_at
                self._stop_event.wait(timeout=max(_STEP_WAIT_POLL_SECONDS, took))
        finally:
            self.is_paused = False

    def _poll_wait_step(self, step: ClickStep) -> tuple[int, int] | None:
        """One look at a wait step's target: where it is, or None if not there yet."""
        if step.type == "wait_image":
            assert step.image is not None
            return step.image.locate()
        assert step.x is not None and step.y is not None and step.rgb is not None
        rgb = tuple(pyautogui.pixel(step.x, step.y))[:3]
        matched = all(abs(int(a) - b) <= step.tolerance for a, b in zip(rgb, step.rgb, strict=True))
        return (step.x, step.y) if matched else None

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

            if self._runaway_tripped():
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
        *,
        action: str | None = None,
        key: str | None = None,
        hold_ms: float | None = None,
    ) -> None:
        """Perform one click, hold or key press, with performance monitoring.

        ``action``, ``key`` and ``hold_ms`` default to the run's; a sequence
        step passes its own (#119).
        """
        click_start_time = time.perf_counter()
        action = self._action if action is None else action
        key = self._key if key is None else key
        hold_ms = self._hold_ms if hold_ms is None else hold_ms

        try:
            if self._cursor_in_failsafe_corner(x, y):
                raise SafetyError("fail_safe", "detected", "Mouse moved to a screen corner")

            # Cursor mode (x and y are None): click wherever the cursor is.
            position: dict[str, int] = {}
            if x is not None and y is not None and action != "key":
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

                x, y = self._spread_point(x, y, bounds)
                # Pass the target on every click: the user may have moved the
                # mouse since the last one, and the click must not follow it.
                position = {"x": x, "y": y}
                self._last_click_pos = (x, y)

            if mouse_button not in ("left", "right", "middle"):
                raise ClickEngineError("perform_click", f"Unsupported mouse button: {mouse_button}")

            # One call for every button. A double click counts as one click toward
            # max_clicks, but as two presses for the runaway guard.
            presses = 2 if click_type == "double" and action == "click" else 1
            try:
                if action == "key":
                    keys = key.split("+")
                    if len(keys) == 1:
                        pyautogui.press(keys[0])
                    else:
                        pyautogui.hotkey(*keys)
                elif action == "hold":
                    self._hold(position, mouse_button, hold_ms)
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

    def _hold(self, position: dict[str, int], button: str, hold_ms: float) -> None:
        """Press ``button`` for ``hold_ms``; always release it, even when stopping."""
        pyautogui.mouseDown(**position, button=button)
        try:
            # Wait in short slices so a stop request or the corner failsafe ends
            # the hold early; the button is released either way.
            deadline = time.monotonic() + hold_ms / 1000
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

    def _spread_point(self, x: int, y: int, bounds: ScreenBounds) -> tuple[int, int]:
        """The target moved by up to ``_spread`` px, inside the image and on screen."""
        if self._spread <= 0:
            return x, y
        sx = sy = self._spread
        if self._image is not None:
            # (x, y) is the image's center: stay on the image.
            sx = min(sx, max(0, (self._image.ready.width - 1) // 2))
            sy = min(sy, max(0, (self._image.ready.height - 1) // 2))
        nx = min(max(x + random.randint(-sx, sx), bounds.left), bounds.right - 1)
        ny = min(max(y + random.randint(-sy, sy), bounds.top), bounds.bottom - 1)
        return nx, ny

    def _cursor_in_failsafe_corner(self, x: int | None, y: int | None) -> bool:
        """True if the user has moved the cursor into a failsafe corner of any monitor."""
        if not self.failsafe_enabled or not self._failsafe_corners:
            return False
        position = cursor_position()
        # Resting on a fixed target that happens to be a corner is not a request to
        # stop, nor resting where the last (spread) click put the cursor.
        if position is None or position in ((x, y), self._last_click_pos):
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

    def run_seconds(self) -> float:
        """Length of the current run, or of the last one once it has ended."""
        if self.start_time <= 0:
            return 0.0
        return max(0.0, (self.end_time or time.monotonic()) - self.start_time)

    def seconds_left(self) -> float | None:
        """Time until the run's earliest time limit (auto-stop or Stop at), or None.

        None when no run is going or no time limit is set (#173).
        """
        if not self.is_running or self.start_time <= 0:
            return None
        now = time.monotonic()
        deadlines = []
        if self._limits[1] > 0:
            deadlines.append(self.start_time + self._limits[1] * 60)
        if self._stop_at is not None:
            deadlines.append(self._stop_at[0])
        return max(0.0, min(deadlines) - now) if deadlines else None

    def get_status(self) -> dict[str, Any]:
        """Get current clicking status"""
        elapsed = int(self.run_seconds())
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60

        status: dict[str, Any] = {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "click_count": self.click_count,
            "runtime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "thread_alive": self.click_thread.is_alive() if self.click_thread else False,
            # Progress toward the run's limits (#173); 0 and None mean no limit.
            "max_clicks": self._limits[0],
            "seconds_left": self.seconds_left(),
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
