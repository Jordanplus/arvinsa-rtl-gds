# Print the bounding box of one GDS cell in um: klayout -b -rd src=<gds> -rd cell=<name> -r gds_bbox.py
# (scripts/check_macro_views.py compares it with the LEF SIZE).
import pya
ly = pya.Layout(); ly.read(src)
c = ly.cell(cell)
b = c.dbbox() if c else None
print("GDS_BBOX none" if b is None or b.empty() else f"GDS_BBOX {b.left:.4f} {b.bottom:.4f} {b.right:.4f} {b.top:.4f}")
