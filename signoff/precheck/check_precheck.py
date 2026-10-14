#!/usr/bin/env python3
"""Judge a ChipFoundry precheck result the way ADR-0019 decision 5 says (Phase 7; skill tapeout-precheck-caravel rule 3).

usage: check_precheck.py --project <dir> --ref-dir <dir> [--results <precheck_results/...>] [--out <dir>]
                         [--top user_project_wrapper] [--macro <SRAM cell>] [--ref-gds <PDK SRAM gds>]

Why: the precheck's KLayout deck (cf-precheck commit 08f559e30a, 2026-05-07) reports MR_mcon.CON.10 and MR_licon.SP.6
inside every OpenRAM bitcell, the PDK's own sky130_sram_* macros too, and nothing turns that off. The official result of
klayout_feol / klayout_beol is FAIL for any design with such an SRAM. The user's decision (2026-10-12): every other
check PASS, and these two only with these two rules, every marker inside the SRAM, each also present at the same place
when the PDK macro is checked alone.

Input: <project> is the directory the precheck ran on: .cf/project.json (status of each check, cf-precheck version,
input_file_hash = sha1 of gds/<top>.gds), gds/<top>.gds and precheck_results/<start time>/ (default: the newest).
<ref-dir> has klayout_feol_check.xml and klayout_beol_check.xml of the same deck on the PDK macro alone (topcell =
the macro; make precheck-sram-ref locally, or the same command in the precheck image).
Checks:
  - project.json: cf-precheck is CF_PRECHECK_VERSION of env/versions.mk; its 13 checks are all there and nothing else
    (magic_drc may be skip or pass); every check but klayout_feol / klayout_beol is pass; input_file_hash = sha1 of
    gds/<top>.gds; the results directory's logs/gds.info names that same sha1 (a report of an earlier run is not read)
    and project.json was written after that directory's start;
  - per DRC check: the report's top cell is <top>, its item count = logs/<check>_check.total, status fail with items and
    pass without; the deck's rule list (names and descriptions) equals the reference report's (same deck); the
    reference's input.sha1 is that of --ref-gds;
  - per DRC check with items: only its allowed rule (FEOL MR_licon.SP.6, BEOL MR_mcon.CON.10; markers of other rules
    in the reference are left out of the comparison and printed, ADR-0019 decision 24); rdb_flatten.py places
    every marker over every instance of its cell (KLayout reads as many items as the XML has): none outside the one
    <macro> instance, none unplaced (an item without a value counts); the bitcell
    arrays (sky130_fd_bd_sram__openram_dp_cell instances) of <macro> and the PDK macro have the same count and size;
    every marker, relative to the array, is also in the reference (with at least the same count).
Deep mode reports a marker in whichever cell holds it, and that differs between the two macros (2 of 264 BEOL items),
so "the same cell" of the decision is checked as the same place after flattening (see rdb_flatten.py).
Prints `precheck: PASS ...` / `precheck: FAIL ...`; exit 0 only on PASS. Negative test: neg_precheck.py.
"""
import argparse
import collections
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# cf-precheck 1.3.7 check_manager.py build_sequence() for a digital sky130A project; magic_drc is optional (off)
CHECKS = ["topcell_check", "gpio_defines", "xor", "klayout_feol", "klayout_beol", "klayout_offgrid",
          "klayout_met_min_ca_density", "klayout_pin_label_purposes_overlapping_drawing", "klayout_zeroarea",
          "spike_check", "illegal_cellname_check", "lvs", "oeb"]
OPTIONAL = {"magic_drc": {"skip", "pass"}}
ALLOWED = {"klayout_feol": {"MR_licon.SP.6"}, "klayout_beol": {"MR_mcon.CON.10"}}
ANCHOR = "sky130_fd_bd_sram__openram_dp_cell"
REF_MACRO = "sky130_sram_2kbyte_1rw1r_32x512_8"


def pin(name):
    m = re.search(rf"^{name}\s*=\s*(\S+)", open(os.path.join(ROOT, "env", "versions.mk")).read(), re.M)
    return m.group(1) if m else None


def ref_gds():
    """The PDK SRAM's GDS (PDK_ROOT, default ~/.ciel, as the flow)."""
    return os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), "sky130A", "libs.ref",
                        "sky130_sram_macros", "gds", f"{REF_MACRO}.gds")


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def report(path):
    """(top cell, deck fingerprint, [(category, cell)] of the items) of a KLayout report database."""
    r = ET.parse(path).getroot()
    rules = sorted((c.findtext("name"), c.findtext("description") or "") for c in r.find("categories").iter("category"))
    fp = hashlib.sha256(json.dumps(rules).encode()).hexdigest()
    items = [(i.findtext("category").strip("'"), i.findtext("cell")) for i in r.find("items")]
    return r.findtext("top-cell"), fp, items


