#!/usr/bin/env python3
"""make neg-gl-core: bug injection into the hardened netlist; `make gl-core` must FAIL on each.

usage: neg_gl_core.py [--harden-run <dir>]   (default runs/picorv32_core)

Each case edits a copy of <harden-run>/final/nl/picorv32.nl.v and runs
dv/gl_core/run_gl_core.py on it (outputs in runs/neg_gl_core/<case>/). The edit must match
exactly one place in the netlist, otherwise the case itself FAILs.

  wdata3_stuck0  the buffer that drives port mem_wdata[3] gets constant 0 at its input.
                 Expected: the upstream self-check FAILs in the GL run (stores are corrupted)
                 and the GL bus trace differs from RTL.
  instr_inverted the buffer that drives port mem_instr is replaced by an inverter.
                 The upstream testbench only uses this signal for verbose printing, so the
                 upstream self-check still prints ALL TESTS PASSED. Expected: gl-core FAILs on
                 the bus-trace checks (I/D flag differs from RTL) - shows what the bus-trace
                 checks add over the upstream self-check.

Prints `neg-gl-core: PASS n/n caught` / `neg-gl-core: FAIL ...`; exit code 0 only on PASS.
Python stdlib only.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "runs", "neg_gl_core")
RUNNER = os.path.join(ROOT, "dv", "gl_core", "run_gl_core.py")


def port_buffer(port):
    """Regex for the single-input buffer instance whose output pin X drives <port>."""
    return re.compile(r"(sky130_fd_sc_hd__\w+) (\S+) \(\.A\(([^)]+)\),\s*\.X\(" + re.escape(port) + r"\)\);")


def stuck0(text):
    rx = port_buffer("mem_wdata[3]")
    return rx, lambda m: f"{m.group(1)} {m.group(2)} (.A(1'b0),\n    .X(mem_wdata[3]));"


def inverted(text):
    rx = port_buffer("mem_instr")
    return rx, lambda m: f"sky130_fd_sc_hd__inv_2 {m.group(2)} (.A({m.group(3)}),\n    .Y(mem_instr));"


CASES = [
    # name, edit, (must the upstream self-check FAIL in the GL run?), required text in summary
    ("wdata3_stuck0", stuck0, True, "bus traces differ"),
    ("instr_inverted", inverted, False, "bus traces differ"),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harden-run", default=os.path.join(ROOT, "runs", "picorv32_core"))
    harden_run = os.path.abspath(ap.parse_args().harden_run)
    netlist = os.path.join(harden_run, "final", "nl", "picorv32.nl.v")
    if not os.path.isfile(netlist):
        print(f"neg-gl-core: FAIL (netlist not found: {netlist}; run `make harden-core` first)")
        return 1
    shutil.rmtree(OUT, ignore_errors=True)  # only runs/neg_gl_core is removed
    os.makedirs(OUT)
    text = open(netlist, encoding="utf8").read()
    procs, errors = {}, []
    for name, edit, _, _ in CASES:
        rx, repl = edit(text)
        matches = rx.findall(text)
        if len(matches) != 1:
            errors.append(f"{name}: edit matched {len(matches)} places in the netlist, expected 1")
            continue
        case_dir = os.path.join(OUT, name)
        os.makedirs(case_dir)
        edited = os.path.join(case_dir, "picorv32.nl.v")
        open(edited, "w", encoding="utf8").write(rx.sub(repl, text))
        log = open(os.path.join(case_dir, "run.log"), "w")
        procs[name] = subprocess.Popen([sys.executable, RUNNER, "--harden-run", harden_run, "--netlist", edited,
                                        "--out", os.path.join(case_dir, "gl_core")],
                                       stdout=log, stderr=subprocess.STDOUT)
        print(f"[neg-gl-core] {name}: running (log: {case_dir}/run.log)")
    caught = 0
    for name, _, upstream_fails, needle in CASES:
        if name not in procs:
            continue
        rc = procs[name].wait()
        case_dir = os.path.join(OUT, name)
        summary_path = os.path.join(case_dir, "gl_core", "summary.txt")
        summary = open(summary_path).read() if os.path.exists(summary_path) else ""
        gl_log_path = os.path.join(case_dir, "gl_core", "gl.log")
        gl_log = open(gl_log_path, errors="replace").read() if os.path.exists(gl_log_path) else ""
        upstream_passed = "\nALL TESTS PASSED.\n" in gl_log
        problems = []
        if rc == 0 or "gl-core: FAIL" not in summary:
            problems.append(f"gl-core did not FAIL (exit {rc})")
        if needle not in summary:
            problems.append(f"summary lacks {needle!r}")
        if upstream_fails and upstream_passed:
            problems.append("upstream self-check still passed in the GL run")
        if not upstream_fails and not upstream_passed:
            problems.append("upstream self-check failed too (case no longer isolates the trace comparison)")
        if problems:
            errors.append(f"{name}: " + "; ".join(problems))
            print(f"  [FAIL] {name}: " + "; ".join(problems))
        else:
            caught += 1
            print(f"  [PASS] {name}: gl-core FAIL as expected; upstream self-check "
                  f"{'FAIL' if not upstream_passed else 'PASS (only the bus-trace checks caught it)'}")
    status = "PASS" if not errors else "FAIL"
    print(f"neg-gl-core: {status} {caught}/{len(CASES)} caught" + ("" if not errors else f" ({'; '.join(errors)})"))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
