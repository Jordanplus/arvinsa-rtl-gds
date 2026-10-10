#!/usr/bin/env python3
"""Whole-macro KLayout DRC (sky130A_mr.drc, the deck of the SoC flow's KLayout DRC); PASS only with 0 errors (ADR-0018
decision 17).

    python3 ip/sram/openram/macro_klayout_drc.py <gds> <top> <out.json>

Why (2026-10-10): the macro passed OpenRAM's DRC and the Magic full deck against the prebuilt baseline (macro_drc.py),
but once it really was in the SoC GDS, the flow's KLayout DRC found 27 errors in it (nwell.6, psdm.1, m2.2), which
OpenRAM's generator made (docs/notes/openram_phase6_bringup.md steps 4b and 3m). The prebuilt macro has 0 (also
renamed), so the target is 0. The deck leaves cells named `*sky130_sram_*kbyte_*` out of nwell.6 always and out of
the nsdm/psdm checks with sram_exclude on, so such a name (macro or a cell in it) is a FAIL here.
Runs KLayout from LibreLane's nix-shell with the flow PDK (PDK_ROOT, default ~/.ciel). Writes <out.json> (total,
counts per rule and per cell, problems) and <out>.lyrdb. Negative tests: neg_openram.py K1-K5.
"""
import argparse
import collections
import fnmatch
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PDK_ROOT = os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel"))
DECK = os.path.join("sky130A", "libs.tech", "klayout", "drc", "sky130A_mr.drc")
# the deck's own cell exclusion (`layout(...).select("-*sky130_sram_*kbyte_*")`: nwell.6, and nsdm/psdm with sram_exclude)
EXCLUDED = "*sky130_sram_*kbyte_*"
# the deck options of the flow's KLayout DRC (KLAYOUT_DRC_DEFINES in runs/soc_top/*-klayout-drc/config.json), plus
# sram_exclude off
OPTIONS = {"feol": "1", "beol": "1", "floating_metal": "0", "offgrid": "1", "seal": "1", "sram_exclude": "false",
           "threads": "6"}
# rules that must be in the report, else the front or back end checks did not run
REQUIRED = ("nwell.2a", "psdm.1", "nsdm.1", "m2.2", "li.1")
CELLS = """import pya
ly = pya.Layout()
ly.read(src)
print("CELLS " + " ".join(c.name for c in ly.each_cell()))
"""


def parse(lyrdb, top):
    """(problems, {rule: n}, {cell: n}) of a KLayout report database."""
    if not os.path.isfile(lyrdb):
        return ["KLayout DRC wrote no report (did not finish)"], {}, {}
    text = open(lyrdb, encoding="utf-8", errors="replace").read()
    out = []
    m = re.search(r"<top-cell>([^<]*)</top-cell>", text)
    if not m or m.group(1) != top:
        out.append(f"report top cell is {m.group(1) if m else 'missing'}, not {top}")
    names = set(re.findall(r"<category>\s*<name>'?([^<']+)'?</name>", text))
    missing = [r for r in REQUIRED if r not in names]
    if missing:
        out.append(f"rules {missing} not in the report (the deck did not run them)")
    rules, cells = collections.Counter(), collections.Counter()
    for item in re.findall(r"<item>.*?</item>", text, re.S):
        rule = re.search(r"<category>'?([^<']+)'?</category>", item)
        cell = re.search(r"<cell>([^<]*)</cell>", item)
        rules[rule.group(1) if rule else "?"] += 1
        cells[cell.group(1) if cell else "?"] += 1
    if rules:
        out.append("errors per rule: " + ", ".join(f"{r} {n}" for r, n in rules.most_common()))
    return out, dict(rules), dict(cells)


def excluded(cells):
    """Cell names the deck would leave out of its nwell/nsdm/psdm checks."""
    return sorted(c for c in cells if fnmatch.fnmatchcase(c, EXCLUDED))


def nix(cmd, log):
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    env = dict(os.environ, PDK_ROOT=PDK_ROOT)
    env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    with open(log, "a") as f:
        f.write(f"$ (cd {ll_dir} && nix-shell --run {cmd!r})\n")
        f.flush()
        subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, env=env, stdout=f, stderr=subprocess.STDOUT)
    return open(log, encoding="utf-8", errors="replace").read()


def run(gds, top, out):
    """The result dict of one macro; writes <out>.lyrdb and <out>.klayout.log next to out."""
    base = os.path.splitext(os.path.abspath(out))[0]
    lyrdb, log, py = base + ".lyrdb", base + ".klayout.log", base + ".cells.py"
    for p in (lyrdb, log):
        if os.path.exists(p):
            os.remove(p)
    open(py, "w").write(CELLS)
    gds = os.path.abspath(gds)
    m = re.search(r"^CELLS (.*)$", nix(f"klayout -b -rd src='{gds}' -r '{py}'", log), re.M)
    names = m.group(1).split() if m else []
    problems = [] if m else ["KLayout could not read the GDS"]
    if names and top not in names:
        problems.append(f"no cell {top} in the GDS")
    hidden = excluded(names)
    if hidden:
        problems.append(f"{len(hidden)} cell name(s) match the deck's exclusion {EXCLUDED} (checked vacuously): {hidden[:3]}")
    opts = " ".join(f"-rd {k}={v}" for k, v in OPTIONS.items())
    nix(f"klayout -b -zz -r '{os.path.join(PDK_ROOT, DECK)}' -rd input='{gds}' -rd topcell={top} -rd report='{lyrdb}' {opts}", log)
    found, rules, cells = parse(lyrdb, top)
    return {"gds": os.path.relpath(gds, ROOT) if gds.startswith(ROOT) else os.path.basename(gds), "top": top,
            "deck": DECK, "options": OPTIONS, "total": sum(rules.values()), "rules": rules, "cells": cells,
            "problems": problems + found}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gds")
    ap.add_argument("top")
    ap.add_argument("out")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    t0 = time.time()
    res = run(a.gds, a.top, a.out)
    sources = open(os.path.join(PDK_ROOT, "sky130A", "SOURCES")).read().split()
    res.update(pdk=" ".join(sources[:2]), minutes=round((time.time() - t0) / 60, 1),
               result="FAIL" if res["problems"] else "PASS")
    json.dump(res, open(a.out, "w"), indent=1, ensure_ascii=False)
    print(f"macro_klayout_drc: {res['result']} - {a.top}: {res['total']} errors"
          + (f"; {'; '.join(res['problems'])}" if res["problems"] else f" ({len(REQUIRED)} required rules ran)"))
    return 1 if res["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
