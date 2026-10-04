#!/usr/bin/env python3
"""make neg-provenance: bug injection into the source tracking of a harden run; provenance.py must
FAIL at the expected row on each case, and PASS on a clean copy (positive control).

usage: neg_provenance.py

Works on a local clone of HEAD in runs/neg_provenance/repo (the submodule is initialized from the
local third_party/ checkout, no network); this repo's working tree is not touched.
  clean           clean clone, pinned LibreLane and PDK          PASS (positive control)
  untracked       clone + one new file                           FAIL uncommitted
  modified        clone + one changed tracked file               FAIL uncommitted
  no_submodule    clone without `git submodule update --init`    FAIL submodules
  librelane       LIBRELANE_DIR = a git checkout at another commit FAIL librelane
  librelane_dirty LIBRELANE_DIR = a clone at the pinned commit with base.sdc edited
                                                                 FAIL librelane_clean
  pdk             PDK_ROOT = a directory whose sky130A points to another version FAIL pdk
  pdk_modified    PDK_ROOT = the pinned version, but one file of libs.tech/netgen edited
                  (the other directories are symlinks to the real PDK) FAIL pdk_content
  head_changed    --verify with a record from another commit     FAIL same_head
  resolved_pdk    --verify with resolved.json PDK_ROOT of another version FAIL resolved_pdk
  resolved_ll     --verify with resolved.json LibreLane 3.0.13   FAIL resolved_librelane
  resolved_outside --verify with resolved.json reading a PDK file outside the content-checked
                  directories (sky130_fd_sc_hs)                  FAIL resolved_pdk_paths
  no_record       --verify without the record file               FAIL record
  final_clean     --final on the clean clone with its own record  PASS (positive control)
  final_dirty     --final on a clone with one changed file       FAIL uncommitted
  final_head      --final with a record from another commit      FAIL same_head
A negative case PASSes only if the expected row is the one that FAILs (pdk: also pdk_content,
because the other version directory is empty) and the verdict is `provenance: FAIL`.
Prints `neg-provenance: PASS n/n` / `neg-provenance: FAIL ...`; exit code 0 only on PASS.
"""
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "runs", "neg_provenance")
PROV = os.path.join(ROOT, "signoff", "scripts", "provenance.py")


