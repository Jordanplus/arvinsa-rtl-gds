---
name: hard-macro-integration
description: 把 SRAM、IP 這類 hard macro（已完成版圖的區塊）放進 LibreLane 設計，或換一顆 macro（例如 OpenRAM 自產 SRAM）時使用；自建或收到 macro 後先做 view QA（LEF、.lib、Verilog、SPICE、GDS 的名稱、腳位與方向一致，.lib 數值範圍與面積，LEF SIZE 對 GDS 外框；check_macro_views 報 internal_power outside、LEF SIZE != GDS box、signal pins differ from the LEF）；MACROS 宣告、各種 view 的來源與產生（例如 macro 的 .lib 只有 TT 或只是解析模型時，用 SPICE 實測產生每個 PVT 的 .lib（openram-macro-characterization），或暫時用保守的 padded .lib；LEF 缺 antenna 資料）、macro 在某個 corner（或 corner 之間的溫度）不能動時的佔位 .lib 與下線風險、確認 STA 每個 corner 只讀到一份 macro .lib（LIB／EXTRA_LIBS 不能重複帶進）、擺放是否與 floorplan 一致（擺放規則在 floorplan-congestion）、未用 port 的 tie-off（OpenRAM SRAM 未用 port 的時脈不能接常數）、macro 的 clock（CTS 在 macro clock pin 前插 `delaybuf_*` 對齊 latency，SRAM 半週期讀出的 setup 與 hold 變差，看 cts-clock-tree）、整合檢查清單。Use when integrating or replacing a hard macro (SRAM/IP) in a LibreLane design, including macros with a single-corner or analytical .lib.
---

# Hard macro 整合

