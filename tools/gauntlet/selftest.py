#!/usr/bin/env python3
"""selftest.py - proves gauntlet.py grades the three task shapes correctly, end to end.

This drives the REAL runner (`gauntlet.run_task`) in a subprocess against a canned OpenAI-shaped endpoint
(`http.server`, 127.0.0.1:<free port>), so nothing here reimplements the runner - it is the runner's own answer,
hidden-test and no-grader paths that are under test. Four checks, one line each; exit 0 only if all four hold:

  a) an exact-answer task whose canned final message MATCHES "answer" -> PASS
  b) the same task, canned message that does NOT match                 -> fail
  c) a task with no hidden/ and no "answer"                            -> a loud failure, never a silent pass
  d) the real 01-ledger-rootcause, driven by a canned model that writes the reference solution -> PASS
     (the hidden-test path is unharmed)

  python3 tools/gauntlet/selftest.py
"""
import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Canned(BaseHTTPRequestHandler):
    """Answers POST /v1/chat/completions from `seq`; past the end it repeats the last one."""
    seq = []
    n = 0

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        msg = Canned.seq[min(Canned.n, len(Canned.seq) - 1)]
        Canned.n += 1
        body = json.dumps(msg).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # keep the selftest's own output clean
        pass


def reply(content, calls=None):
    m = {"role": "assistant", "content": content}
    if calls:
        m["tool_calls"] = calls
    return {"id": "canned", "object": "chat.completion", "created": 0, "model": "canned",
            "choices": [{"index": 0, "message": m, "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}


def call(cid, name, args):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def make_task(root, name, meta, files=None):
    d = Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "task.json").write_text(json.dumps(meta))
    for rel, text in (files or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return d


def drive(url, task, canned):
    """Run the real runner on `task` in a subprocess and return its result dict."""
    Canned.seq, Canned.n = canned, 0
    code = ("import sys, json\n"
            "sys.path.insert(0, %r)\n"
            "import gauntlet\n"
            "from pathlib import Path\n"
            "print(json.dumps(gauntlet.run_task(%r, Path(%r))))\n" % (str(HERE), url, str(task)))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"runner subprocess died (rc={r.returncode}):\n{r.stderr[-2500:]}")
    return json.loads([ln for ln in r.stdout.strip().splitlines() if ln.startswith("{")][-1])


def main() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Canned)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    ans_meta = {"id": "selftest-answer", "category": "selftest", "max_steps": 3,
                "prompt": "What is the answer? Reply with the exact line 'answer: 42'. Then call submit.",
                "answer": r"answer:\s*42"}
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="gauntlet-selftest-") as tmp:
            ans = make_task(tmp, "answer-task", ans_meta)
            r = drive(url, ans, [reply("answer: 42", [call("c1", "submit", {"note": "done"})])])
            results.append(("a) answer task, final message MATCHES the regex -> PASS", r["ok"] is True))

            r = drive(url, ans, [reply("the answer is 43, sorry", [call("c1", "submit", {"note": "done"})])])
            results.append(("b) answer task, final message does NOT match -> fail", r["ok"] is False))

            bare = make_task(tmp, "bare-task", {"id": "selftest-bare", "category": "selftest", "max_steps": 2,
                                                "prompt": "Nothing to do here."},
                             {"workspace/notes.py": "x = 1\n"})
            r = drive(url, bare, [reply("done", [call("c1", "submit", {"note": "done"})])])
            loud = r["ok"] is False and "no hidden" in r["hidden_output"]
            results.append((f"c) no hidden/ + no answer -> loud failure, not a pass ({r['hidden_output'][:60]!r})", loud))

            real = HERE / "tasks" / "01-ledger-rootcause"
            ref = {rel: (real / "reference" / rel).read_text()
                   for rel in ("ledger/parse.py", "ledger/report.py")}
            r = drive(url, real, [reply("", [call("c1", "write_file", {"path": p, "content": c}) for p, c in ref.items()]),
                                  reply("fixed parse_amount", [call("c2", "submit", {"note": "done"})])])
            results.append(("d) real 01-ledger-rootcause, canned reference solution -> PASS", r["ok"] is True))
    finally:
        srv.shutdown()
    for line, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {line}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
