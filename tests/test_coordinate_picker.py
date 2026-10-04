"""Unit tests for the Pick Location overlay and the preset manager."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from autoclicker.core.screen import ScreenBounds
from autoclicker.core.settings_manager import SettingsManager
from autoclicker.gui.picker import CoordinatePicker
from autoclicker.utils.coordinate_picker import PresetManager


class TestOverlayPicker(unittest.TestCase):
    """#43: Pick Location uses a click-absorbing overlay on the Tk thread."""

    def setUp(self):
        self.windows: list[MagicMock] = []

        def factory(_root):
            window = MagicMock()
            self.windows.append(window)
            return window

        self.label_patch = patch("autoclicker.gui.picker.tk.Label")
        self.label_patch.start()
        self.picker = CoordinatePicker(
            MagicMock(),
            bounds=lambda: ScreenBounds(-1920, 0, 3840, 1080),
            toplevel_factory=factory,
        )

    def tearDown(self):
        self.label_patch.stop()

    @staticmethod
    def _event(x, y):
        return SimpleNamespace(x_root=x, y_root=y)

    def test_overlay_covers_whole_desktop_and_is_topmost(self):
        self.assertTrue(self.picker.start_picking(lambda x, y: None))
        overlay = self.windows[0]
        overlay.geometry.assert_called_once_with("3840x1080+-1920+0")
        overlay.overrideredirect.assert_called_once_with(True)
        overlay.attributes.assert_any_call("-topmost", True)
        bound = {c.args[0] for c in overlay.bind.call_args_list}
        self.assertTrue({"<Button-1>", "<Button-3>", "<Escape>", "<Motion>"} <= bound)
        self.assertTrue(self.picker.is_picking())

    def test_click_selects_and_closes(self):
        selected = []
        self.picker.start_picking(lambda x, y: selected.append((x, y)))
        self.picker._on_click(self._event(-1200, 300))
        self.assertEqual(selected, [(-1200, 300)])
        self.assertFalse(self.picker.is_picking())
        for window in self.windows:
            window.destroy.assert_called_once()

    def test_escape_cancels(self):
        cancelled = MagicMock()
        selected = MagicMock()
        self.picker.start_picking(selected, on_cancelled=cancelled)
        self.picker._on_cancel()
        cancelled.assert_called_once()
        selected.assert_not_called()
        self.assertFalse(self.picker.is_picking())

    def test_motion_updates_readout(self):
        self.picker.start_picking(lambda x, y: None)
        self.picker._on_motion(self._event(500, 400))
        readout = self.windows[1]
        readout.geometry.assert_called_with("+518+418")
        text = self.picker._readout_label.configure.call_args.kwargs["text"]
        self.assertTrue(text.startswith("500, 400"))

    def test_second_start_rejected_and_stop_without_cancel(self):
        self.assertTrue(self.picker.start_picking(lambda x, y: None))
        self.assertFalse(self.picker.start_picking(lambda x, y: None))
        cancelled = MagicMock()
        self.picker.on_cancelled = cancelled
        self.picker.stop_picking(cancelled=False)
        cancelled.assert_not_called()
        self.assertFalse(self.picker.is_picking())

    def test_overlay_failure_returns_false(self):
        picker = CoordinatePicker(
            MagicMock(),
            bounds=lambda: ScreenBounds(0, 0, 100, 100),
            toplevel_factory=MagicMock(side_effect=RuntimeError("no display")),
        )
        self.assertFalse(picker.start_picking(lambda x, y: None))
        self.assertFalse(picker.is_picking())


class TestPresetManager(unittest.TestCase):
    """Test cases for PresetManager"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.settings_file = self.temp_file.name
        self.settings = SettingsManager(self.settings_file)
        self.preset_manager = PresetManager(self.settings)

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.settings_file):
            os.unlink(self.settings_file)

    def test_save_preset_success(self):
        """Test successful preset saving"""
        result = self.preset_manager.save_preset("TestPreset", 100, 200)
        self.assertTrue(result)

        # Check that preset was saved in settings
        presets = self.settings.get("presets", {})
        self.assertIn("TestPreset", presets)
        self.assertEqual(presets["TestPreset"], {"x": 100, "y": 200})

    def test_load_preset_success(self):
        """Test successful preset loading"""
        # Save a preset first
        self.preset_manager.save_preset("LoadTest", 300, 400)

        # Load the preset
        coords = self.preset_manager.load_preset("LoadTest")
        self.assertEqual(coords, (300, 400))

    def test_load_preset_not_found(self):
        """Test loading non-existent preset"""
        coords = self.preset_manager.load_preset("NonExistent")
        self.assertIsNone(coords)

    def test_get_preset_names(self):
        """Test getting list of preset names"""
        # Initially empty
        names = self.preset_manager.get_preset_names()
        self.assertEqual(names, [])

        # Add some presets
        self.preset_manager.save_preset("Preset1", 100, 100)
        self.preset_manager.save_preset("Preset2", 200, 200)

        names = self.preset_manager.get_preset_names()
        self.assertEqual(set(names), {"Preset1", "Preset2"})

    def test_delete_preset_success(self):
        """Test successful preset deletion"""
        # Save a preset first
        self.preset_manager.save_preset("DeleteTest", 500, 600)

        # Delete the preset
        result = self.preset_manager.delete_preset("DeleteTest")
        self.assertTrue(result)

        # Check that it's gone
        coords = self.preset_manager.load_preset("DeleteTest")
        self.assertIsNone(coords)

    def test_delete_preset_not_found(self):
        """Test deleting non-existent preset"""
        result = self.preset_manager.delete_preset("NonExistent")
        self.assertFalse(result)

    def test_preset_persistence(self):
        """Test that presets persist across settings manager instances"""
        # Save preset with first manager
        self.preset_manager.save_preset("Persistent", 123, 456)

        # Create new manager and preset manager
        new_settings = SettingsManager(self.settings_file)
        new_preset_manager = PresetManager(new_settings)

        # Load preset with new manager
        coords = new_preset_manager.load_preset("Persistent")
        self.assertEqual(coords, (123, 456))


if __name__ == "__main__":
    unittest.main()
