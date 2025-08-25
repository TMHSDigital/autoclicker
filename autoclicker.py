#!/usr/bin/env python3
"""
Windows Autoclicker Application
A reliable autoclicker with GUI for Windows 10/11

Author: Sonic AI Assistant
Year: 2025
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import random
import json
import os
import sys
import pyautogui
import keyboard
import mouse
from PIL import Image, ImageTk
import win32api
import win32con
import win32gui
import win32process
import pystray
from pystray import MenuItem as item

# Disable pyautogui failsafe for production use
pyautogui.FAILSAFE = False


class AutoclickerApp:
    """Main autoclicker application class"""

    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()

        # Core variables
        self.is_running = False
        self.click_thread = None
        self.click_count = 0
        self.start_time = 0
        self.coordinate_picker_active = False

        # Settings
        self.settings = self.load_settings()

        # GUI components
        self.create_gui()

        # Hotkey setup
        self.setup_hotkeys()

        # System tray setup
        self.tray_icon = None
        self.setup_system_tray()

        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_window(self):
        """Configure main window properties"""
        self.root.title("Windows Autoclicker")
        self.root.geometry("550x700")
        self.root.resizable(True, True)
        self.root.minsize(450, 600)  # Minimum size to prevent content cutoff

        # Set window icon if available
        try:
            self.root.iconbitmap("autoclicker.ico")
        except:
            pass

        # Configure root grid for responsive layout
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Center window on screen
        self.center_window()

        # Set theme
        style = ttk.Style()
        style.theme_use('vista' if sys.platform == 'win32' else 'default')

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
        # Create scrollable canvas for responsive design
        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        h_scrollbar = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Create main frame inside canvas
        main_frame = ttk.Frame(self.canvas, padding="20")
        self.canvas_frame = self.canvas.create_window((0, 0), window=main_frame, anchor="nw")

        # Configure grid weights for responsive layout
        main_frame.grid_rowconfigure(5, weight=1)  # Disclaimer section can expand
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        # Bind canvas resize event
        main_frame.bind('<Configure>', self.on_frame_configure)
        self.canvas.bind('<Configure>', self.on_canvas_configure)

        # Title
        title_label = ttk.Label(main_frame, text="Windows Autoclicker",
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))

        # Coordinate section
        self.create_coordinate_section(main_frame)

        # Click settings section
        self.create_click_settings_section(main_frame)

        # Control buttons
        self.create_control_section(main_frame)

        # Status section
        self.create_status_section(main_frame)

        # Disclaimer
        self.create_disclaimer_section(main_frame)

    def on_frame_configure(self, event):
        """Handle frame resize"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """Handle canvas resize"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
        self.update_scrollbar_visibility()

    def update_scrollbar_visibility(self):
        """Update scrollbar visibility based on content size"""
        # Get the bounding box of all items in the canvas
        bbox = self.canvas.bbox("all")
        if bbox:
            content_width = bbox[2] - bbox[0]
            content_height = bbox[3] - bbox[1]

            # Get canvas dimensions
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            # Show/hide scrollbars based on content size
            if content_width > canvas_width:
                self.canvas.grid_columnconfigure(1, minsize=20)  # Show vertical scrollbar
            else:
                self.canvas.grid_columnconfigure(1, minsize=0)   # Hide vertical scrollbar

            if content_height > canvas_height:
                self.canvas.grid_rowconfigure(1, minsize=20)     # Show horizontal scrollbar
            else:
                self.canvas.grid_rowconfigure(1, minsize=0)      # Hide horizontal scrollbar

    def create_coordinate_section(self, parent):
        """Create coordinate input section"""
        coord_frame = ttk.LabelFrame(parent, text="Target Coordinates", padding="10")
        coord_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Configure coordinate frame grid for responsiveness
        coord_frame.grid_columnconfigure(1, weight=1)
        coord_frame.grid_columnconfigure(3, weight=1)
        coord_frame.grid_columnconfigure(6, weight=1)

        # Row 1: X and Y coordinates
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

        # Row 2: Presets section
        ttk.Label(coord_frame, text="Presets:").grid(row=1, column=0, padx=(0, 5), pady=(10, 0), sticky=tk.W)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(coord_frame, textvariable=self.preset_var,
                                        width=20, state="readonly")
        self.preset_combo.grid(row=1, column=1, columnspan=3, padx=(0, 10), pady=(10, 0), sticky=(tk.W, tk.E))
        self.preset_combo['values'] = list(self.settings.get('presets', {}).keys())
        self.preset_combo.bind('<<ComboboxSelected>>', self.load_preset)

        # Save preset button
        self.save_preset_btn = ttk.Button(coord_frame, text="Save Preset",
                                         command=self.save_preset)
        self.save_preset_btn.grid(row=1, column=4, pady=(10, 0), sticky=tk.W)

    def create_click_settings_section(self, parent):
        """Create click settings section"""
        settings_frame = ttk.LabelFrame(parent, text="Click Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Configure settings frame grid for responsiveness
        settings_frame.grid_columnconfigure(1, weight=1)
        settings_frame.grid_columnconfigure(2, weight=1)
        settings_frame.grid_columnconfigure(3, weight=1)

        # Mouse button selection
        ttk.Label(settings_frame, text="Mouse Button:").grid(row=0, column=0, sticky=tk.W)
        self.button_var = tk.StringVar(value=self.settings.get('mouse_button', 'left'))
        button_frame = ttk.Frame(settings_frame)
        button_frame.grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0))

        ttk.Radiobutton(button_frame, text="Left", variable=self.button_var,
                       value="left").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(button_frame, text="Right", variable=self.button_var,
                       value="right").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(button_frame, text="Middle", variable=self.button_var,
                       value="middle").pack(side=tk.LEFT)

        # Click type
        ttk.Label(settings_frame, text="Click Type:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.click_type_var = tk.StringVar(value=self.settings.get('click_type', 'single'))
        click_type_frame = ttk.Frame(settings_frame)
        click_type_frame.grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(10, 0), pady=(10, 0))

        ttk.Radiobutton(click_type_frame, text="Single", variable=self.click_type_var,
                       value="single").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(click_type_frame, text="Double", variable=self.click_type_var,
                       value="double").pack(side=tk.LEFT)

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

        # Random variation
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

    def create_control_section(self, parent):
        """Create control buttons section"""
        control_frame = ttk.Frame(parent)
        control_frame.grid(row=3, column=0, columnspan=2, pady=(0, 15))

        # Start/Stop buttons
        self.start_btn = ttk.Button(control_frame, text="Start (F6)",
                                   command=self.start_clicking, width=15)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(control_frame, text="Stop (F7)",
                                  command=self.stop_clicking, state=tk.DISABLED, width=15)
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

        # Make the disclaimer section expand to fill available space
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
            # Create a simple icon (you can replace with actual icon file)
            icon_image = Image.new('RGB', (64, 64), color='red')

            self.tray_icon = pystray.Icon(
                "autoclicker",
                icon_image,
                "Windows Autoclicker",
                menu=pystray.Menu(
                    item('Show', self.show_window),
                    item('Start (F6)', self.start_clicking),
                    item('Stop (F7)', self.stop_clicking),
                    item('Exit', self.quit_application)
                )
            )
        except Exception as e:
            print(f"System tray setup failed: {e}")

    def start_coordinate_picker(self):
        """Start coordinate picking mode"""
        if self.is_running:
            messagebox.showwarning("Warning", "Stop clicking before picking coordinates.")
            return

        if self.coordinate_picker_active:
            return  # Already active

        self.coordinate_picker_active = True
        self.status_var.set("Click anywhere to select coordinates...")
        self.pick_btn.config(state=tk.DISABLED)

        # Hide window temporarily
        self.root.withdraw()

        # Start listening for mouse click
        mouse.on_button(self.on_coordinate_click, buttons=('left',), types=('down',))

    def on_coordinate_click(self):
        """Handle coordinate selection click"""
        if not self.coordinate_picker_active:
            return

        # Get current mouse position
        x, y = mouse.get_position()

        # Set coordinates in the UI
        self.x_entry.delete(0, tk.END)
        self.x_entry.insert(0, str(x))
        self.y_entry.delete(0, tk.END)
        self.y_entry.insert(0, str(y))

        # Stop listening for mouse events
        try:
            mouse.unhook(self.on_coordinate_click)
        except ValueError:
            # Handler might already be removed, that's okay
            pass
        except Exception as e:
            print(f"Warning: Could not unhook mouse event: {e}")

        # Reset flag
        self.coordinate_picker_active = False

        # Show window again
        self.show_window()
        self.pick_btn.config(state=tk.NORMAL)
        self.status_var.set("Coordinate selected")

    def save_preset(self):
        """Save current coordinates as preset"""
        try:
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())

            preset_name = tk.simpledialog.askstring("Save Preset",
                                                  "Enter preset name:")
            if preset_name:
                if 'presets' not in self.settings:
                    self.settings['presets'] = {}

                self.settings['presets'][preset_name] = {'x': x, 'y': y}
                self.save_settings()

                # Update combobox
                self.preset_combo['values'] = list(self.settings['presets'].keys())
                messagebox.showinfo("Success", f"Preset '{preset_name}' saved!")

        except ValueError:
            messagebox.showerror("Error", "Invalid coordinates")

    def load_preset(self, event=None):
        """Load selected preset"""
        preset_name = self.preset_var.get()
        if preset_name in self.settings.get('presets', {}):
            preset = self.settings['presets'][preset_name]
            self.x_entry.delete(0, tk.END)
            self.x_entry.insert(0, str(preset['x']))
            self.y_entry.delete(0, tk.END)
            self.y_entry.insert(0, str(preset['y']))

    def start_clicking(self):
        """Start the autoclicking process"""
        if self.is_running:
            return

        try:
            # Get settings
            x = int(self.x_entry.get())
            y = int(self.y_entry.get())
            interval = float(self.interval_entry.get())
            interval_unit = self.interval_unit_var.get()
            variation = int(self.variation_entry.get())
            burst_clicks = int(self.burst_clicks_entry.get())
            burst_pause = float(self.burst_pause_entry.get())
            max_clicks = int(self.max_clicks_entry.get())
            auto_stop_minutes = int(self.auto_stop_entry.get())

            # Convert to milliseconds
            if interval_unit == 'seconds':
                interval *= 1000
            burst_pause /= 1000  # Convert to seconds for time.sleep

            # Validate coordinates
            screen_width, screen_height = pyautogui.size()
            if not (0 <= x <= screen_width and 0 <= y <= screen_height):
                messagebox.showerror("Error", "Coordinates are outside screen bounds")
                return

            # Update settings
            self.settings.update({
                'x_coord': x, 'y_coord': y, 'interval': interval if interval_unit == 'ms' else interval/1000,
                'interval_unit': interval_unit, 'variation': variation, 'mouse_button': self.button_var.get(),
                'click_type': self.click_type_var.get(), 'burst_clicks': burst_clicks, 'burst_pause': burst_pause*1000,
                'max_clicks': max_clicks, 'auto_stop_minutes': auto_stop_minutes
            })
            self.save_settings()

            # Start clicking
            self.is_running = True
            self.click_count = 0
            self.start_time = time.time()

            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_var.set("Running...")
            self.coord_var.set(f"Target: ({x}, {y})")

            # Start click thread
            self.click_thread = threading.Thread(target=self.click_loop, daemon=True,
                                               args=(x, y, interval, variation, burst_clicks, burst_pause,
                                                    max_clicks, auto_stop_minutes))
            self.click_thread.start()

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")

    def click_loop(self, x, y, interval, variation, burst_clicks, burst_pause,
                  max_clicks, auto_stop_minutes):
        """Main clicking loop"""
        while self.is_running:
            try:
                # Check auto-stop conditions
                if max_clicks > 0 and self.click_count >= max_clicks:
                    self.stop_clicking()
                    messagebox.showinfo("Auto-stop", f"Reached maximum click limit ({max_clicks})")
                    break

                if auto_stop_minutes > 0:
                    elapsed_minutes = (time.time() - self.start_time) / 60
                    if elapsed_minutes >= auto_stop_minutes:
                        self.stop_clicking()
                        messagebox.showinfo("Auto-stop", f"Auto-stop after {auto_stop_minutes} minutes")
                        break

                # Perform clicks
                for _ in range(burst_clicks):
                    if not self.is_running:
                        break

                    # Add random variation
                    if variation > 0:
                        actual_interval = interval + random.randint(-variation, variation)
                    else:
                        actual_interval = interval

                    # Perform click
                    self.perform_click(x, y)
                    self.click_count += 1

                    # Update UI
                    self.root.after(0, self.update_status)

                    # Wait between clicks in burst
                    if burst_clicks > 1 and _ < burst_clicks - 1:
                        time.sleep(burst_pause)

                # Wait for next burst
                if self.is_running:
                    time.sleep(actual_interval / 1000)

            except Exception as e:
                print(f"Click loop error: {e}")
                self.stop_clicking()
                break

    def perform_click(self, x, y):
        """Perform a single click at coordinates"""
        button = self.button_var.get()
        click_type = self.click_type_var.get()

        try:
            # Move to position
            pyautogui.moveTo(x, y, duration=0.01)

            # Perform click
            if button == 'left':
                if click_type == 'double':
                    pyautogui.doubleClick()
                else:
                    pyautogui.click()
            elif button == 'right':
                pyautogui.rightClick()
            elif button == 'middle':
                pyautogui.middleClick()

        except Exception as e:
            print(f"Click error: {e}")

    def update_status(self):
        """Update status display"""
        self.click_count_var.set(f"Clicks: {self.click_count}")

        if self.start_time > 0:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.runtime_var.set(f"Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def stop_clicking(self):
        """Stop the autoclicking process"""
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Stopped")

    def emergency_stop(self):
        """Emergency stop - immediate halt"""
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Emergency Stop")

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists('autoclicker_settings.json'):
                with open('autoclicker_settings.json', 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Settings load error: {e}")

        return {
            'x_coord': 100, 'y_coord': 100, 'interval': 1000, 'interval_unit': 'ms',
            'variation': 0, 'mouse_button': 'left', 'click_type': 'single',
            'burst_clicks': 1, 'burst_pause': 1000, 'max_clicks': 0, 'auto_stop_minutes': 0,
            'presets': {}
        }

    def save_settings(self):
        """Save settings to file"""
        try:
            with open('autoclicker_settings.json', 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Settings save error: {e}")

    def show_window(self):
        """Show main window"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_closing(self):
        """Handle window close event"""
        # Clean up coordinate picker if active
        self.cleanup_coordinate_picker()

        if messagebox.askokcancel("Quit", "Do you want to quit the application?"):
            self.quit_application()

    def cleanup_coordinate_picker(self):
        """Clean up coordinate picker if active"""
        if self.coordinate_picker_active:
            try:
                mouse.unhook(self.on_coordinate_click)
            except (ValueError, Exception):
                pass  # Handler might already be removed
            self.coordinate_picker_active = False

    def quit_application(self):
        """Quit the application"""
        self.stop_clicking()
        self.cleanup_coordinate_picker()
        self.save_settings()

        if self.tray_icon:
            self.tray_icon.stop()

        self.root.quit()
        self.root.destroy()

    def run(self):
        """Run the application"""
        try:
            # Start system tray in background
            if self.tray_icon:
                tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
                tray_thread.start()

            # Start main loop
            self.root.mainloop()

        except KeyboardInterrupt:
            self.quit_application()


def main():
    """Main function"""
    try:
        app = AutoclickerApp()
        app.run()
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Error", f"Application failed to start: {e}")


if __name__ == "__main__":
    main()
