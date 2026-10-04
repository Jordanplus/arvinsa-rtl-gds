#!/usr/bin/env python3
"""make neg-pnr: bug injection into the soc_top flow and its results (project-plan.md §7.3 P01-P12, plus P13-P20).

usage: neg_pnr.py [--run <dir>] [--out <dir>] [--cases P01,P02,...] [-j N]
The run must pass signoff/scripts/run_guard.py (PASS, made from the commit checked out now): the
cases compare against it ("real run: none", golden, metrics).

Each case changes one thing and must FAIL at the expected checker, with the expected message.
A case that FAILs elsewhere, or does not FAIL, makes neg-pnr FAIL. Cases that need a LibreLane
step re-run one step on a copy of that step's saved config and input state
(`python3 -m librelane.steps run`); nothing in <run> is modified. Outputs: runs/neg_pnr/<case>/.

  step re-runs (the real tools on the real layout)
  P01  signoff SDC + set_clock_uncertainty -setup 30  OpenROAD.STAPostPNR -> Checker.SetupViolations
  P02  signoff SDC + set_clock_uncertainty -hold 5    OpenROAD.STAPostPNR -> Checker.HoldViolations
       (P01-P03 start from the run's SIGNOFF_SDC_FILE, so they test the SDC that signoff really uses)
  P03  signoff SDC + set_max_transition 0.05 ns     OpenROAD.STAPostPNR -> Checker.MaxSlewViolations
  P04  sta_extra_corner.tcl with SRAM derate 10      OpenROAD.STAPostPNR -> Checker.SetupViolations
       (proves the derate hook is applied: the SRAM half-cycle path then needs 100 ns)
  P05  final DEF without the grid vias on the SRAM power ring
                                                     Magic.SpiceExtraction -> Netgen.LVS -> Checker.LVS
       (PDN_CONNECT_MACROS_TO_GRID=false was tried first: the grid is identical, because the core
        straps cross the SRAM power ring anyway, and PSM still reports every shape connected)
  P10  final GDS + one 0.05 um wide met2 rectangle   KLayout.DRC -> Checker.KLayoutDRC
                                                     Magic.DRC (full GDS) -> check_soc.py magic_drc
  P11  KLayout GDS + one met2 rectangle (Magic GDS unchanged)
                                                     KLayout.XOR -> Checker.XOR
  checker inputs (the checker on an edited copy of one file; the tool is not re-run)
  P06  SRAM LEF with ANTENNAGATEAREA / 1000         OpenROAD check_antennas on the final DEF: > 0 violations
       (with the flow's LEF: 0; shows the antenna checker sees the nets on SRAM inputs)
  P07  metrics: ir__drop__worst 0.2 V                check_signoff.py [max] row
  P08  final netlist: sram0 csb1 on a floating net   check_soc.py port1_tieoff
  P09  final DEF: sram0 moved by 10 um               check_soc.py placement
  P12  metrics: design__instance__count -10 %        check_signoff.py golden comparison
  P13  signoff SDC without its set_output_delay line OpenROAD.STAPostPNR -> check_soc.py sta_setup
       (unconstrained endpoints, project-plan.md §7.2)
  P14  final netlist: sram0 renamed sram9            check_soc.py macro
  P15  disconnected-pin log: 1 critical pin          check_soc.py disconnected
  P16  config.json: one VERILOG_FILES entry dropped  check_inputs.py rtl_files
  P17  padded.lib: one dout0 delay table edited      check_inputs.py padded_lib
  P18  SRAM LEF: one ANTENNAGATEAREA line dropped    check_inputs.py antenna_lef
  P19  config.json: MACROS lib = the PDK TT .lib     check_inputs.py macro_lib
  P20  resolved.json: MACROS lib = the PDK TT .lib   check_inputs.py --resolved
Prints `neg-pnr: PASS n/n caught` / `neg-pnr: FAIL ...`; exit code 0 only on PASS.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "runs", "neg_pnr")   # --out replaces it
LL_DIR = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
CHECK_SOC = os.path.join(ROOT, "pnr", "soc_top", "check_soc.py")
CHECK_SIGNOFF = os.path.join(ROOT, "signoff", "scripts", "check_signoff.py")
CHECK_INPUTS = os.path.join(ROOT, "pnr", "soc_top", "check_inputs.py")
CONFIG = os.path.join(ROOT, "pnr", "soc_top", "config.json")
SRAM = "sky130_sram_2kbyte_1rw1r_32x512_8"
SRAM_IP = os.path.join(ROOT, "ip", "sram", SRAM)
PDK_TT_LIB = f"pdk_dir::libs.ref/sky130_sram_macros/lib/{SRAM}_TT_1p8V_25C.lib"
LIMITS = os.path.join(ROOT, "signoff", "limits", "soc_top.toml")
GOLDEN = os.path.join(ROOT, "signoff", "golden", "soc_top", "metrics.json")
sys.path.insert(0, os.path.join(ROOT, "signoff", "scripts"))
from run_guard import guard  # noqa: E402


def nix(cmd, log):
    env = dict(os.environ)
    if shutil.which("nix-shell") is None:
        env["PATH"] = "/nix/var/nix/profiles/default/bin" + os.pathsep + env.get("PATH", "")
    with open(log, "a", encoding="utf8") as f:
        f.write(f"$ nix-shell --run {cmd!r}\n")
        f.flush()
        return subprocess.run(["nix-shell", "--run", cmd], cwd=LL_DIR, env=env, stdout=f,
                              stderr=subprocess.STDOUT).returncode


def step_dir(run, step_id):
    """The run's step directory for a LibreLane step id (last one if the step ran more than once)."""
    name = step_id.lower().replace(".", "-")
    pat = re.compile(r"\d+-" + re.escape(name) + r"(-\d+)?$")   # a repeated step gets a -1, -2, ... suffix
    dirs = sorted((d for d in glob.glob(os.path.join(run, "[0-9]*")) if pat.fullmatch(os.path.basename(d))),
                  key=lambda d: int(os.path.basename(d).split("-")[0]))
    if not dirs:
        raise FileNotFoundError(f"no step directory for {step_id} in {run}")
    return dirs[-1]


