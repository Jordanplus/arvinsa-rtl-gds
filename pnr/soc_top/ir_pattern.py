#!/usr/bin/env python3
"""Static IR of a run with the max-power pattern, in the slow corners (ADR-0019 decisions 19, 20, 25).

usage: ir_pattern.py <run dir> <out dir> <limits.toml> --vcd <window.vcd> [--vcd ...] [--ll-dir <LibreLane checkout>]
                     [--power <power.json>] [--label ir-soc]
       ir_pattern.py --judge <out dir>/ir_pattern/results.json <limits.toml> [--label ...]   (re-judge; neg_ir.py)

make ir-soc: the IR of soc_top judged with the switching activity of fw/tests/maxpower recorded on the final
netlist at the signoff period (run_gl_soc.py --record-window), the method the user chose on 2026-10-13 for
the wrapper and soc_top alike ("那我們還是採用pattern 評估做法", ADR-0019 decision 20). The harden run's
ir_worst.py (OpenSTA's vectorless activity, about 2.3 times the pattern on the wrapper) is kept as it is: it
is the more pessimistic of the two, so the pattern adds the measured activity, it does not relax anything.
For each --vcd window and each judged corner of ir_worst.py (JUDGED: max_ss_n40C_1v60 and max_ss_100C_1v60,
their libraries, 1.60 V and their own metal resistance, the SRAM's port 1 floating current), the run's own
IR step is re-run with the run's own supply points (ir_worst.run_corner with the window's VCD). Every window
must annotate all pins (0 unannotated) and every corner must have been applied; then the largest VDD drop +
GND rise over windows and corners <= [max_sum] ir_vdd_drop_plus_gnd_rise of the limits file.
Inputs, checked before any tool runs (check_inputs(), shared with ir_caravel.py; Phase 7 review H2, H3):
the run passes the run guard (harden-soc: PASS, made from HEAD); the --vcd files are exactly the windows
WINDOWS (win_5a, win_5b, win_5c: every marked segment of fw/tests/maxpower); in each, the clock port of the
run (CLOCK_PORT of its resolved.json, in scope tb_soc.dut_gl) toggles with the run's CLOCK_PERIOD (an activity
recorded at another period scales the power and the IR). Every drop must be a finite number (a NaN would be
skipped by max()).
Writes <out>/ir_pattern/ (the step runs and results.json: the rows and drops, so that --judge can re-apply a
limit without re-running the tools) and prints `<label>: PASS` / `<label>: FAIL` last; exit code 0 only on
PASS. ir_caravel.py (the wrapper, supplied from Caravel's pads) writes and judges the same results.json.
Python stdlib only (LibreLane runs inside its nix-shell).
"""
import glob
import json
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ir_worst  # noqa: E402
sys.path.insert(0, os.path.join(ir_worst.ROOT, "signoff", "scripts"))
from run_guard import guard  # noqa: E402

WINDOWS = ("5a", "5b", "5c")   # the busy segments fw/tests/maxpower marks on gpio_out (0x5A, 0x5B, 0x5C)


def vcd_clock_period(path, scope, port, edges=11):
    """The period (ps) between the first `edges` rising edges of `port` in `scope` of a VCD, or an error string."""
    stack, ident, unit, t = [], None, None, 0
    rises = []
    with open(path, errors="replace") as f:
        for line in f:
            w = line.split()
            if not w:
                continue
            if ident is None or unit is None:
                if w[0] == "$timescale":
                    unit = w[1] if len(w) > 1 and w[1] != "$end" else next(f).strip()
                elif w[0] == "$scope" and len(w) > 2:
                    stack.append(w[2])
                elif w[0] == "$upscope":
                    stack.pop()
                elif w[0] == "$var" and len(w) > 4 and w[4] == port and w[2] == "1" and stack == scope:
                    ident = w[3]
                elif w[0] == "$enddefinitions":
                    return f"no 1-bit {port} in scope {'.'.join(scope)} (or no $timescale)"
                continue
            if line[0] == "#":
                t = int(line[1:])
            elif line.rstrip("\n") == "1" + ident:
                rises.append(t)
                if len(rises) == edges:
                    break
    if unit not in ("1ps", "1 ps"):
        return f"timescale {unit!r}, expected 1ps"
    periods = {b - a for a, b in zip(rises, rises[1:])}
    if len(rises) < edges or len(periods) != 1:
        return f"{len(rises)} rising edges of {port}, periods {sorted(periods)} ps"
    return periods.pop()


def check_inputs(run, vcds):
    """Rows on the run and the windows, before any tool runs (Phase 7 review H2, H3)."""
    errs = guard(run, "harden-soc: PASS")
    rows = [(not errs, "run guard: " + ("; ".join(errs) if errs else f"{run} passed harden-soc at HEAD"))]
    names = sorted(os.path.splitext(os.path.basename(v))[0] for v in vcds)
    want = sorted(f"win_{w}" for w in WINDOWS)
    rows.append((names == want, f"windows: --vcd {names}, expected {want} (every marked segment of fw/tests/maxpower)"))
    missing = [v for v in vcds if not os.path.isfile(v)]
    if missing:
        return rows + [(False, f"switching activity: need --vcd window(s) of the max-power pattern, missing {missing}")]
    try:
        cfg = json.load(open(os.path.join(run, "resolved.json")))
        period, port = float(cfg["CLOCK_PERIOD"]), cfg["CLOCK_PORT"]
    except (OSError, ValueError, KeyError) as e:
        return rows + [(False, f"activity period: no CLOCK_PERIOD/CLOCK_PORT in {run}/resolved.json ({e})")]
    for v in vcds:
        got = vcd_clock_period(v, ["tb_soc", "dut_gl"], port)
        ok = not isinstance(got, str) and abs(got - period * 1000) < 0.5
        rows.append((ok, f"activity period: {os.path.basename(v)} {port} "
                         + (got if isinstance(got, str) else f"{got / 1000:g} ns") + f" vs the run's CLOCK_PERIOD {period:g} ns"))
    return rows


