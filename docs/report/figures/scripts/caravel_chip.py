#!/usr/bin/env python3
"""caravel_chip_{zh,en}.png: the whole Caravel chip, its pad ring and where this design sits.

Data (read only; nothing in the Caravel tree is executed):
  <caravel>  caravel-lite tag 2024.09.12-1 (commit 5593d992bbeb5608b7524bc279d91237371612f1), copied from
             /opt/caravel of the precheck image chipfoundry/mpw_precheck. Its def/chip_io.def is git blob
             9af4f403..., the ChipFoundry CC2509 file checked in pnr/user_project_wrapper/caravel_pwr/README.md.
    def/caravel.def       DIEAREA (line 6); the 63 package pins (PINS, line 1927 on): each pin's centre
                          lies inside one pad, which gives every pad its signal / net name
    def/chip_io.def       pad and corner cells (COMPONENTS, lines 15830-17467), the three
                          sky130_ef_io__disconnect_vdda_slice_5um cells that split the analog ring
    def/caravel_core.def  placement of mprj (user_project_wrapper), housekeeping, clock_ctrl, por,
                          rstb_level; origins of the flattened pll.* and mgmt_buffers.* cells (10th-90th
                          percentile box, as the cells have no hierarchy box of their own)
  <repo>
    pnr/user_project_wrapper/pin_plan.toml          SRAM location, the GPIOs this design uses
    pnr/user_project_wrapper/caravel_pwr/bridges.txt met3 bridges (manual_power_connections.lef,
                                                     efabless/caravel 27cbe49c), caravel_core units
    pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def  Wishbone pin positions
Cell sizes are LEF SIZE values, written below with their source line. The SoC logic box is schematic:
x <= 861.12, y <= 522.24 um in wrapper coordinates (99th percentile of the logic cells,
docs/report/figures/SOURCES.md, figure 1).

usage: python3 caravel_chip.py [--caravel DIR] [--repo DIR] [--lang zh en]
       (default --caravel: $CARAVEL_SRC, else <repo>/.tools/caravel-lite, which git ignores)
Getting <caravel> (the image is the one `make precheck-caravel` uses; only def/ and verilog/ are needed):
  cid=$(docker create --platform linux/amd64 chipfoundry/mpw_precheck:latest true)
  mkdir -p .tools/caravel-lite && docker cp $cid:/opt/caravel/def .tools/caravel-lite/
  docker cp $cid:/opt/caravel/verilog .tools/caravel-lite/ && docker rm $cid
  git hash-object .tools/caravel-lite/def/chip_io.def   # must print 9af4f4037af382bb01eb3ff256e4a251a585ce6a
Writes docs/report/figures/caravel_chip_<lang>.png.
"""
import argparse
import os
import re
import tomllib

import numpy as np
from matplotlib.patches import Rectangle

from common import FIG, REPO, plt

DEFAULT_CARAVEL = os.path.join(REPO, ".tools", "caravel-lite")

# LEF SIZE (um, N orientation). sky130A sky130_ef_io.lef / sky130_fd_io.lef (ciel 8afc8346), and
# efabless/caravel 27cbe49c lef/<macro>.lef line 9 for the core macros.
SUPPLY_CELL = (75.0, 197.965)                       # e.g. vccd_lvc_clamped3_pad, sky130_ef_io.lef:5482
CELL_SIZE = {
    "sky130_ef_io__gpiov2_pad_wrapped": (80.0, 210.965),       # sky130_ef_io.lef:3691
    "sky130_fd_io__top_xres4v2": (75.0, 200.0),                # sky130_fd_io.lef:177309
    "sky130_ef_io__corner_pad": (200.0, 204.0),                # sky130_ef_io.lef:1940
    "sky130_ef_io__disconnect_vdda_slice_5um": (5.0, 197.965),  # sky130_ef_io.lef:2457
}
MACRO_SIZE = {"housekeeping": (410.23, 550.95), "caravel_clocking": (100.0, 100.0),
              "simple_por": (63.72, 41.69), "xres_buf": (20.0, 17.0),
              "user_project_wrapper": (2920.0, 3520.0)}
