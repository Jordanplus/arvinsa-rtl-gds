# sky130_sram_2kbyte_1rw1r_32x512_8

OpenRAM 產生的 sky130 2 KB SRAM macro（512 words × 32 bit，byte write mask，1RW + 1R 兩個 port）。

## 來源

| 項目 | 值 |
|---|---|
| Repo | https://github.com/fossi-foundation/sky130_sram_macros |
| Commit | `5ad1c96053ee8223fe7e956e314646adfce605dd`（2025-07-10） |
| 授權 | Apache-2.0 |
| 與 PDK 的關係 | open_pdks 從同一個 fossi repo 安裝到 `$PDK_ROOT/sky130A/libs.ref/sky130_sram_macros`；LibreLane 3.0.14 綁定的 sky130 PDK 版本見 `env/versions.mk` |

## 檔案

| 檔案 | 用途 |
|---|---|
| `upstream/sky130_sram_2kbyte_1rw1r_32x512_8.v` | 上游行為模型原檔，未修改 |
| `sim/sky130_sram_2kbyte_1rw1r_32x512_8.v` | 模擬用副本：只加 `\`timescale 1ns/1ps` 並把 `VERBOSE` 改成 0，差異見 `sim/sky130_sram_2kbyte_1rw1r_32x512_8.v.diff` |
| `sky130_sram_2kbyte_1rw1r_32x512_8.bb.v` | lint 與合成用的 blackbox 宣告；**不可**放進模擬 |

GDS、LEF、.lib 在 Phase 3 由 PDK 內的版本提供，不在此 vendor。

## 行為模型時序（模擬用，非 silicon 時序）

- 上升緣：取樣 csb0／web0／wmask0／addr0／din0；同時在上升緣後 `T_HOLD`=1 ns 把 dout0 設成 X。
- 下降緣：寫入（依取樣到的 wmask0）；讀出則在下降緣後 `DELAY`=3 ns 更新 dout0。
- 因此讀出資料只在「讀取的上升緣之後的下降緣 + 3 ns」到「下一個上升緣 + 1 ns」之間有效，**必須在下一個上升緣用 register 接住**。
- Port 1 tie-off（clk1=0）時，port 1 的 always block 不會觸發。

注意：上游 .lib 是 OpenRAM 解析模型（analytical model），時序數字偏樂觀；見 project-plan.md §5.4、§6.2。
