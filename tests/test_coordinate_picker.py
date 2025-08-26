"""
Unit tests for coordinate picker and preset manager
Tests coordinate selection and preset functionality
"""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os

from autoclicker.utils.coordinate_picker import CoordinatePicker, PresetManager
from autoclicker.core.settings_manager import SettingsManager


class TestCoordinatePicker(unittest.TestCase):
    """Test cases for CoordinatePicker"""

    def setUp(self):
        """Set up test fixtures"""
        self.picker = CoordinatePicker()
        self.callback_called = False
        self.callback_coords = None

    def test_initial_state(self):
        """Test initial state of coordinate picker"""
        self.assertFalse(self.picker.is_picking())
        self.assertIsNone(self.picker.on_coordinate_selected)
        self.assertIsNone(self.picker.on_cancelled)

    def test_start_picking_success(self):
        """Test successful start of coordinate picking"""
        def on_selected(x, y):
            self.callback_called = True
            self.callback_coords = (x, y)

        result = self.picker.start_picking(on_selected)
        self.assertTrue(result)
        self.assertTrue(self.picker.is_picking())
        self.assertEqual(self.picker.on_coordinate_selected, on_selected)

    def test_start_picking_already_active(self):
        """Test starting coordinate picking when already active"""
        self.picker.start_picking(lambda x, y: None)
        self.assertTrue(self.picker.is_picking())

        # Try to start again
        result = self.picker.start_picking(lambda x, y: None)
        self.assertFalse(result)

    def test_stop_picking(self):
        """Test stopping coordinate picking"""
        cancelled_called = False

        def on_cancelled():
            nonlocal cancelled_called
            cancelled_called = True

        self.picker.start_picking(lambda x, y: None, on_cancelled)
        self.assertTrue(self.picker.is_picking())

        self.picker.stop_picking()
        self.assertFalse(self.picker.is_picking())
        self.assertTrue(cancelled_called)

    def test_coordinate_selection_callback(self):
        """Test coordinate selection callback"""
        callback_coords = None

        def on_selected(x, y):
            nonlocal callback_coords
            callback_coords = (x, y)

        self.picker.start_picking(on_selected)

        # Simulate coordinate selection
        self.picker._on_mouse_click = MagicMock()
        self.picker.on_coordinate_selected(100, 200)

        self.assertEqual(callback_coords, (100, 200))


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
        presets = self.settings.get('presets', {})
        self.assertIn("TestPreset", presets)
        self.assertEqual(presets["TestPreset"], {'x': 100, 'y': 200})

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


class TestCoordinatePickerIntegration(unittest.TestCase):
    """Integration tests for coordinate picker"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.settings_file = self.temp_file.name
        self.settings = SettingsManager(self.settings_file)
        self.preset_manager = PresetManager(self.settings)
        self.picker = CoordinatePicker()

    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.settings_file):
            os.unlink(self.settings_file)

    @patch('autoclicker.utils.coordinate_picker.mouse')
    def test_full_coordinate_workflow(self, mock_mouse):
        """Test full coordinate picking workflow"""
        # Mock mouse module
        mock_mouse.get_position.return_value = (150, 250)
        mock_mouse.on_button = MagicMock()
        mock_mouse.unhook = MagicMock()

        selected_coords = None
        selection_completed = False

        def on_selected(x, y):
            nonlocal selected_coords, selection_completed
            selected_coords = (x, y)
            selection_completed = True

        # Start coordinate picking
        result = self.picker.start_picking(on_selected)
        self.assertTrue(result)

        # Simulate mouse click
        self.picker._on_mouse_click()

        # Check that coordinates were captured
        self.assertTrue(selection_completed)
        self.assertEqual(selected_coords, (150, 250))
        self.assertFalse(self.picker.is_picking())

        # Check that mouse hooks were managed
        mock_mouse.on_button.assert_called_once()
        mock_mouse.unhook.assert_called_once()


if __name__ == '__main__':
    unittest.main()
