#!/usr/bin/env python3
"""Check the OpenRAM install (Phase 6, ADR-0018): the tracked files and the sky130 cell library.

    python3 ip/sram/openram/check_install.py [<openram_dir> <sky130_fd_bd_sram_dir>]

OpenRAM's `make sky130-install` copies with `cp $?` (only sources newer than the target directory). Its
technology/sky130/*_lib directories exist in the checkout, so a cell library cloned earlier is silently not
copied and make still exits 0; the failure shows up only later as "Custom cell pin names do not match spice
file: [...] vs []" (docs/notes/openram_phase6_bringup.md, item 1). This checks that every cell GDS of
sky130_fd_bd_sram is in gds_lib and every cell SPICE is in sp_lib.
It also checks that OpenRAM's tracked files are exactly OPENRAM_COMMIT with ip/sram/openram/patches/*.patch
applied in order (tree_problems: the tree of the working files equals the pinned tree plus the patches; a
missing patch, another edit or another HEAD all FAIL). Used by setup.sh and gen_macro.py; negative tests in
neg_openram.py (I1-I4, T1-T3).
"""
import glob
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PATCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patches")


def pin(name):
    for line in open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf-8"):
        m = re.match(rf"^{name}\s*=\s*(\S+)", line)
        if m:
            return m.group(1)
    return ""


def patch_files(patch_dir=PATCH_DIR):
    return sorted(glob.glob(os.path.join(patch_dir, "*.patch")))


def tree_problems(or_dir, commit, patches):
    """Problems if the tracked files of the git checkout or_dir are not commit + patches (in order)."""
    def git(*a, index=None):
        env = dict(os.environ, GIT_INDEX_FILE=index) if index else None
        return subprocess.run(["git", "-C", or_dir, *a], capture_output=True, text=True, env=env)
    head = git("rev-parse", "HEAD").stdout.strip()
    out = [] if head == commit else [f"{or_dir} HEAD is {head[:8] or '?'}, not {commit[:8]}"]
    with tempfile.TemporaryDirectory() as t:
        want, have = os.path.join(t, "want"), os.path.join(t, "have")
        if git("read-tree", commit, index=want).returncode or git("read-tree", commit, index=have).returncode:
            return out + [f"commit {commit[:8]} not in {or_dir}"]
        for p in patches:
            r = git("apply", "--cached", p, index=want)
            if r.returncode:
                return out + [f"{os.path.basename(p)} does not apply to {commit[:8]}: {r.stderr.strip()[:120]}"]
        git("add", "-u", index=have)
        t_want, t_have = git("write-tree", index=want).stdout.strip(), git("write-tree", index=have).stdout.strip()
        if t_want != t_have:
            names = git("diff-tree", "-r", "--name-only", t_want, t_have).stdout.split()
            out.append(f"tracked files differ from {commit[:8]} + {len(patches)} patch(es): {', '.join(names[:5])}")
    return out


def default_dirs():
    pdk_hash = ""
    for line in open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf-8"):
        m = re.match(r"^OPENRAM_PDK_HASH\s*=\s*(\S+)", line)
        if m:
            pdk_hash = m.group(1)
    tools = os.path.join(ROOT, ".tools")
    return os.path.join(tools, "openram"), os.path.join(tools, f"openram-pdk-{pdk_hash[:8]}", "sky130_fd_bd_sram")


def problems(or_dir, bd_dir):
    """List of problems (empty = complete)."""
    tech = os.path.join(or_dir, "technology", "sky130")
    gds = sorted(glob.glob(os.path.join(bd_dir, "cells", "*", "*.gds")))
    if not gds:
        return [f"no cell GDS under {bd_dir}/cells"]
    out = []
    miss = [os.path.basename(g) for g in gds if not os.path.isfile(os.path.join(tech, "gds_lib", os.path.basename(g)))]
    if miss:
        out.append(f"{len(miss)} of {len(gds)} cell GDS not in gds_lib (e.g. {miss[0]})")
    # sp_lib keeps <cell>.sp for each <cell>.spice and <cell>.base.spice (lvs/calibre/klayout variants go elsewhere)
    sp = set()
    for s in glob.glob(os.path.join(bd_dir, "cells", "*", "*.spice")):
        b = os.path.basename(s)
        if re.search(r"\.lvs(\.calibre|\.klayout)?\.spice$", b):
            continue
        sp.add(re.sub(r"(\.base)?\.spice$", ".sp", b))
    miss = sorted(x for x in sp if not os.path.isfile(os.path.join(tech, "sp_lib", x)))
    if miss:
        out.append(f"{len(miss)} of {len(sp)} cell SPICE not in sp_lib (e.g. {miss[0]})")
    return out


def main(argv):
    or_dir, bd_dir = argv[1:3] if len(argv) >= 3 else default_dirs()
    patches = patch_files()
    p = tree_problems(or_dir, pin("OPENRAM_COMMIT"), patches) + problems(or_dir, bd_dir)
    print("check_install: " + ("FAIL - " + "; ".join(p) if p else
          f"PASS - {or_dir} is {pin('OPENRAM_COMMIT')[:8]} + {len(patches)} patch(es), cell library installed"))
    return 1 if p else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
