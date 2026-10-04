#!/usr/bin/env python3
"""make neg-gl-soc: bug injection into the soc_top final netlist; `make gl-soc` must FAIL on each,
because the RTL/GL lockstep comparison (dv/monitors/gl_lockstep.v) sees a difference.

usage: neg_gl_soc.py [--harden-run <dir>] [--out <dir>] [--cases a,b]   (defaults runs/soc_top, runs/neg_gl_soc, all)
The harden run must pass signoff/scripts/run_guard.py (PASS, made from the commit checked out now).

Each case edits a copy of the final netlist (each edit must match exactly one place) and runs
dv/gl_soc/run_gl_soc.py on it with the tests listed for the case; outputs in
runs/neg_gl_soc/<case>/. Cases run one after another (they share one build directory). A case
counts as caught only if gl-soc FAILs and at least one test reports fail.gl_lockstep > 0 (not a
compile error or some other failure).
  Four netlist edits of signoff/eqy/neg_eqy.py (soc_top), on the positive tests except the two
  longest (memtest, boot_uart_max); nand2_to_nor2 is left to EQY, whether simulation sees it
  depends on whether the firmware exercises that gate:
  din5_stuck0           sram0.din0[5] tied to 0
  csb0_inverted         sram0.csb0 through an extra inverter
  host_rdata7_inverted  the buffer that drives port host_rdata[7] becomes an inverter
  mux_swap              first mux2_1 that drives a flip-flop D gets A0 and A1 swapped
  The three faults that the Phase 2 GL ISA regression missed (docs/phase_exit/phase2.md known
  limitation 7), each on the Phase 4 test written for it:
  count_cycle45_stuck1  flip-flop u_cpu.count_cycle[45] D tied to 1 (rdcycleh)    test counters
  count_instr40_stuck1  flip-flop u_cpu.count_instr[40] D tied to 1 (rdinstreth)  test counters
  buserr_irq_stuck0     flip-flop u_cpu.irq_pending[2] D tied to 0 (bus-error IRQ) test buserr
  L5 (powered netlist final/pnl, run_gl_soc.py --powered):
  host_rdata7_unpowered the buffer that drives port host_rdata[7] gets VPWR on vssd1   test hello
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

GL_CASES = ["din5_stuck0", "csb0_inverted", "host_rdata7_inverted", "mux_swap"]


def unpowered(port):
    """Powered netlist: the cell whose output X drives <port> gets VPWR on vssd1 instead of vccd1
    (pins in the order OpenROAD writes them: inputs, VGND, VNB, VPB, VPWR, output)."""
    rx = re.compile(r"(\.VPB\(vccd1\),\s*\.VPWR\()vccd1(\),\s*\.X\(" + re.escape(port) + r"\)\);)")
    return rx, lambda m: m.group(1) + "vssd1" + m.group(2)


TESTS = ["hello", "irq", "muldiv", "uart_echo", "bootrom_march", "boot_uart_hello", "boot_host_hello",
         "regs", "unmapped", "uart_burst", "reset_store"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harden-run", default=os.path.join(ROOT, "runs", "soc_top"))
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "neg_gl_soc"))
    ap.add_argument("--cases", help="comma-separated subset of cases")
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

    pnl_path = os.path.join(harden_run, "final", "pnl", "soc_top.pnl.v")
    pnl = open(pnl_path, encoding="utf8").read() if os.path.isfile(pnl_path) else ""

    def one(case):
        name, fn, tests, powered = case
        d = os.path.join(OUT, name)
        os.makedirs(d)
        new, err = neg_eqy.edit(name, pnl if powered else text, fn)
        if err:
            return name, False, f"injection: {err}"
        edited = os.path.join(d, "soc_top.pnl.v" if powered else "soc_top.nl.v")
        open(edited, "w", encoding="utf8").write(new)
        verdict = "gl-soc-powered: FAIL" if powered else "gl-soc: FAIL"
        cp = subprocess.run([sys.executable, RUNNER, "--harden-run", harden_run, "--netlist", edited,
                             "--out", os.path.join(d, "gl"), "--tests", ",".join(tests)] + (["--powered"] if powered else []),
                            capture_output=True, text=True)
        open(os.path.join(d, "run.log"), "w").write(cp.stdout + cp.stderr)
        lockstep = [int(n) for n in re.findall(r"fail\.gl_lockstep=(\d+)", cp.stdout)]
        caught = cp.returncode != 0 and verdict in cp.stdout and any(n > 0 for n in lockstep)
        hit = sum(1 for n in lockstep if n > 0)
        return name, caught, (f"lockstep mismatch in {hit}/{len(tests)} tests" if caught else
                              f"expected {verdict} with fail.gl_lockstep > 0; " + cp.stdout.strip().splitlines()[-1])

    cases = [(n, fn, TESTS, False) for n, fn in neg_eqy.CASES["soc_top"] if n in GL_CASES]
    if len(cases) != len(GL_CASES):
        print(f"neg-gl-soc: FAIL (cases {GL_CASES} not all found in neg_eqy.py)")
        return 1
    cases += [
        ("count_cycle45_stuck1", lambda t: neg_eqy.flop_d_const(r"\u_cpu.count_cycle[45] ", 1), ["counters"], False),
        ("count_instr40_stuck1", lambda t: neg_eqy.flop_d_const(r"\u_cpu.count_instr[40] ", 1), ["counters"], False),
        ("buserr_irq_stuck0", lambda t: neg_eqy.flop_d_const(r"\u_cpu.irq_pending[2] ", 0), ["buserr"], False),
        ("host_rdata7_unpowered", lambda t: unpowered("host_rdata[7]"), ["hello"], True),
    ]
    if args.cases:
        want = args.cases.split(",")
        if set(want) - {c[0] for c in cases}:
            print(f"neg-gl-soc: FAIL (unknown case(s): {sorted(set(want) - {c[0] for c in cases})})")
            return 1
        cases = [c for c in cases if c[0] in want]
    # One case at a time: every case compiles into the same build directory (dvlib variant "gl"
    # or "glp"), so a second compile would replace the executable the first case is still running.
    results = [one(c) for c in cases]
    caught = 0
    for name, ok, msg in results:
        caught += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")
    status = "PASS" if caught == len(results) else "FAIL"
    print(f"neg-gl-soc: {status} {caught}/{len(results)} caught ({round(time.time() - t0)} s)")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
