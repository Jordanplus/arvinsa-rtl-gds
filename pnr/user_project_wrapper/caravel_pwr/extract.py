#!/usr/bin/env python3
"""Extract Caravel's vccd1/vssd1 supply network around user_project_wrapper into the data files of this
directory (README.md). Run once per Caravel version; inputs are files of the Caravel repository.

usage: extract.py <caravel_core.def[.gz]> <manual_power_connections.lef> <out dir>
"""
import gzip
import os
import re
import sys

NETS = ("vccd1", "vssd1")


def main(core_def, lef, out):
    text = (gzip.open(core_def, "rt") if core_def.endswith(".gz") else open(core_def)).read()
    sn = text[text.index("\nSPECIALNETS"):text.index("\nEND SPECIALNETS")]
    vias_used, rows = set(), []
    for net in NETS:
        m = re.search(rf"^    - {net} .*?;\s*$", sn, re.M | re.S)
        for line in m.group(0).splitlines():
            w = re.search(r"(met[45]) (\d+) (?:\+ SHAPE \w+ )?\( (-?\d+) (-?\d+) \)(?: \( (-?\d+|\*) (-?\d+|\*) \))?(?: (\S+))?", line)
            if not w:
                continue
            lay, width, x1, y1, x2, y2, via = w.groups()
            if x2 is None:
                if via and via.startswith("via5_6"):        # met4-met5 only; met3-met4 stacks feed gpio cells
                    vias_used.add(via)
                    rows.append(f"{net} via {via} {x1} {y1}")
            else:
                x2 = x1 if x2 == "*" else x2
                y2 = y1 if y2 == "*" else y2
                rows.append(f"{net} wire {lay} {width} {x1} {y1} {x2} {y2}")
    vias = text[text.index("\nVIAS"):text.index("\nEND VIAS")]
    defs = [l.strip() for l in vias.splitlines() if any(re.match(rf"\s*- {re.escape(v)} ", l) for v in vias_used)]
    # met3 bridges of manual_power_connections (LEF OBS, um -> DEF units of caravel_core, 1000/um)
    sec, rects = None, []
    for line in open(lef):
        m = re.match(r"\s*LAYER (\S+)", line)
        if m:
            sec = m.group(1)
            continue
        m = re.match(r"\s*RECT\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", line)
        if m and sec == "met3":
            x1, y1, x2, y2 = (round(float(v) * 1000) for v in m.groups())
            if x2 - x1 >= 50000:
                rects.append((x1, y1, x2, y2))
    with open(os.path.join(out, "shapes.txt"), "w") as f:
        f.write("# net wire layer width x1 y1 x2 y2 | net via name x y   (caravel_core DEF units, 1000/um)\n")
        f.write("\n".join(rows) + "\n")
    with open(os.path.join(out, "bridges.txt"), "w") as f:
        f.write("# met3 rectangles of manual_power_connections longer than 50 um: x1 y1 x2 y2 (caravel_core, 1000/um)\n")
        f.write("\n".join(" ".join(map(str, r)) for r in sorted(rects)) + "\n")
    with open(os.path.join(out, "vias.def"), "w") as f:
        f.write("\n".join(sorted(defs)) + "\n")
    print(f"{len(rows)} shapes, {len(rects)} bridges, {len(defs)} via definitions")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
