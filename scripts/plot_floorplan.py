#!/usr/bin/env python3
"""Floorplan picture for the review before placement (skill chip-floorplan-pin-planning, CLAUDE.md rule 14).

usage: plot_floorplan.py <def> <png> [--plan pnr/<design>/pin_plan.toml] [--dpi N] [--title TEXT]

Draws from a LibreLane DEF (a run stopped after Odb.ApplyDEFTemplate or later): the die, the PDN
(vccd1 / vssd1 rings bold, straps thin), every placed macro (outline from the DEF component and
the size from --lef files listed in the plan), the standard cells coloured by module and a rough box
around each module (the 5th to 95th percentile of its cell positions; needs hierarchical instance
names, SYNTH_HIERARCHY_MODE = deferred_flatten), the pins (all GPIO numbers; the plan's pins in red
with their signal), the Wishbone and logic-analyzer pins. Tap and endcap cells are not drawn.
Python stdlib + matplotlib.
"""
import argparse
import collections
import os
import re
import tomllib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import Rectangle            # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NAMES = {"u_soc.u_cpu": "CPU (Hazard3 + AHB bridge)", "u_soc.u_uart": "UART", "u_soc.u_test_ctrl": "test control",
         "u_soc.u_bootrom": "boot ROM", "u_soc.u_bus": "bus + SRAM port mux", "u_soc.u_gpio": "GPIO",
         "u_wb": "Wishbone host bridge", "(top)": "wrapper / soc_top glue"}
COLORS = ["tab:blue", "tab:orange", "tab:green", "tab:purple", "tab:brown", "tab:pink", "tab:olive", "tab:cyan", "0.4"]


def module_of(name):
    n = name.replace("\\", "")
    parts = n.split(".")
    if parts[0] == "u_soc" and len(parts) > 2:
        return "u_soc." + parts[1]
    if len(parts) > 1 and parts[0] != "u_soc":
        return parts[0]
    return "(top)"


