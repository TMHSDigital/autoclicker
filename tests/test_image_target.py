"""Image target mode (#87): matcher, engine, validation, controller and picker area mode."""

import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pyautogui
from PIL import Image, ImageDraw

from autoclicker.app.controller import _load_image_target
from autoclicker.core.click_engine import PAUSE_IMAGE, STOP_COMPLETED, ClickEngine
from autoclicker.core.image_match import ImageTarget, find_template, search_region
from autoclicker.core.screen import ScreenBounds
from autoclicker.core.settings_manager import SettingsManager


def _scene():
    hay = Image.new("RGB", (320, 240), (240, 240, 240))
    draw = ImageDraw.Draw(hay)
    for x in range(0, 320, 7):
        draw.line((x, 0, x, 240), fill=(230, 230, 230))
    draw.rectangle((200, 150, 260, 175), fill=(30, 120, 220))
    draw.rectangle((210, 158, 230, 166), fill=(255, 255, 255))
    return hay


class TestFindTemplate(unittest.TestCase):
    def test_finds_exact_position(self):
        hay = _scene()
        needle = hay.crop((195, 145, 265, 180))
        self.assertEqual(find_template(hay, needle), (195, 145))

    def test_missing_or_too_big(self):
        hay = _scene()
        self.assertIsNone(find_template(hay, Image.new("RGB", (10, 10), (1, 2, 3))))
        self.assertIsNone(find_template(hay, Image.new("RGB", (400, 10))))

    def test_match_at_the_edges(self):
        hay = _scene()
        ImageDraw.Draw(hay).rectangle((300, 228, 319, 239), fill=(200, 20, 90))  # unique marker
        corner = hay.crop((320 - 30, 240 - 20, 320, 240))
        self.assertEqual(find_template(hay, corner), (290, 220))

    def test_search_region_clips_to_desktop(self):
        desktop = ScreenBounds(0, 0, 1920, 1080)
        region = search_region(ScreenBounds(10, 1000, 50, 40), 100, desktop)
        self.assertEqual(region, ScreenBounds(0, 900, 160, 180))

    def test_locate_returns_screen_center(self):
        hay = _scene()
        target = ImageTarget(hay.crop((200, 150, 260, 176)), ScreenBounds(1000, 500, 320, 240))
        self.assertEqual(target.locate(grabber=lambda _r: hay), (1000 + 200 + 30, 500 + 150 + 13))
        self.assertIsNone(target.locate(grabber=lambda _r: Image.new("RGB", (320, 240))))


def _mock(m):
    m.size.return_value = (1920, 1080)
    m.FailSafeException = pyautogui.FailSafeException
    m.PyAutoGUIException = pyautogui.PyAutoGUIException


class TestEngineImageTarget(unittest.TestCase):
    @patch("autoclicker.core.click_engine.pyautogui")
    def test_clicks_where_found_and_waits_while_missing(self, m):
        _mock(m)
        positions = [None]
        target = MagicMock(spec=ImageTarget)
        target.locate.side_effect = lambda: positions[0]
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.configure_safety(failsafe=False, max_cps=0)
        done = threading.Event()
        outcomes = []
        engine.start_clicking(
            None, None, 0, 0, 1, 0, 3, 0, "left", "single",
            lambda o: (outcomes.append(o), done.set()), image=target,
        )  # fmt: skip
        time.sleep(0.3)
        self.assertTrue(engine.is_paused)
        self.assertEqual(engine.pause_reason, PAUSE_IMAGE)
        m.click.assert_not_called()
        positions[0] = (640, 360)
        self.assertTrue(done.wait(3))
        self.assertEqual(outcomes[0].reason, STOP_COMPLETED)
        m.click.assert_called_with(x=640, y=360, button="left", clicks=1)

    @patch("autoclicker.core.click_engine.pyautogui")
    def test_no_click_on_a_match_seen_before_the_last_click(self, m):
        """#96: clicking the image closes it; the old position must not be clicked again."""
        _mock(m)
        clicked = threading.Event()
        m.click.side_effect = lambda **_k: clicked.set()

        def locate():
            on_screen = not clicked.is_set()  # what the screenshot shows
            time.sleep(0.03)  # the search itself takes time
            return (640, 360) if on_screen else None

        target = MagicMock(spec=ImageTarget)
        target.locate.side_effect = locate
        engine = ClickEngine(enable_performance_monitoring=False)
        engine.configure_safety(failsafe=False, max_cps=0)
        engine.start_clicking(
            None, None, 0, 0, 1, 0, 0, 0, "left", "single", None, image=target
        )  # fmt: skip
        time.sleep(0.6)
        engine.stop_clicking()
        self.assertEqual(m.click.call_count, 1)
        self.assertTrue(engine.click_thread is None or not engine.click_thread.is_alive())


