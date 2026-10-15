#!/usr/bin/env python3
"""Aggregate density.tcl's per-70um coverage into 700 um windows, the way Caravel's
scripts/check_density.py does (metals and li1 step 350 um, FOM steps 70 um), with the
partial edge boxes weighted by the area that is inside the die.

usage: aggregate.py <density.log> <out.md> [label]
Limits from check_density.py: li1, met1-4 35-60 %, met5 45-76 %, FOM 33-57 %.
"""
import sys

DIE_W, DIE_H, STEP = 2920.0, 3520.0, 70.0
LAYERS = ["fom", "poly", "li1", "met1", "met2", "met3", "met4", "met5"]
LIMITS = {"fom": (0.33, 0.57), "li1": (0.35, 0.60), "met1": (0.35, 0.60), "met2": (0.35, 0.60),
          "met3": (0.35, 0.60), "met4": (0.35, 0.60), "met5": (0.45, 0.76)}
WIN_STEP = {"fom": 1, "poly": 10}  # in 70 um boxes; others 5


def main(log, out, label):
    cov, xt, yt = {}, 0, 0
    for line in open(log, errors="replace"):
        p = line.split()
        if p[:1] == ["XTILES:"]:
            xt = int(p[1])
        elif p[:1] == ["YTILES:"]:
            yt = int(p[1])
        elif p[:1] == ["T"] and len(p) == 11:
            cov[(int(p[1]), int(p[2]))] = [float(v) for v in p[3:]]
    if not xt or len(cov) != xt * yt:
        print(f"aggregate: FAIL tiles {len(cov)} of {xt}x{yt}")
        return 1
    area = {(x, y): (min(DIE_W, (x + 1) * STEP) - x * STEP) * (min(DIE_H, (y + 1) * STEP) - y * STEP)
            for x in range(xt) for y in range(yt)}
    full = STEP * STEP
    rows, worst, nviol = [], {}, {}
    for i, lay in enumerate(LAYERS):
        st = WIN_STEP.get(lay, 5)
        vals = []
        # same windows as check_density.py: they stop short of the right / top edge (the last
        # 120 / 20 um of the wrapper are in no window; in the real check they are judged in chip
        # coordinates together with the harness, which a wrapper-alone trial cannot do)
        for y0 in range(0, yt - 9, st):
            for x0 in range(0, xt - 9, st):
                boxes = [(x, y) for x in range(x0, x0 + 10) for y in range(y0, y0 + 10)]
                d = sum(cov[b][i] * full for b in boxes) / sum(area[b] for b in boxes)
                vals.append((d, x0 * STEP, y0 * STEP))
        whole = sum(cov[b][i] * full for b in cov) / (DIE_W * DIE_H)
        lo, hi = LIMITS.get(lay, (None, None))
        nv = sum(1 for d, _, _ in vals if lo is not None and (d < lo or d > hi))
        mn, mx = min(vals), max(vals)
        worst[lay], nviol[lay] = mn, nv
        lim = f"{lo:.0%}–{hi:.0%}" if lo is not None else "（無）"
        rows.append(f"| {lay} | {lim} | {whole:.1%} | {mn[0]:.1%}（{mn[1]:.0f}, {mn[2]:.0f}） | "
                    f"{mx[0]:.1%}（{mx[1]:.0f}, {mx[2]:.0f}） | {nv} / {len(vals)} |")
    with open(out, "w") as f:
        f.write(f"# 密度彙總：{label}\n\n")
        f.write(f"70 µm 格子 {xt} × {yt}；700 µm 視窗，li1 與金屬步進 350 µm、FOM 70 µm、poly 700 µm；"
                f"座標是視窗左下角（µm）。\n\n")
        f.write("| 層 | check_density 的範圍 | 整塊 | 最低視窗 | 最高視窗 | 超出範圍的視窗 |\n|---|---|---|---|---|---|\n")
        f.write("\n".join(rows) + "\n")
    print(open(out).read())
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else sys.argv[1]))
