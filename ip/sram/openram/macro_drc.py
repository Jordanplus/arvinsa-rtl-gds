#!/usr/bin/env python3
"""Whole-macro Magic DRC with the full rule deck, compared rule by rule with the prebuilt macro (ADR-0018).

    python3 ip/sram/openram/macro_drc.py <gds> <top> <out.json> [--baseline <json>]
    python3 ip/sram/openram/macro_drc.py --make-baseline     # the prebuilt macro from the flow PDK

Why: OpenRAM's own DRC does not use the full deck (`drc style drc(full)`) and missed the Deep N-well moat error
(nwell.5a) of the self-generated 2 KB macro; and a bitcell array always has about 2.2 million SRAM-rule
"errors", so a count alone says nothing (docs/notes/openram_phase6_bringup.md).
Runs Magic from LibreLane's nix-shell with the flow PDK (PDK_ROOT, default ~/.ciel; the SoC flow's DRC deck).
PASS needs: no rule category missing from the baseline, and total <= baseline total. Writes <out.json>
(total, per-rule counts, new categories, problems). Negative tests: neg_openram.py D1-D3.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PDK_ROOT = os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel"))
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drc_baseline_sky130_sram_2kbyte_1rw1r_32x512_8.json")
PREBUILT = "sky130_sram_2kbyte_1rw1r_32x512_8"
TCL = """gds read $::env(DRC_GDS)
load $::env(DRC_TOP)
select top cell
expand
drc euclidean on
drc style drc(full)
drc check
drc catchup
drc count total
foreach {why boxes} [drc listall why] { puts "WHY [llength $boxes] $why" }
puts "MAGIC_DRC_DONE"
quit -noprompt
"""


def parse(text):
    """(total, {rule: boxes}) from the Magic log; total None when the run did not finish."""
    if "MAGIC_DRC_DONE" not in text:
        return None, {}
    m = re.findall(r"Total DRC errors found: (\d+)", text)
    rules = {}
    for n, why in re.findall(r"^WHY (\d+) (.+)$", text, re.M):
        rules[why.strip()] = rules.get(why.strip(), 0) + int(n)
    return (int(m[-1]) if m else None), rules


def compare(total, rules, base):
    """Problems of a result against a baseline dict {"total": n, "rules": {...}} (empty = PASS)."""
    if total is None:
        return ["Magic DRC did not finish (no total)"]
    out = []
    new = sorted(r for r in rules if r not in base["rules"])
    if new:
        out.append(f"{len(new)} rule categories not in the baseline: " + "; ".join(f"{r} ({rules[r]})" for r in new))
    if total > base["total"]:
        out.append(f"total {total} > baseline {base['total']}")
    return out


def run_magic(gds, top, log):
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    rc = os.path.join(PDK_ROOT, "sky130A", "libs.tech", "magic", "sky130A.magicrc")
    tcl = log + ".tcl"
    open(tcl, "w").write(TCL)
    env = dict(os.environ, PDK_ROOT=PDK_ROOT, DRC_GDS=os.path.abspath(gds), DRC_TOP=top)
    cmd = f"magic -dnull -noconsole -rcfile '{rc}' '{tcl}'"
    with open(log, "w") as f:
        f.write(f"$ (cd {ll_dir} && PDK_ROOT={PDK_ROOT} nix-shell --run {cmd!r})\n")
        f.flush()
        subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, env=env, stdout=f, stderr=subprocess.STDOUT)
    return open(log, encoding="utf-8", errors="replace").read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gds", nargs="?")
    ap.add_argument("top", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--baseline", default=BASELINE)
    ap.add_argument("--make-baseline", action="store_true")
    a = ap.parse_args()
    if a.make_baseline:
        a.gds = os.path.join(PDK_ROOT, "sky130A", "libs.ref", "sky130_sram_macros", "gds", PREBUILT + ".gds")
        a.top, a.out = PREBUILT, os.path.join(ROOT, "runs", "openram", "drc_baseline.json")
    if not (a.gds and a.top and a.out):
        ap.error("gds, top and out are required (or --make-baseline)")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    t0 = time.time()
    # absolute: Magic runs in LibreLane's directory, where a relative Tcl path does not exist
    total, rules = parse(run_magic(a.gds, a.top, os.path.splitext(os.path.abspath(a.out))[0] + ".magic.log"))
    sources = open(os.path.join(PDK_ROOT, "sky130A", "SOURCES")).read().split()
    res = {"gds": os.path.relpath(os.path.abspath(a.gds), ROOT) if os.path.abspath(a.gds).startswith(ROOT) else os.path.basename(a.gds),
           "top": a.top, "pdk": " ".join(sources[:2]), "minutes": round((time.time() - t0) / 60, 1),
           "total": total, "rules": dict(sorted(rules.items()))}
    if a.make_baseline:
        if total is None:
            print("macro_drc: FAIL - Magic DRC did not finish")
            return 1
        json.dump(res, open(BASELINE, "w"), indent=1, ensure_ascii=False)
        print(f"macro_drc: baseline written ({total} errors, {len(rules)} rule categories) -> {BASELINE}")
        return 0
    base = json.load(open(a.baseline))
    res["baseline"] = os.path.basename(a.baseline)
    res["new_categories"] = sorted(r for r in rules if r not in base["rules"])
    res["problems"] = compare(total, rules, base)
    res["result"] = "FAIL" if res["problems"] else "PASS"
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"macro_drc: {res['result']} - {a.top}: {total} errors, {len(rules)} rule categories "
          f"(baseline {base['total']}, {len(base['rules'])})" + (f"; {'; '.join(res['problems'])}" if res["problems"] else ""))
    return 1 if res["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
