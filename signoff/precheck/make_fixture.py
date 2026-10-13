# neg_precheck.py's fixture GDS: a top cell <top> with <copies> instance(s) of <macro> from <src>, mirrored about the x
# axis (DEF FS) at (<x>, <y>) um (a second copy 800 um to the right), so that check_precheck.py has to undo a
# transformation that is not a plain shift.
#   klayout -b -rd src=<macro.gds> -rd macro=<cell> -rd top=<top> -rd x=<um> -rd y=<um> -rd copies=<n> -rd dst=<out.gds>
#           -r make_fixture.py
import pya
src, macro, top, x, y, copies, dst = (globals()[k] for k in ("src", "macro", "top", "x", "y", "copies", "dst"))   # -rd
ly = pya.Layout()
ly.read(src)
t = ly.create_cell(top)
for i in range(int(copies)):
    t.insert(pya.DCellInstArray(ly.cell(macro).cell_index(), pya.DCplxTrans(1, 0, True, float(x) + 800 * i, float(y))))
ly.write(dst)
print(f"MAKE_FIXTURE {dst}")
