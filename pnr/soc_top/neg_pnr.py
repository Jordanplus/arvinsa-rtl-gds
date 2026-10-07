#!/usr/bin/env python3
"""make neg-pnr: bug injection into the soc_top flow and its results (project-plan.md §7.3 P01-P12, plus P00, P13-P54).

usage: neg_pnr.py [--cpu picorv32|hazard3] [--run <dir>] [--out <dir>] [--cases P01,P02,...] [-j N]
The run must pass signoff/scripts/run_guard.py (PASS, made from the commit checked out now): the
cases compare against it ("real run: none", golden, metrics).
--cpu (default picorv32; hazard3: Phase 5, ADR-0011) picks the soc_top run of that CPU (default
runs/soc_top or runs/soc_top_hazard3), its config (pnr/soc_top/config.json or config_hazard3.json),
limits and golden (signoff/limits/<tag>.toml, signoff/golden/<tag>/), and is passed to
check_inputs.py. The checkers are the same code for both CPUs.

Each case changes one thing and must FAIL at the expected checker, with the expected message.
A case that FAILs elsewhere, or does not FAIL, makes neg-pnr FAIL. Cases that need a LibreLane
step re-run one step on a copy of that step's saved config and input state
(`python3 -m librelane.steps run`); nothing in <run> is modified. Outputs: runs/neg_pnr/<case>/
(--cpu hazard3: runs/neg_pnr_hazard3/<case>/).

  step re-runs (the real tools on the real layout)
  P01  signoff SDC + set_clock_uncertainty -setup 30  OpenROAD.STAPostPNR -> Checker.SetupViolations
  P02  signoff SDC + set_clock_uncertainty -hold 5    OpenROAD.STAPostPNR -> Checker.HoldViolations
       (P01-P03 start from the run's SIGNOFF_SDC_FILE, so they test the SDC that signoff really uses)
  P03  signoff SDC + set_max_transition 0.05 ns     OpenROAD.STAPostPNR -> Checker.MaxSlewViolations
  P04  sta_extra_corner.tcl + sram0 derate 10       OpenROAD.STAPostPNR -> Checker.SetupViolations
       (proves STA times the SRAM dout0 arcs of the char .lib: the half-cycle path then needs
       10 times the SRAM read delay, more than half the period)
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
  P30  STA log of nom_ff_n40C_1v95 reading the     check_soc.py sram_lib
       tt_025C_1v80 SRAM .lib
  P32  SRAM .lib copies with the dout0 rising_edge   OpenROAD.STAPostPNR -> Checker.HoldViolations
       arc set to 0 (the read data would change at the clock edge: proves STA checks the hold of
       the register that captures dout0, which the vendor .lib had no arc for; ADR-0010). Positive
       control first: unchanged copies of the five .lib give no hold violation (Phase 3.5 review)
  P08  final netlist: sram0 csb1 on a floating net   check_soc.py port1_tieoff
  P09  final DEF: sram0 moved by 10 um               check_soc.py placement
  P12  metrics: design__instance__count -10 %        check_signoff.py golden comparison
  P31  metrics: final route__drc_errors golden + 1;  check_signoff.py golden comparison
       route__drc_errors__iter:2 golden + tolerance + 1 (each alone; the tolerance is read from the
       limits, 100 PicoRV32, 1310 Hazard3 per ADR-0015, and does not cover the final count);
       positive control: iter:2 golden + 3 (Phase 4 regress 2)
  P13  signoff SDC without its set_output_delay line OpenROAD.STAPostPNR -> check_soc.py sta_setup
       (unconstrained endpoints, project-plan.md §7.2; check_soc.py runs on a fake run whose
       STA directory is the re-run)
  P14  final netlist: sram0 renamed sram9            check_soc.py macro
  P15  disconnected-pin log: 1 critical pin          check_soc.py disconnected
  P16  config.json: one VERILOG_FILES entry dropped  check_inputs.py rtl_files
  P17  char .lib (tt): dout0 rising_edge arc turned  check_inputs.py char_lib, the message is STALE and
       into a second falling_edge arc                names the tt .lib (an extra file in the directory
                                                     also FAILs that row; Phase 3.5 review)
  P18  SRAM LEF: one ANTENNAGATEAREA line dropped    check_inputs.py antenna_lef
  P19  config.json: MACROS lib = the PDK TT .lib     check_inputs.py macro_lib
  P20  resolved.json: MACROS lib = the PDK TT .lib   check_inputs.py --resolved
  P35  config.json: EXTRA_LIBS = the PDK TT SRAM     check_inputs.py other_libs (each variant)
       .lib; or LIB of ss_n40C plus the ss_100C char .lib
  P36  resolved.json: EXTRA_LIBS = the PDK TT .lib   check_inputs.py --resolved
  P33  nom_ss_n40C sta.log: also an extra timing     check_soc.py sram_lib
       library line for the PDK TT SRAM .lib (the way LibreLane logs EXTRA_LIBS; Phase 3.5 review)
  P34  nom_tt sta.log: the tt char .lib of another   check_soc.py sram_lib
       checkout (same file name, other real path)
  P37  the CPU's config: CLOCK_PERIOD + 1 ns          check_inputs.py cpu_config (a flow setting that
       differs between config.json and config_hazard3.json; Phase 5)
  P38  the CPU's config: VERILOG_DEFINES changed      check_inputs.py cpu_config (picorv32: the
       (picorv32: SOC_CPU_HAZARD3 added; hazard3:    PicoRV32 run would build Hazard3; hazard3: it
       removed)                                      would build PicoRV32 from the Hazard3 file list)
  P39  resolved.json: VERILOG_DEFINES changed as P38 check_inputs.py --resolved
  P40  the CPU's config: a2111oi_1 dropped from       check_inputs.py weak_cells, naming a2111oi_1 (the
       EXTRA_EXCLUDED_CELLS                          resizer could again pick a size that cannot drive
                                                     one buffer in ss_100C; Phase 5,
                                                     docs/notes/repair_design_loop.md)
  P41  the CPU's config: DESIGN_REPAIR_MAX_SLEW_PCT   check_inputs.py weak_cells, RepairDesignPostGPL row
       50 (Phase 3 soc_explore6 used 50 after GRT)   (a larger margin makes more cells too weak)
  P42  resolved.json: a2111oi_1 dropped as P40        check_inputs.py --resolved weak_cells_run
       (each case first checks that the edit removed or changed something)
  signoff criteria review (signoff/scripts/review_criteria.py on a copy of the run and of
  <run>_signoff made of symlinks, except the edited file; skill signoff-criteria, Phase 5)
  P43  positive control: no edit                     criteria-review: PASS (no FAIL row)
  P44  the CPU's config: PL_RESIZER_SETUP_SLACK_      review_criteria.py config_applied (the run
       MARGIN + 0.5 ns                               did not use the setting the config has)
  P45  ResizerTimingPostCTS config.json: the three   review_criteria.py step_config (the step did
       ss_n40C corners dropped from RSZ_CORNERS      not receive the resolved value)
  P46  max_ss_n40C_1v60 sta.log of the signoff STA    review_criteria.py uncertainty
       without the clock_uncertainty.sdc line
  P47  the signoff STA without the ff_100C_1v95       review_criteria.py signoff_corners
       directory of the max corner
  P48  <run>_signoff without soc_checks.txt (check_soc.py did not run, as before Phase 5 when
       LibreLane failed)                              review_criteria.py checkers_ran
  P49  ResizerTimingPostGRT log without the         review_criteria.py uncertainty (the repair
       clock_uncertainty.sdc line (ADR-0014)         step after global routing must see it too)
  golden comparison with layout tolerances and optional keys (ADR-0015)
  P50  metrics: design__instance__count__stdcell    within its [golden_layout_tolerance]: PASS;
       golden + tolerance, then + tolerance + 1;     one more: FAIL; the limits with a layout
       limits: "*__count" added as a layout pattern  pattern matching violation counts: FAIL
  P51  metrics: the last route__drc_errors__iter    missing optional key: PASS; missing ordinary
       key removed, then design__instance__count__  key: FAIL; the limits with a corner key as
       class:inverter removed; limits: a corner     optional pattern: FAIL
       key pattern added to [golden_optional]
  CTS without macro latency balancing (ADR-0016; check_soc.py on a fake run that also links the
  log of the Arvinsa.CTSNoInsertionDelay step)
  P52  final netlist: one CTS clock buffer renamed  check_soc.py cts_macro_latency (a delay buffer
       delaybuf_0_clk                                CTS adds before sram0/clk0 when it balances)
  P53  CTS step log without the line of the plugin  check_soc.py cts_macro_latency (the flag did not
       Tcl                                           reach clock_tree_synthesis)
  P54  the CPU's config without substituting_steps  check_soc.py cts_macro_latency (the flow would
                                                     run LibreLane's own OpenROAD.CTS)
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
import tomllib
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "runs", "neg_pnr")   # --out replaces it
LL_DIR = os.environ.get("LIBRELANE_DIR", os.path.join(ROOT, ".tools", "librelane"))
CHECK_SOC = os.path.join(ROOT, "pnr", "soc_top", "check_soc.py")
CHECK_SIGNOFF = os.path.join(ROOT, "signoff", "scripts", "check_signoff.py")
CHECK_INPUTS = os.path.join(ROOT, "pnr", "soc_top", "check_inputs.py")
REVIEW = os.path.join(ROOT, "signoff", "scripts", "review_criteria.py")
# --cpu -> (run tag, config); set_cpu() sets CPU, CONFIG, LIMITS and GOLDEN before the cases run.
TAGS = {"picorv32": ("soc_top", "config.json"), "hazard3": ("soc_top_hazard3", "config_hazard3.json")}
CPU = "picorv32"
CONFIG = os.path.join(ROOT, "pnr", "soc_top", "config.json")
SRAM = "sky130_sram_2kbyte_1rw1r_32x512_8"
SRAM_IP = os.path.join(ROOT, "ip", "sram", SRAM)
PDK_TT_LIB = f"pdk_dir::libs.ref/sky130_sram_macros/lib/{SRAM}_TT_1p8V_25C.lib"
NUM_RE = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
LIMITS = os.path.join(ROOT, "signoff", "limits", "soc_top.toml")
GOLDEN = os.path.join(ROOT, "signoff", "golden", "soc_top", "metrics.json")


def set_cpu(cpu):
    global CPU, CONFIG, LIMITS, GOLDEN
    tag, config = TAGS[cpu]
    CPU = cpu
    CONFIG = os.path.join(ROOT, "pnr", "soc_top", config)
    LIMITS = os.path.join(ROOT, "signoff", "limits", f"{tag}.toml")
    GOLDEN = os.path.join(ROOT, "signoff", "golden", tag, "metrics.json")
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
    new = tcl + ('\nset_timing_derate -late -cell_delay 10 [get_cells sram0]\n'
                 'puts "sta_extra_corner: $corner_name: P04 sram0 -late -cell_delay 10"\n')
    p = os.path.join(d, "sta_extra_corner.tcl")
    open(p, "w").write(new)
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.SetupViolations",
                     edit_config=lambda c: c.update(STA_EXTRA_CORNER_TCL_FILE=p))
    ok = rc not in (0, None) and "Setup violations found" in text and "P04 sram0 -late -cell_delay 10" in text_of(d)
    return ok, "Checker.SetupViolations, and the hook printed the derate 10"


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
    DEF, the disconnected-pin logs, the Magic DRC report, the last signoff STA directory and the
    logs of the CTS step (ADR-0016)."""
    links = links or {}
    fr = os.path.join(d, "run")
    sta = os.path.relpath(step_dir(run, "OpenROAD.STAPostPNR"), run)
    for rel in ["final/nl/soc_top.nl.v", "final/def/soc_top.def", sta] + \
            [os.path.relpath(p, run) for p in glob.glob(os.path.join(run, "*-odb-reportdisconnectedpins", "*.log"))
             + glob.glob(os.path.join(run, "*-magic-drc", "reports", "drc.magic.rpt"))
             + glob.glob(os.path.join(run, "*-arvinsa-ctsnoinsertiondelay", "*.log"))]:
        dst = os.path.join(fr, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel in replace:
            open(dst, "w").write(replace[rel])
        elif rel in links:
            os.symlink(os.path.abspath(links[rel]), dst)
        else:
            os.symlink(os.path.join(run, rel), dst)
    return fr


def check_soc(fr, d, run, config=None):
    cp = subprocess.run([sys.executable, CHECK_SOC, fr, "--config", config or CONFIG, "--sram-drc", sram_drc_alone(run)],
                        capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "a").write(cp.stdout + cp.stderr)
    return cp.returncode, cp.stdout


def soc_case(run, d, row, replace=None, links=None, also=(), config=None):
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
    wrong = f"{SRAM}__tt_025C_1v80.lib"
    rel, sta = sta_dir_with(run, d, "nom_ff_n40C_1v95",
                            lambda t: edit_once(t, re.escape(f"{SRAM}__ff_n40C_1v95.lib"), wrong, "the ff SRAM .lib in sta.log"))
    ok, out = soc_case(run, d, "sram_lib", links={rel: sta})
    return ok and re.search(r"nom_ff_n40C_1v95: \['[^']*/" + re.escape(wrong) + r"'\]", out) is not None, \
        "check_soc.py sram_lib: nom_ff_n40C_1v95 read the tt SRAM .lib (only row FAIL, soc-checks: FAIL)"


def p32(run, d):
    """Hold arc of dout0 set to 0 in copies of the five char .lib; the signoff STA must report hold
    violations, and must not with unchanged copies (positive control, Phase 3.5 review)."""
    libs, same = {}, {}
    for key, paths in json.load(open(CONFIG))["MACROS"][SRAM]["lib"].items():
        src = os.path.join(ROOT, paths[0][len("dir::"):])
        text = open(src).read()
        i = text.index("timing_type : rising_edge;")
        j = text.index("rise_transition", i)
        head, body = text[:i], text[i:j]
        body = re.sub(r'values\(((?:[^()]|\n)*?)\)', lambda m: "values(" + re.sub(NUM_RE, "0.0000", m.group(1)) + ")", body)
        dst = os.path.join(d, os.path.basename(src))
        open(dst, "w").write(head + body + text[j:])
        libs[key] = [dst]
        pos = os.path.join(d, "pos")
        os.makedirs(pos, exist_ok=True)
        shutil.copy(src, os.path.join(pos, os.path.basename(src)))
        same[key] = [os.path.join(pos, os.path.basename(src))]
    rc0, text0 = rerun(run, os.path.join(d, "pos"), "OpenROAD.STAPostPNR", "Checker.HoldViolations",
                       edit_config=lambda c: c["MACROS"][SRAM].update(lib=same))
    if rc0 != 0:
        return False, "positive control: unchanged copies of the .lib must give no hold violation"
    rc, text = rerun(run, d, "OpenROAD.STAPostPNR", "Checker.HoldViolations",
                     edit_config=lambda c: c["MACROS"][SRAM].update(lib=libs))
    ok = rc not in (0, None) and re.search(r"[Hh]old violations found", text) is not None
    return ok, "Checker.HoldViolations: Hold violations found (positive control with unchanged copies: none)"


def p33(run, d):
    """An extra SRAM .lib in one corner's STA, logged the way LibreLane logs EXTRA_LIBS."""
    res = json.load(open(os.path.join(run, "resolved.json")))
    extra = res["PDK_ROOT"] + f"/sky130A/libs.ref/sky130_sram_macros/lib/{SRAM}_TT_1p8V_25C.lib"
    c = "nom_ss_n40C_1v60"
    line = f"Reading cell library for the '{c}' corner at '{os.path.join(SRAM_IP, 'char', f'{SRAM}__ss_n40C_1v60.lib')}'"
    rel, sta = sta_dir_with(run, d, c, lambda t: edit_once(
        t, "^" + re.escape(line) + r"[^\n]*\n", lambda m: m.group(0)
        + f"Reading explicitly-specified extra libs for {c}…\nReading extra timing library for the '{c}' corner at '{extra}'…\n",
        "the ss_n40C SRAM .lib line in sta.log"))
    ok, out = soc_case(run, d, "sram_lib", links={rel: sta})
    return ok and f"{c}: [" in out and f"{SRAM}_TT_1p8V_25C.lib" in out, \
        "check_soc.py sram_lib: nom_ss_n40C_1v60 also read the PDK TT SRAM .lib as an extra library (only row FAIL)"


def p34(run, d):
    """One corner's STA reads an SRAM .lib with the right file name from another checkout."""
    other = os.path.join(d, "other_checkout", "ip", "sram", SRAM, "char")
    shutil.copytree(os.path.join(SRAM_IP, "char"), other)
    c, name = "nom_tt_025C_1v80", f"{SRAM}__tt_025C_1v80.lib"
    rel, sta = sta_dir_with(run, d, c, lambda t: edit_once(t, re.escape(os.path.join(SRAM_IP, "char", name)),
                                                           os.path.join(other, name), "the tt SRAM .lib path in sta.log"))
    ok, out = soc_case(run, d, "sram_lib", links={rel: sta})
    return ok and os.path.join(other, name) in out, \
        "check_soc.py sram_lib: nom_tt_025C_1v80 read the tt .lib of another checkout (only row FAIL)"


def p35(run, d):
    """config.json brings another SRAM .lib in through EXTRA_LIBS, or through LIB."""
    caught = []
    for name, edit in (("EXTRA_LIBS", lambda c: c.update(EXTRA_LIBS=[PDK_TT_LIB])),
                       ("LIB", lambda c: c["LIB"]["*_ss_n40C_1v60"].append(f"dir::ip/sram/{SRAM}/char/{SRAM}__ss_100C_1v60.lib"))):
        sub = os.path.join(d, name)
        os.makedirs(sub)
        rc, out = inputs_check(sub, "--config", config_with(sub, edit))
        caught.append(inputs_failed(rc, out, "other_libs"))
    return all(caught), "check_inputs.py other_libs (EXTRA_LIBS and LIB variants)"


def p36(run, d):
    """The run's resolved.json has EXTRA_LIBS (an SRAM .lib read in every corner)."""
    res = json.load(open(os.path.join(run, "resolved.json")))
    res["EXTRA_LIBS"] = [res["PDK_ROOT"] + f"/sky130A/libs.ref/sky130_sram_macros/lib/{SRAM}_TT_1p8V_25C.lib"]
    p = os.path.join(d, "resolved.json")
    json.dump(res, open(p, "w"), indent=1)
    rc, out = inputs_check(d, "--resolved", p)
    return inputs_failed(rc, out, "resolved"), "check_inputs.py --resolved (EXTRA_LIBS)"


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
    with open(LIMITS, "rb") as f:
        tol = tomllib.load(f).get("golden_tolerance", {}).get("route__drc_errors__iter:*", {}).get("abs")
    if not tol:
        return False, "no abs tolerance for route__drc_errors__iter:* in the limits"
    tol = int(tol)
    results = []
    for name, key, delta, caught in (("final_plus_1", "route__drc_errors", 1, True),
                                     (f"iter2_plus_{tol + 1}", "route__drc_errors__iter:2", tol + 1, True),
                                     ("iter2_plus_3", "route__drc_errors__iter:2", 3, False)):
        sub = os.path.join(d, name)
        os.makedirs(sub)
        rc, out = signoff_with(run, sub, lambda m: m.update({key: golden[key] + delta}))
        row = re.search(rf"^  \[FAIL\] golden {re.escape(key)}:", out, re.M) is not None
        results.append(row == caught and (rc != 0) == caught)
    return all(results), \
        "check_signoff.py golden route__drc_errors and route__drc_errors__iter:2 FAIL; iter:2 + 3 PASS " \
        f"(final +1, iter +{tol + 1}, iter +3: {results})"


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


CTS_DIR = "*-arvinsa-ctsnoinsertiondelay"


def p52(run, d):
    rel = "final/nl/soc_top.nl.v"
    nl = open(os.path.join(run, rel)).read()
    new = edit_once(nl, r"^(\s*sky130_fd_sc_hd__clkbuf_\w+\s+)clkbuf_0_clk(\s*\()", r"\1delaybuf_0_clk\2",
                    "CTS root buffer clkbuf_0_clk")
    ok, _ = soc_case(run, d, "cts_macro_latency", replace={rel: new})
    return ok, "check_soc.py cts_macro_latency: a delaybuf_* instance (only row FAIL, soc-checks: FAIL)"


def p53(run, d):
    line = "[INFO] arvinsa: clock_tree_synthesis -no_insertion_delay"
    logs = [q for q in glob.glob(os.path.join(run, CTS_DIR, "*.log")) if line in open(q).read()]
    if len(logs) != 1:
        return False, f"the plugin line not found in exactly one log of {CTS_DIR}"
    new = "".join(x for x in open(logs[0]).read().splitlines(True) if line not in x)
    ok, _ = soc_case(run, d, "cts_macro_latency", replace={os.path.relpath(logs[0], run): new})
    return ok, "check_soc.py cts_macro_latency: no plugin line in the CTS log (only row FAIL, soc-checks: FAIL)"


def p54(run, d):
    cfg = config_with(d, lambda c: c["meta"].pop("substituting_steps"))
    ok, _ = soc_case(run, d, "cts_macro_latency", config=cfg)
    return ok, "check_soc.py cts_macro_latency: config without substituting_steps (only row FAIL, soc-checks: FAIL)"


def inputs_check(d, *args):
    cp = subprocess.run([sys.executable, CHECK_INPUTS, "--cpu", CPU, *args], capture_output=True, text=True)
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
    char = os.path.join(d, "char")
    shutil.copytree(os.path.join(SRAM_IP, "char"), char)
    f = os.path.join(char, f"{SRAM}__tt_025C_1v80.lib")
    new = edit_once(open(f).read(), "timing_type : rising_edge;", "timing_type : falling_edge;",
                    "the dout0 rising_edge arc")
    open(f, "w").write(new)
    rc, out = inputs_check(d, "--char-dir", char)
    line = re.search(r"^  \[FAIL\] char_lib:[^\n]*", out, re.M)
    ok = inputs_failed(rc, out, "char_lib") and line is not None and "unexpected files" not in line.group(0) \
        and re.search(r"STALE \S*" + re.escape(os.path.basename(f)), line.group(0)) is not None
    return ok, "check_inputs.py char_lib: STALE names the edited tt .lib (not another reason, e.g. an extra file)"


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
    if "*_tt_025C_1v80" not in lib:
        return False, f"unexpected resolved MACROS lib {lib}"
    lib["*_tt_025C_1v80"] = [res["PDK_ROOT"] + f"/sky130A/libs.ref/sky130_sram_macros/lib/{SRAM}_TT_1p8V_25C.lib"]
    p = os.path.join(d, "resolved.json")
    json.dump(res, open(p, "w"), indent=1)
    rc, out = inputs_check(d, "--resolved", p)
    return inputs_failed(rc, out, "resolved"), "check_inputs.py --resolved"


def toggle_define(c):
    """P38/P39 edit: picorv32 gets the Hazard3 define, hazard3 loses it."""
    if CPU == "picorv32":
        c["VERILOG_DEFINES"] = ["SOC_CPU_HAZARD3"]
    else:
        c.pop("VERILOG_DEFINES")


def p37(run, d):
    rc, out = inputs_check(d, "--config", config_with(d, lambda c: c.update(CLOCK_PERIOD=c["CLOCK_PERIOD"] + 1)))
    return inputs_failed(rc, out, "cpu_config"), "check_inputs.py cpu_config (CLOCK_PERIOD differs between the configs)"


def p38(run, d):
    rc, out = inputs_check(d, "--config", config_with(d, toggle_define))
    return inputs_failed(rc, out, "cpu_config"), "check_inputs.py cpu_config (VERILOG_DEFINES)"


def p39(run, d):
    res = json.load(open(os.path.join(run, "resolved.json")))
    toggle_define(res)
    p = os.path.join(d, "resolved.json")
    json.dump(res, open(p, "w"), indent=1)
    rc, out = inputs_check(d, "--resolved", p)
    return inputs_failed(rc, out, "resolved"), "check_inputs.py --resolved (VERILOG_DEFINES)"


WEAK = "sky130_fd_sc_hd__a2111oi_1"


def drop_weak(c):
    """P40/P42 edit: a2111oi_1 out of EXTRA_EXCLUDED_CELLS; False if it was not there."""
    cells = c.get("EXTRA_EXCLUDED_CELLS") or []
    if WEAK not in cells:
        return False
    c["EXTRA_EXCLUDED_CELLS"] = [x for x in cells if x != WEAK]
    return True


def weak_fail_line(out, row):
    m = re.search(rf"^  \[FAIL\] {row}:[^\n]*", out, re.M)
    return m.group(0) if m else ""


def p40(run, d):
    found = []
    rc, out = inputs_check(d, "--config", config_with(d, lambda c: found.append(drop_weak(c))))
    line = weak_fail_line(out, "weak_cells")
    if found != [True]:
        return False, f"{WEAK} is not in EXTRA_EXCLUDED_CELLS of {os.path.basename(CONFIG)} (nothing to drop)"
    return inputs_failed(rc, out, "weak_cells") and "a2111oi_1/Y" in line, \
        "check_inputs.py weak_cells names a2111oi_1/Y"


def p41(run, d):
    rc, out = inputs_check(d, "--config", config_with(d, lambda c: c.update(DESIGN_REPAIR_MAX_SLEW_PCT=50)))
    line = weak_fail_line(out, "weak_cells")
    return inputs_failed(rc, out, "weak_cells") and "RepairDesignPostGPL ss_100C_1v60" in line and "50%" in line, \
        "check_inputs.py weak_cells: RepairDesignPostGPL ss_100C_1v60 at 50%"


def p42(run, d):
    res = json.load(open(os.path.join(run, "resolved.json")))
    if not drop_weak(res):
        return False, f"{WEAK} is not in the run's resolved EXTRA_EXCLUDED_CELLS (run made before the fix?)"
    p = os.path.join(d, "resolved.json")
    json.dump(res, open(p, "w"), indent=1)
    rc, out = inputs_check(d, "--resolved", p)
    line = weak_fail_line(out, "weak_cells_run")
    return inputs_failed(rc, out, "weak_cells_run") and "a2111oi_1/Y" in line and \
        re.search(r"^  \[PASS\] weak_cells:", out, re.M) is not None, \
        "check_inputs.py --resolved weak_cells_run names a2111oi_1/Y (weak_cells on the config still PASS)"


def mirror(src, dst, replace=None, drop=()):
    """dst looks like src: symlinks, except the relative paths in `replace` ({path: new text}),
    written as edited copies, and those in `drop`, left out. Returns dst."""
    replace, drop = replace or {}, set(drop)
    edits = set(replace) | drop

    def walk(rel):
        here = os.path.join(dst, rel)
        os.makedirs(here, exist_ok=True)
        for name in sorted(os.listdir(os.path.join(src, rel))):
            r = os.path.normpath(os.path.join(rel, name))
            if r in drop:
                continue
            if r in replace:
                open(os.path.join(here, name), "w").write(replace[r])
            elif any(e.startswith(r + os.sep) for e in edits):
                walk(r)
            else:
                os.symlink(os.path.join(src, r), os.path.join(here, name))
    walk(".")
    return dst


def review_case(run, d, row, run_replace=None, run_drop=(), out_drop=(), config=None):
    """review_criteria.py on mirrored copies of the run and <run>_signoff: (caught, expect). Caught
    only if the FAIL rows are exactly `row` and the verdict is criteria-review: FAIL (row None: the
    positive control, no FAIL row and criteria-review: PASS)."""
    fr = mirror(run, os.path.join(d, "run"), run_replace, run_drop)
    fo = mirror(run.rstrip("/") + "_signoff", os.path.join(d, "out"), drop=out_drop)
    cp = subprocess.run([sys.executable, REVIEW, "--cpu", CPU, "--run", fr, "--out", fo, "--config", config or CONFIG],
                        capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "a").write(cp.stdout + cp.stderr)
    failed = set(re.findall(r"^  \[FAIL\] (\w+):", cp.stdout, re.M))
    if row is None:
        return cp.returncode == 0 and not failed and "criteria-review: PASS" in cp.stdout, "criteria-review: PASS"
    return cp.returncode != 0 and failed == {row} and "criteria-review: FAIL" in cp.stdout, f"review_criteria.py {row}"


def p43(run, d):
    return review_case(run, d, None)


def p44(run, d):
    return review_case(run, d, "config_applied", config=config_with(
        d, lambda c: c.update(PL_RESIZER_SETUP_SLACK_MARGIN=c["PL_RESIZER_SETUP_SLACK_MARGIN"] + 0.5)))


def p45(run, d):
    rel = os.path.join(os.path.relpath(step_dir(run, "OpenROAD.ResizerTimingPostCTS"), run), "config.json")
    cfg = json.load(open(os.path.join(run, rel)))
    kept = [c for c in cfg["RSZ_CORNERS"] if "ss_n40C" not in c]
    if len(kept) == len(cfg["RSZ_CORNERS"]):
        return False, "no ss_n40C corner in the step's RSZ_CORNERS (run made before ADR-0013?)"
    cfg["RSZ_CORNERS"] = kept
    return review_case(run, d, "step_config", run_replace={rel: json.dumps(cfg, indent=1)})


def p46(run, d):
    rel = os.path.join(os.path.relpath(step_dir(run, "OpenROAD.STAPostPNR"), run), "max_ss_n40C_1v60", "sta.log")
    text = open(os.path.join(run, rel), errors="replace").read()
    new = "".join(ln for ln in text.splitlines(True) if "clock_uncertainty.sdc:" not in ln)
    if new == text:
        return False, f"no clock_uncertainty.sdc line in {rel}"
    return review_case(run, d, "uncertainty", run_replace={rel: new})


def p47(run, d):
    rel = os.path.join(os.path.relpath(step_dir(run, "OpenROAD.STAPostPNR"), run), "max_ff_100C_1v95")
    if not os.path.isdir(os.path.join(run, rel)):
        return False, f"no {rel} in the run"
    return review_case(run, d, "signoff_corners", run_drop=[rel])


def p48(run, d):
    if not os.path.isfile(os.path.join(run.rstrip("/") + "_signoff", "soc_checks.txt")):
        return False, "no soc_checks.txt in the run's signoff directory"
    return review_case(run, d, "checkers_ran", out_drop=["soc_checks.txt"])


def p49(run, d):
    try:
        sd = step_dir(run, "OpenROAD.ResizerTimingPostGRT")
    except FileNotFoundError:
        return False, "no ResizerTimingPostGRT step in the run (run made before ADR-0014?)"
    logs = [lg for lg in glob.glob(os.path.join(sd, "**", "*.log"), recursive=True)
            if "clock_uncertainty.sdc:" in open(lg, errors="replace").read()]
    if not logs:
        return False, f"no clock_uncertainty.sdc line in the logs of {os.path.relpath(sd, run)}"
    edits = {os.path.relpath(lg, run): "".join(ln for ln in open(lg, errors="replace").read().splitlines(True)
                                               if "clock_uncertainty.sdc:" not in ln) for lg in logs}
    return review_case(run, d, "uncertainty", run_replace=edits)


def signoff_limits_with(run, d, edit, table=None, line=None):
    """signoff_with, optionally with `line` added under the [table] header of a copy of LIMITS."""
    if table is None:
        return signoff_with(run, d, edit)
    text = open(LIMITS).read()
    head = f"[{table}]\n"
    if head not in text:
        raise RuntimeError(f"no {head.strip()} in {LIMITS}")
    lim = os.path.join(d, "limits.toml")
    open(lim, "w").write(text.replace(head, head + line + "\n", 1))
    m = json.load(open(os.path.join(run.rstrip("/") + "_signoff", "metrics.json")))
    edit(m)
    p = os.path.join(d, "metrics.json")
    json.dump(m, open(p, "w"), indent=1)
    cp = subprocess.run([sys.executable, CHECK_SIGNOFF, p, lim, GOLDEN], capture_output=True, text=True)
    open(os.path.join(d, "run.log"), "w").write(cp.stdout + cp.stderr)
    return cp.returncode, cp.stdout


def p50(run, d):
    golden = json.load(open(GOLDEN))
    with open(LIMITS, "rb") as f:
        spec = tomllib.load(f).get("golden_layout_tolerance", {}).get("design__instance__count__stdcell")
    if not spec:
        return False, "no design__instance__count__stdcell in [golden_layout_tolerance]"
    key = "design__instance__count__stdcell"
    tol = int(spec.get("abs") or (spec.get("rel") or 0) * golden[key])
    results = []
    for name, delta, table, line, row_re, caught in (
            ("within", tol, None, None, rf"\[FAIL\] golden {key}:", False),
            ("beyond", tol + 1, None, None, rf"\[FAIL\] golden {key}:", True),
            ("violation_pattern", 0, "golden_layout_tolerance", '"*__count" = {rel = 0.5}',
             r"\[FAIL\] golden layout tolerance \*__count:", True)):
        sub = os.path.join(d, name)
        os.makedirs(sub)
        rc, out = signoff_limits_with(run, sub, lambda m: m.update({key: golden[key] + delta}), table, line)
        results.append((re.search(row_re, out) is not None) == caught and (rc != 0) == caught)
    return all(results), f"check_signoff.py layout tolerance: stdcell + {tol} PASS, + {tol + 1} FAIL, a pattern " \
        f"matching violation counts FAIL ({results})"


def p51(run, d):
    golden = json.load(open(GOLDEN))
    iters = sorted((k for k in golden if k.startswith("route__drc_errors__iter:")), key=lambda k: int(k.split(":")[1]))
    if not iters:
        return False, "no route__drc_errors__iter:* key in the golden"
    text = open(LIMITS).read()
    m = re.search(r"^\[golden_optional\]\n(?:#.*\n)*keys = \[", text, re.M)
    if not m:
        return False, f"no [golden_optional] keys = [ in {LIMITS}"
    plain = "design__instance__count__class:inverter"
    results = []
    for name, drop, extra, row_re, caught in (
            ("optional_missing", iters[-1], None, rf"\[FAIL\] golden {re.escape(iters[-1])}:", False),
            ("plain_missing", plain, None, rf"\[FAIL\] golden {re.escape(plain)}:", True),
            ("corner_pattern", None, '"timing__setup__ws__corner:*", ', r"\[FAIL\] golden optional timing__setup__ws__corner", True)):
        sub = os.path.join(d, name)
        os.makedirs(sub)
        if extra:
            lim = os.path.join(sub, "limits.toml")
            open(lim, "w").write(text[:m.end()] + extra + text[m.end():])
            cp = subprocess.run([sys.executable, CHECK_SIGNOFF, os.path.join(run.rstrip("/") + "_signoff", "metrics.json"),
                                 lim, GOLDEN], capture_output=True, text=True)
            open(os.path.join(sub, "run.log"), "w").write(cp.stdout + cp.stderr)
            rc, out = cp.returncode, cp.stdout
        else:
            rc, out = signoff_with(run, sub, lambda m, k=drop: m.pop(k))
        results.append((re.search(row_re, out) is not None) == caught and (rc != 0) == caught)
    return all(results), f"check_signoff.py optional keys: missing {iters[-1]} PASS, missing {plain} FAIL, a corner " \
        f"key pattern FAIL ({results})"


CASES = [("P00", p00), ("P01", p01), ("P02", p02), ("P03", p03), ("P04", p04), ("P05", p05), ("P06", p06), ("P07", p07),
         ("P08", p08), ("P09", p09), ("P10", p10), ("P11", p11), ("P12", p12), ("P13", p13), ("P14", p14),
         ("P15", p15), ("P16", p16), ("P17", p17), ("P18", p18), ("P19", p19), ("P20", p20), ("P21", p21),
         ("P22", p22), ("P23", p23), ("P24", p24), ("P25", p25), ("P26", p26), ("P27", p27), ("P28", p28), ("P29", p29), ("P30", p30),
         ("P31", p31), ("P32", p32), ("P33", p33), ("P34", p34), ("P35", p35), ("P36", p36),
         ("P37", p37), ("P38", p38), ("P39", p39), ("P40", p40), ("P41", p41), ("P42", p42),
         ("P43", p43), ("P44", p44), ("P45", p45), ("P46", p46), ("P47", p47), ("P48", p48), ("P49", p49), ("P50", p50), ("P51", p51),
         ("P52", p52), ("P53", p53), ("P54", p54)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cpu", default="picorv32", choices=sorted(TAGS))
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--cases")
    ap.add_argument("-j", type=int, default=4)
    args = ap.parse_args()
    set_cpu(args.cpu)
    run = os.path.abspath(args.run or os.path.join(ROOT, "runs", TAGS[args.cpu][0]))
    out = os.path.abspath(args.out or (OUT if args.cpu == "picorv32" else f"{OUT}_{args.cpu}"))
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
