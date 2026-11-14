"""Adding and editing hold, key and wait steps from the window (#119)."""

import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from autoclicker.core.screen import ScreenBounds
from tests.test_gui_lifecycle import GuiHarness, _settle


class TestAddSteps(GuiHarness):
    def setUp(self):
        super().setUp()
        self.app.target_mode_var.set("sequence")
        self.app._apply_target_mode_state()
        self.picker = self.picker_cls.return_value

    def pick_point(self, x, y):
        self.picker.start_picking.call_args.kwargs["on_selected"](x, y)

    def run_after(self, trigger):
        """Call ``trigger`` and run what it schedules with root.after right away."""
        with patch.object(self.app.root, "after") as after:
            trigger()
        _delay, fn, *args = after.call_args.args
        fn(*args)

    def test_add_menu_lists_every_type(self):
        with patch("autoclicker.gui.features.steps.tk.Menu") as menu_cls:
            self.app.show_add_step_menu()
        labels = [c.kwargs["label"] for c in menu_cls.return_value.add_command.call_args_list]
        self.assertEqual(
            labels, ["Click point…", "Hold…", "Key…", "Wait for image…", "Wait for pixel…"]
        )

    def test_add_key_step_asks_again_until_the_key_is_valid(self):
        self.simpledialog.askstring.side_effect = ["nope", "Ctrl+S"]
        self.app.add_step("key")
        self.messagebox.showerror.assert_called_once()
        self.assertIn("Unknown key: nope", self.messagebox.showerror.call_args.args[1])
        self.assertEqual(
            self.app.sequence_steps, [{"type": "key", "key": "ctrl+s", "delay_ms": 500}]
        )
        self.assertEqual(self.app.settings.get("sequence"), self.app.sequence_steps)  # saved

    def test_cancelled_key_prompt_adds_nothing(self):
        self.simpledialog.askstring.return_value = None
        self.app.add_step("key")
        self.assertEqual(self.app.sequence_steps, [])

    def test_add_hold_step(self):
        self.simpledialog.askfloat.return_value = 750.0
        self.app.add_step("hold")
        self.pick_point(40, 50)
        self.assertEqual(
            self.app.sequence_steps,
            [{"type": "hold", "x": 40, "y": 50, "button": "left", "hold_ms": 750,
              "delay_ms": 500}],
        )  # fmt: skip

    def test_add_wait_pixel_step_reads_the_color(self):
        self.app.add_step("wait_pixel")
        with patch("pyautogui.pixel", return_value=(58, 123, 213)):
            self.run_after(lambda: self.pick_point(70, 80))
        (step,) = self.app.sequence_steps
        self.assertEqual((step["type"], step["x"], step["y"]), ("wait_pixel", 70, 80))
        self.assertEqual(step["color"], "#3a7bd5")

    def capture(self, trigger):
        self.picker.start_selecting_area.return_value = True
        trigger()
        on_selected = self.picker.start_selecting_area.call_args.kwargs["on_selected"]
        with patch(
            "autoclicker.gui.features.steps.grab",
            return_value=Image.new("RGB", (40, 20), (9, 9, 9)),
        ):
            self.run_after(lambda: on_selected(ScreenBounds(500, 400, 40, 20)))

    def test_add_wait_image_step_saves_its_own_capture(self):
        self.capture(lambda: self.app.add_step("wait_image"))
        (step,) = self.app.sequence_steps
        self.assertEqual(step["type"], "wait_image")
        self.assertEqual(step["image_region"], [500, 400, 40, 20])
        self.assertTrue(Path(step["image_path"]).name.startswith("step-"))
        self.assertTrue(Path(step["image_path"]).is_file())

    def test_full_sequence_adds_nothing(self):
        self.app.sequence_steps = [{"type": "key", "key": "a", "delay_ms": 0}] * 50
        self.app.add_step("key")
        self.simpledialog.askstring.assert_not_called()
        self.assertIn("at most 50 steps", self.app.status_var.get())

    def test_steps_added_from_the_window_run(self):
        """A key, a pixel wait and an image wait that clicks, end to end on the click thread."""
        app = self.app
        self.simpledialog.askstring.return_value = "enter"
        app.add_step("key")
        app.add_step("wait_pixel")
        with patch("pyautogui.pixel", return_value=(1, 2, 3)):
            self.run_after(lambda: self.pick_point(10, 10))
        self.capture(lambda: app.add_step("wait_image"))
        app.toggle_step_click(2)
        for step in app.sequence_steps:
            step["delay_ms"] = 0
        self.set_fields(interval="0", sequence_repeat="1")
        self.pyautogui.pixel.return_value = (1, 2, 3)
        with patch("autoclicker.core.image_match.ImageTarget.locate", return_value=(520, 410)):
            app.start_clicking()
            _settle(app)
        self.assertEqual(app.status_var.get(), "Done: ran the sequence 1 time")
        self.pyautogui.press.assert_called_once_with("enter")
        self.pyautogui.click.assert_called_once_with(x=520, y=410, button="left", clicks=1)


