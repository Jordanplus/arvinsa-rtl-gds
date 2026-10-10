#!/usr/bin/env python3
"""Generate the SRAM LEF used by the flow: the PDK LEF plus ANTENNAGATEAREA on every input pin.

The PDK LEF of this macro has no antenna data, so OpenROAD's antenna checker and repair cannot
see the nets that end on SRAM inputs (project-plan.md §6.4, R6). This script copies the PDK LEF
and adds `ANTENNAGATEAREA <um^2> ;` after `DIRECTION INPUT ;` of each input pin. The area is the
transistor gate area (sum of W*L) connected to that pin inside the macro, computed from the
macro's own SPICE netlist by gate_area.py: 0.6 um^2 for 57 pins (D input of the OpenRAM DFF:
nfet W=1 + pfet W=3, L=0.15) and 0.168 um^2 for clk0/clk1. Geometry, pins and obstructions are
unchanged (the GDS is still the PDK one). docs/decisions/0008-sram-antenna-lef.md.

The macro name comes from the LEF (`MACRO <name>`). The input pins come from the netlist's `*.PININFO`
line; a netlist without one (OpenRAM dev, Phase 6 self-generated macro) uses the LEF's `DIRECTION INPUT`
pins instead (check_macro_views.py has compared them with the Verilog model), each of which must be a port
of the netlist's top subckt.

A LEF with `DATABASE MICRONS` above TECH_DBU (OpenRAM dev writes 2000; sky130's tech LEF has 1000) is
rewritten to TECH_DBU: OpenROAD discards it otherwise ("[ODB-0292] LEF data from ... is discarded due to
errors" after ODB-0205). Every coordinate must lie on the 1/TECH_DBU um grid, or the script FAILs (the
rewrite would move a shape); OpenRAM's sky130 LEF is on the 0.005 um manufacturing grid.

A LEF without `FOREIGN <macro> ;` gets one after its CLASS line. LibreLane's KLayout stream-out builds the
macro cell from the LEF, clears it, then merges the macro GDS; without FOREIGN the LEF cell is not a ghost
cell, the GDS cell of the same name is renamed (KLAYOUT_CONFLICT_RESOLUTION RenameCell) and dropped, and
the final GDS has an empty macro with no error (Phase 6, 2026-10-10: XOR 5.69 million; OpenRAM dev writes no
FOREIGN, the PDK's prebuilt LEF has one).

Usage: gen_antenna_lef.py <pdk.lef> <pdk.spice> <out.lef> [--check]
  --check   exit 1 if <out.lef> differs from what would be generated (stale copy)
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gate_area  # noqa: E402

TECH_DBU = 1000   # sky130 tech LEF: DATABASE MICRONS 1000


def tech_units(lef):
    """The LEF with DATABASE MICRONS <= TECH_DBU (lossless, or FAIL)."""
    m = re.search(r"^(\s*DATABASE\s+MICRONS\s+)(\d+)(\s*;)", lef, re.M)
    if not m or int(m.group(2)) <= TECH_DBU:
        return lef
    body = lef.split("END UNITS", 1)[-1]
    off = [x for x in re.findall(r"(?<![\w.])-?\d+\.\d+", body) if abs(float(x) * TECH_DBU - round(float(x) * TECH_DBU)) > 1e-6]
    if off:
        raise SystemExit(f"gen_antenna_lef: FAIL - DATABASE MICRONS {m.group(2)} and {len(off)} coordinate(s) off the "
                         f"1/{TECH_DBU} um grid (e.g. {off[:3]}); cannot rewrite to {TECH_DBU} without moving shapes")
    return lef[:m.start(2)] + str(TECH_DBU) + lef[m.end(2):]


def add_foreign(lef, macro):
    """The LEF with `FOREIGN <macro> ;` after the CLASS line of the macro, if it has none."""
    if re.search(r"^\s*FOREIGN\s+" + re.escape(macro) + r"\b", lef, re.M):
        return lef
    new, n = re.subn(r"^(\s*MACRO\s+" + re.escape(macro) + r"\s*\n(\s*)CLASS[^\n]*\n)", r"\1\2FOREIGN " + macro + " ;\n",
                     lef, count=1, flags=re.M)
    if n != 1:
        raise SystemExit(f"gen_antenna_lef: FAIL - no CLASS line right after MACRO {macro} to put FOREIGN after")
    return new


def lef_macro(lef):
    names = re.findall(r"^\s*MACRO\s+(\S+)", lef, re.M)
    if len(names) != 1:
        raise SystemExit(f"gen_antenna_lef: FAIL - expected one MACRO in the LEF, found {names}")
    return names[0]


def lef_inputs(lef):
    """Input pins of the LEF (bus bits as in the LEF, e.g. din0[3])."""
    out, pin = [], None
    for line in lef.splitlines():
        m = re.match(r"\s*PIN\s+(\S+)", line)
        if m:
            pin = m.group(1)
        elif pin and re.match(r"\s*DIRECTION\s+INPUT\s*;", line):
            out.append(pin)
    return out


def transform(lef, areas, rescaled=False, foreign=False):
    out, done = [], set()
    pin = None
    for line in lef.splitlines(keepends=True):
        m = re.match(r"\s*PIN\s+(\S+)", line)
        if m:
            pin = m.group(1)
        elif re.match(r"\s*END\s+\S+", line) and pin and line.split()[1] == pin:
            pin = None
        out.append(line)
        if pin and re.match(r"\s*DIRECTION\s+INPUT\s*;", line):
            if pin not in areas:
                raise SystemExit(f"gen_antenna_lef: FAIL - input pin {pin} has no gate area in the SPICE netlist")
            if areas[pin] <= 0:
                raise SystemExit(f"gen_antenna_lef: FAIL - input pin {pin} has gate area {areas[pin]}")
            indent = re.match(r"(\s*)", line).group(1)
            out.append(f"{indent}ANTENNAGATEAREA {areas[pin]:.4f} ;\n")
            done.add(pin)
    missing = sorted(set(areas) - done)
    if missing:
        raise SystemExit(f"gen_antenna_lef: FAIL - input pins of the SPICE netlist not found as LEF inputs: {missing}")
    header = ("# GENERATED by ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_antenna_lef.py from the PDK LEF and SPICE.\n"
              "# Adds ANTENNAGATEAREA to the input pins; nothing else differs. Do not edit by hand.\n")
    if rescaled:
        header += f"# DATABASE MICRONS rewritten to {TECH_DBU} (every coordinate is on that grid; OpenROAD ODB-0292).\n"
    if foreign:
        header += "# FOREIGN added (KLayout stream-out would otherwise leave the macro empty in the final GDS).\n"
    return header + "".join(out)


def main(argv):
    if len(argv) not in (4, 5) or (len(argv) == 5 and argv[4] != "--check"):
        print(__doc__)
        return 2
    lef, spice, dst = pathlib.Path(argv[1]), pathlib.Path(argv[2]), pathlib.Path(argv[3])
    raw = lef.read_text(encoding="utf-8")
    text = tech_units(raw)
    macro = lef_macro(text)
    text = add_foreign(text, macro)
    sc = gate_area.parse(str(spice))
    if macro not in sc:
        raise SystemExit(f"gen_antenna_lef: FAIL - no .SUBCKT {macro} in {spice}")
    ga = gate_area.gate_areas(sc, macro)
    try:
        pins = gate_area.inputs(str(spice), macro)
    except ValueError:
        pins = lef_inputs(text)
        missing = sorted(set(pins) - set(sc[macro]["ports"]))
        if missing or not pins:
            raise SystemExit(f"gen_antenna_lef: FAIL - LEF input pins not ports of {macro} in {spice}: {missing or 'none'}")
    areas = {p: ga.get(p, 0.0) for p in pins}
    want = transform(text, areas, rescaled="DATABASE MICRONS 2000" in raw and "DATABASE MICRONS 2000" not in text,
                     foreign="FOREIGN" not in raw)
    if len(argv) == 5:
        have = dst.read_text(encoding="utf-8") if dst.exists() else ""
        if have != want:
            print(f"gen_antenna_lef: STALE {dst} (regenerate with: python3 {argv[0]} {lef} {spice} {dst})")
            return 1
        print(f"gen_antenna_lef: {dst} is up to date")
        return 0
    dst.write_text(want, encoding="utf-8")
    print(f"gen_antenna_lef: wrote {dst} ({len(areas)} input pins)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
