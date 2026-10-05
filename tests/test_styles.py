"""Theme-aware text colors meet WCAG AA contrast (#104)."""

import unittest
from unittest.mock import MagicMock

from autoclicker.gui.styles import ERROR, MUTED, TEXT_COLORS, apply_text_styles

# sv_ttk window backgrounds (sv_ttk/theme/light.tcl and dark.tcl, "-bg").
BACKGROUNDS = {"light": "#fafafa", "dark": "#1c1c1c"}


def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class TestContrast(unittest.TestCase):
    def test_every_text_color_meets_aa(self):
        for theme, colors in TEXT_COLORS.items():
            for style, color in colors.items():
                with self.subTest(theme=theme, style=style):
                    self.assertGreaterEqual(contrast(color, BACKGROUNDS[theme]), 4.5)

    def test_old_gray_failed(self):
        self.assertLess(contrast("#8b949e", BACKGROUNDS["light"]), 4.5)


class TestApply(unittest.TestCase):
    def test_configures_both_styles_for_the_theme(self):
        style = MagicMock()
        apply_text_styles("dark", style=style)
        style.configure.assert_any_call(MUTED, foreground=TEXT_COLORS["dark"][MUTED])
        style.configure.assert_any_call(ERROR, foreground=TEXT_COLORS["dark"][ERROR])

    def test_unknown_theme_uses_light_and_errors_are_swallowed(self):
        style = MagicMock()
        apply_text_styles("sepia", style=style)
        style.configure.assert_any_call(MUTED, foreground=TEXT_COLORS["light"][MUTED])
        style.configure.side_effect = RuntimeError("no Tk")
        apply_text_styles("light", style=style)  # does not raise


if __name__ == "__main__":
    unittest.main()
