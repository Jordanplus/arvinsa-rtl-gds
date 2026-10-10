---
name: hard-macro-integration
description: 把 SRAM、IP 這類 hard macro（已完成版圖的區塊）放進 LibreLane 設計，或換一顆 macro（例如 OpenRAM 自產 SRAM）時使用；自建或收到 macro 後先做 view QA（LEF、.lib、Verilog、SPICE、GDS 的名稱、腳位與方向一致，.lib 數值範圍與面積，LEF SIZE 對 GDS 外框，LEF 的 DATABASE MICRONS 不能比 tech LEF 細；check_macro_views 報 internal_power outside、LEF SIZE != GDS box、signal pins differ from the LEF、LEF DATABASE MICRONS 2000 > the tech LEF's 1000）、LEF has no FOREIGN；最終 GDS 的 macro 是空的、XOR 差異幾百萬（design__xor_difference__count）而 KLayout 印 All LEF cells have matching GDS cells、check_macro_gds 報 cell(s) of the macro missing（OpenRAM 的 LEF 沒有 FOREIGN）、OpenROAD Floorplan 報 ODB-0292 LEF data from ... is discarded due to errors（前面有 ODB-0205 LEF UNITS DATABASE MICRON convert factor (2000) is greater than the database units per micron (1000)；OpenRAM 的 LEF）；MACROS 宣告、各種 view 的來源與產生（例如 macro 的 .lib 只有 TT 或只是解析模型時，用 SPICE 實測產生每個 PVT 的 .lib（openram-macro-characterization），或暫時用保守的 padded .lib；LEF 缺 antenna 資料）、macro 在某個 corner（或 corner 之間的溫度）不能動時的佔位 .lib 與下線風險、確認 STA 每個 corner 只讀到一份 macro .lib（LIB／EXTRA_LIBS 不能重複帶進）、擺放是否與 floorplan 一致（擺放規則在 floorplan-congestion）、未用 port 的 tie-off（OpenRAM SRAM 未用 port 的時脈不能接常數）、macro 的 clock（CTS 在 macro clock pin 前插 `delaybuf_*` 對齊 latency，SRAM 半週期讀出的 setup 與 hold 變差，看 cts-clock-tree）、整合檢查清單。Use when integrating or replacing a hard macro (SRAM/IP) in a LibreLane design, including macros with a single-corner or analytical .lib.
---

# Hard macro 整合

