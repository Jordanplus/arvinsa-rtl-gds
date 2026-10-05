#!/usr/bin/env python3
"""Compare the Hazard3 RTL retirement trace with the rvcpp ISS trace, instruction by instruction
(Phase 5, ADR-0011 user decision 3).

usage: compare_trace.py <rvfi_trace.txt> <rvcpp --trace output> [--from <pc>]
       compare_trace.py --self-test

RTL side: dv/core_hazard3/rvfi_trace.sv, one line per rvfi_valid: pc insn trap intr rd rd_wdata.
ISS side: rvcpp --trace (third_party/hazard3/test/sim/rvcpp/rv_core.cpp 1030-1070):
  "<pc>: <insn32> : <reg> <- <value> :"   or "<pc>:     <insn16> : ..." for compressed;
  "pc <- <target> <" or a blank field when no register is written; "^^^ Trap ... cause" marks
  the instruction above it as trapping; after a trap or "^^^ IRQ" the next instruction is the first
  of a trap handler, which RVFI flags with rvfi_intr (riscv-formal: exceptions included);
  continuation lines (CSR writes, the new pc) are not compared.
--from <pc>: both traces start at the first instruction at that pc (the first riscv-tests test_N
  label: the environment's initialization probes optional CSRs such as the PMP, which rvcpp
  implements for the full Hazard3 configuration and the SoC's configuration does not).
Each pair must have the same pc, instruction (the low 16 bits for a compressed one), trap and
interrupt flags, and, when the ISS writes a register, the same register and value (rvcpp prints a
write only for rd != 0). Values read from cycle, time and their high halves (CSR 0xc00, 0xc01,
0xc80, 0xc81, 0xb00, 0xb80) are not compared: rvcpp's cycle count is a fixed 1-IPC model
(test/sim/csmith/run_csmith.sh 23). Lengths: the ISS trace may end with at most TAIL more
instructions than the RTL trace (the testbench stops at the exit store, while up to TAIL older
instructions are still in the 3-stage pipeline and never reach rvfi_valid); never fewer.
Prints `compare_trace: PASS n instructions` or the first mismatches; exit 0 only on PASS.
--self-test: injects a wrong value, a missing instruction and a wrong trap flag into a small
trace pair and checks that each is reported (a comparator that cannot fail must not PASS).
"""
import re
import sys

REGS = ["zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1"] + [f"a{i}" for i in range(8)] \
    + [f"s{i}" for i in range(2, 12)] + [f"t{i}" for i in range(3, 7)]
TAIL = 2
COUNTER_CSRS = {0xc00, 0xc01, 0xc80, 0xc81, 0xb00, 0xb80}
INSN = re.compile(r"^([0-9a-f]{8}): (?:([0-9a-f]{8})|    ([0-9a-f]{4})) : (.*)$")
WB = re.compile(r"^(\S+)\s+<- ([0-9a-f]{8}) :")


def parse_iss(lines):
    ev, irq_next = [], False
    for line in lines:
        m = INSN.match(line)
        if m:
            insn = int(m.group(2) or m.group(3), 16)
            rd, val = 0, None
            w = WB.match(m.group(4))
            if w and w.group(1) != "pc":
                rd, val = REGS.index(w.group(1)), int(w.group(2), 16)
            ev.append({"pc": int(m.group(1), 16), "insn": insn, "trap": 0, "intr": int(irq_next), "rd": rd, "val": val})
            irq_next = False
        elif line.startswith("^^^ Trap") and ev:
            ev[-1]["trap"] = 1
            irq_next = True
        elif line.startswith("^^^ IRQ"):
            irq_next = True
    return ev


def parse_rtl(lines):
    ev = []
    for line in lines:
        f = line.split()
        if len(f) != 6:
            continue
        ev.append({"pc": int(f[0], 16), "insn": int(f[1], 16), "trap": int(f[2]), "intr": int(f[3]),
                   "rd": int(f[4]), "val": int(f[5], 16)})
    return ev