def run_step(step_id, config, state_in, out, log):
    return nix(f"python3 -m librelane.steps run --id {step_id} -c '{config}' -i '{state_in}' -o '{out}'", log)


def rerun(run, case_dir, step_id, checker_id, edit_config=None, edit_state=None):
    """Re-run step_id with an edited config/state, then checker_id on its output state.
    Returns (checker exit code, text of the log)."""
    src = step_dir(run, step_id)
    cfg = json.load(open(os.path.join(src, "config.json")))
    state = json.load(open(os.path.join(src, "state_in.json")))
    if edit_config:
        edit_config(cfg)
    if edit_state:
        edit_state(state)
    cfg_p, st_p = os.path.join(case_dir, "step_config.json"), os.path.join(case_dir, "step_state_in.json")
    json.dump(cfg, open(cfg_p, "w"), indent=1)
    json.dump(state, open(st_p, "w"), indent=1)
    log = os.path.join(case_dir, "run.log")
    rc = run_step(step_id, cfg_p, st_p, os.path.join(case_dir, "step"), log)
    if rc != 0:
        return None, open(log, errors="replace").read()
    chk = step_dir(run, checker_id)
    rc2 = run_step(checker_id, os.path.join(chk, "config.json"), os.path.join(case_dir, "step", "state_out.json"),
                   os.path.join(case_dir, "checker"), log)
    return rc2, open(log, errors="replace").read()


