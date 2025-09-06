import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.parse import parse_text
from woofnb.lint import lint_notebook
from woofnb.plan import topo_order


class TestLintPlan(unittest.TestCase):
    def test_lint_ok_minimal(self):
        p = Path(__file__).resolve().parents[1] / "examples" / "minimal.woofnb"
        nb = parse_text(p.read_text(encoding="utf-8"))
        errors, warns = lint_notebook(nb)
        self.assertEqual(errors, [])

    def test_cycle_detection_and_topo_error(self):
        text = (
            "%WOOFNB 1.0\nname: cyc\nlanguage: python\n\n"
            "```cell id=a type=code deps=b\n```\n"
            "```cell id=b type=code deps=a\n```\n"
        )
        nb = parse_text(text)
        errors, _ = lint_notebook(nb)
        self.assertTrue(any("Cycle detected" in e.message for e in errors))
        with self.assertRaises(ValueError):
            topo_order(nb)

    def test_missing_dep_error(self):
        text = (
            "%WOOFNB 1.0\nname: miss\nlanguage: python\n\n"
            "```cell id=a type=code deps=b\n```\n"
        )
        nb = parse_text(text)
        errors, _ = lint_notebook(nb)
        self.assertTrue(any("depends on missing id" in e.message for e in errors))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