def flatten(gds, top, macro, rdb, dst):
    """rdb_flatten.py's output (dict), or None if KLayout failed."""
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    cmd = (f"klayout -b -rd gds='{os.path.abspath(gds)}' -rd top={top} -rd macro={macro} -rd anchor={ANCHOR} "
           f"-rd rdb='{os.path.abspath(rdb)}' -rd dst='{os.path.abspath(dst)}' -r '{os.path.join(HERE, 'rdb_flatten.py')}'")
    env = dict(os.environ)
    env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    if os.path.exists(dst):
        os.remove(dst)
    r = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, capture_output=True, text=True, env=env)
    if r.returncode != 0 or not os.path.exists(dst):
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
        return None
    return json.load(open(dst))


def results_dir(project):
    """Newest precheck_results/<DD_MON_YYYY___HH_MM_SS> (UTC start time) and its start time, or (None, None)."""
    best = (None, None)
    for d in glob.glob(os.path.join(project, "precheck_results", "*")):
        try:
            t = datetime.datetime.strptime(os.path.basename(d), "%d_%b_%Y___%H_%M_%S")
        except ValueError:
            continue
        if best[1] is None or t > best[1]:
            best = (d, t)
    return best


def judge_drc(check, args, res, status, out):
    """Problems (list of str) and a summary of one KLayout DRC check against the reference."""
    xml = os.path.join(res, "outputs", "reports", f"{check}_check.xml")
    ref = os.path.join(args.ref_dir, f"{check}_check.xml")
    for p in (xml, ref):
        if not os.path.exists(p):
            return [f"{os.path.relpath(p, ROOT)} not found"], ""
    try:
        top, fp, items = report(xml)
        rtop, rfp, ritems = report(ref)
    except (ET.ParseError, AttributeError) as e:
        return [f"cannot read the report or the reference: {e}"], ""
    errs = []
    if top != args.top:
        errs.append(f"report top cell {top!r}, not {args.top!r}")
    if rtop != REF_MACRO:
        errs.append(f"reference top cell {rtop!r}, not {REF_MACRO!r}")
    if fp != rfp:
        errs.append("the report and the reference come from different decks (rule lists differ)")
    total = os.path.join(res, "logs", f"{check}_check.total")
    t = open(total).read().strip() if os.path.exists(total) else None
    if t != str(len(items)):
        errs.append(f"{len(items)} item(s) in the report, logs/{check}_check.total says {t}")
    if status != ("fail" if items else "pass"):
        errs.append(f"status {status} with {len(items)} item(s)")
    info = os.path.join(args.ref_dir, "input.sha1")
    got = open(info).read().strip() if os.path.exists(info) else None
    if got != f"{os.path.basename(args.ref_gds)}: {sha1(args.ref_gds)}":
        errs.append(f"the reference was not made from {args.ref_gds} (input.sha1: {got})")
    if errs or not items:
        return errs, f"{len(items)} item(s)"
    other = collections.Counter(c for c, _ in items if c not in ALLOWED[check])
    if other:
        errs.append(f"rule(s) other than {sorted(ALLOWED[check])}: {dict(other)}")
    # The PDK macro of the precheck's PDK (3e0e31dc) also has FEOL MR_nsdm.WID.2 / MR_psdm.* in its control logic
    # (ADR-0019 decision 24): those do not excuse anything in the design, which may have the allowed rule only.
    r_other = collections.Counter(c for c, _ in ritems if c not in ALLOWED[check])
    os.makedirs(out, exist_ok=True)
    d = flatten(os.path.join(args.project, "gds", f"{args.top}.gds"), args.top, args.macro, xml,
                os.path.join(out, f"{check}_design.json"))
    r = flatten(args.ref_gds, REF_MACRO, REF_MACRO, ref, os.path.join(out, f"{check}_reference.json"))
    if d is None or r is None:
        return errs + ["rdb_flatten.py failed (KLayout output above)"], ""
    for name, f, n in (("report", d, len(items)), ("reference", r, len(ritems))):
        if f["items"] != n:
            errs.append(f"KLayout read {f['items']} item(s) of the {name}, the XML has {n}")
    if r["unplaced"] or r["outside"]:
        errs.append(f"reference: {len(r['unplaced'])} marker(s) not placed, {len(r['outside'])} outside {REF_MACRO}")
    if d["macro_instances"] != 1:
        errs.append(f"{d['macro_instances']} instance(s) of {args.macro} in {args.top}, expected 1")
    if d["anchor"] is None or r["anchor"] is None or d["anchor"] != r["anchor"]:
        errs.append(f"bitcell arrays differ: {args.macro} {d['anchor']}, {REF_MACRO} {r['anchor']}")
    if d["unplaced"]:
        errs.append(f"{len(d['unplaced'])} marker(s) not placed (cell not below {args.top}), e.g. {d['unplaced'][0]}")
    if d["outside"]:
        o = d["outside"][0]
        errs.append(f"{len(d['outside'])} marker(s) outside {args.macro}, e.g. {o[0]} in {o[1]} at "
                    f"({o[2] / 1000:.3f}, {o[3] / 1000:.3f}) um")
    have = collections.Counter({tuple(m[:5]): m[5] for m in d["inside"]})
    want = collections.Counter({tuple(m[:5]): m[5] for m in r["inside"] if m[0] in ALLOWED[check]})
    extra = have - want
    if extra:
        k = sorted(extra)[0]
        errs.append(f"{sum(extra.values())} marker(s) inside {args.macro} that the PDK macro alone does not have, e.g. "
                    f"{k[0]} at ({k[1] / 1000:.3f}, {k[2] / 1000:.3f}) um from the bitcell array's corner")
    n, nr = sum(have.values()), sum(want.values())
    return errs, (f"{len(items)} item(s) = {n} marker(s), all {'/'.join(sorted(ALLOWED[check]))} inside {args.macro} "
                  f"at places the PDK macro alone also has ({nr} there"
                  + (")" if n == nr else f"; {nr - n} of them not in the design)")
                  + (f"; the reference's other rule(s), not compared: {dict(r_other)}" if r_other else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--ref-dir", required=True)
    ap.add_argument("--results", help="precheck_results/<start time> (default: the newest)")
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "precheck_check"))
    ap.add_argument("--top", default="user_project_wrapper")
    ap.add_argument("--macro", default="arv_sram_2kbyte_1rw1r_32x512_8")
    ap.add_argument("--ref-gds", default=ref_gds())
    args = ap.parse_args()
    lines, ok = [], True

    def line(good, text):
        nonlocal ok
        ok &= good
        lines.append(f"  [{'PASS' if good else 'FAIL'}] {text}")
        print(lines[-1], flush=True)

    pj = os.path.join(args.project, ".cf", "project.json")
    try:
        pre = json.load(open(pj))["precheck"]
        checks = pre["checks"]
    except (OSError, ValueError, KeyError) as e:
        print(f"precheck: FAIL cannot read {pj}: {e}")
        return 1
    res, start = (args.results, None) if args.results else results_dir(args.project)
    if res is None or not os.path.isdir(res):
        print(f"precheck: FAIL no precheck_results directory in {args.project}")
        return 1
    if start is None:
        try:
            start = datetime.datetime.strptime(os.path.basename(os.path.normpath(res)), "%d_%b_%Y___%H_%M_%S")
        except ValueError:
            pass
    print(f"[precheck] cf-precheck {pre.get('version')}, {pre.get('timestamp')}, results {os.path.relpath(res, ROOT)}")
    src = os.path.join(args.project, "arvinsa_source.json")
    if os.path.exists(src):
        s = json.load(open(src))
        print(f"  [INFO] project from {s.get('run')} (commit {s.get('run_commit')}, HEAD then {s.get('head')}): "
              + ("verification, run guard skipped" if s.get("verification") else "run guard PASS"))
    want = pin("CF_PRECHECK_VERSION")
    line(pre.get("version") == want, f"cf-precheck {pre.get('version')} (pinned {want}; another version: read its deck "
         "and checks, then update env/versions.mk)")
    missing = [c for c in CHECKS if c not in checks]
    extra = [c for c in checks if c not in CHECKS and c not in OPTIONAL]
    line(not missing and not extra, f"checks: {len(CHECKS)} expected" + (f", missing {missing}" if missing else "")
         + (f", not expected {extra}" if extra else ""))
    for c, allowed in OPTIONAL.items():
        if c in checks:
            line(checks[c]["status"] in allowed, f"{c}: {checks[c]['status']} (allowed {sorted(allowed)})")
    bad = {c: checks[c]["status"] for c in CHECKS if c in checks and c not in ALLOWED and checks[c]["status"] != "pass"}
    line(not bad, f"{len(CHECKS) - len(ALLOWED)} checks other than klayout_feol/klayout_beol: "
         + ("all pass" if not bad else f"not pass {bad}"))
    gds = os.path.join(args.project, "gds", f"{args.top}.gds")
    h = sha1(gds) if os.path.exists(gds) else None
    line(h is not None and h == pre.get("input_file_hash"),
         f"gds/{args.top}.gds sha1 {h} = the checked file's {pre.get('input_file_hash')}")
    info = os.path.join(res, "logs", "gds.info")
    got = open(info).read().strip() if os.path.exists(info) else None
    line(got == f"{args.top}.gds: {h}", f"the results directory checked this GDS (logs/gds.info: {got})")
    t = datetime.datetime.fromisoformat(pre["timestamp"]).replace(tzinfo=None) if pre.get("timestamp") else None
    line(t is not None and start is not None and t >= start,
         f"project.json written {t}, after the results directory's start {start}")
    for c in ALLOWED:
        if c not in checks:
            continue
        errs, summary = judge_drc(c, args, res, checks[c]["status"], args.out)
        line(not errs, f"{c}: {checks[c]['status']}, " + ("; ".join(errs) if errs else summary))
    n_fail = sum(1 for x in lines if "[FAIL]" in x)
    print(f"precheck: {'PASS' if ok else 'FAIL'} " + ("(ADR-0019 decision 5)" if ok else f"{n_fail} line(s) FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
