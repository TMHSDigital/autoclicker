"""Anti-aliased shapes for the custom-drawn widgets."""

import unittest
from unittest.mock import MagicMock

from autoclicker.gui.widgets import render


class TestRoundedRect(unittest.TestCase):
    def test_size_and_mode(self):
        image = render.rounded_rect(150, 108, 18, "#4aa3ff")
        self.assertEqual(image.size, (150, 108))
        self.assertEqual(image.mode, "RGBA")

    def test_corners_are_transparent_and_center_is_filled(self):
        image = render.rounded_rect(150, 108, 18, "#4aa3ff")
        self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertEqual(image.getpixel((149, 107))[3], 0)
        self.assertEqual(image.getpixel((75, 54)), (0x4A, 0xA3, 0xFF, 255))

    def test_outline_colors_the_edge(self):
        image = render.rounded_rect(80, 40, 6, "#000000", outline="#ffffff", outline_width=2)
        self.assertEqual(image.getpixel((40, 0))[:3], (255, 255, 255))
        self.assertEqual(image.getpixel((40, 20))[:3], (0, 0, 0))

    def test_same_arguments_hit_the_cache(self):
        a = render.rounded_rect(20, 20, 4, "#123456")
        b = render.rounded_rect(20, 20, 4, "#123456")
        self.assertIs(a, b)
        self.assertIsNot(a, render.rounded_rect(20, 20, 4, "#654321"))

    def test_radius_is_clamped_to_the_shape(self):
        image = render.rounded_rect(10, 10, 50, "#ff0000")  # radius larger than the box
        self.assertEqual(image.size, (10, 10))
        self.assertEqual(image.getpixel((5, 5))[:3], (255, 0, 0))


class TestScale(unittest.TestCase):
    def test_scale_from_dpi(self):
        widget = MagicMock()
        widget.winfo_fpixels.return_value = 144.0  # 150% scaling
        self.assertAlmostEqual(render.ui_scale(widget), 1.5)
        widget.winfo_fpixels.return_value = 96.0
        self.assertAlmostEqual(render.ui_scale(widget), 1.0)

    def test_scale_falls_back_to_one(self):
        widget = MagicMock()
        widget.winfo_fpixels.side_effect = RuntimeError("no Tk")
        self.assertEqual(render.ui_scale(widget), 1.0)
        widget.winfo_fpixels.side_effect = None
        widget.winfo_fpixels.return_value = 0
        self.assertEqual(render.ui_scale(widget), 1.0)

    def test_px_rounds_scaled_pixels(self):
        self.assertEqual(render.px(10, 1.5), 15)
        self.assertEqual(render.px(7, 1.25), 9)
        self.assertEqual(render.px(10, 1.0), 10)


if __name__ == "__main__":
    unittest.main()
