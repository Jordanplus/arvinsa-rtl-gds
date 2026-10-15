---
name: macro-qualification
description: 選定、自建、收到或更換 hard macro（SRAM、IP、OpenRAM 自產、先前 harden 的區塊）時，交給 flow 之前的檢查（`CLAUDE.md` 規則 12）。症狀：`check_macro_views` FAIL（`internal_power ... outside (0, 1000]`、`LEF SIZE ... != GDS box`、`signal pins differ from the LEF`、`LEF DATABASE MICRONS 2000 > the tech LEF's 1000`、`LEF has no FOREIGN`、`GDS pin text(s) outside the pin's LEF RECTs`、`metal outside the LEF OBS and pins`）；OpenROAD 報 `ODB-0292 LEF data from ... is discarded due to errors`；最終 GDS 的 macro 是空的、`design__xor_difference__count` 幾百萬而 KLayout 印 `All LEF cells have matching GDS cells`；換 macro 後 checker 的比對對象是空的（KeyError `'sram0'`）。涵蓋 view QA（`make macro-views`、`make neg-macro-views`）、選定前在整個操作範圍做 SPICE 讀寫與平台 DRC deck 的 go／no-go、.lib 輸出的等效驅動電阻要在標準元件範圍內、換 macro 時舊檢查逐條重跑。接進 flow 看 hard-macro-integration。Use for qualifying a hard macro before the flow uses it (view QA, go/no-go, .lib drive strength, replacement checklist).
---

# Hard macro 交給 flow 之前的檢查

