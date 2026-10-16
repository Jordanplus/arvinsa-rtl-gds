#!/usr/bin/env python3
"""Reset value of housekeeping's gpio_configure[33..37] in the Caravel gate-level netlist, and what resets them.

usage: python3 gl_reset_values.py <caravel-lite>/verilog/gl/housekeeping.v

For every flop whose Q is gpio_configure[N][b] (N = 33..37): dfrtp (RESET_B) resets to 0, dfstp (SET_B) to 1.
The RESET_B / SET_B net is traced back through buffers and inverters until it reaches a module port, so the
output shows which housekeeping input resets these registers. Read only; the netlist is not simulated.
"""
import bisect
import re
import sys
from collections import defaultdict

src = open(sys.argv[1]).read()
nl = [m.start() for m in re.finditer("\n", src)]
ports = set(re.findall(r"^\s*input\s+(?:\[[^\]]*\]\s*)?(\\?\S+?)\s*;", src, re.M))
inst_re = re.compile(r"^\s*(sky130_fd_sc_hd__\w+)\s+(\S+)\s*\((.*?)\);", re.M | re.S)
pin_re = re.compile(r"\.(\w+)\(\s*([^()]*?)\s*\)")
driver = {}           # net -> (cell, instance, input net)
flops = defaultdict(dict)
for m in inst_re.finditer(src):
    cell, name, body = m.group(1), m.group(2), m.group(3)
    pins = dict(pin_re.findall(body))
    line = bisect.bisect_right(nl, m.start()) + 1
    base = re.sub(r"_\d+$", "", cell)
    if base in ("sky130_fd_sc_hd__buf", "sky130_fd_sc_hd__clkbuf", "sky130_fd_sc_hd__dlygate4sd3",
                "sky130_fd_sc_hd__dlygate4sd1", "sky130_fd_sc_hd__dlymetal6s2s", "sky130_fd_sc_hd__clkdlybuf4s25",
                "sky130_fd_sc_hd__clkdlybuf4s50", "sky130_fd_sc_hd__dlygate4sd2"):
        driver[pins.get("X")] = (cell, name, pins.get("A"), 0, line)
    elif base in ("sky130_fd_sc_hd__inv", "sky130_fd_sc_hd__clkinv", "sky130_fd_sc_hd__clkinvlp"):
        driver[pins.get("Y")] = (cell, name, pins.get("A"), 1, line)
    q = pins.get("Q", "")
    fm = re.match(r"\\gpio_configure\[(3[3-7])\]\[(\d+)\]", q)
    if fm:
        flops[int(fm.group(1))][int(fm.group(2))] = (cell, name, pins.get("RESET_B"), pins.get("SET_B"), line)


def trace(net):
    path, inv = [], 0
    while net in driver:
        cell, name, a, i, line = driver[net]
        path.append(f"{name}({cell}, line {line})")
        inv ^= i
        net = a
    return net, inv, path


for n in range(33, 38):
    bits = flops[n]
    value = 0
    roots = set()
    for b in range(13):
        cell, name, rst, st, line = bits[b]
        if rst is not None:
            v, net = 0, rst
        elif st is not None:
            v, net = 1, st
        else:
            sys.exit(f"gpio_configure[{n}][{b}] {name} {cell} has no RESET_B/SET_B")
        root, inv, path = trace(net)
        roots.add((root, inv, root in ports))
        value |= v << b
        print(f"gpio_configure[{n}][{b:2d}]  {cell:26s} {name:8s} line {line:6d}  "
              f"{'SET_B' if v else 'RESET_B'}={net} <- {' <- '.join(path) or '(direct)'} <- {root}")
    print(f"gpio_configure[{n}] reset value = 0x{value:04x}; reset source(s): "
          + ", ".join(f"{r}{' (inverted)' if i else ''}{' [module input]' if p else ''}" for r, i, p in sorted(roots)))
    print()
