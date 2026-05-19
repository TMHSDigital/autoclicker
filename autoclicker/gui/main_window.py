# SPDX-License-Identifier: CC-BY-NC-4.0
"""
Main GUI window for the autoclicker application.
Handles user interface and event coordination.
"""

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import pyautogui

from ..app.controller import AutoclickerController
from ..app.hotkeys import setup_hotkeys
from ..app.tray import create_tray_icon
from ..core.exceptions import AutoclickerError, create_user_friendly_error
from .sections import (
    build_click_settings_section,
    build_control_section,
    build_coordinate_section,
    build_disclaimer_section,
    build_status_section,
    build_title_section,
)


class AutoclickerApp:
    """Main autoclicker application class with modular design."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.controller = AutoclickerController()
        self.settings = self.controller.settings
        self.click_engine = self.controller.click_engine
        self.coordinate_picker = self.controller.coordinate_picker
        self.preset_manager = self.controller.preset_manager
        self.controller.apply_safety_from_settings(on_safety_stop=self._on_safety_stop)

        self.setup_window()
        self.create_gui()

        setup_hotkeys(
            start=self.start_clicking,
            stop=self.stop_clicking,
            emergency=self.emergency_stop,
            on_error=self._set_status_message,
        )
        self.tray_icon = create_tray_icon(
            show_window=self.show_window,
            start=self.start_clicking,
            stop=self.stop_clicking,
            quit_app=self.quit_application,
            on_error=self._set_status_message,
        )

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.controller.coordinate_picker.on_coordinate_selected = self._on_coordinates_selected

    def setup_window(self) -> None:
        """Configure main window properties."""
        self.root.title("Windows Autoclicker")
        self.root.geometry("550x700")
        self.root.resizable(True, True)
        self.root.minsize(450, 600)

        try:
            self.root.iconbitmap("autoclicker.ico")
        except Exception:
            pass

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.center_window()

        style = ttk.Style()
        style.theme_use(
            "vista"
            if hasattr(style, "theme_names") and "vista" in style.theme_names()
            else "default"
        )

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
        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        v_scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        h_scrollbar = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        main_frame = ttk.Frame(self.canvas, padding="20")
        self.canvas_frame = self.canvas.create_window((0, 0), window=main_frame, anchor="nw")

        main_frame.grid_rowconfigure(5, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        main_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        build_title_section(self, main_frame)
        build_coordinate_section(self, main_frame)
        build_click_settings_section(self, main_frame)
        build_control_section(self, main_frame)
        build_status_section(self, main_frame)
        build_disclaimer_section(self, main_frame)

    def _set_status_message(self, message: str) -> None:
        """Show a status line in the GUI."""
        if hasattr(self, "status_var"):
            self.status_var.set(message)

    def _on_failsafe_toggle(self) -> None:
        self.controller.configure_safety_from_ui(
            failsafe=self.failsafe_var.get(),
            pause_when_unfocused=self.pause_unfocused_var.get(),
            on_safety_stop=self._on_safety_stop,
        )

    def _on_safety_stop(self, reason: str) -> None:
        self._set_status_message(reason)
        self.controller.log_safety_stop(reason)
        self.stop_clicking()

    def start_coordinate_picker(self) -> None:
        """Start coordinate picking mode."""
        if self.click_engine.is_running:
            messagebox.showwarning("Warning", "Stop clicking before picking coordinates.")
            return

        if self.coordinate_picker.is_picking():
            return

        self.status_var.set("Click anywhere to select coordinates...")
        self.pick_btn.config(state=tk.DISABLED)
        self.root.withdraw()

        self.coordinate_picker.start_picking(
            on_selected=self._on_coordinates_selected,
            on_cancelled=self._on_coordinate_picker_cancelled,
        )

    def _on_coordinates_selected(self, x: int, y: int) -> None:
        """Handle coordinate selection."""
        self.x_entry.delete(0, tk.END)
        self.x_entry.insert(0, str(x))
        self.y_entry.delete(0, tk.END)
        self.y_entry.insert(0, str(y))

        self.show_window()
        self.pick_btn.config(state=tk.NORMAL)
        self.status_var.set("Coordinate selected")

    def _on_coordinate_picker_cancelled(self) -> None:
        """Handle coordinate picker cancellation."""
        self.show_window()
        self.pick_btn.config(state=tk.NORMAL)
        self.status_var.set("Coordinate selection cancelled")

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
                "x_coord": self.x_entry.get(),
                "y_coord": self.y_entry.get(),
                "interval": self.interval_entry.get(),
                "interval_unit": self.interval_unit_var.get(),
                "variation": self.variation_entry.get(),
                "mouse_button": self.button_var.get(),
                "click_type": self.click_type_var.get(),
                "burst_clicks": self.burst_clicks_entry.get(),
                "burst_pause": self.burst_pause_entry.get(),
                "max_clicks": self.max_clicks_entry.get(),
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
                on_safety_stop=self._on_safety_stop,
                on_click_complete=self._on_clicking_complete,
                on_status_update=self._on_status_update,
            )

            if result.validation_errors is not None:
                error_messages = [
                    f"{field.title()}: {error}" for field, error in result.validation_errors.items()
                ]
                messagebox.showerror("Validation Error", "\n".join(error_messages))
                return

            if result.success and result.sanitized is not None:
                sanitized = result.sanitized
                x = sanitized["x_coord"]
                y = sanitized["y_coord"]
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self.status_var.set("Running...")
                self.coord_var.set(f"Target: ({x}, {y})")
                self._start_status_timer()

        except AutoclickerError as e:
            user_message = create_user_friendly_error(e)
            messagebox.showerror("Autoclicker Error", user_message)
        except Exception as e:
            user_message = create_user_friendly_error(e)
            messagebox.showerror("Unexpected Error", user_message)

    def stop_clicking(self) -> None:
        """Stop the autoclicking process."""
        self.controller.stop_clicking(reason="user_stop")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Stopped")
        self._stop_status_timer()

    def emergency_stop(self) -> None:
        """Emergency stop - immediate halt."""
        self.controller.emergency_stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Emergency Stop")
        self._stop_status_timer()

    def _on_clicking_complete(self) -> None:
        """Handle clicking completion."""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Stopped")
        self._stop_status_timer()

    def _on_status_update(self) -> None:
        """Handle status updates from click engine."""
        status = self.click_engine.get_status()
        self.click_count_var.set(f"Clicks: {status['click_count']}")
        self.runtime_var.set(f"Runtime: {status['runtime']}")

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
            self._status_timer = self.root.after(1000, self._update_status_loop)

    def _toggle_click_queuing(self) -> None:
        """Toggle click queuing on/off."""
        enabled = self.click_queuing_var.get()
        self.click_engine.enable_click_queuing(enabled)

    def show_window(self) -> None:
        """Show main window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_frame_configure(self, event) -> None:
        """Handle frame resize."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event) -> None:
        """Handle canvas resize."""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def on_closing(self) -> None:
        """Handle window close event."""
        if messagebox.askokcancel("Quit", "Do you want to quit the application?"):
            self.quit_application()

    def quit_application(self) -> None:
        """Quit the application."""
        self.stop_clicking()
        self.coordinate_picker.stop_picking()
        raw_settings = self._collect_ui_settings()
        screen_size = pyautogui.size()
        if hasattr(self, "controller"):
            self.controller.persist_settings_on_quit(
                raw_settings,
                settings_manager=self.settings,
                screen_size=screen_size,
            )
        else:
            screen_width, screen_height = screen_size
            validation_result = self.settings.validate_all_settings(
                raw_settings, screen_width, screen_height
            )
            if validation_result["valid"]:
                self.settings.update(validation_result["sanitized_settings"])
            else:
                self.settings.update(raw_settings)

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