2026-10-15 從 `hard-macro-integration` 拆出（ADR-0021 決定 5）。`CLAUDE.md` 規則 12 的 view QA 是這裡的規則 1。通過之後怎麼接進 flow（`MACROS`、view 來源、tie-off、電源、macro clock）看 `hard-macro-integration`；SRAM 的 SPICE 量測看 `openram-macro-characterization`；OpenRAM 自產 macro 的產生看 `openram-macro-generation`。本 repo 實例：`scripts/check_macro_views.py`、`scripts/check_macro_gds.py`、`pnr/soc_top/check_inputs.py`、`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/`（ADR-0018）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`（ADR-0010）。

## 規則（已驗證）

1. **macro 的 view QA：自建或收到 macro，先檢查每個交付檔的內容，不只是檔案在不在**（原 `hard-macro-integration` 第 0 項；使用者 2026-10-09：不限 OpenRAM，任何產生或取得 macro 的方式都要做；本 repo `scripts/check_macro_views.py`）。
   - 為什麼：產生工具自己的檢查（DRC、LVS、檔案齊全）不看 LEF、.lib、Verilog 模型的內容；LVS 只把 GDS 和 SPICE 網表綁在一起。2026-10-08 OpenRAM dev 產生的 2 KB SRAM，DRC／LVS 都過，.lib 的 internal_power 全部是 1.036316e+11（預建 macro 13.8），IR drop 分析會直接讀進去（ADR-0018）。
   - 查什麼：LEF `MACRO`／.lib `cell`／Verilog `module`／SPICE `.SUBCKT` 同名；四者的訊號腳位（bus 展開）與方向相同，電源腳位集合相同；.lib 每個數字是有限值，internal_power（power 表的**每一個**數字）、腳位電容在合理範圍，延遲不為負，`area` = LEF 長 × 寬；LEF `SIZE` = GDS 頂層 cell 的外框且在原點。
   - **LEF 與 GDS 的幾何**（Phase 6 獨立審查 H1、H2 後加，`pinpos`、`obs`）：每支 LEF 腳位在 GDS 頂層 cell 有同名文字，而且文字落在該腳位同一層的 LEF RECT 裡；每一層繞線金屬（met1–met5）攤平後，在 LEF 的 OBS 與腳位 RECT 之外的部分，只能是連著某支腳位 RECT 的延伸（OpenRAM 的腳位金屬會從 0.38 µm 的 RECT 往內再走 0.6 µm 才接到 OBS）。為什麼：LVS 只透過 LEF 看 macro（black box），LEF 兩支腳位的 RECT 對調時，名稱、方向、外框全都對，flow 的 DRC、LVS、EQY 也都看不到，矽上兩個 bit 就接反了；LEF 少了 OBS，router 可能從 macro 上方穿過它自己的金屬。KLayout 讀 GDS（`scripts/gds_view.py`，2 KB SRAM 約 7 秒）。
   - 症狀：`check_macro_views: FAIL - <name>: <原因>`（例如 `internal_power 1.036316e+11 outside (0, 1000]`、`LEF SIZE ... != GDS box`、`Verilog signal pins differ from the LEF`）。
   - 怎麼發現：產生 macro 的 target 一定要接這一步（本 repo `make openram-macro` 的第二步，結果在 `runs/openram/<name>/views.json`）；整合中的 macro 用 `make macro-views`。
   - 繞過：QA FAIL 的 view 不能直接交給 flow；修正或替換該 view（例如 .lib 的 power 用 `ip/sram/openram/lib_template.py`），列為已知問題並記錄做法，再用替換後的 view 重跑 QA 到 PASS。
   - 防復發：`make neg-macro-views`（在 `make regress` 裡；案例表在 `scripts/neg_macro_views.py` 開頭）；正常對照用一顆一致的小 macro，另外預建 sky130 2 KB SRAM 的 PDK 原檔與 repo 實際使用的 view 都 PASS。harden 前的 `check_inputs.py` 每次都跑這一步（`macro_views` 列，Phase 6 步驟 4a 接上），並核對 macro 產生器輸出的 sha256（`macro_source`，包括產生器的 TT .lib）與 .lib 範本確實是 `lib_template.py` 的產物（`lib_template`），negative test P63、P66、P71（真 SRAM 的 LEF 腳位 RECT 對調）、P72（LEF 沒有 OBS）、P73、P74。
   - LEF 的資料庫單位（OpenROAD 的行為，Phase 6 已驗證）：
     - 症狀：OpenROAD.Floorplan 失敗，`[ODB-0292] LEF data from <macro>.lef is discarded due to errors`，前面一條 `[ODB-0205] The LEF UNITS DATABASE MICRON convert factor (2000) is greater than the database units per micron (1000) of the current technology`。OpenRAM dev 的 LEF 寫 `DATABASE MICRONS 2000`，sky130 tech LEF 是 1000；PDK 預建 macro 的 LEF 是 1000，所以 Phase 3–5 沒遇到。
     - 怎麼發現：view QA 的 `units` 檢查（`LEF DATABASE MICRONS 2000 > the tech LEF's 1000`，`--dbu` 給 tech 的值）；harden 時看 Floorplan step 的 log。
     - 繞過：產生 flow 用的 LEF 時改成 tech 的值（本 repo `gen_antenna_lef.py` 的 `tech_units()`）；改之前確認每個座標都在 1/tech 單位的格點上，不在就 FAIL（改了會移動圖形）。OpenRAM 的 sky130 LEF 全部在 0.005 µm 製造格點上，轉換無損。macro 產生後對原始 LEF 做 view QA 時用 `--dbu 2000` 並註明原因。
     - 防復發：`neg-macro-views` Q12（2000 必須 FAIL、1000 必須 PASS）；`check_inputs.py macro_views` 每次 harden 前檢查 flow 用的 LEF。
   - LEF 的 `FOREIGN`（LibreLane KLayout stream-out 的行為，Phase 6 已驗證）：
     - 症狀：harden 只在 signoff 報 `design__xor_difference__count` 幾百萬（Phase 6：5,690,757–5,691,003）；最終 GDS（KLayout 輸出）裡 macro cell 是空的，Magic 的 GDS 是完整的；KLayout 的 log 仍印 `All LEF cells have matching GDS cells`，flow 不報錯。同一份 GDS 上的 Magic DRC 在 macro 框內是 0 個違規、KLayout DRC 也空過。
     - 根因（已驗證：只重跑 `KLayout.StreamOut`，LEF 加 `FOREIGN` 後 169 個 cell 全部進去）：`stream_out.py` 先用 LEF 和 DEF 建出 macro cell、清空，再合併 macro 的 GDS；LEF 有 `FOREIGN` 時這個 cell 是 ghost cell，會被同名 GDS cell 取代；沒有時是普通 cell，GDS cell 照 `KLAYOUT_CONFLICT_RESOLUTION=RenameCell` 改名後沒被引用。缺 GDS 的檢查只看 ghost cell。OpenRAM dev 的 LEF 沒有 `FOREIGN`，PDK 預建 macro 的 LEF 有。
     - 怎麼發現：view QA 的 `foreign` 檢查（`LEF has no FOREIGN <top>`）；harden 後 `check_soc.py macro_gds`（最終 GDS 裡 macro 底下的 cell 與內容等於 macro 的 GDS，`scripts/check_macro_gds.py`；FAIL 訊息例：`<n> cell(s) of the macro missing below <cell> in the final GDS`）；XOR 只在 Magic 與 KLayout 結果不同時才抓得到。
     - 繞過：產生 flow 用的 LEF 時補 `FOREIGN <macro> ;`（`gen_antenna_lef.py add_foreign()`）；原始 LEF 的 view QA 用 `--no-foreign` 並註明。
     - 防復發：`neg-macro-views` Q13；`check_inputs.py macro_views`；`check_soc.py macro_gds` 與 negative test P67（最終 GDS 的 macro 被清空）、P68（macro 的一個 cell 內容不同）；`magic_drc` 要求框內違規至少是 macro 單獨的一半，P69。