整合流程與清單；每一項 signoff 的細節連到對應 skill，這裡不重複。本 repo 實例：`pnr/soc_top/config.json`、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`、ADR-0006／0007／0008。

## 整合清單（已驗證）

0. **macro 的 view QA：自建或收到 macro，先檢查每個交付檔的內容，不只是檔案在不在**（使用者 2026-10-09：不限 OpenRAM，任何產生或取得 macro 的方式都要做；本 repo `scripts/check_macro_views.py`）。
   - 為什麼：產生工具自己的檢查（DRC、LVS、檔案齊全）不看 LEF、.lib、Verilog 模型的內容；LVS 只把 GDS 和 SPICE 網表綁在一起。2026-10-08 OpenRAM dev 產生的 2 KB SRAM，DRC／LVS 都過，.lib 的 internal_power 全部是 1.036316e+11（預建 macro 13.8），IR drop 分析會直接讀進去（ADR-0018）。
   - 查什麼：LEF `MACRO`／.lib `cell`／Verilog `module`／SPICE `.SUBCKT` 同名；四者的訊號腳位（bus 展開）與方向相同，電源腳位集合相同；.lib 每個數字是有限值，internal_power、腳位電容在合理範圍，延遲不為負，`area` = LEF 長 × 寬；LEF `SIZE` = GDS 頂層 cell 的外框且在原點。
   - 症狀：`check_macro_views: FAIL - <name>: <原因>`（例如 `internal_power 1.036316e+11 outside (0, 1000]`、`LEF SIZE ... != GDS box`、`Verilog signal pins differ from the LEF`）。
   - 怎麼發現：產生 macro 的 target 一定要接這一步（本 repo `make openram-macro` 的第二步，結果在 `runs/openram/<name>/views.json`）；整合中的 macro 用 `make macro-views`。
   - 繞過：QA FAIL 的 view 不能直接交給 flow；修正或替換該 view（例如 .lib 的 power 用 `ip/sram/openram/lib_template.py`），列為已知問題並記錄做法，再用替換後的 view 重跑 QA 到 PASS。
   - 防復發：`make neg-macro-views` Q1–Q11（在 `make regress` 裡）；正常對照用一顆一致的小 macro，另外預建 sky130 2 KB SRAM 的 PDK 原檔與 repo 實際使用的 view 都 PASS。harden 前的 `check_inputs.py` 接這一步排在 Phase 6 步驟 4a。
1. **view 來源**（每一個產生檔都要有 `--check` 模式，harden 前檢查是否過期：`pnr/soc_top/check_inputs.py`）

   | view | 做法 | 出處 |
   |---|---|---|
   | GDS | PDK 原檔 | `config.json` MACROS |
   | LEF | PDK LEF 補 `ANTENNAGATEAREA`（`gen_antenna_lef.py`） | ADR-0008、`antenna-signoff` |
   | .lib | 每個 PVT 一份（`lib: {"*_<pvt>": [...]}`，萬用字元不可重疊），由 SPICE 實測產生，見 `openram-macro-characterization`。少一個 corner 會被當 black box 且不報錯。只有廠商的單一解析 .lib 時，先用保守的 padded .lib 給全部 corner（`"*"`）再用 STA hook 加 derate。`LIB`（std cell）與 `EXTRA_LIBS` 不可以再帶進 macro 的 .lib：LibreLane 會讀進每個 STA corner，和正確的那份同時存在；檢查要打開 STA 讀的每個 .lib，看誰定義了 macro 的 cell，並比完整路徑（本 repo：`check_inputs.py other_libs`、`check_soc.py sram_lib`，P33–P36） | ADR-0010（取代 ADR-0007）、`project-plan.md` §6.2 |
   | 合成 | `(* blackbox *)` 的 `.bb.v`（MACROS `vh`）；行為模型不可進 `VERILOG_FILES` | §6.1 |
   | 模擬 | 修正過的行為模型（加 timescale、關 VERBOSE、宣告順序） | `ip/sram/.../README.md` |

2. **擺放**：macro 位置、halo、IO pin 與壅塞的規則在 `floorplan-congestion`；這裡只檢查 `MACROS.instances` 的座標與方向和 floorplan 決定一致（`check_soc.py placement`）。
3. **未用的 port**：輸入接 tie cell（RTL 直接寫常數，合成會產生 `conb_1`）；輸出接 RTL 具名 wire，就不算斷線。checker 要檢查實際的 tie 值（`check_soc.py port1_tieoff`）。例外：OpenRAM SRAM 的時脈腳位不能接常數；它的 chip-select 由該 port 的時脈鎖存、沒有 reset，`clk1` 固定為 0 時上電狀態可能讓一列 wordline 一直開著（已用 SPICE 實驗確認，ADR-0018 決定 9；未用 port 的時脈要接系統時脈、`csb` 接 1；checker 與 negative test 在 Phase 6 步驟 4a 補）。
4. **電源**：`VDD_NETS`／`GND_NETS` 與 macro 電源 pin 同名；`PDN_MACRO_CONNECTIONS`；實體連接靠 LVS 驗證（`lvs-signoff`、`pdn-ir-drop`）。
5. **macro 在每個 STA corner 都要先證明功能正確**：時序是在「macro 能動」的前提下才有意義。廠商 macro 不一定在所有 corner 都能動；PDK 的 sky130 2 KB SRAM 在低溫、以及 ss 1.60 V 室溫時讀出前一次的值；STA corner 之間的溫度（例如 25°C）STA 看不到，要另外模擬（ADR-0010「ss −40°C 讀取失敗」）。不能動的 corner 仍要給 .lib（否則被當 black box），用標明 PLACEHOLDER 的佔位 .lib，並列為下線風險；做法看 `openram-macro-characterization` 規則 13。
6. **macro 的 clock**：OpenROAD 的 CTS 預設把 macro 的 clock pin 分到另一棵 tree，插 delay buffer 對齊 flip-flop 的 latency。對 SRAM 這種半週期讀出（下降緣送出）的 macro，這串 buffer 的上升緣、下降緣延遲不同，會讓讀出的 setup 與 hold 同時變差；`soc_top` 用 `clock_tree_synthesis -no_insertion_delay` 關掉（ADR-0016，`cts-clock-tree` 規則 10、12）。整合新 macro 時，harden 後先看 macro clock pin 前有沒有 `delaybuf_*`，再拆 macro 讀出路徑 launch／capture 的 clock latency。
7. **後續各項**：時序（`drv-timing-closure`）→ antenna（`antenna-signoff`）→ DRC baseline（`drc-signoff`）→ LVS black box 範圍（`lvs-signoff`）→ GL 模擬模型（`gate-level-simulation`）→ EQY blackbox（`formal-equivalence-eqy`）。

## negative test

Q1–Q11 view 內容錯誤（power 數量級、電容單位、nan、負延遲、面積、GDS 外框、腳位缺漏、方向、電源腳位、名稱、沒有 power）→ `scripts/check_macro_views.py`（`make neg-macro-views`）；P08 tie-off 斷開 → `check_soc.py port1_tieoff`；P09 擺放漂移 → `check_soc.py placement`；P14 `sram0` 改名 → `check_soc.py macro`；P16–P20 產生檔與來源不一致（少一個 RTL 檔、特性化 .lib 的 hold 弧被改、antenna LEF 少一行、MACROS 的 lib 指回 PDK 的 TT .lib，config 與 `resolved.json` 各一次）→ `check_inputs.py` 對應的列；P30 某個 corner 讀到別的 PVT 的 .lib → `check_soc.py sram_lib`；P32 hold 弧設 0 → `Checker.HoldViolations`；P04／P05／P06 見對應 skill。

## 用完後

新 macro 的特殊情況寫進「經驗紀錄」；同一類問題第二次出現就搬進清單。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore1 | `PDN-0179 Unable to repair all channels` | 已驗證：SRAM 上方只剩約 6 µm row | SRAM 移到 halo 蓋過 core 邊界 | ADR-0006 補充 |
