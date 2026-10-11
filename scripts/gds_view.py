# What scripts/check_macro_views.py needs from the GDS of one macro, as JSON:
#   klayout -b -rd src=<gds> -rd cell=<name> -rd cover=<in.json> -rd dst=<out.json> -r gds_view.py
#   bbox       the top cell's bounding box in um (null when the cell is missing or empty)
#   labels     every text of the top cell: [string, layer, datatype, x, y] (um)
#   uncovered  for each layer of <in.json> {"<layer>/<datatype>": {"obs": [[x1, y1, x2, y2], ...], "pins": [...]}}:
#              the cell's shapes on that layer, flattened, outside the LEF OBS and pin boxes, split into the part
#              that touches a pin box (the pin's own metal running on into the macro) and the rest:
#              {"attached": um2, "loose": um2, "examples": up to 3 loose boxes}
import json

import pya

src, cell, cover, dst = (globals()[k] for k in ("src", "cell", "cover", "dst"))   # set by klayout -rd
ly = pya.Layout()
ly.read(src)
c = ly.cell(cell)
out = {"bbox": None, "labels": [], "uncovered": {}}


def region(boxes):
    r = pya.Region()
    for x1, y1, x2, y2 in boxes:
        r.insert(pya.DBox(x1, y1, x2, y2).to_itype(ly.dbu))
    return r


if c is not None:
    b = c.dbbox()
    out["bbox"] = None if b.empty() else [b.left, b.bottom, b.right, b.top]
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        for s in c.shapes(li).each():
            if s.is_text():
                p = s.text_dpos
                out["labels"].append([s.text_string, info.layer, info.datatype, round(p.x, 4), round(p.y, 4)])
    a2 = ly.dbu * ly.dbu
    for key, lef in json.load(open(cover)).items():
        layer, datatype = (int(x) for x in key.split("/"))
        li = ly.find_layer(pya.LayerInfo(layer, datatype))
        shapes = pya.Region(c.begin_shapes_rec(li)) if li is not None and li >= 0 else pya.Region()
        pins = region(lef["pins"])
        left = (shapes - region(lef["obs"]) - pins).merged()
        attached = left.interacting(pins.sized(1))   # 1 dbu: a piece that only abuts a pin box counts as touching
        loose = left - attached
        examples = [p.bbox().to_dtype(ly.dbu) for _, p in zip(range(3), loose.each())]
        out["uncovered"][key] = {"attached": attached.area() * a2, "loose": loose.area() * a2,
                                 "examples": [[e.left, e.bottom, e.right, e.top] for e in examples]}
json.dump(out, open(dst, "w"))
