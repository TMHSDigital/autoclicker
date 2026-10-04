# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Main GUI window for the autoclicker application.
Handles user interface and event coordination.
"""

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, simpledialog, ttk

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
from ..core.click_engine import STOP_EMERGENCY, STOP_ERROR, STOP_SAFETY, RunOutcome
from ..core.exceptions import AutoclickerError, create_user_friendly_error
from ..core.resources import resource_path
from ..core.settings_manager import field_label
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

# Status-dot state for each way a run can end; anything else is "stopped".
_OUTCOME_STATE = {STOP_EMERGENCY: "error", STOP_SAFETY: "error", STOP_ERROR: "error"}


class AutoclickerApp:
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
            start=lambda: self._ui(self.start_clicking),
            stop=lambda: self._ui(self.stop_clicking),
            quit_app=lambda: self._ui(self.quit_application),
            on_error=lambda msg: self._ui(self._set_status_message, msg, "error"),
            start_label=lambda: "Start" + self._hotkey_suffix("start"),
            stop_label=lambda: "Stop" + self._hotkey_suffix("stop"),
        )
        self._refresh_hotkey_labels()
        self._tray_hint_shown = False
        self.root.bind("<Unmap>", self._on_unmap)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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
        self.root.option_add("*Font", ("Segoe UI", 10))

    def toggle_theme(self) -> None:
        """Switch between light and dark themes and persist the choice."""
        new_theme = "dark" if self.theme_var.get() == "light" else "light"
        self.theme_var.set(new_theme)
        sv_ttk.set_theme(new_theme)
        self.settings.set("theme", new_theme)
        if hasattr(self, "theme_button"):
            label = "\u2600 Light" if new_theme == "dark" else "\u263d Dark"
            self.theme_button.configure(text=label)

    def _fit_to_content(self) -> None:
        """Size the window to its content (Advanced collapsed) so nothing starts cut off.

        Capped at 90% of the screen height; the scrollbar covers anything taller.
        """
        try:
            self.root.update_idletasks()
            width = max(520, int(self.main_frame.winfo_reqwidth()))
            height = int(self.main_frame.winfo_reqheight())
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

        main_frame = ttk.Frame(self.canvas, padding="20")
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
        build_control_section(self, main_frame)
        build_status_section(self, main_frame)
        build_disclaimer_section(self, main_frame)

    def _on_mousewheel(self, event) -> None:
        """Scroll the canvas with the mouse wheel when content overflows."""
        bbox = self.canvas.bbox("all")
        if bbox and bbox[3] > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

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

    def _refresh_hotkey_labels(self) -> None:
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
        if self.click_engine.is_running:
            messagebox.showwarning("Hotkeys", "Stop clicking before changing hotkeys.")
            return
        self._hotkeys.set_suspended(True)
        HotkeysDialog(
            self.root,
            self._hotkeys.bindings,
            on_save=self._save_hotkeys,
            on_close=lambda: self._hotkeys.set_suspended(False),
        )

    def _save_hotkeys(self, bindings: dict[str, str]) -> None:
        self.settings.set("hotkeys", bindings)
        self._hotkeys.set_bindings(bindings)
        self._refresh_hotkey_labels()
        self._set_status_message("Hotkeys saved")

    def toggle_clicking(self) -> None:
        """Toggle hotkey: stop if running, otherwise start."""
        if self.click_engine.is_running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def _paint_stopped(self, message: str, state: str = "stopped") -> None:
        """Reset start/stop widgets after clicking ends."""
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
            confirmed = messagebox.askokcancel(
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

    def _apply_target_mode_state(self) -> None:
        """Enable X/Y and Pick Location only when targeting a fixed location."""
        fixed = self.target_mode_var.get() != "cursor"
        state = tk.NORMAL if fixed else tk.DISABLED
        for widget in (self.x_entry, self.y_entry, self.pick_btn):
            widget.configure(state=state)

    def _on_target_mode_change(self) -> None:
        """Apply and remember the chosen target mode."""
        self._apply_target_mode_state()
        self.settings.set("target_mode", self.target_mode_var.get())

    def start_coordinate_picker(self) -> None:
        """Start coordinate picking mode."""
        if self.click_engine.is_running:
            messagebox.showwarning("Warning", "Stop clicking before picking coordinates.")
            return

        if self.coordinate_picker.is_picking():
            return

        self._set_status_message("Click anywhere to pick a location...", "running")
        self.pick_btn.config(state=tk.DISABLED)

        # The overlay runs on the Tk thread, so its callbacks can touch widgets directly.
        started = self.coordinate_picker.start_picking(
            on_selected=self._on_coordinates_selected,
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

        self.show_window()
        self.pick_btn.config(state=tk.NORMAL)
        self._set_status_message("Coordinate selected", "alert")

    def _on_coordinate_picker_cancelled(self) -> None:
        """Handle coordinate picker cancellation."""
        self.show_window()
        self.pick_btn.config(state=tk.NORMAL)
        self._set_status_message("Coordinate selection cancelled", "alert")

    def save_preset(self) -> None:
        """Save current coordinates as preset."""
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())

            preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
            if preset_name and self.preset_manager.save_preset(preset_name, x, y):
                self.update_preset_list()
                messagebox.showinfo("Success", f"Preset '{preset_name}' saved!")
            elif preset_name:
                messagebox.showerror("Error", "Failed to save preset")

        except ValueError:
            messagebox.showerror("Error", "Invalid coordinates")

    def delete_preset(self) -> None:
        """Delete the selected coordinate preset."""
        preset_name = self.preset_var.get()
        if not preset_name:
            messagebox.showwarning("Delete Preset", "Select a preset to delete.")
            return
        if not messagebox.askokcancel("Delete Preset", f"Delete preset '{preset_name}'?"):
            return
        if self.preset_manager.delete_preset(preset_name):
            self.update_preset_list()
            self.preset_var.set("")
            self._set_status_message(f"Deleted preset '{preset_name}'")
        else:
            messagebox.showerror("Error", "Failed to delete preset")

    def load_preset(self, event=None) -> None:
        """Load selected preset."""
        preset_name = self.preset_var.get()
        coords = self.preset_manager.load_preset(preset_name)
        if coords:
            x, y = coords
            self.x_entry.delete(0, tk.END)
            self.x_entry.insert(0, str(x))
            self.y_entry.delete(0, tk.END)
            self.y_entry.insert(0, str(y))

    def update_preset_list(self) -> None:
        """Update preset combobox with current presets."""
        preset_names = self.preset_manager.get_preset_names()
        self.preset_combo["values"] = preset_names

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
                "max_cps_ceiling": self.settings.get("max_cps_ceiling", 50),
            }
        )

    def start_clicking(self) -> None:
        """Start the autoclicking process with comprehensive validation."""
        try:
            result = self.controller.validate_and_start_clicking(
                self._collect_ui_settings(),
                failsafe=self.failsafe_var.get(),
                pause_when_unfocused=self.pause_unfocused_var.get(),
                on_finished=lambda outcome: self._ui(self._on_run_finished, outcome),
            )

            if result.validation_errors is not None:
                error_messages = [
                    f"{field_label(field)}: {error}"
                    for field, error in result.validation_errors.items()
                ]
                messagebox.showerror("Validation Error", "\n".join(error_messages))
                return

            if result.busy:
                self._set_status_message("Still stopping the previous run. Try again.", "alert")
                return

            if result.success and result.sanitized is not None:
                sanitized = result.sanitized
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self._set_status_message("Running...", "running")
                self._shown_paused = False
                self._hotkeys.set_running(True)
                if sanitized.get("target_mode") == "cursor":
                    self.coord_var.set("Target: current cursor position")
                else:
                    self.coord_var.set(f"Target: ({sanitized['x_coord']}, {sanitized['y_coord']})")
                self._start_status_timer()

        except AutoclickerError as e:
            user_message = create_user_friendly_error(e)
            messagebox.showerror("Autoclicker Error", user_message)
        except Exception as e:
            user_message = create_user_friendly_error(e)
            messagebox.showerror("Unexpected Error", user_message)

    def stop_clicking(self) -> None:
        """Stop the autoclicking process."""
        self.controller.stop_clicking()
        self._paint_stopped("Stopped")

    def emergency_stop(self) -> None:
        """Emergency stop: immediate halt. Cancels the picker if it is active."""
        if self.coordinate_picker.is_picking():
            self.coordinate_picker.stop_picking(cancelled=True)
            return
        self.controller.emergency_stop()
        self._paint_stopped("Emergency stop", "error")

    def _on_run_finished(self, outcome: RunOutcome) -> None:
        """Paint the result of a finished run (exactly once per run)."""
        self.controller.finish_run()
        self._paint_stopped(outcome.message, _OUTCOME_STATE.get(outcome.reason, "stopped"))
        if outcome.reason == STOP_ERROR:
            messagebox.showerror("Clicking stopped", outcome.message)

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
        """Switch the status line between Running and Paused (pause when unfocused)."""
        if paused == getattr(self, "_shown_paused", False):
            return
        self._shown_paused = paused
        if paused:
            self._set_status_message(
                "Paused: waiting for the target window to be in front", "alert"
            )
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
        if messagebox.askokcancel("Quit", "Do you want to quit the application?"):
            self.quit_application()

    def quit_application(self) -> None:
        """Quit the application."""
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