CORE_INST = {"mprj": "user_project_wrapper", "housekeeping": "housekeeping",
             "clock_ctrl": "caravel_clocking", "por": "simple_por", "rstb_level": "xres_buf"}
SOC_LOGIC = (861.12, 522.24)          # wrapper coordinates, SOURCES.md figure 1 (schematic here)
MGMT_SIGNALS = ("clock", "resetb", "flash_csb", "flash_clk", "flash_io0", "flash_io1", "gpio")

# colours: one family per area, the digital (1.8 V) supply strong, the analog (3.3 V) supply light;
# ground pads carry diagonal hatching. Pairs: (power net, ground net).
DOMAINS = [  # key, (power, ground), fill, hatch colour
    ("io", ("vddio", "vssio"), "#eda100", "white"),
    ("mgmt_d", ("vccd", "vssd"), "#6b6a66", "white"),
    ("mgmt_a", ("vdda", "vssa"), "#c4c2bb", "#6b6a66"),
    ("u1_d", ("vccd1", "vssd1"), "#e34948", "white"),
    ("u1_a", ("vdda1", "vssa1"), "#f4b0af", "#c0392b"),
    ("u2_d", ("vccd2", "vssd2"), "#6250d6", "white"),
    ("u2_a", ("vdda2", "vssa2"), "#c3bbf3", "#6250d6"),
]
NET_DOMAIN = {n: d for d in DOMAINS for n in d[1]}
GPIO_FILL, GPIO_EDGE = "#d6e6f8", "#2a78d6"
MGMT_FILL, MGMT_EDGE = "#ffffff", "#3d3c39"
CORNER_FILL = "#ecebe8"
INK, INK2 = "#1d1d1b", "#52514e"
WRAP_C, SOC_C, SRAM_C, SRAM_F = "#2980B9", "#27AE60", "#E67E22", "#FBE5D6"
HILITE = "#111111"
# Heiti TC has no bold face, so the pad labels of this design (Latin text only) use DejaVu Sans Bold
BOLD = {"fontfamily": "DejaVu Sans", "fontweight": "bold"}

