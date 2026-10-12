#!/usr/bin/env python3
"""Static IR drop of a run in the slow corners, where the IR budget applies (ADR-0019 decision 19).

usage: ir_worst.py <run dir> <out dir> <limits.toml> [--ll-dir <LibreLane checkout>] [--power <power.json>]
       ir_worst.py --metrics <state_out.json> <limits.toml>        (check a result only; neg_pnr.py)

The IR budget (signoff/limits/<tag>.toml [max_sum] ir_vdd_drop_plus_gnd_rise) is the lowest supply minus
the voltage of the slow corners' libraries (1.60 V, skill pdn-ir-drop rule 4): it protects the setup timing
of the slow corners. So the drop is judged with the current, voltage and metal resistance of the same slow
corner: JUDGED, max_ss_n40C_1v60 and max_ss_100C_1v60, at 1.60 V with their own ss LAYERS_RC (user decision
2026-10-13, ADR-0019 decision 19). The flow's own IR step runs at nom_tt only.
Until then (Phase 5 exit review, user decision 2026-10-08) the judged value was "ff currents + ss metal
resistance", a combination no real corner has (skill pdn-ir-drop rule 11): it put the ff current (2.2 times
the ss one, with the SRAM port 1 floating current of ff 100C) against a budget the ff corners do not use
(their setup slack is about 8 ns, and a lower voltage helps their hold). It is still run, for the record
and for EM, as REFERENCE, and printed as [INFO] rows that do not change the verdict.

The run's own IR step is re-run with LibreLane (`python3 -m librelane.steps run --id OpenROAD.IRDropReport`,
the step's config.json and state_in.json, so the same ODB, SPEF and supply points) once per corner, with
these changes: DEFAULT_CORNER = that corner (its cell and SRAM .lib and RC SPEF), VSRC_LOC_FILES: the same
points at the corner's voltage, and the SRAM .lib of that PVT replaced by a copy whose leakage includes the
port 1 floating current (power.json static_max_mw of that PVT, next to the char .lib or --power; the .lib
leaves it out, ADR-0018 decisions 11, 19). REFERENCE corners also get LAYERS_RC["*ff*"] = LAYERS_RC["*ss*"].
For each judged corner the check requires: the step log read that PVT's libraries, the SRAM .lib copy and no
tt one, and the supply points at 1.60 V (the corner was really applied); then the larger VDD drop + GND rise
of the two judged corners <= the [max_sum] limit.
Writes <out>/ir_worst/<corner>/ (the step runs) and prints `ir-worst: PASS` / `ir-worst: FAIL` last; exit
code 0 only on PASS. Python stdlib only (LibreLane runs inside its nix-shell).
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
# (corner, supply voltage, metal resistance of ss): judged corners, then the reference combination
JUDGED = (("max_ss_n40C_1v60", "1.60", False), ("max_ss_100C_1v60", "1.60", False))
REFERENCE = (("max_ff_n40C_1v95", "1.95", True), ("max_ff_100C_1v95", "1.95", True))
KEY = "ir_vdd_drop_plus_gnd_rise"
NUM = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"


def limit(limits_path):
    spec = tomllib.load(open(limits_path, "rb")).get("max_sum", {}).get(KEY)
    if not spec or len(spec.get("keys", [])) != 2:
        return None, None
    return spec["max"], spec["keys"]


def drop(metrics, keys):
    """VDD drop + GND rise in V, or None when a key is missing or negative."""
    vals = [metrics.get(k) for k in keys]
    return None if any(not isinstance(v, (int, float)) or v < 0 for v in vals) else vals


def verdict(metrics, limits_path, applied):
    """--metrics mode: one result against the limit."""
    lim, keys = limit(limits_path)
    if lim is None:
        print(f"  [FAIL] limit: no [max_sum] {KEY} with two keys in {limits_path}")
        print("ir-worst: FAIL")
        return 1
    vals = drop(metrics, keys)
    rows = list(applied)
    if vals is None:
        rows.append((False, f"drop: {dict(zip(keys, [metrics.get(k) for k in keys]))} (missing or negative)"))
    else:
        rows.append((sum(vals) <= lim, f"drop: VDD {vals[0] * 1e3:.2f} + GND {vals[1] * 1e3:.2f} = {sum(vals) * 1e3:.2f} mV "
                                       f"vs max {lim * 1e3:.1f} mV"))
    return finish(rows)


def finish(rows, info=()):
    for ok, msg in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    for msg in info:
        print(f"  [INFO] {msg}")
    ok = bool(rows) and all(r[0] for r in rows)
    print(f"ir-worst: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def sram_lib_with_floating(cfg, pvt, power_path, dst_dir):
    """(macro, original .lib, copy with the floating current in its leakage, added mW) or a problem string."""
    hits = [(m, spec["lib"][f"*_{pvt}"][0]) for m, spec in (cfg.get("MACROS") or {}).items()
            if len((spec.get("lib") or {}).get(f"*_{pvt}", [])) == 1]
    if len(hits) != 1:
        return f"MACROS has {len(hits)} macro(s) with one *_{pvt} .lib (expected the SRAM only)"
    macro, lib = hits[0]
    power_path = power_path or os.path.join(os.path.dirname(lib), "power.json")
    try:
        add = json.load(open(power_path))["pvts"][pvt]["static_max_mw"]
    except (OSError, KeyError, ValueError) as e:
        return f"no port 1 floating current for {pvt} in {power_path}: {e!r}"
    if not isinstance(add, (int, float)) or add < 0:
        return f"static_max_mw of {pvt} in {power_path} is {add!r}"
    text = open(lib).read()
    if not re.search(r'leakage_power_unit\s*:\s*"1mW"', text):
        return f"{lib}: leakage_power_unit is not 1mW"
    cell = re.findall(r"\bcell_leakage_power\s*:\s*(" + NUM + r")\s*;", text)
    if len(cell) != 1:
        return f"{lib}: {len(cell)} cell_leakage_power values (expected 1)"
    new = f"{float(cell[0]) + add:.6f}"
    text, n = re.subn(r"(\bcell_leakage_power\s*:\s*)" + re.escape(cell[0]) + r"(\s*;)", r"\g<1>" + new + r"\2", text)
    text, m = re.subn(r"(\bleakage_power\s*\(\s*\)\s*\{\s*value\s*:\s*)" + re.escape(cell[0]) + r"(\s*;)", r"\g<1>" + new + r"\2", text)
    if (n, m) != (1, 1):
        return f"{lib}: could not add the floating current (cell_leakage_power {n}, leakage_power {m} replaced)"
    os.makedirs(dst_dir, exist_ok=True)
    copy = os.path.join(dst_dir, os.path.basename(lib))
    open(copy, "w").write(text)
    return macro, lib, copy, add


def run_corner(step, corner, voltage, ss_r, work, ll_dir, power_path):
    """(rows, metrics or None) of one corner; ss_r: metal resistance of ss instead of the corner's own."""
    pvt = corner.split("_", 1)[1]
    cdir = os.path.join(work, corner)
    os.makedirs(os.path.join(cdir, "vsrc"))
    cfg = json.load(open(os.path.join(step, "config.json")))
    cfg["DEFAULT_CORNER"] = corner
    rc = cfg.get("LAYERS_RC") or {}
    if "*ss*" not in rc or "*ff*" not in rc:
        return [(False, f"{corner}: LAYERS_RC of {step} has no *ss* and *ff* entries")], None
    if ss_r:
        rc["*ff*"] = rc["*ss*"]
    vsrc = {}
    for net, path in (cfg.get("VSRC_LOC_FILES") or {}).items():
        lines = [ln.split(",") for ln in open(path).read().split() if ln.strip()]
        dst = os.path.join(cdir, "vsrc", os.path.basename(path))
        open(dst, "w").write("".join(",".join(p[:3] + [voltage]) + "\n" for p in lines))
        vsrc[net] = dst
    if not vsrc:
        return [(False, f"{corner}: no VSRC_LOC_FILES in {step} (the one-side supply model)")], None
    cfg["VSRC_LOC_FILES"] = vsrc
    sram = sram_lib_with_floating(cfg, pvt, power_path, os.path.join(cdir, "lib"))
    if isinstance(sram, str):
        return [(False, f"{corner}: {sram}")], None
    macro, _, copy, add = sram
    cfg["MACROS"][macro]["lib"][f"*_{pvt}"] = [copy]
    cfg_path = os.path.join(cdir, "config.json")
    json.dump(cfg, open(cfg_path, "w"), indent=1)
    step_out = os.path.join(cdir, "step")
    cmd = (f"python3 -m librelane.steps run --id OpenROAD.IRDropReport -c '{cfg_path}' "
           f"-i '{os.path.join(step, 'state_in.json')}' -o '{step_out}'")
    with open(os.path.join(cdir, "console.log"), "w") as log:
        rc_run = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, stdout=log, stderr=subprocess.STDOUT).returncode
    state = os.path.join(step_out, "state_out.json")
    if rc_run != 0 or not os.path.isfile(state):
        return [(False, f"{corner}: the IR step run failed (rc {rc_run}); see {os.path.join(cdir, 'console.log')}")], None
    logs = "".join(open(p, errors="replace").read() for p in glob.glob(os.path.join(step_out, "*.log")))
    pvt_libs = set(re.findall(r"\S*" + re.escape(pvt) + r"\S*\.lib", logs))
    rows = [(bool(pvt_libs) and "tt_025C_1v80.lib" not in logs and copy in logs,
             f"{corner} currents: the step read {len(pvt_libs)} {pvt} .lib file(s), the SRAM copy with the port 1 "
             f"floating current (+{add:.3f} mW) and no tt one"),
            (all(ln.endswith("," + voltage) for p in vsrc.values() for ln in open(p).read().split()),
             f"{corner} supply points: the run's {sum(len(open(p).read().split()) for p in vsrc.values())} points at {voltage} V")]
    if ss_r:
        rows.append((json.load(open(cfg_path))["LAYERS_RC"]["*ff*"] == json.load(open(os.path.join(step, "config.json")))["LAYERS_RC"]["*ss*"],
                     f"{corner} ss metal resistance: LAYERS_RC *ff* = the run's *ss* values"))
    return rows, json.load(open(state)).get("metrics", {})


