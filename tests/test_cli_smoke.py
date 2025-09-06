import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.cli import main


class TestCLISmoke(unittest.TestCase):
    def test_cli_graph_smoke(self):
        p = Path(__file__).resolve().parents[1] / "examples" / "minimal.woofnb"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["graph", str(p)])
        out = buf.getvalue().strip().split()  # lines
        self.assertEqual(rc, 0)
        self.assertEqual(out, ["data1", "mean", "test1"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
