#!/usr/bin/env python3
"""Layout figures for the report: put um axes, titles and block outlines on the raw KLayout renders
made by render_layouts.sh.

usage: python3 layout_figs.py <raw_dir>
Writes layout_wrapper_full.png, layout_wrapper_soc_zoom.png, layout_soc_top_hazard3.png,
layout_sram_macro.png and layout_picorv32_core.png into docs/report/figures/.

Block outlines come from repo files, not from looking at the picture:
- SRAM location in the wrapper: pnr/user_project_wrapper/pin_plan.toml [block] location (350.98, 413.44);
  in soc_top: pnr/soc_top/config_hazard3.json MACROS ... sram0 location (290.72, 353.6);
  macro size 694.27 x 428.415 um (the macro GDS bbox, printed by gds_shot.py into <png>.json).
- SRAM sub-blocks: instance bboxes of the macro GDS (KLayout, listed in SOURCES.md).
"""
import json
import os
import sys

from matplotlib.patches import Rectangle
from PIL import Image

from common import INK, out, plt

SRAM_W, SRAM_H = 694.27, 428.415
RED = "#e34948"


def load(raw, name):
    meta = json.load(open(os.path.join(raw, name + ".json")))
    return plt.imread(os.path.join(raw, name)), meta


def show(ax, raw, name, xlabel=True):
    img, meta = load(raw, name)
    x1, y1, x2, y2 = meta["box_um"]
    ax.imshow(img, extent=(x1, x2, y1, y2), origin="upper", interpolation="antialiased")
    ax.set_xlim(x1, x2); ax.set_ylim(y1, y2)
    ax.grid(False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(True)
    if xlabel:
        ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    return meta


def outline(ax, x, y, w, h, text, color=RED, ha="left", tx=None, ty=None, fs=11, lw=2.2):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, ec=color, lw=lw, ls="--", zorder=5))
    if text:
        ax.text(tx if tx is not None else x, ty if ty is not None else y + h, text, color=INK, fontsize=fs,
                ha=ha, va="bottom", zorder=6, bbox=dict(fc="white", ec=color, alpha=0.9, pad=3))


def label(ax, x, y, text, fs=11, ha="left", va="center", color=INK):
    ax.text(x, y, text, fontsize=fs, ha=ha, va=va, color=color, zorder=6,
            bbox=dict(fc="white", ec="0.5", alpha=0.9, pad=3))


def save(fig, name, dpi):
    p = out(name)
    fig.savefig(p, dpi=dpi)
    plt.close(fig)
    # palette PNG: the renders have few distinct colours; keeps each file well under 1.5 MB
    Image.open(p).convert("RGB").quantize(colors=160, method=Image.Quantize.FASTOCTREE).save(p, optimize=True)
    print("wrote", p, os.path.getsize(p), "bytes")


def wrapper_full(raw):
    fig, axes = plt.subplots(1, 2, figsize=(16, 10.4))
    show(axes[0], raw, "wrap_full_all.png")
    show(axes[1], raw, "wrap_full_m2m5.png")
    sx, sy = 350.98, 413.44
    for ax in axes:
        outline(ax, sx, sy, SRAM_W, SRAM_H, None)
        outline(ax, 0, 0, 861.12, 522.24, None, color="#1baf7a")
    label(axes[1], sx + SRAM_W + 60, sy + SRAM_H / 2, "SRAM macro u_soc.sram0\n694.27 x 428.415 µm\nat (350.98, 413.44)", fs=10)
    label(axes[1], 900, 200, "Hazard3 SoC logic\n99 % of 25,100 logic cells\nin x ≤ 861, y ≤ 522 µm", fs=10)
    axes[0].set_title("(a) all drawing layers\nempty rows hold 543,617 decap_12 + 425,550 fill cells,\n"
                      "so the met1 rails (blue) cover the whole die", fontsize=11, loc="left")
    axes[1].set_title("(b) met2–met5 only\nsignal routing (met2/met3) is only around the SoC;\n"
                      "met4 (violet) / met5 (yellow) power straps over the whole die", fontsize=11, loc="left")
    fig.suptitle("user_project_wrapper (Caravel user area, 2920 x 3520 µm), final GDS of the closing run (commit 2b04451)\n"
                 "red dashed: SRAM macro; green dashed: box holding 99 % of the SoC logic cells",
                 x=0.01, ha="left", fontsize=13)
    fig.tight_layout()
    save(fig, "layout_wrapper_full.png", 140)


def wrapper_zoom(raw):
    fig, ax = plt.subplots(figsize=(14, 11.6))
    show(ax, raw, "wrap_zoom.png")
    sx, sy = 350.98, 413.44
    outline(ax, sx, sy, SRAM_W, SRAM_H, "SRAM macro u_soc.sram0 (OpenRAM arv_sram_2kbyte_1rw1r_32x512_8), 694.27 x 428.415 µm at (350.98, 413.44)",
            ty=sy + SRAM_H + 6, fs=10.5)
    label(ax, 560, 300, "Hazard3 SoC standard cells (u_soc), placed flat in the wrapper", fs=11)
    label(ax, 1030, 150, "decap / fill cell rows\n(no logic)", fs=10, ha="center")
    ax.set_title("user_project_wrapper, lower-left corner: Hazard3 SoC and SRAM (final GDS, commit 2b04451)\n"
                 "layers: diff, poly, li1, met1–met3 and contacts/vias; met4/met5 power straps hidden for clarity",
                 loc="left", fontsize=12.5)
    fig.tight_layout()
    save(fig, "layout_wrapper_soc_zoom.png", 160)


