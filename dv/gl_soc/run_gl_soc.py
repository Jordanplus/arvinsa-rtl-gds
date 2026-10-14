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
  - every simulation ends within its wall-clock limit (gl_timeout: sized for the gate-level speed)

--powered (`make gl-soc-powered`, project-plan.md §7.1 L5): the powered netlist
<harden-run>/final/pnl/soc_top.pnl.v instead, compiled with -DUSE_POWER_PINS: every cell (also
the fill, decap and diode cells) has its VPWR/VGND/VPB/VNB pins connected (the tap cell only
VPWR/VGND, the pins of its LEF; dv/log_whitelist.txt) and the SRAM model its vccd1/vssd1, driven
by the testbench with 1/0. The cell models then pass every output through a
power-good primitive, so a cell whose supply pins are not on vccd1/vssd1 drives X and the lockstep
comparison FAILs. No SDF: Icarus is not a signoff simulator for timing (project-plan.md §7.1).

usage: run_gl_soc.py [--cpu picorv32|hazard3] [--harden-run <dir>] [--netlist <path>] [--out <dir>] [--tests a,b] [-j N] [--powered]
  --cpu         CPU of soc_top (default picorv32; hazard3: Phase 5, ADR-0011): the RTL copy is built
                from that CPU's file list and defines, the firmware from its build directory
                (dv/scripts/dvlib.py CPUS), and only the tests whose cpus include it run, with its
                [test.<cpu>] overrides
  --harden-run  LibreLane run of `make harden-soc` (default runs/soc_top; CPU=hazard3: runs/soc_top_hazard3;
                caravel: runs/user_project_wrapper, the wrapper with soc_top flattened into it, Phase 7)
  --netlist     netlist to simulate instead of <harden-run>/final/nl/<top>.nl.v (negative tests; top
                soc_top, or user_project_wrapper for caravel)
  --out         output directory (default runs/gl_soc, with --powered runs/gl_soc_powered; another
                CPU adds _<cpu>: runs/gl_soc_hazard3, runs/gl_soc_powered_hazard3)
  --tests       comma-separated subset of tests (default: all positive tests of the CPU)
  --record-window  hex GPIO values, comma-separated (with one test in --tests): instead of the test
                verdict, record the switching activity of the gate-level copy in each window the firmware
                marks on GPIO_OUT (dv/gl_soc/vcd_window.v): one simulation per window, <out>/win_<hex>.vcd,
                at least MIN_WINDOW_CYCLES cycles, no lockstep mismatch before the window ended. For the IR
                max-power pattern (fw/tests/maxpower, ADR-0019 decision 20); prints `gl-record: PASS/FAIL`.
  --clk-half-ns half period of the testbench clock (default the testbench's 20 ns). --record-window
                takes it from CLOCK_PERIOD of the harden run's resolved.json (the signoff period, so that the
                activity per second is the signoff one; an odd period in ns FAILs: tb_soc.v's half period is
                an integer); a --clk-half-ns that differs from it FAILs (Phase 7 review H2)
  --plusarg     an extra plusarg for every --record-window simulation (repeatable; pnr/soc_top/neg_ir.py
                passes one beginning with "vcd" to check that a stray testbench dump FAILs)
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
VCD_WINDOW_V = ROOT / "dv" / "gl_soc" / "vcd_window.v"
MIN_WINDOW_CYCLES = 1000
GL_FLAGS = ["-DGL_LOCKSTEP", "-DFUNCTIONAL", "-DUNIT_DELAY=#1"]
# Wall-clock limit of one simulation. dvlib.default_timeout assumes the RTL speed (4000 cycles/s);
# the lockstep simulation runs about 1200-1600 cycles/s here with 8 in parallel (Phase 4 make
# regress 1, powered: boot_uart_max 362843 cycles in 304 s, memtest 871219 in 548 s) and 2-6 times
# slower on a loaded machine (Phase 4 make regress 3, Spotlight indexing: boot_uart_max killed at
# the old 620 s). A hung firmware already ends at max_cycles in simulated time (checker timeout);
# this limit only stops a simulator that no longer advances, so it is sized for 400 cycles/s:
# boot_uart_max 5120 s, memtest 12620 s, a 200k-cycle test 620 s (10-50x the measured times).
GL_CYCLES_PER_S = 400


