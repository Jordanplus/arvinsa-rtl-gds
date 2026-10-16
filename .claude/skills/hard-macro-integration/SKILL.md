---
name: hard-macro-integration
description: 把 SRAM、IP 這類 hard macro（已完成 layout 的區塊）接進 LibreLane 設計時使用。涵蓋 `MACROS` 宣告與各種 view 的來源（GDS、補 antenna 資料與 `FOREIGN` 的 LEF、每個 PVT 一份 .lib、合成用的 blackbox、模擬模型）；STA 每個 corner 只能讀到一份 macro .lib（`LIB`／`EXTRA_LIBS` 不能重複帶進，少一個 corner 會被當 black box 且沒有錯誤訊息）；placement 和 floorplan 一致；沒用到的 port 怎麼 tie-off（OpenRAM SRAM 沒用到的 port，時脈不能接固定值）；電源連接；macro 在每個 STA corner 能不能動與 placeholder .lib；macro 的 clock（CTS 在 macro clock pin 前插 `delaybuf_*` 對齊 latency，半週期讀出的 setup 與 hold 變差）；detailed routing 報 `DRT-0418 Term sram0/<pin> has no pins on routing grid`；macro 旁的窄 row 報 `PDN-0179`；接進之後的 signoff 順序。選定 macro 前的 go／no-go、view QA（`check_macro_views` FAIL、`ODB-0292`、LEF 沒有 `FOREIGN`、最終 GDS 的 macro 是空的）、.lib 驅動能力與換 macro 的檢查清單看 macro-qualification；.lib 的 SPICE characterization 看 openram-macro-characterization。Use when integrating a hard macro (SRAM/IP) into a LibreLane design (MACROS, view sources, per-corner .lib, tie-offs, power, macro clock).
---

# Hard macro 整合

