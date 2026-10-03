# 工具與版本清單（toolchain）

最後更新：2026-10-03　維護者：專案主控（Claude 與使用者）

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
| Python | regression script、checker（只用標準函式庫，設定檔用 `tomllib`） | 3.14.6 | 3.11 | Homebrew `python@3.14` |
| GNU make | 統一入口 | 3.81 | — | macOS 內建 `/usr/bin/make` |
| bash | script 執行 | 3.2.57 | — | macOS 內建 `/bin/bash` |
| git | 版本控制、submodule | 2.54.0 | — | macOS 內建（Apple Git-157） |

相容性限制（寫 script 時必須遵守）：
- **GNU make 3.81**：不支援 `.SHELLFLAGS`、`.ONESHELL`、`$(file ...)`、`undefine`。
- **bash 3.2**：不支援 associative array（`declare -A`）、`mapfile`／`readarray`、`${var,,}`、`|&`、`coproc`。
- **riscv64-elf-gcc 無 newlib**：firmware 必須 `-ffreestanding -nostdlib`，只能連結 `libgcc`。

## 2. RTL-to-GDS flow（Phase 0，**待安裝**：需要使用者以 sudo 安裝 Nix，見 `env/setup.md`）

| 工具 | 用途 | 版本 | 來源 | 狀態 |
|---|---|---|---|---|
| Nix | 提供 LibreLane 與其內建工具 | 安裝時記錄 | Determinate nix-installer + FOSSi binary cache | 待安裝 |
| LibreLane | RTL-to-GDS flow（Classic flow） | 3.0.14（commit `f24e0ea5db2260719e9a0c7d51d07db74a87fa23`） | github.com/librelane/librelane | 待安裝 |
| ciel | 下載與管理 PDK | 隨 LibreLane | LibreLane 內建 | 待安裝 |
| Yosys（flow 用） | 正式合成 | 隨 LibreLane nix-shell，安裝後填入 | LibreLane 內建 | 待安裝 |
| OpenROAD（含 OpenSTA） | floorplan、PDN、place、CTS、route、STA | 安裝後填入 | LibreLane 內建 | 待安裝 |
| Magic | DRC、GDS 輸出、SPICE extraction | 安裝後填入 | LibreLane 內建 | 待安裝 |
| KLayout | DRC、GDS 輸出、XOR | 安裝後填入 | LibreLane 內建 | 待安裝 |
| Netgen | LVS | 安裝後填入 | LibreLane 內建 | 待安裝 |
| Verilator（flow 用） | `Verilator.Lint` step | 安裝後填入 | LibreLane 內建 | 待安裝 |

LibreLane CI 參考設計（`test_sram_macro` golden）：librelane-ci-designs commit `eef8e18b03c4d5fadbaa48a6a72c2b9aee7e5372`。

## 3. PDK

| 項目 | 值 | 狀態 |
|---|---|---|
| PDK | sky130A | 待下載（ciel） |
| 標準元件庫 | sky130_fd_sc_hd | 待下載 |
| open_pdks commit（LibreLane 3.0.14 綁定，`librelane/pdk_hashes.yaml`） | `8afc8346a57fe1ab7934ba5a6056ea8b43078e71` | 待下載 |

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
| xPack riscv-none-elf-gcc | Phase 5 | 含 newlib 的工具鏈（Hazard3 benchmark） | 有 macOS arm64 原生版 |
| OpenRAM | Phase 3.5／6 | SRAM 產生與 SPICE characterization | 只支援 x86_64 Linux（Colab 或 Lima VM） |
| CVC | 可選 | 含 SDF 的 gate-level 模擬 | x86_64 Linux |

## 6. 釘版值對照（由 `make env-check` 檢查）

以下各值必須與 `env/versions.mk` 一致：
`PDK = sky130A`、`STD_CELL_LIBRARY = sky130_fd_sc_hd`、`SRAM_MACRO = sky130_sram_2kbyte_1rw1r_32x512_8`、`RISCV_PREFIX = riscv64-elf-`、
`VERILATOR_MIN = 5.050`、`ICARUS_MIN = 13.0`、`YOSYS_MIN = 0.69`、`RISCV_GCC_MIN = 16.1`、`PYTHON_MIN = 3.11`。
