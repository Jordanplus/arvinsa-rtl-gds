#!/usr/bin/env python3
"""Source tracking of a harden run (project-plan.md §7.2 "來源追溯").

usage: provenance.py --record <out.json> [--repo <dir>]
       provenance.py --verify <out.json> --resolved <run>/resolved.json [--repo <dir>]
       provenance.py --final <record.json> [<record.json> ...] [--repo <dir>]
       provenance.py --make-pdk-content <out> --from-tarballs <dir>
       (--repo, default this repo, is for signoff/scripts/neg_provenance.py)

--record (before the LibreLane run) checks and writes:
  repo_head    `git rev-parse HEAD` of this repo
  uncommitted  `git status --porcelain` must be empty: no modified, staged or untracked files
               (ignored files such as runs/ and .tools/ do not count). A signoff run must come
               from a commit, otherwise nobody can tell which RTL, config and limits it used.
  submodules   `git submodule status`: every submodule initialized and at the recorded commit
  librelane    HEAD of the LibreLane clone == LIBRELANE_COMMIT in env/versions.mk
  librelane_clean  `git status --porcelain` of the LibreLane clone is empty: the flow scripts,
               base.sdc and the LVS/DRC scripts the run uses are the committed ones (Phase 3
               review: an edited base.sdc still gave `provenance: PASS`)
  pdk          $PDK_ROOT/<PDK> (default ~/.ciel) resolves to versions/<SKY130_PDK_HASH>
  pdk_content  the content of the PDK directories the flow reads (PDK_CONTENT_DIRS) equals
               env/pdk_content.sha256: per directory, sha256 over the sorted lines
               "<relative path>\0<sha256 of the file>\n" of all its files. That file is made
               from the downloaded tarballs (--make-pdk-content), whose sha256 are pinned in
               env/sky130_pdk_assets.sha256, so an edited PDK file FAILs here.
--verify (after the run) checks the same again against the record (HEAD unchanged and the tree
still clean, so files read late in the flow, such as the limits and the golden, are the
committed ones), that the run's resolved.json used the pinned LibreLane version and PDK, and
that every PDK path in resolved.json lies in PDK_CONTENT_DIRS (resolved_pdk_paths), so a file
outside the checked directories cannot be read unnoticed.
--final (end of `make regress`/`make phase3`) checks that HEAD still equals the repo_head of
every given record and the working tree is still clean: the later steps (EQY, simulation,
negative tests) ran on the same commit.
Prints one row per item and `provenance: PASS` / `provenance: FAIL`; exit code 0 only on PASS.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PDK_CONTENT = os.path.join("env", "pdk_content.sha256")


def pdk_content_dirs(repo=ROOT):
    """PDK directories (relative to the version directory) whose content is pinned."""
    pdk = pin("PDK", repo)
    return [f"{pdk}/libs.tech/{t}" for t in ("klayout", "magic", "netgen", "openlane")] + \
        [f"{pdk}/libs.ref/{pin('STD_CELL_LIBRARY', repo)}", f"{pdk}/libs.ref/sky130_sram_macros"]


def digest(files):
    """files: {relative path: sha256 hex}. One sha256 over the sorted "<path>\\0<sha>\\n" lines."""
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(f"{rel}\0{files[rel]}\n".encode())
    return h.hexdigest()


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_content(version_dir, dirs):
    """{dir: (digest, number of files)} of the installed PDK; a missing directory gives (None, 0)."""
    out = {}
    for d in dirs:
        top = os.path.join(version_dir, d)
        files = {}
        for base, _, names in os.walk(top, followlinks=True):
            for n in names:
                p = os.path.join(base, n)
                files[os.path.relpath(p, top)] = sha_file(p)
        out[d] = (digest(files), len(files)) if files else (None, 0)
    return out


def read_pdk_content(repo=ROOT):
    want = {}
    for line in open(os.path.join(repo, PDK_CONTENT), encoding="utf8"):
        if line.strip() and not line.startswith("#"):
            dig, d, n = line.split()
            want[d] = (dig, int(n))
    return want


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
    ll_rc, ll_status = git("status", "--porcelain", "--untracked-files=all", cwd=ll_dir)
    pdk_dir = os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), pin("PDK", repo))
    real = os.path.realpath(pdk_dir) if os.path.isdir(pdk_dir) else None
    return {
        "repo_head": head.strip() if rc == 0 else None,
        "uncommitted": [line for line in status.splitlines() if line.strip()],
        "submodules": [line for line in subs.splitlines() if line.strip()],
        "librelane_dir": ll_dir,
        "librelane_head": ll_head.strip() or None,
        "librelane_uncommitted": [line for line in ll_status.splitlines() if line.strip()] if ll_rc == 0 else None,
        "pdk_dir": pdk_dir,
        "pdk_realpath": real,
        "pdk_content": tree_content(os.path.dirname(real), pdk_content_dirs(repo)) if real else {},
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
    ll_dirty = rec["librelane_uncommitted"]
    row("librelane_clean", ll_dirty == [], "no modified or untracked file in the LibreLane clone" if ll_dirty == []
        else f"not a git checkout: {rec['librelane_dir']}" if ll_dirty is None
        else f"{len(ll_dirty)} modified or untracked file(s) in the LibreLane clone, e.g. {', '.join(ll_dirty[:3])}")
    want = pin("SKY130_PDK_HASH", repo)
    ok = rec["pdk_realpath"] is not None and f"/versions/{want}/" in rec["pdk_realpath"] + "/"
    row("pdk", ok, f"{rec['pdk_dir']} -> {rec['pdk_realpath']}, pinned {want}")
    try:
        pinned = read_pdk_content(repo)
    except (OSError, ValueError) as e:
        pinned = None
        row("pdk_content", False, f"cannot read {PDK_CONTENT}: {e}")
    if pinned is not None:
        have = {d: tuple(v) for d, v in rec["pdk_content"].items()}
        bad = sorted(d for d in set(pinned) | set(have) if have.get(d) != pinned.get(d))
        row("pdk_content", bool(pinned) and not bad,
            f"{len(pinned)} directories, {sum(n for _, n in pinned.values())} files, same content as {PDK_CONTENT}"
            if pinned and not bad else
            f"content differs from {PDK_CONTENT} in: "
            + ", ".join(f"{d} ({have.get(d, (None, 0))[1]} files, pinned {pinned.get(d, (None, 0))[1]})" for d in bad[:4]))


def pdk_paths(value, root, out):
    """All strings in resolved.json (nested) that are paths below root."""
    if isinstance(value, str):
        if value.startswith(root.rstrip("/") + "/"):
            out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            pdk_paths(v, root, out)
    elif isinstance(value, list):
        for v in value:
            pdk_paths(v, root, out)
    return out


def make_pdk_content(out, cache, repo=ROOT):
    """env/pdk_content.sha256 from the PDK tarballs in <cache> (sha256 checked against
    env/sky130_pdk_assets.sha256 first), not from the installed tree."""
    dirs = pdk_content_dirs(repo)
    files = {d: {} for d in dirs}
    for line in open(os.path.join(repo, "env", "sky130_pdk_assets.sha256"), encoding="utf8"):
        sha, name = line.split()
        path = os.path.join(cache, name)
        if sha_file(path) != sha:
            print(f"provenance: FAIL - {path} does not match env/sky130_pdk_assets.sha256")
            return 1
        with tarfile.open(path, "r:zst") as t:
            for m in t:
                d = next((d for d in dirs if m.name.startswith(d + "/")), None)
                if d is None:
                    continue
                if not m.isfile():
                    print(f"provenance: FAIL - {name}: {m.name} is not a regular file")
                    return 1
                files[d][m.name[len(d) + 1:]] = hashlib.sha256(t.extractfile(m).read()).hexdigest()
    with open(out, "w") as f:
        f.write(f"# Content of the PDK directories the flow reads: signoff/scripts/provenance.py pdk_content.\n"
                f"# Made with --make-pdk-content from the tarballs pinned in env/sky130_pdk_assets.sha256\n"
                f"# (SKY130_PDK_HASH {pin('SKY130_PDK_HASH', repo)}). Columns: digest, directory, number of files.\n")
        for d in dirs:
            if not files[d]:
                print(f"provenance: FAIL - no file of {d} in the tarballs")
                return 1
            f.write(f"{digest(files[d])}  {d}  {len(files[d])}\n")
    print(f"provenance: wrote {out} ({len(dirs)} directories, {sum(len(v) for v in files.values())} files)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--record")
    g.add_argument("--verify")
    g.add_argument("--final", nargs="+")
    g.add_argument("--make-pdk-content")
    ap.add_argument("--resolved")
    ap.add_argument("--from-tarballs")
    ap.add_argument("--repo", default=ROOT)
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    if args.make_pdk_content:
        if not args.from_tarballs:
            ap.error("--make-pdk-content needs --from-tarballs")
        return make_pdk_content(args.make_pdk_content, args.from_tarballs, repo)
    rows = []
    if args.final:
        rc, head = git("rev-parse", "HEAD", cwd=repo)
        _, status = git("status", "--porcelain", "--untracked-files=all", cwd=repo)
        dirty = [line for line in status.splitlines() if line.strip()]
        rows.append(not dirty)
        print(f"  [{'PASS' if not dirty else 'FAIL'}] uncommitted: "
              + ("working tree clean" if not dirty else f"{len(dirty)} uncommitted file(s), e.g. {', '.join(dirty[:3])}"))
        for path in args.final:
            try:
                start = json.load(open(path, encoding="utf8")).get("repo_head")
            except (OSError, ValueError) as e:
                start = f"unreadable ({e})"
            ok = rc == 0 and start == head.strip()
            rows.append(ok)
            print(f"  [{'PASS' if ok else 'FAIL'}] same_head: {path}: run from {start}, HEAD {head.strip()}")
        ok = all(rows)
        print(f"provenance: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
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
        paths = pdk_paths(res, pdk_root, []) if ll_ver is not None and pdk_root else []
        top = os.path.join(pdk_root, pin("PDK", repo))
        outside = sorted({p for p in paths if p.rstrip("/") != top
                          and not any(p.startswith(os.path.join(pdk_root, d) + "/") or p == os.path.join(pdk_root, d)
                                      for d in pdk_content_dirs(repo))})
        ok = bool(paths) and not outside
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] resolved_pdk_paths: {len(paths)} PDK paths in resolved.json"
              + (", all in the content-checked directories" if ok else
                 f", {len(outside)} outside the content-checked directories, e.g. {', '.join(outside[:3])}" if paths else ""))
    ok = bool(rows) and all(rows)
    print(f"provenance: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