class TestImageSettings(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings = SettingsManager(os.path.join(self._dir.name, "s.json"))

    def validate(self, **raw):
        base = {"target_mode": "image", "x_coord": "unused", "action": "click"}
        return self.settings.validate_all_settings({**base, **raw}, 1920, 1080)

    def test_valid(self):
        result = self.validate(image_path="a.png", image_region=[10, 10, 300, 200])
        self.assertTrue(result["valid"], result["errors"])

    def test_errors(self):
        self.assertIn("image_path", self.validate(image_region=[0, 0, 5, 5])["errors"])
        self.assertIn(
            "image_region",
            self.validate(image_path="a.png", image_region=[1800, 0, 300, 50])["errors"],
        )
        self.assertIn("image_region", self.validate(image_path="a.png", image_region="x")["errors"])
        result = self.validate(
            image_path="a.png", image_region=[0, 0, 5, 5], action="key", key="f5"
        )
        self.assertIn("action", result["errors"])

    def test_ignored_in_other_modes(self):
        raw = {"target_mode": "fixed", "x_coord": "5", "y_coord": "5", "image_region": "junk"}
        self.assertTrue(self.settings.validate_all_settings(raw, 1920, 1080)["valid"])


class TestLoadImageTarget(unittest.TestCase):
    def test_loads_or_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.png")
            Image.new("RGB", (8, 6), (1, 2, 3)).save(path)
            target, error = _load_image_target({"image_path": path, "image_region": [0, 0, 50, 50]})
            self.assertIsNone(error)
            self.assertEqual(target.template.size, (8, 6))
            self.assertEqual(target.region, ScreenBounds(0, 0, 50, 50))
            target, error = _load_image_target(
                {"image_path": os.path.join(tmp, "missing.png"), "image_region": [0, 0, 5, 5]}
            )
            self.assertIsNone(target)
            self.assertIn("capture it again", error)


class TestPickerAreaMode(unittest.TestCase):
    def _picker(self):
        from autoclicker.gui.picker import CoordinatePicker

        self.canvas = MagicMock()
        return CoordinatePicker(
            MagicMock(),
            bounds=lambda: ScreenBounds(-100, 0, 1000, 800),
            toplevel_factory=lambda _root: MagicMock(),
            canvas_factory=lambda *_a, **_k: self.canvas,
        )

    @staticmethod
    def ev(x, y):
        return SimpleNamespace(x_root=x, y_root=y)

    def test_drag_selects_an_area(self):
        picker = self._picker()
        selected = []
        self.assertTrue(picker.start_selecting_area(selected.append))
        picker._on_click(self.ev(5, 5))  # the toplevel's click binding must not pick a point
        self.assertTrue(picker.is_picking())
        picker._on_drag_start(self.ev(300, 200))
        picker._on_drag(self.ev(250, 260))
        self.canvas.coords.assert_called_with(picker._rect, 400, 200, 350, 260)
        picker._on_drag_end(self.ev(240, 260))
        self.assertFalse(picker.is_picking())
        self.assertEqual(selected, [ScreenBounds(240, 200, 60, 60)])

    def test_tiny_drag_cancels(self):
        picker = self._picker()
        selected, cancelled = [], []
        picker.start_selecting_area(selected.append, lambda: cancelled.append(True))
        picker._on_drag_start(self.ev(10, 10))
        picker._on_drag_end(self.ev(12, 11))
        self.assertEqual(selected, [])
        self.assertEqual(cancelled, [True])


class TestLoadImageTargetSafety(unittest.TestCase):
    """#98/#100: never open network paths; oversized images are an error, not a crash."""

    def test_network_paths_are_refused(self):
        for path in ("\\\\server\\share\\x.png", "//server/share/x.png"):
            with self.subTest(path=path), patch("autoclicker.core.image_match.Image.open") as op:
                target, error = _load_image_target(
                    {"image_path": path, "image_region": [0, 0, 5, 5]}
                )
                self.assertIsNone(target)
                self.assertIn("local file", error)
                op.assert_not_called()

    def test_oversized_or_bomb_images_report_an_error(self):
        from PIL import Image as PILImage

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.png")
            PILImage.new("RGB", (10, 10)).save(path)
            for limit in (50, None):
                with self.subTest(limit=limit):
                    if limit is None:
                        ctx = patch(
                            "autoclicker.core.image_match.Image.open",
                            side_effect=PILImage.DecompressionBombError("bomb"),
                        )
                    else:
                        ctx = patch("autoclicker.core.image_match.MAX_TEMPLATE_PIXELS", limit)
                    with ctx:
                        target, error = _load_image_target(
                            {"image_path": path, "image_region": [0, 0, 5, 5]}
                        )
                    self.assertIsNone(target)
                    self.assertIn("unreadable", error)