T = {
    "zh": {
        "title": "Caravel 晶片全貌：pad 排列、management area 與 user_project_wrapper",
        "sub": "資料：caravel-lite 2024.09.12-1 的 def/caravel.def、chip_io.def、caravel_core.def；座標單位 µm，原點在晶片左下角",
        "die": "晶片 3588 × 5188 µm；63 顆 pad：GPIO 38、management 訊號 7、電源與接地 18",
        "wrap": "user_project_wrapper（mprj）\n2920 × 3520 µm，左下角在 (333.24, 1247.5)",
        "mgmt": "management area（Caravel 固定，在 wrapper 下方）\nmanagement SoC（VexRiscv CPU）在 layout 裡沒有保留模組邊界，不畫框\n虛線框：PLL 與 mgmt_protect 元件集中的範圍",
        "hk": "housekeeping", "clk": "caravel_clocking", "pll": "PLL", "por": "POR\n(simple_por)",
        "xres": "xres_buf", "prot": "mgmt_protect（隔離電路，user area 可單獨斷電）",
        "soc": "SoC 邏輯\n（示意）", "sram": "SRAM macro\n約 694 × 428 µm",
        "wb": "Wishbone 腳位 106 支",
        "bridge": "met3 電源連接線：wrapper 的 vccd1／vssd1 ring\n只從左右兩側接電（每個 net 左 54、右 53 條）",
        "pwr": "vccd1／vssd1 各只有\n這一顆 pad，都在右緣；\n本設計的電源從這裡進來，\nIR 從這兩顆 pad 起算",
        "legend": "圖例",
        "l_gpio": "使用者 GPIO（mprj_io，數字是編號）",
        "l_mgmt": "management 訊號 pad",
        "l_hi": "本設計用到的 pad",
        "l_pwr": "電源 pad（左：電源；右：接地，斜線）",
        "l_dom": {"io": "vddio／vssio 3.3 V：padframe 與 ESD",
                  "mgmt_d": "vccd／vssd 1.8 V：management area 數位",
                  "mgmt_a": "vdda／vssa 3.3 V：management area 類比",
                  "u1_d": "vccd1／vssd1 1.8 V：user area 1 數位",
                  "u1_a": "vdda1／vssa1 3.3 V：user area 1 類比",
                  "u2_d": "vccd2／vssd2 1.8 V：user area 2 數位",
                  "u2_a": "vdda2／vssa2 3.3 V：user area 2 類比"},
        "l_split": "類比電源環切斷點（padframe 分成三段）",
        "l_corner": "角落 cell",
    },
    "en": {
        "title": "Caravel chip: pad ring, management area and user_project_wrapper",
        "sub": "Data: caravel-lite 2024.09.12-1 def/caravel.def, chip_io.def, caravel_core.def; coordinates in µm, origin at the chip's lower left",
        "die": "Die 3588 × 5188 µm; 63 pads: 38 GPIO, 7 management signals, 18 power and ground",
        "wrap": "user_project_wrapper (mprj)\n2920 × 3520 µm, lower left at (333.24, 1247.5)",
        "mgmt": "Management area (fixed by Caravel, below the wrapper)\nmanagement SoC (VexRiscv CPU): no outline, not drawn\ndashed: where the PLL and mgmt_protect cells sit",
        "hk": "housekeeping", "clk": "caravel_clocking", "pll": "PLL", "por": "POR\n(simple_por)",
        "xres": "xres_buf", "prot": "mgmt_protect (isolation, user area may power off)",
        "soc": "SoC logic\n(schematic)", "sram": "SRAM macro\n≈ 694 × 428 µm",
        "wb": "106 Wishbone pins",
        "bridge": "met3 bridges: the wrapper's vccd1 / vssd1 rings\nare fed from the left and right only (54 left, 53 right per net)",
        "pwr": "vccd1 / vssd1: one pad\neach, both on the right;\nthis design's supply enters\nhere, IR is measured from them",
        "legend": "Legend",
        "l_gpio": "User GPIO (mprj_io; number = index)",
        "l_mgmt": "Management signal pad",
        "l_hi": "Pad used by this design",
        "l_pwr": "Supply pads (left: power; right: ground, hatched)",
        "l_dom": {"io": "vddio / vssio 3.3 V: padframe and ESD",
                  "mgmt_d": "vccd / vssd 1.8 V: management digital",
                  "mgmt_a": "vdda / vssa 3.3 V: management analog",
                  "u1_d": "vccd1 / vssd1 1.8 V: user area 1 digital",
                  "u1_a": "vdda1 / vssa1 3.3 V: user area 1 analog",
                  "u2_d": "vccd2 / vssd2 1.8 V: user area 2 digital",
                  "u2_a": "vdda2 / vssa2 3.3 V: user area 2 analog"},
        "l_split": "Analog-ring cut (padframe in three segments)",
        "l_corner": "Corner cell",
    },
}


# ---------------------------------------------------------------------------------------------- data
def die_area(path):
    with open(path) as f:
        for line in f:
            m = re.match(r"\s*DIEAREA \( (-?\d+) (-?\d+) \) \( (-?\d+) (-?\d+) \)", line)
            if m:
                return tuple(int(v) / 1000 for v in m.groups())
    raise SystemExit(f"no DIEAREA in {path}")


