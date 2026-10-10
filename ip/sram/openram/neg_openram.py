#!/usr/bin/env python3
"""Bug injection for the OpenRAM checkers (Phase 6, ADR-0018): make neg-openram.

Each case builds a small fake run (or fake install) in a temp dir from a clean template, injects one error,
and must FAIL with the expected reason; the clean templates must PASS (positive controls).
  O1-O8  gen_macro.judge: OpenRAM log, its DRC/LVS reports, the output files
         (O1 is the defect seen on 2026-10-08: "ERROR ... LVS mismatch" in the log while OpenRAM exits 0)
  I1-I4  check_install.problems: `make sky130-install` leaving cells out while exiting 0
  T1-T3  check_install.tree_problems: OpenRAM's tracked files must be the pinned commit plus the repo patches
         (a patch not applied, another edit, another HEAD)
  D1-D3  macro_drc.parse/compare: a rule category the prebuilt macro does not have (the 2026-10-08 case:
         nwell.5a and routing spacing), a higher total, Magic not finishing
  L1-L2  the .lib template: gen_char_lib.power_problems refuses OpenRAM dev's internal_power 1.036316e+11
         (2026-10-08); lib_template.make refuses .lib files whose power entries differ
  C1-C2  check_char_lib.provenance for a self-generated macro: char.json made from another netlist than
         ip/sram/<macro>/openram/<macro>.sp, and that netlist not the one its summary.json records
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

    base = {"total": 100, "rules": {"Local interconnect width < 0.17um (li.1)": 60, "Diffusion width < 0.15um (diff/tap.1)": 40}}
    log = ("Loading DRC CIF style.\nTotal DRC errors found: {t}\nWHY {a} Local interconnect width < 0.17um (li.1)\n"
           "WHY {b} Diffusion width < 0.15um (diff/tap.1)\n{extra}MAGIC_DRC_DONE\n")
    check("D0 same categories, total within the baseline (positive control)",
          macro_drc.compare(*macro_drc.parse(log.format(t=95, a=55, b=40, extra="")), base), None)
    check("D1 a rule category the baseline does not have",
          macro_drc.compare(*macro_drc.parse(log.format(t=97, a=55, b=40, extra="WHY 2 Metal2 spacing < 0.14um (met2.2)\n")), base),
          "rule categories not in the baseline: Metal2 spacing")
    check("D2 total above the baseline", macro_drc.compare(*macro_drc.parse(log.format(t=101, a=61, b=40, extra="")), base), "total 101 > baseline 100")
    check("D3 Magic did not finish", macro_drc.compare(*macro_drc.parse("Loading DRC CIF style.\nTotal DRC errors found: 0\n"), base), "did not finish")

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
        finally:
            check_char_lib.ROOT, check_char_lib.MACRO = saved

    print(f"neg-openram: {'PASS' if all(results) else 'FAIL'} {sum(results)}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
