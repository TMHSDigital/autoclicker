"""Every attribute a section builder sets on the app is declared in AppBase (#170)."""

import ast
import unittest
from pathlib import Path

from autoclicker.gui.features.base import AppBase

SECTIONS = Path(__file__).resolve().parent.parent / "autoclicker" / "gui" / "sections"


def _assigned_attributes() -> set[str]:
    names = set()
    for path in SECTIONS.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            targets = node.targets if isinstance(node, ast.Assign) else []
            if isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                for item in target.elts if isinstance(target, ast.Tuple) else [target]:
                    if (
                        isinstance(item, ast.Attribute)
                        and isinstance(item.value, ast.Name)
                        and item.value.id == "app"
                    ):
                        names.add(item.attr)
    return names


class TestBuilderAttributes(unittest.TestCase):
    def test_declared_in_appbase(self):
        declared = set(dir(AppBase))
        for klass in AppBase.__mro__:
            declared |= set(getattr(klass, "__annotations__", {}))
        missing = sorted(_assigned_attributes() - declared)
        self.assertEqual(missing, [], "declare these in gui/features/base.py AppBase")

    def test_found_some(self):
        self.assertGreater(len(_assigned_attributes()), 30)


if __name__ == "__main__":
    unittest.main()
