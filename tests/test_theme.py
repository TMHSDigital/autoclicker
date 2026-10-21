"""Dark control-panel theme tokens: contrast and application."""

import unittest
from unittest.mock import MagicMock, patch

from autoclicker.gui import theme
from autoclicker.gui.styles import ERROR, MUTED, PANEL, SEGMENT


def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class TestPalette(unittest.TestCase):
    def test_text_tokens_meet_aa_on_both_backgrounds(self):
        p = theme.PALETTE
        for token in ("text", "muted", "error", "accent_strong"):
            for bg in ("bg", "surface"):
                with self.subTest(token=token, bg=bg):
                    self.assertGreaterEqual(contrast(p[token], p[bg]), 4.5)

    def test_run_button_text_meets_aa_on_every_fill(self):
        p = theme.PALETTE
        for fill in ("accent", "warning", "error"):
            with self.subTest(fill=fill):
                self.assertGreaterEqual(contrast(p["on_accent"], p[fill]), 4.5)

    def test_segment_text_meets_aa_on_segment_fill(self):
        p = theme.PALETTE
        self.assertGreaterEqual(contrast(p["accent_strong"], p["accent_soft"]), 4.5)

    def test_status_colors_cover_every_state(self):
        self.assertEqual(set(theme.STATUS_COLORS), {"running", "stopped", "alert", "error"})
        self.assertEqual(theme.STATUS_COLORS["error"], theme.PALETTE["error"])


class TestApply(unittest.TestCase):
    def setUp(self):
        theme._listeners.clear()
        self.addCleanup(theme._listeners.clear)

    def test_applies_dark_sv_ttk_styles_and_listeners(self):
        style = MagicMock()
        seen = []
        theme.register(seen.append)
        with patch("autoclicker.gui.theme.sv_ttk") as sv:
            result = theme.apply_theme(MagicMock(), style=style)
        sv.set_theme.assert_called_once_with("dark")
        p = theme.PALETTE
        style.configure.assert_any_call(MUTED, background=p["surface"], foreground=p["muted"])
        style.configure.assert_any_call(ERROR, background=p["surface"], foreground=p["error"])
        style.configure.assert_any_call(PANEL, background=p["surface"])
        style.configure.assert_any_call("Bg.TFrame", background=p["bg"])
        self.assertTrue(
            any(c.args[0] == SEGMENT for c in style.map.call_args_list),
            "segmented controls get a selected-state map",
        )
        self.assertEqual(seen, [p])
        self.assertIs(result, p)
        self.assertIs(theme.current(), p)

    def test_labels_drop_the_palette_defaults_so_styles_win(self):
        """sv_ttk's tk_setPalette puts *background in the option database, and a
        ttk label's own option beats its style; blank it for labels."""
        root = MagicMock()
        with patch("autoclicker.gui.theme.sv_ttk"):
            theme.apply_theme(root, style=MagicMock())
        root.option_add.assert_any_call("*TLabel.background", "")
        root.option_add.assert_any_call("*TLabel.foreground", "")
        root.option_add.assert_any_call("*TLabel.font", "")  # *Font would hide Stat fonts

    def test_surface_matches_the_sv_ttk_card(self):
        """Card.TFrame is an image sv_ttk draws in its own gray; panel bodies must match."""
        self.assertEqual(theme.PALETTE["surface"], "#1c1c1c")

    def test_errors_are_swallowed(self):
        style = MagicMock()
        style.configure.side_effect = RuntimeError("no Tk")
        theme.register(MagicMock(side_effect=RuntimeError("dead widget")))
        with patch("autoclicker.gui.theme.sv_ttk"):
            theme.apply_theme(MagicMock(), style=style)  # does not raise

    def test_dimming_swaps_label_foregrounds(self):
        style = MagicMock()
        theme.set_dimmed(True, style=style)
        style.configure.assert_any_call("TLabel", foreground=theme.PALETTE["muted"])
        theme.set_dimmed(False, style=style)
        style.configure.assert_any_call("TLabel", foreground=theme.PALETTE["text"])

    def test_dimming_errors_are_swallowed(self):
        style = MagicMock()
        style.configure.side_effect = RuntimeError("no Tk")
        theme.set_dimmed(True, style=style)  # does not raise


if __name__ == "__main__":
    unittest.main()