整合流程與清單；每一項 signoff 的細節連到對應 skill，這裡不重複。本 repo 實例：`pnr/soc_top/config.json`、`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/`（Phase 6 起，OpenRAM 自產，ADR-0018）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`（Phase 3–5，PDK 預建）、ADR-0006／0007／0008。

## 整合清單（已驗證）

0. **macro 的 view QA：自建或收到 macro，先檢查每個交付檔的內容，不只是檔案在不在**（使用者 2026-10-09：不限 OpenRAM，任何產生或取得 macro 的方式都要做；本 repo `scripts/check_macro_views.py`）。
   - 為什麼：產生工具自己的檢查（DRC、LVS、檔案齊全）不看 LEF、.lib、Verilog 模型的內容；LVS 只把 GDS 和 SPICE 網表綁在一起。2026-10-08 OpenRAM dev 產生的 2 KB SRAM，DRC／LVS 都過，.lib 的 internal_power 全部是 1.036316e+11（預建 macro 13.8），IR drop 分析會直接讀進去（ADR-0018）。
   - 查什麼：LEF `MACRO`／.lib `cell`／Verilog `module`／SPICE `.SUBCKT` 同名；四者的訊號腳位（bus 展開）與方向相同，電源腳位集合相同；.lib 每個數字是有限值，internal_power、腳位電容在合理範圍，延遲不為負，`area` = LEF 長 × 寬；LEF `SIZE` = GDS 頂層 cell 的外框且在原點。
   - 症狀：`check_macro_views: FAIL - <name>: <原因>`（例如 `internal_power 1.036316e+11 outside (0, 1000]`、`LEF SIZE ... != GDS box`、`Verilog signal pins differ from the LEF`）。
   - 怎麼發現：產生 macro 的 target 一定要接這一步（本 repo `make openram-macro` 的第二步，結果在 `runs/openram/<name>/views.json`）；整合中的 macro 用 `make macro-views`。
   - 繞過：QA FAIL 的 view 不能直接交給 flow；修正或替換該 view（例如 .lib 的 power 用 `ip/sram/openram/lib_template.py`），列為已知問題並記錄做法，再用替換後的 view 重跑 QA 到 PASS。
   - 防復發：`make neg-macro-views` Q1–Q13（在 `make regress` 裡）；正常對照用一顆一致的小 macro，另外預建 sky130 2 KB SRAM 的 PDK 原檔與 repo 實際使用的 view 都 PASS。harden 前的 `check_inputs.py` 每次都跑這一步（`macro_views` 列，Phase 6 步驟 4a 接上），並核對 macro 產生器輸出的 sha256（`macro_source`），negative test P63、P66。
   - LEF 的資料庫單位（OpenROAD 的行為，Phase 6 已驗證）：
     - 症狀：OpenROAD.Floorplan 失敗，`[ODB-0292] LEF data from <macro>.lef is discarded due to errors`，前面一條 `[ODB-0205] The LEF UNITS DATABASE MICRON convert factor (2000) is greater than the database units per micron (1000) of the current technology`。OpenRAM dev 的 LEF 寫 `DATABASE MICRONS 2000`，sky130 tech LEF 是 1000；PDK 預建 macro 的 LEF 是 1000，所以 Phase 3–5 沒遇到。
     - 怎麼發現：view QA 的 `units` 檢查（`LEF DATABASE MICRONS 2000 > the tech LEF's 1000`，`--dbu` 給 tech 的值）；harden 時看 Floorplan step 的 log。
     - 繞過：產生 flow 用的 LEF 時改成 tech 的值（本 repo `gen_antenna_lef.py` 的 `tech_units()`）；改之前確認每個座標都在 1/tech 單位的格點上，不在就 FAIL（改了會移動圖形）。OpenRAM 的 sky130 LEF 全部在 0.005 µm 製造格點上，轉換無損。macro 產生後對原始 LEF 做 view QA 時用 `--dbu 2000` 並註明原因。
     - 防復發：`neg-macro-views` Q12（2000 必須 FAIL、1000 必須 PASS）；`check_inputs.py macro_views` 每次 harden 前檢查 flow 用的 LEF。
   - LEF 的 `FOREIGN`（LibreLane KLayout stream-out 的行為，Phase 6 已驗證）：
     - 症狀：harden 只在 signoff 報 `design__xor_difference__count` 幾百萬（Phase 6：5,690,757–5,691,003）；最終 GDS（KLayout 輸出）裡 macro cell 是空的，Magic 的 GDS 是完整的；KLayout 的 log 仍印 `All LEF cells have matching GDS cells`，flow 不報錯。同一份 GDS 上的 Magic DRC 在 macro 框內是 0 個違規、KLayout DRC 也空過。
     - 根因（已驗證：只重跑 `KLayout.StreamOut`，LEF 加 `FOREIGN` 後 169 個 cell 全部進去）：`stream_out.py` 先用 LEF 和 DEF 建出 macro cell、清空，再合併 macro 的 GDS；LEF 有 `FOREIGN` 時這個 cell 是 ghost cell，會被同名 GDS cell 取代；沒有時是普通 cell，GDS cell 照 `KLAYOUT_CONFLICT_RESOLUTION=RenameCell` 改名後沒被引用。缺 GDS 的檢查只看 ghost cell。OpenRAM dev 的 LEF 沒有 `FOREIGN`，PDK 預建 macro 的 LEF 有。
     - 怎麼發現：view QA 的 `foreign` 檢查（`LEF has no FOREIGN <top>`）；harden 後 `check_soc.py macro_gds`（最終 GDS 裡 macro 底下的 cell 與內容等於 macro 的 GDS，`scripts/check_macro_gds.py`）；XOR 只在 Magic 與 KLayout 結果不同時才抓得到。
     - 繞過：產生 flow 用的 LEF 時補 `FOREIGN <macro> ;`（`gen_antenna_lef.py add_foreign()`）；原始 LEF 的 view QA 用 `--no-foreign` 並註明。
     - 防復發：`neg-macro-views` Q13；`check_inputs.py macro_views`；`check_soc.py macro_gds` 與 negative test P67（最終 GDS 的 macro 被清空）、P68（macro 的一個 cell 內容不同）；`magic_drc` 要求框內違規至少是 macro 單獨的一半，P69。
