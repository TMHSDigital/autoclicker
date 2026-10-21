"""Custom widgets: run button, stat tile, panels. Tk is mocked throughout."""

import unittest
from unittest.mock import MagicMock, call, patch

from autoclicker.gui import theme
from autoclicker.gui.styles import (
    BG_FRAME,
    MUTED,
    PANEL,
    PANEL_HEADER,
    PANEL_HEADING,
    STAT,
    STAT_CAPTION,
)


class FakeVar:
    def __init__(self, master=None, value="", name=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class WidgetCase(unittest.TestCase):
    def setUp(self):
        patches = [
            patch("tkinter.Canvas", MagicMock()),
            patch("tkinter.ttk.Frame", MagicMock()),
            patch("tkinter.ttk.Label", MagicMock()),
            patch("tkinter.ttk.Button", MagicMock()),
            patch("tkinter.StringVar", FakeVar),
            patch("autoclicker.gui.widgets.run_button.ImageTk", MagicMock()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)


class TestRunButton(WidgetCase):
    def make(self):
        from autoclicker.gui.widgets.run_button import RunButton

        self.command = MagicMock()
        with patch("autoclicker.gui.widgets.run_button.rounded_rect") as self.shape:
            self.button = RunButton(MagicMock(), command=self.command)
        return self.button

    def texts(self):
        return [c.kwargs.get("text") for c in self.button.canvas.create_text.call_args_list]

    def bound(self, sequence):
        for c in self.button.canvas.bind.call_args_list:
            if c.args[0] == sequence:
                return c.args[1]
        self.fail(f"{sequence} not bound")

    def test_idle_shows_start_in_accent(self):
        self.make()
        self.assertEqual(self.shape.call_args.args[3], theme.PALETTE["accent"])
        self.assertIn("▶  START", self.texts())
        self.assertEqual(self.button.winfo_class(), "RunButton")

    def test_hotkey_is_the_caption(self):
        self.make()
        with patch("autoclicker.gui.widgets.run_button.rounded_rect"):
            self.button.set_hotkey("F6")
        self.assertIn("F6", self.texts())

    def test_running_is_red_stop(self):
        self.make()
        with patch("autoclicker.gui.widgets.run_button.rounded_rect") as shape:
            self.button.set_mode("running")
        self.assertEqual(shape.call_args.args[3], theme.PALETTE["error"])
        self.assertIn("■  STOP", self.texts())

    def test_countdown_is_amber_with_the_seconds(self):
        self.make()
        with patch("autoclicker.gui.widgets.run_button.rounded_rect") as shape:
            self.button.set_mode("countdown", detail="3")
        self.assertEqual(shape.call_args.args[3], theme.PALETTE["warning"])
        self.assertIn("STARTING IN 3", self.texts())

    def test_scheduled_countdown_puts_the_wait_in_the_caption(self):
        self.make()
        with patch("autoclicker.gui.widgets.run_button.rounded_rect"):
            self.button.set_mode("countdown", detail="in 2 h 5 min")
        self.assertIn("STARTING", self.texts())
        self.assertIn("in 2 h 5 min", self.texts())

    def test_same_mode_does_not_redraw(self):
        self.make()
        with patch("autoclicker.gui.widgets.run_button.rounded_rect") as shape:
            self.button.set_mode("idle")
        shape.assert_not_called()

    def test_click_and_keys_run_the_command_once_each(self):
        self.make()
        self.bound("<Button-1>")(MagicMock())
        self.bound("<Return>")(MagicMock())
        self.bound("<space>")(MagicMock())
        self.assertEqual(self.command.call_count, 3)

    def test_hover_brightens_idle_only(self):
        self.make()
        with patch("autoclicker.gui.widgets.run_button.rounded_rect") as shape:
            self.bound("<Enter>")(MagicMock())
            self.assertEqual(shape.call_args.args[3], theme.PALETTE["accent_strong"])
            self.bound("<Leave>")(MagicMock())
            self.assertEqual(shape.call_args.args[3], theme.PALETTE["accent"])
            self.button.set_mode("running")
            self.bound("<Enter>")(MagicMock())
            self.assertEqual(shape.call_args.args[3], theme.PALETTE["error"])

    def test_grid_delegates_to_the_canvas(self):
        self.make()
        self.button.grid(row=1, column=2, padx=3)
        self.button.canvas.grid.assert_called_once_with(row=1, column=2, padx=3)


class TestStatTile(WidgetCase):
    def test_builds_value_over_caption(self):
        import tkinter as tk
        from tkinter import ttk

        from autoclicker.gui.widgets.stat_tile import StatTile

        var = tk.StringVar(value="0")
        tile = StatTile(MagicMock(), caption="clicks", variable=var)
        ttk.Frame.assert_called_once()
        self.assertEqual(ttk.Frame.call_args.kwargs["style"], BG_FRAME)
        kwargs = [c.kwargs for c in ttk.Label.call_args_list]
        self.assertIn({"textvariable": var, "style": STAT}, kwargs)
        self.assertIn({"text": "CLICKS", "style": STAT_CAPTION}, kwargs)
        tile.grid(row=0, column=1)
        tile.frame.grid.assert_called_once_with(row=0, column=1)


class TestPanel(WidgetCase):
    def test_heading_is_upper_case_on_a_card(self):
        from tkinter import ttk

        from autoclicker.gui.widgets.panel import Panel

        panel = Panel(MagicMock(), "Target")
        self.assertEqual(ttk.Frame.call_args_list[0].kwargs["style"], PANEL)
        self.assertEqual(ttk.Label.call_args.kwargs["text"], "TARGET")
        self.assertEqual(ttk.Label.call_args.kwargs["style"], PANEL_HEADING)
        self.assertIsNotNone(panel.body)
        panel.body.grid_columnconfigure.assert_called_with(1, weight=1)


class TestCollapsiblePanel(WidgetCase):
    def make(self):
        from autoclicker.gui.widgets.panel import CollapsiblePanel

        return CollapsiblePanel(MagicMock(), "Timing")

    def test_starts_collapsed_with_a_summary(self):
        from tkinter import ttk

        panel = self.make()
        self.assertFalse(panel.expanded)
        self.assertEqual(ttk.Button.call_args.kwargs["style"], PANEL_HEADER)
        self.assertEqual(ttk.Button.call_args.kwargs["text"], "▸  TIMING")
        panel.body.grid_remove.assert_called_once()
        panel.set_summary("3 s delay")
        self.assertEqual(panel.summary_var.get(), "3 s delay")
        self.assertEqual(ttk.Label.call_args.kwargs["style"], MUTED)

    def test_toggle_swaps_body_and_summary(self):
        panel = self.make()
        panel.toggle()
        self.assertTrue(panel.expanded)
        panel.body.grid.assert_called()
        panel.summary.grid_remove.assert_called_once()
        panel.header.configure.assert_called_with(text="▾  TIMING")
        panel.toggle()
        self.assertFalse(panel.expanded)
        self.assertEqual(panel.body.grid_remove.call_count, 2)
        self.assertIn(call(text="▸  TIMING"), panel.header.configure.call_args_list)


if __name__ == "__main__":
    unittest.main()
