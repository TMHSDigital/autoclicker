"""Windows High Contrast mode (#181)."""

import unittest
from unittest.mock import MagicMock, patch

from autoclicker.gui import high_contrast, theme


def _user32(on=True, colors=None):
    user32 = MagicMock()

    def spi(_action, _size, info_ref, _flags):
        info_ref._obj.dwFlags = high_contrast.HCF_HIGHCONTRASTON if on else 0
        return 1

    user32.SystemParametersInfoW.side_effect = spi
    colors = colors or {}
    user32.GetSysColor.side_effect = lambda index: colors.get(index, 0x00FFFFFF)
    return user32


class TestDetection(unittest.TestCase):
    def test_on_and_off(self):
        self.assertTrue(high_contrast.is_high_contrast(_user32(on=True)))
        self.assertFalse(high_contrast.is_high_contrast(_user32(on=False)))

    def test_unreadable_counts_as_off(self):
        user32 = MagicMock()
        user32.SystemParametersInfoW.return_value = 0
        self.assertFalse(high_contrast.is_high_contrast(user32))
        user32.SystemParametersInfoW.side_effect = OSError
        self.assertFalse(high_contrast.is_high_contrast(user32))

    def test_colorref_is_bgr(self):
        self.assertEqual(high_contrast._hex(0x00332211), "#112233")


class TestSystemPalette(unittest.TestCase):
    def test_off_gives_none(self):
        self.assertIsNone(high_contrast.system_palette(_user32(on=False)))

    def test_maps_system_colors_onto_every_palette_key(self):
        colors = {
            high_contrast.COLOR_WINDOW: 0x00000000,
            high_contrast.COLOR_WINDOWTEXT: 0x0000FFFF,  # yellow on black
            high_contrast.COLOR_HIGHLIGHT: 0x00FF8000,
        }
        palette = high_contrast.system_palette(_user32(colors=colors))
        self.assertEqual(set(palette), set(theme.PALETTE))
        self.assertEqual(palette["bg"], "#000000")
        self.assertEqual(palette["text"], "#ffff00")
        self.assertEqual(palette["accent"], "#0080ff")


class TestApplyTheme(unittest.TestCase):
    def setUp(self):
        saved_palette, saved_status = dict(theme.PALETTE), dict(theme.STATUS_COLORS)

        def restore():
            theme.PALETTE.clear()
            theme.PALETTE.update(saved_palette)
            theme.STATUS_COLORS.clear()
            theme.STATUS_COLORS.update(saved_status)

        self.addCleanup(restore)

    def test_high_contrast_replaces_the_palette_and_skips_sv_ttk(self):
        system = {key: "#000000" for key in theme.PALETTE}
        system.update(text="#ffff00", error="#00ffff")
        style = MagicMock()
        with (
            patch("autoclicker.gui.theme.system_palette", return_value=system),
            patch("autoclicker.gui.theme.sv_ttk") as sv,
        ):
            colors = theme.apply_theme(MagicMock(), style=style)
        sv.set_theme.assert_not_called()
        style.theme_use.assert_called_once_with("clam")
        self.assertEqual(colors["text"], "#ffff00")
        self.assertEqual(theme.PALETTE["text"], "#ffff00")  # widgets reading PALETTE follow
        self.assertEqual(theme.STATUS_COLORS["error"], "#00ffff")

    def test_default_look_is_unchanged(self):
        before = dict(theme.PALETTE)
        with patch("autoclicker.gui.theme.sv_ttk") as sv:
            theme.apply_theme(MagicMock(), style=MagicMock())
        sv.set_theme.assert_called_once_with("dark")
        self.assertEqual(theme.PALETTE, before)


if __name__ == "__main__":
    unittest.main()
