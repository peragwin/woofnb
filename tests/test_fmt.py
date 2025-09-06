import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.fmt import format_text


class TestFmt(unittest.TestCase):
    def _header_lines(self, text: str):
        lines = text.splitlines()
        # find magic
        i = 0
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        assert lines[i].startswith("%WOOFNB ")
        i += 1
        out = []
        while i < len(lines) and not lines[i].lstrip().startswith("```cell"):
            out.append(lines[i])
            i += 1
        return out

    def test_header_ordering_and_idempotence(self):
        text = (
            "%WOOFNB 1.0\n"
            "io_policy:\n  allow_files: false\n"
            "name: sample\n"
            "execution:\n  order: graph\n"
            "language: python\n"
            "metadata:\n  note: x\n"
            "version: 1\n"
            "\n"
            "```cell id=a type=md\n# title\n```\n"
        )
        formatted1 = format_text(text)
        formatted2 = format_text(formatted1)
        self.assertEqual(formatted1, formatted2)
        hdr = self._header_lines(formatted2)
        keys_in_order = [
            "name:",
            "language:",
            "env:",
            "parameters:",
            "defaults:",
            "execution:",
            "io_policy:",
            "provenance:",
            "metadata:",
            "tags:",
            "version:",
        ]
        # Create a map from key prefix to first index or large index if missing
        pos = {k: 10_000 for k in keys_in_order}
        for idx, line in enumerate(hdr):
            for k in keys_in_order:
                if line.startswith(k) and pos[k] == 10_000:
                    pos[k] = idx
        # Ensure monotonic non-decreasing order for those present
        last = -1
        for k in keys_in_order:
            if pos[k] != 10_000:
                self.assertGreaterEqual(pos[k], last, f"key out of order: {k}")
                last = pos[k]


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

