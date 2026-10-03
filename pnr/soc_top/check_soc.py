#!/usr/bin/env python3
"""soc_top-specific physical checks on a LibreLane run (project-plan.md §5.1, §6.4, §7.2).

usage: check_soc.py <LibreLane run dir> [--config pnr/soc_top/config.json]

Checks (each prints a PASS/FAIL row):
  macro        the final netlist has exactly one SRAM macro instance, named sram0
  placement    sram0 in the final DEF is FIXED at the location and orientation of config.json
               MACROS (§7.2 "擺放": the macro must not drift)
  port1_tieoff sram0 port 1 is tied off in the final netlist: csb1 to a tie-high (conb_1 HI),
               clk1 and addr1[8:0] to tie-low (conb_1 LO) (§5.1); dout1 is left unconnected
  disconnected LibreLane's Odb.ReportDisconnectedPins finds no disconnected pin (log line
               "Found 0 disconnected pin(s), of which 0 are critical." and no table). sram0
               dout1 is connected to the RTL wires unused_sram_dout1[31:0], so it is not reported.
  magic_drc    Magic DRC on the full GDS (*-magic-drc/reports/drc.magic.rpt): no violation outside
               the SRAM outline, and inside it only rule types that the SRAM checked alone also
               violates (signoff/waivers/soc_top/sram_magic_drc_baseline.json, made with
               --make-drc-baseline). The SRAM bitcells follow the sky130 SRAM rules, so the standard
               deck flags millions of shapes inside it (project-plan.md §6.3). The number inside
               is compared with the golden run by check_signoff.py (magic__drc_error__count); the
               SRAM-alone count cannot be compared directly, because Magic splits the same error
               into different boxes when the SRAM is checked inside soc_top (README.md).
  sta_setup    OpenSTA `check_setup` (unconstrained endpoints, unclocked registers, missing input
               delays, loops, multiple clocks) in every signoff STA corner: the only allowed warning
               is the unclocked sram0/clk1 (port 1 clock tied to 0). project-plan.md §7.2
               "no unconstrained endpoint". The section must be present in all 9 corners.
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


def main(run_dir, config_path):
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

    # port 1 tie-off
    try:
        conns = sram_connections(nl)
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
    stas = sorted(glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr")), key=lambda d: int(os.path.basename(d).split("-")[0]))
    cs = read_check_setup(stas[-1]) if stas else {}
    bad = {c: [w for w in ws if w not in CHECK_SETUP_ALLOWED] for c, ws in cs.items() if ws is not None}
    missing = [c for c, ws in cs.items() if ws is None]
    bad = {c: ws for c, ws in bad.items() if ws}
    ok = len(cs) == 9 and not missing and not bad
    row("sta_setup", ok, f"check_setup in {len(cs)} corners: only the expected unclocked sram0/clk1" if ok else
        f"{len(cs)} corners, section missing in {missing}, unexpected warnings {dict(list(bad.items())[:2])}")

    # Magic DRC (full GDS)
    rpts = glob.glob(os.path.join(run_dir, "*-magic-drc", "reports", "drc.magic.rpt"))
    if len(rpts) != 1 or m is None or not os.path.isfile(BASELINE):
        row("magic_drc", False, f"need one drc.magic.rpt (found {len(rpts)}), the sram0 placement and {BASELINE}")
    elif orient != "N":
        row("magic_drc", False, f"baseline comparison supports orientation N only, sram0 is {orient}")
    else:
        outline = (round(x * 1000), round(y * 1000), round((x + SRAM_W) * 1000), round((y + SRAM_H) * 1000))
        inside, outside, total = read_magic_drc(rpts[0], outline)
        base = json.load(open(BASELINE, encoding="utf8"))["rules"]
        new_rules = sorted(set(inside) - set(base))
        n_in = sum(inside.values())
        ok = outside == 0 and not new_rules and total == n_in + outside
        row("magic_drc", ok, f"{outside} violations outside the SRAM outline; inside {n_in} in {len(inside)} rule types"
            + (", all also violated by the SRAM alone" if not new_rules else f"; {len(new_rules)} rule type(s) not violated by the SRAM alone, e.g. {new_rules[0]!r}")
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
    cfg_path = "pnr/soc_top/config.json"
    if "--config" in args:
        i = args.index("--config")
        cfg_path = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(args[0], cfg_path))
