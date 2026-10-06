# SPDX-License-Identifier: CC-BY-NC-4.0
"""State shared by AutoclickerApp and its feature mixins.

Declares the widgets the section builders attach and the attributes and
methods the mixins use, so each feature module type-checks on its own.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...app.controller import AutoclickerController
    from ...app.hotkeys import HotkeyManager
    from ...core.click_engine import ClickEngine
    from ...core.recorder import ClickRecorder, RecordedClick
    from ...core.settings_manager import SettingsManager
    from ...utils.profiles import PresetManager
    from ..picker import CoordinatePicker


class AppBase:
    # Core objects (set in AutoclickerApp.__init__)
    root: Any
    controller: AutoclickerController
    settings: SettingsManager
    click_engine: ClickEngine
    preset_manager: PresetManager
    coordinate_picker: CoordinatePicker
    tray_icon: Any
    _hotkeys: HotkeyManager
    _recorded: list[RecordedClick]

    # Widgets and variables the section builders in gui/sections attach.
    # Widgets and variables the section builders in gui/sections attach.
    x_entry: ttk.Entry
    y_entry: ttk.Entry
    pick_btn: ttk.Button
    target_mode_var: tk.StringVar
    coord_var: tk.StringVar
    preset_var: tk.StringVar
    preset_combo: ttk.Combobox
    preset_summary_var: tk.StringVar
    button_var: tk.StringVar
    click_type_var: tk.StringVar
    action_var: tk.StringVar
    # Click / Hold / Key radios, enabled per target mode (#102)
    action_radios: dict[str, ttk.Radiobutton]
    hold_entry: ttk.Entry
    key_entry: ttk.Entry
    condition_var: tk.StringVar
    condition_label_var: tk.StringVar
    condition_swatch: tk.Label
    condition_tolerance_entry: ttk.Entry
    # (x, y, "#rrggbb") of the watched pixel
    condition_point: tuple
    interval_entry: ttk.Entry
    interval_unit_var: tk.StringVar
    variation_entry: ttk.Entry
    burst_clicks_entry: ttk.Entry
    burst_pause_entry: ttk.Entry
    limit_clicks_var: tk.BooleanVar
    max_clicks_entry: ttk.Entry
    auto_stop_entry: ttk.Entry
    max_cps_entry: ttk.Entry
    start_delay_entry: ttk.Entry
    failsafe_var: tk.BooleanVar
    pause_unfocused_var: tk.BooleanVar
    minimize_to_tray_var: tk.BooleanVar
    check_updates_var: tk.BooleanVar
    update_button: ttk.Button
    start_btn: ttk.Button
    stop_btn: ttk.Button
    emergency_btn: ttk.Button
    status_var: tk.StringVar
    status_dot: ttk.Label
    click_count_var: tk.StringVar
    runtime_var: tk.StringVar
    performance_var: tk.StringVar
    theme_button: ttk.Button
    bottom_frame: ttk.Frame
    sequence_frame: ttk.Frame
    image_frame: ttk.Frame
    image_info_var: tk.StringVar
    image_margin_entry: ttk.Entry
    image_tolerance_entry: ttk.Entry
    image_preview: ttk.Label
    image_clear_btn: ttk.Button
    # Keeps the thumbnail's PhotoImage alive while Tk shows it.
    _image_photo: Any = None
    # Image target mode: the captured PNG and the area searched for it
    image_path: str
    image_region: list[int]
    sequence_list: tk.Listbox
    sequence_repeat_entry: ttk.Entry
    # Steps of the sequence target mode: {"x", "y", "button", "click_type", "delay_ms"}
    sequence_steps: list[dict]
    # Pending root.after id while a Start-button countdown is running.
    _countdown_job: str | None = None
    # Release page of a newer version found by the update check.
    _release_url: str | None = None
    # Active while recording a sequence (#86); the hook exists only then.
    _recorder: ClickRecorder | None = None
    first_run_hint: ttk.Frame
    first_run_hint_var: tk.StringVar
    hint_updates_var: tk.BooleanVar
    # Controls disabled while a run or countdown uses the settings (#102).
    _locked_widgets: tuple[Any, ...] = ()
    # True while the Hotkeys dialog is open; global keys are released then (#93).
    _hotkeys_dialog_open: bool = False
    # Pause reason the status line currently shows; None while running normally.
    _shown_paused: str | None = None

    if TYPE_CHECKING:
        # Implemented by AutoclickerApp or another mixin.
        def _ui(self, fn: Callable[..., Any], *args: Any) -> None: ...
        def _set_status_message(self, message: str, state: str = ...) -> None: ...
        def _paint_stopped(self, message: str, state: str = ...) -> None: ...
        def _collect_ui_settings(self) -> dict: ...
        def _show_validation_errors(self, errors: dict[str, str]) -> None: ...
        def _confirm_guard_off(self) -> bool: ...
        def _apply_target_mode_state(self) -> None: ...
        def _apply_action_state(self) -> None: ...
        def _refresh_target_summary(self) -> None: ...
        def _hotkey_suffix(self, action: str) -> str: ...
        def show_window(self) -> None: ...
        def start_clicking(self, confirmed: bool = False) -> None: ...
        def _start_blocked_reason(self) -> str | None: ...
        def _set_settings_locked(self, locked: bool) -> None: ...
        def start_coordinate_picker(
            self, on_selected: Callable[[int, int], None] | None = None
        ) -> None: ...
        def update_preset_list(self) -> None: ...
        def _refresh_sequence_list(self, select: int | None = None) -> None: ...
        def _sequence_changed(self, select: int | None = None) -> None: ...
        def _refresh_condition_label(self) -> None: ...
        def _cancel_countdown(self, message: str | None = ...) -> bool: ...
        def _finish_recording(self) -> bool: ...
        def show_info(self) -> None: ...
        def _refresh_image_label(self) -> None: ...
