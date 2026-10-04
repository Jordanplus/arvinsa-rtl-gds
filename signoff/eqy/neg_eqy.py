#!/usr/bin/env python3
"""Bug injection into a final netlist; signoff/eqy/run_eqy.py must FAIL on each case.

usage: neg_eqy.py --design picorv32_core|soc_top [--run <dir>] [--out <dir>] [-j N]
The harden run must pass signoff/scripts/run_guard.py (PASS, made from the commit checked out now);
run_eqy.py checks it again for every case.

Each case edits a copy of <run>/final/nl/<DESIGN_NAME>.nl.v and runs run_eqy.py on it
(outputs in runs/neg_eqy_<design>/<case>/). An edit must match exactly one place in the
netlist, otherwise the case itself FAILs. A case PASSes when run_eqy.py prints `eqy: FAIL` for an
equivalence reason: a partition not proved, a bit mapped to a constant without proof, or EQY's
partition step refusing conflicting name matches (not some other error such as a missing file),
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
    nand2_to_nor2         first nand2 cell (by instance name) becomes the nor2 of the same size,
                          same name and connections: a wrong function that is neither a constant
                          nor a name conflict, so only the proof step can catch it (Phase 3
                          review, docs/notes/phase3_review/eqy_nand2nor.log)
  soc_top
    din5_stuck0           the net on sram0.din0[5] driven by constant 0
    csb0_inverted         sram0.csb0 driven through an extra inverter
    host_rdata7_inverted  the buffer that drives port host_rdata[7] becomes an inverter
    mux_swap              as for picorv32_core
    nand2_to_nor2         as for picorv32_core
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


def nand2_to_nor2(text):
    """First nand2 instance (sorted by name): cell type nand2_<n> -> nor2_<n> (pins A, B, Y on both)."""
    cands = sorted(re.findall(r"sky130_fd_sc_hd__nand2_(\d+) (\S+) \(", text), key=lambda c: c[1])
    if not cands:
        return re.compile(r"(?!x)x"), None
    size, name = cands[0]
    rx = re.compile(r"sky130_fd_sc_hd__nand2_" + size + r"( " + re.escape(name) + r" \()")
    return rx, lambda m: "sky130_fd_sc_hd__nor2_" + size + m.group(1)


INST = re.compile(r"^\s*(sky130_\w+)\s+(\S+)\s*\((.*?)\);", re.M | re.S)
PIN = re.compile(r"\.(\w+)\(((?:\{[^}]*\})|[^()]*)\)")


def instances(text):
    """{instance: (cell, {pin: [nets]})} of a flat gate netlist (escaped names without the backslash)."""
    out = {}
    for cell, name, body in INST.findall(text):
        pins = {}
        for pin, val in PIN.findall(body):
            val = val.strip()
            nets = [v.strip() for v in val[1:-1].split(",")] if val.startswith("{") else [val]
            pins[pin] = [n.lstrip("\\").strip() for n in nets if n]
        out[name.lstrip("\\")] = (cell, pins)
    return out


BUFFER = re.compile(r"sky130_fd_sc_hd__(buf|clkbuf|inv|clkinv|clkinvlp|bufinv|bufbuf|dlygate4sd\d|dlymetal6s\ds|"
                    r"clkdlybuf4s\d+|dlybuf4s\d+kapwr)_\d+$")


def neighborhood(orig_text, new_text):
    """Names at the injection, on the final netlist: the instances whose cell or connections the
    edit changed; the nets on their changed pins (all pins if the cell type changed or the instance
    is new; constants dropped); then, repeatedly, every instance of the original netlist on one of
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
                if whole or old[1].get(pin) != new[1].get(pin):
                    nets.update(ns)
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


def sram_pin_inverted(pin):
    rx = re.compile(r"(sky130_sram_2kbyte_1rw1r_32x512_8 sram0 \(.*?\." + pin + r"\()([^)]+)(\))", re.S)
    return rx, lambda m: (m.group(1) + "neg_eqy_inv" + m.group(3))


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
    ],
    "soc_top": [
        ("din5_stuck0", lambda t: sram_pin_const0("din0[5]")),
        ("csb0_inverted", lambda t: sram_pin_inverted("csb0")),
        ("host_rdata7_inverted", lambda t: buf_inverted("host_rdata[7]")),
        ("mux_swap", mux_swap),
        ("nand2_to_nor2", nand2_to_nor2),
    ],
}


def edit(name, text, fn):
    rx, repl = fn(text)
    hits = rx.findall(text)
    if len(hits) != 1 or repl is None:
        return None, f"edit matched {len(hits)} places, expected 1"
    new = rx.sub(repl, text, count=1)
    if name == "csb0_inverted":
        # Drive the new net from the original csb0 net through an inverter. The wire is declared just
        # before sram0, its first use (Icarus rejects declaration after use; Yosys accepts it).
        orig = re.search(r"sky130_sram_2kbyte_1rw1r_32x512_8 sram0 \(.*?\.csb0\(([^)]+)\)", text, re.S).group(1)
        new, n = re.subn(r"^( *)(sky130_sram_2kbyte_1rw1r_32x512_8 sram0 \()", r"\1wire neg_eqy_inv;\n\1\2",
                         new, count=1, flags=re.M)
        inv = f" sky130_fd_sc_hd__inv_2 neg_eqy_inv_cell (.A({orig}),\n    .Y(neg_eqy_inv));\nendmodule"
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
    errs = guard(run, {"picorv32_core": "harden-core: PASS", "soc_top": "harden-soc: PASS"}[args.design])
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
    errors, jobs, near = [], [], {}
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
        edited = os.path.join(case_dir, f"{top}.nl.v")
        open(edited, "w", encoding="utf8").write(new)
        jobs.append((name, case_dir, edited))
        near[name] = neighborhood(text, new)

    def one(job):
        name, case_dir, edited = job
        with open(os.path.join(case_dir, "run.log"), "w") as log:
            rc = subprocess.run([sys.executable, RUNNER, "--design", args.design, "--run", run, "--netlist", edited,
                                 "--out", os.path.join(case_dir, "eqy"), "-j", "3"],
                                stdout=log, stderr=subprocess.STDOUT).returncode
        return name, case_dir, rc

    caught = 0
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
            names = fail_names(os.path.join(case_dir, "eqy"))
            outside = sorted(names - near[name])
            if rc != 0 and "eqy: FAIL" in text_log and reasons and names and not outside:
                caught += 1
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
    n = len(cases)
    status = "PASS" if not errors and caught == n else "FAIL"
    print(f"neg-eqy: {status} {caught}/{n} caught ({round(time.time() - t0)} s)" +
          ("" if not errors else f" ({'; '.join(errors)})"))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