## 提早檢查（流程回顧，ADR-0020，使用者決定）

2026-10-14 回顧 Phase 0–7（`docs/notes/flow_retro/`）後使用者決定加的三條。依據是本專案已發生的事件；時間與省下多少是從 commit 時間推算。

2. **選定 macro 之前先做 go／no-go：在晶片的整個操作範圍做 SPICE 讀寫，並用下線平台的 DRC deck 單獨檢查**（原 `hard-macro-integration` 第 8 項；提早檢查 B1；時間點在規則 1 之前、macro 寫進計畫之前；流程文件 4.3 第 0 項）。
   - 為什麼：本 repo 用的 PDK 預建 2 KB SRAM 在 ss −40°C、tt −40°C 與 ss 25°C 1.60 V 都讀成前一次的值（ADR-0010），網表從 Phase 0 就在 PDK 裡，計畫第一版也寫了它的矽量測只到 ≥1.7 V（`project-plan.md` §5.4），比 ss corner 的 1.60 V 高；卻到 Phase 3.5 特性化才發現，Phase 3.5–5 帶著佔位 .lib，Phase 6 改自產並修讀取電路，特性化與整合做了兩次。拿掉 ss −40°C corner 救不了它，因為室溫 ss 25°C 1.60 V 也錯（回顧 README「使用者的例子」）。
   - 做什麼：先拿到 macro 已驗證的範圍（矽量測條件、特性化 corner、.lib 是實測還是解析模型），和晶片的操作範圍比（`signoff-criteria`「提早檢查」A1）。沒涵蓋的部分用廠商或 PDK 附的電晶體級網表模擬：格點包含每個 STA PVT、corner 之間的溫度（例如 25°C）、最低供電（平台規格的下限與 ss corner 的電壓）；序列要有連續兩次讀到相反的值、寫入後馬上讀，未用的 port 照 SoC 的接法；記下輸出在 clock 兩個邊緣之後的波形（決定 .lib 要哪些時序弧）。量法與陷阱看 `openram-macro-characterization` 規則 4、13。另外用下線平台的 DRC deck 單獨跑 macro（`tapeout-precheck-caravel` 規則 2）：precheck 的 deck 對任何 OpenRAM bitcell 報 `MR_licon.SP.6`、`MR_mcon.CON.10`，deck 在 2026-05 就改了，本 repo 到 Phase 7 才看到（ADR-0019 決定 5）。
   - 通過條件：每個格點都讀寫正確；平台 deck 的違規都有根因與比對基準。失敗時先列選項（換 macro、自產並修電路、縮規格）由使用者決定並記 ADR，再整合；選了接受風險才用 `hard-macro-integration` 第 5 項的佔位 .lib。
   - 成本：回顧推算第一次約半天到一天（修剪網表每個 PVT 幾分鐘到幾十分鐘），之後同類 macro 1–2 小時。
   - 自動防護：沒有（是選擇前的模擬，結果寫進 ADR）。
