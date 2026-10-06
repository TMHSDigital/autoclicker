# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Main GUI window for the autoclicker application.
Handles user interface and event coordination.
"""

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

import sv_ttk

from ..app.controller import AutoclickerController
from ..app.hotkeys import (
    DEFAULT_HOTKEYS,
    HotkeyError,
    HotkeyManager,
    callbacks_for,
    validate_bindings,
)
from ..app.tray import create_tray_icon
from ..core.click_engine import (
    PAUSE_FOCUS,
    STOP_EMERGENCY,
    STOP_ERROR,
    STOP_SAFETY,
    RunOutcome,
)
from ..core.exceptions import AutoclickerError, create_user_friendly_error
from ..core.resources import resource_path
from ..core.settings_manager import allowed_actions, field_label, uses_point
from . import dialogs
from .features import (
    ConditionMixin,
    CountdownMixin,
    ImageMixin,
    InfoMixin,
    ProfilesMixin,
    RecordingMixin,
    SequenceMixin,
    UpdatesMixin,
)
from .hotkeys_dialog import HotkeysDialog
from .picker import CoordinatePicker
from .sections import (
    build_advanced_section,
    build_click_settings_section,
    build_control_section,
    build_coordinate_section,
    build_disclaimer_section,
    build_status_section,
    build_title_section,
)
from .sections.status import STATUS_COLORS
from .styles import apply_text_styles

# Status-dot state for each way a run can end; anything else is "stopped".
_OUTCOME_STATE = {STOP_EMERGENCY: "error", STOP_SAFETY: "error", STOP_ERROR: "error"}

# Widget classes locked while a run or countdown uses the settings (#102).
_LOCKABLE = frozenset(
    {"TEntry", "TButton", "TRadiobutton", "TCheckbutton", "TCombobox", "TSpinbox", "Listbox"}
)


def _descendants(widget):
    try:
        children = widget.winfo_children()
    except (AttributeError, tk.TclError):
        return
    for child in children:
        yield child
        yield from _descendants(child)


def _lock_widget(widget) -> bool:
    """Disable an enabled control; True if this call disabled it."""
    try:
        if widget.winfo_class() not in _LOCKABLE:
            return False
        if hasattr(widget, "instate"):  # ttk
            # Section headers and the small Import/Export/theme buttons stay usable.
            if str(widget.cget("style")) == "Toolbutton" or widget.instate(["disabled"]):
                return False
            widget.state(["disabled"])
            return True
        if str(widget.cget("state")) == tk.DISABLED:
            return False
        widget.configure(state=tk.DISABLED)
        return True
    except (AttributeError, TypeError, tk.TclError):
        return False


def _unlock_widget(widget) -> None:
    try:
        if hasattr(widget, "instate"):
            widget.state(["!disabled"])
        else:
            widget.configure(state=tk.NORMAL)
    except (AttributeError, TypeError, tk.TclError):
        pass


class AutoclickerApp(
    ImageMixin,
    SequenceMixin,
    RecordingMixin,
    ConditionMixin,
    ProfilesMixin,
    CountdownMixin,
    UpdatesMixin,
    InfoMixin,
):
    """Main autoclicker application class with modular design."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.controller = AutoclickerController()
        self.settings = self.controller.settings
        self.click_engine = self.controller.click_engine
        self.coordinate_picker = CoordinatePicker(self.root)
        self.preset_manager = self.controller.preset_manager
        self.controller.apply_safety_from_settings()

        self.setup_window()
        self.create_gui()
        self._fit_to_content()

        self._hotkeys = HotkeyManager(
            callbacks_for(
                start=lambda: self._ui(self.start_clicking),
                stop=lambda: self._ui(self.stop_clicking),
                emergency=lambda: self._ui(self.emergency_stop),
                toggle=lambda: self._ui(self.toggle_clicking),
            ),
            on_error=lambda msg: self._ui(self._set_status_message, msg, "error"),
        )
        self._hotkeys.start(self._saved_hotkeys())
        self.tray_icon = create_tray_icon(
            show_window=lambda: self._ui(self.show_window),
            start=lambda: self._ui(self.start_from_button),
            stop=lambda: self._ui(self.stop_clicking),
            quit_app=lambda: self._ui(self.quit_application),
            on_error=lambda msg: self._ui(self._set_status_message, msg, "error"),
            start_label=lambda: "Start" + self._hotkey_suffix("start"),
            stop_label=lambda: "Stop" + self._hotkey_suffix("stop"),
            show_info=lambda: self._ui(self._show_info_from_tray),
        )
        self._refresh_hotkey_labels()
        warning = getattr(self.settings, "load_warning", None)
        if warning:
            self._set_status_message(warning, "alert")
        self._tray_hint_shown = False
        self.root.bind("<Unmap>", self._on_unmap)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.after(1500, self._maybe_check_for_updates)

    def setup_window(self) -> None:
        """Configure main window properties."""
        self.root.title("Windows Autoclicker")
        self.root.geometry("520x560")
        self.root.resizable(True, True)
        self.root.minsize(460, 480)

        try:
            icon = resource_path("autoclicker.ico")
            if icon.is_file():
                self.root.iconbitmap(str(icon))
        except Exception:
            pass

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.center_window()

        theme = "dark" if str(self.settings.get("theme", "light")) == "dark" else "light"
        self.theme_var = tk.StringVar(value=theme)
        sv_ttk.set_theme(theme)
        apply_text_styles(theme, self.root)
        self.root.option_add("*Font", ("Segoe UI", 10))

    def toggle_theme(self) -> None:
        """Switch between light and dark themes and persist the choice."""
        new_theme = "dark" if self.theme_var.get() == "light" else "light"
        self.theme_var.set(new_theme)
        sv_ttk.set_theme(new_theme)
        apply_text_styles(new_theme, self.root)
        self.settings.set("theme", new_theme)
        if hasattr(self, "theme_button"):
            label = "\u2600 Light" if new_theme == "dark" else "\u263d Dark"
            self.theme_button.configure(text=label)

    def _fit_to_content(self) -> None:
        """Size the window to its content (sections collapsed) so nothing starts cut off.

        Capped at 90% of the screen height; the scrollbar covers anything taller.
        """
        try:
            self.root.update_idletasks()
            bottom = getattr(self, "bottom_frame", None)
            width = max(520, int(self.main_frame.winfo_reqwidth()))
            height = int(self.main_frame.winfo_reqheight())
            if bottom is not None:
                width = max(width, int(bottom.winfo_reqwidth()))
                height += int(bottom.winfo_reqheight())
            height = min(height, int(self.root.winfo_screenheight() * 0.9))
        except (TypeError, ValueError, AttributeError):
            return
        self.root.geometry(f"{width}x{height}")
        self.center_window()

    def center_window(self) -> None:
        """Center the window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def create_gui(self) -> None:
        """Create the main GUI interface."""
        self.canvas = tk.Canvas(self.root, highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.v_scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)

        main_frame = ttk.Frame(self.canvas, padding=(20, 20, 20, 0))
        self.main_frame = main_frame
        self.canvas_frame = self.canvas.create_window((0, 0), window=main_frame, anchor="nw")

        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        main_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        build_title_section(self, main_frame)
        build_coordinate_section(self, main_frame)
        build_click_settings_section(self, main_frame)
        build_advanced_section(self, main_frame)

        # Start/Stop, status and footer stay pinned below the scrolling settings,
        # so they are always visible however many sections are open (#85).
        bottom = ttk.Frame(self.root, padding=(20, 6, 20, 14))
        bottom.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)
        self.bottom_frame = bottom
        build_control_section(self, bottom)
        build_status_section(self, bottom)
        build_disclaimer_section(self, bottom)

    def _on_mousewheel(self, event) -> None:
        """Scroll the canvas with the mouse wheel when content overflows.

        Only for widgets in the main window that don't scroll themselves (#103):
        dialogs and lists keep their own wheel. Precision touchpads send deltas
        smaller than one notch; they add up instead of rounding to nothing.
        """
        widget = getattr(event, "widget", None)
        try:
            if widget is not None and (
                widget.winfo_toplevel() is not self.root
                or widget.winfo_class() in ("Listbox", "Text", "TCombobox")
            ):
                return
        except (AttributeError, tk.TclError):
            return
        bbox = self.canvas.bbox("all")
        if not (bbox and bbox[3] > self.canvas.winfo_height()):
            return
        self._wheel_delta = getattr(self, "_wheel_delta", 0) - event.delta
        steps = int(self._wheel_delta / 120)
        if steps:
            self._wheel_delta -= steps * 120
            self.canvas.yview_scroll(steps, "units")

    def _ui(self, fn: Callable, *args) -> None:
        """Marshal a callback onto the Tk main thread."""

        def _run() -> None:
            fn(*args)

        self.root.after(0, _run)

    def _saved_hotkeys(self) -> dict[str, str]:
        """Hotkeys from settings, falling back to the defaults if they are invalid."""
        saved = self.settings.get("hotkeys")
        try:
            return validate_bindings(dict(saved or {}))
        except (HotkeyError, TypeError, ValueError):
            return dict(DEFAULT_HOTKEYS)

    def _hotkey_suffix(self, action: str) -> str:
        """' (F6)' style suffix for labels; Start/Stop fall back to the toggle key."""
        bindings = self._hotkeys.bindings
        key = bindings.get(action) or (
            bindings.get("toggle") if action in ("start", "stop") else ""
        )
        return f" ({key})" if key else ""

    def _first_run_hint_text(self) -> str:
        """The ways to stop a run, with the user's own keys (#124)."""
        hotkeys = getattr(self, "_hotkeys", None)  # built after the window
        bindings = hotkeys.bindings if hotkeys is not None else self._saved_hotkeys()
        stop = bindings.get("stop") or bindings.get("toggle")
        ways = []
        if stop:
            ways.append(f"{stop} stops clicking")
        if bindings.get("emergency"):
            ways.append(f"{bindings['emergency']} is the emergency stop")
        failsafe = getattr(self, "failsafe_var", None)
        if failsafe.get() if failsafe is not None else self.settings.get("enable_failsafe", True):
            ways.append("pushing the mouse into any screen corner stops it too")
        if not ways:
            ways.append("use the Stop button (no stop keys are set)")
        return "Before you start: " + ", ".join(ways) + "."

    def dismiss_first_run_hint(self) -> None:
        """Got it: hide the hint for good, and record the update choice made there."""
        self.settings.set("first_run_hint_dismissed", True)
        hint = getattr(self, "first_run_hint", None)
        if hint is not None:
            hint.grid_remove()
        if self.settings.get("check_for_updates") is None:
            choice = bool(self.hint_updates_var.get())
            self.settings.set("check_for_updates", choice)
            if hasattr(self, "check_updates_var"):
                self.check_updates_var.set(choice)
            if choice:
                self._maybe_check_for_updates()

    def _refresh_hotkey_labels(self) -> None:
        if hasattr(self, "first_run_hint_var"):
            self.first_run_hint_var.set(self._first_run_hint_text())
        if hasattr(self, "start_btn"):
            self.start_btn.config(text="Start" + self._hotkey_suffix("start"))
            self.stop_btn.config(text="Stop" + self._hotkey_suffix("stop"))
            self.emergency_btn.config(text="Emergency stop" + self._hotkey_suffix("emergency"))
        tray = getattr(self, "tray_icon", None)
        if tray is not None:
            try:
                tray.update_menu()
            except Exception:
                pass

    def open_hotkeys_dialog(self) -> None:
        """Rebind hotkeys; global keys are released while the dialog is open."""
        # A run must never start while its stop keys are released (#93).
        if (
            self.click_engine.is_running
            or self._countdown_job is not None
            or self._recorder is not None
            or self.coordinate_picker.is_picking()
        ):
            dialogs.messagebox.showwarning("Hotkeys", "Stop clicking before changing hotkeys.")
            return
        self._hotkeys_dialog_open = True
        self._hotkeys.set_suspended(True)
        HotkeysDialog(
            self.root,
            self._hotkeys.bindings,
            on_save=self._save_hotkeys,
            on_close=self._on_hotkeys_dialog_closed,
        )

    def _on_hotkeys_dialog_closed(self) -> None:
        self._hotkeys_dialog_open = False
        self._hotkeys.set_suspended(False)

    def _start_blocked_reason(self) -> str | None:
        """Why a run cannot start right now, or None if it can."""
        if self._recorder is not None:
            return "Finish recording before starting"
        if self.coordinate_picker.is_picking():
            return "Finish picking before starting"
        if self._hotkeys_dialog_open:
            return "Close the Hotkeys dialog before starting"
        return None

    def _save_hotkeys(self, bindings: dict[str, str]) -> None:
        self.settings.set("hotkeys", bindings)
        self._hotkeys.set_bindings(bindings)
        self._refresh_hotkey_labels()
        self._set_status_message("Hotkeys saved")

    def toggle_clicking(self) -> None:
        """Toggle hotkey: stop if running (or counting down), otherwise start."""
        if self._finish_recording() or self._cancel_countdown():
            return
        if self.click_engine.is_running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def _set_settings_locked(self, locked: bool) -> None:
        """Disable the settings while a run or countdown uses them (#102).

        Changes would not reach the running engine, so the form would stop
        describing the run. Only controls this disabled are re-enabled, so
        fields that are off for the current mode stay off.
        """
        if not locked:
            widgets, self._locked_widgets = self._locked_widgets, ()
            for widget in widgets:
                _unlock_widget(widget)
            return
        frame = getattr(self, "main_frame", None)
        if self._locked_widgets or frame is None:
            return
        self._locked_widgets = tuple(w for w in _descendants(frame) if _lock_widget(w))

    def _paint_stopped(self, message: str, state: str = "stopped") -> None:
        """Reset start/stop widgets after clicking ends."""
        self._set_settings_locked(False)
        if hasattr(self, "_hotkeys"):
            self._hotkeys.set_running(False)
        if hasattr(self, "start_btn"):
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
        self._set_status_message(message, state)
        self._stop_status_timer()
        # Final refresh so the counters show the exact totals, not the last 1 s tick
        if hasattr(self, "click_count_var"):
            self._on_status_update()

    def _set_status_message(self, message: str, state: str = "stopped") -> None:
        """Show a status line and color the dot for ``state``.

        ``state`` is one of ``running``, ``stopped``, ``alert`` or ``error``.
        """
        if hasattr(self, "status_var"):
            self.status_var.set(message)
        self._set_tray_title(message)
        dot = getattr(self, "status_dot", None)
        if dot is not None:
            dot.configure(foreground=STATUS_COLORS.get(state, STATUS_COLORS["stopped"]))

    def _on_failsafe_toggle(self) -> None:
        if not self.failsafe_var.get():
            confirmed = dialogs.messagebox.askokcancel(
                "Disable failsafe",
                "Moving the mouse to a screen corner will no longer abort clicking. Continue?",
            )
            if not confirmed:
                self.failsafe_var.set(True)
                return
        self._sync_safety_from_ui()

    def _sync_safety_from_ui(self) -> None:
        self.controller.configure_safety_from_ui(
            failsafe=self.failsafe_var.get(),
            pause_when_unfocused=self.pause_unfocused_var.get(),
        )
        if hasattr(self, "first_run_hint_var"):
            self.first_run_hint_var.set(self._first_run_hint_text())  # corner on or off

    def _apply_target_mode_state(self) -> None:
        """Enable only what the target mode and action use (#102).

        X/Y and Pick Location for a point that is clicked, the Action choices
        the mode can run, and the steps or image panel for those modes.
        """
        mode = self.target_mode_var.get()
        action_var = getattr(self, "action_var", None)
        allowed = allowed_actions(mode)
        for value, radio in getattr(self, "action_radios", {}).items():
            radio.configure(state=tk.NORMAL if value in allowed else tk.DISABLED)
        action = action_var.get() if action_var is not None else "click"
        state = tk.NORMAL if uses_point(mode, action) else tk.DISABLED
        for widget in (self.x_entry, self.y_entry, self.pick_btn):
            widget.configure(state=state)
        for frame, shown in (
            (getattr(self, "sequence_frame", None), mode == "sequence"),
            (getattr(self, "image_frame", None), mode == "image"),
        ):
            if frame is not None:
                if shown:
                    frame.grid()
                else:
                    frame.grid_remove()
        if hasattr(self, "sequence_frame"):
            self._refresh_target_summary()

    def _target_summary(self) -> str:
        """Status-bar description of what the form currently targets."""
        mode = self.target_mode_var.get()
        if mode != "sequence" and getattr(self, "action_var", None) is not None:
            if self.action_var.get() == "key":
                key = self.key_entry.get().strip() or "?"
                return f"Target: the focused window (press {key})"
        if mode == "cursor":
            return "Target: current cursor position"
        if mode == "image":
            return "Target: wherever the captured image appears"
        if mode == "sequence":
            count = len(self.sequence_steps)
            return f"Target: sequence of {count} point{'s' * (count != 1)}"
        return f"Target: ({self.x_entry.get().strip()}, {self.y_entry.get().strip()})"

    def _refresh_target_summary(self) -> None:
        if hasattr(self, "coord_var"):
            self.coord_var.set(self._target_summary())

    def _apply_action_state(self) -> None:
        """Enable the hold time only for Hold and the key only for Key."""
        self._apply_entry_states()
        if hasattr(self, "target_mode_var"):
            self._apply_target_mode_state()  # Key has no point to click
        self._refresh_target_summary()

    def _apply_entry_states(self) -> None:
        action = self.action_var.get()
        self.hold_entry.configure(state=tk.NORMAL if action == "hold" else tk.DISABLED)
        self.key_entry.configure(state=tk.NORMAL if action == "key" else tk.DISABLED)

    def _on_target_mode_change(self) -> None:
        """Apply and remember the chosen target mode."""
        if self.action_var.get() not in allowed_actions(self.target_mode_var.get()):
            # Picked a mode that can't run the current action: fall back to Click.
            # (Profiles and flags keep theirs, so Start can say what's wrong.)
            self.action_var.set("click")
            self._apply_entry_states()
        self._apply_target_mode_state()
        self.settings.set("target_mode", self.target_mode_var.get())

    def start_coordinate_picker(
        self, on_selected: Callable[[int, int], None] | None = None
    ) -> None:
        """Start coordinate picking mode (fills X/Y unless ``on_selected`` is given)."""
        if self.click_engine.is_running:
            dialogs.messagebox.showwarning("Warning", "Stop clicking before picking coordinates.")
            return

        if self.coordinate_picker.is_picking() or self._countdown_job is not None:
            return

        self._set_status_message("Click anywhere to pick a location...", "running")
        self.pick_btn.config(state=tk.DISABLED)

        # The overlay runs on the Tk thread, so its callbacks can touch widgets directly.
        started = self.coordinate_picker.start_picking(
            on_selected=on_selected or self._on_coordinates_selected,
            on_cancelled=self._on_coordinate_picker_cancelled,
        )
        if not started:
            self.pick_btn.config(state=tk.NORMAL)
            self._set_status_message("Could not start coordinate picker", "error")
            return

        self.root.withdraw()

    def _on_coordinates_selected(self, x: int, y: int) -> None:
        """Handle coordinate selection."""
        self.x_entry.delete(0, tk.END)
        self.x_entry.insert(0, str(x))
        self.y_entry.delete(0, tk.END)
        self.y_entry.insert(0, str(y))

        self._refresh_target_summary()
        self.show_window()
        self._apply_target_mode_state()
        self._set_status_message("Coordinate selected", "alert")

    def _on_coordinate_picker_cancelled(self) -> None:
        """Handle coordinate picker cancellation."""
        self.show_window()
        self._apply_target_mode_state()
        self._set_status_message("Coordinate selection cancelled", "alert")

    def _collect_ui_settings(self) -> dict:
        """Collect current values from UI fields."""
        return AutoclickerController.collect_raw_settings(
            {
                "target_mode": self.target_mode_var.get(),
                "x_coord": self.x_entry.get(),
                "y_coord": self.y_entry.get(),
                "interval": self.interval_entry.get(),
                "interval_unit": self.interval_unit_var.get(),
                "variation": self.variation_entry.get(),
                "mouse_button": self.button_var.get(),
                "click_type": self.click_type_var.get(),
                "burst_clicks": self.burst_clicks_entry.get(),
                "burst_pause": self.burst_pause_entry.get(),
                "max_clicks": (self.max_clicks_entry.get() if self.limit_clicks_var.get() else "0"),
                "auto_stop_minutes": self.auto_stop_entry.get(),
                "enable_failsafe": self.failsafe_var.get(),
                "pause_when_unfocused": self.pause_unfocused_var.get(),
                "max_cps_ceiling": self.max_cps_entry.get(),
                "start_delay_seconds": self.start_delay_entry.get(),
                "sequence": [dict(step) for step in self.sequence_steps],
                "sequence_repeat": self.sequence_repeat_entry.get(),
                "image_path": self.image_path,
                "image_region": list(self.image_region),
                "image_margin": self.image_margin_entry.get(),
                "image_tolerance": self.image_tolerance_entry.get(),
                "action": self.action_var.get(),
                "hold_ms": self.hold_entry.get(),
                "key": self.key_entry.get(),
                "condition": self.condition_var.get(),
                "condition_x": self.condition_point[0],
                "condition_y": self.condition_point[1],
                "condition_color": self.condition_point[2],
                "condition_tolerance": self.condition_tolerance_entry.get(),
            }
        )

    def _confirm_guard_off(self) -> bool:
        """Ask before the first run with the runaway guard turned off."""
        try:
            requested = float(self.max_cps_entry.get().strip())
            saved = float(self.settings.get("max_cps_ceiling", 50))
        except (TypeError, ValueError, AttributeError):
            return True  # validation reports bad input
        if requested != 0 or saved == 0:
            return True
        return bool(
            dialogs.messagebox.askokcancel(
                "Turn off speed limit",
                "With the speed limit at 0, nothing stops a run that clicks faster than "
                "intended. Continue?",
            )
        )

    def _show_validation_errors(self, errors: dict[str, str]) -> None:
        dialogs.messagebox.showerror(
            "Validation Error",
            "\n".join(f"{field_label(field)}: {error}" for field, error in errors.items()),
        )

    def start_clicking(self, confirmed: bool = False) -> None:
        """Start the autoclicking process with comprehensive validation.

        ``confirmed`` skips the speed-limit-off question when the countdown
        already asked it.
        """
        blocked = self._start_blocked_reason()
        if blocked:
            self._set_status_message(blocked, "alert")
            return
        # A Start hotkey during a countdown starts right away.
        self._cancel_countdown(message=None)
        if not confirmed and not self._confirm_guard_off():
            return
        try:
            result = self.controller.validate_and_start_clicking(
                self._collect_ui_settings(),
                failsafe=self.failsafe_var.get(),
                pause_when_unfocused=self.pause_unfocused_var.get(),
                on_finished=lambda outcome: self._ui(self._on_run_finished, outcome),
            )

            if result.validation_errors is not None:
                self._show_validation_errors(result.validation_errors)
                return

            if result.busy:
                self._set_status_message("Still stopping the previous run. Try again.", "alert")
                return

            if result.success:
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self._set_status_message("Running...", "running")
                self._shown_paused = None
                self._hotkeys.set_running(True)
                self._set_settings_locked(True)
                self._refresh_target_summary()
                self._start_status_timer()

        except AutoclickerError as e:
            user_message = create_user_friendly_error(e)
            dialogs.messagebox.showerror("Autoclicker Error", user_message)
        except Exception as e:
            user_message = create_user_friendly_error(e)
            dialogs.messagebox.showerror("Unexpected Error", user_message)

    def stop_clicking(self) -> None:
        """Stop the autoclicking process (or cancel a countdown, or finish recording)."""
        if self._finish_recording() or self._cancel_countdown():
            return
        self.controller.stop_clicking()
        self._paint_stopped("Stopped")

    def emergency_stop(self) -> None:
        """Emergency stop: immediate halt. Cancels the picker if it is active."""
        if self.coordinate_picker.is_picking():
            self.coordinate_picker.stop_picking(cancelled=True)
            if not self.click_engine.is_running:
                return
        if self._finish_recording() or self._cancel_countdown():
            return
        if not self.click_engine.is_running:
            return  # nothing to stop; don't paint a red error (#103)
        self.controller.emergency_stop()
        self._paint_stopped("Emergency stop", "error")

    def _on_run_finished(self, outcome: RunOutcome) -> None:
        """Paint the result of a finished run (exactly once per run)."""
        self.controller.finish_run()
        self._paint_stopped(outcome.message, _OUTCOME_STATE.get(outcome.reason, "stopped"))
        if outcome.reason == STOP_ERROR:
            dialogs.messagebox.showerror("Clicking stopped", outcome.message)

    def _on_status_update(self) -> None:
        """Handle status updates from click engine."""
        status = self.click_engine.get_status()
        self.click_count_var.set(f"Clicks: {status['click_count']}")
        self.runtime_var.set(f"Runtime: {status['runtime']}")
        if status.get("is_running"):
            state = "paused" if status.get("is_paused") else "running"
            self._set_tray_title(f"{state}, {status['click_count']:,} clicks")

        if "performance" in status:
            perf = status["performance"]
            perf_text = (
                f"Performance: {perf['clicks_per_second']} cps, {perf['success_rate']:.1f}% success"
            )
            self.performance_var.set(perf_text)
        else:
            self.performance_var.set("Performance: --")

    def _start_status_timer(self) -> None:
        """Start periodic status updates."""
        self._status_timer = self.root.after(1000, self._update_status_loop)

    def _stop_status_timer(self) -> None:
        """Stop status update timer."""
        if hasattr(self, "_status_timer"):
            self.root.after_cancel(self._status_timer)

    def _update_status_loop(self) -> None:
        """Periodic status update loop."""
        if self.click_engine.is_running:
            self._on_status_update()
            self._show_pause_state(bool(getattr(self.click_engine, "is_paused", False)))
            self._status_timer = self.root.after(1000, self._update_status_loop)

    def _show_pause_state(self, paused: bool) -> None:
        """Switch the status line between Running and Paused (focus or pixel condition)."""
        reason = str(getattr(self.click_engine, "pause_reason", "") or PAUSE_FOCUS)
        # What the status line shows: the pause reason, or a falsy value while running.
        shown = reason if paused else None
        if shown == (getattr(self, "_shown_paused", None) or None):
            return
        self._shown_paused = shown
        if paused:
            self._set_status_message(f"Paused: waiting for {reason}", "alert")
        else:
            self._set_status_message("Running...", "running")

    def _set_tray_title(self, text: str) -> None:
        """Mirror the current state in the tray icon's tooltip."""
        tray = getattr(self, "tray_icon", None)
        if tray is None:
            return
        try:
            tray.title = f"Windows Autoclicker: {text}"[:127]  # Win32 tooltip limit
        except Exception:
            pass

    def _on_unmap(self, event) -> None:
        """Minimizing hides the window to the tray when that option is on."""
        if event.widget is not self.root or self.tray_icon is None:
            return
        if not self.minimize_to_tray_var.get() or self.root.state() != "iconic":
            return
        self.root.withdraw()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            try:
                self.tray_icon.notify(
                    "Still running in the tray. Double-click the icon to restore it.",
                    "Windows Autoclicker",
                )
            except Exception:
                pass

    def _on_minimize_to_tray_toggle(self) -> None:
        self.settings.set("minimize_to_tray", bool(self.minimize_to_tray_var.get()))

    def hide_to_tray(self) -> None:
        """Hide the window (to the tray icon if there is one, else minimize it)."""
        if self.tray_icon is not None:
            self.root.withdraw()
        else:
            self.root.iconify()

    def show_window(self) -> None:
        """Show main window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_frame_configure(self, event) -> None:
        """Handle frame resize."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_scrollbar_visibility()

    def on_canvas_configure(self, event) -> None:
        """Handle canvas resize."""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
        self._update_scrollbar_visibility()

    def _update_scrollbar_visibility(self) -> None:
        """Show the vertical scrollbar only when content overflows."""
        if not hasattr(self, "v_scrollbar"):
            return
        bbox = self.canvas.bbox("all")
        if bbox and bbox[3] > self.canvas.winfo_height():
            self.v_scrollbar.grid()
        else:
            self.v_scrollbar.grid_remove()

    def on_closing(self) -> None:
        """Handle window close event."""
        if dialogs.messagebox.askokcancel("Quit", "Do you want to quit the application?"):
            self.quit_application()

    def quit_application(self) -> None:
        """Quit the application."""
        if self._recorder is not None:
            self._recorder.stop()
            self._recorder = None
        self.stop_clicking()
        self.coordinate_picker.stop_picking(cancelled=False)
        if hasattr(self, "_hotkeys") and self._hotkeys:
            self._hotkeys.unregister()
        self.controller.persist_settings_on_quit(
            self._collect_ui_settings(),
            settings_manager=self.settings,
        )

        if hasattr(self, "tray_icon") and self.tray_icon:
            self.tray_icon.stop()

        self.root.quit()
        self.root.destroy()

    def run(self) -> None:
        """Run the application."""
        try:
            if hasattr(self, "tray_icon") and self.tray_icon:
                tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
                tray_thread.start()

            self.root.mainloop()

        except KeyboardInterrupt:
            self.quit_application()
