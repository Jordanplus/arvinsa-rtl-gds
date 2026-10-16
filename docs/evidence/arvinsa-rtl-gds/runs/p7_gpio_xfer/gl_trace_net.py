#!/usr/bin/env python3
"""Trace one net of a gate-level netlist back through buffers and inverters to the instance pin that drives it.

usage: python3 gl_trace_net.py <netlist.v> <instance name> <pin>
  e.g. gl_trace_net.py <caravel-lite>/verilog/gl/caravel_core.v housekeeping porb
Prints each buffer on the way and the first non-buffer driver (a hierarchical instance's output pin, or a port).
Read only.
"""
import bisect
import re
import sys

path, inst, pin = sys.argv[1:4]
src = open(path).read()
nl = [m.start() for m in re.finditer("\n", src)]
inst_re = re.compile(r"^\s*(\w+)\s+(?:#\s*\(.*?\)\s*)?(\\?\S+)\s*\((.*?)\);", re.M | re.S)
pin_re = re.compile(r"\.(\w+)\(\s*([^()]*?)\s*\)")
BUF = re.compile(r"sky130_fd_sc_hd__(buf|clkbuf|dlygate4sd\d|dlymetal6s2s|clkdlybuf4s\d+)_\d+$")
INV = re.compile(r"sky130_fd_sc_hd__(inv|clkinv|clkinvlp)_\d+$")
OUT_PINS = ("X", "Y")
by_out = {}
target = None
for m in inst_re.finditer(src):
    cell, name, body = m.groups()
    if cell in ("module", "input", "output", "wire", "inout", "assign"):
        continue
    pins = dict(pin_re.findall(body))
    line = bisect.bisect_right(nl, m.start()) + 1
    if name == inst and pin in pins:
        target = (cell, name, pins[pin], line)
    for p, n in pins.items():
        if (BUF.match(cell) or INV.match(cell)) and p in OUT_PINS:
            by_out[n] = (cell, name, pins.get("A"), line, INV.match(cell) is not None)
        elif not cell.startswith("sky130_fd_sc_hd__"):
            by_out.setdefault(("hier", n), []).append((cell, name, p, line))
if target is None:
    sys.exit(f"{inst}.{pin} not found")
cell, name, net, line = target
print(f"{name} ({cell}, line {line}) .{pin}({net})")
inv = 0
while net in by_out:
    c, n, a, l, i = by_out[net]
    inv ^= i
    print(f"  <- {n} ({c}, line {l}) .A({a})")
    net = a
others = [x for x in by_out.get(("hier", net), []) if x[1] != inst]
print(f"  net {net}{' (inverted on the way)' if inv else ''} also on: "
      + "; ".join(f"{n}.{p} ({c}, line {l})" for c, n, p, l in others))