class TestEditSteps(GuiHarness):
    def setUp(self):
        super().setUp()
        self.app.sequence_steps = [
            {"type": "hold", "x": 1, "y": 1, "button": "left", "hold_ms": 500, "delay_ms": 0},
            {"type": "key", "key": "f5", "delay_ms": 0},
            {"type": "wait_image", "image_path": "a.png", "image_region": [0, 0, 5, 5],
             "image_tolerance": 0, "timeout_ms": 0, "on_timeout": "stop", "click": False,
             "delay_ms": 0},
            {"type": "wait_pixel", "x": 2, "y": 2, "color": "#000000", "tolerance": 16,
             "timeout_ms": 0, "on_timeout": "stop", "delay_ms": 0},
        ]  # fmt: skip
        self.app._refresh_sequence_list()

    def menu_labels(self, index):
        with (
            patch("autoclicker.gui.features.sequence.tk.Menu") as menu_cls,
            patch("autoclicker.gui.features.steps.tk.StringVar"),
            patch("autoclicker.gui.features.steps.tk.BooleanVar"),
            patch("autoclicker.gui.features.sequence.tk.StringVar"),
        ):
            self.app._sequence_step_menu(index)
        menu = menu_cls.return_value
        return [
            c.kwargs["label"]
            for name in ("add_command", "add_checkbutton", "add_radiobutton")
            for c in getattr(menu, name).call_args_list
        ]

    def test_each_type_offers_its_own_settings(self):
        self.assertIn("Hold time…", self.menu_labels(0))
        self.assertIn("Key…", self.menu_labels(1))
        image = self.menu_labels(2)
        self.assertIn("Capture the image again…", image)
        self.assertIn("Click the image when it appears", image)
        self.assertIn("Timeout (none)…", image)
        self.assertIn("If it times out: go to the next step", image)
        self.assertNotIn("Left button", image)  # no click, so no button to choose
        pixel = self.menu_labels(3)
        self.assertIn("Pick the pixel again…", pixel)
        self.assertIn("Color tolerance (16)…", pixel)

    def test_edit_hold_time_and_key(self):
        self.simpledialog.askfloat.return_value = 1200.0
        self.app.edit_hold_time(0)
        self.assertEqual(self.app.sequence_steps[0]["hold_ms"], 1200)
        self.simpledialog.askstring.return_value = "Alt+Tab"
        self.app.edit_step_key(1)
        self.assertEqual(self.app.sequence_steps[1]["key"], "alt+tab")

    def test_timeout_is_asked_in_seconds_and_stored_in_ms(self):
        self.simpledialog.askfloat.return_value = 2.5
        self.app.edit_step_timeout(3)
        self.assertEqual(self.app.sequence_steps[3]["timeout_ms"], 2500)
        self.app.set_sequence_step(3, on_timeout="skip")
        self.assertEqual(self.app.settings.get("sequence")[3]["on_timeout"], "skip")

    def test_toggle_click_adds_and_removes_the_button(self):
        self.app.toggle_step_click(2)
        step = self.app.sequence_steps[2]
        self.assertTrue(step["click"])
        self.assertEqual((step["button"], step["click_type"]), ("left", "single"))
        self.assertIn("Left button", self.menu_labels(2))
        self.app.toggle_step_click(2)
        self.assertNotIn("button", self.app.sequence_steps[2])

    def test_tolerance(self):
        self.simpledialog.askinteger.return_value = 40
        self.app.edit_step_tolerance(3)
        self.assertEqual(self.app.sequence_steps[3]["tolerance"], 40)


if __name__ == "__main__":
    unittest.main()