def package_pins(path):
    """caravel.def PINS: name -> centre (um)."""
    text = open(path).read()
    sec = text[text.index("\nPINS"):text.index("\nEND PINS")]
    out = {}
    for name, x, y in re.findall(r"^\s*- (\S+) \+ NET .*?\+ PLACED \( (-?\d+) (-?\d+) \)", sec, re.M | re.S):
        out[name] = (int(x) / 1000, int(y) / 1000)
    return out


def cell_size(cell):
    if cell in CELL_SIZE:
        return CELL_SIZE[cell]
    if re.match(r"sky130_ef_io__v(ccd|ssd|dda|ssa|ddio|ssio)_[hl]vc_clamped3?_pad$", cell):
        return SUPPLY_CELL
    return None


def pad_cells(path):
    """chip_io.def COMPONENTS: pad, corner and disconnect cells with their footprint (um)."""
    text = open(path).read()
    sec = text[text.index("\nCOMPONENTS"):text.index("\nEND COMPONENTS")]
    out = []
    for inst, cell, x, y, orient in re.findall(r"^\s*- (\S+) (\S+)\s*\+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \) (\w+)",
                                               sec, re.M):
        size = cell_size(cell)
        if size is None:
            continue
        w, h = size if orient in ("N", "S", "FN", "FS") else size[::-1]
        x, y = int(x) / 1000, int(y) / 1000
        out.append({"inst": inst.replace("\\", ""), "cell": cell, "box": (x, y, x + w, y + h)})
    return out


def core_blocks(path, origin):
    """Stream caravel_core.def COMPONENTS: named macros and the origins of pll.* / mgmt_buffers.* cells."""
    ox, oy = origin
    blocks, groups = {}, {"pll.": [], "mgmt_buffers.": []}
    pat = re.compile(r"^\s*- (\S+) (\S+) \+ (?:PLACED|FIXED) \( (-?\d+) (-?\d+) \)")
    inside = False
    with open(path) as f:
        for line in f:
            if not inside:
                inside = line.startswith("COMPONENTS")
                continue
            if line.startswith("END COMPONENTS"):
                break
            s = line.lstrip()
            if not s.startswith("- "):
                continue
            name = s[2:s.index(" ", 2)]
            if name in CORE_INST or name.startswith(("pll.", "mgmt_buffers.")):
                m = pat.match(line)
                inst, cell, x, y = m.group(1), m.group(2), int(m.group(3)) / 1000 + ox, int(m.group(4)) / 1000 + oy
                if name in CORE_INST:
                    w, h = MACRO_SIZE[CORE_INST[name]]
                    blocks[name] = (x, y, x + w, y + h)
                elif cell.startswith("sky130_fd_sc_hd__"):
                    groups["pll." if name.startswith("pll.") else "mgmt_buffers."].append((x, y))
    for key, pts in groups.items():
        a = np.array(pts)
        lo, hi = np.percentile(a, 10, axis=0), np.percentile(a, 90, axis=0)
        blocks[key] = (lo[0], lo[1], hi[0], hi[1])
    return blocks


def wishbone_span(def_path):
    text = open(def_path).read()
    xs = [int(x) / 1000 for name, x in
          re.findall(r"^\s*- (wbs?_\S+) \+ NET .*?\+ PLACED \( (-?\d+) -?\d+ \)", text, re.M | re.S)]
    return len(xs), min(xs), max(xs)


