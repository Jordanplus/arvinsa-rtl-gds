# 2 KB 1rw1r 32x512 with byte write, with the settings of the prebuilt sky130_sram_2kbyte_1rw1r_32x512_8
# (fossi-foundation/sky130_sram_macros 5ad1c96: configs/sky130_sram_2kbyte_1rw1r_32x512_8.py + sky130_sram_common.py).
# words_per_row = 1: no column mux (the read failure of ADR-0010 needs the NMOS-only column mux; ADR-0018
# decision 3, step 3b). Everything else as arv_sram_2kbyte_1rw1r_32x512_8.py. Generate with
#   make openram-macro OPENRAM_CONFIG=ip/sram/openram/configs/arv_sram_2kbyte_1rw1r_32x512_8_wpr1.py
word_size = 32
num_words = 512
write_size = 8
num_rw_ports = 1
num_r_ports = 1
num_w_ports = 0
tech_name = "sky130"
nominal_corner_only = True
route_supplies = "side"
check_lvsdrc = True
uniquify = True
words_per_row = 1
output_name = "arv_sram_2kbyte_1rw1r_32x512_8_wpr1"