def main(argv):
    if argv[:1] == ["--metrics"] and len(argv) == 3:
        return verdict(json.load(open(argv[1])).get("metrics", {}), argv[2], [])
    pos, opts = [], {}
    it = iter(argv)
    for a in it:
        if a in ("--ll-dir", "--power"):
            opts[a] = os.path.abspath(next(it, ""))
        else:
            pos.append(a)
    if len(pos) != 3:
        print(__doc__.split("\n\n")[1])
        return 2
    run, out, limits_path = (os.path.abspath(a) for a in pos)
    ll_dir = opts.get("--ll-dir") or os.environ.get("LIBRELANE_DIR") or os.path.join(ROOT, ".tools", "librelane")
    lim, keys = limit(limits_path)
    if lim is None:
        return finish([(False, f"limit: no [max_sum] {KEY} with two keys in {limits_path}")])
    steps = sorted((d for d in glob.glob(os.path.join(run, "[0-9]*-openroad-irdropreport*"))
                    if os.path.isfile(os.path.join(d, "state_out.json"))), key=lambda d: int(os.path.basename(d).split("-")[0]))
    if not steps:
        return finish([(False, f"no finished OpenROAD.IRDropReport step in {run}")])
    work = os.path.join(out, "ir_worst")
    shutil.rmtree(work, ignore_errors=True)   # only this check's own output
    rows, info, drops = [], [], {}
    for corners, judged in ((JUDGED, True), (REFERENCE, False)):
        for corner, voltage, ss_r in corners:
            r, metrics = run_corner(steps[-1], corner, voltage, ss_r, work, ll_dir, opts.get("--power"))
            vals = drop(metrics, keys) if metrics is not None else None
            if metrics is not None:
                r.append((vals is not None, f"{corner} drop: " + (f"VDD {vals[0] * 1e3:.2f} + GND {vals[1] * 1e3:.2f} = {sum(vals) * 1e3:.2f} mV"
                          if vals else f"{dict(zip(keys, [metrics.get(k) for k in keys]))} (missing or negative)")))
            if judged:
                rows += r
                if vals:
                    drops[corner] = vals
            else:   # reference (ff currents + ss metal R): recorded, not judged
                info += [("" if ok else "not applied: ") + msg + ("" if "drop:" not in msg else " (reference: ff currents + port 1 floating current + ss metal R)")
                         for ok, msg in r]
    if len(drops) == len(JUDGED):
        worst = max(drops, key=lambda c: sum(drops[c]))
        rows.append((sum(drops[worst]) <= lim, f"drop: worst {worst} {sum(drops[worst]) * 1e3:.2f} mV "
                                               f"(slow-corner currents + port 1 floating current + ss metal R) vs max {lim * 1e3:.1f} mV"))
    return finish(rows, info)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