def load(caravel, repo):
    die = die_area(os.path.join(caravel, "def/caravel.def"))
    pins = package_pins(os.path.join(caravel, "def/caravel.def"))
    cells = pad_cells(os.path.join(caravel, "def/chip_io.def"))
    pads, splits, used = [], [], set()
    for c in cells:
        x1, y1, x2, y2 = c["box"]
        if c["cell"].endswith("disconnect_vdda_slice_5um"):
            splits.append(c["box"])
            continue
        hit = [n for n, (px, py) in pins.items() if x1 <= px <= x2 and y1 <= py <= y2]
        assert len(hit) <= 1, (c["inst"], hit)
        c["pin"] = hit[0] if hit else None
        if c["pin"]:
            used.add(c["pin"])
        elif not c["cell"].endswith("corner_pad"):
            raise SystemExit(f"pad without a package pin: {c['inst']}")
        pads.append(c)
    assert used == set(pins) and len(pins) == 63, "every package pin must sit on exactly one pad"
    assert len(splits) == 3 and sum(c["pin"] is None for c in pads) == 4
    core = (211.5, 210.5)  # def/caravel.def line 1921: chip_core placed at (211500 210500)
    blocks = core_blocks(os.path.join(caravel, "def/caravel_core.def"), core)
    plan = tomllib.load(open(os.path.join(repo, "pnr/user_project_wrapper/pin_plan.toml"), "rb"))
    bridges = []
    for line in open(os.path.join(repo, "pnr/user_project_wrapper/caravel_pwr/bridges.txt")):
        if line.strip() and not line.startswith("#"):
            x1, y1, x2, y2 = (int(v) / 1000 for v in line.split())
            bridges.append((x1 + core[0], y1 + core[1], x2 + core[0], y2 + core[1]))
    wb = wishbone_span(os.path.join(repo, "pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def"))
    return die, pads, splits, blocks, plan, bridges, wb


# ------------------------------------------------------------------------------------------- drawing
def side_of(box, die):
    x1, y1, x2, y2 = box
    if y1 <= 0.5 and x1 > 0.5 and x2 < die[2] - 0.5:
        return "bottom"
    if y2 >= die[3] - 0.5 and x1 > 0.5 and x2 < die[2] - 0.5:
        return "top"
    if x1 <= 0.5:
        return "left"
    return "right"


def pad_style(pin):
    if pin is None:
        return CORNER_FILL, None, "#9a988f"
    if pin.startswith("mprj_io"):
        return GPIO_FILL, None, GPIO_EDGE
    if pin in MGMT_SIGNALS:
        return MGMT_FILL, None, MGMT_EDGE
    net = re.sub(r"_2$", "", pin)
    d = NET_DOMAIN[net]
    ground = net.startswith("vss")
    return d[2], (d[3] if ground else None), INK2


def draw_rect(ax, box, fill, hatch_c, edge, lw=0.6, z=3):
    x1, y1, x2, y2 = box
    ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fc=fill, ec="none", lw=0, zorder=z))
    if hatch_c:
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec=hatch_c, lw=0, hatch="////", zorder=z + 0.1))
    ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec=edge, lw=lw, zorder=z + 0.2))


