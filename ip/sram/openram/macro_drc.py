#!/usr/bin/env python3
"""Whole-macro Magic DRC with the full rule deck, compared rule by rule with the prebuilt macro (ADR-0018).

    python3 ip/sram/openram/macro_drc.py <gds> <top> <out.json> [--baseline <json>]
    python3 ip/sram/openram/macro_drc.py --make-baseline     # the prebuilt macro from the flow PDK

Why: OpenRAM's own DRC does not use the full deck (`drc style drc(full)`) and missed the Deep N-well moat error
(nwell.5a) of the self-generated 2 KB macro; and a bitcell array always has about 2.2 million SRAM-rule
"errors", so a count alone says nothing (docs/notes/openram_phase6_bringup.md).
Runs Magic from LibreLane's nix-shell with the flow PDK (PDK_ROOT, default ~/.ciel; the SoC flow's DRC deck), then
KLayout (drc_merge.py) to merge each rule's error boxes.
PASS needs: no rule category that the baseline does not have, and for every rule, the merged error regions no more
polygons than the baseline's and no more area than the baseline's + AREA_TOL of it. The area tolerance: where a cut
line passes, Magic draws the error a little smaller, so the merged areas of identical layouts differed by up to
0.015 % (li.5, diff/tap.9; all 388 differing pieces had an edge on one macro's cut line; user decision 2026-10-11:
"塊數嚴格、面積容許 0.05%"). A new error apart from the existing ones adds a polygon and FAILs. Box counts are not compared: Magic cuts one error into several boxes
on lines every 157.28 um of the listed cell, so the self-generated 2 KB macro had 130 / 260 / 65 more diff/tap.1,
licon.5a and poly.2 boxes than the prebuilt one while their merged regions were identical (XOR 0 aligned on the
bitcell array; Phase 6 independent review, user decision 2026-10-11, ADR-0018 decision 19). Until then the check was
"total boxes <= baseline", and one new li.3 error passed (2,234,530 <= 2,235,078). Writes <out.json> (total, per-rule
boxes, merged polygons and area, new categories, problems). Negative tests: neg_openram.py D1-D7.
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
AREA_TOL = 0.0005   # relative, per rule (measured 0.015 % from Magic's cut lines; ADR-0018 decision 19)
TCL = """gds read $::env(DRC_GDS)
load $::env(DRC_TOP)
select top cell
expand
drc euclidean on
drc style drc(full)
drc check
drc catchup
drc count total
set out [open $::env(DRC_BOXES) w]
foreach {why boxes} [drc listall why] {
  puts "WHY [llength $boxes] $why"
  foreach b $boxes { puts $out "B\t$why\t$b" }
}
close $out
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


def compare(total, rules, merged, base):
    """Problems of a result (Magic total, {rule: boxes}, {rule: {"polygons", "area"}}) against a baseline dict
    {"total", "rules", "merged"} (empty = PASS)."""
    if total is None:
        return ["Magic DRC did not finish (no total)"]
    if "merged" not in base:
        return ["the baseline has no merged error regions (old format: run --make-baseline)"]
    out = []
    new = sorted(r for r in rules if r not in base["rules"])
    if new:
        out.append(f"{len(new)} rule categories not in the baseline: " + "; ".join(f"{r} ({rules[r]})" for r in new))
    unmerged = sorted(r for r in rules if r not in merged)
    if unmerged:
        out.append(f"no merged regions for {len(unmerged)} rule(s) with errors (KLayout did not run?): {unmerged[:2]}")
    worse = []
    for r in sorted(set(merged) & set(base["merged"])):
        have, want = merged[r], base["merged"][r]
        if have["polygons"] > want["polygons"] or have["area"] > want["area"] * (1 + AREA_TOL):
            worse.append(f"{r}: {have['polygons']} regions, area {have['area']} > baseline {want['polygons']}, {want['area']}")
    if worse:
        out.append(f"{len(worse)} rule(s) with more merged error regions, or area above the baseline + {AREA_TOL:.2%}: "
                   + "; ".join(worse[:3]))
    return out


def merge(boxes_tsv, out_json):
    """{rule: {"boxes", "polygons", "area"}} from drc_merge.py in KLayout, or {} when it failed."""
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drc_merge.py")
    cmd = f"klayout -b -rd src='{boxes_tsv}' -rd dst='{out_json}' -r '{script}'"
    subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, capture_output=True, text=True)
    return json.load(open(out_json)) if os.path.isfile(out_json) else {}


def run_magic(gds, top, log):
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    rc = os.path.join(PDK_ROOT, "sky130A", "libs.tech", "magic", "sky130A.magicrc")
    tcl = log + ".tcl"
    open(tcl, "w").write(TCL)
    env = dict(os.environ, PDK_ROOT=PDK_ROOT, DRC_GDS=os.path.abspath(gds), DRC_TOP=top, DRC_BOXES=log + ".boxes.tsv")
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
    log = os.path.splitext(os.path.abspath(a.out))[0] + ".magic.log"
    total, rules = parse(run_magic(a.gds, a.top, log))
    merged = merge(log + ".boxes.tsv", log + ".merged.json") if total is not None else {}
    sources = open(os.path.join(PDK_ROOT, "sky130A", "SOURCES")).read().split()
    res = {"gds": os.path.relpath(os.path.abspath(a.gds), ROOT) if os.path.abspath(a.gds).startswith(ROOT) else os.path.basename(a.gds),
           "top": a.top, "pdk": " ".join(sources[:2]), "minutes": round((time.time() - t0) / 60, 1),
           "total": total, "rules": dict(sorted(rules.items())), "merged": merged}
    if a.make_baseline:
        if total is None or sorted(merged) != sorted(rules):
            print("macro_drc: FAIL - Magic DRC did not finish, or KLayout did not merge every rule")
            return 1
        json.dump(res, open(BASELINE, "w"), indent=1, ensure_ascii=False)
        print(f"macro_drc: baseline written ({total} errors, {len(rules)} rule categories) -> {BASELINE}")
        return 0
    base = json.load(open(a.baseline))
    res["baseline"] = os.path.basename(a.baseline)
    res["new_categories"] = sorted(r for r in rules if r not in base["rules"])
    res["problems"] = compare(total, rules, merged, base)
    res["result"] = "FAIL" if res["problems"] else "PASS"
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"macro_drc: {res['result']} - {a.top}: {total} error boxes, {len(rules)} rule categories "
          f"(baseline {base['total']}, {len(base['rules'])}); merged regions and area per rule "
          + (f"within the baseline (area + {AREA_TOL:.2%})" if not res["problems"] else "; ".join(res["problems"])))
    return 1 if res["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
