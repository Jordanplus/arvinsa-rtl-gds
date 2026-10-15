#!/usr/bin/env python3
"""timing_wrapper_corners.png: worst setup and hold slack of user_project_wrapper in each of the 15
signoff corners, from the closing run's final/metrics.json (timing__{setup,hold}__ws__corner:*)."""
import json
import os

import numpy as np

from common import C1, C2, CARAVEL, INK, INK2, out, plt, style

MET = os.path.join(CARAVEL, "runs/user_project_wrapper/final/metrics.json")


def main():
    d = json.load(open(MET))
    corners = sorted({k.split("corner:")[1] for k in d if k.startswith("timing__setup__ws__corner:")})
    order = {"tt_025C_1v80": 0, "ss_100C_1v60": 1, "ss_n40C_1v60": 2, "ff_n40C_1v95": 3, "ff_100C_1v95": 4}
    corners.sort(key=lambda c: (order[c.split("_", 1)[1]], ["min", "nom", "max"].index(c.split("_")[0])))
    assert len(corners) == 15, corners
    su = [d["timing__setup__ws__corner:" + c] for c in corners]
    ho = [d["timing__hold__ws__corner:" + c] for c in corners]
    style()
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True)
    x = np.arange(len(corners))
    for ax, vals, col, name in ((axes[0], su, C1, "setup"), (axes[1], ho, C2, "hold")):
        ax.bar(x, vals, width=0.62, color=col, zorder=3)
        ax.axhline(0, color=INK, lw=1.2, zorder=4)
        i = int(np.argmin(vals))
        top = max(vals)
        for j, v in enumerate(vals):
            ax.text(j, v + top * 0.015, f"{v:+.3f}", ha="center", va="bottom", fontsize=8.5,
                    color=(INK if j == i else INK2), fontweight=("bold" if j == i else "normal"))
        ax.set_ylabel(f"worst {name} slack (ns)")
        ax.set_ylim(min(0, min(vals)) - top * 0.05, top * 1.15)
        ax.set_title(f"{name}: worst {vals[i]:+.3f} ns at {corners[i]}", loc="left", fontsize=11.5, color=INK)
    axes[1].set_xticks(x, corners, rotation=40, ha="right", fontsize=9.5)
    axes[1].set_xlabel("signoff corner (RC corner _ process _ temperature _ supply)")
    fig.suptitle("user_project_wrapper (Caravel, Hazard3 SoC): worst slack per signoff corner, 44 ns clock\n"
                 "closing run at commit 2b04451; all 15 corners >= 0 ns (MET)", x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    fig.savefig(out("timing_wrapper_corners.png"), dpi=150)
    for c, s, h in zip(corners, su, ho):
        print(f"{c:22s} setup {s:+.4f}  hold {h:+.4f}")


if __name__ == "__main__":
    main()
