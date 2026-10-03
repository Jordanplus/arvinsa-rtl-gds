#!/usr/bin/env python3
"""Input checks before `make harden-soc` runs LibreLane.

usage: check_inputs.py [--resolved <run>/resolved.json]

Checks:
  rtl_files   config.json VERILOG_FILES == the source files of rtl/rtl.f, and VERILOG_INCLUDE_DIRS ==
              its +incdir+ entries (the flow hardens the same RTL that the simulations use)
  padded_lib  ip/sram/.../padded.lib is what gen_padded_lib.py makes from the PDK TT .lib of the
              pinned PDK (${PDK_ROOT:-~/.ciel}/sky130A, version SKY130_PDK_HASH in env/versions.mk)
  antenna_lef ip/sram/.../<macro>.lef is what gen_antenna_lef.py makes from the PDK LEF and SPICE
  macro_lib   config.json MACROS uses padded.lib for every corner ("*") and nothing else, and that LEF
With --resolved, also checks that the run used these VERILOG_FILES, that .lib and that LEF
(resolved.json paths are absolute).
Prints `soc-inputs: PASS` / `soc-inputs: FAIL`; exit code 0 only on PASS. Python stdlib only.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(ROOT, "pnr", "soc_top", "config.json")
RTL_F = os.path.join(ROOT, "rtl", "rtl.f")
MACRO = "sky130_sram_2kbyte_1rw1r_32x512_8"
IP = os.path.join(ROOT, "ip", "sram", MACRO)
PADDED = os.path.join(IP, "padded.lib")
ANT_LEF = os.path.join(IP, f"{MACRO}.lef")


def pin(name):
    for line in open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf8"):
        m = re.match(rf"^{name}\s*=\s*(\S+)", line)
        if m:
            return m.group(1)
    raise KeyError(name)


def dir_path(v):
    """'dir::x' -> absolute path below the repo root (run.sh passes --design-dir = repo root)."""
    return os.path.normpath(os.path.join(ROOT, v[len("dir::"):])) if v.startswith("dir::") else v


def main(argv):
    rows = []

    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    cfg = json.load(open(CONFIG, encoding="utf8"))
    inc, files = [], []
    for line in open(RTL_F, encoding="utf8"):
        s = line.split("//")[0].strip()
        if not s:
            continue
        if s.startswith("+incdir+"):
            inc.append(os.path.normpath(os.path.join(ROOT, s[len("+incdir+"):])))
        else:
            files.append(os.path.normpath(os.path.join(ROOT, s)))
    have_files = [dir_path(v) for v in cfg.get("VERILOG_FILES", [])]
    have_inc = [dir_path(v) for v in cfg.get("VERILOG_INCLUDE_DIRS", [])]
    row("rtl_files", sorted(have_files) == sorted(files) and sorted(have_inc) == sorted(inc),
        f"{len(have_files)} files and {len(have_inc)} include dir(s) in config.json vs {len(files)} and {len(inc)} in rtl/rtl.f"
        + ("" if sorted(have_files) == sorted(files) else
           f"; only in config {sorted(set(have_files) - set(files))}, only in rtl.f {sorted(set(files) - set(have_files))}"))

    pdk_lib = os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), pin("PDK"),
                           "libs.ref", "sky130_sram_macros", "lib", f"{MACRO}_TT_1p8V_25C.lib")
    real = os.path.realpath(pdk_lib)
    if f"/versions/{pin('SKY130_PDK_HASH')}/" not in real or not os.path.isfile(real):
        row("padded_lib", False, f"PDK .lib {pdk_lib} missing or not PDK version {pin('SKY130_PDK_HASH')[:12]}")
    else:
        cp = subprocess.run([sys.executable, os.path.join(IP, "gen_padded_lib.py"), real, PADDED, "--check"],
                            capture_output=True, text=True)
        row("padded_lib", cp.returncode == 0, cp.stdout.strip() or cp.stderr.strip())

    sram_ref = os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), pin("PDK"), "libs.ref", "sky130_sram_macros")
    lef, spice = (os.path.realpath(os.path.join(sram_ref, d, f"{MACRO}.{e}")) for d, e in (("lef", "lef"), ("spice", "spice")))
    if not (os.path.isfile(lef) and os.path.isfile(spice)):
        row("antenna_lef", False, f"PDK LEF/SPICE missing under {sram_ref}")
    else:
        cp = subprocess.run([sys.executable, os.path.join(IP, "gen_antenna_lef.py"), lef, spice, ANT_LEF, "--check"],
                            capture_output=True, text=True)
        row("antenna_lef", cp.returncode == 0, cp.stdout.strip() or cp.stderr.strip())

    mac = cfg.get("MACROS", {}).get(MACRO, {})
    want = {"*": ["dir::ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/padded.lib"]}
    want_lef = ["dir::ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/sky130_sram_2kbyte_1rw1r_32x512_8.lef"]
    row("macro_lib", mac.get("lib") == want and mac.get("lef") == want_lef,
        f"MACROS {MACRO} lib = {mac.get('lib')}, lef = {mac.get('lef')}")

    if "--resolved" in argv:
        res = json.load(open(argv[argv.index("--resolved") + 1], encoding="utf8"))
        rfiles = [os.path.normpath(p) for p in res.get("VERILOG_FILES", [])]
        rlib = res.get("MACROS", {}).get(MACRO, {}).get("lib", {})
        rlef = res.get("MACROS", {}).get(MACRO, {}).get("lef", [])
        ok = sorted(rfiles) == sorted(files) and rlib == {"*": [PADDED]} and rlef == [ANT_LEF]
        row("resolved", ok, f"run used {len(rfiles)} RTL files, MACROS lib {rlib}, lef {rlef}")

    ok = all(rows) and rows
    print(f"soc-inputs: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
