#!/usr/bin/env python3
"""soc_top-specific physical checks on a LibreLane run (project-plan.md §5.1, §6.4, §7.2).

usage: check_soc.py <LibreLane run dir> --sram-drc <drc.magic.rpt of the SRAM alone> [--config pnr/soc_top/config.json]

Checks (each prints a PASS/FAIL row):
  macro        the final netlist has exactly one SRAM macro instance, named sram0
  placement    sram0 in the final DEF is FIXED at the location and orientation of config.json
               MACROS (§7.2 "擺放": the macro must not drift)
  ir_sources   the static IR supply model (config VSRC_LOC_FILES, one side only): every source point
               of a net lies on a met5 stripe of that net in the final DEF, every met5 stripe of the
               net has exactly one point, and the voltage column is > 0 for VDD_NETS and 0 for
               GND_NETS. A point that misses its stripe would silently remove a supply (Phase 4).
  port1_tieoff sram0 port 1 is tied off in the final netlist: csb1 to a tie-high (conb_1 HI),
               clk1 and addr1[8:0] to tie-low (conb_1 LO) (§5.1); dout1 is left unconnected
  disconnected LibreLane's Odb.ReportDisconnectedPins finds no disconnected pin (log line
               "Found 0 disconnected pin(s), of which 0 are critical." and no table). sram0
               dout1 is connected to the RTL wires unused_sram_dout1[31:0], so it is not reported.
  sram_drc_ref the Magic DRC report of the SRAM alone (--sram-drc, made by sram_drc_alone.py) has
               exactly the reviewed rule counts of signoff/waivers/soc_top/sram_magic_drc_baseline.json
               (made with --make-drc-baseline)
  magic_drc    Magic DRC on the full GDS (*-magic-drc/reports/drc.magic.rpt): no violation outside
               the SRAM outline, and every violation inside it is one of the SRAM alone: its box
               lies in the union of the same-rule boxes of the SRAM-alone report, moved to the
               sram0 origin (li.5 and diff/tap.9 boxes enlarged by DRC_POS_TOL). The SRAM bitcells follow the sky130 SRAM
               rules, so the standard deck flags millions of shapes inside it (project-plan.md
               §6.3). Magic splits the same error into different boxes when the SRAM is checked
               inside soc_top (5,579,161 boxes alone, 4,665,810 inside soc_top), so the boxes are
               compared by area, not one to one. Phase 3 compared only the rule types, which let a
               new violation of an existing rule pass (known limitation 14 of
               docs/phase_exit/phase3.md).
  sta_setup    OpenSTA `check_setup` (unconstrained endpoints, unclocked registers, missing input
               delays, loops, multiple clocks) in every signoff STA corner: the only allowed warning
               is the unclocked sram0/clk1 (port 1 clock tied to 0). project-plan.md §7.2
               "no unconstrained endpoint". The section must be present in every corner of
               STA_CORNERS in the config, and no other corner may be there.
  pulse_width  minimum pulse width and minimum period (<corner>/pulse_width.rpt, written by
               sta_extra_corner.tcl with report_check_types) in every corner of STA_CORNERS: both
               tables present and each worst slack >= the required slack printed in the report
               (duty cycle distortion + half-period jitter for the pulse width, period jitter for
               the period; values from clock_uncertainty.sdc). The SRAM clk0 needs >= 12 ns high and
               low and a period >= 30 ns (padded.lib).
  sram_derate  the SRAM derate of sta_extra_corner.tcl in every corner of STA_CORNERS: exactly one
               line in <corner>/sta.log, `-late -cell_delay 1.575` for ss, `-early -cell_delay 0.665`
               for ff, `no derate` for tt (ADR-0007, user decision 2026-10-04). P04 shows the ss
               derate changes the timing; this row shows the hook ran with the right value in each
               corner, including the ff early derate that no timing check depends on today.
Prints `soc-checks: PASS` / `soc-checks: FAIL`; exit code 0 only on PASS. Python stdlib only.

usage: check_soc.py --make-drc-baseline <drc.magic.rpt of the SRAM alone> <out.json>
"""
import glob
import json
import os
import re
import sys

