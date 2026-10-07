# 工具與版本清單（toolchain）

最後更新：2026-10-05　維護者：專案主控（Claude 與使用者）

這份清單記錄本專案用到的每個工具、版本與來源。**釘版的唯一來源是 `env/versions.mk`**，本文件是給人看的說明。

## 維護規則

- 升級、新增或移除工具時，**同時**更新 `env/versions.mk`（若有釘版）與本文件，並在 `docs/decisions/` 補 ADR（影響結果的變更）。
- `make env-check` 會自動比對：`env/versions.mk` 的每個值、以及本機實際偵測到的工具版本，都必須出現在本文件中；不一致就 FAIL 並指出哪一項過期。
- 不在本清單上的工具，不得成為任何 make target 的必要依賴。

## 1. 本機工具（Phase 1 使用，已安裝）

| 工具 | 用途 | 目前版本 | 最低版本 | 安裝來源 |
|---|---|---|---|---|
| Verilator | RTL lint（L0）、RTL／GL 模擬 | 5.050 | 5.050 | Homebrew `verilator` |
| Icarus Verilog | RTL／GL 模擬（4-state，用於 X 檢查） | 13.0 | 13.0 | Homebrew `icarus-verilog` |
| Yosys | 本機合成 sanity check、上游 picorv32 `test_synth` | 0.69 | 0.69 | Homebrew `yosys`（git `143eb14f`） |
| riscv64-elf-gcc | firmware 編譯（rv32 multilib：rv32i／rv32im／rv32iac／rv32imac／rv32imafc，ABI ilp32；無 newlib） | 16.1.0 | 16.1 | Homebrew `riscv64-elf-gcc` |
| riscv64-elf-binutils | 組譯、連結、objcopy、objdump | 2.46.1 | — | Homebrew `riscv64-elf-binutils` |
| C++ 編譯器（Apple clang） | Verilator `--binary` 把產生的 C++ 編譯成模擬執行檔（`make regress-rtl` 的 Verilator 部分需要） | 21.0.0 | — | Xcode Command Line Tools（`/usr/bin/c++`，CLTools 27.0） |
| Python | regression script、checker（只用標準函式庫，設定檔用 `tomllib`） | 3.14.6 | 3.11 | Homebrew `python@3.14` |
| ngspice | SRAM macro 的 SPICE 特性化（Phase 3.5，ADR-0010）；sky130 模型的設定用 PDK 的 `libs.tech/ngspice/spinit` | 47 | 47 | Homebrew `ngspice`（含 KLU） |
| GNU make | 統一入口 | 3.81 | — | macOS 內建 `/usr/bin/make` |
| bash | script 執行 | 3.2.57 | — | macOS 內建 `/bin/bash` |
| git | 版本控制、submodule | 2.54.0 | — | macOS 內建（Apple Git-157） |

相容性限制（寫 script 時必須遵守）：
- **GNU make 3.81**：不支援 `.SHELLFLAGS`、`.ONESHELL`、`$(file ...)`、`undefine`。
- **bash 3.2**：不支援 associative array（`declare -A`）、`mapfile`／`readarray`、`${var,,}`、`|&`、`coproc`。
- **riscv64-elf-gcc 無 newlib**：firmware 必須 `-ffreestanding -nostdlib`，只能連結 `libgcc`。

### 1.1 裝在 repo 裡的工具（`.tools/`，不在 PATH 上）

| 工具 | 用途 | 版本 | 安裝 | 驗證 |
|---|---|---|---|---|
| xPack riscv-none-elf-gcc | 含 newlib 的 RISC-V 工具鏈：Hazard3 上游測試（riscv-tests、sw_testcases）需要 libc（Phase 5，ADR-0011）；multilib 含 rv32imc／ilp32 | `XPACK_RISCV_VERSION = 15.2.0-1`（GCC 15.2.0），darwin-arm64 壓縮檔 `XPACK_RISCV_SIZE = 401163559` bytes，`XPACK_RISCV_SHA256 = 6588e8351455fad8aca37551f0e5a5543f3346bfa9a837cf03cbd3bdd4989f8f`（與官方 `.sha` 檔、GitHub asset digest 相同） | `make xpack-fetch`（`env/fetch_xpack.sh`：8 段平行、可續傳、比對大小與 sha256 後解壓到 `.tools/xpack-riscv-none-elf-gcc-15.2.0-1/`，約 1.5 GB；下載快取用完即刪） | 2026-10-05：`-march=rv32imc -mabi=ilp32 -specs=nano.specs -specs=nosys.specs` 編譯含 `snprintf` 的程式成功 |

