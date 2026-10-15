# Phase 6 step 3b experiment: the tt_n40C_1v60 wrong reads of the wpr1 macro at 20 ns, again at other periods.
import os, sys, json
os.environ["SRAM_CHAR_MACRO"] = "arv_sram_2kbyte_1rw1r_32x512_8_wpr1"
os.environ["SRAM_CHAR_WORDS_PER_ROW"] = "1"
sys.path.insert(0, "ip/sram/char")
import sramchar as sc, characterize as ch
sc.PVTS.update({"tt_n40C_1v60": ("tt", 1.60, -40.0)})
w = os.path.abspath("runs/openram/read_check_wpr1/read_check_work")
runner = ch.Runner(os.path.join(w, "trimmed.spice"), w, 4)
ms, ml = ch.CLK_SLEWS[1], ch.LOADS[1]
out = {}
for period in (20.0, 30.0, 44.0):
    s = ch.delay_seq("tt_n40C_1v60", ms, ml, period=period)
    wave = runner.submit(s, f"period_{period:g}").result()
    out[period] = [f"cycle {b[0]} {b[1]}: {b[2]}" for b in sc.check_reads(s, wave)]
    print(period, "ns:", "讀對" if not out[period] else out[period])
json.dump(out, open("runs/openram/read_check_wpr1/period_exp.json", "w"), indent=1)
