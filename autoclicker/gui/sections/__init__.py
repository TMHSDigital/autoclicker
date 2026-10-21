# SPDX-License-Identifier: CC-BY-NC-4.0
"""GUI section builders for the main window."""

from .advanced import build_safety_panel, build_timing_panel
from .click_settings import build_click_panel
from .coordinates import build_target_panel
from .footer import build_footer_section
from .header import build_header_section
from .hero import build_hero_section

__all__ = [
    "build_click_panel",
    "build_footer_section",
    "build_header_section",
    "build_hero_section",
    "build_safety_panel",
    "build_target_panel",
    "build_timing_panel",
]
