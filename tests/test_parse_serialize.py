import sys
import unittest
from pathlib import Path

# Ensure 'src' is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.parse import parse_file, parse_text
from woofnb.serialize import serialize


class TestParseSerialize(unittest.TestCase):
    def test_roundtrip_minimal(self):
        p = Path(__file__).resolve().parents[1] / "examples" / "minimal.woofnb"
        nb1 = parse_file(str(p))
        text = serialize(nb1)
        nb2 = parse_text(text)

        self.assertEqual([c.id for c in nb1.cells], [c.id for c in nb2.cells])
        self.assertEqual([c.type for c in nb1.cells], [c.type for c in nb2.cells])
        self.assertEqual([c.body for c in nb1.cells], [c.body for c in nb2.cells])
        self.assertEqual(nb1.header_text, nb2.header_text)

    def test_token_quotes_and_escapes(self):
        text = (
            "%WOOFNB 1.0\nname: quoted\nlanguage: python\n\n"
            '```cell id=a type=code name="train \\"model\\""'
            "\nprint(1)\n```\n"
        )
        nb = parse_text(text)
        cell = nb.cells[0]
        self.assertEqual(
            cell.header_tokens["name"], 'train "model"'
        )  # escaped quotes handled

        # Re-serialize and parse again; value should persist
        nb2 = parse_text(serialize(nb))
        self.assertEqual(nb2.cells[0].header_tokens["name"], 'train "model"')


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
