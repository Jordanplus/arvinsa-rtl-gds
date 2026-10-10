# 2 KB 1rw 32x512 with byte write: the 1rw1r config with port 1 removed. Feasibility probe only (Phase 6 step 3f,
# ADR-0018 decision 11): at the pinned OpenRAM it generates, but OpenRAM's DRC reports 657 and LVS does not match
# (the column cap rows tie BL and BR of every column together). Rerun it when the OpenRAM pin moves
# (openram-macro-characterization rule 26):
#   make openram-macro OPENRAM_CONFIG=ip/sram/openram/configs/arv_sram_2kbyte_1rw_32x512_8.py
word_size = 32
num_words = 512
write_size = 8
num_rw_ports = 1
num_r_ports = 0
num_w_ports = 0
num_spare_cols = 1    # sky130 1rw needs an even number of columns including the replica column (128 + 1 rbl)
tech_name = "sky130"
nominal_corner_only = True
route_supplies = "side"
check_lvsdrc = True
uniquify = True
output_name = "arv_sram_2kbyte_1rw_32x512_8"
