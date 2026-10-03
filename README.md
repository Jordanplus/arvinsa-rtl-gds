# arvinsa-rtl-gds

以全開源 EDA 工具鏈建立一條可重複執行、有 regression test 的 RTL-to-GDS 流程，
並以開源 RISC-V SoC（含 SRAM macro）當 test vehicle，一路跑到 signoff（DRC／LVS／STA PASS）。

An open-source RTL-to-GDS flow on SkyWater sky130A using LibreLane and OpenRAM SRAM macros,
with RISC-V cores (PicoRV32, then Hazard3) as test vehicles. Documentation is written in Traditional Chinese.

## 專案狀態

**規劃階段（v0.2，2026-10-03），尚未開始實作。** 目前 repo 只有文件，還沒有 RTL、flow 設定或 script。
完整規劃見 [project-plan.md](project-plan.md)。

## 技術組合

| 項目 | 選擇 |
|---|---|
| PDK | SkyWater sky130A，標準元件庫 `sky130_fd_sc_hd` |
| RTL-to-GDS flow | [LibreLane](https://github.com/librelane/librelane) 3.x（Classic flow），內含 Yosys、OpenROAD、Magic、KLayout、Netgen |
| SRAM | 先用 PDK 內附的預建 OpenRAM macro（2 KB，`sky130_sram_2kbyte_1rw1r_32x512_8`），後期改用 [OpenRAM](https://github.com/VLSIDA/OpenRAM) 自產 |
| RISC-V core | 先用 [PicoRV32](https://github.com/YosysHQ/picorv32)，再換 [Hazard3](https://github.com/Wren6991/Hazard3)，證明流程可以換 core |
| 模擬 | Verilator、Icarus Verilog |
| Firmware | riscv64-elf-gcc（rv32） |
| 執行環境 | Apple Silicon macOS + Nix；OpenRAM 需要 x86_64 Linux |

## 為什麼不是 SkyWater 90nm

原本的目標是 SkyWater 90nm FD-SOI（SKY90-FD）。查證後發現它的開源版本無法使用：
主 repo 停在實驗性預覽並已於 2026-02 封存，標準元件庫 repo 裡沒有任何 cell，
OpenRAM、LibreLane、OpenROAD 也都不支援這個製程。
因此改用同為 SkyWater 的 sky130A，並讓流程設定與 PDK 無關，日後取得 sky90 PDK 時可以替換。
查證細節與出處見 project-plan.md 第 1 章。

## 階段路線圖

| Phase | 內容 | 狀態 |
|---|---|---|
| 0 | 環境建置：Nix、LibreLane、sky130A PDK；重跑 LibreLane 官方 SRAM 範例當 golden 參考 | 未開始 |
| 1 | SoC RTL 與 firmware、RTL 模擬 regression | 未開始 |
| 2 | 單獨 harden PicoRV32，打通流程並取得面積與時序實測值 | 未開始 |
| 3 | 整合預建 SRAM macro | 未開始 |
| 3.5 | （可選）用 OpenRAM 做 SPICE characterization，校正 SRAM 時序模型 | 未開始 |
| 4 | Signoff 收斂、單一指令跑完整 regression、補齊文件 | 未開始 |
| 5 | 換成 Hazard3 | 未開始 |
| 6 | 用 OpenRAM 自產的 SRAM 取代預建 macro | 未開始 |
| 7 | （可選）chip-level 整合，例如 ChipFoundry Caravel | 未開始 |

各階段的 exit criteria 與工時估計見 project-plan.md 第 8 章。

## 驗證方式

- **分層 regression test**：lint、RTL 模擬、gate-level 模擬、PnR signoff、equivalence check、post-layout 模擬。
- **Signoff 門檻**：9 個 STA corner（tt／ss／ff 三種 library corner × 三種繞線寄生 RC）的 setup 與 hold 全部 PASS，
  另有 DRC、LVS、antenna、IR drop 等 metrics 門檻。
- **Bug injection**：刻意植入錯誤，確認對應的 checker 確實會 FAIL，避免 checker 永遠 PASS 卻抓不到問題。

細節見 project-plan.md 第 6、7 章。

## 授權

本 repo 的內容以 [Apache License 2.0](LICENSE) 授權。
之後引入的第三方元件保留各自的授權，例如 PicoRV32 為 ISC，Hazard3 與 sky130 PDK 為 Apache-2.0。