## 2. RTL-to-GDS flow（Phase 0，2026-10-03 已安裝；`librelane --smoke-test` PASS）

工具都在 LibreLane 的 nix-shell 裡（`cd .tools/librelane && nix-shell`），版本由 LibreLane 3.0.14 的 `flake.lock` 決定，不另外釘版。soc_top 的 config 用 repo 的 LibreLane plugin 換掉 CTS step（`pnr/librelane_plugin_arvinsa/`，ADR-0016）：手動執行完整 flow 時 `PYTHONPATH` 要含 `pnr/`（`pnr/librelane_flow.sh` 已設好）。
`make flow-setup` 會把實際版本寫到 `runs/flow_setup/versions.txt`；下表就是 2026-10-03 那次的結果。

| 工具 | 用途 | 版本 | 來源 | 狀態 |
|---|---|---|---|---|
| Nix | 提供 LibreLane 與其內建工具 | 2.35.2（安裝程式：NixOS/nix-installer 2.35.2，`nix-installer-aarch64-darwin` sha256 `6314b195321b3acc6826b1c5d66bb9cf9306c8231c6dbb745f51a04c3bcee235`，內含 Nix 本體） | `make nix-install`（`env/install_nix.sh`）：直接從 GitHub releases 下載安裝程式（可續傳、無速度門檻），快取在 `.tools/nix-installer/`，含 FOSSi binary cache | 已安裝 |
| LibreLane | RTL-to-GDS flow（Classic flow） | 3.0.14（commit `f24e0ea5db2260719e9a0c7d51d07db74a87fa23`） | `make flow-setup` clone 到 `.tools/librelane`（github.com/librelane/librelane） | 已安裝，smoke test PASS |
| ciel | 下載與管理 PDK | 2.4.0 | LibreLane nix-shell | 已安裝 |
| Yosys（flow 用） | 正式合成 | 0.62（git `7326bb7d`） | LibreLane nix-shell | 已安裝 |
| OpenROAD（含 OpenSTA） | floorplan、PDN、place、CTS、route、STA | nix 套件 `openroad-2026-02-17`（`openroad -version`：`dcf36133a369abc8f3c5e5738cd4d82e4903c0e0`） | LibreLane nix-shell | 已安裝 |
| Magic | DRC、GDS 輸出、SPICE extraction | 8.3.623 | LibreLane nix-shell | 已安裝 |
| KLayout | DRC、GDS 輸出、XOR | 0.30.7 | LibreLane nix-shell | 已安裝 |
| Netgen | LVS | 1.5.316 | LibreLane nix-shell | 已安裝 |
| Verilator（flow 用） | `Verilator.Lint` step | 5.044 | LibreLane nix-shell | 已安裝 |
| EQY、SBY（YosysHQ） | formal equivalence（`make eqy-core`／`eqy-soc`，Phase 3）；`eqy.formal_pdk_proc` 把 sky130 cell 模型轉成 formal 可用的形式 | 隨 Yosys 0.62（nix 套件 `yosys-eqy-0.62`、`yosys-sby-0.62`） | LibreLane nix-shell | 已安裝。EQY 的切分步驟要 `ulimit -s 65520`（64 MB stack），8 MB 預設會 SIGSEGV；SBY 的 PDR 反例轉換需要的 `yices` 不在 nix-shell 內（只影響失敗時的波形，不影響 PASS／FAIL 判定），見 `signoff/eqy/README.md` |

