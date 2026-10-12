#!/usr/bin/env python3
"""SoC physical checks on a LibreLane run of soc_top or of the Caravel user_project_wrapper (project-plan.md
§5.1, §6.4, §7.2).

usage: check_soc.py <LibreLane run dir> --sram-drc <drc.magic.rpt of the SRAM alone> [--config pnr/soc_top/config.json]
       (run.sh passes the config of its CPU: config.json for PicoRV32, config_hazard3.json for Hazard3;
       pnr/user_project_wrapper/run.sh passes pnr/user_project_wrapper/config.json)
The design is the config's DESIGN_NAME; DESIGNS below gives what differs: the SRAM instance (sram0 in soc_top,
u_soc.sram0 in the flat wrapper, an escaped identifier in the netlist), the clock port, the check_setup
warnings allowed and the static IR supply model of ir_sources.

Checks (each prints a PASS/FAIL row):
  macro        the final netlist has exactly one SRAM macro instance, named sram0
  placement    sram0 in the final DEF is FIXED at the location and orientation of config.json
               MACROS (§7.2 "擺放": the macro must not drift)
  ir_sources   soc_top: the static IR supply model (config VSRC_LOC_FILES, one side only): every source point
               of a net lies on a met5 stripe of that net in the final DEF, every met5 stripe of the
               net has exactly one point, and the voltage column is > 0 for VDD_NETS and 0 for
               GND_NETS. A point that misses its stripe would silently remove a supply (Phase 4).
               user_project_wrapper: the supply comes in from the core ring (ADR-0019 decision 11); that model
               is not implemented yet, so the row FAILs.
  port1_tieoff sram0 port 1 is tied off in the final netlist: csb1 to a tie-high (conb_1 HI),
               addr1[8:0] to tie-low (conb_1 LO) (§5.1); dout1 is left unconnected. clk1 must be
               the system clock: through buffers and an even number of inverters back to the top-level
               port clk, never a constant (OpenRAM latches csb1 on clk1 with no reset; a constant
               clk1 can leave a wordline on after power-up, ADR-0018 decision 9)
  disconnected LibreLane's Odb.ReportDisconnectedPins finds no disconnected pin (log line
               "Found 0 disconnected pin(s), of which 0 are critical." and no table). sram0
               dout1 is connected to the RTL wires unused_sram_dout1[31:0], so it is not reported.
               user_project_wrapper (DESIGNS unused_ports): the fixed Caravel ports the design does
               not use are reported, so the table must list exactly those, on the top module only, and
               0 critical: every input or inout port except the Wishbone inputs and the io_in of the
               GPIOs in an input mode of pin_plan.toml, plus the supply pins no cell uses (cells
               use the first net of VDD_NETS / GND_NETS and the nets of PDN_MACRO_CONNECTIONS). An output port, a used input or a cell pin in the table FAILs, and so does an
               expected unused port that is connected.
  sram_drc_ref the Magic DRC report of the SRAM alone (--sram-drc, made by sram_drc_alone.py) has
               exactly the reviewed rule counts of signoff/waivers/soc_top/sram_magic_drc_baseline.json
               (made with --make-drc-baseline)
  magic_drc    Magic DRC on the full GDS (*-magic-drc/reports/drc.magic.rpt): no violation outside
               the SRAM outline, and every violation inside it is one of the SRAM alone: its box
               lies in the union of the same-rule boxes of the SRAM-alone report, moved to the
               sram0 origin (li.5, diff/tap.9 and, since Phase 6, licon.14 boxes enlarged by DRC_POS_TOL). The SRAM bitcells follow the sky130 SRAM
               rules, so the standard deck flags millions of shapes inside it (project-plan.md
               §6.3). Magic splits the same error into different boxes when the SRAM is checked
               inside soc_top (5,579,161 boxes alone, 4,665,810 inside soc_top), so the boxes are
               compared by area, not one to one. Phase 3 compared only the rule types, which let a
               new violation of an existing rule pass (known limitation 14 of
               docs/phase_exit/phase3.md). The inside count must be at least DRC_IN_MIN_FRAC of the SRAM
               alone: with no SRAM in the checked GDS the row passed with 0 inside (Phase 6).
  sta_setup    OpenSTA `check_setup` (unconstrained endpoints, unclocked registers, missing input
               delays, loops, multiple clocks) in every signoff STA corner: the only allowed warning
               was the unclocked sram0/clk1 while clk1 was tied to 0, before Phase 6 (ADR-0018
               decision 9); now none is allowed in soc_top. The wrapper allows one: the 29 analog_io
               pads of the Caravel template as unconstrained endpoints (no analog circuit; exactly
               that warning with exactly those ports). project-plan.md §7.2
               "no unconstrained endpoint". The section must be present in every corner of
               STA_CORNERS in the config, and no other corner may be there.
  max_slew     in every corner of STA_CORNERS, every max slew violator of <corner>/checks.rpt (the count line
               must be there and match the listed pins) is either an input port with an external transition
               in the design's boundary SDC (DESIGNS boundary_sdc; soc_top has none, so no violator is
               allowed) or a pin on the net of such a port, with a slew of at most that transition +
               BOUNDARY_SLEW_MARGIN. Caravel drives la_oenb, la_data_in, wbs_adr_i, wbs_dat_i at
               0.84-0.97 ns, above the 0.75 ns limit, and nothing inside the wrapper can change that
               (ADR-0019 decision 16); LibreLane's MaxSlewViolations does not fail the wrapper's flow.
  pulse_width  minimum pulse width and minimum period (<corner>/pulse_width.rpt, written by
               sta_extra_corner.tcl with report_check_types) in every corner of STA_CORNERS: both
               tables present and each worst slack >= the required slack printed in the report
               (duty cycle distortion + half-period jitter for the pulse width, period jitter for
               the period; values from clock_uncertainty.sdc). The SRAM clk0 limits are in its
               characterized .lib (ADR-0010).
  macro_gds    scripts/check_macro_gds.py: the SRAM in the final GDS (final/gds, KLayout's stream-out) has
               exactly the cells of the macro GDS of config MACROS, each with the same contents, and no
               renamed copy of one (Phase 6: an OpenRAM LEF without FOREIGN left the SRAM empty there,
               with no flow error; only the Magic/KLayout XOR showed it). Magic's own GDS renames the
               SRAM sub-cells (T2_*, EN_*) and is not the deliverable.
  sram_lib     in every corner of STA_CORNERS, of all the .lib files <corner>/sta.log reads (LibreLane
               logs them as "Reading cell library", "Reading extra timing library" or "Reading timing
               library ... for the '<corner>' corner at '<path>'"), exactly one defines the SRAM cell,
               and its real path is this repo's ip/sram/<macro>/char/<macro>__<pvt>.lib of that
               corner's PVT (ADR-0010); no line names another corner. LibreLane matches the MACROS lib
               wildcards to corners silently; this row shows what STA used. Phase 3.5 review: only
               the first message was read, and only the end of the path compared, so an SRAM .lib
               from EXTRA_LIBS or another checkout passed.
  cts_macro_latency  the config replaces OpenROAD.CTS by Arvinsa.CTSNoInsertionDelay (meta
               substituting_steps, ADR-0016); the run has exactly one step directory of it and none
               of OpenROAD.CTS; its log has the line of pnr/librelane_plugin_arvinsa/
               cts_no_insertion_delay.tcl (clock_tree_synthesis really got -no_insertion_delay);
               step directories are matched with or without a -<n> suffix (a repeated step);
               in the final netlist, at most SRAM_CLK_CHAIN_MAX clock buffers in a row above
               sram0/clk0 drive nothing else (CTS balancing the macro latency puts a chain of
               single-fanout delay buffers there: 11 and 12 on the two balanced Phase 5 runs, 0
               on the runs without; a structural check, so it does not depend on what OpenROAD
               names them), and no instance is named delaybuf_* (cts-clock-tree rule 10)
Prints `soc-checks: PASS` / `soc-checks: FAIL`; exit code 0 only on PASS. Python stdlib only.

usage: check_soc.py --make-drc-baseline <drc.magic.rpt of the SRAM alone> <out.json>
"""
import glob
import json
import os
import re
import subprocess
import sys

