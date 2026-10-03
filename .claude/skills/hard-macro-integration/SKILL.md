---
name: hard-macro-integration
description: 把 SRAM、IP 這類 hard macro（已完成版圖的區塊）放進 LibreLane 設計，或換一顆 macro（例如 OpenRAM 自產 SRAM）時使用：MACROS 宣告、各種 view 的來源與產生、擺放與 halo、未用 port 的 tie-off、整合檢查清單。Use when integrating or replacing a hard macro (SRAM/IP) in a LibreLane design.
---

# Hard macro 整合

整合流程與清單；每一項 signoff 的細節連到對應 skill，這裡不重複。本 repo 實例：`pnr/soc_top/config.json`、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`、ADR-0006／0007／0008。

## 整合清單（已驗證）

1. **view 來源**（每一個產生檔都要有 `--check` 模式，harden 前檢查是否過期：`pnr/soc_top/check_inputs.py`）

   | view | 做法 | 出處 |
   |---|---|---|
   | GDS | PDK 原檔 | `config.json` MACROS |
   | LEF | PDK LEF 補 `ANTENNAGATEAREA`（`gen_antenna_lef.py`） | ADR-0008、`antenna-signoff` |
   | .lib | 保守的 padded.lib，`lib: {"*": [...]}`；少一個 corner 會被當 black box 且不報錯 | ADR-0007、`project-plan.md` §6.2 |
   | 合成 | `(* blackbox *)` 的 `.bb.v`（MACROS `vh`）；行為模型不可進 `VERILOG_FILES` | §6.1 |
   | 模擬 | 修正過的行為模型（加 timescale、關 VERBOSE、宣告順序） | `ip/sram/.../README.md` |

2. **擺放**：macro 位置、halo、IO pin 與壅塞的規則在 `floorplan-congestion`；這裡只檢查 `MACROS.instances` 的座標與方向和 floorplan 決定一致（`check_soc.py placement`）。
3. **未用的 port**：輸入接 tie cell（RTL 直接寫常數，合成會產生 `conb_1`）；輸出接 RTL 具名 wire，就不算斷線。checker 要檢查實際的 tie 值（`check_soc.py port1_tieoff`）。
4. **電源**：`VDD_NETS`／`GND_NETS` 與 macro 電源 pin 同名；`PDN_MACRO_CONNECTIONS`；實體連接靠 LVS 驗證（`lvs-signoff`、`pdn-ir-drop`）。
5. **後續各項**：時序（`drv-timing-closure`）→ antenna（`antenna-signoff`）→ DRC baseline（`drc-signoff`）→ LVS black box 範圍（`lvs-signoff`）→ GL 模擬模型（`gate-level-simulation`）→ EQY blackbox（`formal-equivalence-eqy`）。

## negative test

P08 tie-off 斷開 → `check_soc.py port1_tieoff`；P09 擺放漂移 → `check_soc.py placement`；P04／P05／P06 見對應 skill。

## 用完後

新 macro 的特殊情況寫進「經驗紀錄」；同一類問題第二次出現就搬進清單。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore1 | `PDN-0179 Unable to repair all channels` | 已驗證：SRAM 上方只剩約 6 µm row | SRAM 移到 halo 蓋過 core 邊界 | ADR-0006 補充 |
