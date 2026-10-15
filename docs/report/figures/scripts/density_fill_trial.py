#!/usr/bin/env python3
"""density_fill_trial.png: layer density of user_project_wrapper in 700 um windows, before and
after the Caravel-style fill trial (runs/p7_review/fill_trial, ADR-0019 decision 26).

Input: runs/p7_review/fill_trial/{nofill,withfill}/density.log, lines `T x y fom poly li m1 m2 m3 m4 m5`
(coverage of each 70 um tile, 42 x 51 tiles, die 2920 x 3520 um).
Windows are computed exactly like runs/p7_review/fill_trial/aggregate.py (itself a rewrite of
Caravel's check_density.py): 10 x 10 tiles, step 5 tiles (350 um) for li1 and metals, 1 tile (70 um)
for FOM; partial edge tiles weighted by their area inside the die; windows stop short of the right
and top edge. Lower limits: li1, met1-4 35 %, met5 45 %, FOM 33 %; upper 60 % (met5 76 %, FOM 57 %).
The script prints the same per-layer summary as aggregate.py so the numbers can be compared with
withfill/density.md and nofill/density.md.
"""
import os

import numpy as np
from matplotlib.patches import Rectangle

from common import C1, INK, INK2, REPO, out, plt, style

TRIAL = os.path.join(REPO, "runs/p7_review/fill_trial")
DIE_W, DIE_H, STEP = 2920.0, 3520.0, 70.0
COLS = ["fom", "poly", "li1", "met1", "met2", "met3", "met4", "met5"]
LIMITS = {"fom": (0.33, 0.57), "li1": (0.35, 0.60), "met1": (0.35, 0.60), "met2": (0.35, 0.60),
          "met3": (0.35, 0.60), "met4": (0.35, 0.60), "met5": (0.45, 0.76)}
WIN_STEP = {"fom": 1, "poly": 10}
SHOW = ["fom", "li1", "met1", "met2", "met3", "met4", "met5"]
GRAY = "#9a9994"


def read(path):
    cov, xt, yt = {}, 0, 0
    for line in open(path, errors="replace"):
        p = line.split()
        if p[:1] == ["XTILES:"]:
            xt = int(p[1])
        elif p[:1] == ["YTILES:"]:
            yt = int(p[1])
        elif p[:1] == ["T"] and len(p) == 11:
            cov[(int(p[1]), int(p[2]))] = [float(v) for v in p[3:]]
    assert xt and len(cov) == xt * yt, (path, len(cov), xt, yt)
    return cov, xt, yt


def windows(cov, xt, yt, lay):
    i = COLS.index(lay)
    st = WIN_STEP.get(lay, 5)
    full = STEP * STEP
    area = {(x, y): (min(DIE_W, (x + 1) * STEP) - x * STEP) * (min(DIE_H, (y + 1) * STEP) - y * STEP)
            for x in range(xt) for y in range(yt)}
    vals = []
    for y0 in range(0, yt - 9, st):
        for x0 in range(0, xt - 9, st):
            boxes = [(x, y) for x in range(x0, x0 + 10) for y in range(y0, y0 + 10)]
            d = sum(cov[b][i] * full for b in boxes) / sum(area[b] for b in boxes)
            vals.append((d, x0 * STEP, y0 * STEP))
    whole = sum(cov[b][i] * full for b in cov) / (DIE_W * DIE_H)
    return vals, whole