MACRO = "arv_sram_2kbyte_1rw1r_32x512_8"   # OpenRAM self-generated (Phase 6, ADR-0018)
INST = "sram0"        # set by main() from DESIGNS; the default is soc_top's
NL_INST = "sram0"     # the instance name as the netlist writes it
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LIB_LINE = re.compile(r"^Reading (?:cell|extra timing|timing) library for the '([^']*)' corner at '(.*?)'", re.M)
CTS_STEP = "Arvinsa.CTSNoInsertionDelay"
CTS_LINE = "[INFO] arvinsa: clock_tree_synthesis -no_insertion_delay"
# The violations inside the SRAM outline must be at least this fraction of the SRAM alone, or the GDS that Magic
# checked has no SRAM in it and the row would pass with nothing to compare (Phase 6: an OpenRAM LEF without FOREIGN
# left the SRAM empty, inside 0). Magic splits the same errors into fewer boxes in soc_top (Phase 4: 4,665,810 of
# 5,579,161, 84 %).
DRC_IN_MIN_FRAC = 0.5
SRAM_CLK_CHAIN_MAX = 2   # single-fanout clock buffers in a row above sram0/clk0 (measured 0 / 11-12)
CLK_BUF = re.compile(r"sky130_fd_sc_hd__(?:clkbuf|buf|clkdlybuf\w*|dlygate\w*|dlymetal\w*|clkinv|clkinvlp|inv)_\d+$")
_DEFINES = {}


def clock_source(nl, pin):
    """(net, inverters) at the top of the buffer/inverter chain above sram0/<pin> (any fanout), or (None, 0)."""
    drv, start = {}, None
    for m in re.finditer(r"^\s*(\S+)\s+(\\\S+|\S+)\s*\((.*?)\);", nl, re.M | re.S):
        cell, name, body = m.groups()
        pins = {k: v.strip() for k, v in re.findall(r"\.(\w+)\(\s*(\\\S+\s|[^()\s]+)\s*\)", body)}
        if CLK_BUF.match(cell) and (pins.get("X") or pins.get("Y")):
            drv[pins.get("X") or pins.get("Y")] = (cell, pins.get("A"))
        if name == NL_INST:
            start = pins.get(pin)
    net, inv, seen = start, 0, set()
    while net in drv and net not in seen:
        seen.add(net)
        cell, net = drv[net]
        inv += "inv" in cell
    return net, inv


def sram_clock_chain(nl):
    """The clock buffers (and inverters) in a row above sram0/clk0 whose output drives nothing else:
    [(instance, cell)], nearest first. A buffer's input pin counts as a load of the net it reads."""
    drv, fanout, clk = {}, {}, None
    for m in re.finditer(r"^\s*(\S+)\s+(\\\S+|\S+)\s*\((.*?)\);", nl, re.M | re.S):
        cell, name, body = m.groups()
        pins = {k: v.strip() for k, v in re.findall(r"\.(\w+)\(\s*(\\\S+\s|[^()\s]+)\s*\)", body)}
        buf = CLK_BUF.match(cell) is not None
        for pin, net in pins.items():
            if not (buf and pin in ("X", "Y")):
                fanout[net] = fanout.get(net, 0) + 1
        if buf and (pins.get("X") or pins.get("Y")):
            drv[pins.get("X") or pins.get("Y")] = (name, cell, pins.get("A"))
        if name == NL_INST:
            clk = pins.get("clk0")
    chain, net = [], clk
    while net in drv and fanout.get(net, 0) == 1 and len(chain) < 1000:
        chain.append(drv[net][:2])
        net = drv[net][2]
    return chain


def defines_sram(path):
    """True if the .lib at path defines the SRAM cell, None if it cannot be read."""
    if path not in _DEFINES:
        try:
            text = open(path, encoding="utf8", errors="replace").read()
            _DEFINES[path] = re.search(r"^\s*cell\s*\(\s*\"?" + re.escape(MACRO) + r"\"?\s*\)", text, re.M) is not None
        except OSError:
            _DEFINES[path] = None
    return _DEFINES[path]
TIE_HI = ["csb1"]
TIE_LO = [f"addr1[{i}]" for i in range(9)]
CLK_PORT = "clk"     # sram0/clk1 must come from it (ADR-0018 decision 9); set by main() from DESIGNS
WIDTH = {"wmask0": 4, "addr0": 9, "din0": 32, "dout0": 32, "addr1": 9, "dout1": 32}




