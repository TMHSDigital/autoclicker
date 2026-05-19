# SPDX-License-Identifier: CC-BY-NC-4.0
"""GUI section builders for the main window."""

from .click_settings import build_click_settings_section
from .control import build_control_section
from .coordinates import build_coordinate_section
from .disclaimer import build_disclaimer_section
from .status import build_status_section
from .title import build_title_section

__all__ = [
    "build_click_settings_section",
    "build_control_section",
    "build_coordinate_section",
    "build_disclaimer_section",
    "build_status_section",
    "build_title_section",
]
