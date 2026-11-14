"""Sequences: edit steps in place, list shortcuts, undo for Remove and Record (#175)."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.test_gui_lifecycle import GuiHarness


class TestSequenceEditing(GuiHarness):
    def setUp(self):
        super().setUp()
        app = self.app
        app.sequence_steps = [
            {"x": x, "y": x, "button": "left", "click_type": "single", "delay_ms": 500}
            for x in (10, 20, 30)
        ]
        app._refresh_sequence_list()

    def select(self, index):
        self.app.sequence_list.curselection.return_value = (index,)

    def xs(self):
        return [step["x"] for step in self.app.sequence_steps]

    def test_change_button_and_click_type_in_place(self):
        app = self.app
        app.set_sequence_step(1, button="right")
        app.set_sequence_step(1, click_type="double")
        self.assertEqual(
            (app.sequence_steps[1]["button"], app.sequence_steps[1]["click_type"]),
            ("right", "double"),
        )
        self.assertEqual(app.settings.get("sequence")[1]["button"], "right")  # saved
        app.set_sequence_step(9, button="middle")  # out of range is ignored

    def test_repick_moves_only_the_point(self):
        app = self.app
        app.sequence_steps[1]["delay_ms"] = 75
        app.repick_sequence_point(1)
        picked = self.picker_cls.return_value.start_picking.call_args.kwargs["on_selected"]
        picked(400, 300)
        step = app.sequence_steps[1]
        self.assertEqual((step["x"], step["y"], step["delay_ms"]), (400, 300, 75))
        self.assertEqual(self.xs(), [10, 400, 30])

    def test_duplicate_inserts_a_copy_after(self):
        self.app.duplicate_sequence_step(0)
        self.assertEqual(self.xs(), [10, 10, 20, 30])
        self.app.sequence_steps[1]["x"] = 11
        self.assertEqual(self.app.sequence_steps[0]["x"], 10)  # a copy, not the same dict

    def test_remove_then_undo(self):
        app = self.app
        self.select(1)
        app.remove_sequence_step()
        self.assertEqual(self.xs(), [10, 30])
        self.assertIn("Removed step 2", app.status_var.get())
        app.undo_sequence_change()
        self.assertEqual(self.xs(), [10, 20, 30])
        self.assertEqual(len(app.settings.get("sequence")), 3)
        app.undo_sequence_change()  # only one level
        self.assertEqual(app.status_var.get(), "Nothing to undo")

    def test_keys_on_the_list(self):
        app = self.app
        self.select(2)
        self.assertEqual(app._on_sequence_key("up"), "break")
        self.assertEqual(self.xs(), [10, 30, 20])
        self.select(1)
        app._on_sequence_key("down")
        self.assertEqual(self.xs(), [10, 20, 30])
        self.select(0)
        app._on_sequence_key("delete")
        self.assertEqual(self.xs(), [20, 30])
        app._on_sequence_key("undo")
        self.assertEqual(self.xs(), [10, 20, 30])

    def test_record_replace_can_be_undone(self):
        app = self.app
        app._recorder = MagicMock()
        app._recorded = []
        self.messagebox.askyesnocancel.return_value = True  # replace
        new_steps = [{"x": 1, "y": 1, "button": "left", "click_type": "single", "delay_ms": 0}]
        with patch("autoclicker.gui.features.recording.clicks_to_steps", return_value=new_steps):
            app._finish_recording()
        self.assertEqual(self.xs(), [1])
        app.undo_sequence_change()
        self.assertEqual(self.xs(), [10, 20, 30])

    def test_menu_offers_every_edit(self):
        app = self.app
        self.select(0)
        with (
            patch("autoclicker.gui.features.sequence.tk.Menu") as menu_cls,
            patch("autoclicker.gui.features.sequence.tk.StringVar"),
        ):
            app.show_sequence_step_menu()
        menu = menu_cls.return_value
        labels = [c.kwargs["label"] for c in menu.add_command.call_args_list]
        self.assertEqual(labels, ["Re-pick point…", "Wait after this step…", "Duplicate"])
        radios = [c.kwargs["label"] for c in menu.add_radiobutton.call_args_list]
        self.assertEqual(len(radios), 5)  # three buttons, single and double
        menu.tk_popup.assert_called_once()

    def test_menu_offers_only_what_a_step_type_uses(self):
        app = self.app
        app.sequence_steps[0] = {"type": "key", "key": "f5", "delay_ms": 0}
        app.sequence_steps[1] = {
            "type": "hold", "x": 1, "y": 1, "button": "left", "hold_ms": 500, "delay_ms": 0
        }  # fmt: skip
        for index, commands, radios in (
            (0, ["Wait after this step…", "Duplicate"], 0),  # key: no point, no button
            (1, ["Re-pick point…", "Wait after this step…", "Duplicate"], 3),  # hold: buttons
        ):
            self.select(index)
            with (
                self.subTest(step=index),
                patch("autoclicker.gui.features.sequence.tk.Menu") as menu_cls,
                patch("autoclicker.gui.features.sequence.tk.StringVar"),
            ):
                app.show_sequence_step_menu()
                menu = menu_cls.return_value
                labels = [c.kwargs["label"] for c in menu.add_command.call_args_list]
                self.assertEqual(labels, commands)
                self.assertEqual(menu.add_radiobutton.call_count, radios)

    def test_menu_needs_a_selected_step(self):
        self.app.sequence_list.curselection.return_value = ()
        with patch("autoclicker.gui.features.sequence.tk.Menu") as menu_cls:
            self.app.show_sequence_step_menu()
        menu_cls.assert_not_called()
        self.assertEqual(self.app.status_var.get(), "Select a step first")

    def test_double_click_selects_the_step_under_the_pointer(self):
        app = self.app
        app.sequence_list.nearest.return_value = 2
        self.select(2)
        event = SimpleNamespace(y=40, x_root=5, y_root=6)
        with (
            patch("autoclicker.gui.features.sequence.tk.Menu"),
            patch("autoclicker.gui.features.sequence.tk.StringVar"),
        ):
            app.show_sequence_step_menu(event)
        app.sequence_list.selection_set.assert_called_with(2)


if __name__ == "__main__":
    unittest.main()