整合流程與清單；每一項 signoff 的細節連到對應 skill，這裡不重複。2026-10-15 拆分（ADR-0021 決定 5）：交給 flow 之前的檢查（view QA、選定前的 go／no-go、.lib 驅動能力、換 macro 的檢查清單）移到 `macro-qualification`，這裡留接進 flow 的做法。本 repo 實例：`pnr/soc_top/config.json`、`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/`（Phase 6 起，用 OpenRAM 產生，ADR-0018）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`（Phase 3–5，PDK 附的）、ADR-0006／0007／0008。

## 整合清單（已驗證）

0. 第 0 項移到 `macro-qualification` 規則 1（macro 的 view QA，`CLAUDE.md` 規則 12）。
1. **view 來源**（每一個由腳本產生的檔案都要有 `--check` 模式，harden 前檢查是否過期：`pnr/soc_top/check_inputs.py`）

   | view | 做法 | 出處 |
   |---|---|---|
   | GDS | PDK 原檔（PDK 附的 macro）；自己產生的 macro（例如用 memory compiler）用產生器輸出、複製進 repo，sha256 對產生紀錄（`summary.json`） | `config.json` MACROS、`check_inputs.py macro_source` |
   | LEF | PDK 或產生器的 LEF 補 `ANTENNAGATEAREA`、`DATABASE MICRONS` 改成 tech 的值、缺 `FOREIGN` 時補上（`gen_antenna_lef.py`；netlist 沒有 `*.PININFO` 時輸入腳位取自 LEF） | ADR-0008、`antenna-signoff` |
   | .lib | 每個 PVT 一份（`lib: {"*_<pvt>": [...]}`，萬用字元不可重疊），由 SPICE 模擬的量測結果產生，見 `openram-macro-characterization`。少一個 corner 會被當 black box 且沒有錯誤訊息。只有廠商的單一解析 .lib 時，先用保守的 padded .lib 給全部 corner（`"*"`）再用 STA hook 加 derate。`LIB`（std cell）與 `EXTRA_LIBS` 不可以再帶進 macro 的 .lib：LibreLane 會讀進每個 STA corner，和正確的那份同時存在；檢查要打開 STA 讀的每個 .lib，看誰定義了 macro 的 cell，並比完整路徑（本 repo：`check_inputs.py other_libs`、`check_soc.py sram_lib`，P33–P36） | ADR-0010（取代 ADR-0007）、`project-plan.md` §6.2 |
   | 合成 | `(* blackbox *)` 的 `.bb.v`（MACROS `vh`）；行為模型不可進 `VERILOG_FILES` | §6.1 |
   | 模擬 | 修正過的行為模型（加 timescale、關 VERBOSE、宣告順序） | `ip/sram/.../README.md` |

2. **placement**：macro 位置、halo、IO pin 與壅塞的規則在 `floorplan-congestion`；這裡只檢查 `MACROS.instances` 的座標與方向和 floorplan 決定一致（`check_soc.py placement`）。
3. **沒用到的 port**：輸入接 tie cell（RTL 直接寫常數，合成會產生 `conb_1`）；輸出接到 RTL 裡宣告的 wire，就不會被列為 disconnected pin。checker 要檢查實際的 tie 值（`check_soc.py port1_tieoff`）。例外：OpenRAM SRAM 的時脈腳位不能接固定值；它的 chip-select 由該 port 的時脈取樣、沒有 reset，`clk1` 固定為 0 時上電狀態可能讓一列 wordline 一直開著（已用 SPICE 實驗確認，ADR-0018 決定 9；沒用到的 port，時脈要接系統時脈、`csb` 接 1）。checker：`check_soc.py port1_tieoff` 從 `clk1` 沿 buffer／反相器往回追，必須到頂層時脈 port、反相器數為偶數、不是 tie 的 net；negative test P65（`clk1` 接 `conb_1` LO）。接上時脈後 STA 的 `check_setup` 不再有「`clk1` 沒有時脈」的警告，允許清單要清空。
4. **電源**：`VDD_NETS`／`GND_NETS` 與 macro 電源 pin 同名；`PDN_MACRO_CONNECTIONS`；實體連接靠 LVS 驗證（`lvs-signoff`、`pdn-ir-drop`）。
5. **macro 在每個 STA corner 都要先證明功能正確**（這一項應該在選定 macro 之前就做，見 `macro-qualification` 規則 2；這裡是在實際交付的 netlist 上重跑）：時序是在「macro 能動」的前提下才有意義。廠商 macro 不一定在所有 corner 都能動；PDK 的 sky130 2 KB SRAM 在低溫、以及 ss 1.60 V 室溫時讀出前一次的值；STA corner 之間的溫度（例如 25°C）STA 看不到，要另外模擬（ADR-0010「ss −40°C 讀取失敗」）。不能動的 corner 仍要給 .lib（否則被當 black box），用標明 PLACEHOLDER 的 .lib，並列為下線風險；做法看 `openram-macro-characterization` 規則 13。
6. **macro 的 clock**：OpenROAD 的 CTS 預設把 macro 的 clock pin 分到另一棵 tree，插 delay buffer 對齊 flip-flop 的 latency。對 SRAM 這種半週期讀出（在 falling edge launch 資料）的 macro，這串 buffer 的上升緣、下降緣延遲不同，會讓讀出的 setup 與 hold 同時變差；`soc_top` 用 `clock_tree_synthesis -no_insertion_delay` 關掉（ADR-0016，`cts-clock-tree` 規則 10、12）。整合新 macro 時，harden 後先看 macro clock pin 前有沒有 `delaybuf_*`，再拆 macro 讀出路徑 launch／capture 的 clock latency。
7. **後續各項**：時序（`drv-timing-closure`）→ antenna（`antenna-signoff`）→ DRC baseline（`drc-signoff`）→ LVS black box 範圍（`lvs-signoff`）→ GL 模擬模型（`gate-level-simulation`）→ EQY blackbox（`formal-equivalence-eqy`）。

## 提早檢查（流程回顧，ADR-0020，使用者決定）

8. 第 8 項移到 `macro-qualification` 規則 2（選定 macro 之前的 go／no-go）。
9. 第 9 項移到 `macro-qualification` 規則 3（macro .lib 輸出的驅動能力）。
10. 第 10 項移到 `macro-qualification` 規則 4（換 macro 時舊檢查逐條重跑）。

## negative test

P08 tie-off 斷開、P65 沒用到的 port 時脈接固定值 → `check_soc.py port1_tieoff`；P09 sram0 在 final DEF 裡移動 10 µm → `check_soc.py placement`；P14 `sram0` 改名 → `check_soc.py macro`；P64 模擬模型過期 → `check_inputs.py sim_model`；P16–P20 由腳本產生的檔案與來源不一致（少一個 RTL 檔、characterization 產生的 .lib 的 hold arc 被改、antenna LEF 少一行、MACROS 的 lib 指回 PDK 的 TT .lib，config 與 `resolved.json` 各一次）→ `check_inputs.py` 對應的列；P30 某個 corner 讀到別的 PVT 的 .lib → `check_soc.py sram_lib`；P32 hold arc 設 0 → `Checker.HoldViolations`；P04／P05／P06 見對應 skill。view QA 與最終 GDS 比對的 negative test（`neg-macro-views`、P63、P66–P69、P71–P76）在 `macro-qualification`。案例表在 `pnr/soc_top/neg_pnr.py`。

## 用完後

新 macro 的特殊情況寫進「經驗紀錄」；同一類問題第二次出現就搬進清單。

## 經驗紀錄

這張表 2026-10-15 拆分（ADR-0021 決定 5）：view QA 與換 macro 的列（2026-10-10 的 `ODB-0205`、`FOREIGN`、`KeyError: 'sram0'`，2026-10-11 的獨立審查）搬到 `macro-qualification`；這裡留接進 flow 的列。

| 日期 | 專案／run | 現象 | 原因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore1 | `PDN-0179 Unable to repair all channels` | 已驗證：SRAM 上方只剩約 6 µm row | SRAM 移到 halo 蓋過 core 邊界 | ADR-0006 補充 |
| 2026-10-10 | Phase 6 步驟 4a，換 macro | OpenRAM dev 的 netlist 沒有 `*.PININFO`，`gen_antenna_lef` 取不到輸入腳位；新版 Verilog 模型已把 `mem` 宣告放在使用前，`gen_sim_model` 的「恰好一次」搬移會誤刪 | 已驗證（讀檔確認） | 輸入腳位改取 LEF 的 `DIRECTION INPUT` 並核對是 netlist 頂層的 port；`gen_sim_model` 只在宣告晚於使用時搬移 | `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_antenna_lef.py`、`ip/sram/gen_sim_model.py` |
| 2026-10-10 | Phase 6 步驟 4b 第二、三輪 harden（`3ceca55`、`ad184f5`，兩個 CPU） | detailed routing 報 25 行 `[WARNING DRT-0418] Term sram0/<pin> has no pins on routing grid`（`addr0` 3、`addr1` 2、`clk0`、`web0`、沒繞線的 `dout1` 18），兩輪、兩個 CPU 相同；PDK 附的 SRAM 沒有這個警告；最終 DRC、LVS、antenna 都是 0 | 推測：OpenRAM 產生的 LEF，腳位座標沒有對齊 sky130 的繞線格點（沒有量腳位對 track 的偏移） | 只記錄；golden 有 `flow__warnings__count:DRT-0418`，數量改變就會被 golden 比對抓到 | `runs/soc_top/46-openroad-detailedrouting/openroad-detailedrouting.log`、`runs/p6_3m_pico_signoff/criteria_review.md` |
