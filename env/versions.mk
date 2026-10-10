# Pinned versions for reproducible runs. Single source of truth for tool/IP versions.
# Changing any value here requires updating golden results and an ADR (see project-plan.md §7.4).
# Format: plain `NAME = value` lines, readable by GNU make 3.81 and by scripts (grep/sed).

# ---- Nix installer (make nix-install; binary embeds the Nix tarball) ----
NIX_INSTALLER_VERSION        = 2.35.2
NIX_INSTALLER_SHA256_AARCH64_DARWIN = 6314b195321b3acc6826b1c5d66bb9cf9306c8231c6dbb745f51a04c3bcee235

# ---- RTL-to-GDS flow (Phase 0, needs Nix; see env/setup.md) ----
LIBRELANE_TAG        = 3.0.14
LIBRELANE_COMMIT     = f24e0ea5db2260719e9a0c7d51d07db74a87fa23
# open_pdks commit bound to LibreLane 3.0.14 (librelane/pdk_hashes.yaml @ 3.0.14)
SKY130_PDK_HASH      = 8afc8346a57fe1ab7934ba5a6056ea8b43078e71
PDK                  = sky130A
STD_CELL_LIBRARY     = sky130_fd_sc_hd
# LibreLane CI reference designs (test_sram_macro golden, Phase 0): the test/designs submodule commit of LibreLane 3.0.14
LIBRELANE_CI_COMMIT  = 9b3bebe834ccd972a5b4f10d82c32354f9a6a1ca

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
# ngspice: SRAM macro SPICE characterization (Phase 3.5, ADR-0010); verified on 2026-10-04
NGSPICE_MIN          = 47
# xPack RISC-V toolchain with newlib (Phase 5, ADR-0011: Hazard3 upstream tests need libc); make xpack-fetch
# installs it into .tools/. SHA256 = the release's .sha file and GitHub's asset digest (both checked 2026-10-05).
XPACK_RISCV_VERSION  = 15.2.0-1
XPACK_RISCV_SIZE     = 401163559
XPACK_RISCV_SHA256   = 6588e8351455fad8aca37551f0e5a5543f3346bfa9a837cf03cbd3bdd4989f8f

# ---- OpenRAM self-generated SRAM (Phase 6, ADR-0018); make openram-setup installs into .tools/ ----
# The macro is generated and DRC/LVS-checked with OpenRAM's own pinned PDK (decision 5); the SoC flow keeps SKY130_PDK_HASH.
OPENRAM_REPO             = https://github.com/VLSIDA/OpenRAM
OPENRAM_COMMIT           = 3608704cab61c8fdb1f7a0c727ef2fb47bfb15b8
SKY130_FD_BD_SRAM_REPO   = https://github.com/VLSIDA/sky130_fd_bd_sram
SKY130_FD_BD_SRAM_COMMIT = fc63b12883b4bf458ee8c756ba64c37063e1ffb9
# open_pdks commit pinned by OpenRAM's Makefile (SKY130_CIEL, 2022.07.29); only libs.tech (common) and sky130_fd_pr are used
# SHA256 computed on 2026-10-08 from the ciel-releases assets (the release has no digest; sizes match the GitHub API,
# and Colab's independent ciel install of the same hash produced the same macro, docs/notes/openram_phase6_bringup.md)
OPENRAM_PDK_HASH         = e8294524e5f67c533c5d0c3afa0bcc5b2a5fa066
OPENRAM_PDK_COMMON_SHA256 = a37160e9a00e39e540e5e7746c064537c7331d6542ebd7a3b05b5801ef7cf044
OPENRAM_PDK_FD_PR_SHA256  = 9795dee2b08e0ca794e39a041f661b72168cba1dd4140474bde94320d75bcb46
