"""
Coordinate picker utility
Handles interactive coordinate selection with mouse events
"""

import threading
import mouse
from typing import Optional, Callable, Tuple


class CoordinatePicker:
    """Handles interactive coordinate selection"""

    def __init__(self):
        self.is_active = False
        self.on_coordinate_selected: Optional[Callable[[int, int], None]] = None
        self.on_cancelled: Optional[Callable] = None

    def start_picking(self, on_selected: Callable[[int, int], None],
                     on_cancelled: Optional[Callable] = None) -> bool:
        """
        Start coordinate picking mode

        Args:
            on_selected: Callback when coordinates are selected (x, y)
            on_cancelled: Callback when picking is cancelled

        Returns:
            True if started successfully
        """
        if self.is_active:
            return False

        self.is_active = True
        self.on_coordinate_selected = on_selected
        self.on_cancelled = on_cancelled

        # Start listening for mouse events
        try:
            mouse.on_button(self._on_mouse_click, buttons=('left',), types=('down',))
            return True
        except Exception as e:
            print(f"Failed to start coordinate picker: {e}")
            self.is_active = False
            return False

    def stop_picking(self) -> None:
        """Stop coordinate picking mode"""
        if not self.is_active:
            return

        self.is_active = False

        # Stop listening for mouse events
        try:
            mouse.unhook(self._on_mouse_click)
        except (ValueError, Exception):
            # Handler might already be removed
            pass

        # Call cancelled callback
        if self.on_cancelled:
            self.on_cancelled()

    def _on_mouse_click(self) -> None:
        """Handle mouse click for coordinate selection"""
        if not self.is_active:
            return

        try:
            # Get current mouse position
            x, y = mouse.get_position()

            # Stop listening
            self.stop_picking()

            # Call selection callback
            if self.on_coordinate_selected:
                self.on_coordinate_selected(x, y)

        except Exception as e:
            print(f"Coordinate picker error: {e}")
            self.stop_picking()

    def is_picking(self) -> bool:
        """Check if coordinate picking is active"""
        return self.is_active


class PresetManager:
    """Manages coordinate presets"""

    def __init__(self, settings_manager):
        self.settings = settings_manager

    def save_preset(self, name: str, x: int, y: int) -> bool:
        """Save coordinates as a preset"""
        try:
            presets = self.settings.get('presets', {})
            presets[name] = {'x': x, 'y': y}
            self.settings.set('presets', presets)
            return True
        except Exception as e:
            print(f"Failed to save preset: {e}")
            return False

    def load_preset(self, name: str) -> Optional[Tuple[int, int]]:
        """Load coordinates from a preset"""
        try:
            presets = self.settings.get('presets', {})
            if name in presets:
                preset = presets[name]
                return preset['x'], preset['y']
            return None
        except Exception as e:
            print(f"Failed to load preset: {e}")
            return None

    def get_preset_names(self) -> list:
        """Get list of available preset names"""
        presets = self.settings.get('presets', {})
        return list(presets.keys())

    def delete_preset(self, name: str) -> bool:
        """Delete a preset"""
        try:
            presets = self.settings.get('presets', {})
            if name in presets:
                del presets[name]
                self.settings.set('presets', presets)
                return True
            return False
        except Exception as e:
            print(f"Failed to delete preset: {e}")
            return False
