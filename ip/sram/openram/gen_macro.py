#!/usr/bin/env python3
"""Generate an SRAM macro with the pinned OpenRAM (Phase 6, ADR-0018) and check OpenRAM's own DRC/LVS.

    python3 ip/sram/openram/gen_macro.py <config.py> <out_dir> [--drc-max N]

- Needs `make openram-setup`. OpenRAM must be OPENRAM_COMMIT plus ip/sram/openram/patches/*.patch (check_install). Runs OpenRAM's sram_compiler.py inside LibreLane's nix-shell (Magic, Netgen,
  KLayout on PATH) with the .tools/openram-venv Python, PDK_ROOT = OpenRAM's own pinned PDK (decision 5).
- The config holds the design settings only; this script appends use_nix = False, keep_temp = True and
  output_path (<out_dir>/macro), and sets OPENRAM_TMP=<out_dir>/tmp (openram_temp in a config file is ignored).
- PYTHONHASHSEED=0: without it two runs of the same config route met2/met3/via2 differently
  (docs/notes/openram_phase6_bringup.md, item 6).
- PASS needs all of: no "ERROR" line in the OpenRAM log (OpenRAM exits 0 even on an LVS mismatch, item 2),
  "Total DRC errors found: N" with N <= --drc-max, LVS "Final result: Circuits match uniquely.", and the
  GDS/LEF/SPICE/Verilog outputs present. Writes <out_dir>/summary.json (pins, config, results, sha256).
- The contents of the views are not judged here: make openram-macro runs scripts/check_macro_views.py next
  (CLAUDE.md rule 12).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_install  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def pin(name):
    for line in open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf-8"):
        m = re.match(rf"^{name}\s*=\s*(\S+)", line)
        if m:
            return m.group(1)
    raise SystemExit(f"gen_macro: FAIL - {name} missing in env/versions.mk")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def judge(out, name, rc, drc_max):
    """(problems, drc, lvs, outputs sha256) of a finished run in <out> (openram.log, tmp/, macro/)."""
    problems = []
    text = open(os.path.join(out, "openram.log"), encoding="utf-8", errors="replace").read()
    errors = [ln for ln in text.splitlines() if ln.startswith("ERROR")]
    tmp = os.path.join(out, "tmp")
    drc = lvs = None
    try:
        drc = int(re.findall(r"Total DRC errors found: (\d+)", open(os.path.join(tmp, f"{name}.drc.out")).read())[-1])
    except (OSError, IndexError):
        problems.append("no DRC result")
    try:
        lvs = re.findall(r"Final result: (.*)", open(os.path.join(tmp, f"{name}.lvs.report")).read())[-1].strip()
    except (OSError, IndexError):
        problems.append("no LVS result")
    if rc != 0:
        problems.append(f"OpenRAM exit {rc}")
    if errors:
        problems.append(f"{len(errors)} ERROR line(s): {errors[0][:120]}")
    if drc is not None and drc > drc_max:
        problems.append(f"DRC {drc} > {drc_max}")
    if lvs is not None and lvs != "Circuits match uniquely.":
        problems.append(f"LVS: {lvs}")
    files = {}
    # the .lib is <name>_TT_1p8V_25C.lib (until 2026-10-09 this looked for <name>.lib and never recorded it);
    # its contents are checked by scripts/check_macro_views.py, the next step of make openram-macro
    for ext in (".gds", ".lef", ".sp", ".lvs.sp", ".v", "_TT_1p8V_25C.lib"):
        p = os.path.join(out, "macro", name + ext)
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            files[os.path.basename(p)] = sha256(p)
        elif not ext.endswith(".lib"):
            problems.append(f"missing or empty {name}{ext}")
    return problems, drc, lvs, files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("out_dir")
    ap.add_argument("--drc-max", type=int, default=0, help="OpenRAM's Magic DRC count allowed (default 0)")
    a = ap.parse_args()

    tools = os.path.join(ROOT, ".tools")
    or_dir = os.path.join(tools, "openram")
    pdk = os.path.join(tools, "openram-pdk-" + pin("OPENRAM_PDK_HASH")[:8])
    py = os.path.join(tools, "openram-venv", "bin", "python3")
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(tools, "librelane"))
    problems = []
    patches = check_install.patch_files()
    problems += check_install.tree_problems(or_dir, pin("OPENRAM_COMMIT"), patches)
    problems += check_install.problems(or_dir, os.path.join(pdk, "sky130_fd_bd_sram"))
    if not os.path.isfile(py) or not os.path.isdir(os.path.join(pdk, "sky130A")):
        problems.append("venv or OpenRAM PDK missing")
    if problems:
        print("gen_macro: FAIL - " + "; ".join(problems) + " (run make openram-setup)")
        return 1

    out = os.path.abspath(a.out_dir)
    if os.path.exists(out):
        moved = f"{out}.old-{time.strftime('%Y%m%d-%H%M%S')}"
        os.rename(out, moved)
        print(f"gen_macro: moved the previous {out} to {moved}")
    os.makedirs(out)
    base = open(a.config, encoding="utf-8").read()
    cfg = os.path.join(out, "config.py")
    with open(cfg, "w", encoding="utf-8") as f:
        f.write(base.rstrip("\n") + "\n\n# appended by ip/sram/openram/gen_macro.py\n"
                "use_nix = False\nkeep_temp = True\n"
                f"output_path = {os.path.join(out, 'macro')!r}\n")
    name = re.search(r'^output_name\s*=\s*"([^"]+)"', base, re.M)
    if not name:
        print("gen_macro: FAIL - the config must set output_name = \"...\" as a literal")
        return 1
    name = name.group(1)

    # OPENRAM_TMP, not openram_temp in the config: read_config only takes keys OPTS does not have yet, and
    # openram_temp is set at start-up, so the config value is silently ignored (reports land in /tmp).
    os.makedirs(os.path.join(out, "tmp"))
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONUNBUFFERED="1", PDK_ROOT=pdk, OPENRAM_TMP=os.path.join(out, "tmp"),
               OPENRAM_HOME=os.path.join(or_dir, "compiler"), OPENRAM_TECH=os.path.join(or_dir, "technology"),
               PYTHONPATH=f"{or_dir}:{os.path.join(or_dir, 'compiler')}")
    cmd = f"cd '{out}' && '{py}' '{os.path.join(or_dir, 'sram_compiler.py')}' '{cfg}'"
    log = os.path.join(out, "openram.log")
    t0 = time.time()
    with open(log, "w") as f:
        f.write(f"$ (cd {ll_dir} && nix-shell --run {cmd!r})  # PYTHONHASHSEED=0 PDK_ROOT={pdk} OPENRAM_TMP={out}/tmp\n")
        f.flush()
        rc = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
    minutes = round((time.time() - t0) / 60, 1)

    problems, drc, lvs, files = judge(out, name, rc, a.drc_max)
    summary = {
        "result": "FAIL" if problems else "PASS", "problems": problems, "minutes": minutes,
        "config": os.path.relpath(os.path.abspath(a.config), ROOT), "config_sha256": sha256(a.config),
        "openram_commit": pin("OPENRAM_COMMIT"),
        "openram_patches": [{"file": os.path.basename(p), "sha256": sha256(p)} for p in patches],
        "sky130_fd_bd_sram_commit": pin("SKY130_FD_BD_SRAM_COMMIT"),
        "openram_pdk_hash": pin("OPENRAM_PDK_HASH"), "pythonhashseed": 0,
        "drc_errors": drc, "drc_max": a.drc_max, "lvs": lvs, "outputs_sha256": files,
    }
    json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=2)
    print(f"gen_macro: {summary['result']} - {name}, {minutes} min, DRC {drc}, LVS {lvs}"
          + (f"; {'; '.join(problems)}" if problems else "") + f" ({out}/summary.json)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
