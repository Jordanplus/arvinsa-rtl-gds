#!/usr/bin/env python3
"""make neg-run-guard: bug injection into the input of every step that uses a harden run; each
step must refuse the run (signoff/scripts/run_guard.py, known limitation 12 of
docs/phase_exit/phase3.md) and remove its old output.

usage: neg_run_guard.py

Fake runs in runs/neg_run_guard/<case>/ have only <run>_signoff/result.txt and provenance.json:
  not_pass      result.txt says `harden-<x>: FAIL`             refused: "does not say"
  other_commit  provenance.json repo_head = 000...0           refused: "was made from commit"
  no_record     no provenance.json                            refused: "cannot read the source record"
  current       PASS and repo_head = HEAD (positive control): the step must get past the guard
                (no guard message) and FAIL later for a missing file
For each case the step's output directory first holds a file stale.txt, which must be gone
afterwards (a refused run leaves no output of an earlier run behind).
Steps: run_eqy.py (soc_top, picorv32_core), run_gl_soc.py, run_gl_core.py, neg_eqy.py (soc_top,
picorv32_core), neg_gl_soc.py, neg_gl_core.py, neg_pnr.py. Prints `neg-run-guard: PASS n/n` / `FAIL ...`; exit
code 0 only on PASS.
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "runs", "neg_run_guard")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_guard import guard, head  # noqa: E402

PY = sys.executable
S = lambda *p: os.path.join(ROOT, *p)  # noqa: E731
# (name, design, command with {run} and {out}, verdict line printed on FAIL)
STEPS = [
    ("run_eqy_soc", "soc_top", [PY, S("signoff/eqy/run_eqy.py"), "--design", "soc_top", "--run", "{run}", "--out", "{out}"], "eqy: FAIL"),
    ("run_eqy_core", "picorv32_core", [PY, S("signoff/eqy/run_eqy.py"), "--design", "picorv32_core", "--run", "{run}", "--out", "{out}"], "eqy: FAIL"),
    ("run_gl_soc", "soc_top", [PY, S("dv/gl_soc/run_gl_soc.py"), "--harden-run", "{run}", "--out", "{out}"], "gl-soc: FAIL"),
    ("run_gl_core", "picorv32_core", [PY, S("dv/gl_core/run_gl_core.py"), "--harden-run", "{run}", "--out", "{out}"], "gl-core: FAIL"),
    ("neg_eqy_soc", "soc_top", [PY, S("signoff/eqy/neg_eqy.py"), "--design", "soc_top", "--run", "{run}", "--out", "{out}"], "neg-eqy: FAIL"),
    ("neg_eqy_core", "picorv32_core", [PY, S("signoff/eqy/neg_eqy.py"), "--design", "picorv32_core", "--run", "{run}", "--out", "{out}"], "neg-eqy: FAIL"),
    ("neg_gl_soc", "soc_top", [PY, S("dv/gl_soc/neg_gl_soc.py"), "--harden-run", "{run}", "--out", "{out}"], "neg-gl-soc: FAIL"),
    ("neg_gl_core", "picorv32_core", [PY, S("dv/gl_core/neg_gl_core.py"), "--harden-run", "{run}", "--out", "{out}"], "neg-gl-core: FAIL"),
    ("neg_pnr", "soc_top", [PY, S("pnr/soc_top/neg_pnr.py"), "--run", "{run}", "--out", "{out}"], "neg-pnr: FAIL"),
]
VERDICT = {"soc_top": "harden-soc: PASS", "picorv32_core": "harden-core: PASS"}
CASES = {"not_pass": "does not say", "other_commit": "was made from commit",
         "no_record": "cannot read the source record", "current": None}
GUARD_TEXT = [t for t in CASES.values() if t]


def fake_run(d, design, case):
    run = os.path.join(d, design)
    sign = run + "_signoff"
    os.makedirs(run)
    os.makedirs(sign)
    verdict = VERDICT[design] if case != "not_pass" else VERDICT[design].replace("PASS", "FAIL")
    open(os.path.join(sign, "result.txt"), "w").write(verdict + "\n")
    if case != "no_record":
        json.dump({"repo_head": "0" * 40 if case == "other_commit" else head()}, open(os.path.join(sign, "provenance.json"), "w"))
    return run


def main():
    shutil.rmtree(OUT, ignore_errors=True)  # only runs/neg_run_guard is removed
    os.makedirs(OUT)
    results = []
    # positive control of the guard itself
    d = os.path.join(OUT, "guard_current")
    errs = guard(fake_run(d, "soc_top", "current"), VERDICT["soc_top"])
    results.append(not errs)
    print(f"  [{'PASS' if not errs else 'FAIL'}] guard_current: run_guard.guard accepts a PASS run of HEAD {errs or ''}")
    for step, design, cmd, fail_line in STEPS:
        for case, want in CASES.items():
            d = os.path.join(OUT, f"{step}__{case}")
            run = fake_run(d, design, case)
            out = os.path.join(d, "out")
            os.makedirs(out)
            open(os.path.join(out, "stale.txt"), "w").write("output of an earlier run\n")
            cp = subprocess.run([c.format(run=run, out=out) for c in cmd], capture_output=True, text=True, timeout=600)
            text = cp.stdout + cp.stderr
            open(os.path.join(d, "run.log"), "w").write(text)
            stale_gone = not os.path.exists(os.path.join(out, "stale.txt"))
            failed = cp.returncode != 0 and fail_line in cp.stdout
            if want:
                ok = failed and want in cp.stdout and stale_gone
                what = f"refused ({want!r}), old output removed"
            else:
                ok = failed and not any(t in cp.stdout for t in GUARD_TEXT) and stale_gone
                what = "passed the guard, then FAILed for a missing file"
            results.append(ok)
            print(f"  [{'PASS' if ok else 'FAIL'}] {step} {case}: {what}"
                  + ("" if ok else f" (exit {cp.returncode}, stale removed {stale_gone}; see {os.path.relpath(d, ROOT)}/run.log)"))
    ok = all(results)
    print(f"neg-run-guard: {'PASS' if ok else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
