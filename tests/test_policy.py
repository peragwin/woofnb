import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from woofnb.cli import main


def nb_header(io_policy: str = "") -> str:
    base = ["%WOOFNB 1.0", "execution:", "  order: linear"]
    if io_policy:
        base.append("io_policy:")
        base.extend([f"  {line}" for line in io_policy.splitlines() if line.strip()])
    return "\n".join(base) + "\n\n"


def fence(id_: str, type_: str, tokens: str = "", body: str = "pass\n") -> str:
    token_str = (" " + tokens.strip()) if tokens.strip() else ""
    return f"```cell id={id_} type={type_}{token_str}\n{body}\n```\n"


class TestPolicy(unittest.TestCase):
    def _run_nb(self, text: str, expect_ok: bool):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "p.woofnb"
            p.write_text(text, encoding="utf-8")
            rc = main(["run", str(p)])
            if expect_ok:
                self.assertEqual(rc, 0)
            else:
                self.assertNotEqual(rc, 0)
            return p.with_suffix(p.suffix + ".out")

    def test_files_blocked_by_default(self):
        nb = nb_header() + fence("fs1", "code", body='open("tmp.txt","w").write("x")\n')
        self._run_nb(nb, expect_ok=False)

    def test_files_require_policy_and_sidefx(self):
        # Policy true but missing sidefx=fs should still block
        pol = "allow_files: true"
        nb = nb_header(pol) + fence(
            "fs1", "code", body='open("tmp.txt","w").write("x")\n'
        )
        self._run_nb(nb, expect_ok=False)
        # Now add sidefx=fs -> allowed
        nb2 = nb_header(pol) + fence(
            "fs2", "code", tokens="sidefx=fs", body='open("tmp.txt","w").write("x")\n'
        )
        self._run_nb(nb2, expect_ok=True)

    def test_network_blocked_and_then_allowed(self):
        nb = nb_header() + fence(
            "net1", "code", body="import socket; socket.socket()\n"
        )
        self._run_nb(nb, expect_ok=False)
        pol = "allow_network: true"
        nb2 = nb_header(pol) + fence(
            "net2",
            "code",
            tokens="sidefx=net",
            body='import socket; socket.socket(); print("ok")\n',
        )
        self._run_nb(nb2, expect_ok=True)

    def test_bash_requires_shell_policy(self):
        nb = nb_header() + fence("sh1", "bash", body='print("hi")\n')
        self._run_nb(nb, expect_ok=False)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