def rerun_chain(run, case_dir, step_ids, checker_id, edit_state=None):
    """Re-run several steps in order (the first with an edited input state, each next one on the
    previous output state), then checker_id. Returns (checker exit code, log text)."""
    log = os.path.join(case_dir, "run.log")
    state_p = None
    for i, step_id in enumerate(step_ids):
        src = step_dir(run, step_id)
        if i == 0:
            state = json.load(open(os.path.join(src, "state_in.json")))
            if edit_state:
                edit_state(state)
            state_p = os.path.join(case_dir, "step_state_in.json")
            json.dump(state, open(state_p, "w"), indent=1)
        out = os.path.join(case_dir, f"step{i}")
        if run_step(step_id, os.path.join(src, "config.json"), state_p, out, log) != 0:
            return None, open(log, errors="replace").read()
        state_p = os.path.join(out, "state_out.json")
    chk = step_dir(run, checker_id)
    rc = run_step(checker_id, os.path.join(chk, "config.json"), state_p, os.path.join(case_dir, "checker"), log)
    return rc, open(log, errors="replace").read()


def sdc_with(extra, case_dir, step_cfg):
    """The SDC the signoff STA of the run uses (SIGNOFF_SDC_FILE, else LibreLane's base.sdc) plus `extra`."""
    src = step_cfg.get("SIGNOFF_SDC_FILE") or os.path.join(LL_DIR, "librelane", "scripts", "base.sdc")
    p = os.path.join(case_dir, "neg.sdc")
    open(p, "w").write(open(src).read() + "\n# neg_pnr.py\n" + extra + "\n")
    return p


def sdc_without_output_delay(case_dir, step_cfg):
    """The signoff SDC with LibreLane's base.sdc inlined and its one set_output_delay line removed."""
    src = step_cfg.get("SIGNOFF_SDC_FILE") or os.path.join(LL_DIR, "librelane", "scripts", "base.sdc")
    base = os.path.join(LL_DIR, "librelane", "scripts", "base.sdc")
    text = open(src).read()
    if src != base:
        source_line = "source $::env(SCRIPTS_DIR)/base.sdc"
        if text.count(source_line) != 1:
            raise RuntimeError(f"{src}: expected exactly one '{source_line}'")
        text = text.replace(source_line, open(base).read())
    lines = text.splitlines(keepends=True)
    kept = [x for x in lines if not x.startswith("set_output_delay ")]
    if len(lines) - len(kept) != 1:
        raise RuntimeError(f"expected exactly one set_output_delay line, found {len(lines) - len(kept)}")
    p = os.path.join(case_dir, "neg.sdc")
    open(p, "w").write("# neg_pnr.py P13: signoff SDC with base.sdc inlined, set_output_delay removed\n"
                       + "".join(kept))
    return p


def gds_add_met2(src, dst, case_dir, log):
    """Copy src GDS to dst with one 0.05 x 5 um met2 (69/20) rectangle at (2, 2) um in the top cell."""
    script = os.path.join(case_dir, "add_shape.py")
    open(script, "w").write(f"""import pya
ly = pya.Layout()
ly.read({src!r})
top = ly.top_cell()
li = ly.layer(69, 20)
top.shapes(li).insert(pya.Box(int(2.0 / ly.dbu), int(2.0 / ly.dbu), int(2.05 / ly.dbu), int(7.0 / ly.dbu)))
ly.write({dst!r})
print("neg_pnr: added met2 box to", top.name)
""")
    return nix(f"klayout -b -r '{script}'", log)


# ---------------------------------------------------------------- cases
def p01(run, d):
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.SetupViolations",
                     edit_config=lambda c: c.update(SIGNOFF_SDC_FILE=sdc_with("set_clock_uncertainty -setup 30 [all_clocks]", d, c)))
    return rc not in (0, None) and "Setup violations found" in text, "Checker.SetupViolations: Setup violations found"


def p02(run, d):
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.HoldViolations",
                     edit_config=lambda c: c.update(SIGNOFF_SDC_FILE=sdc_with("set_clock_uncertainty -hold 5 [all_clocks]", d, c)))
    return rc not in (0, None) and "Hold violations found" in text, "Checker.HoldViolations: Hold violations found"


def p03(run, d):
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.MaxSlewViolations",
                     edit_config=lambda c: c.update(SIGNOFF_SDC_FILE=sdc_with("set_max_transition 0.05 [current_design]", d, c)))
    return rc not in (0, None) and re.search(r"[Mm]ax [Ss]lew violations found", text) is not None, \
        "Checker.MaxSlewViolations: Max Slew violations found"