def counter_read(insn):
    return insn & 0x7f == 0x73 and (insn >> 12) & 0x3 != 0 and insn >> 20 in COUNTER_CSRS


def compare(rtl, iss, limit=5):
    bad = []
    for i, (r, s) in enumerate(zip(rtl, iss)):
        ri = r["insn"] if r["insn"] & 3 == 3 else r["insn"] & 0xffff
        why = []
        if r["pc"] != s["pc"] or ri != s["insn"]:
            why.append(f"pc/insn {r['pc']:08x}/{ri:08x} vs ISS {s['pc']:08x}/{s['insn']:08x}")
        if r["trap"] != s["trap"] or r["intr"] != s["intr"]:
            why.append(f"trap/intr {r['trap']}/{r['intr']} vs ISS {s['trap']}/{s['intr']}")
        if not why and not s["trap"] and s["rd"] and not counter_read(s["insn"]):
            if r["rd"] != s["rd"] or r["val"] != s["val"]:
                why.append(f"x{r['rd']} <- {r['val']:08x} vs ISS x{s['rd']} <- {s['val']:08x}")
        if why:
            bad.append(f"#{i} pc {s['pc']:08x}: " + "; ".join(why))
            if len(bad) >= limit:
                break
    if not 0 <= len(iss) - len(rtl) <= TAIL and len(bad) < limit:
        bad.append(f"length: RTL {len(rtl)} instructions, ISS {len(iss)} (the ISS may have at most {TAIL} more)")
    return bad


def self_test():
    iss = ["80000040: 00000093 : ra    <- 00000000 :", "80000044: 00100113 : sp    <- 00000001 :",
           "80000048: 00000073 :                   :", "^^^ Trap           : cause <- 11       :",
           "80000000: 00000193 : gp    <- 00000000 :"]
    rtl = ["80000040 00000093 0 0 1 00000000", "80000044 00100113 0 0 2 00000001",
           "80000048 00000073 1 0 0 00000000", "80000000 00000193 0 1 3 00000000"]
    if compare(parse_rtl(rtl), parse_iss(iss)):
        return "the matching pair was reported"
    cases = {"wrong value": (rtl[:1] + ["80000044 00100113 0 0 2 00000003"] + rtl[2:], "#1 "),
             "missing instruction": (rtl[:1] + rtl[2:], "#1 "),
             "wrong trap flag": (rtl[:2] + ["80000048 00000073 0 0 0 00000000"] + rtl[3:], "#2 ")}
    for name, (r, where) in cases.items():
        found = compare(parse_rtl(r), parse_iss(iss))
        if not found or not found[0].startswith(where):
            return f"{name} not reported at {where.strip()} ({found})"
    return None


def main(argv):
    if argv[1:] == ["--self-test"]:
        err = self_test()
        print("compare_trace: self-test " + ("FAIL - " + err if err else "PASS 3/3 injected differences reported"))
        return 1 if err else 0
    if len(argv) not in (3, 5) or len(argv) == 5 and argv[3] != "--from":
        print(__doc__)
        return 2
    rtl = parse_rtl(open(argv[1]).read().splitlines())
    iss = parse_iss(open(argv[2], errors="replace").read().splitlines())
    if len(argv) == 5:
        start = int(argv[4], 16)
        ri = next((i for i, e in enumerate(rtl) if e["pc"] == start), None)
        si = next((i for i, e in enumerate(iss) if e["pc"] == start), None)
        if ri is None or si is None:
            print(f"compare_trace: FAIL - pc {start:08x} not in the {'RTL' if ri is None else 'ISS'} trace")
            return 1
        rtl, iss = rtl[ri:], iss[si:]
    if not rtl or not iss:
        print(f"compare_trace: FAIL - empty trace (RTL {len(rtl)}, ISS {len(iss)})")
        return 1
    bad = compare(rtl, iss)
    if bad:
        print("compare_trace: FAIL " + " | ".join(bad))
        return 1
    print(f"compare_trace: PASS {len(rtl)} instructions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
