#!/usr/bin/env python3
"""Input checks before `make harden-soc` runs LibreLane.

usage: check_inputs.py [--cpu picorv32|hazard3] [--resolved <run>/resolved.json] [--config F] [--char-dir D] [--lef F]
                       [--openram D] [--sim-model F]
       (--config/--char-dir/--lef/--openram/--sim-model replace the repo files; used by pnr/soc_top/neg_pnr.py)
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
  macro_source the OpenRAM outputs in ip/sram/<macro>/openram/ (GDS, LEF, SPICE, Verilog, TT .lib) have the
              sha256 that summary.json recorded when make openram-macro made them (Phase 6, ADR-0018;
              the TT .lib since the Phase 6 independent review, H3),
              and upstream/<macro>.v is the same file as openram/<macro>.v; the SPICE netlist may instead have
              the spice_content_sha256 that summary.json recorded (same subcircuits in another order, the netlist
              the .lib was characterized from; ADR-0018 decision 17)
  sim_model   sim/<macro>.v is what ip/sram/gen_sim_model.py makes from upstream/<macro>.v
  macro_views scripts/check_macro_views.py on the views the flow reads: the antenna LEF, the five char
              .lib, the Verilog model, the SPICE netlist and the GDS (names, pins and directions, .lib
              numbers and area, LEF SIZE = GDS box, LEF pin RECTs at the GDS pin texts, GDS routing metal
              inside the LEF OBS and pins; CLAUDE.md rule 12)
  lib_template openram/<macro>_TT_template.lib is what ip/sram/openram/lib_template.py makes from the OpenRAM
              TT .lib and the PDK macro's TT .lib: the template's pins, capacitances, area and port 1
              timing go into the five char .lib unchecked otherwise (Phase 6 independent review H3: input
              capacitances / 10 in the template passed every row)
  char_lib    the five ip/sram/.../char/<macro>__<pvt>.lib are what ip/sram/char/gen_char_lib.py makes
              from char/char.json (the ngspice characterization, ADR-0010), the .lib template
              openram/<macro>_TT_template.lib and char/power.json (ADR-0018 decisions 10-15); the char
              directory holds only those, char.json, confirm.json and power.json
  char_values ip/sram/char/check_char_lib.py: every number of those .lib recomputed independently from
              char.json, char.json made from the pinned PDK netlist and settings, and confirm.json
              (every lane simulated at the .lib values) passed (gen_char_lib.py --check only compares
              the program with itself; Phase 3.5 review)
  antenna_lef ip/sram/<macro>/<macro>.lef is what gen_antenna_lef.py makes from openram/<macro>.lef and .sp
  macro_lib   config.json MACROS lib maps each PVT of the STA corners ("*_<pvt>") to its own char .lib
              and nothing else, and uses that LEF and openram/<macro>.gds
  other_libs  config.json LIB maps each PVT to its sky130_fd_sc_hd .lib only, and EXTRA_LIBS is unset:
              LibreLane reads both into every STA corner, so another SRAM .lib there would be timed
              next to (or instead of) the characterized one (Phase 3.5 review)
  weak_cells  pnr/check_weak_cells.py on the CPU's config: no cell the resizer may use drives one
              buffer above the slew limit of a design-repair step in a resizer corner (otherwise
              repair_design can insert buffers at one point forever; Phase 5, a2111oi_1,
              docs/notes/repair_design_loop.md)
With --resolved, also checks that the run used these VERILOG_FILES, VERILOG_INCLUDE_DIRS and
VERILOG_DEFINES, these .lib (MACROS, and LIB = the sky130_fd_sc_hd .lib of the pinned PDK, no
EXTRA_LIBS) and that LEF (resolved.json paths are absolute), and runs check_weak_cells.py on
resolved.json (weak_cells_run: the exclusions, corners, margins and SDC the run really used).
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
MACRO = "arv_sram_2kbyte_1rw1r_32x512_8"   # OpenRAM self-generated (Phase 6, ADR-0018)
IP = os.path.join(ROOT, "ip", "sram", MACRO)
OPENRAM = os.path.join(IP, "openram")
CHAR_DIR = os.path.join(IP, "char")
GEN_ANTENNA_LEF = os.path.join(ROOT, "ip", "sram", "sky130_sram_2kbyte_1rw1r_32x512_8", "gen_antenna_lef.py")
PDK_SRAM_TT = "libs.ref/sky130_sram_macros/lib/sky130_sram_2kbyte_1rw1r_32x512_8_TT_1p8V_25C.lib"   # = Makefile SRAM_PDK_LIB
sys.path.insert(0, os.path.join(ROOT, "ip", "sram", "openram"))
import lib_template  # noqa: E402
# the characterization scripts pick the macro and its netlist from these (Makefile OR_SRAM_ENV)
CHAR_ENV = dict(os.environ, SRAM_CHAR_MACRO=MACRO, SRAM_CHAR_NETLIST=os.path.join(OPENRAM, MACRO + ".sp"))
PVTS = ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95", "ss_n40C_1v60", "ff_100C_1v95")


def char_lib(d, pvt):
    return os.path.join(d, f"{MACRO}__{pvt}.lib")
ANT_LEF = os.path.join(IP, f"{MACRO}.lef")
WEAK_CELLS = os.path.join(ROOT, "pnr", "check_weak_cells.py")


def pin(name):
    for line in open(os.path.join(ROOT, "env", "versions.mk"), encoding="utf8"):
        m = re.match(rf"^{name}\s*=\s*(\S+)", line)
        if m:
            return m.group(1)
    raise KeyError(name)


def sha256(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def spice_content_sha256(path):
    """sha256 of a SPICE netlist's sorted .subckt blocks (exact text) and sorted non-comment lines outside them: the
    same for the same circuit written in another order or with other comments (same definition as gen_macro.py,
    written again here so the check does not import the generator)."""
    import hashlib
    text = open(path, encoding="utf-8", errors="replace").read()
    pat = re.compile(r"^\.subckt\s.*?^\.ends\b[^\n]*", re.M | re.S | re.I)
    blocks = sorted(m.group(0) for m in pat.finditer(text))
    rest = sorted(ln for ln in pat.sub("", text).splitlines() if ln.strip() and not ln.lstrip().startswith("*"))
    return hashlib.sha256(("\0".join(blocks) + "\1" + "\0".join(rest)).encode()).hexdigest()


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
    ap.add_argument("--openram", default=OPENRAM)
    ap.add_argument("--sim-model", default=os.path.join(IP, "sim", f"{MACRO}.v"))
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

    try:
        summ = json.load(open(os.path.join(args.openram, "summary.json"), encoding="utf8"))
        want_sha = summ["outputs_sha256"]
        files = {"gds": f"{MACRO}.gds", "lef": f"{MACRO}.lef", "sp": f"{MACRO}.sp", "v": f"{MACRO}.v",
                 "tt_lib": f"{MACRO}_TT_1p8V_25C.lib"}
        bad_sha = [e for e, f in files.items() if sha256(os.path.join(args.openram, f)) != want_sha.get(f)]
        # the netlist may be the earlier run's that the .lib was characterized from, when it is the same circuit
        # (same subcircuits, word for word; only order and comments differ; ADR-0018 decision 17)
        sp_same = "sp" in bad_sha and summ.get("spice_content_sha256") == spice_content_sha256(
            os.path.join(args.openram, f"{MACRO}.sp"))
        if sp_same:
            bad_sha.remove("sp")
        same_v = sha256(os.path.join(IP, "upstream", f"{MACRO}.v")) == sha256(os.path.join(args.openram, f"{MACRO}.v"))
        row("macro_source", not bad_sha and same_v,
            "openram/ GDS, LEF, SPICE, Verilog and TT .lib match summary.json"
            + (" (SPICE: same subcircuits, other order/comments)" if sp_same else "") + "; upstream/ model = openram/ model"
            if not bad_sha and same_v
            else f"sha256 differs from summary.json: {bad_sha}" + ("" if same_v else "; upstream/ model differs from openram/"))
    except (OSError, KeyError, ValueError) as e:
        row("macro_source", False, f"cannot read {args.openram}: {e}")
    upstream_v, sim_v = os.path.join(IP, "upstream", f"{MACRO}.v"), args.sim_model
    cp = subprocess.run([sys.executable, os.path.join(ROOT, "ip", "sram", "gen_sim_model.py"), upstream_v, sim_v, "--check"],
                        capture_output=True, text=True)
    row("sim_model", cp.returncode == 0, cp.stdout.strip() or cp.stderr.strip()[-200:])
    cp = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_macro_views.py"), "--name", MACRO, "--lef", args.lef]
                        + [x for p in PVTS for x in ("--lib", char_lib(args.char_dir, p))]
                        + ["--verilog", upstream_v, "--spice", os.path.join(args.openram, f"{MACRO}.sp"),
                           "--gds", os.path.join(args.openram, f"{MACRO}.gds")], capture_output=True, text=True)
    row("macro_views", cp.returncode == 0, (cp.stdout.strip() or cp.stderr.strip())[-300:])

    template = os.path.join(args.openram, f"{MACRO}_TT_template.lib")
    pdk_dir = os.path.join(os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel")), pin("PDK"))
    try:
        made, probs = lib_template.make(open(os.path.join(args.openram, f"{MACRO}_TT_1p8V_25C.lib"), encoding="utf8").read(),
                                        open(os.path.join(pdk_dir, PDK_SRAM_TT), encoding="utf8").read())
        same = made is not None and made == open(template, encoding="utf8").read()
        row("lib_template", same, "openram/ TT template = lib_template.py(OpenRAM TT .lib, PDK macro TT .lib)" if same
            else "; ".join(probs) or "the template differs from what lib_template.py makes (edited by hand, or stale)")
    except OSError as e:
        row("lib_template", False, f"cannot read: {e}")
    power = os.path.join(args.char_dir, "power.json")
    cp = subprocess.run([sys.executable, os.path.join(ROOT, "ip", "sram", "char", "gen_char_lib.py"),
                         os.path.join(args.char_dir, "char.json"), template, args.char_dir, "--power", power, "--check"],
                        capture_output=True, text=True, env=CHAR_ENV)
    extra = sorted(set(os.listdir(args.char_dir)) - {"char.json", "confirm.json", "power.json"}
                   - {os.path.basename(char_lib("", p)) for p in PVTS}) if os.path.isdir(args.char_dir) else []
    row("char_lib", cp.returncode == 0 and not extra,
        (cp.stdout.strip() or cp.stderr.strip()) + (f"; unexpected files {extra}" if extra else ""))
    cp = subprocess.run([sys.executable, os.path.join(ROOT, "ip", "sram", "char", "check_char_lib.py"),
                         os.path.join(args.char_dir, "char.json"), args.char_dir], capture_output=True, text=True, env=CHAR_ENV)
    bad = re.findall(r"^  \[FAIL\] ([^\n]*)", cp.stdout, re.M)
    row("char_values", cp.returncode == 0 and cp.stdout.rstrip().endswith("check_char_lib: PASS"),
        "check_char_lib.py PASS (values recomputed independently, provenance, confirmation simulations)"
        if cp.returncode == 0 else f"check_char_lib.py FAIL: {'; '.join(bad[:2]) or cp.stderr.strip()[-200:]}")

    lef, spice = os.path.join(args.openram, f"{MACRO}.lef"), os.path.join(args.openram, f"{MACRO}.sp")
    cp = subprocess.run([sys.executable, GEN_ANTENNA_LEF, lef, spice, args.lef, "--check"], capture_output=True, text=True)
    row("antenna_lef", cp.returncode == 0, cp.stdout.strip() or cp.stderr.strip())

    mac = cfg.get("MACROS", {}).get(MACRO, {})
    want = {f"*_{p}": [f"dir::ip/sram/{MACRO}/char/{MACRO}__{p}.lib"] for p in PVTS}
    want_lef = [f"dir::ip/sram/{MACRO}/{MACRO}.lef"]
    want_gds = [f"dir::ip/sram/{MACRO}/openram/{MACRO}.gds"]
    row("macro_lib", mac.get("lib") == want and mac.get("lef") == want_lef and mac.get("gds") == want_gds,
        f"MACROS {MACRO} lib = {mac.get('lib')}, lef = {mac.get('lef')}, gds = {mac.get('gds')}")
    want_std = {f"*_{p}": [f"pdk_dir::libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__{p}.lib"] for p in PVTS}
    row("other_libs", cfg.get("LIB") == want_std and not cfg.get("EXTRA_LIBS"),
        f"LIB = the sky130_fd_sc_hd .lib of each PVT, EXTRA_LIBS unset" if cfg.get("LIB") == want_std and not cfg.get("EXTRA_LIBS")
        else f"LIB = {cfg.get('LIB')}, EXTRA_LIBS = {cfg.get('EXTRA_LIBS')}")

    def weak_cells(name, cfg_path):
        cp = subprocess.run([sys.executable, WEAK_CELLS, cfg_path, "--pdk-dir", pdk_dir], capture_output=True, text=True)
        bad = re.findall(r"^  \[FAIL\] ([^\n]*)", cp.stdout, re.M)
        row(name, cp.returncode == 0 and cp.stdout.rstrip().endswith("weak-cells: PASS"),
            f"check_weak_cells.py PASS on {os.path.basename(cfg_path)} ({cp.stdout.count(chr(10) + '  [PASS] ') + cp.stdout.startswith('  [PASS] ')} step x PVT rows)"
            if cp.returncode == 0 else f"check_weak_cells.py FAIL: {'; '.join(bad) or cp.stderr.strip()[-300:]}")

    weak_cells("weak_cells", args.config or config)

    if args.resolved:
        weak_cells("weak_cells_run", args.resolved)
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