def p04(run, d):
    tcl = open(os.path.join(ROOT, "pnr", "soc_top", "sta_extra_corner.tcl")).read()
    new = tcl.replace("set sram_late_ss 1.5", "set sram_late_ss 10")
    assert new != tcl
    p = os.path.join(d, "sta_extra_corner.tcl")
    open(p, "w").write(new)
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.SetupViolations",
                     edit_config=lambda c: c.update(STA_EXTRA_CORNER_TCL_FILE=p))
    ok = rc not in (0, None) and "Setup violations found" in text and "sram0 -late -cell_delay 10" in text_of(d)
    return ok, "Checker.SetupViolations in the ss corners, and the hook printed the derate 10"


def text_of(d):
    return "".join(open(f, errors="replace").read() for f in glob.glob(os.path.join(d, "step", "**", "*.log"), recursive=True))


def p05(run, d):
    """SRAM power pins cut off the grid: the final DEF without the vias that the grid puts on the SRAM
    power ring (special-net vias inside the SRAM outline); Magic extraction + Netgen LVS must FAIL."""
    src_state = json.load(open(os.path.join(step_dir(run, "Magic.SpiceExtraction"), "state_in.json")))
    text = open(src_state["def"]).read()
    x0, y0, x1, y1 = 301760, 364480, 301760 + 683100, 364480 + 416540   # sram0 outline (DEF units)
    head, rest = text.split("SPECIALNETS", 1)
    body, tail = rest.split("END SPECIALNETS", 1)
    kept, removed = [], 0
    for line in body.split("\n"):
        m = re.search(r"^\s*(NEW|\+ ROUTED) (met\d) \d+ \+ SHAPE STRIPE \( (\d+) (\d+) \) via\w+", line)
        if m and x0 <= int(m.group(3)) <= x1 and y0 <= int(m.group(4)) <= y1:
            removed += 1
            if m.group(1) == "+ ROUTED":   # keep the net statement valid: next segment takes over + ROUTED
                kept.append("__ROUTED__")
            continue
        if kept and kept[-1] == "__ROUTED__":
            kept[-1] = None
            line = re.sub(r"^(\s*)NEW ", r"\1+ ROUTED ", line)
        kept.append(line)
    if removed == 0:
        return False, "no grid via found inside the SRAM outline"
    bad = os.path.join(d, "soc_top.def")
    open(bad, "w").write(head + "SPECIALNETS" + "\n".join(k for k in kept if k is not None) + "END SPECIALNETS" + tail)
    open(os.path.join(d, "run.log"), "a").write(f"neg_pnr: removed {removed} grid vias inside the SRAM outline\n")
    rc, text = rerun_chain(run, d, ["Magic.SpiceExtraction", "Netgen.LVS"], "Checker.LVS",
                           edit_state=lambda s: s.update({"def": bad}))
    return rc not in (0, None) and "LVS errors found" in text, f"Checker.LVS: LVS errors found ({removed} vias removed)"


