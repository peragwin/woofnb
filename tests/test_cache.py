import json
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.cli import main

NB_HEADER = "%WOOFNB 1.0\nexecution:\n  order: linear\n  cache: content-hash\n"


def make_nb(code: str) -> str:
    return NB_HEADER + "\n" + "```cell id=hello type=code\n" + code + "\n```\n"


class TestCache(unittest.TestCase):
    def test_content_hash_cache(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cachetest.woofnb"
            p.write_text(make_nb('print("hi")'), encoding="utf-8")

            # First run: not cached
            rc1 = main(["run", str(p)])
            self.assertEqual(rc1, 0)
            sidecar = p.with_suffix(p.suffix + ".out")
            recs1 = [json.loads(line) for line in sidecar.read_text().splitlines()]
            self.assertEqual(len(recs1), 1)
            self.assertNotIn("cached", recs1[0])

            # Second run: cached
            rc2 = main(["run", str(p)])
            self.assertEqual(rc2, 0)
            recs2 = [json.loads(line) for line in sidecar.read_text().splitlines()]
            self.assertEqual(len(recs2), 1)
            self.assertTrue(recs2[0].get("cached", False))

            # Modify code: cache miss
            p.write_text(make_nb('print("bye")'), encoding="utf-8")
            rc3 = main(["run", str(p)])
            self.assertEqual(rc3, 0)
            recs3 = [json.loads(line) for line in sidecar.read_text().splitlines()]
            self.assertEqual(len(recs3), 1)
            self.assertFalse(recs3[0].get("cached", False))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
