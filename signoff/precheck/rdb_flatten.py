# Every marker of a KLayout DRC report at its place relative to the SRAM's bitcell array (Phase 7, ADR-0019 decision 5):
#   klayout -b -rd gds=<gds> -rd top=<top cell> -rd macro=<macro cell> -rd anchor=<bitcell cell> -rd rdb=<report.xml>
#           -rd dst=<out.json> -r rdb_flatten.py
# The precheck deck runs in deep mode: a marker is reported once, in the cell where KLayout found it, in that cell's
# coordinates. Which cell gets it depends on the hierarchy: the self-generated SRAM reports 2 of its 264 BEOL markers
# in dummy_array cells, the PDK SRAM in replica_bitcell_array. So every marker is repeated over every instance of its
# cell below <top> (arrays element by element), giving top coordinates. A marker inside the box of the one <macro>
# instance is taken back into the macro's coordinates and made relative to the lower-left corner of all <anchor>
# instances in the macro (the bitcell array): the self-generated macro's array sits (5.61, 9.32) um from where the PDK
# macro has it. For the macro checked alone, <top> = <macro>.
# Writes {"items", "macro_instances", "macro_box" (top, um), "anchor": {"count", "size" [w, h] nm},
# "inside": [[category, x1, y1, x2, y2 (nm, relative to the anchor), count]], "outside": [[category, cell, x1, y1, x2,
# y2 (nm, top)]], "unplaced": [[category, cell, value]]} (unplaced: an item without a value, a value that is no
# geometry, or a cell not below <top>). Used by check_precheck.py.
import collections
import json
import pya
gds, top, macro, anchor, rdb, dst = (globals()[k] for k in ("gds", "top", "macro", "anchor", "rdb", "dst"))   # klayout -rd
ly = pya.Layout()
ly.read(gds)
tc, mc, ac = ly.cell(top), ly.cell(macro), ly.cell(anchor)
db = pya.ReportDatabase("")
db.load(rdb)
cat_name = {c.rdb_id(): c.name() for c in db.each_category()}
cell_name = {c.rdb_id(): c.name() for c in db.each_cell()}


def instances(parent, child):
    """DCplxTrans of every instance of `child` below `parent` (identity if they are the same cell)."""
    if child.cell_index() == parent.cell_index():
        return [pya.DCplxTrans()]
    out = []
    it = parent.begin_instances_rec()
    it.targets = [child.cell_index()]
    while not it.at_end():
        out.append(it.dtrans() * it.inst_dtrans())
        it.next()
    return out


def nm(b):
    return [round(b.left * 1000), round(b.bottom * 1000), round(b.right * 1000), round(b.top * 1000)]


out = {"items": 0, "macro_instances": 0, "macro_box": None, "anchor": None, "inside": [], "outside": [], "unplaced": []}
m_trans, m_box, a_ll = None, None, None
if tc is not None and mc is not None:
    ms = instances(tc, mc)
    out["macro_instances"] = len(ms)
    if len(ms) == 1:
        m_trans = ms[0]
        m_box = m_trans * mc.dbbox()
        out["macro_box"] = [m_box.left, m_box.bottom, m_box.right, m_box.top]
    if ac is not None:
        a_box = pya.DBox()
        a_ts = instances(mc, ac)
        for t in a_ts:
            a_box += t * ac.dbbox()
        if a_ts:
            a_ll = pya.DVector(a_box.left, a_box.bottom)
            out["anchor"] = {"count": len(a_ts), "size": [round(a_box.width() * 1000), round(a_box.height() * 1000)]}

paths = {}
inside = collections.Counter()
for item in db.each_item():
    out["items"] += 1
    cat, cname = cat_name[item.category_id()].strip("'"), cell_name[item.cell_id()]
    if cname not in paths:
        c = ly.cell(cname)
        paths[cname] = instances(tc, c) if c is not None and tc is not None else []
    values = list(item.each_value())
    if not values:
        out["unplaced"].append([cat, cname, "(no value)"])
    for v in values:
        if v.is_edge_pair():
            box = v.edge_pair().bbox()
        elif v.is_polygon():
            box = v.polygon().bbox()
        elif v.is_box():
            box = v.box()
        elif v.is_edge():
            box = v.edge().bbox()
        else:
            box = None
        if box is None or not paths[cname]:
            out["unplaced"].append([cat, cname, v.to_s()])
            continue
        for t in paths[cname]:
            b = t * box
            if m_box is not None and a_ll is not None and m_box.contains(b.p1) and m_box.contains(b.p2):
                inside[tuple([cat] + nm((m_trans.inverted() * b).moved(-a_ll)))] += 1
            else:
                out["outside"].append([cat, cname] + nm(b))
out["inside"] = [list(k) + [n] for k, n in sorted(inside.items())]
with open(dst, "w") as f:
    json.dump(out, f)
print(f"RDB_FLATTEN items {out['items']} inside {sum(inside.values())} outside {len(out['outside'])} "
      f"unplaced {len(out['unplaced'])} macro_instances {out['macro_instances']}")