1. **view 來源**（每一個產生檔都要有 `--check` 模式，harden 前檢查是否過期：`pnr/soc_top/check_inputs.py`）

   | view | 做法 | 出處 |
   |---|---|---|
   | GDS | PDK 原檔（預建 macro）；自產 macro 用產生器輸出、複製進 repo，sha256 對產生紀錄（`summary.json`） | `config.json` MACROS、`check_inputs.py macro_source` |
   | LEF | PDK 或產生器的 LEF 補 `ANTENNAGATEAREA`、`DATABASE MICRONS` 改成 tech 的值、缺 `FOREIGN` 時補上（`gen_antenna_lef.py`；網表沒有 `*.PININFO` 時輸入腳位取自 LEF） | ADR-0008、`antenna-signoff` |
   | .lib | 每個 PVT 一份（`lib: {"*_<pvt>": [...]}`，萬用字元不可重疊），由 SPICE 實測產生，見 `openram-macro-characterization`。少一個 corner 會被當 black box 且不報錯。只有廠商的單一解析 .lib 時，先用保守的 padded .lib 給全部 corner（`"*"`）再用 STA hook 加 derate。`LIB`（std cell）與 `EXTRA_LIBS` 不可以再帶進 macro 的 .lib：LibreLane 會讀進每個 STA corner，和正確的那份同時存在；檢查要打開 STA 讀的每個 .lib，看誰定義了 macro 的 cell，並比完整路徑（本 repo：`check_inputs.py other_libs`、`check_soc.py sram_lib`，P33–P36） | ADR-0010（取代 ADR-0007）、`project-plan.md` §6.2 |
   | 合成 | `(* blackbox *)` 的 `.bb.v`（MACROS `vh`）；行為模型不可進 `VERILOG_FILES` | §6.1 |
   | 模擬 | 修正過的行為模型（加 timescale、關 VERBOSE、宣告順序） | `ip/sram/.../README.md` |

