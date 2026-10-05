#!/usr/bin/env python3
"""Extract the SRAM macro's GDS with Magic into a SPICE netlist with wire capacitances.

usage: extract_sram.py [<out_dir>]      (default runs/sram_extract/)

Runs Magic from LibreLane's nix-shell (LIBRELANE_DIR, default .tools/librelane) with PDK_ROOT set:
without PDK_ROOT the magicrc cannot find the tech file and Magic still exits 0 with no output
(skill openram-macro-characterization rule 8), so the result is checked, not the exit code.
Capacitance and coupling capacitance are extracted, resistance is not (ADR-0010). Takes about
26 minutes and 1.4 GB for the 2 KB macro.
Writes <out_dir>/<macro>.spice and <out_dir>/extract.log; prints `extract_sram: PASS ...` when the
netlist defines the macro subckt with the 16384 bitcells and the capacitors, else FAIL.
"""
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sramchar as sc  # noqa: E402

GDS = os.path.join(sc.PDK_ROOT, "sky130A", "libs.ref", "sky130_sram_macros", "gds", sc.MACRO + ".gds")
MAGICRC = os.path.join(sc.PDK_ROOT, "sky130A", "libs.tech", "magic", "sky130A.magicrc")


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(sc.ROOT, "runs", "sram_extract"))
    ext = os.path.join(out, "ext")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(ext)
    spice = os.path.join(out, sc.MACRO + ".spice")
    tcl = os.path.join(out, "extract.tcl")
    open(tcl, "w").write("\n".join([
        "gds readonly true", "gds rescale false", f"gds read {GDS}", f"load {sc.MACRO}", f"cd {ext}",
        "select top cell", "extract do capacitance", "extract do coupling", "extract no resistance",
        "extract all", "ext2spice lvs", "ext2spice cthresh 0.01", f"ext2spice -o {spice}",
        'puts "EXTRACT_DONE"', "quit -noprompt", ""]))
    ll_dir = os.environ.get("LIBRELANE_DIR", os.path.join(sc.ROOT, ".tools", "librelane"))
    env = dict(os.environ, PDK_ROOT=sc.PDK_ROOT)
    if shutil.which("nix-shell") is None:
        env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    cmd = f"magic -dnull -noconsole -rcfile '{MAGICRC}' '{tcl}'"
    log = os.path.join(out, "extract.log")
    with open(log, "w") as f:
        f.write(f"$ (cd {ll_dir} && PDK_ROOT={sc.PDK_ROOT} nix-shell --run {cmd!r})\n")
        f.flush()
        rc = subprocess.run(["nix-shell", "--run", cmd], cwd=ll_dir, env=env, stdout=f,
                            stderr=subprocess.STDOUT).returncode
    problems = []
    text = open(log, errors="replace").read()
    if "EXTRACT_DONE" not in text:
        problems.append("Magic did not reach the end of the script")
    if not os.path.isfile(spice):
        problems.append("no netlist written")
    else:
        net = open(spice, errors="replace").read()
        if not re.search(rf"^\.subckt {sc.MACRO}\s", net, re.M):
            problems.append(f"no .subckt {sc.MACRO}")
        joined = re.sub(r"\n\+", " ", net)       # continuation lines
        cells = len(re.findall(rf"^X\S* .* {sc.BITCELL}\s*$", joined, re.M))
        caps = len(re.findall(r"^C", net, re.M))
        if cells != sc.ROWS * sc.COLS:
            problems.append(f"{cells} bitcell instances, expected {sc.ROWS * sc.COLS}")
        if caps < 10000:
            problems.append(f"only {caps} capacitors")
    if rc != 0 or problems:
        print(f"extract_sram: FAIL (Magic exit {rc}; {'; '.join(problems) or 'see log'}; {log})")
        return 1
    print(f"extract_sram: PASS {spice} ({cells} bitcells, {caps} capacitors, sha256 {sc.sha256(spice)[:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
