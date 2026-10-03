#!/usr/bin/env python3
"""Check that the only disconnected pins of the hardened PicoRV32 are the unused PCPI inputs.

usage: check_disconnected.py <LibreLane run dir>

Reads <run>/*-odb-reportdisconnectedpins/full_disconnected_pins_table.txt (LibreLane step
Odb.ReportDisconnectedPins) and requires, for the top cell `picorv32`:
  - no disconnected power pin
  - disconnected signal pins == pcpi_rd[31:0], pcpi_wr, pcpi_wait, pcpi_ready (35 pins).
    These inputs are unused with ENABLE_PCPI=0, so no cell connects to them; in soc_top
    they are tied to 0 (soc_spec.md §4.1).
and no other row with a disconnected pin. The metric design__disconnected_pin__count only
gives the number; this check makes sure it is these 35 pins and not others.
LibreLane leaves cells of IGNORE_DISCONNECTED_MODULES (and the CTS dummy loads) out of the table,
so the run's resolved.json must keep that list at its sky130 default [sky130_fd_sc_hd__conb_1];
the table must also be complete (its closing border line is required).
Prints `disconnected-pins: PASS` / `disconnected-pins: FAIL`; exit code 0 only on PASS.
"""
import glob
import json
import os
import sys

EXPECTED = {"picorv32": {f"pcpi_rd[{i}]" for i in range(32)} | {"pcpi_wr", "pcpi_wait", "pcpi_ready"}}
IGNORED = ["sky130_fd_sc_hd__conb_1"]


def main(run_dir):
    tables = glob.glob(os.path.join(run_dir, "*-odb-reportdisconnectedpins", "full_disconnected_pins_table.txt"))
    if len(tables) != 1:
        print(f"disconnected-pins: FAIL (expected one disconnected-pin table, found {len(tables)})")
        return 1
    resolved = os.path.join(run_dir, "resolved.json")
    ignored = json.load(open(resolved, encoding="utf8")).get("IGNORE_DISCONNECTED_MODULES") if os.path.isfile(resolved) else "<no resolved.json>"
    if ignored != IGNORED:
        print(f"disconnected-pins: FAIL (IGNORE_DISCONNECTED_MODULES is {ignored}, expected {IGNORED})")
        return 1
    lines = open(tables[0], encoding="utf8").read().splitlines()
    if not lines or not lines[-1].startswith("└"):
        print("disconnected-pins: FAIL (table is incomplete: no closing border line)")
        return 1
    power, signal, inst = {}, {}, None
    for line in lines:
        if not line.startswith("│"):
            continue
        cols = [c.strip() for c in line.strip().strip("│").split("│")]
        if len(cols) != 5:
            print(f"disconnected-pins: FAIL (unexpected table row: {line.rstrip()!r})")
            return 1
        if cols[0]:
            inst = cols[0]
        if cols[2]:
            power.setdefault(inst, set()).add(cols[2])
        if cols[4]:
            signal.setdefault(inst, set()).add(cols[4])
    errors = []
    for name, pins in power.items():
        errors.append(f"{name}: disconnected power pins {sorted(pins)}")
    for name in sorted(set(signal) | set(EXPECTED)):
        have, want = signal.get(name, set()), EXPECTED.get(name, set())
        if have != want:
            errors.append(f"{name}: unexpected {sorted(have - want)}, missing {sorted(want - have)}")
    for e in errors:
        print(f"  [FAIL] {e}")
    if not errors:
        print(f"  [PASS] picorv32: disconnected pins are exactly the {len(EXPECTED['picorv32'])} unused PCPI inputs")
    print(f"disconnected-pins: {'PASS' if not errors else 'FAIL'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: check_disconnected.py <LibreLane run dir>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
