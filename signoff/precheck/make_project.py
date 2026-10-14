#!/usr/bin/env python3
"""The project directory ChipFoundry's precheck runs on, from a harden run of user_project_wrapper (Phase 7 step 7,
ADR-0019).

usage: make_project.py --run runs/user_project_wrapper --out <dir> [--verification]

cf-precheck 1.3.7 reads (config.py get_project_config, checks/*): gds/user_project_wrapper.gds,
verilog/gl/user_project_wrapper.v (the powered netlist, LVS), verilog/rtl/user_defines.v (gpio_defines, oeb) and
lvs/user_project_wrapper/lvs_config.json. The LVS configuration follows ChipFoundry's caravel_user_sram example
(adf59a8f): the SRAM cell is in EXTRACT_ABSTRACT, and the netlist has no module for it, so Netgen compares it as a
black box (ADR-0019 decision 7). Paths in lvs_config.json start with $PDK_ROOT / $UPRJ_ROOT (config.py rejects others).
Files are copied, not linked: the precheck VM mounts only its work directory.

The run must pass the run guard (signoff/scripts/run_guard.py: harden PASS, made from HEAD). --verification skips that
for a check of an older run; arvinsa_source.json in <out> records the run, its commit, HEAD and whether the guard
passed, and check_precheck.py prints it. <out> is replaced only if it is missing or was made by this script.
Prints `precheck-project: PASS ...` / `FAIL ...`.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "signoff", "scripts"))
from run_guard import guard, head  # noqa: E402

TOP = "user_project_wrapper"
MACRO = "arv_sram_2kbyte_1rw1r_32x512_8"
MARK = "arvinsa_source.json"


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def lvs_config():
    return {
        "TOP_SOURCE": TOP,
        "TOP_LAYOUT": "$TOP_SOURCE",
        "EXTRACT_FLATGLOB": [""],
        "EXTRACT_ABSTRACT": ["*__fill_*", "*__fakediode_*", "*__tapvpwrvgnd_*", MACRO],
        "EXTRACT_CREATE_SUBCUT": [""],
        "LVS_FLATTEN": [""],
        "LVS_NOFLATTEN": [""],
        "LVS_IGNORE": [""],
        "LVS_SPICE_FILES": ["$PDK_ROOT/$PDK/libs.ref/sky130_fd_sc_hd/spice/sky130_ef_sc_hd__decap*.spice",
                            "$PDK_ROOT/$PDK/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"],
        "LVS_VERILOG_FILES": ["$UPRJ_ROOT/verilog/gl/$TOP_SOURCE.v"],
        "LAYOUT_FILE": "$UPRJ_ROOT/gds/$TOP_LAYOUT.gds",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default=os.path.join(ROOT, "runs", TOP))
    ap.add_argument("--out", required=True)
    ap.add_argument("--verification", action="store_true", help="skip the run guard (not a formal result)")
    args = ap.parse_args()
    run, out = os.path.abspath(args.run), os.path.abspath(args.out)
    errs = guard(run, "harden-soc: PASS")
    if errs and not args.verification:
        print("precheck-project: FAIL " + "; ".join(errs))
        return 1
    if os.path.exists(out) and not os.path.exists(os.path.join(out, MARK)):
        print(f"precheck-project: FAIL {out} exists and was not made by make_project.py; not removed")
        return 1
    files = {
        f"gds/{TOP}.gds": os.path.join(run, "final", "gds", f"{TOP}.gds"),
        f"verilog/gl/{TOP}.v": os.path.join(run, "final", "pnl", f"{TOP}.pnl.v"),
        "verilog/rtl/user_defines.v": os.path.join(ROOT, "rtl", "caravel", "user_defines.v"),
    }
    missing = [s for s in files.values() if not os.path.isfile(s)]
    if missing:
        print(f"precheck-project: FAIL not found: {missing}")
        return 1
    shutil.rmtree(out, ignore_errors=True)
    for dst, src in files.items():
        os.makedirs(os.path.dirname(os.path.join(out, dst)), exist_ok=True)
        shutil.copyfile(src, os.path.join(out, dst))
    lvs = os.path.join(out, "lvs", TOP, "lvs_config.json")
    os.makedirs(os.path.dirname(lvs))
    json.dump(lvs_config(), open(lvs, "w"), indent="\t")
    prov = json.load(open(run + "_signoff/provenance.json")) if os.path.exists(run + "_signoff/provenance.json") else {}
    src = {"run": os.path.relpath(run, ROOT), "run_commit": prov.get("repo_head"), "head": head(),
           "run_guard": errs or "PASS", "verification": bool(args.verification),
           "files": {d: {"from": os.path.relpath(s, ROOT), "sha1": sha1(os.path.join(out, d))} for d, s in files.items()}}
    json.dump(src, open(os.path.join(out, MARK), "w"), indent=1)
    kind = "verification (run guard skipped: " + "; ".join(errs) + ")" if errs else "formal (run guard PASS)"
    print(f"precheck-project: PASS {out} from {src['run']} ({src['run_commit']}), {kind}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
