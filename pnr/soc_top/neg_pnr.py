#!/usr/bin/env python3
"""make neg-pnr: bug injection into the soc_top flow and its results (project-plan.md §7.3 P01-P12, plus P00, P13-P31).

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
       outside the SRAM                              Magic.DRC (full GDS) -> check_soc.py magic_drc
  P21  final GDS + two 0.5 um li1 squares 0.1 um   Magic.DRC (full GDS) -> check_soc.py magic_drc
       apart inside the SRAM outline, where the SRAM (a new violation of a rule the SRAM alone also
       has no li1, licon, mcon, diff, poly or tap    violates, li.3 li spacing; the Phase 3 check
                                                      compared only rule types and missed it, known
                                                      limitation 14)
  P22  signoff SDC clock waveform {0 10}: 10 ns    OpenROAD.STAPostPNR -> check_soc.py pulse_width
       high phase, the SRAM clk0 needs 12 ns          (min pulse width)
  P23  signoff SDC clock period 29 ns, {0 14.5}:   OpenROAD.STAPostPNR -> check_soc.py pulse_width
       the SRAM clk0 needs 30 ns                      (min period)
  P24  signoff SDC clock waveform {0 0.6*T}: duty  OpenROAD.STAPostPNR -> Checker.SetupViolations,
       cycle 60 %, beyond the 55 % budget             worst ss path launched by the sram0 falling edge
  P25  clock_uncertainty.sdc unc_duty_max 0.60     OpenROAD.STAPostPNR -> Checker.SetupViolations,
       (the duty cycle budget reaches the              worst ss path launched by the sram0 falling edge
       half-cycle paths: inter-edge uncertainty)
  P11  KLayout GDS + one met2 rectangle (Magic GDS unchanged)
                                                     KLayout.XOR -> Checker.XOR
  checker inputs (the checker on an edited copy of one file; the tool is not re-run)
  P00  positive control: the fake run of the cases below, without any edit: check_soc.py PASS
       (each fake run links the run's final netlist and DEF, disconnected-pin log, Magic DRC
       report and signoff STA directory; the edited file replaces its link)
  P06  SRAM LEF with ANTENNAGATEAREA / 1000         OpenROAD check_antennas on the final DEF: > 0 violations
       (with the flow's LEF: 0; shows the antenna checker sees the nets on SRAM inputs)
  P07  metrics: VDD drop 11 mV and GND rise 11 mV  check_signoff.py [max_sum] ir_vdd_drop_plus_gnd_rise
       (each below 20 mV, the sum above: proves the budget is on the sum of the two nets)
  P29  metrics: VDD drop 19 mV, GND rise -15 mV     check_signoff.py [max_sum] ir_vdd_drop_plus_gnd_rise
       (sum 4 mV; every term of the sum must be >= 0)
  P26  VSRC_LOC_FILES: one vccd1 source point moved check_soc.py ir_sources
       7 um off its met5 stripe (config copy)
  P27  VSRC_LOC_FILES: one vccd1 source 2000 um      check_soc.py ir_sources
       wide (it covers its whole stripe: close to the ideal-supply model that gave 0.3 mV)
  P28  VSRC_LOC_FILES: one vccd1 source in the        check_soc.py ir_sources
       middle of its stripe (fed from the middle, about 1/4 of the one-side drop)
  P30  STA log of nom_ff_n40C_1v95 without the     check_soc.py sram_derate
       sta_extra_corner derate line (the ff early derate no timing check depends on today)
  P08  final netlist: sram0 csb1 on a floating net   check_soc.py port1_tieoff
  P09  final DEF: sram0 moved by 10 um               check_soc.py placement
  P12  metrics: design__instance__count -10 %        check_signoff.py golden comparison
  P31  metrics: final route__drc_errors golden + 1;  check_signoff.py golden comparison
       route__drc_errors__iter:2 golden + 101 (each alone; the iteration-count tolerance is 100,
       and does not cover the final count); positive control: iter:2 golden + 3 (Phase 4 regress 2)
  P13  signoff SDC without its set_output_delay line OpenROAD.STAPostPNR -> check_soc.py sta_setup
       (unconstrained endpoints, project-plan.md §7.2; check_soc.py runs on a fake run whose
       STA directory is the re-run)
  P14  final netlist: sram0 renamed sram9            check_soc.py macro
  P15  disconnected-pin log: 1 critical pin          check_soc.py disconnected
  P16  config.json: one VERILOG_FILES entry dropped  check_inputs.py rtl_files
  P17  padded.lib: one dout0 delay table edited      check_inputs.py padded_lib
  P18  SRAM LEF: one ANTENNAGATEAREA line dropped    check_inputs.py antenna_lef
  P19  config.json: MACROS lib = the PDK TT .lib     check_inputs.py macro_lib
  P20  resolved.json: MACROS lib = the PDK TT .lib   check_inputs.py --resolved
A check_soc.py case is caught only if the injected row is the only FAIL row and the verdict is
`soc-checks: FAIL` (the row alone failing does not prove the verdict follows it). Two cases have a
second row that must FAIL with it: P09 magic_drc (the DEF moved, the GDS did not, and the DRC
comparison takes the sram0 origin from the DEF) and P14 port1_tieoff (it looks for sram0).
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


def flat_sdc(step_cfg):
    """The SDC the signoff STA of the run uses (SIGNOFF_SDC_FILE, else LibreLane's base.sdc) as one
    text: its `source` lines for base.sdc and for clock_uncertainty.sdc (next to it) are replaced by
    the files, so that an edited copy in a case directory still reads them."""
    base = os.path.join(LL_DIR, "librelane", "scripts", "base.sdc")
    src = step_cfg.get("SIGNOFF_SDC_FILE") or base
    text = open(src).read()
    for line, path in (("source $::env(SCRIPTS_DIR)/base.sdc", base),
                       ("source [file join [file dirname [info script]] clock_uncertainty.sdc]",
                        os.path.join(os.path.dirname(src), "clock_uncertainty.sdc"))):
        n = text.count(line)
        if n > 1 or (n == 0 and path == base and src != base):
            raise RuntimeError(f"{src}: expected one '{line}', found {n}")
        text = text.replace(line, open(path).read())
    return text


def write_sdc(case_dir, text, note):
    p = os.path.join(case_dir, "neg.sdc")
    open(p, "w").write(f"# neg_pnr.py: {note}\n" + text)
    return p


def sdc_with(extra, case_dir, step_cfg):
    """The signoff SDC (flattened) plus `extra` at the end."""
    return write_sdc(case_dir, flat_sdc(step_cfg) + "\n" + extra + "\n", f"signoff SDC + {extra}")


def sdc_edit(case_dir, step_cfg, pattern, repl, note):
    """The signoff SDC (flattened) with exactly one regex match replaced."""
    new, n = re.subn(pattern, repl, flat_sdc(step_cfg), flags=re.M)
    if n != 1:
        raise RuntimeError(f"{note}: pattern {pattern!r} matched {n} times in the signoff SDC")
    return write_sdc(case_dir, new, note)


def sdc_without_output_delay(case_dir, step_cfg):
    """The signoff SDC with its one set_output_delay line removed."""
    return sdc_edit(case_dir, step_cfg, r"^set_output_delay .*\n", "", "P13: set_output_delay removed")


def gds_add_box(src, dst, case_dir, log, layer=(69, 20), boxes=((2.0, 2.0, 2.05, 7.0),)):
    """Copy src GDS to dst with rectangles (x0, y0, x1, y1 in um) on `layer` (default one 0.05 x 5 um
    met2 69/20 box at (2, 2)) in the top cell."""
    script = os.path.join(case_dir, "add_shape.py")
    open(script, "w").write(f"""import pya
ly = pya.Layout()
ly.read({src!r})
top = ly.top_cell()
li = ly.layer({layer[0]}, {layer[1]})
for b in {list(boxes)!r}:
    top.shapes(li).insert(pya.Box(*[round(v / ly.dbu) for v in b]))
ly.write({dst!r})
print("neg_pnr: added {len(boxes)} box(es) on {layer} to", top.name)
""")
    return nix(f"klayout -b -r '{script}'", log)


def magic_on(run, d, gds, log):
    """Re-run Magic.DRC (full GDS) of the run on another GDS; returns the report path or None."""
    src = step_dir(run, "Magic.DRC")
    state = json.load(open(os.path.join(src, "state_in.json")))
    state["gds"] = gds
    st_p = os.path.join(d, "magic_state_in.json")
    json.dump(state, open(st_p, "w"), indent=1)
    if run_step("Magic.DRC", os.path.join(src, "config.json"), st_p, os.path.join(d, "magic"), log) != 0:
        return None
    return os.path.join(d, "magic", "reports", "drc.magic.rpt")


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
    new = tcl.replace("set sram_late_ss 1.575\n", "set sram_late_ss 10\n")
    assert new != tcl
    p = os.path.join(d, "sta_extra_corner.tcl")
    open(p, "w").write(new)
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.SetupViolations",
                     edit_config=lambda c: c.update(STA_EXTRA_CORNER_TCL_FILE=p))
    ok = rc not in (0, None) and "Setup violations found" in text and "sram0 -late -cell_delay 10" in text_of(d)
    return ok, "Checker.SetupViolations in the ss corners, and the hook printed the derate 10"


def text_of(d):
    return "".join(open(f, errors="replace").read() for f in glob.glob(os.path.join(d, "step", "**", "*.log"), recursive=True))


CREATE_CLOCK = r"^(create_clock .*-period )\$::env\(CLOCK_PERIOD\)$"


def sta_rerun(run, d, sdc):
    """Re-run the signoff STA with another SIGNOFF_SDC_FILE; returns the output directory or None."""
    src = step_dir(run, "OpenROAD.STAPostPNR")
    cfg = json.load(open(os.path.join(src, "config.json")))
    cfg["SIGNOFF_SDC_FILE"] = sdc(cfg)
    cfg_p = os.path.join(d, "step_config.json")
    json.dump(cfg, open(cfg_p, "w"), indent=1)
    if run_step("OpenROAD.STAPostPNR", cfg_p, os.path.join(src, "state_in.json"), os.path.join(d, "step"),
                os.path.join(d, "run.log")) != 0:
        return None
    return os.path.join(d, "step")


def pulse_case(run, d, waveform, kind):
    out = sta_rerun(run, d, lambda c: sdc_edit(d, c, CREATE_CLOCK, r"\g<1>" + waveform, f"create_clock -period {waveform}"))
    if out is None:
        return False, "STA re-run failed"
    ok, text = soc_case(run, d, "pulse_width", links={os.path.relpath(step_dir(run, "OpenROAD.STAPostPNR"), run): out})
    # the kinds of all problems, not the first one: at 29 ns (P23) the ss corners also miss the min
    # pulse width, and only the report order put a min_period problem first (Phase 4 review)
    hit = re.search(r"\[FAIL\] pulse_width: \d+ problem\(s\) \[([^\]]*)\]", text)
    return ok and hit is not None and kind in hit.group(1).split(", "), \
        f"check_soc.py pulse_width: {kind} slack below the required slack (only row FAIL, soc-checks: FAIL)"


def p22(run, d):
    return pulse_case(run, d, "$::env(CLOCK_PERIOD) -waveform {0 10}", "min_pulse_width")


def p23(run, d):
    return pulse_case(run, d, "29 -waveform {0 14.5}", "min_period")


def worst_ss_from_sram_fall(step):
    """The worst setup path of nom_ss_100C_1v60 starts at the sram0 falling edge (the half-cycle path)."""
    rpt = os.path.join(step, "nom_ss_100C_1v60", "max.rpt")
    m = re.search(r"^Startpoint: (\S+) \((\w+) edge-triggered", open(rpt).read(), re.M) if os.path.isfile(rpt) else None
    return m is not None and m.groups() == ("sram0", "falling")


def p24(run, d):
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.SetupViolations",
                     edit_config=lambda c: c.update(SIGNOFF_SDC_FILE=sdc_edit(
                         d, c, CREATE_CLOCK, r"\g<1>$::env(CLOCK_PERIOD) -waveform [list 0 [expr {0.6 * $::env(CLOCK_PERIOD)}]]", "duty cycle 60 %")))
    ok = rc not in (0, None) and "Setup violations found" in text and worst_ss_from_sram_fall(os.path.join(d, "step"))
    return ok, "Checker.SetupViolations, worst nom_ss path launched by the sram0 falling edge"


def p25(run, d):
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.SetupViolations",
                     edit_config=lambda c: c.update(SIGNOFF_SDC_FILE=sdc_edit(
                         d, c, r"^set unc_duty_max 0\.55 ", "set unc_duty_max 0.60 ", "duty cycle budget 60 %")))
    ok = rc not in (0, None) and "Setup violations found" in text and worst_ss_from_sram_fall(os.path.join(d, "step"))
    return ok, "Checker.SetupViolations, worst nom_ss path launched by the sram0 falling edge"


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
    if gds_add_box(gds, bad, d, log) != 0:
        return False, "could not edit the GDS"
    rc, text = rerun(run, d, "KLayout.DRC", "Checker.KLayoutDRC", edit_state=lambda s: s.update(gds=bad))
    if not (rc not in (0, None) and "KLayout DRC errors found" in text):
        return False, "Checker.KLayoutDRC: KLayout DRC errors found"
    # Magic DRC on the same GDS: ERROR_ON_MAGIC_DRC is false in soc_top, so the checker is
    # check_soc.py magic_drc (no violation outside the SRAM outline). The box is at (2, 2) um,
    # far from the SRAM at (301.76, 364.48).
    rpt = magic_on(run, d, bad, log)
    if rpt is None:
        return False, "Magic.DRC re-run failed"
    ok, out = soc_case(run, d, "magic_drc", links={magic_rel(run): rpt})
    return ok and re.search(r"\[FAIL\] magic_drc: [1-9]\d* violations outside the SRAM outline", out) is not None, \
        "Checker.KLayoutDRC (KLayout DRC errors found) and check_soc.py magic_drc (violations outside the SRAM)"


# SRAM-local point (um) with no li1, licon, mcon, diff, poly or tap within 2 um in x and from 2 um
# below to 7 um above (KLayout scan of the PDK GDS, 2026-10-04). Two 0.5 um li1 squares there,
# 0.1 um apart, violate li.3 (li spacing 0.17 um), a rule the SRAM alone also violates. First try,
# a 0.05 um wide li1 line, gave li.c1 (core li width), which the SRAM alone does not violate, so
# the Phase 3 rule-type check would have caught it too and the case would not test the position.
P21_SRAM_LOCAL = (5.0, 5.0)


def p21(run, d):
    gds = json.load(open(os.path.join(step_dir(run, "Magic.DRC"), "state_in.json")))["gds"]
    cfg = json.load(open(CONFIG))["MACROS"][SRAM]["instances"]["sram0"]["location"]
    x, y = cfg[0] + P21_SRAM_LOCAL[0], cfg[1] + P21_SRAM_LOCAL[1]
    bad = os.path.join(d, "soc_top.gds")
    log = os.path.join(d, "run.log")
    if gds_add_box(gds, bad, d, log, layer=(67, 20), boxes=((x, y, x + 0.5, y + 0.5), (x + 0.6, y, x + 1.1, y + 0.5))) != 0:
        return False, "could not edit the GDS"
    rpt = magic_on(run, d, bad, log)
    if rpt is None:
        return False, "Magic.DRC re-run failed"
    ok, out = soc_case(run, d, "magic_drc", links={magic_rel(run): rpt})
    base = json.load(open(os.path.join(ROOT, "signoff", "waivers", "soc_top", "sram_magic_drc_baseline.json")))["rules"]
    hit = re.search(r"\[FAIL\] magic_drc: 0 violations outside the SRAM outline; inside \d+, ([1-9]\d*) not at the position "
                    r"of a same-rule violation of the SRAM alone \[rules: ([^\]]+)\], e\.g\. '([^']+)' at \(([\d.]+), ([\d.]+)\)", out)
    # every rule of the unexplained boxes is in the SRAM-alone baseline: a rule the SRAM alone does
    # not have would also FAIL the Phase 3 rule-type check, so it would not show the fix (Phase 4 review)
    ok = ok and hit is not None and all(r in base for r in hit.group(2).split(" | ")) \
        and abs(float(hit.group(4)) - x) < 1.5 and abs(float(hit.group(5)) - y) < 1.5
    return ok, (f"check_soc.py magic_drc: a new {hit.group(2) if hit else 'li'!r} violation inside the SRAM outline at "
                f"({x:.2f}, {y:.2f}) um; that rule is in the SRAM-alone baseline, so the Phase 3 rule-type check would PASS")


def p11(run, d):
    kgds = json.load(open(os.path.join(step_dir(run, "KLayout.XOR"), "state_in.json")))["klayout_gds"]
    bad = os.path.join(d, "soc_top.klayout.gds")
    log = os.path.join(d, "run.log")
    if gds_add_box(kgds, bad, d, log) != 0:
        return False, "could not edit the GDS"
    rc, text = rerun(run, d, "KLayout.XOR", "Checker.XOR", edit_state=lambda s: s.update(klayout_gds=bad))
    return rc not in (0, None) and "XOR differences found" in text, "Checker.XOR: XOR differences found"


def magic_rel(run):
    return os.path.relpath(os.path.join(step_dir(run, "Magic.DRC"), "reports", "drc.magic.rpt"), run)


def sram_drc_alone(run):
    """The SRAM-alone Magic DRC report that `make harden-soc` made for this run (run.sh)."""
    return run.rstrip(os.sep) + "_signoff/sram_drc_alone/step/reports/drc.magic.rpt"


def fake_run(run, d, replace, links=None):
    """A directory that looks like <run> to check_soc.py: symlinks, except the files in `replace`
    ({relative path: new text}), which are written as edited copies, and the files or directories
    in `links` ({relative path: other path}), which point elsewhere. Linked: the final netlist and
    DEF, the disconnected-pin logs, the Magic DRC report and the last signoff STA directory."""
    links = links or {}
    fr = os.path.join(d, "run")
    sta = os.path.relpath(step_dir(run, "OpenROAD.STAPostPNR"), run)
    for rel in ["final/nl/soc_top.nl.v", "final/def/soc_top.def", sta] + \
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


def check_soc(fr, d, run, config=CONFIG):
    cp = subprocess.run([sys.executable, CHECK_SOC, fr, "--config", config, "--sram-drc", sram_drc_alone(run)],
                        capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "a").write(cp.stdout + cp.stderr)
    return cp.returncode, cp.stdout


def soc_case(run, d, row, replace=None, links=None, also=(), config=CONFIG):
    """check_soc.py on a fake run with one edit: (caught, output). Caught only if the FAIL rows are
    exactly `row` (plus `also`) and the verdict is soc-checks: FAIL."""
    rc, out = check_soc(fake_run(run, d, replace or {}, links), d, run, config)
    failed = set(re.findall(r"^  \[FAIL\] (\w+):", out, re.M))
    return rc != 0 and failed == {row, *also} and "soc-checks: FAIL" in out, out


def sta_dir_with(run, d, corner, edit):
    """A copy of the signoff STA directory made of symlinks, except <corner>/sta.log, which is
    edit(text) of the original. Returns (relative path of the STA directory in the run, copy)."""
    src = step_dir(run, "OpenROAD.STAPostPNR")
    dst = os.path.join(d, "sta")
    for root, dirs, files in os.walk(src):
        here = os.path.join(dst, os.path.relpath(root, src))
        os.makedirs(here, exist_ok=True)
        for f in files:
            if os.path.relpath(os.path.join(root, f), src) == os.path.join(corner, "sta.log"):
                open(os.path.join(here, f), "w").write(edit(open(os.path.join(root, f), errors="replace").read()))
            else:
                os.symlink(os.path.join(root, f), os.path.join(here, f))
    return os.path.relpath(src, run), dst


def p30(run, d):
    rel, sta = sta_dir_with(run, d, "nom_ff_n40C_1v95",
                            lambda t: re.sub(r"^sta_extra_corner: nom_ff_n40C_1v95: sram0 .*\n", "", t, flags=re.M))
    ok, out = soc_case(run, d, "sram_derate", links={rel: sta})
    return ok and "nom_ff_n40C_1v95: []" in out, \
        "check_soc.py sram_derate: no SRAM derate line in nom_ff_n40C_1v95 (only row FAIL, soc-checks: FAIL)"


def p00(run, d):
    rc, out = check_soc(fake_run(run, d, {}), d, run)
    return rc == 0 and "[FAIL]" not in out and out.rstrip().endswith("soc-checks: PASS"), \
        "positive control: check_soc.py PASS on the unedited fake run"


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
    ok, _ = soc_case(run, d, "port1_tieoff", replace={rel: new})
    return ok, "check_soc.py port1_tieoff (only row FAIL, soc-checks: FAIL)"


def p09(run, d):
    rel = "final/def/soc_top.def"
    df = open(os.path.join(run, rel)).read()
    new, n = re.subn(r"(-\s+sram0\s+sky130_sram_2kbyte_1rw1r_32x512_8\s*\+\s*\w+\s*\(\s*)(\d+)",
                     lambda m: m.group(1) + str(int(m.group(2)) + 10000), df, count=1)
    if n != 1:
        return False, "sram0 component not found"
    ok, _ = soc_case(run, d, "placement", replace={rel: new}, also=("magic_drc",))
    return ok, "check_soc.py placement (with magic_drc, whose origin is the DEF position; soc-checks: FAIL)"


def signoff_with(run, d, edit):
    m = json.load(open(os.path.join(run.rstrip("/") + "_signoff", "metrics.json")))
    edit(m)
    p = os.path.join(d, "metrics.json")
    json.dump(m, open(p, "w"), indent=1)
    cp = subprocess.run([sys.executable, CHECK_SIGNOFF, p, LIMITS, GOLDEN], capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "w").write(cp.stdout + cp.stderr)
    return cp.returncode, cp.stdout


def p07(run, d):
    rc, out = signoff_with(run, d, lambda m: m.update({"design_powergrid__drop__worst__net:vccd1": 0.011,
                                                       "design_powergrid__drop__worst__net:vssd1": 0.011}))
    failed = re.findall(r"^  \[FAIL\] (\w+)\s+(\S+)", out, re.M)
    return rc != 0 and [f for f in failed if f[0] == "max"] == [("max", "ir_vdd_drop_plus_gnd_rise")], \
        "check_signoff.py [max_sum] ir_vdd_drop_plus_gnd_rise (each net 11 mV, sum 22 mV)"


def p29(run, d):
    rc, out = signoff_with(run, d, lambda m: m.update({"design_powergrid__drop__worst__net:vccd1": 0.019,
                                                       "design_powergrid__drop__worst__net:vssd1": -0.015}))
    failed = re.findall(r"^  \[FAIL\] (\w+)\s+(\S+)", out, re.M)
    return rc != 0 and [f for f in failed if f[0] == "max"] == [("max", "ir_vdd_drop_plus_gnd_rise")] \
        and "negative: design_powergrid__drop__worst__net:vssd1" in out, \
        "check_signoff.py [max_sum] ir_vdd_drop_plus_gnd_rise (VDD 19 mV, GND -15 mV: sum 4 mV, a term below 0)"


def p26(run, d):
    cfg = json.load(open(CONFIG))
    src = os.path.join(ROOT, cfg["VSRC_LOC_FILES"]["vccd1"].replace("dir::", "", 1))
    lines = open(src).read().splitlines()
    x, y, size, volt = lines[1].split(",")
    lines[1] = ",".join([x, f"{float(y) - 7.0:.3f}", size, volt])
    vsrc = os.path.join(d, "vccd1.vsrc")
    open(vsrc, "w").write("\n".join(lines) + "\n")
    cfg["VSRC_LOC_FILES"]["vccd1"] = vsrc
    cfg_p = os.path.join(d, "config.json")
    json.dump(cfg, open(cfg_p, "w"), indent=1)
    ok, out = soc_case(run, d, "ir_sources", config=cfg_p)
    return ok and "vccd1: 5 points for 5 met5 stripes, 1 not on exactly one stripe" in out, \
        "check_soc.py ir_sources: a vccd1 source point off its met5 stripe (only row FAIL, soc-checks: FAIL)"


def vsrc_case(run, d, edit, expect):
    """check_soc.py with the second vccd1 source point changed by edit(x, y, size) -> (x, y, size)."""
    cfg = json.load(open(CONFIG))
    src = os.path.join(ROOT, cfg["VSRC_LOC_FILES"]["vccd1"].replace("dir::", "", 1))
    lines = open(src).read().splitlines()
    x, y, size, volt = lines[1].split(",")
    lines[1] = ",".join(f"{v:.3f}" for v in edit(float(x), float(y), float(size))) + "," + volt
    vsrc = os.path.join(d, "vccd1.vsrc")
    open(vsrc, "w").write("\n".join(lines) + "\n")
    cfg["VSRC_LOC_FILES"]["vccd1"] = vsrc
    cfg_p = os.path.join(d, "config.json")
    json.dump(cfg, open(cfg_p, "w"), indent=1)
    ok, out = soc_case(run, d, "ir_sources", config=cfg_p)
    return ok and expect in out


def p27(run, d):
    ok = vsrc_case(run, d, lambda x, y, size: (x, y, 2000.0),
                   "vccd1: 5 points for 5 met5 stripes, 0 not on exactly one stripe, voltages ok, 1 larger than the stripe width, 0 not at")
    return ok, "check_soc.py ir_sources: a 2000 um vccd1 source (covers its whole stripe) (only row FAIL, soc-checks: FAIL)"


def p28(run, d):
    ok = vsrc_case(run, d, lambda x, y, size: (500.0, y, size),
                   "vccd1: 5 points for 5 met5 stripes, 0 not on exactly one stripe, voltages ok, 0 larger than the stripe width, 1 not at the left end")
    return ok, "check_soc.py ir_sources: a vccd1 source in the middle of its stripe (only row FAIL, soc-checks: FAIL)"


def p12(run, d):
    rc, out = signoff_with(run, d, lambda m: m.update({"design__instance__count": int(m["design__instance__count"] * 0.9)}))
    return rc != 0 and re.search(r"\[FAIL\] golden design__instance__count", out) is not None, \
        "check_signoff.py golden design__instance__count"


def p31(run, d):
    golden = json.load(open(GOLDEN))
    results = []
    for name, key, delta, caught in (("final_plus_1", "route__drc_errors", 1, True),
                                     ("iter2_plus_101", "route__drc_errors__iter:2", 101, True),
                                     ("iter2_plus_3", "route__drc_errors__iter:2", 3, False)):
        sub = os.path.join(d, name)
        os.makedirs(sub)
        rc, out = signoff_with(run, sub, lambda m: m.update({key: golden[key] + delta}))
        row = re.search(rf"^  \[FAIL\] golden {re.escape(key)}:", out, re.M) is not None
        results.append(row == caught and (rc != 0) == caught)
    return all(results), \
        "check_signoff.py golden route__drc_errors and route__drc_errors__iter:2 FAIL; iter:2 + 3 PASS " \
        f"(final +1, iter +101, iter +3: {results})"


def p13(run, d):
    """Unconstrained endpoints are caught: the signoff SDC without its set_output_delay line, re-run
    STA, then check_soc.py on a fake run whose signoff STA directory is the re-run: sta_setup must be
    the only FAIL row (unexpected check_setup warnings in every corner).
    unset_output_delay is not used: OpenSTA still counts an unset delay as present (2026-10-03: with
    `unset_output_delay -clock clk [all_outputs]` the outputs had no timed paths, yet check_setup
    -unconstrained_endpoints and -no_output_delay both reported nothing)."""
    out = sta_rerun(run, d, lambda c: sdc_without_output_delay(d, c))
    if out is None:
        return False, "STA re-run failed"
    ok, text = soc_case(run, d, "sta_setup", links={os.path.relpath(step_dir(run, "OpenROAD.STAPostPNR"), run): out})
    ok = ok and re.search(r"\[FAIL\] sta_setup: \d+ corners .*, section missing in \[\], unexpected warnings", text) is not None
    return ok, "check_soc.py sta_setup: unexpected check_setup warnings (only row FAIL, soc-checks: FAIL)"


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
    ok, out = soc_case(run, d, "macro", replace={rel: new}, also=("port1_tieoff",))
    return ok, "check_soc.py macro (with port1_tieoff, which looks for sram0; soc-checks: FAIL)"


def p15(run, d):
    line = "Found 0 disconnected pin(s), of which 0 are critical"
    logs = [p for p in glob.glob(os.path.join(run, "*-odb-reportdisconnectedpins", "*.log")) if line in open(p).read()]
    if len(logs) != 1 or open(logs[0]).read().count(line) != 1:
        return False, "the 'Found 0 disconnected pin(s)' line not found exactly once"
    new = open(logs[0]).read().replace(line, "Found 1 disconnected pin(s), of which 1 are critical")
    ok, _ = soc_case(run, d, "disconnected", replace={os.path.relpath(logs[0], run): new})
    return ok, "check_soc.py disconnected (only row FAIL, soc-checks: FAIL)"


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


CASES = [("P00", p00), ("P01", p01), ("P02", p02), ("P03", p03), ("P04", p04), ("P05", p05), ("P06", p06), ("P07", p07),
         ("P08", p08), ("P09", p09), ("P10", p10), ("P11", p11), ("P12", p12), ("P13", p13), ("P14", p14),
         ("P15", p15), ("P16", p16), ("P17", p17), ("P18", p18), ("P19", p19), ("P20", p20), ("P21", p21),
         ("P22", p22), ("P23", p23), ("P24", p24), ("P25", p25), ("P26", p26), ("P27", p27), ("P28", p28), ("P29", p29), ("P30", p30),
         ("P31", p31)]


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
