#!/usr/bin/env python3
"""Bug injection into a final netlist; signoff/eqy/run_eqy.py must FAIL on each case.

usage: neg_eqy.py --design picorv32_core|soc_top [--run <dir>] [--out <dir>] [-j N]
The harden run must pass signoff/scripts/run_guard.py (PASS, made from the commit checked out now);
run_eqy.py checks it again for every case.

Each case edits a copy of <run>/final/nl/<DESIGN_NAME>.nl.v and runs run_eqy.py on it
(outputs in runs/neg_eqy_<design>/<case>/). An edit must match exactly one place in the
netlist, otherwise the case itself FAILs. A case PASSes when run_eqy.py prints `eqy: FAIL` for an
equivalence reason: a partition not proved, a bit mapped to a constant without proof, EQY's
partition step refusing conflicting name matches, a sequential cell that differs from the
synthesized netlist, or a clock pin that reaches another clock source (not some other error such
as a missing file),
and every name in those reasons is at the injection (known limitation 16 of
docs/phase_exit/phase3.md): an instance whose cell or connections the edit changed, a net on
one of their pins, or an instance on such a net (fail_names, neighborhood).

Cases (the same kinds of error as the Phase 2 GL qualification, docs/phase_exit/phase2.md):
  picorv32_core
    wdata3_stuck0         the buffer that drives port mem_wdata[3] gets constant 0 at its input
    instr_inverted        the buffer that drives port mem_instr becomes an inverter
    count_cycle45_stuck1  flip-flop count_cycle[45] D tied to 1 (rdcycleh; missed by gl-core)
    count_instr40_stuck1  flip-flop count_instr[40] D tied to 1 (rdinstreth; missed by gl-core)
    buserr_irq_stuck0     flip-flop irq_pending[2] (bus-error IRQ) D tied to 0 (missed by gl-core)
    x8_bit24_stuck0       flip-flop cpuregs[8][24] D tied to 0
    mux_swap              first mux2_1 cell (by instance name) that drives a flip-flop D
                          directly gets its A0 and A1 inputs swapped
    flop_q_inverted       first dfxtp_2 (by instance name) becomes a dfxbp_2 driving its net from Q_N
    flop_async_reset      first dfxtp_2 becomes a dfrtp_2 with RESET_B on the resetn port; EQY alone
                          proves all partitions (its sat strategy does not see a flip-flop's own
                          behaviour), so only run_eqy.py's sequential cell check catches it
    flop_clk_inverted     first dfxtp_2 gets its clock through an extra clkinv_1 (it samples on the
                          falling edge); EQY's sat strategy puts every flip-flop on one implicit
                          clock, so only run_eqy.py's clock source check catches it
    nand2_to_nor2         first nand2 cell (by instance name) becomes the nor2 of the same size,
                          same name and connections: a wrong function that is neither a constant
                          nor a name conflict, so only the proof step can catch it (Phase 3
                          review, docs/notes/phase3_review/eqy_nand2nor.log)
  soc_top
    din5_stuck0           the net on sram0.din0[5] driven by constant 0
    csb0_inverted         sram0.csb0 driven through an extra inverter
    host_rdata7_inverted  the buffer that drives port host_rdata[7] becomes an inverter
    clk0_inverted         sram0.clk0 driven through an extra clkinv_1
    mux_swap              as for picorv32_core
    nand2_to_nor2         as for picorv32_core
    flop_q_inverted, flop_async_reset, flop_clk_inverted   as for picorv32_core
Prints `neg-eqy: PASS n/n caught` / `neg-eqy: FAIL ...`; exit code 0 only on PASS.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RUNNER = os.path.join(ROOT, "signoff", "eqy", "run_eqy.py")
sys.path.insert(0, os.path.join(ROOT, "signoff", "scripts"))
from run_guard import guard  # noqa: E402
from run_eqy import VERDICT, instances  # noqa: E402  (same directory as this script)
CELL = r"(sky130_fd_sc_hd__\w+)"


def port_buffer(port):
    """Single-input buffer instance whose output X drives <port>: groups (type, name, input)."""
    return re.compile(CELL + r" (\S+) \(\.A\(([^)]+)\),\s*\.X\(" + re.escape(port) + r"\)\);")


def buf_const0(port):
    rx = port_buffer(port)
    return rx, lambda m: f"{m.group(1)} {m.group(2)} (.A(1'b0),\n    .X({port}));"


def buf_inverted(port):
    rx = port_buffer(port)
    return rx, lambda m: f"sky130_fd_sc_hd__inv_2 {m.group(2)} (.A({m.group(3)}),\n    .Y({port}));"


def flop_d_const(q_name, value):
    """dfxtp flip-flop whose Q is net <q_name>: its D becomes the constant <value>."""
    rx = re.compile(r"(sky130_fd_sc_hd__df\w+ \S+ \(\.CLK\([^)]*\),\s*\.D\()[^)]*(\),\s*\.Q\("
                    + re.escape(q_name) + r"\s*\)\);)")
    return rx, lambda m: f"{m.group(1)}1'b{value}{m.group(2)}"


def mux_swap(text):
    """First mux2_1 instance (sorted by name) whose output is the D input of a flip-flop: A0 and A1 swapped."""
    d_nets = set(re.findall(r"sky130_fd_sc_hd__df\w+ \S+ \(\.CLK\([^)]*\),\s*\.D\(([^)]+)\)", text))
    cands = sorted((name, x) for name, x in
                   re.findall(r"sky130_fd_sc_hd__mux2_1 (\S+) \(\.A0\([^)]*\),\s*\.A1\([^)]*\),\s*\.S\([^)]*\),\s*\.X\(([^)]+)\)\);", text)
                   if x in d_nets)
    if not cands:
        return re.compile(r"(?!x)x"), None
    rx = re.compile(r"(sky130_fd_sc_hd__mux2_1 " + re.escape(cands[0][0]) + r" \(\.A0\()([^)]*)(\),\s*\.A1\()([^)]*)(\))")
    return rx, lambda m: m.group(1) + m.group(4) + m.group(3) + m.group(2) + m.group(5)


def flop_q_inverted(text):
    """First dfxtp_2 flip-flop (sorted by instance name) becomes a dfxbp_2 whose inverted output Q_N
    drives the same net: a state element that holds the inverse of what it should. Every bit of its
    fan-in and fan-out keeps its name. EQY's partition step refuses it (conflicting name matches) and
    run_eqy.py's sequential cell check sees dfxtp -> dfxbp; no case shows that the proof of a
    partition with a flip-flop catches anything (Phase 4: EQY's sat strategy proves such partitions
    vacuously)."""
    cands = sorted(re.findall(r"sky130_fd_sc_hd__dfxtp_2 (\S+) \(\.CLK\(", text))
    if not cands:
        return re.compile(r"(?!x)x"), None
    rx = re.compile(r"sky130_fd_sc_hd__dfxtp_2( " + re.escape(cands[0]) + r" \(\.CLK\([^)]*\),\s*\.D\([^)]*\),\s*\.)Q(\()")
    return rx, lambda m: "sky130_fd_sc_hd__dfxbp_2" + m.group(1) + "Q_N" + m.group(2)


def flop_async_reset(text):
    """First dfxtp_2 (sorted by instance name) becomes a dfrtp_2 whose RESET_B is the resetn port: a
    flip-flop that is cleared while resetn is low, which the synthesized one is not. Every name stays
    the same, so only the proof of the partition with this flip-flop can catch it."""
    cands = sorted(re.findall(r"sky130_fd_sc_hd__dfxtp_2 (\S+) \(\.CLK\(", text))
    if not cands or not re.search(r"^\s*input resetn;", text, re.M):
        return re.compile(r"(?!x)x"), None
    rx = re.compile(r"sky130_fd_sc_hd__dfxtp_2( " + re.escape(cands[0]) + r" \(\.CLK\([^)]*\),\s*\.D\([^)]*\),)(\s*\.Q\()")
    return rx, lambda m: "sky130_fd_sc_hd__dfrtp_2" + m.group(1) + "\n    .RESET_B(resetn)," + m.group(2)


def flop_clk_inverted(text):
    """First dfxtp_2 (sorted by instance name): its CLK net becomes neg_eqy_flop_clk_inv, which edit()
    drives from the original clock net through an inverter, so the flip-flop samples on the falling edge."""
    cands = sorted(re.findall(r"sky130_fd_sc_hd__dfxtp_2 (\S+) \(\.CLK\(", text))
    if not cands:
        return re.compile(r"(?!x)x"), None
    rx = re.compile(r"(sky130_fd_sc_hd__dfxtp_2 " + re.escape(cands[0]) + r" \(\.CLK\()([^)]*)(\))")
    return rx, lambda m: m.group(1) + "neg_eqy_flop_clk_inv" + m.group(3)


def nand2_to_nor2(text):
    """First nand2 instance (sorted by name): cell type nand2_<n> -> nor2_<n> (pins A, B, Y on both)."""
    cands = sorted(re.findall(r"sky130_fd_sc_hd__nand2_(\d+) (\S+) \(", text), key=lambda c: c[1])
    if not cands:
        return re.compile(r"(?!x)x"), None
    size, name = cands[0]
    rx = re.compile(r"sky130_fd_sc_hd__nand2_" + size + r"( " + re.escape(name) + r" \()")
    return rx, lambda m: "sky130_fd_sc_hd__nor2_" + size + m.group(1)


BUFFER = re.compile(r"sky130_fd_sc_hd__(buf|clkbuf|inv|clkinv|clkinvlp|bufinv|bufbuf|dlygate4sd\d|dlymetal6s\ds|"
                    r"clkdlybuf4s\d+|dlybuf4s\d+kapwr)_\d+$")


def edited(orig_text, new_text):
    """Instances whose cell or connections differ between the two netlists (new ones included)."""
    a, b = instances(orig_text), instances(new_text)
    return {n for n in set(a) | set(b) if a.get(n) != b.get(n)}


def neighborhood(orig_text, new_text):
    """Names at the injection, on the final netlist: the instances whose cell or connections the
    edit changed; the nets on their changed pins (all pins if the cell type changed or the instance
    is new; of a bus pin only the bits that changed; constants dropped); then, repeatedly, every instance of the original netlist on one of
    those nets, and for buffers and inverters also the nets on their other pin, so that the walk
    passes through the buffer chains that placement and routing add (a flip-flop of the synthesized
    netlist that drives a port is several buffers away from it in the final netlist). Clock nets
    (clknet_*) are not followed."""
    a, b = instances(orig_text), instances(new_text)
    changed = {n for n in set(a) | set(b) if a.get(n) != b.get(n)}
    nets = set()
    for n in changed:
        old, new = a.get(n), b.get(n)
        whole = old is None or new is None or old[0] != new[0]
        for d in (old, new):
            for pin, ns in (d[1].items() if d else ()):
                if whole:
                    nets.update(ns)
                    continue
                o, w = old[1].get(pin) or [], new[1].get(pin) or []
                if o != w:
                    nets.update([x for pair in zip(o, w) if pair[0] != pair[1] for x in pair]
                                if len(o) == len(w) else o + w)
    # A clock net is not walked (the whole clock tree would be "at the injection"); instead its source
    # is added, found by walking back through the clock buffers (EQY names the gold clock port when a
    # clock pin is inverted: clk0_inverted).
    drv = {net: name for name, (cell, pins) in a.items() if BUFFER.match(cell) for pin in ("X", "Y")
           for net in pins.get(pin, [])}
    for n in [n for n in nets if n.startswith("clknet")]:
        for _ in range(100):
            if n not in drv or not a[drv[n]][1].get("A"):
                break
            n = a[drv[n]][1]["A"][0]
        nets.add(n)
    nets = {n for n in nets if not re.fullmatch(r"\d+'[bh][0-9a-fA-F]+", n) and not n.startswith("clknet")}
    on_net = {}
    for name, (_, pins) in a.items():
        for ns in pins.values():
            for net in ns:
                on_net.setdefault(net, set()).add(name)
    found, todo = set(changed) | nets, list(nets)
    while todo:
        net = todo.pop()
        for inst in on_net.get(net, ()):
            if inst in found:
                continue
            found.add(inst)
            cell, pins = a[inst]
            if BUFFER.match(cell):
                for ns in pins.values():
                    for n2 in ns:
                        if n2 not in found and not n2.startswith("clknet"):
                            found.add(n2)
                            todo.append(n2)
    return found


def fail_names(eqy_dir):
    """Names (instance or net, without the backslash, bus index as [n]) in the EQY reasons for FAIL:
    partitions not proved, constant matches, conflicting matches."""
    log = os.path.join(eqy_dir, "eqy_run.log")
    plist = os.path.join(eqy_dir, "work", "partition.list")
    plog = os.path.join(eqy_dir, "work", "partition.log")
    text = open(log, errors="replace").read() if os.path.isfile(log) else ""
    parts = [line.split()[1] for line in open(plist) if line.strip()] if os.path.isfile(plist) else []
    proved = set(re.findall(r"Proved equivalence of partition '([^']+)'", text))
    raw = [p.split(".", 1)[1] for p in parts if p not in proved]           # drop the module prefix
    ptext = open(plog, errors="replace").read() if os.path.isfile(plog) else ""
    raw += re.findall(r"found constant \w+ bit for \w+ bit \\?(\S+):", ptext)
    for m in re.findall(r"ERROR: conflicting \w+ for \w+ bit \\?(\S+): \\?(\S+) vs \\?(\S+)", ptext):
        raw += list(m)
    names = set()
    for r in raw:
        base = r.split(".")[0]
        if re.fullmatch(r"[^.\[]+\.\d+", r):                               # partition name sram_din0.5
            base = re.sub(r"\.(\d+)$", r"[\1]", r)
        names.add(base)
    return names


def sram_pin_const0(pin):
    """sram0 connection .<pin>({... net ...}) or .<pin>(net): one bit replaced by 1'b0."""
    bus, idx = re.fullmatch(r"(\w+)\[(\d+)\]", pin).groups()
    rx = re.compile(r"(sky130_sram_2kbyte_1rw1r_32x512_8 sram0 \(.*?\." + bus + r"\(\{)([^}]*)(\}\))", re.S)

    def repl(m):
        bits = [b.strip() for b in m.group(2).split(",")]
        bits[len(bits) - 1 - int(idx)] = "1'b0"   # concatenation is MSB first
        return m.group(1) + ",\n    ".join(bits) + m.group(3)
    return rx, repl