def sh(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def clone(name, init_submodules=True):
    d = os.path.join(OUT, name)
    sh("git", "clone", "-q", ROOT, d)
    if init_submodules:
        out = subprocess.run(["git", "-C", d, "config", "--file", ".gitmodules", "--get-regexp", r"submodule\..*\.path"],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            key, path = line.split()
            name_ = key[len("submodule."):-len(".path")]
            sh("git", "-C", d, "config", f"submodule.{name_}.url", os.path.join(ROOT, path))
        sh("git", "-c", "protocol.file.allow=always", "-C", d, "submodule", "update", "--init", "-q")
    return d


def prov(*args, env=None):
    e = dict(os.environ)
    e.update(env or {})
    cp = subprocess.run([sys.executable, PROV, *args], capture_output=True, text=True, env=e)
    return cp.returncode, cp.stdout


def pin(name):
    for line in open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf8"):
        m = re.match(rf"^{name}\s*=\s*(\S+)", line)
        if m:
            return m.group(1)
    raise KeyError(name)


def main():
    shutil.rmtree(OUT, ignore_errors=True)  # only runs/neg_provenance is removed
    os.makedirs(OUT)
    repo = clone("repo")
    rec = os.path.join(OUT, "record.json")
    resolved = os.path.join(OUT, "resolved.json")
    pdk_root = os.path.join(os.path.expanduser("~/.ciel"), "ciel", "sky130", "versions", pin("SKY130_PDK_HASH"))
    lib = lambda scl: {"*": [f"{pdk_root}/{pin('PDK')}/libs.ref/{scl}/lib/{scl}__tt_025C_1v80.lib"]}  # noqa: E731
    json.dump({"meta": {"librelane_version": pin("LIBRELANE_TAG")}, "PDK_ROOT": pdk_root, "LIB": lib(pin("STD_CELL_LIBRARY"))},
              open(resolved, "w"))

    results = []

    def case(name, rc_out, want, also=()):
        rc, out = rc_out
        if want == "PASS":
            ok = rc == 0 and out.rstrip().endswith("provenance: PASS")
        else:
            failed = set(re.findall(r"^  \[FAIL\] (\w+):", out, re.M))
            ok = rc != 0 and failed == {want, *also} and out.rstrip().endswith("provenance: FAIL")
        results.append(ok)
        open(os.path.join(OUT, f"{name}.log"), "w").write(out)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: expected {want if want == 'PASS' else 'FAIL at ' + want}")

    case("clean", prov("--record", rec, "--repo", repo), "PASS")
    if not results[-1]:
        print("neg-provenance: FAIL (the positive control did not PASS; see runs/neg_provenance/clean.log)")
        return 1
    case("clean_verify", prov("--verify", rec, "--resolved", resolved, "--repo", repo), "PASS")

    d = clone("untracked")
    open(os.path.join(d, "new_file.txt"), "w").write("x\n")
    case("untracked", prov("--record", os.devnull, "--repo", d), "uncommitted")

    d = clone("modified")
    with open(os.path.join(d, "README.md"), "a") as f:
        f.write("\n")
    case("modified", prov("--record", os.devnull, "--repo", d), "uncommitted")

    d = clone("no_submodule", init_submodules=False)
    case("no_submodule", prov("--record", os.devnull, "--repo", d), "submodules")

    case("librelane", prov("--record", os.devnull, "--repo", repo, env={"LIBRELANE_DIR": repo}), "librelane")

    ll_src = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    ll = os.path.join(OUT, "librelane_dirty")
    sh("git", "clone", "-q", "--no-checkout", "--shared", ll_src, ll)
    sh("git", "-C", ll, "checkout", "-q", "--detach", pin("LIBRELANE_COMMIT"))
    with open(os.path.join(ll, "librelane", "scripts", "base.sdc"), "a") as f:
        f.write("set_clock_uncertainty 0 [all_clocks]\n")
    case("librelane_dirty", prov("--record", os.devnull, "--repo", repo, env={"LIBRELANE_DIR": ll}), "librelane_clean")

    fake = os.path.join(OUT, "fake_pdk_root")
    other = os.path.join(fake, "ciel", "sky130", "versions", "0" * 40, pin("PDK"))
    os.makedirs(other)
    os.symlink(other, os.path.join(fake, pin("PDK")))
    case("pdk", prov("--record", os.devnull, "--repo", repo, env={"PDK_ROOT": fake}), "pdk", also=("pdk_content",))

    # Same version hash, one edited file: real directories with symlinks to the real PDK, except a
    # copy of libs.tech/netgen.
    sys.path.insert(0, os.path.dirname(PROV))
    import provenance  # noqa: E402
    fake2 = os.path.join(OUT, "fake_pdk_modified")
    ver = os.path.join(fake2, "ciel", "sky130", "versions", pin("SKY130_PDK_HASH"))
    for d in provenance.pdk_content_dirs():
        dst = os.path.join(ver, d)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if d.endswith("libs.tech/netgen"):
            shutil.copytree(os.path.join(pdk_root, d), dst)
            with open(os.path.join(dst, f"{pin('PDK')}_setup.tcl"), "a") as f:
                f.write("# neg_provenance: edited\n")
        else:
            os.symlink(os.path.join(pdk_root, d), dst)
    os.symlink(os.path.join(ver, pin("PDK")), os.path.join(fake2, pin("PDK")))
    case("pdk_modified", prov("--record", os.devnull, "--repo", repo, env={"PDK_ROOT": fake2}), "pdk_content")

    r = json.load(open(rec))
    r["repo_head"] = "0" * 40
    bad_rec = os.path.join(OUT, "record_other_head.json")
    json.dump(r, open(bad_rec, "w"))
    case("head_changed", prov("--verify", bad_rec, "--resolved", resolved, "--repo", repo), "same_head")

    bad = os.path.join(OUT, "resolved_pdk.json")
    other = pdk_root.replace(pin("SKY130_PDK_HASH"), "0" * 40)
    json.dump({"meta": {"librelane_version": pin("LIBRELANE_TAG")}, "PDK_ROOT": other,
               "LIB": {"*": [p.replace(pdk_root, other) for p in lib(pin("STD_CELL_LIBRARY"))["*"]]}}, open(bad, "w"))
    case("resolved_pdk", prov("--verify", rec, "--resolved", bad, "--repo", repo), "resolved_pdk")

    bad = os.path.join(OUT, "resolved_ll.json")
    json.dump({"meta": {"librelane_version": "3.0.13"}, "PDK_ROOT": pdk_root, "LIB": lib(pin("STD_CELL_LIBRARY"))}, open(bad, "w"))
    case("resolved_ll", prov("--verify", rec, "--resolved", bad, "--repo", repo), "resolved_librelane")

    bad = os.path.join(OUT, "resolved_outside.json")
    r = json.load(open(resolved))
    r["EXTRA_LIBS"] = lib("sky130_fd_sc_hs")["*"]
    json.dump(r, open(bad, "w"))
    case("resolved_outside", prov("--verify", rec, "--resolved", bad, "--repo", repo), "resolved_pdk_paths")

    case("no_record", prov("--verify", os.path.join(OUT, "missing.json"), "--resolved", resolved, "--repo", repo),
         "record")

    case("final_clean", prov("--final", rec, "--repo", repo), "PASS")
    d = clone("final_dirty")
    with open(os.path.join(d, "README.md"), "a") as f:
        f.write("\n")
    rec_d = os.path.join(OUT, "record_final_dirty.json")
    json.dump({"repo_head": subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()},
              open(rec_d, "w"))
    case("final_dirty", prov("--final", rec_d, "--repo", d), "uncommitted")
    case("final_head", prov("--final", bad_rec, "--repo", repo), "same_head")

    n = len(results)
    ok = all(results)
    print(f"neg-provenance: {'PASS' if ok else 'FAIL'} {sum(results)}/{n}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
