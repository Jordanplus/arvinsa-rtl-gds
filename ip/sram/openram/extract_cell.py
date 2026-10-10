# Cut one cell (with its children) out of a GDS: klayout -b -rd src=<gds> -rd cell=<name> -rd dst=<gds> -r extract_cell.py
# (ip/sram/openram/setup.sh, for the dlxtn_1 cell that OpenRAM's sky130-install copies).
import pya
ly = pya.Layout(); ly.read(src)
c = ly.cell(cell)
keep = set([c.cell_index()]) | set(c.called_cells())
for ci in [x.cell_index() for x in ly.each_cell()]:
    if ci not in keep: ly.delete_cell(ci)
ly.write(dst)
