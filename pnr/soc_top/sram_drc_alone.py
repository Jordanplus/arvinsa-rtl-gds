#!/usr/bin/env python3
"""Magic DRC of the SRAM macro alone: the reference for check_soc.py magic_drc.

usage: sram_drc_alone.py <soc_top LibreLane run> <out dir>

Re-runs LibreLane's Magic.DRC step with the configuration of the run's own Magic.DRC step
(MAGIC_DRC_USE_GDS = true, same Magic, tech file and DRC style), except DESIGN_NAME = the SRAM
cell, on the PDK GDS of the SRAM (MACROS gds of the run). The report is
<out>/step/reports/drc.magic.rpt. It takes about 2.5 minutes and writes about 1.5 GB (the
report and a KLayout marker database). check_soc.py compares every violation inside the
sram0 outline with this report, and this report with the reviewed rule counts in
signoff/waivers/soc_top/sram_magic_drc_baseline.json.
Prints `sram-drc-alone: PASS` / `sram-drc-alone: FAIL`; exit code 0 only on PASS.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MACRO = "sky130_sram_2kbyte_1rw1r_32x512_8"


def main(run, out):
    def fail(msg):
        print(f"sram-drc-alone: FAIL ({msg})")
        return 1

    shutil.rmtree(out, ignore_errors=True)  # only the output directory is removed
    os.makedirs(out)
    steps = glob.glob(os.path.join(run, "*-magic-drc"))
    if len(steps) != 1:
        return fail(f"expected one Magic.DRC step directory in {run}, found {len(steps)}")
    cfg = json.load(open(os.path.join(steps[0], "config.json")))
    gds = cfg["MACROS"][MACRO]["gds"]
    if not cfg.get("MAGIC_DRC_USE_GDS") or len(gds) != 1:
        return fail(f"the run's Magic.DRC must use the GDS (MAGIC_DRC_USE_GDS {cfg.get('MAGIC_DRC_USE_GDS')}) "
                    f"and MACROS {MACRO} must have one gds ({gds})")
    cfg["DESIGN_NAME"] = MACRO
    state = {k: None for k in json.load(open(os.path.join(steps[0], "state_in.json")))}
    state["gds"], state["metrics"] = gds[0], {}
    cfg_p, st_p = os.path.join(out, "config.json"), os.path.join(out, "state_in.json")
    json.dump(cfg, open(cfg_p, "w"), indent=1)
    json.dump(state, open(st_p, "w"), indent=1)
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
    env = dict(os.environ)
    if shutil.which("nix-shell") is None:
        env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    log = os.path.join(out, "run.log")
    cmd = f"python3 -m librelane.steps run --id Magic.DRC -c '{cfg_p}' -i '{st_p}' -o '{os.path.join(out, 'step')}'"
    with open(log, "w") as f:
        f.write(f"$ (cd {ll_dir} && nix-shell --run {cmd!r})\n")
        f.flush()
        rc = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
    rpt = os.path.join(out, "step", "reports", "drc.magic.rpt")
    if rc != 0 or not os.path.isfile(rpt):
        return fail(f"Magic.DRC exit {rc}, report {'present' if os.path.isfile(rpt) else 'missing'}; see {log}")
    print(f"sram-drc-alone: PASS ({rpt})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])))