注意：flow 用的 Yosys（0.62）、Verilator（5.044）比 §1 的本機版本（0.69、5.050）舊。正式流程一律用 nix-shell 內的版本；§1 的版本只用在 Phase 1 的本機模擬與 sanity check。

LibreLane CI 參考設計（`test_sram_macro` golden）：librelane-ci-designs commit `9b3bebe834ccd972a5b4f10d82c32354f9a6a1ca`，也就是 LibreLane 3.0.14 自己的 `test/designs` submodule 指向的 commit（官方 CI 跑的就是這份）。

## 3. PDK

| 項目 | 值 | 狀態 |
|---|---|---|
| PDK | sky130A | 已安裝（2026-10-03） |
| 標準元件庫 | sky130_fd_sc_hd | 已安裝 |
| open_pdks commit（LibreLane 3.0.14 綁定，`librelane/pdk_hashes.yaml`） | `8afc8346a57fe1ab7934ba5a6056ea8b43078e71` | 已安裝 |
| 安裝方式 | `make pdk-fetch`（`env/fetch_pdk.sh`）：7 個壓縮檔平行下載、可續傳，快取在 `.tools/pdk-cache/`；sha256 釘在 `env/sky130_pdk_assets.sha256`（取自 GitHub release 的 digest）；再由 ciel 從本機 mirror 安裝 | — |
| 安裝位置與內容 | `~/.ciel`（2.1 GB）：ciel 的 sky130 預設函式庫 sky130_fd_io、sky130_fd_pr、sky130_fd_sc_hd、sky130_fd_sc_hvl、sky130_ml_xx_hd、sky130_sram_macros | — |
| PDK 內容（Phase 4） | flow 讀的 6 個目錄（`libs.tech/{klayout,magic,netgen,openlane}`、`libs.ref/sky130_fd_sc_hd`、`libs.ref/sky130_sram_macros`，2109 個檔）的 sha256 摘要釘在 `env/pdk_content.sha256`，由 `provenance.py --make-pdk-content --from-tarballs .tools/pdk-cache/sky130-<hash>` 從上面的壓縮檔算出；每次 harden 由 `provenance.py` 比對安裝好的 PDK（改過任何一個檔就 FAIL）。升級 PDK 時要重新產生 | — |
| SRAM macro 檢查（`make env-check`） | PDK 內 `sky130_sram_2kbyte_1rw1r_32x512_8` 的 LEF 有 `FOREIGN`、尺寸 683.1 × 416.54 µm；Verilog 模型與 §4 釘版副本 sha256 相同 | PASS |

為什麼不用 LibreLane 自己下載 PDK：ciel 只用一條連線、不能續傳。2026-10-03 本機到 GitHub 單一連線只有 45–175 KB/s，中斷就要從頭重下約 340 MB；平行下載約 360 KB/s。

## 4. IP

| IP | 用途 | 版本 | 授權 | 位置 |
|---|---|---|---|---|
| PicoRV32 | RISC-V CPU（Phase 1–4） | commit `ef203c2b0a3fb793280f5114941416c425c5b461` | ISC | `third_party/picorv32`（submodule） |
| simpleuart | UART（取自 PicoRV32 的 picosoc） | 同上 | ISC | `third_party/picorv32/picosoc/simpleuart.v` |
| sky130_sram_2kbyte_1rw1r_32x512_8 | 2 KB SRAM macro | fossi-foundation/sky130_sram_macros commit `5ad1c96053ee8223fe7e956e314646adfce605dd`；行為模型 sha256 `2712357fbc3d1ee3343c4bcb7d630de92ca87d869fb5d50d1d3cea967f288208` | Apache-2.0 | `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`（repo：https://github.com/fossi-foundation/sky130_sram_macros） |

## 5. 後續階段才會加入

