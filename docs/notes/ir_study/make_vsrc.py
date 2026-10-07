# Build PSM -vsrc files. Format (found by experiment, PSM-0075 rejects whitespace):
#   one source per line: x_um,y_um,size_um,voltage   (square of side 'size' centred at x,y; nodes on the top layer inside it become ideal sources)
# Strap geometry from final/def/soc_top.def PINS: met5 straps x 5.52..994.06 um, PDN_HWIDTH wide
#   (argv[2], default 4.8 since Phase 5; the Phase 4 study used 1.6), 1.7 um apart:
#   vccd1 centre y = 640.25 - k*153.18 ; vssd1 centre y = 640.25 + width + 1.7 - k*153.18 (k=0..4)
#   (1.6 um: 643.55, as in the Phase 4 study; 4.8 um: 646.75)
import os, sys
W = sys.argv[1]
HW = float(sys.argv[2]) if len(sys.argv) > 2 else 4.8
XL = 5.52
for v in ("1.80", "1.60", "1.95"):
    for model in ("oneside", "single"):
        d = f"{W}/vsrc/{model}_v{v}"
        os.makedirs(d, exist_ok=True)
        for net, y0, volt in (("vccd1", 640.25, v), ("vssd1", 640.25 + HW + 1.7, "0")):
            ks = range(5) if model == "oneside" else [0]
            with open(f"{d}/{net}.vsrc", "w") as f:
                for k in ks:
                    y = round(y0 - k * 153.18, 3)
                    # 1.6 um square at the very left end of the strap
                    f.write(f"{XL + 0.8:.3f},{y:.3f},1.6,{volt}\n")
print("done")
