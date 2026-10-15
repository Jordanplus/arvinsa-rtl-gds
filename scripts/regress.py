#!/usr/bin/env python3
"""make regress / make regress-picorv32: the whole regression in one command (project-plan.md §7.5,
§8 Phase 4, §10 item 1).

usage: regress.py [--cpu hazard3|picorv32|caravel] [--list]

--cpu picks the CPU of soc_top (ADR-0011 user decision 4): hazard3 (default, `make regress`, the
main design since Phase 5) or picorv32 (`make regress-picorv32`, the Phase 1-4 design); caravel
(`make regress-caravel`, Phase 7, ADR-0019 decision 25) is the Hazard3 SoC in the Caravel wrapper. Every
target runs with CPU=<cpu> in its environment (the Makefile's `CPU ?= picorv32` takes it), each as
its own `make <target>`, in this order, and the run stops at the first one that FAILs (later
targets use earlier results, e.g. eqy-soc uses the run of harden-soc):
  hazard3
  RTL and firmware             env-check-flow py-check lint synth-check fw core-hazard3 regress-rtl neg-rtl
                               regress-rtl-caravel neg-rtl-caravel (Caravel wrapper, Phase 7)
  checkers of the flow         neg-provenance neg-run-guard neg-regress test-flow-retry test-review-hook neg-openram neg-macro-views
                               pin-plan neg-pin-plan neg-precheck
  soc_top with Hazard3         harden-soc eqy-soc neg-eqy-soc gl-soc gl-soc-powered neg-gl-soc neg-pnr
                               ir-soc neg-ir-soc (IR with the max-power pattern, ADR-0019 decision 25)
  end                          provenance-final (HEAD unchanged, working tree still clean)
  caravel (the wrapper's own targets; the checkers it shares with soc_top are qualified by make regress)
  RTL                          env-check-flow py-check lint regress-rtl-caravel neg-rtl-caravel
  checkers of the flow         pin-plan neg-pin-plan neg-precheck
  wrapper                      harden-caravel eqy-caravel neg-eqy-caravel gl-caravel neg-gl-caravel
                               ir-caravel neg-ir-caravel neg-pnr-caravel precheck-caravel (the official image in the
                               lima VM: env-check-flow checks it with CPU=caravel)
  end                          provenance-final
  picorv32
  RTL and firmware (Phase 1)   env-check-flow py-check lint synth-check fw core-stock regress-rtl neg-rtl
  checkers of the flow         neg-provenance neg-run-guard neg-regress test-flow-retry test-review-hook neg-openram neg-macro-views
                               pin-plan neg-pin-plan neg-precheck
  soc_top (Phase 3, 4)         harden-soc eqy-soc neg-eqy-soc gl-soc gl-soc-powered neg-gl-soc neg-pnr
  PicoRV32 alone (Phase 2)     harden-core gl-core neg-gl-core eqy-core neg-eqy-core
  end                          provenance-final
A target PASSes only if `make <target>` exits 0; every script behind a target exits 0 only on its
own PASS. Before the first target: the working tree must be clean (no modified, staged or untracked
file) and MAKEFLAGS must not carry -i (ignore errors: a FAIL would exit 0), -n, -q or -t (nothing
would run); the HEAD is recorded and must be the same after the last target, so every target ran
on that one commit (Phase 4 review: provenance-final alone compares only the harden records).
The disk holding the checkout must have at least REGRESS_MIN_FREE_GB (default 100) GiB free:
a full disk made one 2026-10-15 regression FAIL on a write error and left another one hanging in an
STA with no error and no end (ADR-0021 decision 3; each regress worktree keeps 40-70 GB of
negative-test intermediates). Every target has a time limit, 3 x its reference time from the
2026-10-15 closing runs (REF_MIN) and at least 30 minutes, times REGRESS_TIMEOUT_SCALE (default 1);
a target over its limit is killed with its whole process group and FAILs with
`regress: TIMEOUT <target> after <n> min (limit <m> min: ...)` in its log, so a hang reads as a hang.
The group gets SIGTERM, then SIGKILL; a process that starts its own session (a docker or lima
container) is outside the group and is not stopped.
make neg-regress (scripts/neg_regress.py) checks these refusals and the timeout. Outputs (runs/regress for hazard3,
runs/regress_picorv32 for picorv32): <target>.log (full output), summary.md (target, result,
minutes, the last line of its output), junit.xml (one testcase per target).
Needs a committed working tree (harden-soc and harden-core check it). A clean worktree has no .tools/:
LIBRELANE_DIR and XPACK_DIR (hazard3: core-hazard3) point at installed copies; env-check-flow checks both. About 2.5 hours on the
development machine (Apple M-series, 10 cores) for picorv32.
Prints `regress: PASS n/n` / `regress: FAIL at <target>`; exit code 0 only on PASS.
"""
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from xml.sax.saxutils import escape

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTS = {"hazard3": os.path.join(ROOT, "runs", "regress"), "picorv32": os.path.join(ROOT, "runs", "regress_picorv32"),
        "caravel": os.path.join(ROOT, "runs", "regress_caravel")}
