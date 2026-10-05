#!/usr/bin/env python3
"""Input checks before `make harden-soc` runs LibreLane.

usage: check_inputs.py [--cpu picorv32|hazard3] [--resolved <run>/resolved.json] [--config F] [--char-dir D] [--lef F]
       (--config/--char-dir/--lef replace the repo files; used by pnr/soc_top/neg_pnr.py)
--cpu picks the CPU of soc_top (default picorv32; hazard3: Phase 5, ADR-0011), and with it the config
and RTL file list: picorv32 pnr/soc_top/config.json and rtl/rtl.f, hazard3
pnr/soc_top/config_hazard3.json and rtl/rtl_hazard3.f (--config replaces the config of that CPU).

Checks:
  rtl_files   the config's VERILOG_FILES == the source files of the CPU's RTL file list, and
              VERILOG_INCLUDE_DIRS == its +incdir+ entries (the flow hardens the same RTL that the
              simulations use)
  cpu_config  the two configs (config.json, config_hazard3.json; the one of --cpu replaced by --config)
              have the same value for every key except VERILOG_FILES, VERILOG_INCLUDE_DIRS,
              VERILOG_DEFINES and the comments (keys starting with //), and VERILOG_DEFINES is unset in
              config.json and exactly SOC_CPU_HAZARD3 in config_hazard3.json: the Hazard3 run uses the
              flow settings of the PicoRV32 run (Phase 5 exit criterion "flow 設定只需改 design 層").
              Checked for both CPUs, so a setting changed in one config only FAILs the next harden of
              either.
  char_lib    the five ip/sram/.../char/<macro>__<pvt>.lib are what ip/sram/char/gen_char_lib.py makes
              from char/char.json (the ngspice characterization, ADR-0010) and the PDK TT .lib of the
              pinned PDK (${PDK_ROOT:-~/.ciel}/sky130A, version SKY130_PDK_HASH in env/versions.mk);
              the char directory holds only those, char.json and confirm.json
  char_values ip/sram/char/check_char_lib.py: every number of those .lib recomputed independently from
              char.json, char.json made from the pinned PDK netlist and settings, and confirm.json
              (every lane simulated at the .lib values) passed (gen_char_lib.py --check only compares
              the program with itself; Phase 3.5 review)
  antenna_lef ip/sram/.../<macro>.lef is what gen_antenna_lef.py makes from the PDK LEF and SPICE
  macro_lib   config.json MACROS lib maps each PVT of the STA corners ("*_<pvt>") to its own char .lib
              and nothing else, and uses that LEF
  other_libs  config.json LIB maps each PVT to its sky130_fd_sc_hd .lib only, and EXTRA_LIBS is unset:
              LibreLane reads both into every STA corner, so another SRAM .lib there would be timed
              next to (or instead of) the characterized one (Phase 3.5 review)
With --resolved, also checks that the run used these VERILOG_FILES, VERILOG_INCLUDE_DIRS and
VERILOG_DEFINES, these .lib (MACROS, and LIB = the sky130_fd_sc_hd .lib of the pinned PDK, no
EXTRA_LIBS) and that LEF (resolved.json paths are absolute).
Prints `soc-inputs: PASS` / `soc-inputs: FAIL`; exit code 0 only on PASS. Python stdlib only.
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# CPU -> (config, RTL file list, VERILOG_DEFINES)
CPUS = {"picorv32": (os.path.join(ROOT, "pnr", "soc_top", "config.json"), os.path.join(ROOT, "rtl", "rtl.f"), []),
        "hazard3": (os.path.join(ROOT, "pnr", "soc_top", "config_hazard3.json"),
                    os.path.join(ROOT, "rtl", "rtl_hazard3.f"), ["SOC_CPU_HAZARD3"])}
CPU_KEYS = ("VERILOG_FILES", "VERILOG_INCLUDE_DIRS", "VERILOG_DEFINES")
MACRO = "sky130_sram_2kbyte_1rw1r_32x512_8"
IP = os.path.join(ROOT, "ip", "sram", MACRO)
CHAR_DIR = os.path.join(IP, "char")
PVTS = ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95", "ss_n40C_1v60", "ff_100C_1v95")


def char_lib(d, pvt):
    return os.path.join(d, f"{MACRO}__{pvt}.lib")
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpu", default="picorv32", choices=sorted(CPUS))
    ap.add_argument("--resolved")
    ap.add_argument("--config")
    ap.add_argument("--char-dir", default=CHAR_DIR)
    ap.add_argument("--lef", default=ANT_LEF)
    args = ap.parse_args(argv)
    rows = []

    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    config, rtl_f, defines = CPUS[args.cpu]
    configs = {c: json.load(open(args.config if c == args.cpu and args.config else CPUS[c][0], encoding="utf8"))
               for c in CPUS}
    cfg = configs[args.cpu]
    inc, files = [], []
    for line in open(rtl_f, encoding="utf8"):
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
        f"{len(have_files)} files and {len(have_inc)} include dir(s) in {os.path.basename(config)} vs {len(files)} and {len(inc)} "
        f"in {os.path.relpath(rtl_f, ROOT)}"
        + ("" if sorted(have_files) == sorted(files) else
           f"; only in config {sorted(set(have_files) - set(files))}, only in the file list {sorted(set(files) - set(have_files))}"))
    pico, h3 = configs["picorv32"], configs["hazard3"]
    differ = sorted(k for k in set(pico) | set(h3) if not k.startswith("//") and k not in CPU_KEYS and pico.get(k) != h3.get(k))
    bad_def = [f"{c} VERILOG_DEFINES = {configs[c].get('VERILOG_DEFINES')}" for c in CPUS
               if (configs[c].get("VERILOG_DEFINES") or []) != CPUS[c][2]]
    row("cpu_config", not differ and not bad_def,
        "config.json and config_hazard3.json differ only in " + ", ".join(CPU_KEYS) + " (and comments)"
        if not differ and not bad_def else "; ".join(([f"other keys differ: {differ}"] if differ else []) + bad_def))

    pdk_lib = os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), pin("PDK"),
                           "libs.ref", "sky130_sram_macros", "lib", f"{MACRO}_TT_1p8V_25C.lib")
    real = os.path.realpath(pdk_lib)
    if f"/versions/{pin('SKY130_PDK_HASH')}/" not in real or not os.path.isfile(real):
        row("char_lib", False, f"PDK .lib {pdk_lib} missing or not PDK version {pin('SKY130_PDK_HASH')[:12]}")
    else:
        cp = subprocess.run([sys.executable, os.path.join(ROOT, "ip", "sram", "char", "gen_char_lib.py"),
                             os.path.join(args.char_dir, "char.json"), real, args.char_dir, "--check"],
                            capture_output=True, text=True)
        extra = sorted(set(os.listdir(args.char_dir)) - {"char.json", "confirm.json"} - {os.path.basename(char_lib("", p)) for p in PVTS}) \
            if os.path.isdir(args.char_dir) else []
        row("char_lib", cp.returncode == 0 and not extra,
            (cp.stdout.strip() or cp.stderr.strip()) + (f"; unexpected files {extra}" if extra else ""))
        cp = subprocess.run([sys.executable, os.path.join(ROOT, "ip", "sram", "char", "check_char_lib.py"),
                             os.path.join(args.char_dir, "char.json"), args.char_dir], capture_output=True, text=True)
        bad = re.findall(r"^  \[FAIL\] ([^\n]*)", cp.stdout, re.M)
        row("char_values", cp.returncode == 0 and cp.stdout.rstrip().endswith("check_char_lib: PASS"),
            "check_char_lib.py PASS (values recomputed independently, provenance, confirmation simulations)"
            if cp.returncode == 0 else f"check_char_lib.py FAIL: {'; '.join(bad[:2]) or cp.stderr.strip()[-200:]}")

    sram_ref = os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), pin("PDK"), "libs.ref", "sky130_sram_macros")
    lef, spice = (os.path.realpath(os.path.join(sram_ref, d, f"{MACRO}.{e}")) for d, e in (("lef", "lef"), ("spice", "spice")))
    if not (os.path.isfile(lef) and os.path.isfile(spice)):
        row("antenna_lef", False, f"PDK LEF/SPICE missing under {sram_ref}")
    else:
        cp = subprocess.run([sys.executable, os.path.join(IP, "gen_antenna_lef.py"), lef, spice, args.lef, "--check"],
                            capture_output=True, text=True)
        row("antenna_lef", cp.returncode == 0, cp.stdout.strip() or cp.stderr.strip())

    mac = cfg.get("MACROS", {}).get(MACRO, {})
    want = {f"*_{p}": [f"dir::ip/sram/{MACRO}/char/{MACRO}__{p}.lib"] for p in PVTS}
    want_lef = ["dir::ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/sky130_sram_2kbyte_1rw1r_32x512_8.lef"]
    row("macro_lib", mac.get("lib") == want and mac.get("lef") == want_lef,
        f"MACROS {MACRO} lib = {mac.get('lib')}, lef = {mac.get('lef')}")
    want_std = {f"*_{p}": [f"pdk_dir::libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{p}.lib"] for p in PVTS}
    row("other_libs", cfg.get("LIB") == want_std and not cfg.get("EXTRA_LIBS"),
        f"LIB = the sky130_fd_sc_hd .lib of each PVT, EXTRA_LIBS unset" if cfg.get("LIB") == want_std and not cfg.get("EXTRA_LIBS")
        else f"LIB = {cfg.get('LIB')}, EXTRA_LIBS = {cfg.get('EXTRA_LIBS')}")

    if args.resolved:
        res = json.load(open(args.resolved, encoding="utf8"))
        rfiles = [os.path.normpath(p) for p in res.get("VERILOG_FILES", [])]
        rlib = res.get("MACROS", {}).get(MACRO, {}).get("lib", {})
        rlef = res.get("MACROS", {}).get(MACRO, {}).get("lef", [])
        rstd = res.get("LIB") or {}
        std_ok = set(rstd) == {f"*_{p}" for p in PVTS} and all(
            len(rstd[f"*_{p}"]) == 1 and rstd[f"*_{p}"][0].endswith(f"/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{p}.lib")
            and f"/versions/{pin('SKY130_PDK_HASH')}/" in os.path.realpath(rstd[f"*_{p}"][0]) for p in PVTS)
        rinc = [os.path.normpath(p) for p in res.get("VERILOG_INCLUDE_DIRS") or []]
        rdef = res.get("VERILOG_DEFINES") or []
        ok = sorted(rfiles) == sorted(files) and sorted(rinc) == sorted(inc) and rdef == defines \
            and rlib == {f"*_{p}": [char_lib(CHAR_DIR, p)] for p in PVTS} \
            and rlef == [ANT_LEF] and std_ok and not res.get("EXTRA_LIBS")
        row("resolved", ok, f"run used {len(rfiles)} RTL files, {len(rinc)} include dir(s), defines {rdef}, MACROS lib {rlib}, lef {rlef}"
            + ("" if std_ok and not res.get("EXTRA_LIBS") else f"; LIB {rstd}, EXTRA_LIBS {res.get('EXTRA_LIBS')}"))

    ok = all(rows) and rows
    print(f"soc-inputs: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