MACRO = "sky130_sram_2kbyte_1rw1r_32x512_8"
INST = "sram0"
TIE_HI = ["csb1"]
TIE_LO = ["clk1"] + [f"addr1[{i}]" for i in range(9)]
WIDTH = {"wmask0": 4, "addr0": 9, "din0": 32, "dout0": 32, "addr1": 9, "dout1": 32}


SRAM_W, SRAM_H = 683.1, 416.54   # LEF SIZE
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "signoff", "waivers",
                        "soc_top", "sram_magic_drc_baseline.json")
# Enlargement (nm) of the SRAM-alone boxes in the position comparison. Measured on the Phase 3
# run (2026-10-04): 4,651,644 of the 4,665,810 boxes inside the SRAM equal an SRAM-alone box,
# 13,935 lie in the union of same-rule SRAM-alone boxes, and the other 231 stick out by up to
# 85 nm (li.5 and diff/tap.9: the same error drawn longer); 100 nm covers all of them. Only those
# two rules get it (Phase 4 review): for the others it would hide a new violation of the same rule
# in a 5-7 times larger area, e.g. li.3 from 0.9 % to 6.5 % of the SRAM.
DRC_POS_TOL = 100
DRC_POS_TOL_RULES = ("(li.5)", "(diff/tap.9)")
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