def soc_top_h3(raw):
    fig, ax = plt.subplots(figsize=(14, 11.8))
    show(ax, raw, "h3.png")
    sx, sy = 290.72, 353.6
    outline(ax, sx, sy, SRAM_W, SRAM_H, None)
    label(ax, sx + SRAM_W / 2, sy + SRAM_H / 2, "SRAM macro sram0\n694.27 x 428.415 µm at (290.72, 353.6)", fs=11, ha="center")
    label(ax, 500, 170, "Hazard3 CPU, bus, UART, GPIO, boot ROM, test control\n(92,321 instances incl. fill, decap and tap cells)", fs=11, ha="center")
    ax.set_title("soc_top with Hazard3 (1000 x 800 µm), final GDS of the closing run (commit 2b04451)\n"
                 "all drawing layers; 44 ns clock, 15 signoff corners: worst setup +0.656 ns, hold +0.126 ns",
                 loc="left", fontsize=12.5)
    fig.tight_layout()
    save(fig, "layout_soc_top_hazard3.png", 160)


def sram(raw):
    fig = plt.figure(figsize=(16, 13.6))
    ax = fig.add_axes([0.05, 0.44, 0.92, 0.51])
    show(ax, raw, "sram_full.png")
    blocks = [  # name, x1, y1, x2, y2 (instance bboxes in the macro GDS), label anchor
        ("bitcell array 128 rows x 128 columns (4 words per row)\nwith replica and dummy cells around it", 139.3, 101.8, 556.5, 368.2, "c"),
        ("port 0 (RW) address:\nrow decoder +\nwordline drivers", 75.3, 106.1, 138.2, 361.7, "l"),
        ("port 1 (R) address:\nwordline drivers +\nrow decoder", 557.6, 108.2, 620.5, 363.8, "r"),
        ("port 0 data: precharge, column mux, sense amps, write drivers, write mask", 139.2, 47.4, 547.8, 101.8, "b"),
        ("port 1 data: precharge, column mux, sense amps", 139.5, 368.2, 550.9, 404.1, "t"),
        ("control logic RW", 12.5, 44.3, 74.5, 137.3, "l2"),
        ("control logic R", 621.7, 318.5, 681.8, 411.4, "r2"),
        ("data / wmask / col addr DFFs (port 0)", 80.1, 12.0, 302.8, 19.6, "b2"),
    ]
    for name, x1, y1, x2, y2, where in blocks:
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec=RED, lw=1.8, ls="--", zorder=5))
        if where == "c":
            label(ax, (x1 + x2) / 2, (y1 + y2) / 2, name, fs=12, ha="center")
        elif where == "l":
            label(ax, 12, (y1 + y2) / 2 + 60, name, fs=9.5, ha="left")
        elif where == "r":
            label(ax, x2 + 4, (y1 + y2) / 2 - 20, name, fs=9.5, ha="left")
        elif where == "b":
            label(ax, (x1 + x2) / 2, y1 + 18, name, fs=9.5, ha="center")
        elif where == "t":
            label(ax, (x1 + x2) / 2, y2 + 14, name, fs=9.5, ha="center")
        elif where == "l2":
            label(ax, x1, y2 + 14, name, fs=9.5, ha="left")
        elif where == "r2":
            label(ax, x2, y1 - 14, name, fs=9.5, ha="right")
        elif where == "b2":
            label(ax, x2 + 6, y1 + 4, name, fs=9.5, ha="left")
    ax.add_patch(Rectangle((128, 98), 40, 25, fill=False, ec="#2a78d6", lw=2.4, zorder=6))
    ax.text(166, 96, "(b)", color="#2a78d6", fontsize=12, fontweight="bold", ha="left", va="top", zorder=6)
    ax.set_title("(a) whole macro, 694.27 x 428.415 µm; drawing layers except "
                 "met2 / met4 (hidden: the met2 bitlines cover the array)", loc="left", fontsize=11.5)
    ax2 = fig.add_axes([0.05, 0.03, 0.55, 0.30])
    show(ax2, raw, "sram_zoom.png")
    ax2.set_title("(b) zoom 40 x 25 µm at the lower-left corner of the array, all drawing layers:\n"
                  "port 0 wordline drivers (left), bitcells (upper right), column periphery (bottom)",
                  loc="left", fontsize=11)
    fig.text(0.63, 0.31, "OpenRAM-generated SRAM (ADR-0018)\narv_sram_2kbyte_1rw1r_32x512_8\n\n"
             "2 KB, 512 words x 32 bit, write mask per 8 bit\nport 0: read/write (1RW), port 1: read-only (1R)\n\n"
             "block outlines = instance bounding boxes\nin the macro GDS\n(ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/\nopenram/*.gds)",
             fontsize=11.5, va="top", ha="left", color=INK)
    fig.suptitle("SRAM macro layout (sky130A)", x=0.05, ha="left", y=0.995, fontsize=14)
    save(fig, "layout_sram_macro.png", 150)


def pico(raw):
    fig, ax = plt.subplots(figsize=(12.5, 12.4))
    show(ax, raw, "pico.png")
    ax.set_title("picorv32_core (533.575 x 544.295 µm), final GDS of the closing run (commit 2b04451)\n"
                 "all drawing layers; 40 ns clock, 9 corners: worst setup +6.175 ns, hold +0.039 ns",
                 loc="left", fontsize=12.5)
    fig.tight_layout()
    save(fig, "layout_picorv32_core.png", 160)


if __name__ == "__main__":
    raw = sys.argv[1]
    for f in (wrapper_full, wrapper_zoom, soc_top_h3, sram, pico):
        f(raw)