def sram_pin_inverted(pin, net="neg_eqy_inv"):
    rx = re.compile(r"(sky130_sram_2kbyte_1rw1r_32x512_8 sram0 \(.*?\." + pin + r"\()([^)]+)(\))", re.S)
    return rx, lambda m: (m.group(1) + net + m.group(3))


CASES = {
    "picorv32_core": [
        ("wdata3_stuck0", lambda t: buf_const0("mem_wdata[3]")),
        ("instr_inverted", lambda t: buf_inverted("mem_instr")),
        ("count_cycle45_stuck1", lambda t: flop_d_const(r"\count_cycle[45] ", 1)),
        ("count_instr40_stuck1", lambda t: flop_d_const(r"\count_instr[40] ", 1)),
        ("buserr_irq_stuck0", lambda t: flop_d_const(r"\irq_pending[2] ", 0)),
        ("x8_bit24_stuck0", lambda t: flop_d_const(r"\cpuregs[8][24] ", 0)),
        ("mux_swap", mux_swap),
        ("nand2_to_nor2", nand2_to_nor2),
        ("flop_q_inverted", flop_q_inverted),
        ("flop_async_reset", flop_async_reset),
        ("flop_clk_inverted", flop_clk_inverted),
    ],
    "soc_top": [
        ("din5_stuck0", lambda t: sram_pin_const0("din0[5]")),
        ("csb0_inverted", lambda t: sram_pin_inverted("csb0")),
        ("clk0_inverted", lambda t: sram_pin_inverted("clk0", "neg_eqy_clk0_inv")),
        ("host_rdata7_inverted", lambda t: buf_inverted("host_rdata[7]")),
        ("mux_swap", mux_swap),
        ("nand2_to_nor2", nand2_to_nor2),
        ("flop_q_inverted", flop_q_inverted),
        ("flop_async_reset", flop_async_reset),
        ("flop_clk_inverted", flop_clk_inverted),
    ],
}

