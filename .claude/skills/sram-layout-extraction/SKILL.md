---
name: sram-layout-extraction
description: 從 SRAM（或其他 macro）的 GDS 萃取寄生、模擬萃取網表時使用（Magic `extract`、`ext2spice`，ngspice）。症狀：Magic 沒設 `PDK_ROOT` 時 exit 0 卻沒有輸出；萃取網表的直流工作點報 `singular matrix`（儲存節點、`VSUBS` 只接電容）；暫態在第一個 clock 邊緣報 `Timestep too small`（`ext2spice lvs` 階層式輸出的負值修正電容讓節點總電容為負，`extract_sram.py` 報 `nodes with negative total capacitance`）；平面網表 ngspice 解析很久還沒開始模擬；萃取網表在 ss 用短週期讀取 FAIL（讀出值在上升緣後才到）；只換 bitcell 估寄生偏低、出現假的寫入失敗。涵蓋平面輸出 `ext2spice hierarchy off` 與平面修剪、`rshunt`、寄生倍數用整顆萃取量到的值（不用假設的 × 1.6）、特性化之前先試萃取。特性化本身看 openram-macro-characterization。Use for Magic parasitic extraction of SRAM macros and simulating the extracted netlist with ngspice (sky130).
---

# SRAM 的版圖萃取與萃取網表的模擬

2026-10-15 從 `openram-macro-characterization` 拆出（ADR-0021 決定 5）。SPICE 量測與 .lib 看 `openram-macro-characterization`（修剪、步長、ngspice 設定都在那裡）；用 OpenRAM 產生 macro 看 `openram-macro-generation`。本 repo 實例：`ip/sram/char/extract_sram.py`、`ip/sram/char/sramchar.py`（`trim_extracted`）、ADR-0010、ADR-0018 決定 20、`docs/notes/openram_phase6_bringup.md` 步驟 5d。

## 規則（已驗證）

1. **從 GDS 萃取寄生（Magic）**（原 `openram-macro-characterization` 規則 8）：
   - 沒設 `PDK_ROOT` 時 magicrc 找不到 tech 檔，Magic 仍然 exit 0 而且沒有輸出；腳本要檢查輸出檔存在，不能只看 exit code。
   - 2 KB macro 的電容萃取（`extract do capacitance`、`extract do coupling`、`ext2spice cthresh 0.01`）花 26 分鐘、1.4 GB 記憶體，產生 7.9 萬顆電容；bitcell 的特殊元件都能正確辨識。
2. **Magic 萃取的 SRAM 網表不能直接模擬**（原 `openram-macro-characterization` 規則 10；sky130 2 KB，Magic 8.3.623，`ext2spice lvs` + `cthresh 0.01`）：
    - 每顆 bitcell 的儲存節點被當成 port 一路傳到最上層，在最上層是一般網路，並有電容接到基板網路 `<...>/VSUBS`；
    - VSUBS 沒有接任何元件（只接電容），直流工作點會 singular；
    - 修剪掉的 bitcell，其儲存節點也變成浮接；
    - 做法：在最上層把 VSUBS 與被修剪 cell 的儲存節點都改名成地（`sramchar.trim_extracted`）。改完之後仍有其他只接電容的金屬網路（例如 `control_logic_r_0/m2_2554_0#`），要加 `.options rshunt=1e12`。
    - **階層式輸出的負值修正電容**（Phase 6 試跑，2026-10-11；自產 2 KB，Magic 8.3.623，open_pdks `8afc834`）：
      - 症狀：上面兩項處理完之後，暫態在第一個 clock 邊緣報 `Timestep too small`（例：`time = 2.19037e-09, timestep = 1.25e-22: trouble with node "vwm2#branch"`，出事的節點每次不同）；不萃取 coupling 時，直流工作點在子 cell 內部節點報 `singular matrix`。
      - 根因（已驗證，前後比較）：`ext2spice lvs` 是階層式輸出，Magic 在上層 subckt 放負值電容，修正 cell 重疊處重複算的電容。攤平後部分節點的總電容是負的：2 KB 有 263 個（`bank_0/port_data_0/bl_127` −108 fF），修剪後 995 個。修正電容寫在子 cell 的非 port 節點時，在 ngspice 是另一個只接電容的浮接節點。同一份網表拿掉負值電容就能跑；`ext2spice hierarchy off`（平面輸出）沒有負值電容，可以直接模擬。
      - 怎麼發現：`ip/sram/char/extract_sram.py` 輸出網表後攤平計算每個節點的總電容，有負值就 FAIL，訊息是 `nodes with negative total capacitance`，並印出最負的節點（`negative_nodes()`）。
      - 繞過：用平面輸出，再做平面修剪；拿掉負值電容只能用來確認根因，因為剩下的電容偏大。平面網表的 ngspice 解析很慢：96654 顆元件解析 13 分鐘都還沒開始模擬，要先拿掉被修剪 column 上只接 drain 的電晶體（剩 34254 顆，讀檔加工作點約 11 分鐘、暫態約 21 分鐘、2.3 GB）。
      - 防復發：`make neg-char` N22（上層修正電容大於子 cell 電容、修正電容寫在子 cell 的內部節點，兩種都要被抓到；只部分修正的正常網表要 PASS）。萃取與 neg-char 都不在 `make regress` 裡，換 Magic 版本或改萃取設定時要手動跑。
    - **寄生的影響要用整顆版圖萃取估，不能只換 bitcell**（Phase 6 試跑，2026-10-11，已驗證）：sky130 自產 2 KB 只換 bitcell 估讀出穩定時間 +48%，整顆平面萃取是 2.0 倍（tt 25°C、ss −40°C、ss 100°C 都在 2.00–2.03 倍）；只換 bitcell 還出現假的寫入失敗，整顆萃取時寫入都正確。dout 的 transition 也要看整顆萃取：只換 bitcell 得到 0.23–0.28 ns，整顆萃取和電路圖一致（ss 100°C 約 2.1 ns）。這顆設計的數字在 ADR-0018 決定 20。
    - **萃取網表的讀取檢查，低電位要不小於 .lib 的 `min_pulse_width`**：sky130 自產 2 KB 在 ss −40°C 用 20 ns 週期（低電位 10 ns，.lib 下限 12 ns）時，7 次讀取都判 FAIL；讀出值在下一個上升緣後才到 0.8 VDD，看起來像讀取做不完。改用 SoC 實際週期 44 ns 後讀對，穩定時間 10.9 ns。看到「上升緣後才出現」時，先拉長週期分辨是變慢還是讀不出來，不要直接判功能錯。

