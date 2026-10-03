#!/usr/bin/env python3
"""Source tracking of a harden run (project-plan.md §7.2 "來源追溯").

usage: provenance.py --record <out.json> [--repo <dir>]
       provenance.py --verify <out.json> --resolved <run>/resolved.json [--repo <dir>]
       (--repo, default this repo, is for signoff/scripts/neg_provenance.py)

--record (before the LibreLane run) checks and writes:
  repo_head    `git rev-parse HEAD` of this repo
  uncommitted  `git status --porcelain` must be empty: no modified, staged or untracked files
               (ignored files such as runs/ and .tools/ do not count). A signoff run must come
               from a commit, otherwise nobody can tell which RTL, config and limits it used.
  submodules   `git submodule status`: every submodule initialized and at the recorded commit
  librelane    HEAD of the LibreLane clone == LIBRELANE_COMMIT in env/versions.mk
  pdk          $PDK_ROOT/<PDK> (default ~/.ciel) resolves to versions/<SKY130_PDK_HASH>
--verify (after the run) checks the same again against the record (HEAD unchanged and the tree
still clean, so files read late in the flow, such as the limits and the golden, are the
committed ones) and that the run's resolved.json used the pinned LibreLane version and PDK.
Prints one row per item and `provenance: PASS` / `provenance: FAIL`; exit code 0 only on PASS.
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def pin(name, repo=ROOT):
    for line in open(os.path.join(repo, "env", "versions.mk"), encoding="utf8"):
        m = re.match(rf"^{name}\s*=\s*(\S+)", line)
        if m:
            return m.group(1)
    raise KeyError(name)


def git(*args, cwd):
    cp = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    return cp.returncode, cp.stdout


def collect(repo):
    rc, head = git("rev-parse", "HEAD", cwd=repo)
    _, status = git("status", "--porcelain", "--untracked-files=all", cwd=repo)
    _, subs = git("submodule", "status", cwd=repo)
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    _, ll_head = git("rev-parse", "HEAD", cwd=ll_dir)
    pdk_dir = os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), pin("PDK", repo))
    return {
        "repo_head": head.strip() if rc == 0 else None,
        "uncommitted": [line for line in status.splitlines() if line.strip()],
        "submodules": [line for line in subs.splitlines() if line.strip()],
        "librelane_dir": ll_dir,
        "librelane_head": ll_head.strip() or None,
        "pdk_dir": pdk_dir,
        "pdk_realpath": os.path.realpath(pdk_dir) if os.path.isdir(pdk_dir) else None,
    }


def check(rec, rows, repo):
    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    row("repo_head", bool(rec["repo_head"]), rec["repo_head"] or "not a git checkout")
    n = len(rec["uncommitted"])
    row("uncommitted", n == 0, "working tree clean" if n == 0 else
        f"{n} uncommitted file(s), e.g. {', '.join(rec['uncommitted'][:3])}; commit first, a signoff run must come from a commit")
    bad = [s for s in rec["submodules"] if s[:1] in "-+U"]
    row("submodules", bool(rec["submodules"]) and not bad,
        f"{len(rec['submodules'])} at the recorded commit" if rec["submodules"] and not bad
        else f"not initialized or not at the recorded commit: {bad or 'none listed'}")
    want = pin("LIBRELANE_COMMIT", repo)
    row("librelane", rec["librelane_head"] == want, f"{rec['librelane_dir']} at {rec['librelane_head']}, pinned {want}")
    want = pin("SKY130_PDK_HASH", repo)
    ok = rec["pdk_realpath"] is not None and f"/versions/{want}/" in rec["pdk_realpath"] + "/"
    row("pdk", ok, f"{rec['pdk_dir']} -> {rec['pdk_realpath']}, pinned {want}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--record")
    g.add_argument("--verify")
    ap.add_argument("--resolved")
    ap.add_argument("--repo", default=ROOT)
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    rows = []
    rec = collect(repo)
    check(rec, rows, repo)
    if args.record:
        json.dump(rec, open(args.record, "w"), indent=1)
    else:
        if not args.resolved:
            ap.error("--verify needs --resolved")
        try:
            start = json.load(open(args.verify, encoding="utf8"))
        except (OSError, ValueError) as e:
            start = None
            rows.append(False)
            print(f"  [FAIL] record: cannot read {args.verify}: {e}")
        if start is not None:
            same = start.get("repo_head") == rec["repo_head"]
            rows.append(same)
            print(f"  [{'PASS' if same else 'FAIL'}] same_head: start {start.get('repo_head')}, end {rec['repo_head']}")
        try:
            res = json.load(open(args.resolved, encoding="utf8"))
            ll_ver = res.get("meta", {}).get("librelane_version")
            pdk_root = res.get("PDK_ROOT") or ""
        except (OSError, ValueError) as e:
            ll_ver, pdk_root = None, ""
            print(f"  [FAIL] resolved: cannot read {args.resolved}: {e}")
        ok = ll_ver == pin("LIBRELANE_TAG", repo)
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] resolved_librelane: {ll_ver}, pinned {pin('LIBRELANE_TAG', repo)}")
        ok = pdk_root.rstrip("/").endswith("/versions/" + pin("SKY130_PDK_HASH", repo))
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] resolved_pdk: PDK_ROOT {pdk_root or None}")
    ok = bool(rows) and all(rows)
    print(f"provenance: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
