#!/usr/bin/env python3
"""Estimate the standard-cell area of soc_top from the hardened PicoRV32 (Phase 2, DIE_AREA input).

usage: soc_area_estimate.py [<LibreLane run dir of make harden-core>]   (default runs/picorv32_core)

Synthesizes two designs with the same local Yosys recipe and the sky130_fd_sc_hd TT liberty:
  cpu : third_party/picorv32/picorv32.v, top picorv32, SYNTH_PARAMETERS of pnr/picorv32_core/config.json
  soc : rtl/rtl.f, top soc_top, SRAM as blackbox (its area is not counted)
recipe: synth -flatten; dfflibmap -liberty; abc -liberty; opt_clean; stat -liberty
The ratio soc/cpu of these two areas is applied to the stdcell area that LibreLane reported for the
hardened core (design__instance__area__stdcell, after placement, CTS, resizing and routing), which
gives the expected stdcell area of soc_top after the same flow. This is an estimate (Phase 3 measures
it); the ratio assumes the peripherals grow during placement and routing like the core does.
Output: a table, plus runs/soc_area_estimate/estimate.json. Python stdlib only; needs local yosys.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "runs", "soc_area_estimate")
SRAM_BB = "ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/sky130_sram_2kbyte_1rw1r_32x512_8.bb.v"
LIB_REL = "libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"


def chip_area(log):
    m = re.findall(r"Chip area for (?:top )?module '\\?(\w+)': ([0-9.]+)", log)
    if not m:
        raise RuntimeError("no 'Chip area' line in the Yosys log")
    return float(m[-1][1])


def yosys(name, script):
    os.makedirs(OUT, exist_ok=True)
    ys, log = os.path.join(OUT, f"{name}.ys"), os.path.join(OUT, f"{name}.log")
    open(ys, "w").write(script)
    with open(log, "w") as f:
        subprocess.run(["yosys", "-s", ys], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)
    return chip_area(open(log).read())


def main(run_dir):
    if not os.path.isfile(os.path.join(run_dir, "final", "metrics.json")):
        print(f"soc-area: FAIL - {run_dir}/final/metrics.json not found; run make harden-core first")
        return 1
    metrics = json.load(open(os.path.join(run_dir, "final", "metrics.json")))
    resolved = json.load(open(os.path.join(run_dir, "resolved.json")))
    lib = os.path.join(resolved["PDK_ROOT"], resolved["PDK"], LIB_REL)
    config = json.load(open(os.path.join(ROOT, "pnr", "picorv32_core", "config.json")))
    chparam = " ".join(f"-set {p.split('=', 1)[0]} {p.split('=', 1)[1]}" for p in config["SYNTH_PARAMETERS"])
    mapping = (f"dfflibmap -liberty {lib}\nabc -liberty {lib}\nopt_clean\n"
               f"tee -o {OUT}/{{name}}.stat.txt stat -liberty {lib}\n")

    cpu_script = (f"read_verilog -sv third_party/picorv32/picorv32.v\nchparam {chparam} picorv32\n"
                  "synth -top picorv32 -flatten\n" + mapping.format(name="cpu"))
    incs, files = [], []
    for line in open(os.path.join(ROOT, "rtl", "rtl.f")):
        line = line.strip()
        if line.startswith("+incdir+"):
            incs.append("-I" + line[len("+incdir+"):])
        elif line:
            files.append(line)
    soc_script = "".join(f"read_verilog {' '.join(incs)} {f}\n" for f in files)
    soc_script += f"read_verilog -lib {SRAM_BB}\nsynth -top soc_top -flatten\n" + mapping.format(name="soc")

    cpu, soc = yosys("cpu", cpu_script), yosys("soc", soc_script)
    hardened = metrics["design__instance__area__stdcell"]
    est = hardened * soc / cpu
    rows = [
        ("Yosys area, picorv32 alone (um^2)", cpu),
        ("Yosys area, soc_top without SRAM (um^2)", soc),
        ("ratio soc/cpu", soc / cpu),
        ("LibreLane picorv32 stdcell area after PnR (um^2)", hardened),
        ("estimated soc_top stdcell area after PnR (um^2)", est),
    ]
    for k, v in rows:
        print(f"  {k:52s} {v:12.3f}")
    json.dump({k: v for k, v in rows} | {"liberty": lib, "run": run_dir},
              open(os.path.join(OUT, "estimate.json"), "w"), indent=2)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 2:
        print("usage: soc_area_estimate.py [<LibreLane run dir of make harden-core>]   (default runs/picorv32_core)")
        sys.exit(2)
    sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else os.path.join(ROOT, "runs", "picorv32_core")))