def p10(run, d):
    gds = json.load(open(os.path.join(step_dir(run, "KLayout.DRC"), "state_in.json")))["gds"]
    bad = os.path.join(d, "soc_top.gds")
    log = os.path.join(d, "run.log")
    if gds_add_met2(gds, bad, d, log) != 0:
        return False, "could not edit the GDS"
    rc, text = rerun(run, d, "KLayout.DRC", "Checker.KLayoutDRC", edit_state=lambda s: s.update(gds=bad))
    if not (rc not in (0, None) and "KLayout DRC errors found" in text):
        return False, "Checker.KLayoutDRC: KLayout DRC errors found"
    # Magic DRC on the same GDS: ERROR_ON_MAGIC_DRC is false in soc_top, so the checker is
    # check_soc.py magic_drc (no violation outside the SRAM outline). The box is at (2, 2) um,
    # far from the SRAM at (301.76, 364.48).
    src = step_dir(run, "Magic.DRC")
    state = json.load(open(os.path.join(src, "state_in.json")))
    state["gds"] = bad
    st_p = os.path.join(d, "magic_state_in.json")
    json.dump(state, open(st_p, "w"), indent=1)
    if run_step("Magic.DRC", os.path.join(src, "config.json"), st_p, os.path.join(d, "magic"), log) != 0:
        return False, "Magic.DRC re-run failed"
    rel = os.path.relpath(os.path.join(src, "reports", "drc.magic.rpt"), run)
    rc, out = check_soc(fake_run(run, d, {}, {rel: os.path.join(d, "magic", "reports", "drc.magic.rpt")}), d)
    return rc != 0 and re.search(r"\[FAIL\] magic_drc: [1-9]\d* violations outside the SRAM outline", out) is not None, \
        "Checker.KLayoutDRC (KLayout DRC errors found) and check_soc.py magic_drc (violations outside the SRAM)"


def p11(run, d):
    kgds = json.load(open(os.path.join(step_dir(run, "KLayout.XOR"), "state_in.json")))["klayout_gds"]
    bad = os.path.join(d, "soc_top.klayout.gds")
    log = os.path.join(d, "run.log")
    if gds_add_met2(kgds, bad, d, log) != 0:
        return False, "could not edit the GDS"
    rc, text = rerun(run, d, "KLayout.XOR", "Checker.XOR", edit_state=lambda s: s.update(klayout_gds=bad))
    return rc not in (0, None) and "XOR differences found" in text, "Checker.XOR: XOR differences found"