def lef_size(path):
    """(width, height) um of the LEF SIZE of MACRO."""
    m = re.search(r"MACRO\s+" + re.escape(MACRO) + r"\b.*?SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", open(path).read(), re.S)
    return float(m.group(1)), float(m.group(2))


SRAM_W, SRAM_H = lef_size(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ip", "sram", MACRO, f"{MACRO}.lef"))
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "signoff", "waivers",
                        "soc_top", "sram_magic_drc_baseline.json")
# Enlargement (nm) of the SRAM-alone boxes in the position comparison. Measured on the Phase 3
# run (2026-10-04): 4,651,644 of the 4,665,810 boxes inside the SRAM equal an SRAM-alone box,
# 13,935 lie in the union of same-rule SRAM-alone boxes, and the other 231 stick out by up to
# 85 nm (li.5 and diff/tap.9: the same error drawn longer); 100 nm covers all of them. Only those
# two rules get it (Phase 4 review): for the others it would hide a new violation of the same rule
# in a 5-7 times larger area, e.g. li.3 from 0.9 % to 6.5 % of the SRAM.
# Phase 6 (OpenRAM self-generated SRAM, user decision 2026-10-10, ADR-0018 decision 17): licon.14 too. 195 boxes
# on one row inside the SRAM (y = 157.255 um SRAM-local), identical in both CPUs, each touching a same-rule
# SRAM-alone box and sticking out by 60-90 nm (60 nm: 195 unexplained, 90 nm: 0). +100 nm makes licon.14 cover
# 3.32 % of the SRAM instead of 0.65 % (li.5 1.29 %, diff/tap.9 8.71 %).
DRC_POS_TOL = 100
DRC_POS_TOL_RULES = ("(li.5)", "(diff/tap.9)", "(licon.14)")
NUM = re.compile(r"^ (-?[\d.]+)um (-?[\d.]+)um (-?[\d.]+)um (-?[\d.]+)um$")


def magic_boxes(path, info=None):
    """Yield (rule, (x0, y0, x1, y1) in nm) for every box of a LibreLane Magic drc.magic.rpt;
    info["count"] gets the value of the report's COUNT line."""
    rule = None
    with open(path, encoding="utf8", errors="replace") as f:
        next(f, None)                                     # cell name
        for line in f:
            line = line.rstrip("\n")
            m = NUM.match(line)
            if m:
                yield rule, tuple(round(float(v) * 1000) for v in m.groups())
            elif line.startswith("[INFO] COUNT:") and info is not None:
                info["count"] = int(line.split(":")[1])
            elif line and not line.startswith("-") and not line.startswith("[INFO]"):
                rule = line


def union_area(rects):
    """Area of the union of axis-parallel rectangles (x0, y0, x1, y1); few rectangles expected."""
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    area = 0
    for x0, x1 in zip(xs, xs[1:]):
        cov, cur = 0, None
        for a, b in sorted((r[1], r[3]) for r in rects if r[0] <= x0 and r[2] >= x1):
            if cur is None or a > cur[1]:
                cov += cur[1] - cur[0] if cur else 0
                cur = [a, b]
            else:
                cur[1] = max(cur[1], b)
        cov += cur[1] - cur[0] if cur else 0
        area += cov * (x1 - x0)
    return area


