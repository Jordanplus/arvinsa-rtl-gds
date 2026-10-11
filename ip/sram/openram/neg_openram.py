#!/usr/bin/env python3
"""Bug injection for the OpenRAM checkers (Phase 6, ADR-0018): make neg-openram.

Each case builds a small fake run (or fake install) in a temp dir from a clean template, injects one error,
and must FAIL with the expected reason; the clean templates must PASS (positive controls).
  O1-O8  gen_macro.judge: OpenRAM log, its DRC/LVS reports, the output files
         (O1 is the defect seen on 2026-10-08: "ERROR ... LVS mismatch" in the log while OpenRAM exits 0)
  I1-I4  check_install.problems: `make sky130-install` leaving cells out while exiting 0
  T1-T3  check_install.tree_problems: OpenRAM's tracked files must be the pinned commit plus the repo patches
         (a patch not applied, another edit, another HEAD)
  D1-D8  macro_drc.parse/compare (merged regions per rule, area within AREA_TOL): a rule category the prebuilt macro does not have (the 2026-10-08 case:
         nwell.5a and routing spacing), a higher total, Magic not finishing
  K0-K8  macro_klayout_drc: an error in the report, no report, front-end rules not run, a cell name the KLayout
         deck excludes; two real runs on a tiny GDS (psdm 0.26 um apart: the 2026-10-10 case; the same under an
         excluded name); K7 the same under a sky130_fd_io name the deck leaves out of nwell.6 (Phase 6 independent
         review H5: only the SRAM pattern was known); K8 the deck's selections parsed from a deck text
  L1-L2  the .lib template: gen_char_lib.power_problems refuses OpenRAM dev's internal_power 1.036316e+11
         (2026-10-08); lib_template.make refuses .lib files whose power entries differ
  C1-C5  check_char_lib.provenance for a self-generated macro: char.json made from another netlist than
         ip/sram/<macro>/openram/<macro>.sp, and that netlist not the one its summary.json records; an earlier
         run's netlist of the same circuit in another order passes (C3), one with a transistor changed or a
         subcircuit missing does not (C4, C5; ADR-0018 decision 17)
  C6-C7  check_char_lib.power_problems on a copy of the self-generated macro's char/: a clk0 internal_power table
         with a second number 1e11 (C6), or with an index_1 (C7), FAILs; the copy as is passes (C6a). Until the
         Phase 6 independent review (H7) only the first number was read
Prints PASS n/n; exit 0 only when every case behaves as expected.
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_install  # noqa: E402
import gen_macro  # noqa: E402
import macro_drc  # noqa: E402
import macro_klayout_drc  # noqa: E402
import lib_template  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "char"))
import gen_char_lib  # noqa: E402
import check_char_lib  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402

NAME = "neg_sram"
LVS_OK = "Circuits match uniquely."


def make_run(d, log="** End: 30 seconds\n", drc="Total DRC errors found: 0\n", lvs=f"Final result: {LVS_OK}\n",
             files=(".gds", ".lef", ".sp", ".lvs.sp", ".v"), empty=()):
    os.makedirs(os.path.join(d, "tmp"))
    os.makedirs(os.path.join(d, "macro"))
    open(os.path.join(d, "openram.log"), "w").write(log)
    if drc is not None:
        open(os.path.join(d, "tmp", f"{NAME}.drc.out"), "w").write("Loading DRC CIF style.\n" + drc)
    if lvs is not None:
        open(os.path.join(d, "tmp", f"{NAME}.lvs.report"), "w").write("Subcircuit summary:\n" + lvs)
    for ext in files:
        open(os.path.join(d, "macro", NAME + ext), "w").write("" if ext in empty else "x\n")
    return d


def make_install(d, drop_gds=False, drop_sp=False, no_cells=False):
    bd, tech = os.path.join(d, "bd"), os.path.join(d, "openram", "technology", "sky130")
    for sub in ("gds_lib", "sp_lib"):
        os.makedirs(os.path.join(tech, sub))
    os.makedirs(os.path.join(bd, "cells", "c1"))
    if not no_cells:
        for f in ("cell_a.gds", "cell_a.spice", "cell_a.lvs.spice", "cell_b.gds", "cell_b.base.spice"):
            open(os.path.join(bd, "cells", "c1", f), "w").write("x\n")
    if not drop_gds:
        open(os.path.join(tech, "gds_lib", "cell_a.gds"), "w").write("x\n")
    open(os.path.join(tech, "gds_lib", "cell_b.gds"), "w").write("x\n")
    open(os.path.join(tech, "sp_lib", "cell_a.sp"), "w").write("x\n")
    if not drop_sp:
        open(os.path.join(tech, "sp_lib", "cell_b.sp"), "w").write("x\n")
    return os.path.join(d, "openram"), bd


def main():
    results = []

    def check(name, problems, want):
        ok = (not problems) if want is None else any(want in p for p in problems)
        results.append(ok)
        got = "; ".join(problems) or "PASS"
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {got[:110]}" + ("" if ok else f" (expected {want or 'PASS'})"))

    with tempfile.TemporaryDirectory(prefix="neg_openram_") as t:
        def run(case, rc=0, drc_max=0, **kw):
            return gen_macro.judge(make_run(os.path.join(t, case), **kw), NAME, rc, drc_max)[0]

        check("O0 clean run passes (positive control)", run("o0"), None)
        check("O1 ERROR line in the log while OpenRAM exits 0", run("o1", log=f"ERROR: file magic.py: line 387: {NAME}\tLVS mismatch\n** End: 30 seconds\n"), "ERROR line")
        check("O2 LVS final result is a mismatch", run("o2", lvs="Final result: Netlists do not match.\n"), "LVS: Netlists do not match.")
        check("O3 DRC count above the limit", run("o3", drc="Total DRC errors found: 3\n"), "DRC 3 > 0")
        check("O3b same DRC count within --drc-max passes (positive control)", run("o3b", drc_max=5, drc="Total DRC errors found: 3\n"), None)
        check("O4 DRC report without the total line", run("o4", drc="Finished drc check\n"), "no DRC result")
        check("O5 LVS report missing", run("o5", lvs=None), "no LVS result")
        check("O6 GDS output empty", run("o6", empty=(".gds",)), f"missing or empty {NAME}.gds")
        check("O7 OpenRAM exit code non-zero", run("o7", rc=1), "OpenRAM exit 1")
        check("O8 LVS netlist output missing", run("o8", files=(".gds", ".lef", ".sp", ".v")), f"missing or empty {NAME}.lvs.sp")

        check("I0 complete install passes (positive control)", check_install.problems(*make_install(os.path.join(t, "i0"))), None)
        check("I1 a cell GDS not copied into gds_lib", check_install.problems(*make_install(os.path.join(t, "i1"), drop_gds=True)), "1 of 2 cell GDS not in gds_lib")
        check("I2 a cell SPICE (.base.spice) not copied into sp_lib", check_install.problems(*make_install(os.path.join(t, "i2"), drop_sp=True)), "1 of 2 cell SPICE not in sp_lib")
        check("I3 cell library directory empty", check_install.problems(*make_install(os.path.join(t, "i3"), no_cells=True)), "no cell GDS")
        i4 = make_install(os.path.join(t, "i4"))
        shutil.rmtree(os.path.join(i4[0], "technology", "sky130", "gds_lib"))
        check("I4 gds_lib directory missing", check_install.problems(*i4), "2 of 2 cell GDS not in gds_lib")

    with tempfile.TemporaryDirectory(prefix="neg_openram_git_") as g:
        repo, pdir = os.path.join(g, "or"), os.path.join(g, "patches")
        os.makedirs(pdir)

        def git(*a):
            subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@invalid", *a],
                           check=True, capture_output=True)
        subprocess.run(["git", "init", "-q", repo], check=True)
        open(os.path.join(repo, "a.py"), "w").write("x = 1\n")
        open(os.path.join(repo, "b.py"), "w").write("y = 2\n")
        git("add", "-A")
        git("commit", "-q", "-m", "pin")
        pinned = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        open(os.path.join(repo, "a.py"), "w").write("x = 10\n")
        patch = os.path.join(pdir, "0001-a.patch")
        open(patch, "w").write(subprocess.run(["git", "-C", repo, "diff"], capture_output=True, text=True).stdout)
        open(os.path.join(repo, "untracked_lib.gds"), "w").write("installed\n")    # like the cell library
        check("T0 pinned commit + patch, untracked install files (positive control)",
              check_install.tree_problems(repo, pinned, [patch]), None)
        open(os.path.join(repo, "b.py"), "w").write("y = 3\n")
        check("T1 a tracked edit that is not in a patch", check_install.tree_problems(repo, pinned, [patch]), "tracked files differ")
        git("checkout", "--", "b.py")
        git("checkout", "--", "a.py")
        check("T2 the patch not applied", check_install.tree_problems(repo, pinned, [patch]), "tracked files differ")
        git("apply", patch)
        git("commit", "-q", "-am", "patch as a commit")
        check("T3 HEAD is not the pinned commit", check_install.tree_problems(repo, pinned, [patch]), "HEAD is")

    li1, dt1 = "Local interconnect width < 0.17um (li.1)", "Diffusion width < 0.15um (diff/tap.1)"
    base = {"total": 100, "rules": {li1: 60, dt1: 40},
            "merged": {li1: {"polygons": 30, "area": 900}, dt1: {"polygons": 20, "area": 400}}}
    log = ("Loading DRC CIF style.\nTotal DRC errors found: {t}\nWHY {a} Local interconnect width < 0.17um (li.1)\n"
           "WHY {b} Diffusion width < 0.15um (diff/tap.1)\n{extra}MAGIC_DRC_DONE\n")
    same = {li1: {"polygons": 30, "area": 900}, dt1: {"polygons": 20, "area": 400}}
    def md(text, merged=same):
        return macro_drc.compare(*macro_drc.parse(text), merged, base)
    check("D0 same categories and merged regions (positive control)", md(log.format(t=95, a=55, b=40, extra="")), None)
    check("D1 a rule category the baseline does not have",
          md(log.format(t=97, a=55, b=40, extra="WHY 2 Metal2 spacing < 0.14um (met2.2)\n"), {**same, "Metal2 spacing < 0.14um (met2.2)": {"polygons": 2, "area": 8}}),
          "rule categories not in the baseline: Metal2 spacing")
    check("D2 one more merged region of a rule", md(log.format(t=97, a=57, b=40, extra=""), {**same, li1: {"polygons": 31, "area": 900}}),
          "more merged error regions, or area above the baseline + 0.05%: Local interconnect width")
    check("D3 Magic did not finish", md("Loading DRC CIF style.\nTotal DRC errors found: 0\n"), "did not finish")
    check("D4 merged area 0.25 % above the baseline", md(log.format(t=100, a=60, b=40, extra=""), {**same, dt1: {"polygons": 20, "area": 401}}),
          "Diffusion width < 0.15um (diff/tap.1): 20 regions, area 401 > baseline 20, 400")
    check("D8 merged area 0.1 % above the baseline", md(log.format(t=100, a=60, b=40, extra=""), {**same, li1: {"polygons": 30, "area": 900.9}}),
          "area above the baseline + 0.05%")
    check("D8a merged area 0.03 % above the baseline (Magic's cut lines; positive control)",
          md(log.format(t=100, a=60, b=40, extra=""), {**same, li1: {"polygons": 30, "area": 900.27}}), None)
    check("D5 more boxes, same merged regions (Phase 6: Magic cut boxes on another line; positive control)",
          md(log.format(t=230, a=60, b=170, extra="")), None)
    check("D6 a rule with errors but no merged regions (KLayout did not run)", md(log.format(t=95, a=55, b=40, extra=""), {li1: same[li1]}),
          "no merged regions for 1 rule(s)")
    # D7: one real Magic + KLayout run on a tiny GDS: two li1 pairs 0.10 um apart (li.3 needs 0.17) must have more
    # merged li.3 regions than a baseline made from one pair
    with tempfile.TemporaryDirectory() as t:
        mk = os.path.join(t, "mk.py")
        open(mk, "w").write("import pya\nly = pya.Layout()\nly.dbu = 0.001\nc = ly.create_cell(top)\nli = ly.layer(67, 20)\n"
                            "for i in range(int(pairs)):\n    y = 4000 * i\n    c.shapes(li).insert(pya.Box(0, y, 1000, y + 1000))\n"
                            "    c.shapes(li).insert(pya.Box(1100, y, 2100, y + 1000))\nly.write(dst)\n")
        got = {}
        for pairs in ("1", "2"):
            gds = os.path.join(t, f"p{pairs}.gds")
            macro_klayout_drc.nix(f"klayout -b -rd top=neg_li -rd pairs={pairs} -rd dst='{gds}' -r '{mk}'", os.path.join(t, "mk.log"))
            logf = os.path.join(t, f"p{pairs}.magic.log")
            total, rules = macro_drc.parse(macro_drc.run_magic(gds, "neg_li", logf))
            got[pairs] = (total, rules, macro_drc.merge(logf + ".boxes.tsv", logf + ".merged.json"))
        base7 = {"total": got["1"][0], "rules": got["1"][1], "merged": got["1"][2]}
        check("D7 one more li.3 error than the baseline (real Magic and KLayout run)",
              macro_drc.compare(*got["2"], base7) if got["1"][2] else ["the baseline run merged nothing"],
              "more merged error regions, or area above the baseline + 0.05%: Local interconnect spacing")

    def lib(power, extra_when=False):
        groups = [("!csb0 & !web0", power), ("csb0 & web0", power)] + ([("!csb0 & web0", power)] if extra_when else [])
        body = "".join(f'        internal_power(){{\n            when : "{w}"; \n            rise_power(scalar){{\n'
                       f'                values("{v}");\n            }}\n            fall_power(scalar){{\n'
                       f'                values("{v}");\n            }}\n        }}\n' for w, v in groups)
        return f"cell (m){{\n    area : 1.0;\n    pin(clk0){{\n        clock : true;\n{body}    }}\n}}\n"
    ours, pdk = lib("1.036316e+11"), lib("1.380840e+01")
    tmpl, probs = lib_template.make(ours, pdk)
    check("L0 template from OpenRAM's .lib with the PDK macro's power (positive control)",
          probs + gen_char_lib.power_problems(tmpl or ""), None)
    check("L1 OpenRAM's internal_power used as the template", gen_char_lib.power_problems(ours), "outside (0, 1000]")
    check("L2 power entries of the two .lib differ", lib_template.make(lib("1.036316e+11", extra_when=True), pdk)[1],
          "power entries differ")

    # check_char_lib.provenance on a fake repo root holding a self-generated macro; only its netlist rows are judged
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "env"))
        shutil.copy(os.path.join(check_char_lib.ROOT, "env", "versions.mk"), os.path.join(root, "env"))
        d = os.path.join(root, "ip", "sram", "neg_sram", "openram")
        os.makedirs(d)
        net = os.path.join(d, "neg_sram.sp")
        open(net, "w").write(".SUBCKT neg_sram a b\n.ENDS\n")
        sha = hashlib.sha256(open(net, "rb").read()).hexdigest()
        summ = os.path.join(d, "summary.json")
        json.dump({"outputs_sha256": {"neg_sram.sp": sha}}, open(summ, "w"))
        saved = check_char_lib.ROOT, check_char_lib.MACRO
        check_char_lib.ROOT, check_char_lib.MACRO = root, "neg_sram"
        try:
            netrows = lambda doc: [p for p in check_char_lib.provenance(doc) if p.startswith("netlist_sha256") or "summary.json" in p]
            check("C0 char.json from the committed netlist that summary.json records (positive control)",
                  netrows({"netlist_sha256": sha}), None)
            check("C1 char.json made from another netlist", netrows({"netlist_sha256": "0" * 64}), "netlist_sha256 000000000000 is not")
            json.dump({"outputs_sha256": {"neg_sram.sp": "1" * 64}}, open(summ, "w"))
            check("C2 the netlist is not the one summary.json records", netrows({"netlist_sha256": sha}),
                  "is not the netlist summary.json records")
            # a later run wrote the same circuit in another order (2026-10-10): summary.json records that run's
            # sha256 and its spice_content_sha256; the committed netlist is the earlier one the .lib came from
            two = "* header\n.SUBCKT neg_sram a b\nX1 a b inv\n.ENDS\n.subckt inv a b\nM1 b a 0 0 nfet W=1\n.ends\n"
            later = os.path.join(root, "later.sp")
            open(later, "w").write("* other header\n.subckt inv a b\nM1 b a 0 0 nfet W=1\n.ends\n"
                                   ".SUBCKT neg_sram a b\nX1 a b inv\n.ENDS\n")
            for case, text, want in (("C3 earlier netlist, same subcircuits in another order (positive control)", two, None),
                                     ("C4 earlier netlist with one transistor width changed", two.replace("W=1", "W=2"),
                                      "is not the netlist summary.json records"),
                                     ("C5 earlier netlist with one subcircuit missing", two.split(".subckt")[0],
                                      "is not the netlist summary.json records")):
                open(net, "w").write(text)
                sha = hashlib.sha256(text.encode()).hexdigest()
                json.dump({"outputs_sha256": {"neg_sram.sp": "2" * 64},
                           "spice_content_sha256": gen_macro.spice_content_sha256(later)}, open(summ, "w"))
                check(case, netrows({"netlist_sha256": sha}), want)
        finally:
            check_char_lib.ROOT, check_char_lib.MACRO = saved

    # check_char_lib.power_problems on the self-generated macro's char/ (C6, C7: Phase 6 independent review H7)
    macro = "arv_sram_2kbyte_1rw1r_32x512_8"
    src = os.path.join(check_char_lib.ROOT, "ip", "sram", macro, "char")
    saved = check_char_lib.MACRO
    check_char_lib.MACRO = macro
    try:
        doc = json.load(open(os.path.join(src, "char.json")))
        one = 'rise_power(scalar){\n                values("12.180757");'
        for case, new, want in (("C6a the macro's char/ as is (positive control)", one, None),
                                ("C6 a clk0 internal_power table with a second number 1e11",
                                 'rise_power(scalar){\n                values("12.180757, 1.0e11");', "rise_power nan"),
                                ("C7 a clk0 internal_power table with an index_1",
                                 'rise_power(scalar){\n                index_1("0.01");\n                values("12.180757");', "rise_power nan")):
            with tempfile.TemporaryDirectory() as t:
                d = os.path.join(t, "char")
                shutil.copytree(src, d)
                f = os.path.join(d, f"{macro}__tt_025C_1v80.lib")
                text = open(f).read()
                if text.count(one) != 1:
                    raise SystemExit(f"neg_openram: injection point not found once in {f}")
                open(f, "w").write(text.replace(one, new))
                check(case, check_char_lib.power_problems(doc, d)[0], want)
    finally:
        check_char_lib.MACRO = saved

    # macro_klayout_drc: report parsing (K0-K3), the deck's name exclusion (K4), and one real KLayout run each on a
    # tiny GDS with two psdm 0.26 um apart (psdm.1 needs 0.38; the 2026-10-10 case) under a plain name and under a
    # name the deck excludes (K5, K6)
    rule = "  <category>\n   <name>{r}</name>\n  </category>\n"
    def rdb(top="m", rules=macro_klayout_drc.REQUIRED, items=()):
        return (f"<report-database>\n <top-cell>{top}</top-cell>\n <categories>\n" + "".join(rule.format(r=r) for r in rules)
                + " </categories>\n <items>\n" + "".join(f"  <item>\n   <category>'{r}'</category>\n   <cell>{c}</cell>\n  </item>\n"
                                                      for r, c in items) + " </items>\n</report-database>\n")
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "r.lyrdb")
        open(p, "w").write(rdb())
        check("K0 report with every required rule and no item (positive control)", macro_klayout_drc.parse(p, "m")[0], None)
        open(p, "w").write(rdb(items=[("psdm.1", "m_delay_chain")]))
        check("K1 one error in the report", macro_klayout_drc.parse(p, "m")[0], "errors per rule: psdm.1 1")
        check("K2 no report (KLayout did not finish)", macro_klayout_drc.parse(os.path.join(t, "none.lyrdb"), "m")[0],
              "wrote no report")
        open(p, "w").write(rdb(rules=("m2.2", "li.1")))
        check("K3 front-end rules missing (feol off)", macro_klayout_drc.parse(p, "m")[0], "not in the report")
    deck = open(os.path.join(macro_klayout_drc.PDK_ROOT, macro_klayout_drc.DECK), encoding="utf-8").read()
    pats = macro_klayout_drc.deck_patterns(deck)
    check("K4 a cell name the deck leaves out of its nwell/nsdm/psdm checks",
          ["excluded"] if macro_klayout_drc.excluded(["arv_x", "sky130_sram_2kbyte_1rw1r_32x512_8_bank"], pats) else [], "excluded")
    fake = 'x = layout(source.cell_obj).select(\n  "-*io_pad*",\n  "-cmux"\n)\n# y = layout(source.cell_obj).select("-*commented*")\n'
    got = macro_klayout_drc.deck_patterns(fake)
    check("K8 the deck's selections parsed (two patterns, not the commented one)",
          [] if got == ["*io_pad*", "cmux"] else [f"parsed {got}"], None)
    with tempfile.TemporaryDirectory() as t:
        mk = os.path.join(t, "mk.py")
        open(mk, "w").write("import pya\nly = pya.Layout()\nly.dbu = 0.001\nc = ly.create_cell(top)\nli = ly.layer(94, 20)\n"
                            "c.shapes(li).insert(pya.Box(0, 0, 1000, 1000))\nc.shapes(li).insert(pya.Box(1260, 0, 2260, 1000))\n"
                            "ly.write(dst)\n")
        for case, top, want in (("K5 two psdm 0.26 um apart (real KLayout run)", "neg_psdm", "errors per rule: psdm.1"),
                                ("K6 the same under a name the deck excludes (real KLayout run)", "neg_sky130_sram_1kbyte_x",
                                 "match a name the deck treats specially"),
                                ("K7 the same under a sky130_fd_io name the deck leaves out of nwell.6 (real KLayout run)",
                                 "neg_sky130_fd_io__simple_pad_and_busses", "match a name the deck treats specially")):
            gds = os.path.join(t, top + ".gds")
            macro_klayout_drc.nix(f"klayout -b -rd top={top} -rd dst='{gds}' -r '{mk}'", os.path.join(t, "mk.log"))
            check(case, macro_klayout_drc.run(gds, top, os.path.join(t, top + ".json"))["problems"], want)

    print(f"neg-openram: {'PASS' if all(results) else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
