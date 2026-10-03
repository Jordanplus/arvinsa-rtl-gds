#!/usr/bin/env python3
"""Gate area (um^2) connected to each input pin of an OpenRAM macro, from its SPICE netlist.

usage: gate_area.py <macro.spice> <top subckt>

Flattens the hierarchy and, for every input port of the top subckt (its `*.PININFO` line, `name:I`), sums W*L of each
sky130_fd_pr__{n,p}fet_01v8* transistor whose gate terminal is on that net (m= multiplies).
Used by gen_antenna_lef.py (ANTENNAGATEAREA). Python stdlib only.
"""
import re
import sys
from collections import defaultdict

FET = re.compile(r"sky130_fd_pr__[np]fet_01v8\w*$")


def parse(path):
    subckts, cur, lines = {}, None, []
    for raw in open(path, encoding="utf8", errors="replace"):
        raw = raw.rstrip("\n")
        if raw.startswith("+") and lines:
            lines[-1] += " " + raw[1:]
        else:
            lines.append(raw)
    for line in lines:
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        tok = s.split()
        if tok[0].lower() == ".subckt":
            cur = tok[1]
            subckts[cur] = {"ports": tok[2:], "elems": []}
        elif tok[0].lower() == ".ends":
            cur = None
        elif cur and tok[0][0] in "Xx":
            params = {k.lower(): v for k, v in (t.split("=", 1) for t in tok[1:] if "=" in t)}
            nets = [t for t in tok[1:] if "=" not in t]
            subckts[cur]["elems"].append((nets[:-1], nets[-1], params))
    return subckts


def num(v):
    m = re.fullmatch(r"([-\d.eE+]+)([a-zA-Z]*)", v)
    scale = {"": 1, "u": 1, "n": 1e-3, "m": 1e3}.get(m.group(2).lower(), None) if m else None
    if scale is None:
        raise ValueError(f"unsupported number {v!r}")
    return float(m.group(1)) * scale   # W/L in this netlist are in um


def gate_areas(subckts, top):
    memo = {}

    def per_port(name):
        """{port index: gate area} for a subckt (gates reachable from each port)."""
        if name in memo:
            return memo[name]
        sc = subckts[name]
        area = defaultdict(float)  # local net -> gate area
        for nets, model, params in sc["elems"]:
            if FET.match(model):
                d, g, s, b = nets[:4]
                area[g] += num(params.get("w", "0")) * num(params.get("l", "0")) * float(params.get("m", "1"))
            elif model in subckts:
                child = per_port(model)
                for i, a in child.items():
                    area[nets[i]] += a
        memo[name] = {i: area.get(p, 0.0) for i, p in enumerate(sc["ports"])}
        return memo[name]

    res = per_port(top)
    return {subckts[top]["ports"][i]: a for i, a in res.items()}


def inputs(path, top):
    """Input ports of `top` from its `*.PININFO name:I ...` line."""
    text = open(path, encoding="utf8", errors="replace").read()
    m = re.search(r"^\.SUBCKT " + re.escape(top) + r" .*?\n\*\.PININFO (.*)$", text, re.M | re.S | re.I)
    if not m:
        raise ValueError(f"no *.PININFO line for {top}")
    return [p[:-2] for p in m.group(1).split() if p.endswith(":I")]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sc = parse(sys.argv[1])
    ga = gate_areas(sc, sys.argv[2])
    for p in inputs(sys.argv[1], sys.argv[2]):
        print(f"{p} {ga.get(p, 0.0):.4f}")
