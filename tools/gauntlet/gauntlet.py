#!/usr/bin/env python3
"""gauntlet.py - the Gauntlet: small, hard, machine-graded agentic coding tasks (see DESIGN.md).

  gauntlet.py run   <url> <outdir> [--only 01,02]    one model through every task (OpenAI endpoint at <url>/v1)
  gauntlet.py score <outdir> ...                     pass/10, tokens, seconds, decode tok/s during the run

Uses tools/taskeval's chat() (same request shape, TASKEVAL_THINK_BUDGET, timings recording) and parse_calls().
Each task's workspace is staged in a temp dir; the model gets list_files / read_file / write_file / run_tests /
submit; after it submits (or runs out of steps) the hidden tests are copied in and pytest decides pass / fail.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "taskeval"))
import taskeval as T  # noqa: E402

fn = T.fn
TOOLS = [fn("list_files", "List the workspace's files.", {}),
         fn("read_file", "Read a workspace file.", {"path": {"type": "string"}}, ["path"]),
         fn("write_file", "Create or overwrite a workspace file (tests are read-only).",
            {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
         fn("run_tests", "Run the workspace's visible pytest tests; returns their output (truncated).", {}),
         fn("run_python", "Run a Python snippet with the workspace as the current directory (20 s limit); returns "
            "stdout + stderr (truncated).", {"code": {"type": "string"}}, ["code"]),
         fn("submit", "Finish: your work is graded now.", {"note": {"type": "string"}})]
SYSTEM = ("You are a careful senior engineer working as a coding agent in a small Python workspace. You can only act "
          "through the tools. The visible tests are not the whole grade: hidden tests check the documented behaviour. "
          "Fix causes, not symptoms. Call submit when you are done.")


def _pytest(d: Path, hidden: bool) -> tuple[bool, str]:
    files = sorted(str(p.relative_to(d)) for p in d.rglob("test_*.py") if p.name.startswith("test_hidden_") == hidden)
    if not files:
        return True, "no tests"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *files], cwd=d,
                       capture_output=True, text=True, timeout=300)
    return r.returncode == 0, (r.stdout + r.stderr)[-4000:]


def _safe(d: Path, p: str) -> Path | None:
    q = (d / p.lstrip("/")).resolve()
    return q if str(q).startswith(str(d.resolve())) else None


def run_task(url: str, task: Path) -> dict:
    meta = json.loads((task / "task.json").read_text())
    d = Path(tempfile.mkdtemp(prefix="gauntlet-run-"))
    shutil.copytree(task / "workspace", d, dirs_exist_ok=True)
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": meta["prompt"]}]
    log, toks, secs, test_runs, py_runs, submitted = [], 0, 0.0, 0, 0, False
    for _ in range(meta.get("max_steps", 12)):
        j = T.chat(url, msgs, TOOLS, max_tokens=4096)
        toks += j.get("usage", {}).get("completion_tokens", 0)
        secs += j["_secs"]
        m = j["choices"][0]["message"]
        calls = T.parse_calls(m)
        log.append({"content": m.get("content"), "calls": calls})
        if not calls:
            msgs.append({"role": "assistant", "content": m.get("content") or ""})
            msgs.append({"role": "user", "content": "Use the tools (call submit when you are done)."})
            continue
        msgs.append({"role": "assistant", "content": m.get("content") or "", "tool_calls": m["tool_calls"]})
        for c in calls:
            a, name = c["args"], c["name"]
            if name == "list_files":
                res = "\n".join(sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()
                                       and "__pycache__" not in p.parts))
            elif name == "read_file":
                p = _safe(d, a.get("path", ""))
                res = p.read_text() if p and p.is_file() else f"error: no such file {a.get('path')}"
            elif name == "write_file":
                p = _safe(d, a.get("path", ""))
                if not p or p.name.startswith("test_"):
                    res = "error: tests are read-only (and paths must stay in the workspace)"
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(a.get("content", ""))
                    res = f"wrote {len(a.get('content', ''))} bytes to {p.relative_to(d)}"
            elif name == "run_tests":
                test_runs += 1
                res = "error: test-run limit reached" if test_runs > meta.get("max_test_runs", 6) else _pytest(d, False)[1]
            elif name == "run_python":
                py_runs += 1
                if py_runs > meta.get("max_python_runs", 12):
                    res = "error: run_python limit reached"
                else:
                    try:
                        r = subprocess.run([sys.executable, "-c", a.get("code", "")], cwd=d, capture_output=True,
                                           text=True, timeout=20)
                        res = (r.stdout + r.stderr)[-4000:] or "(no output)"
                    except subprocess.TimeoutExpired:
                        res = "error: timed out after 20 s"
            elif name == "submit":
                submitted, res = True, "submitted"
            else:
                res = f"error: unknown tool {name}"
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": res})
        if submitted:
            break
    shutil.copytree(task / "hidden", d, dirs_exist_ok=True)
    ok, out = _pytest(d, True)
    shutil.rmtree(d, ignore_errors=True)
    return {"id": meta["id"], "ok": ok, "submitted": submitted, "steps": len(log), "test_runs": test_runs,
            "tokens": toks, "secs": round(secs, 1), "hidden_output": out[-1500:], "log": log}


def run(url, out, only):
    os.makedirs(out, exist_ok=True)
    tasks = sorted(p for p in (HERE / "tasks").iterdir() if p.is_dir() and (not only or p.name[:2] in only))
    res = []
    for t in tasks:
        r = run_task(url, t)
        res.append(r)
        print(f"{r['id']}: {'PASS' if r['ok'] else 'fail'} ({r['steps']} steps, {r['tokens']} tok, {r['secs']:.0f}s)", flush=True)
    json.dump({"tasks": res, "timings": T.TIMINGS}, open(os.path.join(out, "gauntlet.json"), "w"), indent=1)


def score(dirs):
    print(f"{'run':28s} {'pass':>6s} {'tok':>7s} {'secs':>6s} {'decode tok/s':>13s}  passed")
    for d in dirs:
        g = json.load(open(os.path.join(d, "gauntlet.json")))
        ts = [t["timings"] for t in g.get("timings", []) if t.get("timings")]
        dn, dms = sum(t.get("predicted_n", 0) for t in ts), sum(t.get("predicted_ms", 0) for t in ts)
        rs = g["tasks"]
        print(f"{os.path.basename(d.rstrip('/')):28s} {sum(r['ok'] for r in rs):>3d}/{len(rs):<2d} "
              f"{sum(r['tokens'] for r in rs):>7d} {sum(r['secs'] for r in rs):>6.0f} "
              f"{1000 * dn / max(dms, 1e-9):>13.1f}  {' '.join(r['id'][:2] for r in rs if r['ok'])}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
        run(sys.argv[2], sys.argv[3], only)
    else:
        score(sys.argv[2:])
