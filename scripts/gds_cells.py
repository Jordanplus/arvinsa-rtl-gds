# Fingerprint of every cell below one GDS cell: klayout -b -rd src=<gds> -rd cell=<name> -r gds_cells.py
# Prints `GDS_CELLS <json>`: {"all": every cell name in the file, "tree": {name: sha1}} for <name> and the cells it
# calls (null if <name> is missing). A cell's sha1 covers, per layer/datatype, the number of shapes and a weighted sum
# of their box corners, and every instance (child name, transformation, array). scripts/check_macro_gds.py compares
# the macro's own GDS with the final GDS (Phase 6, ADR-0018).
import hashlib
import json
import pya
src, cell = (globals()[k] for k in ("src", "cell"))   # set by klayout -rd (make py-check sees them bound)
ly = pya.Layout()
ly.read(src)
top = ly.cell(cell)
out = {"all": sorted(c.name for c in ly.each_cell()), "tree": None}
if top is not None:
    tree = {}
    for ci in [top.cell_index()] + list(top.called_cells()):
        c = ly.cell(ci)
        h = hashlib.sha1()
        for li in sorted(ly.layer_indexes(), key=lambda i: (ly.get_info(i).layer, ly.get_info(i).datatype)):
            n, acc = 0, 0
            for s in c.shapes(li).each():
                b = s.bbox()
                n += 1
                acc += b.left + 3 * b.bottom + 7 * b.right + 11 * b.top
            if n:
                h.update(f"{ly.get_info(li).layer}/{ly.get_info(li).datatype}:{n}:{acc};".encode())
        insts = sorted(f"{ly.cell(i.cell_index).name}|{i.cplx_trans}|{i.a}|{i.b}|{i.na}|{i.nb}" for i in c.each_inst())
        h.update("\n".join(insts).encode())
        tree[c.name] = h.hexdigest()
    out["tree"] = tree
print("GDS_CELLS " + json.dumps(out))
