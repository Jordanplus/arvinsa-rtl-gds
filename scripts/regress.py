#!/usr/bin/env python3
"""make regress: the whole regression in one command (project-plan.md §7.5, §8 Phase 4, §10 item 1).

usage: regress.py [--list]

Runs these make targets in this order, each as its own `make <target>`, and stops at the first one
that FAILs (later targets use earlier results, e.g. eqy-soc uses the run of harden-soc):
  RTL and firmware (Phase 1)   env-check-flow py-check lint synth-check fw core-stock regress-rtl neg-rtl
  checkers of the flow         neg-provenance neg-run-guard test-flow-retry
  soc_top (Phase 3, 4)         harden-soc eqy-soc neg-eqy-soc gl-soc gl-soc-powered neg-gl-soc neg-pnr
  PicoRV32 alone (Phase 2)     harden-core gl-core neg-gl-core eqy-core neg-eqy-core
  end                          provenance-final (HEAD unchanged, working tree still clean)
A target PASSes only if `make <target>` exits 0; every script behind a target exits 0 only on its
own PASS. Outputs: runs/regress/<target>.log (full output), runs/regress/summary.md (target,
result, minutes, the last line of its output), runs/regress/junit.xml (one testcase per target).
Needs a committed working tree (harden-soc and harden-core check it). About 2.5 hours on the
development machine (Apple M-series, 10 cores).
Prints `regress: PASS n/n` / `regress: FAIL at <target>`; exit code 0 only on PASS.
"""
import os
import shutil
import subprocess
import sys
import time
from xml.sax.saxutils import escape

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "runs", "regress")
TARGETS = [
    "env-check-flow", "py-check", "lint", "synth-check", "fw", "core-stock", "regress-rtl", "neg-rtl",
    "neg-provenance", "neg-run-guard", "test-flow-retry",
    "harden-soc", "eqy-soc", "neg-eqy-soc", "gl-soc", "gl-soc-powered", "neg-gl-soc", "neg-pnr",
    "harden-core", "gl-core", "neg-gl-core", "eqy-core", "neg-eqy-core",
    "provenance-final",
]


def last_line(text):
    lines = [x for x in text.splitlines() if x.strip()]
    return lines[-1].strip() if lines else ""


def main():
    if "--list" in sys.argv[1:]:
        print(" ".join(TARGETS))
        return 0
    shutil.rmtree(OUT, ignore_errors=True)  # only runs/regress is removed
    os.makedirs(OUT)
    make = os.environ.get("MAKE", "make")
    rows, t_all = [], time.time()
    for t in TARGETS:
        t0 = time.time()
        log = os.path.join(OUT, f"{t}.log")
        print(f"[regress] {t} ...", flush=True)
        with open(log, "w") as f:
            rc = subprocess.run([make, "--no-print-directory", t], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        text = open(log, errors="replace").read()
        rows.append((t, rc, time.time() - t0, last_line(text)))
        print(f"[regress] {t}: {'PASS' if rc == 0 else 'FAIL'} ({(time.time() - t0) / 60:.1f} min) {last_line(text)}", flush=True)
        if rc != 0:
            break
    passed = sum(1 for _, rc, _, _ in rows if rc == 0)
    ok = passed == len(TARGETS)
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write(f"# make regress\n\ncommit `{head}`; {passed}/{len(TARGETS)} targets PASS; "
                f"{(time.time() - t_all) / 60:.0f} min\n\n| # | target | result | min | last line |\n|---|---|---|---|---|\n")
        for i, (t, rc, dt, line) in enumerate(rows, 1):
            f.write(f"| {i} | `{t}` | {'PASS' if rc == 0 else 'FAIL'} | {dt / 60:.1f} | {line.replace('|', '/')} |\n")
        for t in TARGETS[len(rows):]:
            f.write(f"| - | `{t}` | not run | - | - |\n")
    with open(os.path.join(OUT, "junit.xml"), "w") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="regress" tests="{len(TARGETS)}" '
                f'failures="{len(rows) - passed}" skipped="{len(TARGETS) - len(rows)}" time="{time.time() - t_all:.0f}">\n')
        for t, rc, dt, line in rows:
            f.write(f'  <testcase classname="make" name="{t}" time="{dt:.0f}">')
            if rc != 0:
                f.write(f'<failure message="{escape(line, {chr(34): "&quot;"})}">see runs/regress/{t}.log</failure>')
            f.write("</testcase>\n")
        for t in TARGETS[len(rows):]:
            f.write(f'  <testcase classname="make" name="{t}"><skipped message="not run: an earlier target FAILed"/></testcase>\n')
        f.write("</testsuite>\n")
    print(f"regress: PASS {passed}/{len(TARGETS)}" if ok else f"regress: FAIL at {rows[-1][0]} ({passed}/{len(TARGETS)} PASS)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
