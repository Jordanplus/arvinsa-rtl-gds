#!/usr/bin/env python3
"""ir_drop_map.png: static IR drop of user_project_wrapper from Caravel's pads, max-power pattern,
worst corner / window of the closing run (make ir-caravel, ADR-0019 decision 20).

Input: <caravel worktree>/runs/ir_caravel/ir_caravel/corners/<corner>_<window>/step/net-{vccd1,vssd1}.csv
(OpenROAD PSM node voltages at every instance power pin: Instance, Terminal, Layer, X, Y, Voltage) and
vsrc/*.vsrc (the supply points, at Caravel's single vccd1 / vssd1 pad on the right of the chip).
The corner/window is the one with the largest VDD + GND drop in results.json `drops`.
Drop = 1.60 V - node voltage for both nets: PSM solves vssd1 with the same 1.60 V source value
(irdrop.rpt "Supply voltage : 1.60e+00 V" for vssd1 too), so for the ground net 1.60 - V is the
VSS (ground) rise; its maximum equals the report's "Worstcase IR drop" for vssd1.
Each 20 um bin shows the largest drop of the pins inside it.
"""
import csv
import json
import os

import numpy as np
from matplotlib.patches import Rectangle

from common import CARAVEL, INK, INK2, out, plt, style

IR = os.path.join(CARAVEL, "runs/ir_caravel/ir_caravel")
VDD = 1.60
BIN = 20.0
DIE_W, DIE_H = 2920.0, 3520.0


def load(path):
    xs, ys, vs = [], [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            xs.append(float(r["X location"])); ys.append(float(r["Y location"])); vs.append(float(r["Voltage"]))
    return np.array(xs), np.array(ys), np.array(vs)


def binmax(x, y, v):
    nx, ny = int(np.ceil(DIE_W / BIN)), int(np.ceil(DIE_H / BIN))
    g = np.full((ny, nx), np.nan)
    ix = np.clip((x / BIN).astype(int), 0, nx - 1)
    iy = np.clip((y / BIN).astype(int), 0, ny - 1)
    flat = np.full(nx * ny, -np.inf)
    np.maximum.at(flat, iy * nx + ix, v)
    flat[np.isinf(flat)] = np.nan
    return flat.reshape(ny, nx)


def main():
    res = json.load(open(os.path.join(IR, "results.json")))
    assert all(ok for ok, _ in res["rows"]), "results.json has a FAIL row"
    worst = max(res["drops"], key=lambda k: sum(res["drops"][k]))
    rep_vdd, rep_gnd = res["drops"][worst]
    cdir = os.path.join(IR, "corners", worst)
    corner, window = worst.rsplit("_win_", 1)
    style()
    fig, axes = plt.subplots(1, 2, figsize=(16, 10.2))
    for ax, net, rep, what in ((axes[0], "vccd1", rep_vdd, "VDD drop"), (axes[1], "vssd1", rep_gnd, "VSS rise")):
        x, y, v = load(os.path.join(cdir, "step", f"net-{net}.csv"))
        d = (VDD - v) * 1000
        assert abs(d.max() - rep * 1000) < 0.01, (net, d.max(), rep)
        g = binmax(x, y, d)
        im = ax.imshow(g, origin="lower", extent=(0, g.shape[1] * BIN, 0, g.shape[0] * BIN),
                       cmap="Oranges", vmin=np.nanmin(g), vmax=np.nanmax(g), interpolation="nearest")
        ax.add_patch(Rectangle((0, 0), DIE_W, DIE_H, fill=False, ec=INK2, lw=1, ls="--"))
        ax.add_patch(Rectangle((350.98, 413.44), 694.27, 428.415, fill=False, ec=INK, lw=1.4))
        ax.text(350.98 + 347, 413.44 + 440, "SRAM (one power node in the CSV)", ha="center", va="bottom", fontsize=9.5, color=INK)
        ax.add_patch(Rectangle((0, 0), 861.12, 522.24, fill=False, ec="#2a78d6", lw=1.4, ls="--"))
        src = [tuple(map(float, l.split(",")[:2])) for l in open(os.path.join(cdir, "vsrc", f"{net}.vsrc")) if l.strip()]
        ax.scatter([p[0] for p in src], [p[1] for p in src], marker="s", s=60, color=INK, zorder=5, clip_on=False)
        ax.annotate(f"{net} pad\n(supply points,\n{VDD:.2f} V)", xy=src[0], xytext=(src[0][0] - 60, src[0][1] - 420),
                    ha="right", fontsize=10, color=INK, arrowprops=dict(arrowstyle="->", color=INK, lw=1),
                    bbox=dict(fc="white", ec="0.5", alpha=0.9, pad=3))
        i = int(np.argmax(d))
        ax.scatter([x[i]], [y[i]], marker="x", s=90, color="#e34948", lw=2.5, zorder=6)
        ax.annotate(f"worst {d[i]:.2f} mV\nat ({x[i]:.0f}, {y[i]:.0f})", xy=(x[i], y[i]),
                    xytext=(x[i] + 700, y[i] + 950), fontsize=10, color=INK,
                    arrowprops=dict(arrowstyle="->", color=INK, lw=1), bbox=dict(fc="white", ec="0.5", alpha=0.9, pad=3))
        ax.set_xlim(-60, 3120); ax.set_ylim(-60, DIE_H + 60)
        ax.set_aspect("equal"); ax.grid(False)
        ax.set_xlabel("x (µm)"); ax.set_ylabel("y (µm)")
        ax.set_title(f"{what} ({net}): worst {d.max():.2f} mV, median over {len(d):,} pins {np.median(d):.2f} mV",
                     loc="left", fontsize=11.5)
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.set_label(f"{what}, max per {BIN:.0f} µm bin (mV)")
        print(f"{net}: pins {len(d)}, worst {d.max():.3f} mV at {x[i]:.1f},{y[i]:.1f} ({rep*1000:.2f} in results.json), "
              f"median {np.median(d):.3f}, min {d.min():.3f}")
    fig.suptitle(f"user_project_wrapper static IR from Caravel's pads, max-power pattern: corner {corner}, window {window}\n"
                 f"VDD drop {rep_vdd*1000:.2f} mV + VSS rise {rep_gnd*1000:.2f} mV = {(rep_vdd+rep_gnd)*1000:.2f} mV "
                 f"(limit 20 mV; worst of 2 slow corners x 3 windows). Blue dashed: 99 % of the SoC logic cells",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    fig.savefig(out("ir_drop_map.png"), dpi=130)


if __name__ == "__main__":
    main()
