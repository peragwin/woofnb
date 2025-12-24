import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.cli import main


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[1]
        self.example = self.repo / "examples" / "minimal.woofnb"
        # Clean sidecar if exists
        sidecar = self.example.with_suffix(self.example.suffix + ".out")
        if sidecar.exists():
            sidecar.unlink()

    def _read_sidecar(self):
        sidecar = self.example.with_suffix(self.example.suffix + ".out")
        self.assertTrue(sidecar.exists(), "sidecar should be created")
        return [
            json.loads(line)
            for line in sidecar.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_run_and_sidecar(self):
        rc = main(["run", str(self.example)])
        self.assertEqual(rc, 0)
        lines = self._read_sidecar()
        # Expect records for data1, mean, test1 (skipping md/raw)
        ids = [rec["cell"] for rec in lines]
        self.assertEqual(ids, ["data1", "mean", "test1"])
        # mean should print a number; capture stdout stream record
        mean_rec = next(rec for rec in lines if rec["cell"] == "mean")
        streams = [
            o
            for o in mean_rec["outputs"]
            if o.get("output_type") == "stream" and o.get("name") == "stdout"
        ]
        self.assertTrue(streams, "expected stdout stream for mean cell")

    def test_test_mode(self):
        rc = main(["test", str(self.example)])
        self.assertEqual(rc, 0)
        # Only deps of test cells + test cells should execute; here all three still run
        lines = self._read_sidecar()
        ids = [rec["cell"] for rec in lines]
        self.assertEqual(ids, ["data1", "mean", "test1"])

    def test_run_single_cell_no_deps(self):
        # Only the specified cell should run
        rc = main(["run", str(self.example), "--cell", "test1", "--no-deps"])
        self.assertEqual(rc, 0)
        lines = self._read_sidecar()
        ids = [rec["cell"] for rec in lines]
        self.assertEqual(ids, ["test1"])  # no deps included

    def test_run_single_cell_with_deps(self):
        # Selected cell should run with its transitive dependencies by default
        rc = main(
            ["run", str(self.example), "--cell", "test1"]
        )  # include deps (default)
        self.assertEqual(rc, 0)
        lines = self._read_sidecar()
        ids = [rec["cell"] for rec in lines]
        self.assertEqual(ids, ["data1", "mean", "test1"])  # deps + target in order


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
