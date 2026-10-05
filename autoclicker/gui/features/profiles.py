# SPDX-License-Identifier: CC-BY-NC-4.0
"""Named profiles: save, load, import and export (#73)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...utils.profiles import PROFILE_KEYS, describe_profile
from .. import dialogs
from .base import AppBase


class ProfilesMixin(AppBase):
    def _profile_from_ui(self) -> dict | None:
        """The current target and click settings as a profile, or None if invalid."""
        result = self.controller.validate(self._collect_ui_settings())
        if not result["valid"]:
            self._show_validation_errors(result["errors"])
            return None
        sanitized = result["sanitized_settings"]
        profile = {k: sanitized[k] for k in PROFILE_KEYS if k in sanitized}
        # Cursor-mode profiles still keep a point, so switching them to Fixed works.
        for axis, key in (("x", "x_coord"), ("y", "y_coord")):
            value = sanitized.get(key, self.settings.get(key, 100))
            try:
                profile[axis] = int(value)
            except (TypeError, ValueError):
                profile[axis] = 100
        return profile

    def save_preset(self) -> None:
        """Save the target and click settings as a named profile."""
        profile = self._profile_from_ui()
        if profile is None:
            return
        name = dialogs.simpledialog.askstring("Save Profile", "Profile name:")
        name = name.strip() if name else ""
        if not name:
            return
        if self.preset_manager.has_profile(name) and not dialogs.messagebox.askyesno(
            "Save Profile", f"Replace the existing profile '{name}'?"
        ):
            return
        if self.preset_manager.save_profile(name, profile):
            self.update_preset_list()
            self.preset_var.set(name)
            self.preset_summary_var.set(describe_profile(profile))
            self._set_status_message(f"Saved profile '{name}'")
        else:
            dialogs.messagebox.showerror("Error", "Failed to save the profile")

    def delete_preset(self) -> None:
        """Delete the selected coordinate preset."""
        preset_name = self.preset_var.get()
        if not preset_name:
            dialogs.messagebox.showwarning("Delete Profile", "Select a profile to delete.")
            return
        if not dialogs.messagebox.askokcancel("Delete Profile", f"Delete profile '{preset_name}'?"):
            return
        if self.preset_manager.delete_preset(preset_name):
            self.update_preset_list()
            self.preset_var.set("")
            self.preset_summary_var.set("")
            self._set_status_message(f"Deleted profile '{preset_name}'")
        else:
            dialogs.messagebox.showerror("Error", "Failed to delete the profile")

    def load_preset(self, event=None) -> None:
        """Apply the selected profile to the form (only the settings it stores)."""
        profile = self.preset_manager.load_profile(self.preset_var.get())
        if profile is None:
            return
        self.apply_form_values(profile)
        self.preset_summary_var.set(describe_profile(profile))

    def apply_form_values(self, values: dict) -> None:
        """Fill the form from profile-shaped values (``x``/``y`` for the point).

        Only keys present are changed. Used for profiles and command-line flags;
        nothing is validated here, Start reports bad values as usual.
        """

        def put(entry: ttk.Entry, value) -> None:
            state = str(entry.cget("state"))
            entry.configure(state=tk.NORMAL)
            entry.delete(0, tk.END)
            entry.insert(0, str(value))
            entry.configure(state=state)

        entries = {
            "x": self.x_entry,
            "y": self.y_entry,
            "interval": self.interval_entry,
            "variation": self.variation_entry,
            "burst_clicks": self.burst_clicks_entry,
            "burst_pause": self.burst_pause_entry,
            "auto_stop_minutes": self.auto_stop_entry,
            "sequence_repeat": self.sequence_repeat_entry,
            "start_delay_seconds": self.start_delay_entry,
            "hold_ms": self.hold_entry,
            "key": self.key_entry,
        }
        for key, entry in entries.items():
            if key in values:
                put(entry, values[key])
        variables = {
            "interval_unit": self.interval_unit_var,
            "mouse_button": self.button_var,
            "click_type": self.click_type_var,
            "action": self.action_var,
        }
        for key, var in variables.items():
            if key in values:
                var.set(values[key])
        self._apply_action_state()
        if "max_clicks" in values:
            try:
                limited = float(values["max_clicks"]) != 0
            except (TypeError, ValueError):
                limited = True  # let validation report the bad value
            self.limit_clicks_var.set(limited)
            if limited:
                put(self.max_clicks_entry, values["max_clicks"])
            self.max_clicks_entry.configure(state=tk.NORMAL if limited else tk.DISABLED)
        if "condition_tolerance" in values:
            put(self.condition_tolerance_entry, values["condition_tolerance"])
        if all(k in values for k in ("condition_x", "condition_y", "condition_color")):
            self.condition_point = (
                values["condition_x"],
                values["condition_y"],
                str(values["condition_color"]),
            )
        if values.get("condition") in ("none", "wait", "stop"):
            self.condition_var.set(values["condition"])
        self._refresh_condition_label()
        if isinstance(values.get("sequence"), list):
            self.sequence_steps = [dict(step) for step in values["sequence"]]
            self._refresh_sequence_list()
        if "image_margin" in values:
            put(self.image_margin_entry, values["image_margin"])
        if values.get("target_mode") == "image" or "image_path" in values:
            # An image profile brings its own image; one without it must not
            # silently click the image captured last (#98).
            self.image_path = str(values.get("image_path") or "")
            region = values.get("image_region")
            self.image_region = list(region) if isinstance(region, list) else []
            self.settings.update({"image_path": self.image_path, "image_region": self.image_region})
            self._refresh_image_label()
        if values.get("target_mode") in ("fixed", "cursor", "sequence", "image"):
            self.target_mode_var.set(values["target_mode"])
            self._apply_target_mode_state()
        self._refresh_target_summary()

    def export_profiles(self) -> None:
        """Save every profile to a JSON file."""
        if not self.preset_manager.get_preset_names():
            dialogs.messagebox.showinfo("Export Profiles", "There are no profiles to export yet.")
            return
        path = dialogs.filedialog.asksaveasfilename(
            title="Export Profiles",
            defaultextension=".json",
            initialfile="autoclicker-profiles.json",
            filetypes=[("Profiles", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            count = self.preset_manager.export_profiles(path)
        except OSError as e:
            dialogs.messagebox.showerror("Export Profiles", f"Could not write the file: {e}")
            return
        self._set_status_message(f"Exported {count} profile{'s' if count != 1 else ''}")

    def import_profiles(self) -> None:
        """Add profiles from a file exported by this app."""
        path = dialogs.filedialog.askopenfilename(
            title="Import Profiles",
            filetypes=[("Profiles", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            profiles = self.preset_manager.read_profiles_file(path)
        except ValueError as e:
            dialogs.messagebox.showerror("Import Profiles", str(e))
            return
        clashes = [name for name in profiles if self.preset_manager.has_profile(name)]
        replace = bool(clashes) and dialogs.messagebox.askyesno(
            "Import Profiles",
            "These profiles already exist:\n\n"
            + "\n".join(clashes)
            + "\n\nReplace them with the imported ones?",
        )
        result = self.preset_manager.import_profiles(profiles, replace_existing=replace)
        self.update_preset_list()
        lines = [f"Added {len(result.added)}, replaced {len(result.replaced)}."]
        if result.skipped:
            lines.append(f"Kept existing: {', '.join(result.skipped)}.")
        if result.invalid:
            lines.append(f"Skipped invalid: {', '.join(result.invalid)}.")
        dialogs.messagebox.showinfo("Import Profiles", "\n".join(lines))

    def update_preset_list(self) -> None:
        """Update preset combobox with current presets."""
        preset_names = self.preset_manager.get_preset_names()
        self.preset_combo["values"] = preset_names
