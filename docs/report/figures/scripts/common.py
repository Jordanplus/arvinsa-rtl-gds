"""Shared paths and style for the report figures (docs/report/figures/scripts/)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(FIG, "..", "..", ".."))
PRJ = os.path.dirname(REPO)
CARAVEL = os.path.join(PRJ, "arvinsa-rtl-gds-p7close2_caravel")
H3 = os.path.join(PRJ, "arvinsa-rtl-gds-p7close2_h3")
PICO = os.path.join(PRJ, "arvinsa-rtl-gds-p7close2_pico")

# categorical slots (dataviz reference palette, light mode), fixed order
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#dddcd7"


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 13,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
        "savefig.facecolor": "white", "savefig.bbox": "tight", "savefig.pad_inches": 0.15,
    })


def out(name):
    return os.path.join(FIG, name)