def main():
    data = {k: read(os.path.join(TRIAL, k, "density.log")) for k in ("nofill", "withfill")}
    res = {k: {lay: windows(*data[k], lay) for lay in SHOW} for k in data}
    for k in res:
        print(f"== {k}")
        for lay in SHOW:
            vals, whole = res[k][lay]
            lo, hi = LIMITS[lay]
            mn, mx = min(vals), max(vals)
            nv = sum(1 for d, _, _ in vals if d < lo or d > hi)
            print(f"{lay:5s} whole {whole:6.1%}  min {mn[0]:6.1%} at ({mn[1]:.0f}, {mn[2]:.0f})  "
                  f"max {mx[0]:6.1%}  out of range {nv} / {len(vals)}")

    style()
    fig = plt.figure(figsize=(16, 12.5))
    gs = fig.add_gridspec(2, 7, height_ratios=[1, 1.25], hspace=0.32, wspace=0.35)
    rng = np.random.default_rng(1)
    for j, lay in enumerate(SHOW):
        ax = fig.add_subplot(gs[0, j])
        lo, hi = LIMITS[lay]
        for xpos, k, col in ((0, "nofill", GRAY), (1, "withfill", C1)):
            v = np.array([d for d, _, _ in res[k][lay][0]]) * 100
            jit = rng.uniform(-0.18, 0.18, len(v))
            ax.scatter(xpos + jit, v, s=(6 if lay == "fom" else 16), color=col, alpha=0.75, lw=0, zorder=3)
            ax.plot([xpos - 0.3, xpos + 0.3], [np.median(v)] * 2, color=INK, lw=1.5, zorder=4)
            nv = int(np.sum((v < lo * 100) | (v > hi * 100)))
            ax.text(xpos, 87, f"{nv}/{len(v)}\nout", ha="center", va="top", fontsize=8.5,
                    color=(INK if nv else INK2), fontweight=("bold" if nv else "normal"))
        ax.axhline(lo * 100, color="#e34948", lw=1.6, ls="--", zorder=2)
        ax.axhline(hi * 100, color="#e34948", lw=1.0, ls=":", zorder=2)
        ax.set_xlim(-0.6, 1.6)
        ax.set_ylim(0, 90)
        ax.set_yticks(range(0, 81, 10))
        ax.set_xticks([0, 1], ["no fill", "with\nfill"], fontsize=9.5)
        ax.set_title(lay.upper() if lay == "fom" else lay, fontsize=12)
        ax.grid(axis="x", visible=False)
        if j == 0:
            ax.set_ylabel("density in a 700 µm window (%)")
    fig.text(0.02, 0.965, "(a) every 700 µm window: grey = wrapper as harden left it, blue = after the Caravel-style fill; "
             "red dashed = lower limit, red dotted = upper limit;\n     black bar = median; "
             "\"n/N out\" = windows outside the limits (FOM windows step 70 µm, li1 and metals 350 µm)",
             fontsize=10.5, color=INK, va="top")

    for j, lay in enumerate(("fom", "met2")):
        ax = fig.add_subplot(gs[1, j * 3:(j * 3 + 3)] if j == 0 else gs[1, 4:7])
        vals, _ = res["withfill"][lay]
        st = WIN_STEP.get(lay, 5) * STEP
        xs = sorted({x for _, x, _ in vals}); ys = sorted({y for _, _, y in vals})
        grid = np.full((len(ys), len(xs)), np.nan)
        for d, x, y in vals:
            grid[ys.index(y), xs.index(x)] = d * 100
        lo = LIMITS[lay][0] * 100
        # window value drawn at the window centre, one cell per step
        ext = (xs[0] + 350 - st / 2, xs[-1] + 350 + st / 2, ys[0] + 350 - st / 2, ys[-1] + 350 + st / 2)
        im = ax.imshow(grid, origin="lower", extent=ext, cmap="Blues", vmin=30, vmax=60, aspect="equal")
        for d, x, y in vals:
            if d * 100 < lo:
                ax.add_patch(Rectangle((x + 350 - st / 2, y + 350 - st / 2), st, st, fill=False, ec="#e34948", lw=1.6))
        ax.add_patch(Rectangle((0, 0), DIE_W, DIE_H, fill=False, ec=INK2, lw=1, ls="--"))
        ax.add_patch(Rectangle((350.98, 413.44), 694.27, 428.415, fill=False, ec=INK, lw=1.2))
        ax.text(350.98 + 347, 413.44 + 214, "SRAM", ha="center", va="center", fontsize=9, color=INK)
        ax.set_xlim(-100, DIE_W + 100); ax.set_ylim(-100, DIE_H + 100)
        ax.set_xlabel("window centre x (µm)"); ax.set_ylabel("window centre y (µm)")
        ax.grid(False)
        nlow = sum(1 for d, _, _ in vals if d * 100 < lo)
        mn = min(vals)
        ax.set_title(f"({'b' if j == 0 else 'c'}) {lay.upper() if lay == 'fom' else lay} after fill, 700 µm window, "
                     f"step {st:.0f} µm\n{nlow} window(s) below {lo:.0f} % (red), lowest {mn[0]:.1%} at window "
                     f"corner ({mn[1]:.0f}, {mn[2]:.0f}); dashed = die", fontsize=11, loc="left")
        cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.02)
        cb.set_label("density (%)")
    fig.suptitle("user_project_wrapper metal / FOM density before and after a Caravel-style fill trial "
                 "(runs/p7_review/fill_trial, 2026-10-15)", x=0.02, ha="left", y=1.0, fontsize=13.5)
    fig.savefig(out("density_fill_trial.png"), dpi=130)


if __name__ == "__main__":
    main()