### 提早檢查（流程回顧，ADR-0020，使用者決定）

3. **特性化之前先試版圖萃取；寄生的倍數用萃取量到的值，不用假設**（原 `openram-macro-characterization` 規則 29；提早檢查 B2，流程文件 4.3 第 5 項）。
    - 為什麼：Phase 3.5 用「萃取 bitcell 試驗 +45–48%」訂了 × 1.6，Phase 6 最後才做整顆萃取，實際是 2.0 倍（規則 2）；dout0 transition .lib 寫 0.5 ns、萃取量到 1.4–2.2 ns。到那時重產 .lib 要再 6–8 小時，使用者選擇不改 .lib、寫進已知限制（ADR-0018 決定 20 與已知限制）；Phase 7 wrapper 把 transition 換成實際值後，最差 setup 從 +0.548 剩 +0.151 ns（回顧 `docs/notes/flow_retro/retro_p6_7.md` #15）。萃取試跑約 3 小時。
    - 做什麼：取得或產生 macro、通過 view QA 之後，先從 GDS 萃取整顆 macro 的寄生（平面輸出 `ext2spice hierarchy off`、檢查沒有總電容為負的節點，規則 2），在 tt、最慢的 ss、最低溫的 ss 做讀寫。能模擬就直接用萃取網表特性化；只能用電路圖網表時，倍數用萃取網表和電路圖在同一個量測點的比值。
    - 通過條件：萃取網表在上述 PVT 讀寫正確；.lib 的延遲與 transition 不低於萃取值。
    - 自動防護：沒有（.lib 與萃取值的比較目前是人工；可以加進 `check_char_lib.py`，下一個專案開始時做）。
    - .lib 裡其他沒把握的假設（例如 macro 輸出的 transition）偏樂觀已出現兩次（Phase 3.5 經驗紀錄 2026-10-05 的 what-if、Phase 7 的上面那一例）：先用只重跑 STA 的 what-if 量它對 slack 的影響，再決定要不要重新特性化。

## 待補

- 用萃取網表重新特性化（ff、tt −40°C 也要跑）還沒做：Phase 6 用整顆平面萃取量到讀出穩定時間是電路圖的 2.0 倍（規則 2），.lib 仍用 × 1.6 加下限（原 `openram-macro-characterization`「待補」；ADR-0018 決定 20 與已知限制）。

## 用完後

1. 新的現象加進「經驗紀錄」，根因標明已驗證／推測。
2. 換 Magic 版本或改萃取設定時，手動跑萃取與 `make neg-char`（都不在 `make regress` 裡，規則 2）。

## 經驗紀錄

2026-10-15 從 `openram-macro-characterization` 的經驗紀錄搬來（ADR-0021 決定 5）。

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | Phase 3.5 寄生萃取 | 第一次萃取 5 秒就結束、exit 0、沒有輸出 | 已驗證：沒設 `PDK_ROOT` | 規則 1（原規則 8） | 同上 |
| 2026-10-05 | Phase 3.5 萃取網表 | 修剪後 singular matrix（VSUBS、被修剪 cell 的儲存節點）；處理後、加 rshunt，暫態仍在第一個 clock 邊緣報 `Timestep too small`（出事的節點每次不同） | 前半已驗證（規則 2（原規則 10））；後半未解決 | 萃取網表暫不用於特性化 | 同上 |
| 2026-10-05 | Phase 3.5 寄生估計 | 電路圖網表換上 Magic 萃取的 bitcell（含 cell 內寄生與接面面積）後，TT 寫入第 0 列第 0 行失敗：預充電只到 1.68 V，寫入時兩條 bitline 同時偏低，儲存節點停在約 0.4 V 後倒向錯的一邊 | 未解決：可能是真的餘量問題，也可能是只換 bitcell、周邊沒有寄生造成的不一致 | 使用者 2026-10-05 決定：記為下線前風險，Phase 6 用 OpenRAM 環境確認（ADR-0010 已知限制 4） | 同上 |
| 2026-10-11 | Phase 6 步驟 5d，自產 2 KB 版圖萃取試跑（Magic 8.3.623，`8afc834`） | 階層式萃取：暫態 `Timestep too small; time = 2.19037e-09 ... trouble with node "vwm2#branch"`；平面萃取：tt 讀對、穩定時間 2.0 倍；ss −40°C 20 ns 週期 7 次讀取都判 FAIL | 已驗證：負值修正電容讓 263 個節點總電容為負（拿掉後能跑、平面輸出能跑）；ss −40°C 是變慢，44 ns 週期讀對（10.88 ns） | 規則 2（原規則 10） 三條；`extract_sram.py` 負值電容 checker、`neg-char` N22；.lib 不改，寫進 ADR-0018 已知限制（決定 20） | `runs/p6_extract_trial/`；`docs/notes/openram_phase6_bringup.md` 步驟 5d |