2. **擺放**：macro 位置、halo、IO pin 與壅塞的規則在 `floorplan-congestion`；這裡只檢查 `MACROS.instances` 的座標與方向和 floorplan 決定一致（`check_soc.py placement`）。
3. **未用的 port**：輸入接 tie cell（RTL 直接寫常數，合成會產生 `conb_1`）；輸出接 RTL 具名 wire，就不算斷線。checker 要檢查實際的 tie 值（`check_soc.py port1_tieoff`）。例外：OpenRAM SRAM 的時脈腳位不能接常數；它的 chip-select 由該 port 的時脈鎖存、沒有 reset，`clk1` 固定為 0 時上電狀態可能讓一列 wordline 一直開著（已用 SPICE 實驗確認，ADR-0018 決定 9；未用 port 的時脈要接系統時脈、`csb` 接 1）。checker：`check_soc.py port1_tieoff` 從 `clk1` 沿 buffer／反相器往回追，必須到頂層時脈 port、反相器數為偶數、不是 tie 的 net；negative test P65（`clk1` 接 `conb_1` LO）。接上時脈後 STA 的 `check_setup` 不再有「`clk1` 沒有時脈」的警告，允許清單要清空。
4. **電源**：`VDD_NETS`／`GND_NETS` 與 macro 電源 pin 同名；`PDN_MACRO_CONNECTIONS`；實體連接靠 LVS 驗證（`lvs-signoff`、`pdn-ir-drop`）。
5. **macro 在每個 STA corner 都要先證明功能正確**：時序是在「macro 能動」的前提下才有意義。廠商 macro 不一定在所有 corner 都能動；PDK 的 sky130 2 KB SRAM 在低溫、以及 ss 1.60 V 室溫時讀出前一次的值；STA corner 之間的溫度（例如 25°C）STA 看不到，要另外模擬（ADR-0010「ss −40°C 讀取失敗」）。不能動的 corner 仍要給 .lib（否則被當 black box），用標明 PLACEHOLDER 的佔位 .lib，並列為下線風險；做法看 `openram-macro-characterization` 規則 13。
6. **macro 的 clock**：OpenROAD 的 CTS 預設把 macro 的 clock pin 分到另一棵 tree，插 delay buffer 對齊 flip-flop 的 latency。對 SRAM 這種半週期讀出（下降緣送出）的 macro，這串 buffer 的上升緣、下降緣延遲不同，會讓讀出的 setup 與 hold 同時變差；`soc_top` 用 `clock_tree_synthesis -no_insertion_delay` 關掉（ADR-0016，`cts-clock-tree` 規則 10、12）。整合新 macro 時，harden 後先看 macro clock pin 前有沒有 `delaybuf_*`，再拆 macro 讀出路徑 launch／capture 的 clock latency。
7. **後續各項**：時序（`drv-timing-closure`）→ antenna（`antenna-signoff`）→ DRC baseline（`drc-signoff`）→ LVS black box 範圍（`lvs-signoff`）→ GL 模擬模型（`gate-level-simulation`）→ EQY blackbox（`formal-equivalence-eqy`）。

## negative test

Q1–Q13 view 內容錯誤（power 數量級、電容單位、nan、負延遲、面積、GDS 外框、腳位缺漏、方向、電源腳位、名稱、沒有 power、LEF 資料庫單位、LEF 沒有 FOREIGN）→ `scripts/check_macro_views.py`（`make neg-macro-views`）；P63 產生器輸出被改 → `check_inputs.py macro_source`；P64 模擬模型過期 → `sim_model`；P66 LEF SIZE → `macro_views`；P08 tie-off 斷開、P65 未用 port 的時脈接常數 → `check_soc.py port1_tieoff`；P67、P68 最終 GDS 的 macro 被清空或內容不同 → `check_soc.py macro_gds`；P69 框內 DRC 違規太少（macro 不在被檢查的 GDS）→ `magic_drc`；P09 擺放漂移 → `check_soc.py placement`；P14 `sram0` 改名 → `check_soc.py macro`；P16–P20 產生檔與來源不一致（少一個 RTL 檔、特性化 .lib 的 hold 弧被改、antenna LEF 少一行、MACROS 的 lib 指回 PDK 的 TT .lib，config 與 `resolved.json` 各一次）→ `check_inputs.py` 對應的列；P30 某個 corner 讀到別的 PVT 的 .lib → `check_soc.py sram_lib`；P32 hold 弧設 0 → `Checker.HoldViolations`；P04／P05／P06 見對應 skill。

## 用完後