# check_setup warnings that are expected in soc_top: (warning text, set of listed pins)
CHECK_SETUP_ALLOWED = {("There is 1 unclocked register/latch pin.", ("sram0/clk1",))}


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
    m = re.search(re.escape(MACRO) + r"\s+" + INST + r"\s*\((.*?)\);", netlist_text, re.S)
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
    rows = []

    def row(name, ok, msg):
        rows.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {msg}")

    cfg = json.load(open(config_path, encoding="utf8"))
    inst_cfg = cfg["MACROS"][MACRO]["instances"][INST]
    nl_path = os.path.join(run_dir, "final", "nl", "soc_top.nl.v")
    def_path = os.path.join(run_dir, "final", "def", "soc_top.def")
    for p in (nl_path, def_path):
        if not os.path.isfile(p):
            print(f"soc-checks: FAIL (missing {p})")
            return 1
    nl = open(nl_path, encoding="utf8").read()

    # macro
    insts = re.findall(re.escape(MACRO) + r"\s+(\S+)\s*\(", nl)
    row("macro", insts == [INST], f"{MACRO} instances in the final netlist: {insts}")

    # placement
    d = open(def_path, encoding="utf8").read()
    units = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", d).group(1))
    m = re.search(r"-\s+" + INST + r"\s+" + re.escape(MACRO) + r"\s*\+\s*(\w+)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*(\w+)", d)
    if not m:
        row("placement", False, f"{INST} not found in the COMPONENTS of {def_path}")
    else:
        status, x, y, orient = m.group(1), int(m.group(2)) / units, int(m.group(3)) / units, m.group(4)
        want = (float(inst_cfg["location"][0]), float(inst_cfg["location"][1]), inst_cfg.get("orientation", "N"))
        ok = status == "FIXED" and abs(x - want[0]) < 1e-6 and abs(y - want[1]) < 1e-6 and orient == want[2]
        row("placement", ok, f"{INST} {status} ({x}, {y}) {orient}; config.json ({want[0]}, {want[1]}) {want[2]}")

    # static IR supply model
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
        row("port1_tieoff", not bad, "csb1 tie-high, clk1 and addr1[8:0] tie-low" if not bad
            else f"not tied as required: {', '.join(f'{p}={conns.get(p)}' for p in bad)}")

    # disconnected pins
    steps = glob.glob(os.path.join(run_dir, "*-odb-reportdisconnectedpins"))
    if len(steps) != 1:
        row("disconnected", False, f"expected one Odb.ReportDisconnectedPins step, found {len(steps)}")
    else:
        logs = glob.glob(os.path.join(steps[0], "*.log"))
        text = "".join(open(f, encoding="utf8", errors="replace").read() for f in logs)
        found = re.findall(r"Found (\d+) disconnected pin\(s\), of which (\d+) are critical", text)
        table = os.path.join(steps[0], "full_disconnected_pins_table.txt")
        ok = found == [("0", "0")] and not os.path.exists(table)
        row("disconnected", ok, f"Odb.ReportDisconnectedPins: {found or 'no result line'}"
            + ("" if not os.path.exists(table) else f"; table {table} exists"))

    # STA check_setup
    corners = cfg.get("STA_CORNERS") or []
    stas = sorted(glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr")), key=lambda d: int(os.path.basename(d).split("-")[0]))
    cs = read_check_setup(stas[-1]) if stas else {}
    bad = {c: [w for w in ws if w not in CHECK_SETUP_ALLOWED] for c, ws in cs.items() if ws is not None}
    missing = [c for c, ws in cs.items() if ws is None] + sorted(set(corners) - set(cs))
    bad = {c: ws for c, ws in bad.items() if ws}
    ok = bool(corners) and sorted(cs) == sorted(corners) and not missing and not bad
    row("sta_setup", ok, f"check_setup in {len(cs)} corners: only the expected unclocked sram0/clk1" if ok else
        f"{len(cs)} corners ({len(corners)} in STA_CORNERS), section missing in {missing}, unexpected warnings {dict(list(bad.items())[:2])}")

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

    # SRAM derate per corner (sta_extra_corner.tcl)
    want = {"ss": "-late -cell_delay 1.575", "ff": "-early -cell_delay 0.665", "tt": "no derate"}
    problems = []
    for c in corners:
        log = os.path.join(stas[-1], c, "sta.log") if stas else ""
        lines = re.findall(r"^sta_extra_corner: " + re.escape(c) + r": sram0 (.*?)\s*$",
                           open(log, encoding="utf8", errors="replace").read(), re.M) if os.path.isfile(log) else None
        kind = c.split("_")[1] if c.count("_") >= 2 else None
        if kind not in want or lines != [want[kind]]:
            problems.append(f"{c}: {lines if lines is not None else 'no sta.log'}")
    row("sram_derate", bool(corners) and not problems,
        f"{len(corners)} corners: ss {want['ss']}, ff {want['ff']}, tt {want['tt']}" if corners and not problems
        else f"{len(problems)} corner(s) without the expected line, e.g. {'; '.join(problems[:2])}" if corners
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
        ok = outside == 0 and not unexplained and total == n_in + outside
        ex = "; ".join(f"{r!r} at ({b[0] / 1000}, {b[1] / 1000})-({b[2] / 1000}, {b[3] / 1000}) um" for r, b in unexplained[:2])
        row("magic_drc", ok, f"{outside} violations outside the SRAM outline; inside {n_in}, "
            + (f"all at the position of a violation of the SRAM alone ({how['exact']} identical boxes, "
               f"{how['by_area']} in the union of same-rule boxes, {DRC_POS_TOL} nm wider for {' '.join(DRC_POS_TOL_RULES)})"
               if not unexplained else
               f"{len(unexplained)} not at the position of a same-rule violation of the SRAM alone "
               f"[rules: {' | '.join(sorted({r for r, _ in unexplained}))}], e.g. {ex}")
            + ("" if total == n_in + outside else f"; report COUNT {total} != {n_in + outside} parsed"))

    ok = all(rows) and rows
    print(f"soc-checks: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def make_baseline(rpt, out):
    rules, _, total = read_magic_drc(rpt)
    n = sum(rules.values())
    if total != n:
        print(f"check_soc: FAIL - report COUNT {total} != {n} parsed boxes")
        return 1
    json.dump({"source": "Magic DRC (LibreLane 3.0.14 Magic.DRC step, MAGIC_DRC_USE_GDS = true) on the PDK GDS of "
               f"{MACRO} alone (pnr/soc_top/README.md)", "count": n, "rules": rules},
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