def render(lang, data):
    die, pads, splits, blocks, plan, bridges, wb = data
    t = T[lang]
    font = ["Heiti TC", "Arial Unicode MS", "DejaVu Sans"] if lang == "zh" else ["DejaVu Sans"]
    plt.rcParams.update({"font.family": font, "font.size": 7.5, "axes.unicode_minus": False,
                         "hatch.linewidth": 0.7, "figure.facecolor": "white", "savefig.facecolor": "white"})
    use = {p["gpio"]: p["signal"] for p in plan["pin"]}
    ML, MR, MB, MT = 720.0, 560.0, 420.0, 300.0         # label margins around the die (um)
    xr, yr = die[2] + ML + MR, die[3] + MB + MT
    W = 6.6
    title_in = 0.42
    s = W / xr                                           # inch per um
    H = yr * s + title_in
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0, 1, (yr * s) / H])
    ax.set_xlim(-ML, die[2] + MR)
    ax.set_ylim(-MB, die[3] + MT)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.text(0.012, 1 - 0.10 / H, t["title"], fontsize=10.5, fontweight="bold", va="top", color=INK)
    fig.text(0.012, 1 - 0.29 / H, t["sub"], fontsize=7, va="top", color=INK2)

    # die and caravel_core
    ax.add_patch(Rectangle((0, 0), die[2], die[3], fc="#fbfbfa", ec=INK, lw=1.2, zorder=1))

    # management area: caravel_core y 0-1037 (= chip y 210.5-1247.5), below the wrapper
    wx1, wy1, wx2, wy2 = blocks["mprj"]
    ax.add_patch(Rectangle((211.5, 210.5), 3165, wy1 - 210.5, fc="#efeeea", ec="#a8a69e", lw=0.6, zorder=1.5))
    ax.text(250, 760, t["mgmt"], fontsize=7.2, color=INK, va="center", ha="left", zorder=6, linespacing=1.35)
    for key, lab, dx, dy, ha, va in (("housekeeping", t["hk"], 0, 20, "center", "bottom"),
                                     ("clock_ctrl", t["clk"], 0, 30, "center", "bottom"),
                                     ("por", t["por"], 0, 25, "center", "bottom"),
                                     ("rstb_level", t["xres"], 30, 0, "left", "center")):
        x1, y1, x2, y2 = blocks[key]
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fc="#d9d7d0", ec=INK2, lw=0.7, zorder=4))
        if va == "center" and ha == "center":
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, lab, ha=ha, va=va, fontsize=7.2, zorder=6)
        elif va == "bottom":
            ax.text((x1 + x2) / 2 + dx, y2 + dy, lab, ha=ha, va=va, fontsize=7.2, zorder=6, linespacing=1.1)
        else:
            ax.text(x2 + dx, (y1 + y2) / 2 + dy, lab, ha=ha, va=va, fontsize=7.2, zorder=6)
    x1, y1, x2, y2 = blocks["pll."]
    ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fc="#d9d7d0", ec=INK2, lw=0.7, ls="--", zorder=4))
    ax.text(x1 - 25, (y1 + y2) / 2, t["pll"], ha="right", va="center", fontsize=7.2, zorder=6)
    x1, y1, x2, y2 = blocks["mgmt_buffers."]
    ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fc="#d9d7d0", ec=INK2, lw=0.7, ls="--", zorder=4))
    ax.text((x1 + x2) / 2, y1 - 22, t["prot"], ha="center", va="top", fontsize=7.2, zorder=6)

    # wrapper, SoC, SRAM, Wishbone pins
    ax.add_patch(Rectangle((wx1, wy1), wx2 - wx1, wy2 - wy1, fc="#f4f8fc", ec=WRAP_C, lw=1.4, zorder=2))
    ax.text(wx1 + 45, wy2 - 45, t["wrap"], ha="left", va="top", fontsize=7.8, color="#1f5f8b",
            fontweight="bold", zorder=6, linespacing=1.3)
    sw, sh = SOC_LOGIC
    ax.add_patch(Rectangle((wx1, wy1), sw, sh, fc="#e2f0d9", ec=SOC_C, lw=1.0, ls="--", zorder=4))
    ax.text(wx1 + 25, wy1 + 90, t["soc"], ha="left", va="bottom", fontsize=7.2, color="#1e7a44", zorder=6,
            linespacing=1.15)
    sx, sy = plan["block"]["location"]
    ax.add_patch(Rectangle((wx1 + sx, wy1 + sy), 694.27, 428.415, fc=SRAM_F, ec=SRAM_C, lw=1.2, zorder=5))
    ax.text(wx1 + sx + 347, wy1 + sy + 214, t["sram"], ha="center", va="center", fontsize=7.2, zorder=6,
            linespacing=1.2)
    n_wb, wbx1, wbx2 = wb
    ax.plot([wx1 + wbx1, wx1 + wbx2], [wy1, wy1], color="#1f3f8b", lw=3.2, solid_capstyle="butt", zorder=7)
    ax.text(wx1 + 10, wy1 - 18, t["wb"], ha="left", va="top", fontsize=7.0, color="#1f3f8b", zorder=7)

    # met3 bridges between Caravel's ring and the wrapper ring
    for x1, y1, x2, y2 in bridges:
        ax.plot([x1, x2], [(y1 + y2) / 2] * 2, color="#b8322f", lw=0.45, zorder=3)
    left = [b for b in bridges if b[0] < die[2] / 2]
    ly = 2350
    ax.annotate(t["bridge"], xy=(left[0][2], ly), xytext=(wx1 + 70, ly), fontsize=7.0, va="center", ha="left",
                color="#8e2421", zorder=7, arrowprops=dict(arrowstyle="->", color="#8e2421", lw=0.8),
                linespacing=1.3)

    # pads
    for p in pads:
        side = side_of(p["box"], die)
        fill, hatch_c, edge = pad_style(p["pin"])
        draw_rect(ax, p["box"], fill, hatch_c, edge)
        x1, y1, x2, y2 = p["box"]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        pin = p["pin"]
        if pin is None:
            continue
        m = re.match(r"mprj_io\[(\d+)\]", pin)
        hi = False
        if m:
            k = int(m.group(1))
            ax.text(cx, cy, str(k), ha="center", va="center", fontsize=6.6,
                    color=INK, zorder=8, **(BOLD if k in use else {}))
            hi = k in use
            label = use.get(k)
        else:
            label = re.sub(r"_2$", "", pin)
            hi = label in ("vccd1", "vssd1")
        if hi:
            ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec=HILITE, lw=1.9, zorder=9))
        if not label:
            continue
        kw = dict(fontsize=7.2, color=INK, zorder=8, **(BOLD if hi else {}))
        g = 28
        if side == "left":
            ax.text(-g, cy, label, ha="right", va="center", **kw)
        elif side == "right":
            ax.text(die[2] + g, cy, label, ha="left", va="center", **kw)
        elif side == "top":
            ax.text(cx, die[3] + g, label, ha="center", va="bottom", rotation=90, **kw)
        else:
            ax.text(cx, -g, label, ha="center", va="top", rotation=90, **kw)
    for x1, y1, x2, y2 in splits:  # 5 um cells: drawn as a thick bar across the ring
        if x2 - x1 < y2 - y1:
            ax.plot([(x1 + x2) / 2] * 2, [y1 - 25, y2 + 25], color=INK, lw=2.4, zorder=9, solid_capstyle="butt")
        else:
            ax.plot([x1 - 25, x2 + 25], [(y1 + y2) / 2] * 2, color=INK, lw=2.4, zorder=9, solid_capstyle="butt")

    # supply entry note (vccd1 / vssd1)
    vp = {re.sub(r"_2$", "", p["pin"]): p["box"] for p in pads if p["pin"] in ("vccd1", "vssd1")}
    tx, ty = wx2 - 70, 1830
    ax.text(tx, ty, t["pwr"], ha="right", va="center", fontsize=7.0, color="#8e2421", zorder=7, linespacing=1.3,
            bbox=dict(fc="white", ec="#e3a09f", lw=0.6, pad=3))
    for net in ("vccd1", "vssd1"):
        b = vp[net]
        ax.annotate("", xy=(b[0], (b[1] + b[3]) / 2), xytext=(tx + 20, ty + 205),
                    arrowprops=dict(arrowstyle="->", color="#8e2421", lw=0.9,
                                    connectionstyle="angle,angleA=90,angleB=0,rad=0"), zorder=7)

    # die caption just below the top pad row
    ax.text(260, die[3] - 255, t["die"], ha="left", va="center", fontsize=6.8, color=INK2, zorder=6)

    legend(ax, t, (wx2 - 90, 4400), lang)
    fig.savefig(os.path.join(FIG, f"caravel_chip_{lang}.png"), dpi=220)
    plt.close(fig)