SOC = ["harden-soc", "eqy-soc", "neg-eqy-soc", "gl-soc", "gl-soc-powered", "neg-gl-soc", "neg-pnr"]
FLOW_CHECKERS = ["neg-provenance", "neg-run-guard", "neg-regress", "test-flow-retry", "test-review-hook", "neg-openram", "neg-macro-views",
                 "pin-plan", "neg-pin-plan", "neg-precheck"]
TARGET_LISTS = {
    "hazard3": ["env-check-flow", "py-check", "lint", "synth-check", "fw", "core-hazard3", "regress-rtl", "neg-rtl",
                "regress-rtl-caravel", "neg-rtl-caravel"]
               + FLOW_CHECKERS + SOC + ["ir-soc", "neg-ir-soc", "provenance-final"],
    "picorv32": ["env-check-flow", "py-check", "lint", "synth-check", "fw", "core-stock", "regress-rtl", "neg-rtl"]
                + FLOW_CHECKERS + SOC
                + ["harden-core", "gl-core", "neg-gl-core", "eqy-core", "neg-eqy-core", "provenance-final"],
    "caravel": ["env-check-flow", "py-check", "lint", "regress-rtl-caravel", "neg-rtl-caravel", "pin-plan", "neg-pin-plan",
                "neg-precheck", "harden-caravel", "eqy-caravel", "neg-eqy-caravel", "gl-caravel", "neg-gl-caravel",
                "ir-caravel", "neg-ir-caravel", "neg-pnr-caravel", "precheck-caravel", "provenance-final"],
}


# reference minutes: the longest of the 2026-10-15 closing runs (docs/phase_exit/phase7.md, the three
# runs/regress*/summary.md); targets not listed take the 30-minute floor
REF_MIN = {"harden-caravel": 287, "precheck-caravel": 99, "harden-soc": 53, "neg-eqy-soc": 47, "neg-eqy-core": 48,
           "ir-caravel": 29, "neg-eqy-caravel": 25, "gl-soc-powered": 24, "neg-pnr": 23, "harden-core": 21,
           "gl-caravel": 17, "eqy-caravel": 14, "neg-precheck": 14, "gl-soc": 13, "neg-gl-core": 12, "neg-gl-soc": 10}
MIN_TIMEOUT_MIN = 30
TIMEOUT_FACTOR = 3


def timeout_min(target):
    scale = float(os.environ.get("REGRESS_TIMEOUT_SCALE", "1"))
    return max(MIN_TIMEOUT_MIN, TIMEOUT_FACTOR * REF_MIN.get(target, 0)) * scale


def run_target(cmd, env, log, target):
    """(exit code, timed out) of one make target; on timeout the whole process group is killed"""
    limit = timeout_min(target)
    t0 = time.time()
    with open(log, "w") as f:
        p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return p.wait(timeout=limit * 60), False
        except subprocess.TimeoutExpired:
            pass
    # SIGTERM first so tools can flush, then SIGKILL the whole group: a child that ignores SIGTERM
    # would otherwise survive once make itself has exited. Processes that start their own session
    # (a docker / lima container) are not in the group and are not stopped here.
    for sig, wait_s in ((signal.SIGTERM, 10), (signal.SIGKILL, 10)):
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=wait_s)
        except subprocess.TimeoutExpired:
            pass
    with open(log, "a") as f:
        f.write(f"\nregress: TIMEOUT {target} after {(time.time() - t0) / 60:.1f} min (limit {limit:.1f} min: "
                f"3 x its reference time, at least {MIN_TIMEOUT_MIN} min; REF_MIN in scripts/regress.py)\n")
    return 124, True


def log_of(out, target):
    return os.path.join(out, f"{target}.log")


