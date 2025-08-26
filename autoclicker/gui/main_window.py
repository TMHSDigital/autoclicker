"""
Main GUI window for the autoclicker application
Handles user interface and event coordination
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import time
import keyboard
import pystray
from PIL import Image
import win32api
import pyautogui
from typing import Optional, Callable

from ..core.settings_manager import SettingsManager
from ..core.click_engine import ClickEngine
from ..core.exceptions import AutoclickerError, create_user_friendly_error
from ..utils.coordinate_picker import CoordinatePicker, PresetManager


class AutoclickerApp:
    """Main autoclicker application class with modular design"""

    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()

        # Core components
        self.settings = SettingsManager()
        self.click_engine = ClickEngine()
        self.coordinate_picker = CoordinatePicker()
        self.preset_manager = PresetManager(self.settings)

        # GUI components
        self.create_gui()

        # Setup system integration
        self.setup_hotkeys()
        self.setup_system_tray()

        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Coordinate picker callback
        self.coordinate_picker.on_coordinate_selected = self._on_coordinates_selected

    def setup_window(self):
        """Configure main window properties"""
        self.root.title("Windows Autoclicker")
        self.root.geometry("550x700")
        self.root.resizable(True, True)
        self.root.minsize(450, 600)

        # Set window icon if available
        try:
            self.root.iconbitmap("autoclicker.ico")
        except:
            pass

        # Configure root grid
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Center window
        self.center_window()

        # Set theme
        style = ttk.Style()
        style.theme_use('vista' if hasattr(style, 'theme_names') and 'vista' in style.theme_names() else 'default')

    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_gui(self):
        """Create the main GUI interface"""
        # Create scrollable canvas
        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        h_scrollbar = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Create main frame
        main_frame = ttk.Frame(self.canvas, padding="20")
        self.canvas_frame = self.canvas.create_window((0, 0), window=main_frame, anchor="nw")

        # Configure grid weights
        main_frame.grid_rowconfigure(5, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        # Bind resize events
        main_frame.bind('<Configure>', self.on_frame_configure)
        self.canvas.bind('<Configure>', self.on_canvas_configure)

        # Create sections
        self.create_title_section(main_frame)
        self.create_coordinate_section(main_frame)
        self.create_click_settings_section(main_frame)
        self.create_control_section(main_frame)
        self.create_status_section(main_frame)
        self.create_disclaimer_section(main_frame)

    def create_title_section(self, parent):
        """Create title section"""
        title_label = ttk.Label(parent, text="Windows Autoclicker",
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))

    def create_coordinate_section(self, parent):
        """Create coordinate input section"""
        coord_frame = ttk.LabelFrame(parent, text="Target Coordinates", padding="10")
        coord_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        coord_frame.grid_columnconfigure(1, weight=1)
        coord_frame.grid_columnconfigure(3, weight=1)
        coord_frame.grid_columnconfigure(6, weight=1)

        # X and Y coordinates
        ttk.Label(coord_frame, text="X:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        self.x_entry = ttk.Entry(coord_frame, width=8)
        self.x_entry.grid(row=0, column=1, padx=(0, 15), sticky=(tk.W, tk.E))
        self.x_entry.insert(0, str(self.settings.get('x_coord', '100')))

        ttk.Label(coord_frame, text="Y:").grid(row=0, column=2, padx=(0, 5), sticky=tk.W)
        self.y_entry = ttk.Entry(coord_frame, width=8)
        self.y_entry.grid(row=0, column=3, padx=(0, 15), sticky=(tk.W, tk.E))
        self.y_entry.insert(0, str(self.settings.get('y_coord', '100')))

        # Pick coordinate button
        self.pick_btn = ttk.Button(coord_frame, text="Pick Location",
                                  command=self.start_coordinate_picker)
        self.pick_btn.grid(row=0, column=4, padx=(10, 5), sticky=tk.W)

        # Presets section
        ttk.Label(coord_frame, text="Presets:").grid(row=1, column=0, padx=(0, 5), pady=(10, 0), sticky=tk.W)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(coord_frame, textvariable=self.preset_var,
                                        width=20, state="readonly")
        self.preset_combo.grid(row=1, column=1, columnspan=3, padx=(0, 10), pady=(10, 0), sticky=(tk.W, tk.E))
        self.update_preset_list()
        self.preset_combo.bind('<<ComboboxSelected>>', self.load_preset)

        # Save preset button
        self.save_preset_btn = ttk.Button(coord_frame, text="Save Preset",
                                         command=self.save_preset)
        self.save_preset_btn.grid(row=1, column=4, pady=(10, 0), sticky=tk.W)

    def create_click_settings_section(self, parent):
        """Create click settings section"""
        settings_frame = ttk.LabelFrame(parent, text="Click Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        settings_frame.grid_columnconfigure(1, weight=1)
        settings_frame.grid_columnconfigure(2, weight=1)
        settings_frame.grid_columnconfigure(3, weight=1)

        # Mouse button selection
        ttk.Label(settings_frame, text="Mouse Button:").grid(row=0, column=0, sticky=tk.W)
        self.button_var = tk.StringVar(value=self.settings.get('mouse_button', 'left'))
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0))

        ttk.Radiobutton(button_frame, text="Left", variable=self.button_var, value="left").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(button_frame, text="Right", variable=self.button_var, value="right").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(button_frame, text="Middle", variable=self.button_var, value="middle").pack(side=tk.LEFT)

        # Click type
        ttk.Label(settings_frame, text="Click Type:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.click_type_var = tk.StringVar(value=self.settings.get('click_type', 'single'))
        click_type_frame = ttk.Frame(settings_frame)
        click_type_frame.grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

        ttk.Radiobutton(click_type_frame, text="Single", variable=self.click_type_var, value="single").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(click_type_frame, text="Double", variable=self.click_type_var, value="double").pack(side=tk.LEFT)

        # Interval settings
        ttk.Label(settings_frame, text="Interval:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        interval_frame = ttk.Frame(settings_frame)
        interval_frame.grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

        self.interval_entry = ttk.Entry(interval_frame, width=8)
        self.interval_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.interval_entry.insert(0, str(self.settings.get('interval', '1000')))

        self.interval_unit_var = tk.StringVar(value=self.settings.get('interval_unit', 'ms'))
        ttk.Combobox(interval_frame, textvariable=self.interval_unit_var,
                    values=['ms', 'seconds'], width=8, state="readonly").pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(interval_frame, text="±").pack(side=tk.LEFT)
        self.variation_entry = ttk.Entry(interval_frame, width=6)
        self.variation_entry.pack(side=tk.LEFT)
        self.variation_entry.insert(0, str(self.settings.get('variation', '0')))
        ttk.Label(interval_frame, text="ms").pack(side=tk.LEFT)

        # Burst mode
        ttk.Label(settings_frame, text="Burst Mode:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        burst_frame = ttk.Frame(settings_frame)
        burst_frame.grid(row=3, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

        ttk.Label(burst_frame, text="Clicks:").pack(side=tk.LEFT)
        self.burst_clicks_entry = ttk.Entry(burst_frame, width=5)
        self.burst_clicks_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.burst_clicks_entry.insert(0, str(self.settings.get('burst_clicks', '1')))

        ttk.Label(burst_frame, text="Pause:").pack(side=tk.LEFT, padx=(10, 0))
        self.burst_pause_entry = ttk.Entry(burst_frame, width=5)
        self.burst_pause_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.burst_pause_entry.insert(0, str(self.settings.get('burst_pause', '1000')))
        ttk.Label(burst_frame, text="ms").pack(side=tk.LEFT)

        # Safety settings
        ttk.Label(settings_frame, text="Safety:").grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        safety_frame = ttk.Frame(settings_frame)
        safety_frame.grid(row=4, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

        ttk.Label(safety_frame, text="Max clicks:").pack(side=tk.LEFT)
        self.max_clicks_entry = ttk.Entry(safety_frame, width=8)
        self.max_clicks_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.max_clicks_entry.insert(0, str(self.settings.get('max_clicks', '0')))

        ttk.Label(safety_frame, text="Auto-stop after:").pack(side=tk.LEFT, padx=(10, 0))
        self.auto_stop_entry = ttk.Entry(safety_frame, width=5)
        self.auto_stop_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.auto_stop_entry.insert(0, str(self.settings.get('auto_stop_minutes', '0')))
        ttk.Label(safety_frame, text="minutes").pack(side=tk.LEFT)

        # Performance settings section
        ttk.Label(settings_frame, text="Performance:").grid(row=5, column=0, sticky=tk.W, pady=(15, 0))
        performance_frame = ttk.Frame(settings_frame)
        performance_frame.grid(row=5, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(15, 0))

        # Performance monitoring toggle
        self.performance_monitoring_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(performance_frame, text="Monitor Performance",
                       variable=self.performance_monitoring_var,
                       command=self._toggle_performance_monitoring).pack(side=tk.LEFT)

        # Click queuing toggle
        self.click_queuing_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(performance_frame, text="Enable Queuing",
                       variable=self.click_queuing_var,
                       command=self._toggle_click_queuing).pack(side=tk.LEFT, padx=(10, 0))

    def create_control_section(self, parent):
        """Create control buttons section"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=3, column=0, columnspan=2, pady=(0, 15))

        # Start/Stop buttons
        self.start_btn = ttk.Button(control_frame, text="Start (F6)", command=self.start_clicking, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(control_frame, text="Stop (F7)", command=self.stop_clicking,
                                  state=tk.DISABLED, width=15)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Emergency stop
        self.emergency_btn = ttk.Button(control_frame, text="Emergency Stop (ESC)",
                                       command=self.emergency_stop, width=20)
        self.emergency_btn.pack(side=tk.LEFT)

    def create_status_section(self, parent):
        """Create status display section"""
        status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Status indicator
        self.status_var = tk.StringVar(value="Stopped")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                     font=("Arial", 12, "bold"))
        self.status_label.pack(anchor=tk.W)

        # Click counter
        self.click_count_var = tk.StringVar(value="Clicks: 0")
        ttk.Label(status_frame, textvariable=self.click_count_var).pack(anchor=tk.W, pady=(5, 0))

        # Runtime
        self.runtime_var = tk.StringVar(value="Runtime: 0:00:00")
        ttk.Label(status_frame, textvariable=self.runtime_var).pack(anchor=tk.W, pady=(2, 0))

        # Current coordinates
        self.coord_var = tk.StringVar(value="Target: (100, 100)")
        ttk.Label(status_frame, textvariable=self.coord_var).pack(anchor=tk.W, pady=(2, 0))

        # Performance metrics
        self.performance_var = tk.StringVar(value="Performance: --")
        ttk.Label(status_frame, textvariable=self.performance_var).pack(anchor=tk.W, pady=(2, 0))

    def create_disclaimer_section(self, parent):
        """Create disclaimer section"""
        disclaimer_text = ("WARNING: USE RESPONSIBLY\n\n"
                          "This tool is for legitimate automation purposes only.\n"
                          "Ensure compliance with application terms of service,\n"
                          "website policies, and local laws. The author assumes\n"
                          "no responsibility for misuse.")

        disclaimer_label = ttk.Label(parent, text=disclaimer_text,
                                    background="#fff3cd", foreground="#856404",
                                    padding="10", justify=tk.CENTER, relief="solid", wraplength=400)
        disclaimer_label.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

        parent.grid_rowconfigure(5, weight=1)

    def setup_hotkeys(self):
        """Setup keyboard hotkeys"""
        try:
            keyboard.add_hotkey('f6', self.start_clicking)
            keyboard.add_hotkey('f7', self.stop_clicking)
            keyboard.add_hotkey('esc', self.emergency_stop)
        except Exception as e:
            print(f"Hotkey setup failed: {e}")

    def setup_system_tray(self):
        """Setup system tray icon"""
        try:
            # Create a simple icon
            icon_image = Image.new('RGB', (64, 64), color='red')

            self.tray_icon = pystray.Icon(
                "autoclicker",
                icon_image,
                "Windows Autoclicker",
                menu=pystray.Menu(
                    pystray.MenuItem('Show', self.show_window),
                    pystray.MenuItem('Start (F6)', self.start_clicking),
                    pystray.MenuItem('Stop (F7)', self.stop_clicking),
                    pystray.MenuItem('Exit', self.quit_application)
                )
            )
        except Exception as e:
            print(f"System tray setup failed: {e}")

    def start_coordinate_picker(self):
        """Start coordinate picking mode"""
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
            on_cancelled=self._on_coordinate_picker_cancelled
        )

    def _on_coordinates_selected(self, x: int, y: int):
        """Handle coordinate selection"""
        self.x_entry.delete(0, tk.END)
        self.x_entry.insert(0, str(x))
        self.y_entry.delete(0, tk.END)
        self.y_entry.insert(0, str(y))

        self.show_window()
        self.pick_btn.config(state=tk.NORMAL)
        self.status_var.set("Coordinate selected")

    def _on_coordinate_picker_cancelled(self):
        """Handle coordinate picker cancellation"""
        self.show_window()
        self.pick_btn.config(state=tk.NORMAL)
        self.status_var.set("Coordinate selection cancelled")

    def save_preset(self):
        """Save current coordinates as preset"""
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

    def load_preset(self, event=None):
        """Load selected preset"""
        preset_name = self.preset_var.get()
        coords = self.preset_manager.load_preset(preset_name)
        if coords:
            x, y = coords
            self.x_entry.delete(0, tk.END)
            self.x_entry.insert(0, str(x))
            self.y_entry.delete(0, tk.END)
            self.y_entry.insert(0, str(y))

    def update_preset_list(self):
        """Update preset combobox with current presets"""
        preset_names = self.preset_manager.get_preset_names()
        self.preset_combo['values'] = preset_names

    def start_clicking(self):
        """Start the autoclicking process with comprehensive validation"""
        try:
            # Collect all settings from UI
            raw_settings = {
                'x_coord': self.x_entry.get(),
                'y_coord': self.y_entry.get(),
                'interval': self.interval_entry.get(),
                'interval_unit': self.interval_unit_var.get(),
                'variation': self.variation_entry.get(),
                'mouse_button': self.button_var.get(),
                'click_type': self.click_type_var.get(),
                'burst_clicks': self.burst_clicks_entry.get(),
                'burst_pause': self.burst_pause_entry.get(),
                'max_clicks': self.max_clicks_entry.get(),
                'auto_stop_minutes': self.auto_stop_entry.get()
            }

            # Get screen dimensions for coordinate validation
            screen_width, screen_height = pyautogui.size()

            # Validate all settings
            validation_result = self.settings.validate_all_settings(raw_settings, screen_width, screen_height)

            if not validation_result['valid']:
                # Show validation errors
                error_messages = []
                for field, error in validation_result['errors'].items():
                    error_messages.append(f"{field.title()}: {error}")

                messagebox.showerror("Validation Error", "\n".join(error_messages))
                return

            # Use sanitized settings
            sanitized = validation_result['sanitized_settings']

            # Extract values for click engine
            x = sanitized['x_coord']
            y = sanitized['y_coord']
            interval = sanitized['interval']
            interval_unit = sanitized['interval_unit']
            variation = sanitized['variation']
            burst_clicks = sanitized['burst_clicks']
            burst_pause = sanitized['burst_pause'] / 1000  # Convert to seconds for click engine

            # Convert interval to milliseconds for click engine
            if interval_unit == 'seconds':
                interval_ms = interval * 1000
            else:
                interval_ms = interval

            # Update settings with sanitized values
            self.settings.update(sanitized)

            # Start clicking with validated settings
            if self.click_engine.start_clicking(
                x=x, y=y, interval=interval_ms, variation=variation,
                burst_clicks=burst_clicks, burst_pause=burst_pause,
                max_clicks=sanitized['max_clicks'], auto_stop_minutes=sanitized['auto_stop_minutes'],
                mouse_button=sanitized['mouse_button'], click_type=sanitized['click_type'],
                on_click_complete=self._on_clicking_complete,
                on_status_update=self._on_status_update
            ):
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                self.status_var.set("Running...")
                self.coord_var.set(f"Target: ({x}, {y})")

                # Start status update timer
                self._start_status_timer()

        except AutoclickerError as e:
            # Handle our custom exceptions with user-friendly messages
            user_message = create_user_friendly_error(e)
            messagebox.showerror("Autoclicker Error", user_message)
        except Exception as e:
            # Handle unexpected errors
            user_message = create_user_friendly_error(e)
            messagebox.showerror("Unexpected Error", user_message)

    def stop_clicking(self):
        """Stop the autoclicking process"""
        self.click_engine.stop_clicking()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Stopped")
        self._stop_status_timer()

    def emergency_stop(self):
        """Emergency stop - immediate halt"""
        self.click_engine.emergency_stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Emergency Stop")
        self._stop_status_timer()

    def _on_clicking_complete(self):
        """Handle clicking completion"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Stopped")
        self._stop_status_timer()

    def _on_status_update(self):
        """Handle status updates from click engine"""
        status = self.click_engine.get_status()
        self.click_count_var.set(f"Clicks: {status['click_count']}")
        self.runtime_var.set(f"Runtime: {status['runtime']}")

        # Update performance metrics if available
        if 'performance' in status:
            perf = status['performance']
            perf_text = f"Performance: {perf['clicks_per_second']} cps, {perf['success_rate']:.1f}% success"
            self.performance_var.set(perf_text)
        else:
            self.performance_var.set("Performance: --")

    def _start_status_timer(self):
        """Start periodic status updates"""
        self._status_timer = self.root.after(1000, self._update_status_loop)

    def _stop_status_timer(self):
        """Stop status update timer"""
        if hasattr(self, '_status_timer'):
            self.root.after_cancel(self._status_timer)

    def _update_status_loop(self):
        """Periodic status update loop"""
        if self.click_engine.is_running:
            self._on_status_update()
            self._status_timer = self.root.after(1000, self._update_status_loop)

    def _toggle_performance_monitoring(self):
        """Toggle performance monitoring on/off"""
        enabled = self.performance_monitoring_var.get()
        # Note: Performance monitoring is always enabled in the current implementation
        # This could be extended to allow disabling it entirely
        pass

    def _toggle_click_queuing(self):
        """Toggle click queuing on/off"""
        enabled = self.click_queuing_var.get()
        self.click_engine.enable_click_queuing(enabled)

    def show_window(self):
        """Show main window"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_frame_configure(self, event):
        """Handle frame resize"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """Handle canvas resize"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def on_closing(self):
        """Handle window close event"""
        if messagebox.askokcancel("Quit", "Do you want to quit the application?"):
            self.quit_application()

    def quit_application(self):
        """Quit the application"""
        self.stop_clicking()
        self.coordinate_picker.stop_picking()
        self.settings.update({})  # Save current settings

        if hasattr(self, 'tray_icon') and self.tray_icon:
            self.tray_icon.stop()

        self.root.quit()
        self.root.destroy()

    def run(self):
        """Run the application"""
        try:
            # Start system tray in background
            if hasattr(self, 'tray_icon') and self.tray_icon:
                tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
                tray_thread.start()

            # Start main loop
            self.root.mainloop()

        except KeyboardInterrupt:
            self.quit_application()
