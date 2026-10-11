# Merge the Magic DRC error boxes of each rule (ip/sram/openram/macro_drc.py):
#   klayout -b -rd src=<boxes.tsv> -rd dst=<merged.json> -r drc_merge.py
# <boxes.tsv>: lines "B<TAB><rule><TAB><llx lly urx ury>" in Magic internal units. Writes {rule: {"boxes": n,
# "polygons": merged polygons, "area": merged area in internal units^2}}. Touching boxes join: Magic splits one
# error into several boxes on lines every 157.28 um of the listed cell (Phase 6 independent review), so box counts
# move with the array's position while the merged regions do not.
import collections
import json

import pya

src, dst = (globals()[k] for k in ("src", "dst"))   # set by klayout -rd
regions, boxes = collections.defaultdict(pya.Region), collections.Counter()
for line in open(src):
    if line.startswith("B\t"):
        _, why, b = line.rstrip("\n").split("\t")
        x0, y0, x1, y1 = (int(round(float(v))) for v in b.split())
        regions[why].insert(pya.Box(x0, y0, x1, y1))
        boxes[why] += 1
out = {}
for why, r in regions.items():
    m = r.merged()
    out[why] = {"boxes": boxes[why], "polygons": m.count(), "area": m.area()}
json.dump(out, open(dst, "w"), indent=1, sort_keys=True)
