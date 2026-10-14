#!/usr/bin/env python3
"""make neg-precheck: bug injection into the input of check_precheck.py (ADR-0019 decision 5); every injected case must
FAIL at its own line, the positive controls (positive, clean, ref_extra_rule, verification_flag) must PASS.

usage: neg_precheck.py

Fixture (runs/neg_precheck/, rebuilt every time, about 2 minutes):
  base/  a precheck project made without the image: gds/user_project_wrapper.gds = the self-generated SRAM mirrored
         (DEF FS) in an otherwise empty top cell (make_fixture.py); precheck_results/<time>/ with the pinned deck's
         FEOL/BEOL reports of it (run_deck.py, the OpenRAM bitcell markers only); .cf/project.json with every other
         check pass, magic_drc skip, input_file_hash and logs/gds.info = sha1 of the GDS; arvinsa_source.json as
         make_project.py writes it for a run that passed the run guard; two_macros.gds has a second copy of the SRAM.
  ref/   the same deck on the PDK SRAM alone (as make precheck-sram-ref).
Cases (expected text in a FAIL line of check_precheck.py):
  positive         base as it is: PASS
  clean            FEOL/BEOL without any item, status pass: PASS
  other_check      lvs fail                                   "not pass {'lvs': 'fail'}"
  missing_check    oeb not in project.json                    "missing ['oeb']"
  magic_drc_fail   magic_drc fail                             "magic_drc: fail"
  other_gds        input_file_hash of another file            "sha1"
  other_version    cf-precheck 1.3.8                          "pinned 1.3.7"
  stale_results    logs/gds.info of another GDS (an earlier run's reports)  "checked this GDS"
  results_after    project.json older than the results directory  "after the results directory's start"
  results_after_tz the same in +08:00 (07:00 = 23:00 UTC the day before; review H6)  "after the results directory's start"
  no_tz            project.json time stamp without a time zone    "has no time zone"
  no_source        arvinsa_source.json removed (review H7)        "source: cannot read"
  verification_source  arvinsa_source.json of make_project.py --verification  "not a signoff result"
  source_gds       arvinsa_source.json records another GDS sha1   "the one recorded from"
  verification_flag  the verification source with --verification: PASS (verification only)
  status_skip      klayout_beol status skip with its items    "status skip with"
  other_top        BEOL report of another top cell            "report top cell"
  unplaced         MR_mcon.CON.10 in a cell the GDS does not have  "not placed"
  no_value         MR_mcon.CON.10 item without a value        "not placed"
  two_macros       the GDS has the SRAM twice                 "2 instance(s) of"
  total_mismatch   logs/klayout_beol_check.total off by one    "check.total says"
  status_pass      klayout_beol status pass with its items     "status pass with"
  other_rule       BEOL item of another rule in the bitcell   "rule(s) other than"
  outside          MR_mcon.CON.10 in the top cell, off the SRAM  "outside arv_sram"
  moved            one bitcell marker moved 0.1 um            "that the PDK macro alone does not have"
  other_deck       a rule description changed in the reference  "different decks"
  ref_extra_rule   the reference has an item of another rule (the PDK macro of 3e0e31dc has FEOL nsdm/psdm ones):
                   PASS, printed as not compared
  ref_other_rule   both the reference and the design have a bitcell item of another rule  "rule(s) other than"
  ref_sha          the reference's input.sha1 of another GDS   "the reference was not made from"
  other_ref_gds    the reference GDS (and its input.sha1) is not the PDK macro  "bitcell arrays differ"
  no_macro         --macro names a cell not in the design      "instance(s) of"
Prints `neg-precheck: PASS n/n` / `FAIL ...`; exit code 0 only on PASS.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "runs", "neg_precheck")
sys.path.insert(0, HERE)
import check_precheck as cp  # noqa: E402
import run_deck  # noqa: E402

PY = sys.executable
MACRO = "arv_sram_2kbyte_1rw1r_32x512_8"
MACRO_GDS = os.path.join(ROOT, "ip", "sram", MACRO, "openram", f"{MACRO}.gds")
START = "14_OCT_2026___00_00_00"
CHECKS = ("klayout_feol", "klayout_beol")


def klayout(script, **rd):
    env = dict(os.environ)
    env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    args = " ".join(f"-rd {k}='{v}'" for k, v in rd.items())
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    r = subprocess.run(["nix-shell", "--run", f"klayout -b {args} -r '{os.path.join(HERE, script)}'"], cwd=ll_dir,
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit(f"neg-precheck: FAIL {script}: {r.stdout[-1000:]}{r.stderr[-1000:]}")


def build():
    base, ref = os.path.join(OUT, "base"), os.path.join(OUT, "ref")
    res = os.path.join(base, "precheck_results", START)
    gds = os.path.join(base, "gds", "user_project_wrapper.gds")
    os.makedirs(os.path.dirname(gds))
    klayout("make_fixture.py", src=MACRO_GDS, macro=MACRO, top="user_project_wrapper", x=350.98, y=850, copies=1, dst=gds)
    klayout("make_fixture.py", src=MACRO_GDS, macro=MACRO, top="user_project_wrapper", x=350.98, y=850, copies=2,
            dst=os.path.join(OUT, "two_macros.gds"))
    reports, logs = os.path.join(res, "outputs", "reports"), os.path.join(res, "logs")
    os.makedirs(logs)
    counts = {}
    for c in CHECKS:
        n = run_deck.run(gds, reports, c)
        if not n:
            sys.exit(f"neg-precheck: FAIL the fixture's {c} report has {n} item(s); expected the bitcell markers")
        counts[c] = n
        for ext in ("total", "log"):
            os.replace(os.path.join(reports, f"{c}_check.{ext}"), os.path.join(logs, f"{c}_check.{ext}"))
        os.remove(os.path.join(reports, "input.sha1"))
        if not run_deck.run(cp.ref_gds(), ref, c):
            sys.exit(f"neg-precheck: FAIL the reference's {c} report has no item")
    checks = {c: {"status": "pass", "duration_s": 1.0} for c in cp.CHECKS}
    for c in CHECKS:
        checks[c]["status"] = "fail"
    checks["magic_drc"] = {"status": "skip", "duration_s": 0.0}
    open(os.path.join(logs, "gds.info"), "w").write(f"user_project_wrapper.gds: {cp.sha1(gds)}\n")
    os.makedirs(os.path.join(base, ".cf"))
    json.dump({"precheck": {"version": "1.3.7", "timestamp": "2026-10-14T00:20:00+00:00", "pdk": "sky130A",
                            "passed": False, "input_file_hash": cp.sha1(gds), "checks": checks}},
              open(os.path.join(base, ".cf", "project.json"), "w"), indent=2)
    json.dump({"run": "runs/user_project_wrapper", "run_commit": "f" * 40, "head": "f" * 40, "run_guard": "PASS",
               "verification": False, "files": {"gds/user_project_wrapper.gds": {"sha1": cp.sha1(gds)}}},
              open(os.path.join(base, "arvinsa_source.json"), "w"), indent=1)
    print(f"[neg-precheck] fixture: FEOL {counts['klayout_feol']}, BEOL {counts['klayout_beol']} item(s); reference in "
          f"{os.path.relpath(ref, ROOT)}", flush=True)
    return base, ref


# ---- mutations: each gets (project dir, ref dir) of the case's own copy ----
def pj_edit(f):
    def m(p, _r):
        path = os.path.join(p, ".cf", "project.json")
        d = json.load(open(path))
        f(d["precheck"])
        json.dump(d, open(path, "w"), indent=2)
    return m


def xml_edit(where, check, f):
    def m(p, r):
        path = (os.path.join(p, "precheck_results", START, "outputs", "reports", f"{check}_check.xml") if where == "design"
                else os.path.join(r, f"{check}_check.xml"))
        tree = ET.parse(path)
        f(tree.getroot())
        tree.write(path, encoding="utf-8", xml_declaration=True)
        n = len(tree.getroot().find("items"))
        if where == "design":
            open(os.path.join(p, "precheck_results", START, "logs", f"{check}_check.total"), "w").write(str(n))
    return m


def add_item(root, cat, cell, value):
    if not any(c.findtext("name") == cell for c in root.find("cells")):
        c = ET.SubElement(root.find("cells"), "cell")
        ET.SubElement(c, "name").text = cell
        ET.SubElement(c, "variant")
        ET.SubElement(c, "layout-name")
        ET.SubElement(c, "references")
    it = ET.SubElement(root.find("items"), "item")
    ET.SubElement(it, "tags")
    ET.SubElement(it, "category").text = f"'{cat}'"
    ET.SubElement(it, "cell").text = cell
    ET.SubElement(it, "visited").text = "false"
    ET.SubElement(it, "multiplicity").text = "1"
    vals = ET.SubElement(it, "values")
    if value is not None:
        ET.SubElement(vals, "value").text = value


def first_bitcell_item(root):
    return next(i for i in root.find("items") if i.findtext("cell") == cp.ANCHOR)


def other_rule(root):
    i = first_bitcell_item(root)
    rule = next(c.findtext("name").strip("'") for c in root.find("categories").iter("category")
                if c.findtext("name").strip("'") not in cp.ALLOWED["klayout_beol"])
    add_item(root, rule, cp.ANCHOR, i.find("values")[0].text)


def outside(root):
    add_item(root, "MR_mcon.CON.10", "user_project_wrapper", "polygon: (10,10;10,10.2;10.2,10.2;10.2,10)")


def moved(root):
    v = first_bitcell_item(root).find("values")[0]
    kind, coords = v.text.split(":", 1)
    v.text = kind + ":" + re.sub(r"-?\d+(\.\d+)?", lambda m: f"{float(m.group(0)) + 0.1:.3f}", coords)


def unplaced(root):
    add_item(root, "MR_mcon.CON.10", "NOT_IN_GDS", "polygon: (0,0;0,0.2;0.2,0.2;0.2,0)")


def no_value(root):
    add_item(root, "MR_mcon.CON.10", cp.ANCHOR, None)


def ref_other_rule(p, r):
    xml_edit("ref", "klayout_beol", other_rule)(p, r)
    xml_edit("design", "klayout_beol", other_rule)(p, r)


def other_top(root):
    root.find("top-cell").text = "user_proj_example"


def gds_info_edit(text):
    def m(p, _r):
        open(os.path.join(p, "precheck_results", START, "logs", "gds.info"), "w").write(text)
    return m


def ref_sha(_p, r):
    open(os.path.join(r, "input.sha1"), "w").write(f"{cp.REF_MACRO}.gds: {'0' * 40}\n")


def two_macros(p, r):
    g = os.path.join(p, "gds", "user_project_wrapper.gds")
    os.remove(g)
    os.symlink(os.path.join(OUT, "two_macros.gds"), g)
    h = cp.sha1(g)
    pj_edit(lambda pre: pre.update(input_file_hash=h))(p, r)
    gds_info_edit(f"user_project_wrapper.gds: {h}\n")(p, r)


def ref_from_macro(_p, r):
    open(os.path.join(r, "input.sha1"), "w").write(f"{MACRO}.gds: {cp.sha1(MACRO_GDS)}\n")


def other_deck(root):
    c = next(c for c in root.find("categories").iter("category") if c.findtext("description"))
    c.find("description").text += " (edited)"


def clean(p, r):
    for c in CHECKS:
        xml_edit("design", c, lambda root: [root.find("items").remove(i) for i in list(root.find("items"))])(p, r)
    pj_edit(lambda pre: [pre["checks"][c].update(status="pass") for c in CHECKS])(p, r)


def source_edit(f):
    def m(p, _r):
        path = os.path.join(p, "arvinsa_source.json")
        d = json.load(open(path))
        f(d)
        json.dump(d, open(path, "w"), indent=1)
    return m


def as_verification(d):
    d.update(run_guard=["the harden run was made from commit 0000000, but HEAD is ffffff"], verification=True)


def total_off(p, _r):
    path = os.path.join(p, "precheck_results", START, "logs", "klayout_beol_check.total")
    n = int(open(path).read())
    open(path, "w").write(str(n + 1))


CASES = [  # (name, mutation, extra args, expected text in a FAIL line or None for PASS)
    ("positive", None, [], None),
    ("clean", clean, [], None),
    ("other_check", pj_edit(lambda pre: pre["checks"]["lvs"].update(status="fail")), [], "not pass {'lvs': 'fail'}"),
    ("missing_check", pj_edit(lambda pre: pre["checks"].pop("oeb")), [], "missing ['oeb']"),
    ("magic_drc_fail", pj_edit(lambda pre: pre["checks"]["magic_drc"].update(status="fail")), [], "magic_drc: fail"),
    ("other_gds", pj_edit(lambda pre: pre.update(input_file_hash="0" * 40)), [], "sha1"),
    ("other_version", pj_edit(lambda pre: pre.update(version="1.3.8")), [], "pinned 1.3.7"),
    ("stale_results", gds_info_edit(f"user_project_wrapper.gds: {'0' * 40}\n"), [], "checked this GDS"),
    ("results_after", pj_edit(lambda pre: pre.update(timestamp="2026-10-13T23:59:00+00:00")), [],
     "after the results directory's start"),
    ("results_after_tz", pj_edit(lambda pre: pre.update(timestamp="2026-10-14T07:00:00+08:00")), [],
     "after the results directory's start"),
    ("no_tz", pj_edit(lambda pre: pre.update(timestamp="2026-10-14T00:20:00")), [], "has no time zone"),
    ("no_source", lambda p, _r: os.remove(os.path.join(p, "arvinsa_source.json")), [], "source: cannot read"),
    ("verification_source", source_edit(as_verification), [], "not a signoff result"),
    ("source_gds", source_edit(lambda d: d["files"]["gds/user_project_wrapper.gds"].update(sha1="0" * 40)), [],
     "the one recorded from"),
    ("verification_flag", source_edit(as_verification), ["--verification"], None),
    ("status_skip", pj_edit(lambda pre: pre["checks"]["klayout_beol"].update(status="skip")), [], "status skip with"),
    ("other_top", xml_edit("design", "klayout_beol", other_top), [], "report top cell"),
    ("unplaced", xml_edit("design", "klayout_beol", unplaced), [], "not placed"),
    ("no_value", xml_edit("design", "klayout_beol", no_value), [], "not placed"),
    ("two_macros", two_macros, [], "2 instance(s) of"),
    ("total_mismatch", total_off, [], "check.total says"),
    ("status_pass", pj_edit(lambda pre: pre["checks"]["klayout_beol"].update(status="pass")), [], "status pass with"),
    ("other_rule", xml_edit("design", "klayout_beol", other_rule), [], "rule(s) other than"),
    ("outside", xml_edit("design", "klayout_beol", outside), [], f"outside {MACRO}"),
    ("moved", xml_edit("design", "klayout_beol", moved), [], "that the PDK macro alone does not have"),
    ("other_deck", xml_edit("ref", "klayout_beol", other_deck), [], "different decks"),
    ("ref_extra_rule", xml_edit("ref", "klayout_beol", other_rule), [], None),
    ("ref_other_rule", ref_other_rule, [], "rule(s) other than"),
    ("ref_sha", ref_sha, [], "the reference was not made from"),
    ("other_ref_gds", ref_from_macro, ["--ref-gds", MACRO_GDS], "bitcell arrays differ"),
    ("no_macro", None, ["--macro", cp.REF_MACRO], "instance(s) of"),
]


def main():
    if not os.path.exists(run_deck.deck()):
        print(f"neg-precheck: FAIL {run_deck.deck()} not found (make precheck-deck)")
        return 1
    shutil.rmtree(OUT, ignore_errors=True)  # only runs/neg_precheck is removed
    base, ref = build()
    results = []
    for name, mutate, extra, want in CASES:
        d = os.path.join(OUT, name)
        p, r = os.path.join(d, "project"), os.path.join(d, "ref")
        shutil.copytree(base, p, ignore=shutil.ignore_patterns("*.gds"))
        os.symlink(os.path.join(base, "gds", "user_project_wrapper.gds"), os.path.join(p, "gds", "user_project_wrapper.gds"))
        shutil.copytree(ref, r)
        if mutate:
            mutate(p, r)
        cmd = [PY, os.path.join(HERE, "check_precheck.py"), "--project", p, "--ref-dir", r, "--ref-gds", cp.ref_gds(),
               "--out", os.path.join(d, "out")] + extra
        c = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        open(os.path.join(d, "run.log"), "w").write(c.stdout + c.stderr)
        fails = [x for x in c.stdout.splitlines() if "[FAIL]" in x]
        if want is None:
            ok = c.returncode == 0 and "precheck: PASS" in c.stdout and not fails
            what = "PASS"
        else:
            ok = c.returncode != 0 and "precheck: FAIL" in c.stdout and any(want in x for x in fails)
            what = f"FAIL at {want!r}"
        results.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {what}"
              + ("" if ok else f" (exit {c.returncode}; see {os.path.relpath(d, ROOT)}/run.log)"), flush=True)
    ok = all(results)
    print(f"neg-precheck: {'PASS' if ok else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
