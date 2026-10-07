#!/usr/bin/env python3
"""Worst-case static IR drop of a soc_top run: ff currents with ss metal resistance (Phase 5 exit review).

usage: ir_worst.py <run dir> <out dir> <limits.toml> [--ll-dir <LibreLane checkout>]
       ir_worst.py --metrics <state_out.json> <limits.toml>        (check a result only; neg_pnr.py)

The flow's IR step (OpenROAD.IRDropReport) runs at nom_tt, and the limit (signoff/limits/<tag>.toml
[max_sum] ir_vdd_drop_plus_gnd_rise, 20 mV) was accepted for nom_tt in Phase 4 only because the worst
combination, "ff currents + ss metal resistance", measured 11.46 mV on the PicoRV32 layout
(docs/notes/ir_worst_case_soc_top.md). On the Hazard3 layout that combination measured 25.75 mV
while nom_tt was 18.28 mV (Phase 5 exit review, user decision 2026-10-08: check it in every run).
No real corner has both (skill pdn-ir-drop rule 11), so this is an upper bound made on purpose.

The run's own IR step is re-run once with LibreLane (`python3 -m librelane.steps run --id
OpenROAD.IRDropReport`, the step's config.json and state_in.json, so the same ODB, SPEF and supply
points), with three changes: DEFAULT_CORNER = max_ff_n40C_1v95 (ff cell and SRAM .lib, 1.95 V,
the max-RC SPEF), LAYERS_RC["*ff*"] = LAYERS_RC["*ss*"] (the grid's metal resistance of ss), and
VSRC_LOC_FILES: the same points at 1.95 V (<out>/ir_worst/vsrc/). The check then requires:
  the step log read the ff_n40C_1v95 libraries and the config carries the ss resistance (the
  combination was really applied), and VDD drop + GND rise <= the [max_sum] limit.
Writes <out>/ir_worst/ (the step run) and prints `ir-worst: PASS` / `ir-worst: FAIL` last; exit
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
CORNER = "max_ff_n40C_1v95"
VOLTAGE = "1.95"
KEY = "ir_vdd_drop_plus_gnd_rise"


def limit(limits_path):
    spec = tomllib.load(open(limits_path, "rb")).get("max_sum", {}).get(KEY)
    if not spec or len(spec.get("keys", [])) != 2:
        return None, None
    return spec["max"], spec["keys"]


def verdict(metrics, limits_path, applied):
    lim, keys = limit(limits_path)
    if lim is None:
        print(f"  [FAIL] limit: no [max_sum] {KEY} with two keys in {limits_path}")
        print("ir-worst: FAIL")
        return 1
    vals = [metrics.get(k) for k in keys]
    rows = list(applied)
    if any(not isinstance(v, (int, float)) or v < 0 for v in vals):
        rows.append((False, f"drop: {dict(zip(keys, vals))} (missing or negative)"))
    else:
        total = sum(vals)
        rows.append((total <= lim, f"drop: VDD {vals[0] * 1e3:.2f} + GND {vals[1] * 1e3:.2f} = {total * 1e3:.2f} mV "
                                   f"(ff currents + ss metal R) vs max {lim * 1e3:.1f} mV"))
    for ok, msg in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    ok = all(r[0] for r in rows)
    print(f"ir-worst: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv):
    if argv[:1] == ["--metrics"] and len(argv) == 3:
        return verdict(json.load(open(argv[1])).get("metrics", {}), argv[2], [])
    if len(argv) not in (3, 5) or (len(argv) == 5 and argv[3] != "--ll-dir"):
        print(__doc__.split("\n\n")[1])
        return 2
    run, out, limits_path = (os.path.abspath(a) for a in argv[:3])
    ll_dir = os.path.abspath(argv[4]) if len(argv) == 5 else os.environ.get("LIBRELANE_DIR") or os.path.join(ROOT, ".tools", "librelane")
    steps = sorted((d for d in glob.glob(os.path.join(run, "[0-9]*-openroad-irdropreport*"))
                    if os.path.isfile(os.path.join(d, "state_out.json"))), key=lambda d: int(os.path.basename(d).split("-")[0]))
    if not steps:
        print(f"  [FAIL] no finished OpenROAD.IRDropReport step in {run}")
        print("ir-worst: FAIL")
        return 1
    step = steps[-1]
    work = os.path.join(out, "ir_worst")
    shutil.rmtree(work, ignore_errors=True)   # only this check's own output
    os.makedirs(os.path.join(work, "vsrc"))
    cfg = json.load(open(os.path.join(step, "config.json")))
    cfg["DEFAULT_CORNER"] = CORNER
    rc = cfg.get("LAYERS_RC") or {}
    if "*ss*" not in rc or "*ff*" not in rc:
        print(f"  [FAIL] LAYERS_RC of {step} has no *ss* and *ff* entries")
        print("ir-worst: FAIL")
        return 1
    rc["*ff*"] = rc["*ss*"]
    vsrc = {}
    for net, path in (cfg.get("VSRC_LOC_FILES") or {}).items():
        lines = [ln.split(",") for ln in open(path).read().split() if ln.strip()]
        dst = os.path.join(work, "vsrc", os.path.basename(path))
        open(dst, "w").write("".join(",".join(p[:3] + [VOLTAGE]) + "\n" for p in lines))
        vsrc[net] = dst
    if not vsrc:
        print(f"  [FAIL] no VSRC_LOC_FILES in {step} (the one-side supply model)")
        print("ir-worst: FAIL")
        return 1
    cfg["VSRC_LOC_FILES"] = vsrc
    cfg_path = os.path.join(work, "config.json")
    json.dump(cfg, open(cfg_path, "w"), indent=1)
    step_out = os.path.join(work, "step")
    cmd = (f"python3 -m librelane.steps run --id OpenROAD.IRDropReport -c '{cfg_path}' "
           f"-i '{os.path.join(step, 'state_in.json')}' -o '{step_out}'")
    with open(os.path.join(work, "console.log"), "w") as log:
        rc_run = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, stdout=log, stderr=subprocess.STDOUT).returncode
    state = os.path.join(step_out, "state_out.json")
    if rc_run != 0 or not os.path.isfile(state):
        print(f"  [FAIL] the IR step run failed (rc {rc_run}); see {os.path.join(work, 'console.log')}")
        print("ir-worst: FAIL")
        return 1
    logs = "".join(open(p, errors="replace").read() for p in glob.glob(os.path.join(step_out, "*.log")))
    ff_libs = re.findall(r"\S*ff_n40C_1v95\S*\.lib", logs)
    applied = [(bool(ff_libs) and "tt_025C_1v80.lib" not in logs, f"ff currents: the step read {len(set(ff_libs))} "
                f"ff_n40C_1v95 .lib file(s) and no tt one"),
               (json.load(open(cfg_path))["LAYERS_RC"]["*ff*"] == json.load(open(os.path.join(step, "config.json")))["LAYERS_RC"]["*ss*"],
                "ss metal resistance: LAYERS_RC *ff* = the run's *ss* values"),
               (all(ln.endswith("," + VOLTAGE) for p in vsrc.values() for ln in open(p).read().split()),
                f"supply points: the run's {sum(len(open(p).read().split()) for p in vsrc.values())} points at {VOLTAGE} V")]
    return verdict(json.load(open(state)).get("metrics", {}), limits_path, applied)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