新 macro 的特殊情況寫進「經驗紀錄」；同一類問題第二次出現就搬進清單。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore1 | `PDN-0179 Unable to repair all channels` | 已驗證：SRAM 上方只剩約 6 µm row | SRAM 移到 halo 蓋過 core 邊界 | ADR-0006 補充 |
| 2026-10-10 | Phase 6 步驟 4a，只跑到 PDN 的試跑 `runs/p6_fp_pico` | `[ODB-0205] The LEF UNITS DATABASE MICRON convert factor (2000) is greater than the database units per micron (1000)`、`[ODB-0292] LEF data from .../arv_sram_2kbyte_1rw1r_32x512_8.lef is discarded due to errors`，Floorplan 失敗 | 已驗證（OpenRAM LEF `DATABASE MICRONS 2000`，1178 個座標都在 0.005 µm 格點；改成 1000 後同一個試跑 rc=0） | 清單第 0 項「LEF 的資料庫單位」；`gen_antenna_lef.py tech_units()`、`check_macro_views.py` 單位檢查、Q12 | `runs/p6_fp_pico.console`、`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/arv_sram_2kbyte_1rw1r_32x512_8.lef` |
| 2026-10-10 | Phase 6 步驟 4a，換 macro | OpenRAM dev 的網表沒有 `*.PININFO`，`gen_antenna_lef` 取不到輸入腳位；新版 Verilog 模型已把 `mem` 宣告放在使用前，`gen_sim_model` 的「恰好一次」搬移會誤刪 | 已驗證（讀檔確認） | 輸入腳位改取 LEF 的 `DIRECTION INPUT` 並核對是網表頂層的 port；`gen_sim_model` 只在宣告晚於使用時搬移 | `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/gen_antenna_lef.py`、`ip/sram/gen_sim_model.py` |
| 2026-10-10 | Phase 6 步驟 4b 第一輪 harden（`221822a`，兩個 CPU） | `design__xor_difference__count` 5,691,003／5,690,757（上限 0），其他 signoff 上限都 PASS；`soc_top.gds` 的 SRAM cell 沒有子 cell，Magic 的 GDS 有 168 個；`magic_drc` 框內 0 個違規仍 PASS | 已驗證（單步重跑 `KLayout.StreamOut`，LEF 加 `FOREIGN` 後完整；讀 `stream_out.py`） | 清單第 0 項「LEF 的 FOREIGN」；`add_foreign()`、view QA、`check_macro_gds.py`（步驟 3d）、`magic_drc` 下限；Q13、P67–P69；兩個 CPU 重新 harden | `runs/soc_top.prev`、`runs/p6_4b_harden_*.log`，commit `3ceca55` |
| 2026-10-10 | Phase 6 步驟 4b 第二、三輪 harden（`3ceca55`、`ad184f5`，兩個 CPU） | detailed routing 報 25 行 `[WARNING DRT-0418] Term sram0/<pin> has no pins on routing grid`（`addr0` 3、`addr1` 2、`clk0`、`web0`、沒繞線的 `dout1` 18），兩輪、兩個 CPU 相同；預建 SRAM 沒有這個警告；最終 DRC、LVS、antenna 都是 0 | 推測：OpenRAM 自產 LEF 的腳位座標沒有對齊 sky130 的繞線格點（沒有量腳位對 track 的偏移） | 只記錄；golden 有 `flow__warnings__count:DRT-0418`，數量改變就會被 golden 比對抓到 | `runs/soc_top/46-openroad-detailedrouting/openroad-detailedrouting.log`、`runs/p6_3m_pico_signoff/criteria_review.md` |
| 2026-10-10 | Phase 6 step 4c（`940e395`） | 換成自產 macro `arv_sram_2kbyte_1rw1r_32x512_8` 後，`neg-eqy-soc`／`neg-gl-soc` 以 `KeyError: 'sram0'` 中止；`eqy-soc` 的 SRAM clock 檢查從 step 4a 起被略過 | 已驗證：`signoff/eqy/run_eqy.py` 的網表解析只認 `sky130_` 開頭的 cell | 解析改成任何 cell 名稱，並要求 config `MACROS` 的 instance 被解析到（`formal-equivalence-eqy` 規則 5）。換 macro（尤其換名稱）時，搜尋 repo 中用 cell 名稱前綴或舊 macro 名稱認東西的腳本（例如 `grep -rn "sky130_" signoff dv pnr scripts`，再看每一處是不是在認 cell 種類） | `runs/p6_4c_neg-eqy-soc_*.log` |
