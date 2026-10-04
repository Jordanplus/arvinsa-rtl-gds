#!/usr/bin/env python3
"""Shared check for every step that uses the output of a harden run (EQY, gate-level simulation,
neg-pnr, ...). Known limitation 12 of docs/phase_exit/phase3.md.

guard(run, verdict) returns a list of errors; an empty list means the run may be used:
  1. <run>_signoff/result.txt is exactly the line `verdict` (`harden-soc: PASS` or
     `harden-core: PASS`): the harden target's overall verdict, which includes the signoff limits,
     the golden comparison, the design checks and the source tracking.
  2. <run>_signoff/provenance.json (written by signoff/scripts/provenance.py --record at the start
     of the run) records repo_head == `git rev-parse HEAD` of this repo: the run was made from
     the commit that is checked out now. Without this, `make eqy-soc` after a new commit still
     checks the netlist of the old commit and can PASS.
Callers remove their own output directory before calling guard(), so a refused run leaves no
output of an earlier run behind.

usage: run_guard.py <run> <verdict>   (prints the errors; exit code 0 only if there are none)
"""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def head(repo=ROOT):
    cp = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True)
    return cp.stdout.strip() if cp.returncode == 0 else None


def guard(run, verdict, repo=ROOT):
    sign = os.path.abspath(run).rstrip(os.sep) + "_signoff"
    errors = []
    result = os.path.join(sign, "result.txt")
    lines = open(result, encoding="utf8").read().splitlines() if os.path.isfile(result) else []
    if lines != [verdict]:
        errors.append(f"{result} does not say '{verdict}': the harden run did not pass")
    prov = os.path.join(sign, "provenance.json")
    try:
        run_head = json.load(open(prov, encoding="utf8")).get("repo_head")
        if not run_head:
            errors.append(f"{prov} has no repo_head")
    except (OSError, ValueError) as e:
        run_head = None
        errors.append(f"cannot read the source record {prov}: {e}")
    now = head(repo)
    if run_head and run_head != now:
        errors.append(f"the harden run was made from commit {run_head}, but HEAD is {now}: "
                      "re-run the harden target for this commit")
    return errors


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    errs = guard(sys.argv[1], sys.argv[2])
    for e in errs:
        print(f"  [FAIL] {e}")
    print(f"run-guard: {'PASS' if not errs else 'FAIL'}")
    sys.exit(0 if not errs else 1)