def drc_position_compare(alone_rpt, soc_rpt, origin, outline, tol=DRC_POS_TOL):
    """Compare the soc_top report with the SRAM-alone report moved to `origin` (nm).
    Returns (boxes inside outline, boxes outside, unexplained boxes inside [(rule, box)],
    {"exact": .., "by_area": .., "count": COUNT line of the soc_top report})."""
    ox, oy = origin
    rules, exact = {}, set()
    for r, b in magic_boxes(alone_rpt):
        exact.add((rules.setdefault(r, len(rules)), b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy))
    unmatched, n_in, n_out, info = [], 0, 0, {}
    for r, b in magic_boxes(soc_rpt, info):
        if not (b[0] >= outline[0] and b[1] >= outline[1] and b[2] <= outline[2] and b[3] <= outline[3]):
            n_out += 1
            continue
        n_in += 1
        if r not in rules or (rules[r], *b) not in exact:
            unmatched.append((r, b))
    del exact
    g = 2000
    cells = {(r, gx, gy) for r, b in unmatched for gx in range(b[0] // g, b[2] // g + 1)
             for gy in range(b[1] // g, b[3] // g + 1)}
    grid = {}
    for r, b in magic_boxes(alone_rpt):
        e = tol if r.endswith(DRC_POS_TOL_RULES) else 0
        t = (b[0] + ox - e, b[1] + oy - e, b[2] + ox + e, b[3] + oy + e)
        for gx in range(t[0] // g, t[2] // g + 1):
            for gy in range(t[1] // g, t[3] // g + 1):
                if (r, gx, gy) in cells:
                    grid.setdefault((r, gx, gy), []).append(t)
    unexplained = []
    for r, b in unmatched:
        cands = {c for gx in range(b[0] // g, b[2] // g + 1) for gy in range(b[1] // g, b[3] // g + 1)
                 for c in grid.get((r, gx, gy), ())}
        clip = [(max(c[0], b[0]), max(c[1], b[1]), min(c[2], b[2]), min(c[3], b[3])) for c in cands]
        clip = [c for c in clip if c[0] < c[2] and c[1] < c[3]]
        if not (clip and union_area(clip) == (b[2] - b[0]) * (b[3] - b[1])):
            unexplained.append((r, b))
    return n_in, n_out, unexplained, {"exact": n_in - len(unmatched), "by_area": len(unmatched) - len(unexplained),
                                      "count": info.get("count")}


def read_magic_drc(path, outline=None):
    """Parse a LibreLane Magic drc.magic.rpt. Returns ({rule: count of boxes inside `outline`
    (x0, y0, x1, y1 in nm; None = everything)}, number of boxes outside, the COUNT line value)."""
    rules, outside, total, rule = {}, 0, None, None
    num = re.compile(r"^ (-?[\d.]+)um (-?[\d.]+)um (-?[\d.]+)um (-?[\d.]+)um$")
    with open(path, encoding="utf8", errors="replace") as f:
        next(f, None)                                     # cell name
        for line in f:
            line = line.rstrip("\n")
            m = num.match(line)
            if m:
                x0, y0, x1, y1 = (round(float(v) * 1000) for v in m.groups())
                if outline and not (x0 >= outline[0] and y0 >= outline[1] and x1 <= outline[2] and y1 <= outline[3]):
                    outside += 1
                    continue
                rules[rule] = rules.get(rule, 0) + 1
            elif line.startswith("[INFO] COUNT:"):
                total = int(line.split(":")[1])
            elif line and not line.startswith("-") and not line.startswith("[INFO]"):
                rule = line
    return rules, outside, total


# check_setup warnings that are expected: (warning text, sorted tuple of the listed pins); set by main() from DESIGNS
CHECK_SETUP_ALLOWED = set()   # Phase 3-5 allowed the unclocked sram0/clk1 (tied to 0); ADR-0018 decision 9
# What differs between the designs (keyed by the config's DESIGN_NAME).
# max_slew: a pin on a net driven by an input port with an external transition (boundary_sdc) may exceed the
# max transition up to that transition + this margin, the PnR-to-signoff margin of every other net
# (0.70 ns pnr.sdc -> 0.75 ns signoff; ADR-0019 decision 16)
BOUNDARY_SLEW_MARGIN = 0.05
DESIGNS = {
    "soc_top": {"inst": "sram0", "clk_port": "clk", "check_setup_allowed": set(), "ir_model": "met5_left_end",
                "boundary_sdc": None, "unused_ports": None},
    # Phase 7 (ADR-0019): the SoC flat in the wrapper. analog_io[28:0] are pads of the fixed Caravel template with
    # nothing connected (the SoC has no analog circuit), so STA lists them as unconstrained endpoints.
    "user_project_wrapper": {
        "inst": "u_soc.sram0", "clk_port": "wb_clk_i", "ir_model": "core_ring",
        "boundary_sdc": "pnr/user_project_wrapper/caravel_io.sdc",
        # disconnected: the fixed Caravel ports the design leaves unconnected. Used inputs are the Wishbone
        # bus and the io_in of the GPIOs that pin_plan.toml puts in an input mode; every other input or inout
        # port and every supply pin that no cell uses (see the row) must be unconnected, every output connected.
        "unused_ports": {"used_inputs": r"wb_clk_i|wb_rst_i|wbs_\w+_i(\[\d+\])?",
                         "pin_plan": "pnr/user_project_wrapper/pin_plan.toml",
                         "supplies": ["vccd1", "vccd2", "vdda1", "vdda2", "vssa1", "vssa2", "vssd1", "vssd2"]},
        "check_setup_allowed": {("There are 29 unconstrained endpoints.",
                                 tuple(sorted(f"analog_io[{i}]" for i in range(29))))}},
}


def read_check_setup(sta_dir):
    """{corner: [(warning, (listed items...)), ...] or None if the section is missing} from
    <sta_dir>/<corner>/checks.rpt of an OpenROAD.STAPostPNR step."""
    out = {}
    for rpt in sorted(glob.glob(os.path.join(sta_dir, "*", "checks.rpt"))):
        corner = os.path.basename(os.path.dirname(rpt))
        text = open(rpt, encoding="utf8", errors="replace").read()
        m = re.search(r"^check_setup .*?\n=+\n(.*?)(?=^=+\n|\Z)", text, re.M | re.S)
        if not m:
            out[corner] = None
            continue
        warns, cur = [], None
        for line in m.group(1).splitlines():
            if line.startswith("Warning:"):
                cur = [line[len("Warning:"):].strip(), []]
                warns.append(cur)
            elif line.startswith("  ") and cur is not None and line.strip():
                cur[1].append(line.strip())
        out[corner] = [(w, tuple(items)) for w, items in warns]
    return out


def read_input_transitions(path):
    """{port name without index: max input transition in ns} from the SDC's
    `set_input_transition -max <v> [get_ports {<name>[*]}]` lines."""
    out = {}
    for v, name in re.findall(r"^set_input_transition\s+-max\s+([\d.]+)\s+\[get_ports\s+\{?([A-Za-z_]\w*)",
                              open(path, encoding="utf8").read(), re.M):
        out[name] = float(v)
    return out


def read_max_slew(path):
    """(count, [(pin, slew), ...]) of the max slew violators in a <corner>/checks.rpt, or None without the
    `max slew violation count` line."""
    if not os.path.isfile(path):
        return None
    text = open(path, encoding="utf8", errors="replace").read()
    m = re.search(r"^max slew violation count (\d+)$", text, re.M)
    if not m:
        return None
    sec = re.search(r"^max slew\n(.*?)(?=^max (?:fanout|capacitance)\n|^=+\n|^max slew violation count)", text, re.M | re.S)
    viol = [(p, float(sl)) for p, sl in re.findall(r"^(\S+)\s+[\d.]+\s+([\d.]+)\s+-[\d.]+ \(VIOLATED\)", sec.group(1) if sec else "",
                                                   re.M)]
    return int(m.group(1)), viol


def top_ports(nl, top):
    """{bit name: direction} of the ports of module `top` in a Verilog netlist ("input [3:0] a;" -> a[0..3])."""
    m = re.search(rf"\bmodule\s+{re.escape(top)}\b(.*?)\bendmodule\b", nl, re.S)
    ports = {}
    for d, msb, lsb, name in re.findall(r"^\s*(input|output|inout)\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)\s*;",
                                         m.group(1) if m else "", re.M):
        if msb == "":
            ports[name] = d
        else:
            for i in range(min(int(msb), int(lsb)), max(int(msb), int(lsb)) + 1):
                ports[f"{name}[{i}]"] = d
    return ports


def read_disconnected_table(path):
    """Odb.ReportDisconnectedPins full_disconnected_pins_table.txt -> {instance: (disconnected power pins,
    disconnected signal pins)}; a row with an empty first column continues the instance above it."""
    out, inst = {}, None
    for line in open(path, encoding="utf8", errors="replace"):
        cols = [c.strip() for c in line.rstrip("\n").split("\u2502")]
        if len(cols) != 7:
            continue
        inst = cols[1] or inst
        power, signal = out.setdefault(inst, (set(), set()))
        if cols[3]:
            power.add(cols[3])
        if cols[5]:
            signal.add(cols[5])
    return out


def pin_net(nl, inst, pin, cache):
    """Net on <inst>/<pin> in the netlist text (None if not found)."""
    key = (inst, pin)
    if key not in cache:
        name = inst if re.fullmatch(r"[A-Za-z_]\w*", inst) else "\\" + inst + " "
        m = re.search(r"(?:^|\s)" + re.escape(name) + r"\s*\((.*?)\);", nl, re.S)
        c = re.search(r"\." + re.escape(pin) + r"\(\s*([^)]*?)\s*\)", m.group(1)) if m else None
        cache[key] = c.group(1) if c else None
    return cache[key]


def read_pulse_width(path):
    """pulse_width.rpt of sta_extra_corner.tcl: {"required": {"min_pulse_width": x, "min_period": y} or
    None, "min_pulse_width": (pin, slack) or None, "min_period": (pin, slack) or None}; None if the
    file is missing. The tables are those of report_check_types (worst pin of each check)."""
    if not os.path.isfile(path):
        return None
    text = open(path, encoding="utf8", errors="replace").read()
    m = re.search(r"^required_slack min_pulse_width (\S+) min_period (\S+)$", text, re.M)
    out = {"required": {"min_pulse_width": float(m.group(1)), "min_period": float(m.group(2))} if m else None}
    for kind, head in (("min_pulse_width", r"Required\s+Actual\s*\n\s*Pin\s+Width\s+Width\s+Slack"),
                       ("min_period", r"Min\s*\n\s*Pin\s+Period\s+Period\s+Slack")):
        t = re.search(head + r"\s*\n-+\n(\S+(?: \(\w+\))?)\s+\S+\s+\S+\s+(-?[\d.]+) \((?:MET|VIOLATED)\)", text)
        out[kind] = (t.group(1), float(t.group(2))) if t else None
    return out


def met5_stripes(def_text, net):
    """[(y_center, half_width, x0, x1)] in DEF units of the horizontal met5 STRIPE shapes of a special net."""
    sn = def_text[def_text.index("\nSPECIALNETS"):def_text.index("END SPECIALNETS")]
    m = re.search(r"^\s*- " + re.escape(net) + r" .*?;\s*$", sn, re.M | re.S)
    if not m:
        return []
    out = []
    for w, x0, y0, x1, y1 in re.findall(r"(?:ROUTED|NEW) met5 (\d+) \+ SHAPE STRIPE \( (-?\d+) (-?\d+) \) \( (-?\d+|\*) (-?\d+|\*) \)",
                                       m.group(0)):
        y1 = y0 if y1 == "*" else y1
        if y0 == y1:
            out.append((int(y0), int(w) // 2, min(int(x0), int(x1)), max(int(x0), int(x1))))
    return out


def sram_connections(netlist_text):
    """{pin: net} for sram0 in the final netlist (bus connections expanded, MSB first)."""
    m = re.search(re.escape(MACRO) + r"\s+" + re.escape(NL_INST) + r"\s*\((.*?)\);", netlist_text, re.S)
    if not m:
        return None
    conns = {}
    for pin, val in re.findall(r"\.(\w+)\(((?:\{[^}]*\})|[^()]*)\)", m.group(1)):
        val = val.strip()
        if val.startswith("{"):
            bits = [b.strip() for b in val[1:-1].split(",")]
            if len(bits) != WIDTH.get(pin, -1):
                raise ValueError(f"{pin}: {len(bits)} bits, expected {WIDTH.get(pin)}")
            for i, b in enumerate(reversed(bits)):
                conns[f"{pin}[{i}]"] = b
        else:
            conns[pin] = val
    return conns


def tie_nets(netlist_text):
    """(nets driven by conb_1 HI, nets driven by conb_1 LO)."""
    hi, lo = set(), set()
    for body in re.findall(r"sky130_fd_sc_hd__conb_1\s+\S+\s*\((.*?)\);", netlist_text, re.S):
        for pin, net in re.findall(r"\.(HI|LO)\(([^)]*)\)", body):
            (hi if pin == "HI" else lo).add(net.strip())
    return hi, lo


def main(run_dir, config_path, sram_drc):
    global INST, NL_INST, CLK_PORT, CHECK_SETUP_ALLOWED
    rows = []

    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    cfg = json.load(open(config_path, encoding="utf8"))
    design = cfg.get("DESIGN_NAME")
    if design not in DESIGNS:
        print(f"soc-checks: FAIL (DESIGN_NAME {design!r} of {config_path} is not one of {sorted(DESIGNS)})")
        return 1
    dz = DESIGNS[design]
    INST, CLK_PORT, CHECK_SETUP_ALLOWED = dz["inst"], dz["clk_port"], dz["check_setup_allowed"]
    NL_INST = "\\" + INST if "." in INST else INST
    inst_cfg = cfg["MACROS"][MACRO]["instances"][INST]
    nl_path = os.path.join(run_dir, "final", "nl", f"{design}.nl.v")
    def_path = os.path.join(run_dir, "final", "def", f"{design}.def")
    for p in (nl_path, def_path):
        if not os.path.isfile(p):
            print(f"soc-checks: FAIL (missing {p})")
            return 1
    nl = open(nl_path, encoding="utf8").read()

    # macro
    insts = re.findall(re.escape(MACRO) + r"\s+(\S+)\s*\(", nl)
    row("macro", insts == [NL_INST], f"{MACRO} instances in the final netlist: {insts}")

    # placement
    d = open(def_path, encoding="utf8").read()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", d).group(1))
    m = re.search(r"-\s+" + re.escape(INST) + r"\s+" + re.escape(MACRO) + r"\s*\+\s*(\w+)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*(\w+)", d)
    if not m:
        row("placement", False, f"{INST} not found in the COMPONENTS of {def_path}")
    else:
        status, x, y, orient = m.group(1), int(m.group(2)) / units, int(m.group(3)) / units, m.group(4)
        want = (float(inst_cfg["location"][0]), float(inst_cfg["location"][1]), inst_cfg.get("orientation", "N"))
        ok = status == "FIXED" and abs(x - want[0]) < 1e-6 and abs(y - want[1]) < 1e-6 and orient == want[2]
        row("placement", ok, f"{INST} {status} ({x}, {y}) {orient}; config.json ({want[0]}, {want[1]}) {want[2]}")

    # static IR supply model
    if dz["ir_model"] == "core_ring":
        row("ir_sources", False, "the core-ring supply model of ADR-0019 decision 11 is not implemented yet")
    else:
        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
        vsrc = cfg.get("VSRC_LOC_FILES") or {}
        problems = []
        for net in list(cfg.get("VDD_NETS") or []) + list(cfg.get("GND_NETS") or []):
            path = vsrc.get(net)
            path = os.path.join(root, path[len("dir::"):]) if path and path.startswith("dir::") else path
            if not path or not os.path.isfile(path):
                problems.append(f"{net}: no source file ({vsrc.get(net)})")
                continue
            stripes = met5_stripes(d, net)
            pts = [[float(v) for v in line.split(",")] for line in open(path) if line.strip()]
            hits = [[i for i, (yc, hw, x0, x1) in enumerate(stripes)
                     if abs(y * units - yc) <= hw and x0 <= x * units <= x1] for x, y, _, _ in pts]
            volt_ok = all((p[3] > 0) if net in (cfg.get("VDD_NETS") or []) else (p[3] == 0) for p in pts)
            # One side only (the documented model): each source no larger than its stripe is wide, and
            # within one stripe width of the stripe's left end. A larger source or one further in feeds
            # the stripe over a longer stretch, i.e. a more optimistic model (Phase 4 review).
            on = [(p, stripes[h[0]]) for p, h in zip(pts, hits) if len(h) == 1]
            too_big = sum(1 for p, (yc, hw, x0, x1) in on if p[2] * units > 2 * hw)
            not_end = sum(1 for p, (yc, hw, x0, x1) in on if p[0] * units - x0 > 2 * hw)
            if not stripes or any(len(h) != 1 for h in hits) or sorted(h[0] for h in hits) != list(range(len(stripes))) \
                    or not volt_ok or too_big or not_end:
                problems.append(f"{net}: {len(pts)} points for {len(stripes)} met5 stripes, "
                                f"{sum(1 for h in hits if len(h) != 1)} not on exactly one stripe, voltages {'ok' if volt_ok else 'wrong'}, "
                                f"{too_big} larger than the stripe width, {not_end} not at the left end")
        row("ir_sources", bool(vsrc) and not problems,
            f"one source, no larger than the stripe width, at the left end of each met5 stripe of {', '.join(sorted(vsrc))}"
            if vsrc and not problems
            else ("; ".join(problems) if problems else "VSRC_LOC_FILES missing in the config"))

    # port 1 tie-off
    try:
        conns = sram_connections(nl)
        if conns is None:
            row("port1_tieoff", False, f"{MACRO} {INST} not found in the final netlist")
    except ValueError as e:
        conns = None
        row("port1_tieoff", False, f"cannot parse {INST} connections: {e}")
    if conns is not None:
        hi, lo = tie_nets(nl)
        bad = [p for p in TIE_HI if conns.get(p) not in hi] + [p for p in TIE_LO if conns.get(p) not in lo]
        src, inv = clock_source(nl, "clk1")
        if conns.get("clk1") in hi | lo or src != CLK_PORT or inv % 2:
            bad.append(f"clk1 (net {conns.get('clk1')}, from {src} through {inv} inverter(s); must come from {CLK_PORT})")
        row("port1_tieoff", not bad, f"csb1 tie-high, addr1[8:0] tie-low, clk1 from the clock port {CLK_PORT}" if not bad
            else f"not tied as required: {', '.join(p if p.startswith('clk1 ') else f'{p}={conns.get(p)}' for p in bad)}")

    # disconnected pins
    steps = glob.glob(os.path.join(run_dir, "*-odb-reportdisconnectedpins"))
    if len(steps) != 1:
        row("disconnected", False, f"expected one Odb.ReportDisconnectedPins step, found {len(steps)}")
    else:
        logs = glob.glob(os.path.join(steps[0], "*.log"))
        text = "".join(open(f, encoding="utf8", errors="replace").read() for f in logs)
        found = re.findall(r"Found (\d+) disconnected pin\(s\), of which (\d+) are critical", text)
        table = os.path.join(steps[0], "full_disconnected_pins_table.txt")
        up = dz["unused_ports"]
        if up is None:
            ok = found == [("0", "0")] and not os.path.exists(table)
            row("disconnected", ok, f"Odb.ReportDisconnectedPins: {found or 'no result line'}"
                + ("" if not os.path.exists(table) else f"; table {table} exists"))
        else:
            import tomllib
            plan = tomllib.load(open(os.path.join(ROOT, up["pin_plan"]), "rb"))
            used = {f"io_in[{p['gpio']}]" for p in plan.get("pin", []) if "INPUT" in p.get("mode", "")}
            ports = top_ports(nl, design)
            exp_sig = {p for p, d in ports.items() if d != "output"
                       and not re.fullmatch(up["used_inputs"], p) and p not in used}
            # supplies with cell pins on them: the first VDD/GND net (standard cells) and the nets of
            # PDN_MACRO_CONNECTIONS ("inst vdd gnd vdd_pin gnd_pin"); the other pairs only have their core ring
            fed = {(cfg.get("VDD_NETS") or [None])[0], (cfg.get("GND_NETS") or [None])[0]}
            fed |= {n for c in cfg.get("PDN_MACRO_CONNECTIONS") or [] for n in c.split()[1:3]}
            exp_pow = set(up["supplies"]) - fed
            tab = read_disconnected_table(table) if os.path.isfile(table) else {}
            got_pow, got_sig = tab.get(design, (set(), set()))
            others = sorted(i for i in tab if i != design)
            n = len(exp_sig) + len(exp_pow)
            bad = []
            if found != [(str(n), "0")]:
                bad.append(f"result line {found or 'missing'}, expected [('{n}', '0')]")
            if others:
                bad.append(f"instances with disconnected pins: {others[:5]}")
            for what, extra in (("unexpectedly disconnected", (got_sig - exp_sig) | (got_pow - exp_pow)),
                                ("expected unused but connected", (exp_sig - got_sig) | (exp_pow - got_pow))):
                if extra:
                    bad.append(f"{what}: {sorted(extra)[:8]}" + (f" (+{len(extra) - 8})" if len(extra) > 8 else ""))
            row("disconnected", not bad, f"{n} pins unconnected, all of them top-level ports the design does not use "
                f"({len(exp_sig)} signal, {len(exp_pow)} supply; used inputs: Wishbone and {sorted(used)}), 0 critical"
                if not bad else "; ".join(bad))

    # CTS without macro latency balancing (ADR-0016)
    subst = ((cfg.get("meta") or {}).get("substituting_steps")) or {}
    names = os.listdir(run_dir) if os.path.isdir(run_dir) else []
    cts_dirs = [os.path.join(run_dir, n) for n in names if re.fullmatch(r"\d+-arvinsa-ctsnoinsertiondelay(-\d+)?", n)]
    old_dirs = [n for n in names if re.fullmatch(r"\d+-openroad-cts(-\d+)?", n)]
    cts_log = "".join(open(f, encoding="utf8", errors="replace").read()
                      for d in cts_dirs for f in glob.glob(os.path.join(d, "*.log")))
    delaybufs = re.findall(r"^\s*sky130_fd_sc_hd__\w+\s+(delaybuf_\S+)\s*\(", nl, re.M)
    problems = []
    if subst.get("OpenROAD.CTS") != CTS_STEP:
        problems.append(f"config meta substituting_steps OpenROAD.CTS -> {subst.get('OpenROAD.CTS')}, expected {CTS_STEP}")
    if len(cts_dirs) != 1 or old_dirs:
        problems.append(f"{len(cts_dirs)} {CTS_STEP} step(s) and {len(old_dirs)} OpenROAD.CTS step(s) in the run")
    elif CTS_LINE not in cts_log:
        problems.append(f"no '{CTS_LINE}' in the log of {os.path.basename(cts_dirs[0])}")
    if delaybufs:
        problems.append(f"{len(delaybufs)} delaybuf_* instance(s) in the final netlist ({', '.join(delaybufs[:3])})")
    chain = sram_clock_chain(nl)
    if len(chain) > SRAM_CLK_CHAIN_MAX:
        problems.append(f"{len(chain)} single-fanout clock buffers in a row above {INST}/clk0 (max {SRAM_CLK_CHAIN_MAX}: "
                        f"{', '.join(n for n, _ in chain[:3])}, ...)")
    row("cts_macro_latency", not problems, f"CTS step with -no_insertion_delay, 0 delaybuf_* instances, "
        f"{len(chain)} single-fanout clock buffer(s) above {INST}/clk0" if not problems else "; ".join(problems))

    # STA check_setup
    corners = cfg.get("STA_CORNERS") or []
    stas = sorted(glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr")), key=lambda d: int(os.path.basename(d).split("-")[0]))
    cs = read_check_setup(stas[-1]) if stas else {}
    bad = {c: [w for w in ws if (w[0], tuple(sorted(w[1]))) not in CHECK_SETUP_ALLOWED] for c, ws in cs.items() if ws is not None}
    missing = [c for c, ws in cs.items() if ws is None] + sorted(set(corners) - set(cs))
    bad = {c: ws for c, ws in bad.items() if ws}
    ok = bool(corners) and sorted(cs) == sorted(corners) and not missing and not bad
    row("sta_setup", ok, f"check_setup in {len(cs)} corners: no warning"
        + (f" other than the {len(CHECK_SETUP_ALLOWED)} allowed one(s) of {design}" if CHECK_SETUP_ALLOWED else "") if ok else
        f"{len(cs)} corners ({len(corners)} in STA_CORNERS), section missing in {missing}, unexpected warnings {dict(list(bad.items())[:2])}")

    # max slew (ADR-0019 decision 16): every violator in every corner is a pin of a net driven by an input port
    # that has an external transition (the port, or a load on its net), at most that transition + the margin
    trans = read_input_transitions(os.path.join(ROOT, dz["boundary_sdc"])) if dz["boundary_sdc"] else {}
    problems, allowed, excess, cache = [], 0, None, {}
    for c in corners:
        r = read_max_slew(os.path.join(stas[-1], c, "checks.rpt")) if stas else None
        if r is None:
            problems.append(f"{c}: no 'max slew violation count' in checks.rpt")
            continue
        count, viol = r
        if len(viol) != count:
            problems.append(f"{c}: {len(viol)} violators parsed, the report counts {count}")
        for p, sl in viol:
            net = pin_net(nl, *p.rsplit("/", 1), cache) if "/" in p else p
            v = trans.get(re.sub(r"\[.*", "", net or ""))
            if v is None or sl > v + BOUNDARY_SLEW_MARGIN + 1e-9:
                problems.append(f"{c}: {p} {sl} ns" + (f" (net {net}, external transition {v} ns)" if v is not None else
                                                       f" (net {net}: not driven by a port with an external transition)"))
            else:
                allowed += 1
                excess = max(excess if excess is not None else -1e9, sl - v)
    row("max_slew", bool(corners) and not problems,
        f"{len(corners)} corners: " + (f"{allowed} violators, all on nets driven by input ports with an external transition, "
                                       f"at most {excess:+.3f} ns from it (margin {BOUNDARY_SLEW_MARGIN} ns)" if allowed else "no violator")
        if corners and not problems else f"{len(problems)} problem(s), e.g. {'; '.join(problems[:3])}")

    # minimum pulse width and minimum period
    pw = {c: read_pulse_width(os.path.join(stas[-1], c, "pulse_width.rpt")) if stas else None for c in corners}
    problems = []
    for c, r in pw.items():
        if r is None or r["required"] is None or r["min_pulse_width"] is None or r["min_period"] is None:
            problems.append(f"{c}: report or table missing")
            continue
        for kind in ("min_pulse_width", "min_period"):
            pin, slack = r[kind]
            if slack < r["required"][kind]:
                problems.append(f"{c}: {kind} slack {slack} at {pin} < required {r['required'][kind]:.3g}")
    worst = {k: min((r[k][1], r[k][0]) for r in pw.values() if r and r[k]) for k in ("min_pulse_width", "min_period")}         if pw and not any(r is None or r["min_pulse_width"] is None or r["min_period"] is None for r in pw.values()) else {}
    kinds = sorted({k for p in problems for k in ("min_pulse_width", "min_period", "missing") if k in p})
    row("pulse_width", bool(corners) and not problems,
        f"{len(pw)} corners; worst min pulse width slack {worst['min_pulse_width'][0]} ({worst['min_pulse_width'][1]}), "
        f"min period slack {worst['min_period'][0]} ({worst['min_period'][1]}), all >= the required slack"
        if corners and not problems else
        f"{len(problems)} problem(s) [{', '.join(kinds)}], e.g. {'; '.join(problems[:2])}" if corners
        else "STA_CORNERS missing in the config")

    # the SRAM in the final GDS is the macro's own GDS
    mgds = [os.path.join(ROOT, g[len("dir::"):]) if g.startswith("dir::") else g for g in cfg["MACROS"][MACRO].get("gds", [])]
    fgds = os.path.join(run_dir, "final", "gds", f"{design}.gds")
    if len(mgds) != 1 or not os.path.isfile(fgds):
        row("macro_gds", False, f"need one MACROS gds ({mgds}) and {fgds}")
    else:
        cp = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_macro_gds.py"), "--cell", MACRO,
                             "--macro-gds", mgds[0], "--final-gds", fgds], capture_output=True, text=True)
        row("macro_gds", cp.returncode == 0, (cp.stdout.strip() or cp.stderr.strip()[-300:])[:400])

    # SRAM .lib per corner: the STA of corner <rc>_<pvt> reads one SRAM .lib, the characterized one of <pvt>
    problems = []
    for c in corners:
        log = os.path.join(stas[-1], c, "sta.log") if stas else ""
        text = open(log, encoding="utf8", errors="replace").read() if os.path.isfile(log) else None
        if text is None:
            problems.append(f"{c}: no sta.log")
            continue
        lines = LIB_LINE.findall(text)
        other = sorted({cc for cc, _ in lines if cc != c})
        libs = [p for cc, p in lines if cc == c]
        unread = [p for p in libs if defines_sram(p) is None]
        sram = [p for p in libs if defines_sram(p)]
        want = os.path.realpath(os.path.join(ROOT, "ip", "sram", MACRO, "char", f"{MACRO}__{c.split('_', 1)[1]}.lib"))
        if other or unread or len(sram) != 1 or os.path.realpath(sram[0]) != want:
            problems.append(f"{c}: " + (f"lines for corner(s) {other}" if other else f"unreadable {unread}" if unread
                                        else str([p if os.path.realpath(p) != want else os.path.basename(p) for p in sram])))
    row("sram_lib", bool(corners) and not problems,
        f"{len(corners)} corners, each read only the char .lib of its PVT (ADR-0010)" if corners and not problems
        else f"{len(problems)} corner(s) with the wrong SRAM .lib, e.g. {'; '.join(problems[:2])}" if corners
        else "STA_CORNERS missing in the config")

    # Magic DRC (full GDS)
    base = json.load(open(BASELINE, encoding="utf8")) if os.path.isfile(BASELINE) else None
    if base is None or not sram_drc or not os.path.isfile(sram_drc):
        row("sram_drc_ref", False, f"need {BASELINE} and the SRAM-alone report (--sram-drc {sram_drc})")
    else:
        rules, _, total = read_magic_drc(sram_drc)
        ok = rules == base["rules"] and total == base["count"] == sum(rules.values())
        row("sram_drc_ref", ok, f"SRAM alone: {total} violations in {len(rules)} rule types"
            + (", same as the reviewed baseline" if ok else f"; baseline {base['count']} in {len(base['rules'])} rule types"))
    rpts = glob.glob(os.path.join(run_dir, "*-magic-drc", "reports", "drc.magic.rpt"))
    if len(rpts) != 1 or m is None or not sram_drc or not os.path.isfile(sram_drc):
        row("magic_drc", False, f"need one drc.magic.rpt (found {len(rpts)}), the sram0 placement and the SRAM-alone report")
    elif orient != "N":
        row("magic_drc", False, f"position comparison supports orientation N only, sram0 is {orient}")
    else:
        origin = (round(x * 1000), round(y * 1000))
        outline = (origin[0], origin[1], round((x + SRAM_W) * 1000), round((y + SRAM_H) * 1000))
        n_in, outside, unexplained, how = drc_position_compare(sram_drc, rpts[0], origin, outline)
        total = how["count"]
        alone = read_magic_drc(sram_drc)[2]
        enough = n_in >= DRC_IN_MIN_FRAC * alone
        ok = outside == 0 and not unexplained and total == n_in + outside and enough
        ex = "; ".join(f"{r!r} at ({b[0] / 1000}, {b[1] / 1000})-({b[2] / 1000}, {b[3] / 1000}) um" for r, b in unexplained[:2])
        row("magic_drc", ok, f"{outside} violations outside the SRAM outline; inside {n_in}, "
            + (f"all at the position of a violation of the SRAM alone ({how['exact']} identical boxes, "
               f"{how['by_area']} in the union of same-rule boxes, {DRC_POS_TOL} nm wider for {' '.join(DRC_POS_TOL_RULES)})"
               if not unexplained else
               f"{len(unexplained)} not at the position of a same-rule violation of the SRAM alone "
               f"[rules: {' | '.join(sorted({r for r, _ in unexplained}))}], e.g. {ex}")
            + ("" if total == n_in + outside else f"; report COUNT {total} != {n_in + outside} parsed")
            + ("" if enough else f"; only {n_in} inside, < {DRC_IN_MIN_FRAC:.0%} of the SRAM alone ({alone}): "
               f"the SRAM is missing from the checked GDS"))

    ok = all(rows) and rows
    print(f"soc-checks: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def make_baseline(rpt, out):
    rules, _, total = read_magic_drc(rpt)
    n = sum(rules.values())
    if total != n:
        print(f"check_soc: FAIL - report COUNT {total} != {n} parsed boxes")
        return 1
    json.dump({"source": "Magic DRC (LibreLane 3.0.14 Magic.DRC step, MAGIC_DRC_USE_GDS = true) on the GDS of "
               f"{MACRO} alone, the one config.json MACROS names (pnr/soc_top/README.md)", "count": n, "rules": rules},
              open(out, "w"), indent=1, sort_keys=True)
    print(f"check_soc: wrote {out} ({n} violations in {len(rules)} rule types)")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--make-drc-baseline"] and len(args) == 3:
        sys.exit(make_baseline(args[1], args[2]))
    opts = {"--config": "pnr/soc_top/config.json", "--sram-drc": None}
    for opt in opts:
        if opt in args:
            i = args.index(opt)
            opts[opt] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(args[0], opts["--config"], opts["--sram-drc"]))
