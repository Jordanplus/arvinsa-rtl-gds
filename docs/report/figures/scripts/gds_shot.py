# Render a GDS to PNG with KLayout's LayoutView (headless, klayout -z -r).
# usage: klayout -z -rd gds=<in.gds> -rd out=<out.png> -rd lyp=<layer props> [-rd w=2400] [-rd h=2400]
#        [-rd box=x1,y1,x2,y2 (um)] [-rd levels=N] [-rd layers=L/D,L/D,...] [-rd hide=L/D,...] -r gds_shot.py
#
# Only the drawing layers in `layers` are shown (default: sky130 nwell, diff/tap, poly, contacts,
# li1, met1-met5 and the vias). Boundary, areaid, pin, label, text and other marker layers are
# hidden so they do not cover the picture. `hide` removes layers from that list.
# Pass a box with the same aspect ratio as w:h; the picture then covers exactly that box, which is
# written to <out>.json (box_um) so an annotation script can put um axes on the picture.
import json
import pya

# klayout -rd name=value defines each parameter as a global variable; read them explicitly
gds, out = globals()["gds"], globals()["out"]
lyp, box = globals().get("lyp", ""), globals().get("box", "")
w = int(globals().get("w", "2400")); h = int(globals().get("h", "2400"))
DEFAULT = ("64/20,65/20,65/44,66/20,66/44,67/20,67/44,68/20,68/44,69/20,69/44,"
           "70/20,70/44,71/20,71/44,72/20")
want = [s.strip() for s in globals().get("layers", DEFAULT).split(",") if s.strip()]
drop = set(s.strip() for s in globals().get("hide", "").split(",") if s.strip())
show = set(want) - drop

view = pya.LayoutView()
view.load_layout(gds, True)
if lyp:
    view.load_layer_props(lyp)
view.set_config("background-color", "#ffffff")
view.set_config("grid-visible", "false")
view.set_config("text-visible", "false")
view.max_hier_levels = int(globals().get("levels", "20"))
view.min_hier_levels = 0

shown = []
it = view.begin_layers()
while not it.at_end():
    lp = it.current()
    key = "%d/%d" % (lp.source_layer, lp.source_datatype)
    vis = key in show
    if vis:
        shown.append(key)
    if lp.visible != vis:
        lp.visible = vis
        view.set_layer_properties(it, lp)
    it.next()

if box:
    x1, y1, x2, y2 = [float(v) for v in box.split(",")]
    view.zoom_box(pya.DBox(x1, y1, x2, y2))
else:
    view.zoom_fit()
view.save_image(out, w, h)
top = view.cellview(0).cell
bx = [float(v) for v in box.split(",")] if box else None
json.dump({"gds": gds, "top": top.name, "box_um": bx,
           "cell_bbox_um": [top.dbbox().left, top.dbbox().bottom, top.dbbox().right, top.dbbox().top],
           "w": w, "h": h, "layers_shown": sorted(set(shown))}, open(out + ".json", "w"), indent=1)
print("saved", out, "box", bx, "top", top.name)