| 工具／IP | 階段 | 用途 | 備註 |
|---|---|---|---|
| Hazard3 | Phase 5 | 第二顆 RISC-V core | Apache-2.0 |
| OpenRAM | Phase 3.5／6 | SRAM 產生與 SPICE characterization | 只支援 x86_64 Linux（Colab 或 Lima VM） |
| CVC | 可選 | 含 SDF 的 gate-level 模擬 | x86_64 Linux |

## 6. 釘版值對照（由 `make env-check` 檢查）

以下各值必須與 `env/versions.mk` 一致：
`PDK = sky130A`、`STD_CELL_LIBRARY = sky130_fd_sc_hd`、`SRAM_MACRO = sky130_sram_2kbyte_1rw1r_32x512_8`、`RISCV_PREFIX = riscv64-elf-`、
`VERILATOR_MIN = 5.050`、`ICARUS_MIN = 13.0`、`YOSYS_MIN = 0.69`、`RISCV_GCC_MIN = 16.1`、`PYTHON_MIN = 3.11`；
xPack 工具鏈的三個值見 §1.1。乾淨 worktree 沒有 `.tools/`：設 `XPACK_DIR` 指向已安裝的目錄（與 `LIBRELANE_DIR` 相同做法）；`make env-check-flow CPU=hazard3` 檢查它。

## 7. 各 regression 實際用到的工具子元件與 override（驗證紀錄）

這一節記錄「哪一組版本下，哪支 regression test 實際 PASS」，方便升級工具後回頭比對。工具版本以 §1 為準；這裡只補 §1 沒寫出來的子元件與 make 命令列 override。

### 7.1 L1a core-stock（`make core-stock`，`scripts/core_stock.sh`；2026-10-03 實測）

| 子元件 | 用在哪裡 | 版本（實測） | 對應 §1 的列 |
|---|---|---|---|
| `iverilog` | 編譯上游 `testbench.v`、`testbench_wb.v`、`testbench_ez.v`、`testbench_synth` | 13.0 | Icarus Verilog |
| `vvp` | 執行上述編譯結果（Icarus 的模擬執行器，隨 Icarus 安裝） | 13.0 | Icarus Verilog |
| `yosys` | `test_synth`：用上游 `scripts/yosys/synth_sim.ys` 合成出 `synth.v` | 0.69+post（git `143eb14f`） | Yosys |
| `riscv64-elf-gcc` | 編譯上游 firmware：`-march=rv32imc`／`rv32ic`／`rv32im`、`-mabi=ilp32`、`-ffreestanding -nostdlib`，只連結 `libgcc` | 16.1.0 | riscv64-elf-gcc |
| `riscv64-elf-ld`、`riscv64-elf-objcopy` | 連結 firmware、轉成 `.bin` | 2.46.1 | riscv64-elf-binutils |
| `python3`（標準函式庫） | 上游 `firmware/makehex.py`；`core_stock.sh` 內 `test_ez` 的 checker | 3.14.6 | Python |
| `make`、`bash` | 上游 Makefile、`core_stock.sh` | 3.81、3.2.57 | GNU make、bash |

make 命令列 override（上游 Makefile 一律不改）：

| override | 為什麼需要 |
|---|---|
| `TOOLCHAIN_PREFIX=riscv64-elf-` | 上游預設指向 `/opt/riscv32i/bin/riscv32-unknown-elf-`，本機沒有；改用 §1 的 `riscv64-elf-gcc` |
| （無其他） | GCC 16.1 下上游 `GCC_WARNS` 的 `-Werror` 沒有觸發；`-march=rv32imc` 不需要加 `_zicsr` |

結果（上述組合）：`test`、`test_ez`、`test_wb`、`test_synth` 全部 PASS；`test_rvf` 為 N/A，原因是它需要 riscv-formal（YosysHQ/riscv-formal）產生的 `rvfimon.v`，該 repo 不在本專案內、也不在本清單上（依「不在清單上的工具不得成為必要依賴」的規則排除）。細節見 `docs/notes/core_stock.md`。

升級 §1 的 iverilog／Yosys／riscv64-elf-gcc／binutils 任何一項後，要重跑 `make core-stock`，並回來更新本節的版本與結果。