def gl_timeout(max_cycles):
    return int(120 + max_cycles / GL_CYCLES_PER_S)


# Top module of the netlist per CPU build: the Caravel build (Phase 7, ADR-0019) hardens the wrapper
# with soc_top flattened into it (make harden D=user_project_wrapper, run tag user_project_wrapper).
TOPS = {"caravel": "user_project_wrapper"}


def rename_top(text, top="soc_top"):
    """Netlist text with `module <top> (` renamed to <top>_gl; must occur exactly once."""
    pat = re.compile(r"^module " + re.escape(top) + r"\s*\(", re.M)
    if len(pat.findall(text)) != 1:
        raise ValueError(f"expected exactly one `module {top} (` in the netlist")
    return pat.sub(f"module {top}_gl (", text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpu", default="picorv32", choices=sorted(dvlib.CPUS))
    ap.add_argument("--harden-run")
    ap.add_argument("--netlist")
    ap.add_argument("--out")
    ap.add_argument("--tests")
    ap.add_argument("-j", type=int, default=dvlib.default_jobs())
    ap.add_argument("--powered", action="store_true")
    ap.add_argument("--record-window")
    ap.add_argument("--clk-half-ns", type=int)
    ap.add_argument("--plusarg", action="append", default=[])
    args = ap.parse_args()
    cpu = dvlib.CPUS[args.cpu]
    suffix = "" if args.cpu == "picorv32" else f"_{args.cpu}"
    top = TOPS.get(args.cpu, "soc_top")
    harden_run = Path(args.harden_run or ROOT / "runs" / (top if top != "soc_top" else f"soc_top{suffix}")).resolve()
    label = "gl-soc-powered" if args.powered else "gl-soc"
    default_nl = harden_run / "final" / (f"pnl/{top}.pnl.v" if args.powered else f"nl/{top}.nl.v")
    netlist = Path(args.netlist).resolve() if args.netlist else default_nl
    out = Path(args.out or ROOT / "runs" / (("gl_soc_powered" if args.powered else "gl_soc") + suffix)).resolve()
    flags = GL_FLAGS + (["-DUSE_POWER_PINS"] if args.powered else [])
    if args.clk_half_ns and not args.record_window:
        flags += [f"-DTB_CLK_HALF_NS={args.clk_half_ns}"]
    windows = [w.strip().lower() for w in args.record_window.split(",")] if args.record_window else []
    if windows:
        label = "gl-record"
        flags += ["-s", "vcd_window"]
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
    if windows:   # the recording runs at the run's signoff period
        period = json.loads(resolved.read_text()).get("CLOCK_PERIOD")
        if not isinstance(period, (int, float)) or period % 2:
            return fail(f"CLOCK_PERIOD {period!r} of {resolved}: the testbench's half period is an integer number of ns")
        if args.clk_half_ns and args.clk_half_ns * 2 != period:
            return fail(f"--clk-half-ns {args.clk_half_ns} is not half of the run's CLOCK_PERIOD {period} ns")
        flags += [f"-DTB_CLK_HALF_NS={int(period) // 2}"]
    try:
        tests = dvlib.load_tests()
    except (OSError, dvlib.DvError) as e:
        return fail(f"cannot read dv/tests.toml: {e}")
    names = [n for n, t in tests.items() if not t["negative_only"] and dvlib.applies(t, args.cpu)]
    if args.tests:
        want = args.tests.split(",")
        unknown = [n for n in want if n not in names]
        if unknown:
            return fail(f"unknown, negative-only or not for {args.cpu} test(s): {', '.join(unknown)}")
        names = want

    out.mkdir(parents=True)
    gl_v = out / f"{top}_gl.v"
    try:
        gl_v.write_text(rename_top(netlist.read_text(), top))
    except ValueError as e:
        return fail(str(e))

    print(f"[{label}] cpu {args.cpu}, netlist {netlist}")
    print(f"[{label}] compile tb_soc with the RTL and gate-level SoC (Icarus, {' '.join(flags)})")
    b = dvlib.build("icarus", defines=cpu["defines"], rtl_f=cpu["rtl_f"],
                    extra_files=[LOCKSTEP_V] + [Path(m) for m in cell_models] + [gl_v] + ([VCD_WINDOW_V] if windows else []),
                    extra_flags=flags, variant="glrec" if windows else "glp" if args.powered else "gl")
    if not b.ok:
        return fail(f"compile: {b.message}")
    if windows:
        if len(names) != 1:
            return fail(f"--record-window needs exactly one test in --tests, got {names}")
        return record_windows(names[0], windows, tests, b, cpu, args, out, label)

    print(f"[{label}] run {len(names)} tests, {args.j} in parallel")

    def one(name):
        r = dvlib.run_test(name, "icarus", out_root=str(out), build_result=b, quiet=True,
                           rtl_f=cpu["rtl_f"], fw_dir=cpu["fw_dir"], cpu=args.cpu,
                           timeout=gl_timeout(dvlib.for_cpu(tests[name], args.cpu)["max_cycles"]))
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
    summary = {"cpu": args.cpu, "netlist": str(netlist), "tests": len(results), "failed": errors,
               "wall_time_s": round(time.time() - t0, 1)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    status = "PASS" if errors == 0 and results else "FAIL"
    print(f"{label}: {status} {len(results) - errors}/{len(results)} tests passed ({summary['wall_time_s']} s)")
    return 0 if status == "PASS" else 1


def record_windows(name, windows, tests, b, cpu, args, out, label):
    """One simulation per window; each must record at least MIN_WINDOW_CYCLES cycles into its VCD before any
    lockstep mismatch."""
    ok_all = True
    for w in windows:
        vcd = out / f"win_{w}.vcd"
        r = dvlib.run_test(name, "icarus", out_root=str(out / f"run_{w}"), build_result=b, quiet=True,
                           rtl_f=cpu["rtl_f"], fw_dir=cpu["fw_dir"], cpu=args.cpu,
                           extra_plusargs=[f"irwin_gpio={w}", f"irwin_vcd={vcd}"] + args.plusarg,
                           timeout=gl_timeout(dvlib.for_cpu(tests[name], args.cpu)["max_cycles"]))
        logs = "".join(p.read_text(errors="replace") for p in (ROOT / r.get("run_dir", "")).glob("*.log"))
        m = re.search(r"\[vcd_window\] end after (\d+) cycles", logs)
        cycles = int(m.group(1)) if m else 0
        mism = len(re.findall(r"\[CHK:gl_lockstep\] FAIL", logs))
        # tb_soc.v's $test$plusargs("vcd") matches any plusarg beginning with "vcd": it would dump the whole
        # testbench into wave.vcd from time 0 and the window's $dumpfile would be ignored (Phase 7)
        stray = list((ROOT / r.get("run_dir", "")).glob("wave.vcd"))
        ok = cycles >= MIN_WINDOW_CYCLES and vcd.is_file() and vcd.stat().st_size > 0 and mism == 0 and not stray
        ok_all &= ok
        print(f"  [{'PASS' if ok else 'FAIL'}] window {w}: {cycles} cycles recorded to {vcd} "
              f"({vcd.stat().st_size if vcd.is_file() else 0} bytes), {mism} lockstep mismatch(es)"
              + (f", testbench dump {stray[0]} present" if stray else ""))
    print(f"{label}: {'PASS' if ok_all else 'FAIL'} {name} windows {','.join(windows)}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
