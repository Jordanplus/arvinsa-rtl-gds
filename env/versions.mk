# Pinned versions for reproducible runs. Single source of truth for tool/IP versions.
# Changing any value here requires updating golden results and an ADR (see project-plan.md §7.4).
# Format: plain `NAME = value` lines, readable by GNU make 3.81 and by scripts (grep/sed).

# ---- RTL-to-GDS flow (Phase 0, needs Nix; see env/setup.md) ----
LIBRELANE_TAG        = 3.0.14
LIBRELANE_COMMIT     = f24e0ea5db2260719e9a0c7d51d07db74a87fa23
# open_pdks commit bound to LibreLane 3.0.14 (librelane/pdk_hashes.yaml @ 3.0.14)
SKY130_PDK_HASH      = 8afc8346a57fe1ab7934ba5a6056ea8b43078e71
PDK                  = sky130A
STD_CELL_LIBRARY     = sky130_fd_sc_hd
# LibreLane CI reference designs (test_sram_macro golden, Phase 0)
LIBRELANE_CI_COMMIT  = eef8e18b03c4d5fadbaa48a6a72c2b9aee7e5372

# ---- IP ----
PICORV32_COMMIT      = ef203c2b0a3fb793280f5114941416c425c5b461
SRAM_MACRO           = sky130_sram_2kbyte_1rw1r_32x512_8
SRAM_MACROS_REPO     = https://github.com/fossi-foundation/sky130_sram_macros
SRAM_MACROS_COMMIT   = 5ad1c96053ee8223fe7e956e314646adfce605dd
SRAM_MODEL_SHA256    = 2712357fbc3d1ee3343c4bcb7d630de92ca87d869fb5d50d1d3cea967f288208

# ---- Local tools (minimum versions verified on 2026-10-03) ----
VERILATOR_MIN        = 5.050
ICARUS_MIN           = 13.0
YOSYS_MIN            = 0.69
RISCV_PREFIX         = riscv64-elf-
RISCV_GCC_MIN        = 16.1
PYTHON_MIN           = 3.11
