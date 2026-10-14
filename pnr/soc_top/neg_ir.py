#!/usr/bin/env python3
"""make neg-ir-soc / neg-ir-caravel: bug injection into the IR checks with the max-power pattern (ADR-0019 decisions
20, 25): ir_pattern.py (soc_top), ir_caravel.py (the wrapper from Caravel's pads) and the recording of the windows
(run_gl_soc.py --record-window, dv/gl_soc/vcd_window.v).

usage: neg_ir.py --design soc_top_hazard3|user_project_wrapper [--out <dir>] [--run <harden run>] [--pos <check out>]
                 [--vcd-dir <dir>]   (the defaults are the regression's paths; the others are for a dev fixture)

Runs after the positive check of the same design in the regression (make ir-soc / make ir-caravel) and uses its
outputs: <ir out>/<check>/results.json (the rows and drops of every window x slow corner) and the window VCDs.
Every case must FAIL at its own line (the expected text in a [FAIL] row, and `<label>: FAIL`); the positive
controls must PASS.
  both designs
    positive         the positive run's results.json re-judged with the real limit                    PASS
    limit_above      limit = worst + 0.01 mV                                                           PASS
    limit_below      limit = worst - 0.01 mV                                                           "drop: worst"
    missing_result   one window x corner result removed (a run that failed without a row)              "window x corner results"
    failed_row       one row of the run turned FAIL (e.g. a corner not applied)                        that row's text
    nan_drop         the second drop of results.json turned NaN (max() skipped it; review H4)          "not a finite number"
    one_window       the checker with --vcd win_5b only (review H3)                                    "windows:"
    period           win_5a with every time stamp x 1.1 (recorded at 48.4 ns, not CLOCK_PERIOD; H2)   "activity period"
  soc_top_hazard3 (the code shared with ir_caravel.py: ir_worst.run_corner, the recording)
    no_vcd           --vcd of a file that does not exist                                               "switching activity"
    unannotated      window 5a with every variable moved to a scope dut_xx but its clock (the period   "pins annotated from win_5a"
                     check needs it), with 5b, 5c as they are: the IR step runs, annotates no logic pin
    stray_dump       recording with an extra plusarg beginning with "vcd" (tb_soc.v dumps the whole     "testbench dump"
                     testbench into wave.vcd from time 0 and the window's own $dumpfile is ignored)
    no_window        recording of a window the firmware never marks (gpio 0xee)                         "0 cycles recorded"
  user_project_wrapper (what only ir_caravel.py has)
    bridge_missing   Caravel's data (IR_CARAVEL_DATA) with the first met3 bridge removed               "met3 bridges"
    pad_missing      the same with the first pad strap removed                                          "pad straps"
Outputs: <out>/<case>/ (default runs/neg_ir_<design>). Prints `neg-ir: PASS n/n` / `FAIL ...`; exit 0 only on PASS.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import ir_worst  # noqa: E402

PY = sys.executable
IR_PATTERN = os.path.join(HERE, "ir_pattern.py")
IR_CARAVEL = os.path.join(ROOT, "pnr", "user_project_wrapper", "ir_caravel.py")
RUN_GL = os.path.join(ROOT, "dv", "gl_soc", "run_gl_soc.py")
DESIGNS = {   # label, harden run, limits, [max_sum] key, positive check output, VCD directory, CPU of run_gl_soc
    "soc_top_hazard3": ("ir-soc", "runs/soc_top_hazard3", "signoff/limits/soc_top_hazard3.toml", ir_worst.KEY,
                        "runs/ir_soc/ir_pattern", "runs/ir_soc_vcd", "hazard3"),
    "user_project_wrapper": ("ir-caravel", "runs/user_project_wrapper", "signoff/limits/user_project_wrapper.toml",
                             "ir_caravel_vdd_drop_plus_gnd_rise", "runs/ir_caravel/ir_caravel", "runs/ir_caravel_vcd", "caravel"),
}


def limits_file(path, keys, lim):
    """A limits file with only the [max_sum] row ir_pattern.py --judge reads."""
    open(path, "w").write(f'[max_sum]\n"{ir_worst.KEY}" = {{ keys = {json.dumps(keys)}, max = {lim!r} }}\n')
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--design", required=True, choices=sorted(DESIGNS))
    ap.add_argument("--out")
    ap.add_argument("--run")
    ap.add_argument("--pos")
    ap.add_argument("--vcd-dir")
    args = ap.parse_args()
    label, run, limits, key, pos_dir, vcd_dir, cpu = DESIGNS[args.design]
    run, pos_dir, vcd_dir = args.run or run, args.pos or pos_dir, args.vcd_dir or vcd_dir
    run, limits, pos_dir, vcd_dir = (os.path.abspath(os.path.join(ROOT, p)) for p in (run, limits, pos_dir, vcd_dir))
    out = os.path.abspath(args.out or os.path.join(ROOT, "runs", f"neg_ir_{args.design}"))
    shutil.rmtree(out, ignore_errors=True)   # only this test's own output
    os.makedirs(out)
    results_path = os.path.join(pos_dir, "results.json")
    spec = __import__("tomllib").load(open(limits, "rb")).get("max_sum", {}).get(key)
    try:
        results = json.load(open(results_path))
    except (OSError, ValueError) as e:
        print(f"neg-ir: FAIL cannot read the positive run's {results_path} ({e}); run make {label} first")
        return 1
    if not spec or not results.get("drops"):
        print(f"neg-ir: FAIL no [max_sum] {key} in {limits} or no drops in {results_path}")
        return 1
    keys, lim = spec["keys"], spec["max"]
    worst = max(sum(v) for v in results["drops"].values())

    def judge_case(d, res, lim_):
        rp = os.path.join(d, "results.json")
        json.dump(res, open(rp, "w"), indent=1)
        return [PY, IR_PATTERN, "--judge", rp, limits_file(os.path.join(d, "limits.toml"), keys, lim_), "--label", label]

    def missing(d):
        res = json.loads(json.dumps(results))
        del res["drops"][sorted(res["drops"])[0]]   # its rows stay PASS: only the count can catch it
        return judge_case(d, res, lim)

    def failed_row(d):
        res = json.loads(json.dumps(results))
        res["rows"][0][0] = False
        return judge_case(d, res, lim)

    def nan_drop(d):
        res = json.loads(json.dumps(results))
        res["drops"][sorted(res["drops"])[1]][0] = float("nan")
        return judge_case(d, res, lim)

    vcd = {w: os.path.join(vcd_dir, f"win_{w}.vcd") for w in ("5a", "5b", "5c")}
    checker = IR_PATTERN if args.design == "soc_top_hazard3" else IR_CARAVEL

    def run_checker(d, vcds):
        return [PY, checker, run, os.path.join(d, "ir"), limits] + sum((["--vcd", v] for v in vcds), []) \
            + (["--label", label] if checker == IR_PATTERN else [])

    def period(d):
        bad = os.path.join(d, "win_5a.vcd")
        with open(vcd["5a"]) as src, open(bad, "w") as dst:
            for line in src:
                dst.write(f"#{round(int(line[1:]) * 1.1)}\n" if line[0] == "#" else line)
        return run_checker(d, [bad, vcd["5b"], vcd["5c"]])

    cases = [  # (name, command builder(dir), expected text in a FAIL row or None for PASS, env)
        ("positive", lambda d: judge_case(d, results, lim), None, None),
        ("limit_above", lambda d: judge_case(d, results, worst + 1e-5), None, None),
        ("limit_below", lambda d: judge_case(d, results, worst - 1e-5), "drop: worst", None),
        ("missing_result", missing, "window x corner results", None),
        ("failed_row", failed_row, results["rows"][0][1] if results["rows"] else "?", None),
        ("nan_drop", nan_drop, "not a finite number", None),
        ("one_window", lambda d: run_checker(d, [vcd["5b"]]), "windows:", None),
        ("period", period, "activity period", None),
    ]
    vcd5a = vcd["5a"]
    if args.design == "soc_top_hazard3":
        def unannotated(d):
            bad = os.path.join(d, "win_5a.vcd")
            port = json.load(open(os.path.join(run, "resolved.json")))["CLOCK_PORT"]
            n, clk, depth = 0, None, 0
            with open(vcd5a) as src, open(bad, "w") as dst:
                for line in src:
                    w = line.split()
                    if line.startswith("$scope module dut_gl "):
                        line, n = line.replace("dut_gl", "dut_xx", 1), n + 1
                    if w[:1] == ["$scope"]:
                        depth += 1
                    elif w[:1] == ["$upscope"]:
                        depth -= 1
                    elif depth == 2 and w[:1] == ["$var"] and len(w) > 4 and w[4] == port:
                        clk = w[3]
                    if line.startswith("$enddefinitions"):   # the clock alone stays in dut_gl (the period check)
                        dst.write(f"$scope module tb_soc $end\n$scope module dut_gl $end\n$var wire 1 {clk} {port} $end\n"
                                  "$upscope $end\n$upscope $end\n")
                        dst.write(line)
                        dst.writelines(src)   # the value changes, unchanged
                        break
                    dst.write(line)
            if n != 1 or clk is None:
                raise RuntimeError(f"{vcd5a}: {n} '$scope module dut_gl' lines (expected 1), clock {port} {clk}")
            return run_checker(d, [bad, vcd["5b"], vcd["5c"]])

        def record(gpio, extra):
            return lambda d: [PY, RUN_GL, "--cpu", cpu, "--harden-run", run, "--tests", "maxpower", "--out", os.path.join(d, "vcd"),
                              "--record-window", gpio] + sum((["--plusarg", p] for p in extra), [])

        cases += [
            ("no_vcd", lambda d: [PY, IR_PATTERN, run, os.path.join(d, "ir"), limits, "--vcd", os.path.join(d, "none.vcd"),
                                  "--label", label], "switching activity", None),
            ("unannotated", unannotated, "pins annotated from win_5a", None),
            ("stray_dump", record("5a", ["vcd_extra"]), "testbench dump", None),
            ("no_window", record("ee", []), "0 cycles recorded", None),
        ]
    else:
        data = os.path.join(ROOT, "pnr", "user_project_wrapper", "caravel_pwr")

        def without_first(name):
            def build(d):
                dd = os.path.join(d, "caravel_pwr")
                shutil.copytree(data, dd)
                lines = open(os.path.join(dd, name)).read().splitlines(keepends=True)
                i = next(i for i, l in enumerate(lines) if l.strip() and not l.startswith("#"))
                open(os.path.join(dd, name), "w").writelines(lines[:i] + lines[i + 1:])
                return run_checker(d, [vcd["5a"], vcd["5b"], vcd["5c"]])
            return build

        cases += [
            ("bridge_missing", without_first("bridges.txt"), "met3 bridges", "IR_CARAVEL_DATA"),
            ("pad_missing", without_first("pads.txt"), "pad straps", "IR_CARAVEL_DATA"),
        ]
    ok_all, n_ok = True, 0
    for name, build, want, env_key in cases:
        d = os.path.join(out, name)
        os.makedirs(d)
        try:
            cmd = build(d)
        except (OSError, RuntimeError, StopIteration) as e:
            print(f"  [FAIL] {name}: cannot build the case ({e})")
            ok_all = False
            continue
        env = dict(os.environ)
        if env_key:
            env[env_key] = os.path.join(d, "caravel_pwr")
        c = subprocess.run(cmd, capture_output=True, text=True, env=env)
        open(os.path.join(d, "run.log"), "w").write(c.stdout + c.stderr)
        last = [l for l in c.stdout.splitlines() if l.strip()][-1:] or [""]
        fails = [l for l in c.stdout.splitlines() if "[FAIL]" in l]
        verdict = re.match(r"^(\S+): (PASS|FAIL)", last[0])
        if want is None:
            ok = c.returncode == 0 and verdict is not None and verdict.group(2) == "PASS" and not fails
        else:
            ok = c.returncode != 0 and verdict is not None and verdict.group(2) == "FAIL" and any(want in l for l in fails)
        ok_all &= ok
        n_ok += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: " + ("PASS" if want is None else f"FAIL at {want!r}")
              + ("" if ok else f" (exit {c.returncode}, last line {last[0]!r}; see {os.path.relpath(d, ROOT)}/run.log)"), flush=True)
    print(f"neg-ir: {'PASS' if ok_all else 'FAIL'} {n_ok}/{len(cases)} ({args.design}, worst {worst * 1e3:.2f} mV, limit {lim * 1e3:.1f} mV)")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