def fake_run(run, d, replace, links=None):
    """A directory that looks like <run> to check_soc.py: symlinks, except the files in `replace`
    ({relative path: new text}), which are written as edited copies, and the files in `links`
    ({relative path: other file}), which point to another file."""
    links = links or {}
    fr = os.path.join(d, "run")
    for rel in ["final/nl/soc_top.nl.v", "final/def/soc_top.def"] + \
            [os.path.relpath(p, run) for p in glob.glob(os.path.join(run, "*-odb-reportdisconnectedpins", "*.log"))
             + glob.glob(os.path.join(run, "*-magic-drc", "reports", "drc.magic.rpt"))]:
        dst = os.path.join(fr, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel in replace:
            open(dst, "w").write(replace[rel])
        elif rel in links:
            os.symlink(os.path.abspath(links[rel]), dst)
        else:
            os.symlink(os.path.join(run, rel), dst)
    return fr


def check_soc(fr, d):
    cp = subprocess.run([sys.executable, CHECK_SOC, fr], capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "a").write(cp.stdout + cp.stderr)
    return cp.returncode, cp.stdout


def antenna_check(run, sram_lef, d, tag):
    """OpenROAD check_antennas on the final DEF, with the tech/cell LEFs of the run and `sram_lef`.
    Returns the number of net violations (None if OpenROAD failed)."""
    cfg = json.load(open(os.path.join(step_dir(run, "OpenROAD.CheckAntennas"), "config.json")))
    lefs = [cfg["TECH_LEFS"]["nom_*"]] + list(cfg["CELL_LEFS"]) + [sram_lef]
    tcl = os.path.join(d, f"ant_{tag}.tcl")
    rpt = os.path.join(d, f"ant_{tag}.rpt")
    open(tcl, "w").write("".join(f"read_lef {{{p}}}\n" for p in lefs)
                         + f"read_def {{{os.path.join(run, 'final', 'def', 'soc_top.def')}}}\n"
                         + f"check_antennas -report_file {{{rpt}}}\n")
    log = os.path.join(d, "run.log")
    if nix(f"openroad -exit -no_splash '{tcl}'", log) != 0:
        return None
    found = re.findall(r"Found (\d+) net violations", open(log, errors="replace").read())
    return int(found[-1]) if found else None


def p06(run, d):
    """The antenna checker sees the nets on SRAM inputs: OpenROAD check_antennas on the final layout
    with the flow's SRAM LEF (expected 0 violations) and with its ANTENNAGATEAREA divided by 1000
    (expected > 0)."""
    lef_src = os.path.join(ROOT, "ip", "sram", "sky130_sram_2kbyte_1rw1r_32x512_8", "sky130_sram_2kbyte_1rw1r_32x512_8.lef")
    text = open(lef_src).read()
    new, n = re.subn(r"ANTENNAGATEAREA ([\d.]+) ;", lambda m: f"ANTENNAGATEAREA {float(m.group(1)) / 1000:.6f} ;", text)
    if n != 59:
        return False, f"expected 59 ANTENNAGATEAREA lines in {lef_src}, found {n}"
    tiny = os.path.join(d, "sram_tiny_gate.lef")
    open(tiny, "w").write(new)
    real_n = antenna_check(run, lef_src, d, "real")
    tiny_n = antenna_check(run, tiny, d, "tiny")
    open(os.path.join(d, "run.log"), "a").write(f"\nneg_pnr: net violations with the flow LEF {real_n}, with gate area / 1000 {tiny_n}\n")
    return real_n == 0 and isinstance(tiny_n, int) and tiny_n > 0, \
        f"OpenROAD check_antennas: {tiny_n} net violations with gate area / 1000 (flow LEF: {real_n})"


def p08(run, d):
    rel = "final/nl/soc_top.nl.v"
    nl = open(os.path.join(run, rel)).read()
    new, n = re.subn(r"(sky130_sram_2kbyte_1rw1r_32x512_8\s+sram0\s*\(.*?\.csb1\()[^)]+(\))", r"\1neg_pnr_floating\2", nl, count=1, flags=re.S)
    if n != 1:
        return False, "csb1 connection not found"
    rc, out = check_soc(fake_run(run, d, {rel: new}), d)
    return rc != 0 and "[FAIL] port1_tieoff" in out, "check_soc.py port1_tieoff"


def p09(run, d):
    rel = "final/def/soc_top.def"
    df = open(os.path.join(run, rel)).read()
    new, n = re.subn(r"(-\s+sram0\s+sky130_sram_2kbyte_1rw1r_32x512_8\s*\+\s*\w+\s*\(\s*)(\d+)",
                     lambda m: m.group(1) + str(int(m.group(2)) + 10000), df, count=1)
    if n != 1:
        return False, "sram0 component not found"
    rc, out = check_soc(fake_run(run, d, {rel: new}), d)
    return rc != 0 and "[FAIL] placement" in out, "check_soc.py placement"


def signoff_with(run, d, edit):
    m = json.load(open(os.path.join(run.rstrip("/") + "_signoff", "metrics.json")))
    edit(m)
    p = os.path.join(d, "metrics.json")
    json.dump(m, open(p, "w"), indent=1)
    cp = subprocess.run([sys.executable, CHECK_SIGNOFF, p, LIMITS, GOLDEN], capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "w").write(cp.stdout + cp.stderr)
    return cp.returncode, cp.stdout


def p07(run, d):
    rc, out = signoff_with(run, d, lambda m: m.update({"ir__drop__worst": 0.2}))
    return rc != 0 and re.search(r"\[FAIL\] max\s+ir__drop__worst", out) is not None, "check_signoff.py [max] ir__drop__worst"


def p12(run, d):
    rc, out = signoff_with(run, d, lambda m: m.update({"design__instance__count": int(m["design__instance__count"] * 0.9)}))
    return rc != 0 and re.search(r"\[FAIL\] golden design__instance__count", out) is not None, \
        "check_signoff.py golden design__instance__count"


def p13(run, d):
    """Unconstrained endpoints are caught: the signoff SDC without its set_output_delay line, re-run
    STA, then check_soc.read_check_setup on the result must report warnings other than the allowed one.
    unset_output_delay is not used: OpenSTA still counts an unset delay as present (2026-10-03: with
    `unset_output_delay -clock clk [all_outputs]` the outputs had no timed paths, yet check_setup
    -unconstrained_endpoints and -no_output_delay both reported nothing)."""
    sys.path.insert(0, os.path.dirname(CHECK_SOC))
    import check_soc  # noqa: E402
    src = step_dir(run, "OpenROAD.STAPostPNR")
    cfg = json.load(open(os.path.join(src, "config.json")))
    cfg["SIGNOFF_SDC_FILE"] = sdc_without_output_delay(d, cfg)
    cfg_p = os.path.join(d, "step_config.json")
    json.dump(cfg, open(cfg_p, "w"), indent=1)
    log = os.path.join(d, "run.log")
    if run_step("OpenROAD.STAPostPNR", cfg_p, os.path.join(src, "state_in.json"), os.path.join(d, "step"), log) != 0:
        return False, "STA re-run failed"
    real = check_soc.read_check_setup(src)
    neg = check_soc.read_check_setup(os.path.join(d, "step"))
    extra = {c: [w for w in ws if w not in check_soc.CHECK_SETUP_ALLOWED] for c, ws in neg.items() if ws}
    extra = {c: ws for c, ws in extra.items() if ws}
    real_extra = {c: [w for w in ws if w not in check_soc.CHECK_SETUP_ALLOWED] for c, ws in real.items() if ws}
    open(log, "a").write(f"\nneg_pnr: unexpected check_setup warnings: {extra}\n")
    return len(extra) == 9 and not any(real_extra.values()), \
        "check_soc.py sta_setup: unexpected check_setup warnings in all 9 corners (real run: none)"


def edit_once(text, pattern, repl, what):
    new, n = re.subn(pattern, repl, text, count=1, flags=re.M)
    if n != 1:
        raise RuntimeError(f"injection point not found: {what}")
    return new


def p14(run, d):
    rel = "final/nl/soc_top.nl.v"
    nl = open(os.path.join(run, rel)).read()
    if len(re.findall(re.escape(SRAM) + r"\s+sram0\s*\(", nl)) != 1:
        return False, "sram0 instance not found exactly once"
    new = edit_once(nl, re.escape(SRAM) + r"(\s+)sram0(\s*\()", SRAM + r"\1sram9\2", "sram0 instance")
    rc, out = check_soc(fake_run(run, d, {rel: new}), d)
    return rc != 0 and "[FAIL] macro" in out, "check_soc.py macro"


def p15(run, d):
    line = "Found 0 disconnected pin(s), of which 0 are critical"
    logs = [p for p in glob.glob(os.path.join(run, "*-odb-reportdisconnectedpins", "*.log")) if line in open(p).read()]
    if len(logs) != 1 or open(logs[0]).read().count(line) != 1:
        return False, "the 'Found 0 disconnected pin(s)' line not found exactly once"
    new = open(logs[0]).read().replace(line, "Found 1 disconnected pin(s), of which 1 are critical")
    rc, out = check_soc(fake_run(run, d, {os.path.relpath(logs[0], run): new}), d)
    return rc != 0 and "[FAIL] disconnected" in out, "check_soc.py disconnected"


def inputs_check(d, *args):
    cp = subprocess.run([sys.executable, CHECK_INPUTS, *args], capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "a").write(cp.stdout + cp.stderr)
    return cp.returncode, cp.stdout


def config_with(d, edit):
    cfg = json.load(open(CONFIG))
    edit(cfg)
    p = os.path.join(d, "config.json")
    json.dump(cfg, open(p, "w"), indent=1)
    return p


def inputs_failed(rc, out, row):
    return rc != 0 and re.search(rf"^  \[FAIL\] {row}:", out, re.M) is not None and "soc-inputs: FAIL" in out


def p16(run, d):
    rc, out = inputs_check(d, "--config", config_with(d, lambda c: c["VERILOG_FILES"].pop()))
    return inputs_failed(rc, out, "rtl_files"), "check_inputs.py rtl_files"


def p17(run, d):
    text = open(os.path.join(SRAM_IP, "padded.lib")).read()
    new = edit_once(text, r'values\("10\.000, ', 'values("1.000, ', "first 10 ns dout0 delay table")
    p = os.path.join(d, "padded.lib")
    open(p, "w").write(new)
    rc, out = inputs_check(d, "--padded", p)
    return inputs_failed(rc, out, "padded_lib"), "check_inputs.py padded_lib"


def p18(run, d):
    text = open(os.path.join(SRAM_IP, f"{SRAM}.lef")).read()
    new = edit_once(text, r"^[ \t]*ANTENNAGATEAREA[^\n]*\n", "", "first ANTENNAGATEAREA line")
    p = os.path.join(d, f"{SRAM}.lef")
    open(p, "w").write(new)
    rc, out = inputs_check(d, "--lef", p)
    return inputs_failed(rc, out, "antenna_lef"), "check_inputs.py antenna_lef"


def p19(run, d):
    cfg = config_with(d, lambda c: c["MACROS"][SRAM].update(lib={"*": [PDK_TT_LIB]}))
    rc, out = inputs_check(d, "--config", cfg)
    return inputs_failed(rc, out, "macro_lib"), "check_inputs.py macro_lib"


def p20(run, d):
    res = json.load(open(os.path.join(run, "resolved.json")))
    lib = res["MACROS"][SRAM]["lib"]
    if list(lib) != ["*"]:
        return False, f"unexpected resolved MACROS lib {lib}"
    res["MACROS"][SRAM]["lib"] = {"*": [res["PDK_ROOT"] + f"/sky130A/libs.ref/sky130_sram_macros/lib/{SRAM}_TT_1p8V_25C.lib"]}
    p = os.path.join(d, "resolved.json")
    json.dump(res, open(p, "w"), indent=1)
    rc, out = inputs_check(d, "--resolved", p)
    return inputs_failed(rc, out, "resolved"), "check_inputs.py --resolved"


CASES = [("P01", p01), ("P02", p02), ("P03", p03), ("P04", p04), ("P05", p05), ("P06", p06), ("P07", p07),
         ("P08", p08), ("P09", p09), ("P10", p10), ("P11", p11), ("P12", p12), ("P13", p13), ("P14", p14),
         ("P15", p15), ("P16", p16), ("P17", p17), ("P18", p18), ("P19", p19), ("P20", p20)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default=os.path.join(ROOT, "runs", "soc_top"))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--cases")
    ap.add_argument("-j", type=int, default=4)
    args = ap.parse_args()
    run = os.path.abspath(args.run)
    out = os.path.abspath(args.out)
    shutil.rmtree(out, ignore_errors=True)  # only the output directory is removed, before any check
    cases = CASES
    if args.cases:
        want = args.cases.split(",")
        cases = [c for c in CASES if c[0] in want]
        if len(cases) != len(want):
            print(f"neg-pnr: FAIL (unknown case in {want})")
            return 1
    errs = guard(run, "harden-soc: PASS")
    if errs:
        print(f"neg-pnr: FAIL ({'; '.join(errs)}; run `make harden-soc`)")
        return 1
    if not os.path.isdir(os.path.join(run, "final")):
        print(f"neg-pnr: FAIL ({run} has no final/; run `make harden-soc` first)")
        return 1
    t0 = time.time()

    def one(case):
        name, fn = case
        d = os.path.join(out, name)
        os.makedirs(d)
        try:
            ok, expect = fn(run, d)
        except Exception as e:  # noqa: BLE001 - a broken case is reported, not raised
            ok, expect = False, f"case error: {e!r}"
        return name, ok, expect

    with ThreadPoolExecutor(max_workers=max(1, args.j)) as ex:
        results = list(ex.map(one, cases))
    caught = 0
    for name, ok, expect in results:
        caught += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {'FAIL at ' if ok else 'expected FAIL at '}{expect}"
              + ("" if ok else f" (see {os.path.relpath(os.path.join(out, name), ROOT)}/run.log)"))
    status = "PASS" if caught == len(cases) else "FAIL"
    print(f"neg-pnr: {status} {caught}/{len(cases)} caught ({round(time.time() - t0)} s)")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
