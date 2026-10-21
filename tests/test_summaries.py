"""Pure text summaries for the hero readouts and the collapsed panels."""

import unittest

from autoclicker.gui.summaries import (
    Stats,
    click_summary,
    format_stats,
    safety_summary,
    timing_summary,
)

_CLICK_DEFAULTS = dict(
    mouse_button="left",
    click_type="single",
    action="click",
    interval="100",
    interval_unit="ms",
    variation="0",
    hold_ms="500",
    key="",
)
_TIMING_DEFAULTS = dict(burst_clicks="1", burst_pause="100", start_delay="3", start_at="")
_SAFETY_DEFAULTS = dict(
    limit_clicks=False,
    max_clicks="100",
    auto_stop_minutes="0",
    max_cps="50",
    condition="none",
    failsafe=True,
    pause_unfocused=False,
)


class TestFormatStats(unittest.TestCase):
    def test_running_status_fills_every_tile(self):
        status = {
            "is_running": True,
            "click_count": 1284,
            "runtime": "00:02:11",
            "performance": {"clicks_per_second": 9.84, "success_rate": 100.0},
        }
        self.assertEqual(format_stats(status), Stats("1,284", "00:02:11", "9.8/s"))

    def test_no_performance_shows_dashes(self):
        status = {"is_running": False, "click_count": 0, "runtime": "00:00:00"}
        self.assertEqual(format_stats(status).rate, "--")

    def test_zero_rate_while_stopped_shows_dashes(self):
        status = {
            "is_running": False,
            "click_count": 0,
            "runtime": "00:00:00",
            "performance": {"clicks_per_second": 0},
        }
        self.assertEqual(format_stats(status).rate, "--")

    def test_zero_rate_while_running_is_shown(self):
        status = {
            "is_running": True,
            "click_count": 0,
            "runtime": "00:00:01",
            "performance": {"clicks_per_second": 0},
        }
        self.assertEqual(format_stats(status).rate, "0.0/s")


class TestClickSummary(unittest.TestCase):
    def summary(self, **overrides):
        return click_summary(**{**_CLICK_DEFAULTS, **overrides})

    def test_default_single_click(self):
        self.assertEqual(self.summary(), "Left click · every 100 ms")

    def test_double_click_and_button(self):
        self.assertEqual(
            self.summary(mouse_button="right", click_type="double"),
            "Double right click · every 100 ms",
        )

    def test_seconds_unit(self):
        self.assertEqual(
            self.summary(interval="1.5", interval_unit="seconds").split(" · ")[1], "every 1.5 s"
        )

    def test_variation_is_appended_when_set(self):
        self.assertEqual(self.summary(variation="20"), "Left click · every 100 ms ± 20 ms")

    def test_hold_action(self):
        self.assertEqual(
            self.summary(action="hold", hold_ms="250"), "Hold left 250 ms · every 100 ms"
        )

    def test_key_action(self):
        self.assertEqual(self.summary(action="key", key="f5"), "Press f5 · every 100 ms")

    def test_blank_key_shows_placeholder(self):
        self.assertTrue(self.summary(action="key", key="  ").startswith("Press ?"))

    def test_garbage_numbers_fall_back_to_placeholder(self):
        self.assertEqual(self.summary(interval="abc", variation="x"), "Left click · every ? ms")

    def test_integer_valued_floats_print_as_integers(self):
        self.assertEqual(self.summary(interval="100.0"), "Left click · every 100 ms")


class TestTimingSummary(unittest.TestCase):
    def summary(self, **overrides):
        return timing_summary(**{**_TIMING_DEFAULTS, **overrides})

    def test_defaults_show_the_start_delay(self):
        self.assertEqual(self.summary(), "3 s delay")

    def test_nothing_set(self):
        self.assertEqual(self.summary(start_delay="0"), "no delay · no burst")

    def test_burst_delay_and_schedule(self):
        self.assertEqual(
            self.summary(burst_clicks="3", burst_pause="50", start_at="09:30"),
            "burst of 3, 50 ms apart · 3 s delay · at 09:30",
        )

    def test_garbage_counts_as_unset(self):
        self.assertEqual(self.summary(burst_clicks="x", start_delay=""), "no delay · no burst")


class TestSafetySummary(unittest.TestCase):
    def summary(self, **overrides):
        return safety_summary(**{**_SAFETY_DEFAULTS, **overrides})

    def test_defaults(self):
        self.assertEqual(self.summary(), "failsafe on · no limit")

    def test_click_and_time_limits(self):
        self.assertEqual(
            self.summary(limit_clicks=True, max_clicks="1000", auto_stop_minutes="10"),
            "failsafe on · stop after 1,000 clicks or 10 min",
        )

    def test_time_limit_only(self):
        self.assertEqual(
            self.summary(limit_clicks=True, max_clicks="0", auto_stop_minutes="10"),
            "failsafe on · stop after 10 min",
        )

    def test_limit_toggle_off_hides_values(self):
        self.assertEqual(
            self.summary(max_clicks="1000", auto_stop_minutes="10"), "failsafe on · no limit"
        )

    def test_speed_limit_shown_only_when_changed(self):
        self.assertIn("max 20/s", self.summary(max_cps="20"))
        self.assertIn("speed limit off", self.summary(max_cps="0"))
        self.assertNotIn("max 50/s", self.summary())

    def test_condition_failsafe_and_focus(self):
        text = self.summary(condition="wait", failsafe=False, pause_unfocused=True)
        self.assertEqual(text, "failsafe off · no limit · wait for pixel · pause when unfocused")
        self.assertIn("stop on pixel", self.summary(condition="stop"))


if __name__ == "__main__":
    unittest.main()