3. **macro .lib 輸出的驅動能力要落在標準元件的範圍內**（原 `hard-macro-integration` 第 9 項；提早檢查 B3，view QA 的一部分）。
   - 為什麼：OpenROAD 把 .lib 延遲表對負載的斜率當成 driver 的強度。Phase 3.5 的 SRAM .lib 斜率等於 60–140 kΩ 的 driver，`repair_design` 跑 75 分鐘後 `failed with an unexpected error`，單步重跑 4 種 .lib 才找到原因（ADR-0010；`openram-macro-characterization` 規則 14）。
   - 做什麼：從每條輸出弧的延遲表算等效驅動電阻（延遲變化 ÷ 負載變化），和同一份 library 標準元件的範圍比；延遲表隨負載要單調不減。
   - 通過條件：落在範圍內；植入一份斜率過大的 .lib 必須 FAIL。
   - 自動防護：目前沒有（`check_macro_views.py` 沒有這項），下一個專案開始時加進 view QA，並加一個植入錯誤的 Q 案例。換上任何新 macro .lib 時，照舊先單步重跑 `RepairDesignPostGPL` 確認時間（`drv-timing-closure` 規則 10）。
4. **換 macro 時，舊 macro 做過的檢查逐條重跑，每支 checker 證明比對對象不是空的**（原 `hard-macro-integration` 第 10 項；提早檢查 B4）。
    - 為什麼：Phase 0 就確認過預建 SRAM 的 LEF 有 `FOREIGN`（`docs/phase_exit/phase0.md`），Phase 6 換自產 macro 時沒重查，最終 GDS 的 SRAM 是空的，第一輪 harden 白跑（規則 1「LEF 的 FOREIGN」）；EQY 的網表解析只認 `sky130_` 開頭的 cell，SRAM 的 clock 檢查在 Phase 6 步驟 4a–4c 被略過照樣 PASS（經驗紀錄 2026-10-10）。
    - 做什麼：把之前對舊 macro 做過的每一項檢查（不論在哪個 Phase、是不是 checker）列成清單，對新 macro 逐條重跑並附結果；每支會碰到 macro 的 checker（EQY、DRC 位置比對、最終 GDS 比對、STA 讀的 .lib）在第一次 positive run 印出讀到的 macro instance 與內容摘要；macro 換名稱時，搜尋用舊名稱或名稱前綴認東西的腳本。
    - 通過條件：清單逐條 PASS；每支 checker 的 positive run 都印出 macro instance。
    - 自動防護：部分已有（`formal-equivalence-eqy` 規則 5、`check_soc.py macro_gds`、`magic_drc` 的框內違規下限）；「舊檢查逐條重跑」本身沒有自動防護，下一個專案開始時做成 checker。

## negative test

view 內容錯誤 → `scripts/check_macro_views.py`（`make neg-macro-views`，案例表在 `scripts/neg_macro_views.py` 開頭）；P63 產生器輸出被改 → `check_inputs.py macro_source`；P66 LEF SIZE → `check_inputs.py macro_views`；P71、P72 真 SRAM 的 LEF 腳位對調、沒有 OBS → `macro_views`；P73 .lib 範本不是 `lib_template.py` 的產物 → `check_inputs.py lib_template`；P74 產生器的 TT .lib 被改 → `macro_source`；P67、P68、P75、P76 最終 GDS 的 macro 被清空或內容不同（含標籤互換、同外框的圖形）→ `check_soc.py macro_gds`；P69 框內 DRC 違規太少（macro 不在被檢查的 GDS）→ `magic_drc`。案例表在 `pnr/soc_top/neg_pnr.py`。

## 用完後

新 macro 的特殊情況寫進「經驗紀錄」；同一類問題第二次出現就搬進規則。新的 view 錯誤類型要在 `scripts/neg_macro_views.py` 加一個植入錯誤的案例（`CLAUDE.md` 規則 12）。