def write_results(path, rows, drops, expected, what):
    """rows: [(ok, msg)] of the runs; drops: {corner+tag: [vdd, gnd]}; expected: how many drops a complete run has."""
    json.dump({"rows": [[bool(ok), msg] for ok, msg in rows], "drops": drops, "expected": expected, "what": what},
              open(path, "w"), indent=1)


def judge(results, lim):
    """The verdict rows of a results.json against the limit lim (V)."""
    rows = [(ok, msg) for ok, msg in results["rows"]]
    drops, n = results["drops"], results["expected"]
    bad = sorted(c for c, v in drops.items() if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v))
    if bad:
        rows.append((False, f"drop: not a finite number in {bad}"))
    elif len(drops) != n:
        rows.append((False, f"drop: {len(drops)} of the {n} window x corner results (a run failed)"))
    elif drops:
        worst = max(drops, key=lambda c: sum(drops[c]))
        rows.append((sum(drops[worst]) <= lim, f"drop: worst {worst} {sum(drops[worst]) * 1e3:.2f} mV {results['what']} "
                                               f"vs max {lim * 1e3:.1f} mV"))
    else:
        rows.append((False, "drop: no result"))
    return rows


def finish(rows, label, info=()):
    for ok, msg in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    for msg in info:
        print(f"  [INFO] {msg}")
    ok = bool(rows) and all(r[0] for r in rows)
    print(f"{label}: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv):
    pos, opts = [], {"--label": "ir-soc"}
    it = iter(argv)
    for a in it:
        if a in ("--ll-dir", "--power", "--judge"):
            opts[a] = os.path.abspath(next(it, ""))
        elif a == "--label":
            opts[a] = next(it, "ir-soc")
        elif a == "--vcd":
            opts.setdefault("--vcd", []).append(os.path.abspath(next(it, "")))
        else:
            pos.append(a)
    label = opts["--label"]
    if "--judge" in opts:
        if len(pos) != 1:
            print(__doc__.split("\n\n")[1])
            return 2
        lim, _ = ir_worst.limit(os.path.abspath(pos[0]))
        if lim is None:
            return finish([(False, f"limit: no [max_sum] {ir_worst.KEY} with two keys in {pos[0]}")], label)
        try:
            results = json.load(open(opts["--judge"]))
        except (OSError, ValueError) as e:
            return finish([(False, f"cannot read {opts['--judge']}: {e}")], label)
        return finish(judge(results, lim), label)
    if len(pos) != 3:
        print(__doc__.split("\n\n")[1])
        return 2
    run, out, limits_path = (os.path.abspath(a) for a in pos)
    ll_dir = opts.get("--ll-dir") or os.environ.get("LIBRELANE_DIR") or os.path.join(ir_worst.ROOT, ".tools", "librelane")
    lim, keys = ir_worst.limit(limits_path)
    if lim is None:
        return finish([(False, f"limit: no [max_sum] {ir_worst.KEY} with two keys in {limits_path}")], label)
    vcds = opts.get("--vcd") or []
    work = os.path.join(out, "ir_pattern")
    shutil.rmtree(work, ignore_errors=True)   # only this check's own output, before the run guard
    rows = check_inputs(run, vcds)
    if not all(ok for ok, _ in rows):
        return finish(rows, label)
    steps = sorted((d for d in glob.glob(os.path.join(run, "[0-9]*-openroad-irdropreport*"))
                    if os.path.isfile(os.path.join(d, "state_out.json"))), key=lambda d: int(os.path.basename(d).split("-")[0]))
    if not steps:
        return finish([(False, f"no finished OpenROAD.IRDropReport step in {run}")], label)
    os.makedirs(work)
    drops = {}
    for vcd in vcds:
        tag = "_" + os.path.splitext(os.path.basename(vcd))[0]
        for corner, voltage, ss_r in ir_worst.JUDGED:
            r, metrics = ir_worst.run_corner(steps[-1], corner, voltage, ss_r, os.path.join(work, "corners"), ll_dir,
                                             opts.get("--power"), vcd=vcd, tag=tag)
            vals = ir_worst.drop(metrics, keys) if metrics is not None else None
            if vals:
                r.append((True, f"{corner}{tag} drop: VDD {vals[0] * 1e3:.2f} + GND {vals[1] * 1e3:.2f} = {sum(vals) * 1e3:.2f} mV"))
                drops[corner + tag] = vals
            elif metrics is not None:
                r.append((False, f"{corner}{tag} drop: {[metrics.get(k) for k in keys]} (missing or negative)"))
            rows += r
    results = os.path.join(work, "results.json")
    write_results(results, rows, drops, len(WINDOWS) * len(ir_worst.JUDGED),
                  "(max-power pattern, slow corner, the run's supply points)")
    return finish(judge(json.load(open(results)), lim), label)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