def last_line(text):
    lines = [x for x in text.splitlines() if x.strip()]
    return lines[-1].strip() if lines else ""


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpu", default="hazard3", choices=sorted(TARGET_LISTS))
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    TARGETS, OUT = TARGET_LISTS[args.cpu], OUTS[args.cpu]
    if args.list:
        print(" ".join(TARGETS))
        return 0
    shutil.rmtree(OUT, ignore_errors=True)  # only this CPU's output directory is removed
    os.makedirs(OUT)
    make = os.environ.get("MAKE", "make")
    env = dict(os.environ, CPU=args.cpu)
    rows, t_all = [], time.time()
    start = git("rev-parse", "HEAD").strip()
    words = os.environ.get("MAKEFLAGS", "").split()
    letters = words[0] if words and not words[0].startswith("-") and "=" not in words[0] else ""
    refuse = []
    if set(letters) & set("inqt"):
        refuse.append(f"make flags '{''.join(sorted(set(letters) & set('inqt')))}' (-i: a FAIL would exit 0; -n/-q/-t: nothing would run)")
    dirty = [line for line in git("status", "--porcelain", "--untracked-files=all").splitlines() if line.strip()]
    if dirty:
        refuse.append(f"{len(dirty)} uncommitted file(s), e.g. {', '.join(dirty[:3])}: the regression must run on a commit")
    if not start:
        refuse.append("not a git checkout")
    free_gb = shutil.disk_usage(ROOT).free / 2**30
    min_gb = float(os.environ.get("REGRESS_MIN_FREE_GB", "100"))
    if free_gb < min_gb:
        refuse.append(f"only {free_gb:.0f} GiB free on the disk of {ROOT}, at least {min_gb:.0f} GiB needed "
                      "(REGRESS_MIN_FREE_GB; remove old worktrees and negative-test intermediates)")
    for t in TARGETS if not refuse else []:
        t0 = time.time()
        log = log_of(OUT, t)
        print(f"[regress] {t} (CPU={args.cpu}) ...", flush=True)
        rc, _ = run_target([make, "--no-print-directory", t], env, log, t)
        text = open(log, errors="replace").read()
        rows.append((t, rc, time.time() - t0, last_line(text)))
        print(f"[regress] {t}: {'PASS' if rc == 0 else 'FAIL'} ({(time.time() - t0) / 60:.1f} min) {last_line(text)}", flush=True)
        if rc != 0:
            break
    passed = sum(1 for _, rc, _, _ in rows if rc == 0)
    head = git("rev-parse", "HEAD").strip()
    if not refuse and head != start:
        refuse.append(f"HEAD changed during the regression: {start} at the start, {head} at the end")
    ok = passed == len(TARGETS) and not refuse
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write(f"# make regress (CPU={args.cpu})\n\ncommit `{start}`; {passed}/{len(TARGETS)} targets PASS; "
                f"{(time.time() - t_all) / 60:.0f} min; {'PASS' if ok else 'FAIL'}\n\n"
                + "".join(f"- FAIL: {r}\n" for r in refuse) + ("\n" if refuse else "")
                + "| # | target | result | min | last line |\n|---|---|---|---|---|\n")
        for i, (t, rc, dt, line) in enumerate(rows, 1):
            f.write(f"| {i} | `{t}` | {'PASS' if rc == 0 else 'FAIL'} | {dt / 60:.1f} | {line.replace('|', '/')} |\n")
        for t in TARGETS[len(rows):]:
            f.write(f"| - | `{t}` | not run | - | - |\n")
    with open(os.path.join(OUT, "junit.xml"), "w") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<testsuite name="regress_{args.cpu}" tests="{len(TARGETS) + bool(refuse)}" '
                f'failures="{len(rows) - passed + bool(refuse)}" skipped="{len(TARGETS) - len(rows)}" time="{time.time() - t_all:.0f}">\n')
        if refuse:
            f.write(f'  <testcase classname="regress" name="clean tree, make flags, same HEAD">'
                    f'<failure message="{escape("; ".join(refuse), {chr(34): "&quot;"})}"/></testcase>\n')
        for t, rc, dt, line in rows:
            f.write(f'  <testcase classname="make" name="{t}" time="{dt:.0f}">')
            if rc != 0:
                f.write(f'<failure message="{escape(line, {chr(34): "&quot;"})}">see {os.path.relpath(log_of(OUT, t), ROOT)}</failure>')
            f.write("</testcase>\n")
        for t in TARGETS[len(rows):]:
            f.write(f'  <testcase classname="make" name="{t}"><skipped message="not run: an earlier target FAILed"/></testcase>\n')
        f.write("</testsuite>\n")
    for r in refuse:
        print(f"[regress] FAIL: {r}")
    print(f"regress: PASS {passed}/{len(TARGETS)}" if ok else
          f"regress: FAIL before the first target ({'; '.join(refuse)})" if not rows else
          f"regress: FAIL at {rows[-1][0]} ({passed}/{len(TARGETS)} PASS)" if rows[-1][1] != 0 else
          f"regress: FAIL ({'; '.join(refuse)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