# Cases whose edit points a pin at a new net: (instance it belongs to, pin, inverter cell, new net).
# edit() drives the new net from the pin's original net through that inverter (instance <net>_cell).
# Each case has its own names, so the location cross check compares them with each other.
INVERTER = {"csb0_inverted": ("sram0", "csb0", "sky130_fd_sc_hd__inv_2", "neg_eqy_inv"),
            "clk0_inverted": ("sram0", "clk0", "sky130_fd_sc_hd__clkinv_1", "neg_eqy_clk0_inv"),
            "flop_clk_inverted": (None, "CLK", "sky130_fd_sc_hd__clkinv_1", "neg_eqy_flop_clk_inv")}


def edit(name, text, fn):
    rx, repl = fn(text)
    hits = rx.findall(text)
    if len(hits) != 1 or repl is None:
        return None, f"edit matched {len(hits)} places, expected 1"
    new = rx.sub(repl, text, count=1)
    if name in INVERTER:
        # Drive the new net from the pin's original net through an inverter. The wire is declared just
        # before the instance, its first use (Icarus rejects declaration after use; Yosys accepts it).
        inst, pin, cell, net = INVERTER[name]
        if inst is None:  # the instance the edit changed
            inst = next(n for n, (c, p) in instances(new).items() if p.get(pin) == [net])
        a = instances(text)[inst]
        orig = a[1][pin][0]
        new, n = re.subn(r"^( *)(" + re.escape(a[0]) + r" \\?" + re.escape(inst) + r" \()", r"\1wire " + net + r";\n\1\2",
                         new, count=1, flags=re.M)
        inv = f" {cell} {net}_cell (.A({orig}),\n    .Y({net}));\nendmodule"
        new, m = re.subn(r"endmodule\s*$", inv, new.rstrip() + "\n")
        if n != 1 or m != 1:
            return None, "could not add the inverter"
    if new == text:
        return None, "edit did not change the netlist"
    return new, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--design", required=True, choices=sorted(CASES))
    ap.add_argument("--run")
    ap.add_argument("-j", type=int, default=3, help="cases run in parallel (each EQY run uses -j 3)")
    ap.add_argument("--cases", help="comma-separated subset of cases")
    ap.add_argument("--out", help="output directory (default runs/neg_eqy_<design>)")
    args = ap.parse_args()
    run = os.path.abspath(args.run or os.path.join(ROOT, "runs", args.design))
    out = os.path.abspath(args.out or os.path.join(ROOT, "runs", f"neg_eqy_{args.design}"))
    shutil.rmtree(out, ignore_errors=True)  # only the output directory is removed, before any check
    errs = guard(run, VERDICT[args.design])
    if errs:
        print(f"neg-eqy: FAIL ({'; '.join(errs)})")
        return 1
    if not os.path.isfile(os.path.join(run, "resolved.json")):
        print(f"neg-eqy: FAIL ({run}/resolved.json not found)")
        return 1
    top = json.load(open(os.path.join(run, "resolved.json")))["DESIGN_NAME"]
    netlist = os.path.join(run, "final", "nl", f"{top}.nl.v")
    if not os.path.isfile(netlist):
        print(f"neg-eqy: FAIL (netlist not found: {netlist})")
        return 1
    os.makedirs(out)
    text = open(netlist, encoding="utf8").read()
    t0 = time.time()
    errors, jobs, near, edits = [], [], {}, {}
    cases = CASES[args.design]
    if args.cases:
        want = args.cases.split(",")
        unknown = [w for w in want if w not in dict(cases)]
        if unknown:
            print(f"neg-eqy: FAIL (unknown case(s): {', '.join(unknown)})")
            return 1
        cases = [c for c in cases if c[0] in want]
    for name, fn in cases:
        new, err = edit(name, text, fn)
        if err:
            errors.append(f"{name}: {err}")
            print(f"  [FAIL] {name}: {err}")
            continue
        case_dir = os.path.join(out, name)
        os.makedirs(case_dir)
        edited_path = os.path.join(case_dir, f"{top}.nl.v")
        open(edited_path, "w", encoding="utf8").write(new)
        jobs.append((name, case_dir, edited_path))
        near[name] = neighborhood(text, new)
        edits[name] = edited(text, new)

    def one(job):
        name, case_dir, netlist_path = job
        with open(os.path.join(case_dir, "run.log"), "w") as log:
            rc = subprocess.run([sys.executable, RUNNER, "--design", args.design, "--run", run, "--netlist", netlist_path,
                                 "--out", os.path.join(case_dir, "eqy"), "-j", "3"],
                                stdout=log, stderr=subprocess.STDOUT).returncode
        return name, case_dir, rc

    caught, found = 0, {}
    with ThreadPoolExecutor(max_workers=max(1, args.j)) as ex:
        for name, case_dir, rc in ex.map(one, jobs):
            text_log = open(os.path.join(case_dir, "run.log")).read()
            summ_path = os.path.join(case_dir, "eqy", "summary.json")
            summ = json.load(open(summ_path)) if os.path.isfile(summ_path) else {}
            not_proved = summ.get("partitions", 0) - summ.get("proved", 0)
            reasons = []
            if summ.get("partitions", 0) > 0 and not_proved > 0:
                reasons.append(f"{not_proved}/{summ['partitions']} partitions not proved")
            if summ.get("constant_matches", 0) > 0:
                reasons.append(f"{summ['constant_matches']} bit(s) mapped to a constant")
            if summ.get("conflicting_matches", 0) > 0:
                reasons.append("partition step refused: conflicting name matches")
            if summ.get("sequential_mismatch"):
                reasons.append(f"sequential cells differ: {', '.join(summ['sequential_mismatch'][:3])}")
            if summ.get("clock_mismatch"):
                reasons.append(f"clock source differs: {', '.join(summ['clock_mismatch'][:3])}")
            names = (fail_names(os.path.join(case_dir, "eqy")) | set(summ.get("sequential_mismatch") or [])
                     | set(summ.get("clock_mismatch") or []))
            outside = sorted(names - near[name])
            if rc != 0 and "eqy: FAIL" in text_log and reasons and names and not outside:
                caught += 1
                found[name] = names
                print(f"  [PASS] {name}: eqy FAIL as expected ({'; '.join(reasons)}), "
                      f"at the injection ({', '.join(sorted(names)[:4])})")
            elif rc != 0 and "eqy: FAIL" in text_log and reasons:
                msg = (f"eqy FAILed, but not at the injection: {', '.join(outside[:4]) or 'no name found'} "
                       f"not connected to the edited cells")
                errors.append(f"{name}: {msg}")
                print(f"  [FAIL] {name}: {msg}")
            else:
                msg = f"eqy did not FAIL on a partition (exit {rc}, summary {summ.get('errors')})"
                errors.append(f"{name}: {msg}")
                print(f"  [FAIL] {name}: {msg}")
    # The location check must tell the cases apart: for two cases that edit different instances, the
    # FAIL names of one must not all lie at the injection of the other (otherwise "at the injection"
    # would accept a FAIL anywhere). Cases on the same instance (the flop_* cases) are not compared.
    pairs = 0
    for a_name, a_names in found.items():
        for b_name in found:
            if b_name == a_name or edits[a_name] & edits[b_name]:
                continue
            pairs += 1
            if a_names <= near[b_name]:
                errors.append(f"location check does not tell {a_name} from {b_name}: all FAIL names of "
                              f"{a_name} ({', '.join(sorted(a_names)[:3])}) are also at the injection of {b_name}")
                print(f"  [FAIL] {errors[-1]}")
    if pairs:
        print(f"  [{'PASS' if not any('location check' in e for e in errors) else 'FAIL'}] location check: "
              f"{pairs} ordered pairs of cases on different instances, none accepts the other's FAIL names")
    n = len(cases)
    status = "PASS" if not errors and caught == n else "FAIL"
    print(f"neg-eqy: {status} {caught}/{n} caught ({round(time.time() - t0)} s)" +
          ("" if not errors else f" ({'; '.join(errors)})"))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