## 經驗紀錄

2026-10-15 從 `hard-macro-integration` 的經驗紀錄搬來（ADR-0021 決定 5）。

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-10 | Phase 6 步驟 4a，只跑到 PDN 的試跑 `runs/p6_fp_pico` | `[ODB-0205] The LEF UNITS DATABASE MICRON convert factor (2000) is greater than the database units per micron (1000)`、`[ODB-0292] LEF data from .../arv_sram_2kbyte_1rw1r_32x512_8.lef is discarded due to errors`，Floorplan 失敗 | 已驗證（OpenRAM LEF `DATABASE MICRONS 2000`，1178 個座標都在 0.005 µm 格點；改成 1000 後同一個試跑 rc=0） | 清單第 0 項（現在本 skill 規則 1）「LEF 的資料庫單位」；`gen_antenna_lef.py tech_units()`、`check_macro_views.py` 單位檢查、Q12 | `runs/p6_fp_pico.console`、`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/arv_sram_2kbyte_1rw1r_32x512_8.lef` |
| 2026-10-10 | Phase 6 步驟 4b 第一輪 harden（`221822a`，兩個 CPU） | `design__xor_difference__count` 5,691,003／5,690,757（上限 0），其他 signoff 上限都 PASS；`soc_top.gds` 的 SRAM cell 沒有子 cell，Magic 的 GDS 有 168 個；`magic_drc` 框內 0 個違規仍 PASS | 已驗證（單步重跑 `KLayout.StreamOut`，LEF 加 `FOREIGN` 後完整；讀 `stream_out.py`） | 清單第 0 項（現在本 skill 規則 1）「LEF 的 FOREIGN」；`add_foreign()`、view QA、`check_macro_gds.py`（步驟 3d）、`magic_drc` 下限；Q13、P67–P69；兩個 CPU 重新 harden | `runs/p6_4b_harden_*.log`，commit `3ceca55`（run 目錄 `runs/soc_top.prev` 已被之後的 harden 覆蓋；同一情況由 P67、P69 重現） |
| 2026-10-10 | Phase 6 step 4c（`940e395`） | 換成自產 macro `arv_sram_2kbyte_1rw1r_32x512_8` 後，`neg-eqy-soc`／`neg-gl-soc` 以 `KeyError: 'sram0'` 中止；`eqy-soc` 的 SRAM clock 檢查從 step 4a 起被略過 | 已驗證：`signoff/eqy/run_eqy.py` 的網表解析只認 `sky130_` 開頭的 cell | 解析改成任何 cell 名稱，並要求 config `MACROS` 的 instance 被解析到（`formal-equivalence-eqy` 規則 5）。換 macro（尤其換名稱）時，搜尋 repo 中用 cell 名稱前綴或舊 macro 名稱認東西的腳本（例如 `grep -rn "sky130_" signoff dv pnr scripts`，再看每一處是不是在認 cell 種類） | `runs/p6_4c_neg-eqy-soc_*.log` |
| 2026-10-11 | Phase 6 獨立審查（找 checker 漏洞的 agent，12 個植入實驗） | view QA 對「LEF 兩支腳位 RECT 對調」「LEF 沒有 OBS」「.lib 範本電容 / 10 並重新產生 char .lib」「power 表第二個數字 1e11」都 PASS；`check_macro_gds.py` 對標籤互換、同外框的多邊形、兩個框反向各移 10 nm 都 PASS | 已驗證（植入實驗；我重跑 H1 確認）。LVS 把 macro 當 black box，LEF 與 GDS 的幾何沒有別處在比；指紋只算圖形數與座標加權和 | `check_macro_views` 加 `pinpos`、`obs`，power 表讀全部數字；`check_inputs` 加 `lib_template`、`macro_source` 含 TT .lib；`gds_cells.py` 改成每個圖形完整描述的雜湊；Q14–Q20、P71–P76。交付的 SRAM 125 支腳位逐支比對一致，結果不是假 PASS | `docs/phase_exit/phase6.md`「獨立審查」、ADR-0018 決定 19 |
