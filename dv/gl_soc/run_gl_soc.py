#!/usr/bin/env python3
"""make gl-soc: Phase 3 gate-level simulation of soc_top (project-plan.md §7.1 L2, §8 Phase 3).

Runs the Phase 1 SoC tests (dv/tests.toml, every test that is not negative_only) on Icarus with
two copies of the SoC in one testbench (dv/tb/tb_soc.v, define GL_LOCKSTEP):
  dut     the RTL soc_top (rtl/rtl.f), as in `make regress-rtl`
  dut_gl  the final netlist of `make harden-soc` (module renamed soc_top_gl) with the
          sky130_fd_sc_hd Verilog cell models (-DFUNCTIONAL -DUNIT_DELAY=#1, files from
          CELL_VERILOG_MODELS in LibreLane's resolved.json) and the SRAM simulation model
Both copies get the same inputs. dv/monitors/gl_lockstep.v compares every output and the SRAM
port 0 pins of the two copies at every falling clock edge (rules in its header). All other
checkers watch the RTL copy, exactly as in the RTL regression.

PASS needs all of:
  - the harden run passed all its own checks and was made from the commit checked out now
    (signoff/scripts/run_guard.py: <harden-run>_signoff/result.txt says `harden-soc: PASS`, which
    includes signoff limits and golden, soc checks, inputs, source tracking; provenance.json
    records HEAD)
  - every selected test PASS (all Phase 1 checkers, dv/scripts/dvlib.py run_test)
  - every test: tb_result.txt fail.gl_lockstep=0 and gl_compares > 0 (the comparison ran)

--powered (`make gl-soc-powered`, project-plan.md §7.1 L5): the powered netlist
<harden-run>/final/pnl/soc_top.pnl.v instead, compiled with -DUSE_POWER_PINS: every cell (also
the fill, decap and diode cells) has its VPWR/VGND/VPB/VNB pins connected (the tap cell only
VPWR/VGND, the pins of its LEF; dv/log_whitelist.txt) and the SRAM model its vccd1/vssd1, driven
by the testbench with 1/0. The cell models then pass every output through a
power-good primitive, so a cell whose supply pins are not on vccd1/vssd1 drives X and the lockstep
comparison FAILs. No SDF: Icarus is not a signoff simulator for timing (project-plan.md §7.1).

usage: run_gl_soc.py [--harden-run <dir>] [--netlist <path>] [--out <dir>] [--tests a,b] [-j N] [--powered]
  --harden-run  LibreLane run of `make harden-soc` (default runs/soc_top)
  --netlist     netlist to simulate instead of <harden-run>/final/nl/soc_top.nl.v (negative tests)
  --out         output directory (default runs/gl_soc, with --powered runs/gl_soc_powered)
  --tests       comma-separated subset of tests (default: all positive tests)
Prints `gl-soc: PASS` / `gl-soc: FAIL` (`gl-soc-powered: ...` with --powered); exit code 0 only
on PASS. Python stdlib only.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dv" / "scripts"))
import dvlib  # noqa: E402
sys.path.insert(0, str(ROOT / "signoff" / "scripts"))
from run_guard import guard  # noqa: E402

LOCKSTEP_V = ROOT / "dv" / "monitors" / "gl_lockstep.v"
GL_FLAGS = ["-DGL_LOCKSTEP", "-DFUNCTIONAL", "-DUNIT_DELAY=#1"]


def rename_top(text):
    """Netlist text with `module soc_top (` renamed to soc_top_gl; must occur exactly once."""
    pat = re.compile(r"^module soc_top\s*\(", re.M)
    if len(pat.findall(text)) != 1:
        raise ValueError("expected exactly one `module soc_top (` in the netlist")
    return pat.sub("module soc_top_gl (", text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--harden-run", default=str(ROOT / "runs" / "soc_top"))
    ap.add_argument("--netlist")
    ap.add_argument("--out")
    ap.add_argument("--tests")
    ap.add_argument("-j", type=int, default=dvlib.default_jobs())
    ap.add_argument("--powered", action="store_true")
    args = ap.parse_args()
    harden_run = Path(args.harden_run).resolve()
    label = "gl-soc-powered" if args.powered else "gl-soc"
    default_nl = harden_run / "final" / ("pnl/soc_top.pnl.v" if args.powered else "nl/soc_top.nl.v")
    netlist = Path(args.netlist).resolve() if args.netlist else default_nl
    out = Path(args.out or ROOT / "runs" / ("gl_soc_powered" if args.powered else "gl_soc")).resolve()
    flags = GL_FLAGS + (["-DUSE_POWER_PINS"] if args.powered else [])
    t0 = time.time()

    def fail(msg):
        print(f"{label}: FAIL ({msg})")
        return 1

    # Only the output directory is removed, first, so that a refused run leaves no old result behind.
    shutil.rmtree(out, ignore_errors=True)
    errs = guard(harden_run, "harden-soc: PASS")
    if errs:
        return fail("; ".join(errs) + "; run `make harden-soc`")
    if not netlist.is_file():
        return fail(f"netlist not found: {netlist}; run `make harden-soc` first")
    resolved = harden_run / "resolved.json"
    if not resolved.is_file():
        return fail(f"{resolved} not found; run `make harden-soc` first")
    cell_models = json.loads(resolved.read_text())["CELL_VERILOG_MODELS"]
    try:
        tests = dvlib.load_tests()
    except (OSError, dvlib.DvError) as e:
        return fail(f"cannot read dv/tests.toml: {e}")
    names = [n for n, t in tests.items() if not t["negative_only"]]
    if args.tests:
        want = args.tests.split(",")
        unknown = [n for n in want if n not in names]
        if unknown:
            return fail(f"unknown or negative-only test(s): {', '.join(unknown)}")
        names = want

    out.mkdir(parents=True)
    gl_v = out / "soc_top_gl.v"
    try:
        gl_v.write_text(rename_top(netlist.read_text()))
    except ValueError as e:
        return fail(str(e))

    print(f"[{label}] netlist {netlist}")
    print(f"[{label}] compile tb_soc with the RTL and gate-level SoC (Icarus, {' '.join(flags)})")
    b = dvlib.build("icarus", extra_files=[LOCKSTEP_V] + [Path(m) for m in cell_models] + [gl_v],
                    extra_flags=flags, variant="glp" if args.powered else "gl")
    if not b.ok:
        return fail(f"compile: {b.message}")

    print(f"[{label}] run {len(names)} tests, {args.j} in parallel")

    def one(name):
        r = dvlib.run_test(name, "icarus", out_root=str(out), build_result=b, quiet=True)
        tbr_path = ROOT / r.get("run_dir", "") / "tb_result.txt"
        tbr = dvlib._parse_tb_result(tbr_path) if tbr_path.is_file() else {}
        problems = []
        if r["status"] != "PASS":
            problems.append("failing checkers: " + ", ".join(r["failing_checkers"]))
            problems += [m for m in r["messages"][:5]]
        if tbr.get("fail.gl_lockstep") != "0":
            problems.append(f"fail.gl_lockstep={tbr.get('fail.gl_lockstep')}")
        compares = dvlib._int_or_none(tbr.get("gl_compares"))
        if not compares or compares <= 0:
            problems.append(f"gl_compares={tbr.get('gl_compares')} (the RTL/GL comparison did not run)")
        return name, r, compares, problems

    with ThreadPoolExecutor(max_workers=max(1, args.j)) as ex:
        results = list(ex.map(one, names))
    errors = 0
    for name, r, compares, problems in results:
        if problems:
            errors += 1
            print(f"  [FAIL] {name}: " + "; ".join(problems))
        else:
            print(f"  [PASS] {name}: {r.get('cycles')} cycles, {compares} RTL/GL comparisons, "
                  f"{r.get('wall_time_s')} s")
    summary = {"netlist": str(netlist), "tests": len(results), "failed": errors,
               "wall_time_s": round(time.time() - t0, 1)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    status = "PASS" if errors == 0 and results else "FAIL"
    print(f"{label}: {status} {len(results) - errors}/{len(results)} tests passed ({summary['wall_time_s']} s)")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