def lef_sizes(paths):
    out = {}
    for p in paths:
        t = open(p, errors="replace").read()
        for m in re.finditer(r"MACRO\s+(\S+).*?SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", t, re.S):
            out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("def_file")
    ap.add_argument("png")
    ap.add_argument("--plan")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    t = open(a.def_file, errors="replace").read()
    u = float(re.search(r"UNITS DISTANCE MICRONS (\d+)", t).group(1))
    x0, y0, x1, y1 = (int(v) / u for v in re.search(r"DIEAREA \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)", t).groups())
    plan = tomllib.load(open(a.plan, "rb")) if a.plan else {}
    lefs = [os.path.join(ROOT, plan["block"]["macro_lef"])] if plan.get("block", {}).get("macro_lef") else []
    sizes = lef_sizes(lefs)

    w, h = x1 - x0, y1 - y0
    fig, ax = plt.subplots(figsize=(20, 20 * h / w + 1), dpi=a.dpi)
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, lw=2, ec="k"))

    sn = t[t.index("SPECIALNETS"):t.index("END SPECIALNETS")] if "SPECIALNETS" in t else ""
    pcol = {"vccd1": "tab:red", "vssd1": "tab:blue"}
    for blk in re.split(r"\n\s*- ", sn)[1:]:
        net = blk.split()[0]
        if net not in pcol:
            continue
        for m in re.finditer(r"(met4|met5) (\d+) (?:\+ SHAPE (\w+) )?\( (-?\d+) (-?\d+) \) \( (\*|-?\d+) (\*|-?\d+) \)", blk):
            _, _, shape, xa, ya, xb, yb = m.groups()
            xa, ya = int(xa) / u, int(ya) / u
            xb = xa if xb == "*" else int(xb) / u
            yb = ya if yb == "*" else int(yb) / u
            ax.plot([xa, xb], [ya, yb], color=pcol[net], lw=(1.5 if shape == "RING" else 0.4), alpha=(0.8 if shape == "RING" else 0.25))

    comps = t[t.index("COMPONENTS"):t.index("END COMPONENTS")]
    cells = collections.defaultdict(list)
    for name, cell, x, y in re.findall(r"- (\S+) (\S+) .*?\+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \)", comps):
        if cell in sizes:
            sx, sy = int(x) / u, int(y) / u
            ax.add_patch(Rectangle((sx, sy), *sizes[cell], fc="orange", ec="k", lw=1.5, alpha=0.55, zorder=2))
            ax.text(sx + sizes[cell][0] / 2, sy + sizes[cell][1] / 2,
                    "SRAM macro %s\n%s\n%.0f x %.0f um at (%.2f, %.2f)" % (name.replace("\\", ""), cell, *sizes[cell], sx, sy),
                    ha="center", va="center", fontsize=11, zorder=5)
            continue
        if "TAP" in name or "PHY_EDGE" in name or "tapvpwr" in cell:
            continue
        cells[module_of(name)].append((int(x) / u, int(y) / u))
    order = sorted(cells, key=lambda k: -len(cells[k]))
    for i, mod in enumerate(order):
        pts, c = cells[mod], COLORS[i % len(COLORS)]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=0.6, color=c, alpha=0.6, zorder=3, linewidths=0)
        if len(pts) >= 20:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            bx0, bx1, by0, by1 = pct(xs, 0.05), pct(xs, 0.95), pct(ys, 0.05), pct(ys, 0.95)
            ax.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=False, ec=c, lw=2.2, ls="--", zorder=4))
            ax.text(bx0, by1 + 6, "%s  (%d cells)" % (NAMES.get(mod, mod), len(pts)), color=c, fontsize=11,
                    fontweight="bold", zorder=6, bbox=dict(fc="white", ec="none", alpha=0.7, pad=1))

    pins = {n: (int(x) / u, int(y) / u) for n, x, y in
            re.findall(r"- (\S+) \+ NET \S+[^;]*?\+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \)", t, re.S)}
    planned = {p["gpio"]: p["signal"] for p in plan.get("pin", [])}
    wb = [p for n, p in pins.items() if n.startswith(("wb_", "wbs_"))]
    la = [p for n, p in pins.items() if n.startswith("la_data_out[")]
    ax.scatter([p[0] for p in wb], [p[1] for p in wb], s=10, color="tab:green", zorder=6, label="Wishbone pins")
    ax.scatter([p[0] for p in la], [p[1] for p in la], s=4, color="tab:purple", zorder=6, label="logic analyzer pins")
    for g in range(64):
        if f"io_in[{g}]" not in pins:
            continue
        x, y = pins[f"io_in[{g}]"]
        hit = g in planned
        ax.scatter([x], [y], s=(70 if hit else 15), color=("tab:red" if hit else "0.55"), zorder=7)
        dx = 25 if x < (x0 + x1) / 2 else -25
        ax.text(x + dx, y - (45 if y > y1 - 10 else 0), ("GPIO %d %s" % (g, planned[g])) if hit else str(g),
                fontsize=(11 if hit else 8), color=("tab:red" if hit else "0.4"), ha=("left" if dx > 0 else "right"),
                va="center", zorder=7)
    ax.set_xlim(x0 - 0.04 * w, x1 + 0.04 * w)
    ax.set_ylim(y0 - 0.04 * h, y1 + 0.04 * h)
    ax.set_aspect("equal")
    ax.set_xlabel("um"); ax.set_ylabel("um")
    ax.set_title((a.title + "\n" if a.title else "") + "red: vccd1, blue: vssd1 (ring bold, straps thin); dashed box: 5-95 % of a module's cells",
                 fontsize=14)
    ax.legend(loc="upper right", fontsize=11, markerscale=2)
    fig.tight_layout()
    fig.savefig(a.png)
    print("wrote", a.png, {NAMES.get(k, k): len(v) for k, v in cells.items()})


if __name__ == "__main__":
    main()
