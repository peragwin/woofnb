import json
import sys
import tempfile
from pathlib import Path

import unittest

# Ensure 'src' is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.parse import parse_file
from woofnb.jupyter import woof_to_ipynb_dict, ipynb_dict_to_woof
from woofnb.cli import main


class TestJupyterInterop(unittest.TestCase):
    def test_programmatic_roundtrip_preserves_ids_types_bodies(self):
        p = Path(__file__).resolve().parents[1] / "examples" / "minimal.woofnb"
        nb1 = parse_file(str(p))

        nb_json = woof_to_ipynb_dict(nb1)
        nb2 = ipynb_dict_to_woof(nb_json)

        self.assertEqual([c.id for c in nb1.cells], [c.id for c in nb2.cells])
        self.assertEqual([c.type for c in nb1.cells], [c.type for c in nb2.cells])
        self.assertEqual([c.body for c in nb1.cells], [c.body for c in nb2.cells])

    def test_cli_export_import_smoke(self):
        p = Path(__file__).resolve().parents[1] / "examples" / "minimal.woofnb"
        with tempfile.TemporaryDirectory() as td:
            ipynb_path = Path(td) / "roundtrip.ipynb"
            wnb_path = Path(td) / "roundtrip.woofnb"

            # Export to ipynb
            rc1 = main(["export", str(p), "-o", str(ipynb_path)])
            self.assertEqual(rc1, 0)
            self.assertTrue(ipynb_path.exists())
            data = json.loads(ipynb_path.read_text(encoding="utf-8"))
            self.assertIn("cells", data)
            self.assertIsInstance(data["cells"], list)

            # Import back to woofnb
            rc2 = main(["import", str(ipynb_path), "-o", str(wnb_path)])
            self.assertEqual(rc2, 0)
            self.assertTrue(wnb_path.exists())

            nb_back = parse_file(str(wnb_path))
            nb_orig = parse_file(str(p))
            self.assertEqual(len(nb_back.cells), len(nb_orig.cells))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

