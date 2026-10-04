#!/usr/bin/env python3
"""make neg-gl-soc: bug injection into the soc_top final netlist; `make gl-soc` must FAIL on each,
because the RTL/GL lockstep comparison (dv/monitors/gl_lockstep.v) sees a difference.

usage: neg_gl_soc.py [--harden-run <dir>] [--out <dir>]   (defaults runs/soc_top, runs/neg_gl_soc)
The harden run must pass signoff/scripts/run_guard.py (PASS, made from the commit checked out now).

Uses the same netlist edits as signoff/eqy/neg_eqy.py (soc_top cases; each edit must match
exactly one place). Each edited netlist runs dv/gl_soc/run_gl_soc.py on the positive tests except
the two longest (memtest, boot_uart_max), outputs in runs/neg_gl_soc/<case>/. Cases run one after another (they share
one build directory). A case counts as caught only if gl-soc FAILs and at least one test reports fail.gl_lockstep > 0 (not a compile
error or some other failure).
  din5_stuck0           sram0.din0[5] tied to 0
  csb0_inverted         sram0.csb0 through an extra inverter
  host_rdata7_inverted  the buffer that drives port host_rdata[7] becomes an inverter
  mux_swap              first mux2_1 that drives a flip-flop D gets A0 and A1 swapped
Prints `neg-gl-soc: PASS n/n caught` / `neg-gl-soc: FAIL ...`; exit code 0 only on PASS.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUNNER = os.path.join(ROOT, "dv", "gl_soc", "run_gl_soc.py")
sys.path.insert(0, os.path.join(ROOT, "signoff", "eqy"))
import neg_eqy  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "signoff", "scripts"))
from run_guard import guard  # noqa: E402

TESTS = ["hello", "irq", "muldiv", "uart_echo", "bootrom_march", "boot_uart_hello", "boot_host_hello",
         "regs", "unmapped", "uart_burst", "reset_store"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harden-run", default=os.path.join(ROOT, "runs", "soc_top"))
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "neg_gl_soc"))
    args = ap.parse_args()
    harden_run, OUT = os.path.abspath(args.harden_run), os.path.abspath(args.out)
    netlist = os.path.join(harden_run, "final", "nl", "soc_top.nl.v")
    shutil.rmtree(OUT, ignore_errors=True)  # only the output directory is removed, before any check
    errs = guard(harden_run, "harden-soc: PASS")
    if errs:
        print(f"neg-gl-soc: FAIL ({'; '.join(errs)}; run `make harden-soc`)")
        return 1
    if not os.path.isfile(netlist):
        print(f"neg-gl-soc: FAIL (netlist not found: {netlist}; run `make harden-soc` first)")
        return 1
    text = open(netlist, encoding="utf8").read()
    t0 = time.time()

    def one(case):
        name, fn = case
        d = os.path.join(OUT, name)
        os.makedirs(d)
        new, err = neg_eqy.edit(name, text, fn)
        if err:
            return name, False, f"injection: {err}"
        edited = os.path.join(d, "soc_top.nl.v")
        open(edited, "w", encoding="utf8").write(new)
        cp = subprocess.run([sys.executable, RUNNER, "--harden-run", harden_run, "--netlist", edited,
                             "--out", os.path.join(d, "gl"), "--tests", ",".join(TESTS)],
                            capture_output=True, text=True)
        open(os.path.join(d, "run.log"), "w").write(cp.stdout + cp.stderr)
        lockstep = [int(n) for n in re.findall(r"fail\.gl_lockstep=(\d+)", cp.stdout)]
        caught = cp.returncode != 0 and "gl-soc: FAIL" in cp.stdout and any(n > 0 for n in lockstep)
        hit = sum(1 for n in lockstep if n > 0)
        return name, caught, (f"lockstep mismatch in {hit}/{len(TESTS)} tests" if caught else
                              "expected gl-soc FAIL with fail.gl_lockstep > 0; " + cp.stdout.strip().splitlines()[-1])

    # One case at a time: every case compiles into the same build directory (dvlib variant "gl"),
    # so a second compile would replace the executable the first case is still running.
    results = [one(c) for c in neg_eqy.CASES["soc_top"]]
    caught = 0
    for name, ok, msg in results:
        caught += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")
    status = "PASS" if caught == len(results) else "FAIL"
    print(f"neg-gl-soc: {status} {caught}/{len(results)} caught ({round(time.time() - t0)} s)")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
