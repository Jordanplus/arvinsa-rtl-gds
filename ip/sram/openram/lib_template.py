#!/usr/bin/env python3
"""Make the .lib template of a self-generated SRAM macro for ip/sram/char/gen_char_lib.py (Phase 6, ADR-0018).

    python3 ip/sram/openram/lib_template.py <openram TT .lib> <PDK macro TT .lib> <out.lib>

OpenRAM dev 3608704c writes every internal_power value of its analytical TT .lib as 1.036316e+11 (2 KB 1rw1r;
the PDK macro's .lib, OpenRAM v1.1.15, has 1.380840e+01 everywhere): ten orders of magnitude off, and the SoC
IR-drop analysis takes the SRAM current from these numbers (skill pdn-ir rule 4). Root cause not checked.
This copies the OpenRAM .lib (pins, capacitances, area, port 1 timing: the macro's own) and replaces each
internal_power rise_power/fall_power value with the PDK macro's value for the same pin and `when`. Both
analytical models stay unreliable (ADR-0007 limitation 3); this keeps the Phase 5 numbers.
FAILs unless both files have the same (pin, when, rise/fall) power entries and nothing else changes.
gen_char_lib.py refuses a template whose power is above POWER_MAX (neg_openram.py L1).
"""
import re
import sys

POWER = re.compile(r'(\bpin\s*\(\s*(\w+)\s*\)\s*\{)|(when\s*:\s*"([^"]*)")|((rise|fall)_power\s*\(\s*scalar\s*\)\s*\{\s*values\(")'
                   r'(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)')


def power_entries(text):
    """[(pin, when, rise|fall, value, value span)] in file order."""
    out, pin, when = [], None, None
    for m in POWER.finditer(text):
        if m.group(1):
            pin, when = m.group(2), None
        elif m.group(3):
            when = m.group(4)
        else:
            out.append((pin, when, m.group(6), m.group(7), m.span(7)))
    return out


def make(openram_text, pdk_text):
    """(template text, problems)."""
    ours, ref = power_entries(openram_text), power_entries(pdk_text)
    keys = [e[:3] for e in ours]
    ref_val = {e[:3]: e[3] for e in ref}
    probs = []
    if not ours:
        probs.append("no internal_power values in the OpenRAM .lib")
    if len(set(keys)) != len(keys):
        probs.append("repeated (pin, when, rise/fall) power entries in the OpenRAM .lib")
    if sorted(keys) != sorted(ref_val):
        probs.append(f"power entries differ: OpenRAM {sorted(set(keys) - set(ref_val))[:3]}, "
                     f"PDK {sorted(set(ref_val) - set(keys))[:3]}")
    if probs:
        return None, probs
    out, pos = [], 0
    for pin, when, rf, _, (a, b) in ours:
        out += [openram_text[pos:a], ref_val[(pin, when, rf)]]
        pos = b
    out.append(openram_text[pos:])
    text = "".join(out)
    # nothing but the power values may change
    strip = lambda t: POWER.sub(lambda m: m.group(0)[:m.start(7) - m.start(0)] + "#" if m.group(5) else m.group(0), t)
    if strip(text) != strip(openram_text):
        probs.append("text other than the power values changed")
    return text, probs


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    text, probs = make(open(argv[1], encoding="utf-8").read(), open(argv[2], encoding="utf-8").read())
    if probs:
        print("lib_template: FAIL - " + "; ".join(probs))
        return 1
    open(argv[3], "w", encoding="utf-8").write(text)
    n = len(power_entries(text))
    print(f"lib_template: PASS - {n} internal_power values taken from {argv[2].split('/')[-1]} -> {argv[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
