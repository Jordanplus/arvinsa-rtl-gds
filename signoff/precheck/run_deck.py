#!/usr/bin/env python3
"""The precheck's KLayout deck on one GDS, called the way cf-precheck does (checks/klayout_drc.py: input, topcell = the
GDS file name, report, thr, plus feol=true / beol=true), with the pinned deck (make precheck-deck) and LibreLane's
KLayout. Phase 7, ADR-0019 decision 5.

usage: run_deck.py --gds <file.gds> --out <dir> [--checks klayout_feol,klayout_beol]

Writes <out>/<check>_check.xml, <out>/<check>_check.log, <out>/<check>_check.total (item count, as cf-precheck
writes it) and <out>/input.sha1 (`<gds file>: <sha1>`, like cf-precheck's logs/gds.info). make precheck-sram-ref
runs it on the PDK SRAM for check_precheck.py's reference; neg_precheck.py on its fixture. Not a judgement: the judging run is the official image (skill tapeout-precheck-caravel rule 1).
Prints `run-deck: PASS ...` / `run-deck: FAIL ...` (FAIL only when KLayout fails, not for violations).
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def pin(name):
    m = re.search(rf"^{name}\s*=\s*(\S+)", open(os.path.join(ROOT, "env", "versions.mk")).read(), re.M)
    return m.group(1)


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def deck():
    return os.environ.get("PRECHECK_DECK", os.path.join(ROOT, ".tools", f"cf-precheck-{pin('CF_PRECHECK_VERSION')}",
                                                        "sky130A_mr.drc"))


def run(gds, out, check, thr=8):
    """Item count of the report, or None if KLayout failed."""
    os.makedirs(out, exist_ok=True)
    xml = os.path.join(out, f"{check}_check.xml")
    flag = check.split("_", 1)[1]
    gds = os.path.abspath(gds)
    top = os.path.splitext(os.path.basename(gds))[0]
    cmd = (f"klayout -b -r '{deck()}' -rd input='{gds}' -rd topcell={top} -rd report='{os.path.abspath(xml)}' "
           f"-rd thr={thr} -rd {flag}=true")
    env = dict(os.environ)
    env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    if os.path.exists(xml):
        os.remove(xml)
    with open(os.path.join(out, f"{check}_check.log"), "w") as log:
        r = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, stdout=log, stderr=subprocess.STDOUT, env=env)
    if r.returncode != 0 or not os.path.exists(xml):
        return None
    n = open(xml).read().count("<item>")
    open(os.path.join(out, f"{check}_check.total"), "w").write(str(n))
    with open(os.path.join(out, "input.sha1"), "w") as f:   # check_precheck.py ties the reference to --ref-gds
        f.write(f"{os.path.basename(gds)}: {sha1(gds)}\n")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gds", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--checks", default="klayout_feol,klayout_beol")
    args = ap.parse_args()
    if not os.path.exists(deck()):
        print(f"run-deck: FAIL {deck()} not found (make precheck-deck)")
        return 1
    ok = True
    for c in args.checks.split(","):
        t = time.time()
        n = run(args.gds, args.out, c)
        ok &= n is not None
        print(f"  [{'PASS' if n is not None else 'FAIL'}] {c}: "
              + (f"{n} item(s)" if n is not None else f"KLayout failed, see {args.out}/{c}_check.log")
              + f", {time.time() - t:.0f} s")
    print(f"run-deck: {'PASS' if ok else 'FAIL'} {os.path.basename(args.gds)} -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
