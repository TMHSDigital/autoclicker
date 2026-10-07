"""Docs Blue theme tokens: contrast and application."""

import unittest
from unittest.mock import MagicMock, patch

from autoclicker.gui import theme
from autoclicker.gui.styles import ERROR, MUTED


def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class TestPalettes(unittest.TestCase):
    def test_both_modes_have_every_token(self):
        self.assertEqual(set(theme.PALETTES["light"]), set(theme.PALETTES["dark"]))

    def test_text_tokens_meet_aa_on_both_backgrounds(self):
        for mode, p in theme.PALETTES.items():
            for token in ("text", "muted", "error", "accent_strong"):
                for bg in ("bg", "surface"):
                    with self.subTest(mode=mode, token=token, bg=bg):
                        self.assertGreaterEqual(contrast(p[token], p[bg]), 4.5)

    def test_pill_and_button_text_meet_aa(self):
        for mode, p in theme.PALETTES.items():
            with self.subTest(mode=mode):
                self.assertGreaterEqual(contrast(p["accent_strong"], p["accent_soft"]), 4.5)
                self.assertGreaterEqual(contrast(p["on_accent"], p["accent"]), 4.5)

    def test_unknown_mode_is_light(self):
        self.assertIs(theme.palette("sepia"), theme.PALETTES["light"])


class TestApply(unittest.TestCase):
    def setUp(self):
        theme._listeners.clear()
        self.addCleanup(theme._listeners.clear)

    def test_runs_sv_ttk_styles_and_listeners(self):
        style = MagicMock()
        seen = []
        theme.register(seen.append)
        with patch("autoclicker.gui.theme.sv_ttk") as sv:
            theme.apply_theme(MagicMock(), "dark", style=style)
        sv.set_theme.assert_called_once_with("dark")
        style.configure.assert_any_call(MUTED, foreground=theme.PALETTES["dark"]["muted"])
        style.configure.assert_any_call(ERROR, foreground=theme.PALETTES["dark"]["error"])
        self.assertEqual(seen, [theme.PALETTES["dark"]])
        self.assertIs(theme.current(), theme.PALETTES["dark"])

    def test_errors_are_swallowed(self):
        style = MagicMock()
        style.configure.side_effect = RuntimeError("no Tk")
        theme.register(MagicMock(side_effect=RuntimeError("dead widget")))
        with patch("autoclicker.gui.theme.sv_ttk"):
            theme.apply_theme(MagicMock(), "light", style=style)  # does not raise


if __name__ == "__main__":
    unittest.main()
