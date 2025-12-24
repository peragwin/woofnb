import sys
import json
import traceback
import io
from contextlib import redirect_stdout, redirect_stderr
from .runner import _cell_attempt_exec

class Kernel:
    def __init__(self):
        self.g = {"__name__": "__main__", "woof": {}}

    def run(self):
        """Main loop: read JSON from stdin, execute, write JSON to stdout."""
        # Use unbuffered stdin/stdout wrapper or just flush manually
        stdin = sys.stdin
        stdout = sys.stdout

        while True:
            try:
                line = stdin.readline()
                if not line:
                    break

                req = json.loads(line)
                cmd = req.get("command")

                if cmd == "run_cell":
                    self.handle_run_cell(req, stdout)
                elif cmd == "ping":
                    self.send_response(stdout, {"status": "ok", "id": req.get("id")})
                else:
                    self.send_error(stdout, "Unknown command", req.get("id"))

            except KeyboardInterrupt:
                break
            except Exception as e:
                # Top level error in loop
                self.send_error(stdout, str(e))

    def handle_run_cell(self, req: dict, stdout):
        req_id = req.get("id")
        code = req.get("code", "")

        # runner._cell_attempt_exec returns {"outputs": [...]}
        result = _cell_attempt_exec(code, self.g, timeout=None)

        resp = {
            "id": req_id,
            "status": "ok",
            "outputs": result.get("outputs", [])
        }
        self.send_response(stdout, resp)

    def send_response(self, stdout, data: dict):
        json.dump(data, stdout, ensure_ascii=False)
        stdout.write("\n")
        stdout.flush()

    def send_error(self, stdout, msg: str, req_id=None):
        resp = {
            "id": req_id,
            "status": "error",
            "error": msg
        }
        json.dump(resp, stdout)
        stdout.write("\n")
        stdout.flush()

def main():
    k = Kernel()
    k.run()

if __name__ == "__main__":
    main()
