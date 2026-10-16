#!/usr/bin/env python3
"""validate.py - every Gauntlet task must be valid before any model is graded on it:

  start      hidden tests FAIL on the starting workspace (otherwise there is nothing to do)
  reference  visible AND hidden tests PASS with reference/ applied (otherwise the task is impossible / wrong)
  trap       (if trap/ exists) visible tests PASS and hidden tests FAIL with trap/ applied (the trap is tempting AND caught)

  python3 tools/gauntlet/validate.py [task-dir ...]      (default: every tasks/NN-*)
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pytest_ok(d: Path, which: str) -> bool:
    files = sorted(str(p.relative_to(d)) for p in d.rglob("test_*.py")
                   if (which == "hidden") == p.name.startswith("test_hidden_"))
    if not files:
        return True
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *files], cwd=d,
                       capture_output=True, text=True, timeout=300)
    return r.returncode == 0


def stage(task: Path, overlay: str | None) -> Path:
    d = Path(tempfile.mkdtemp(prefix="gauntlet-"))
    shutil.copytree(task / "workspace", d, dirs_exist_ok=True)
    if overlay:
        shutil.copytree(task / overlay, d, dirs_exist_ok=True)
    shutil.copytree(task / "hidden", d, dirs_exist_ok=True)
    return d


def validate(task: Path) -> bool:
    checks = []
    d = stage(task, None)
    checks.append(("start: hidden FAIL", not pytest_ok(d, "hidden")))
    shutil.rmtree(d)
    d = stage(task, "reference")
    checks.append(("reference: visible PASS", pytest_ok(d, "visible")))
    checks.append(("reference: hidden PASS", pytest_ok(d, "hidden")))
    shutil.rmtree(d)
    if (task / "trap").is_dir():
        d = stage(task, "trap")
        checks.append(("trap: visible PASS (tempting)", pytest_ok(d, "visible")))
        checks.append(("trap: hidden FAIL (caught)", not pytest_ok(d, "hidden")))
        shutil.rmtree(d)
    ok = all(c[1] for c in checks)
    print(f"{'OK  ' if ok else 'BAD '} {task.name}: " + ", ".join(f"{n} {'yes' if v else 'NO'}" for n, v in checks))
    return ok


if __name__ == "__main__":
    tasks = [Path(a).resolve() for a in sys.argv[1:]] or sorted(p for p in (HERE / "tasks").iterdir() if p.is_dir())
    sys.exit(0 if all([validate(t) for t in tasks]) else 1)