def text_width(ax, s, **kw):
    """Width of a text in data units (um), measured with the figure's renderer."""
    r = ax.figure.canvas.get_renderer()
    a = ax.text(0, 0, s, **kw)
    w = a.get_window_extent(r).width
    a.remove()
    return w / (ax.transData.transform((1, 0))[0] - ax.transData.transform((0, 0))[0])


def legend(ax, t, xy, lang):
    """Legend box whose right edge is at xy[0]; its width follows the longest entry."""
    x_right, ytop = xy
    row = 112.0
    sw, sh = 150.0, 70.0
    rows = [("gpio", t["l_gpio"]), ("mgmt", t["l_mgmt"]), ("hi", t["l_hi"]), ("hdr", t["l_pwr"])]
    rows += [(d[0], t["l_dom"][d[0]]) for d in DOMAINS]
    rows += [("split", t["l_split"]), ("corner", t["l_corner"])]
    tw = max(text_width(ax, lab, fontsize=7.0, fontweight="bold" if k == "u1_d" else "normal")
             if k != "hdr" else text_width(ax, lab, fontsize=7.0) - sw - 45 for k, lab in rows)
    width = 40 + sw + 45 + tw + 50
    x0 = x_right - width + 40
    height = row * (len(rows) + 1) + 40
    ax.add_patch(Rectangle((x0 - 40, ytop - height), width, height + 30, fc="white", ec="#a8a69e", lw=0.7, zorder=10))
    ax.text(x0, ytop - 30, t["legend"], fontsize=7.8, fontweight="bold", va="center", zorder=11)
    y = ytop - 30 - row
    for key, lab in rows:
        if key == "hdr":
            ax.text(x0, y, lab, fontsize=7.0, va="center", color=INK2, zorder=11)
            y -= row
            continue
        bx = x0
        if key == "gpio":
            draw_rect(ax, (bx, y - sh / 2, bx + sw, y + sh / 2), GPIO_FILL, None, GPIO_EDGE, z=11)
            ax.text(bx + sw / 2, y, "12", fontsize=6.0, ha="center", va="center", zorder=12)
        elif key == "mgmt":
            draw_rect(ax, (bx, y - sh / 2, bx + sw, y + sh / 2), MGMT_FILL, None, MGMT_EDGE, z=11)
        elif key == "hi":
            draw_rect(ax, (bx, y - sh / 2, bx + sw, y + sh / 2), GPIO_FILL, None, HILITE, lw=1.9, z=11)
        elif key == "split":
            ax.plot([bx + 20, bx + sw - 20], [y, y], color=INK, lw=2.4, zorder=11, solid_capstyle="butt")
        elif key == "corner":
            draw_rect(ax, (bx, y - sh / 2, bx + sw, y + sh / 2), CORNER_FILL, None, "#9a988f", z=11)
        else:
            d = next(d for d in DOMAINS if d[0] == key)
            draw_rect(ax, (bx, y - sh / 2, bx + 70, y + sh / 2), d[2], None, INK2, z=11)
            draw_rect(ax, (bx + 80, y - sh / 2, bx + sw, y + sh / 2), d[2], d[3], INK2, z=11)
        ax.text(x0 + sw + 45, y, lab, fontsize=7.0, va="center", zorder=11,
                fontweight="bold" if key == "u1_d" else "normal")
        y -= row


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--caravel", default=os.environ.get("CARAVEL_SRC", DEFAULT_CARAVEL))
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--lang", nargs="+", default=["zh", "en"])
    a = ap.parse_args()
    data = load(a.caravel, a.repo)
    die, pads, splits, blocks, plan, bridges, wb = data
    print(f"die {die}; pads {len(pads)} (corners {sum(p['pin'] is None for p in pads)}); splits {len(splits)}; "
          f"wrapper {blocks['mprj']}; bridges {len(bridges)}; wishbone pins {wb}")
    for k in ("housekeeping", "clock_ctrl", "por", "rstb_level", "pll.", "mgmt_buffers."):
        print(k, tuple(round(v, 2) for v in blocks[k]))
    for lang in a.lang:
        render(lang, data)
        print("wrote", os.path.join(FIG, f"caravel_chip_{lang}.png"))


if __name__ == "__main__":
    main()
