---
name: openram-macro-characterization
description: SRAM macro（OpenRAM 產生的預建 macro 或自產 macro）的時序要用 SPICE 實測、產生多 corner 的 .lib 時使用：判斷廠商 .lib 是不是解析模型、macro 在低溫讀出前一次的值（sense amp 沒有預充電、column mux 只有 NMOS）與不能動的 corner 怎麼給佔位 .lib、換上新 .lib 後 repair_design 跑很久或異常結束（延遲表的負載斜率）、用 ngspice 量 clk→dout 延遲與 dout 在上升緣後被拉回的時間、setup/hold、最小週期與 pulse width、網表修剪與模擬步長怎麼驗證、從 GDS 萃取寄生電容（Magic）、OpenRAM 自己特性化的缺陷、量測結果怎麼寫成 .lib 並用植入錯誤證明量得對，以及 ngspice 讀大網表很慢、bus 節點名稱報 bad v() syntax、萃取網表報 singular matrix 或 Timestep too small 這類問題。macro 怎麼放進設計看 hard-macro-integration，餘量怎麼定看 signoff-criteria。Use for SPICE characterization of SRAM macros (ngspice + sky130), per-corner Liberty generation, netlist trimming, parasitic extraction and OpenRAM characterizer pitfalls.
---

# SRAM macro 的 SPICE 特性化與 .lib

macro 整合清單看 `hard-macro-integration`；量到的數字要加多少餘量看 `signoff-criteria`；corner 清單看 `multicorner-sta`。本 repo 實例：ADR-0010、`ip/sram/char/`（腳本與方法）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`（結果）。

名詞：
- **特性化（characterization）**：用電路模擬量出 macro 的延遲、setup/hold、最小週期等，寫成 STA 讀的 Liberty（.lib）。
- **解析模型（analytical model）**：OpenRAM 不跑 SPICE、用公式（Elmore RC 估算）算出的 .lib。
- **修剪（trim）**：模擬時只保留記憶體陣列的第一／最後一列與第一／最後一行，其他 bitcell 拿掉；被量測的 bit 放在保留的最後一列、最後一行，所以它那條 bitline 與 wordline 的負載完整。

## 規則（已驗證）

1. **先判斷廠商 .lib 是不是 SPICE 量的**。OpenRAM 解析模型的特徵：
   - macro 的產生 log 寫 `Analytical model enabled`、`Characterization is disabled`；
   - 延遲表每一列相同（不隨 input slew 變）；
   - `minimum_period` = 最大延遲 × 2 × 1.85（OpenRAM `compiler/characterizer/elmore.py`）。
   sky130 PDK 內附 `libs.ref/sky130_sram_macros/lib/` 的全部 .lib（含 `sram_1rw1r_32_256_8_sky130` 的 SS／FF 檔）都是這種，最小週期 0.119–1.956 ns，不可用於 signoff。
2. **量 macro 隨附的網表**（`libs.ref/sky130_sram_macros/spice/`，與 GDS 同一顆電路），不要用 OpenRAM 重新產生的電路代替（OpenRAM 版本不同，電路可能不同）。先確認網表自足：bitcell 等 subckt 都有定義，用到的元件都在 PDK 模型裡。sky130 SRAM 用 `special_nfet_latch`、`special_pfet_latch`、`special_nfet_01v8`，它們隨 corner 變的參數在 `libs.tech/ngspice/corners/<c>/specialized_cells.spice`，要用 `.lib sky130.lib.spice <corner>` 整段載入。
3. **OpenRAM 自己的 SPICE 特性化（`-c`）不能直接當 signoff 依據**（VLSIDA/OpenRAM `stable` 的 `compiler/characterizer/`）：
   - setup/hold 只模擬輸入端那顆 DFF，沒算 macro 內部 clock buffer；只在第一個 corner 量，其他 corner 沿用；clock 的 slew 沒有施加。
   - `cell_rise`／`rise_transition` 用 fall 的值覆蓋（`delay.alter_lh_char_data`）。
   - `min_pulse_width` 直接取 `min_period / 2`。
   - 預設不含走線 RC（`use_pex=False`）；不測兩個 port 同時存取。
4. **ngspice＋sky130 的設定與速度**：
   - 把 PDK 的 `libs.tech/ngspice/spinit` 複製成工作目錄的 `.spiceinit`（`ngbehavior=hsa`、KLU）。
   - ngspice-47 讀 2 KB macro 的完整網表（約 15 萬顆 MOSFET）時，光是解析元件（`INP2M`）就超過 35 分鐘還沒開始模擬。修剪後（bitcell 16384 → 508）讀檔加模擬 440 ns 共 7 分鐘。
   - 修剪的結果要和完整網表在同一個量測點比對一次再採用。
5. **`.tran` 的 TSTEP 會壓住最大步長**：`.tran 10p` 跑 33 分鐘，`.tran 100p` 跑 7 分鐘，延遲差 1.8%（TT 2.348 vs 2.305 ns）。換步長要用小步長的結果驗證一次，並把誤差記下來算進餘量。
6. **ngspice 控制語言的兩個陷阱**：
   - 節點名稱有 `[ ]`（bus）時，`wrdata v(dout0[31])` 報 `bad v() syntax`（`[ ]` 被當成向量索引）；用 `E` 電壓源接到沒有括號的節點名稱再輸出。
   - `meas tran ... TARG ... FALL=1` 從 t=0 起算，不是從觸發點之後；要加 `TD=<觸發時間>`。
7. **OpenRAM SRAM 的 dout 在每個有效週期（`csb=0`）的上升緣後約 1 ns 就被拉回 0**，讀 1 時要到下降緣之後才升上來（sky130 2 KB、TT：上升緣後 1.05–1.29 ns 拉低，下降緣後 2.2–2.3 ns 讀出 1）。
   - 廠商 .lib 只有 `falling_edge` 一條弧，STA 以為資料保持到下一個下降緣；接收端 flop 的 clock 比 macro 的 clock 晚到約 1 ns 就會抓錯，STA 卻不會報。
   - .lib 要加一條 `rising_edge` 弧，最小延遲取上升緣到 dout 開始變化的時間，讓 STA 對接收端做 hold 檢查。
   - 行為模型的 `T_HOLD`（上升緣後 1 ns 把 dout 設成 X）模擬的就是這件事。
8. **從 GDS 萃取寄生（Magic）**：
   - 沒設 `PDK_ROOT` 時 magicrc 找不到 tech 檔，Magic 仍然 exit 0 而且沒有輸出；腳本要檢查輸出檔存在，不能只看 exit code。
   - 2 KB macro 的電容萃取（`extract do capacitance`、`extract do coupling`、`ext2spice cthresh 0.01`）花 26 分鐘、1.4 GB 記憶體，產生 7.9 萬顆電容；bitcell 的特殊元件都能正確辨識。

9. **setup/hold 要在整顆 macro 上量，不能只量輸入那顆 DFF**：macro 內部的 clock buffer 讓 DFF 晚一點才抓資料，所以 pin 上的 setup 變小（可為負）、hold 變大。sky130 2 KB、TT：setup −0.16～−0.22 ns、hold +0.20～+0.24 ns；PDK 解析模型（OpenRAM 只量 DFF）寫 setup 0.103、hold −0.056，hold 少算約 0.3 ns。量法：在測試週期把一組輸入的轉態時間往前或往後移，用寫入再讀回的資料判斷新值或舊值，二分搜尋（`ip/sram/char/characterize.py` 的 lanes）。
10. **Magic 萃取的 SRAM 網表不能直接模擬**（sky130 2 KB，Magic 8.3.623，`ext2spice lvs` + `cthresh 0.01`）：
    - 每顆 bitcell 的儲存節點被當成 port 一路傳到最上層，在最上層是一般網路，並有電容接到基板網路 `<...>/VSUBS`；
    - VSUBS 沒有接任何元件（只接電容），直流工作點會 singular；
    - 修剪掉的 bitcell，其儲存節點也變成浮接；
    - 做法：在最上層把 VSUBS 與被修剪 cell 的儲存節點都改名成地（`sramchar.trim_extracted`）。改完之後仍有其他只接電容的金屬網路（例如 `control_logic_r_0/m2_2554_0#`），要加 `.options rshunt=1e12`。

11. **量測方法要先驗證誤差，再用植入錯誤證明腳本量得對**（sky130 2 KB，TT；`ip/sram/char/`）：
    - 誤差來源逐一比對：模擬步長（100 ps 對 10 ps）、修剪對完整網表、UIC 對直流工作點、延遲表只模擬十字 5 點時四角的推算。四項都要偏保守的方向，數字寫進 ADR。
    - 植入錯誤至少涵蓋：延遲變大（sense amp 加電容）→ 量到的延遲必須變大；bitcell 卡住 → 讀出檢查 FAIL；搜尋的「移動轉態時間」失效 → 必須報錯而不是給一個數字；網表數量、JSON 缺項、.lib 被手改 → FAIL／STALE（`make neg-char`）。
    - 植入的字串要先確認在檔案裡找得到、而且改到預期的次數；否則植入什麼都沒做，測不到要測的東西（N6 第一版：`--check` 判沒有過期，N6 FAIL，見經驗紀錄）。
12. **.lib 的時序弧要和實測行為對得上**：dout 在上升緣後會變化（規則 7），所以除了 `falling_edge` 弧還要 `rising_edge` 弧；接進 SoC 後要有 negative test 證明 STA 真的用到它（本 repo 的 P32：把它設成 0，hold 必須 FAIL）。
13. **每個 PVT 先證明讀寫正確，再量時序**（sky130 2 KB，PDK 網表；ADR-0010「ss −40°C 讀取失敗」）：
    - OpenRAM 的 sky130 sense amp（`sky130_fd_bd_sram__openram_sense_amp`）是沒有自己預充電的 latch，每次讀取前靠 bitline 經過只有 NMOS 的 column mux 把內部節點拉回去，最多只到 VDD − Vt。低溫或慢製程時拉不回來，連續兩次讀取的值不同時讀成前一次的值。
    - 實測（修剪網表，bit 0 的內部節點）：tt −40°C 1.60 V、ss −40°C 1.60–1.95 V 失敗；tt 25°C 1.80 V、ss 100°C 1.60 V、ff 正常。
    - 測試序列要有「連續讀取不同值」的讀取，否則看不到這個錯；每個 PVT 先跑一次，有錯就只記下錯的讀取（`read_fail`），不量時序。
    - 不能動的 PVT 仍要給 STA 一份 .lib（`hard-macro-integration` 第 5 項）：用同製程、能動的 PVT 的數字，hold 弧取所有 PVT 最早的值，檔頭寫明 PLACEHOLDER；並列為下線風險。
    - 修剪後只剩 2 顆 bitcell 的 bitline 電容太小，會讓這個錯更早出現（ss 25°C、60°C 只有這些 bit 錯），判斷時要看完整 bitline 的那幾個 bit。
14. **.lib 延遲表的負載斜率會被 OpenROAD 當成 driver 的強度**（sky130 2 KB；ADR-0010「延遲表為什麼不隨負載變化」）：
    - 讀出穩定時間是 dout 進入有效電壓範圍的時刻，不是 RC 延遲，會隨負載跳動（ss 100°C 5 → 20 fF 跳 1.3 ns）。直接寫進表裡，等於 60–140 kΩ 的 driver。
    - 這樣的表讓 `repair_design` 一直在輸出 net 上插 buffer：同一份輸入單步重跑，卡在第 9000 個 driver 之後；加大輸出 pin 的 `max_transition` 沒用；表在負載方向攤平後 52–98 秒完成。
    - 做法：每列（clock slew）取負載中的最大延遲、hold 弧取最小值，`max_capacitance` 設成特性化過的最大負載。產生 .lib 後先用單步重跑 `OpenROAD.RepairDesignPostGPL` 確認時間正常，再跑完整流程（`librelane-run-debug` 規則 3）。

## 待補

- 寄生：萃取網表無法收斂（經驗紀錄 2026-10-05），寄生的影響目前只有「換上萃取 bitcell」的估計；Phase 6 用 OpenRAM 環境再量。
- 其他 PVT 的步長與修剪誤差只在 TT 驗證過。
- Phase 6：在 x86 Linux 用 OpenRAM 自產 macro 時的規則。

## 不在這裡

- macro 的 MACROS 宣告、LEF、擺放 → `hard-macro-integration`
- 量到的數字要加多少餘量、怎麼對照矽量測 → `signoff-criteria`
- STA 用哪些 corner、每個 corner 的 hook → `multicorner-sta`

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | Phase 3.5 試跑（完整網表） | ngspice 35 分鐘以上停在 `INP2M` | 已驗證（`sample` 取樣）：逐顆 MOSFET 解析 sky130 模型 | 改用修剪網表（規則 4） | scratchpad 試跑，ADR-0010 |
| 2026-10-04 | Phase 3.5 試跑（修剪網表，TT） | `.tran 10p` 33 分鐘；`wrdata` 報 `bad v() syntax`；量下降延遲時抓到錯的邊緣 | 已驗證：TSTEP 壓住步長；`[ ]` 是向量索引；`FALL=1` 從 t=0 起算 | 規則 5、6 | 同上 |
| 2026-10-04 | Phase 3.5 試跑（修剪網表，TT） | dout 在上升緣後約 1 ns 拉回 0 | 已驗證（波形） | 規則 7：.lib 加 `rising_edge` 弧 | 同上 |
| 2026-10-04 | Phase 3.5 寄生萃取 | 第一次萃取 5 秒就結束、exit 0、沒有輸出 | 已驗證：沒設 `PDK_ROOT` | 規則 8 | 同上 |
| 2026-10-05 | Phase 3.5 驗證（TT，delay 序列） | 步長 100 ps 對 10 ps：穩定時間 +1.6%、開始變化 −0.7%；修剪對完整網表：讀出延遲 +2.0%；UIC 對直流工作點 +0.5%；十字 5 點推算四角 ≤ 1% | 已驗證：誤差都偏保守 | 記入 ADR-0010 的餘量 | `docs/phase_exit/phase3_5.md` |
| 2026-10-05 | Phase 3.5 TT 特性化 | setup 為負、hold 為正（規則 9）；最小 high 0.80 ns、low 2.80 ns、週期 5.62 ns | 已驗證（二分搜尋到 0.02–0.04 ns） | 規則 9 | `ip/sram/.../char/char.json` |
| 2026-10-05 | Phase 3.5 萃取網表 | 修剪後 singular matrix（VSUBS、被修剪 cell 的儲存節點）；處理後、加 rshunt，暫態仍在第一個 clock 邊緣報 `Timestep too small`（出事的節點每次不同） | 前半已驗證（規則 10）；後半未解決 | 萃取網表暫不用於特性化 | 同上 |
| 2026-10-05 | Phase 3.5 寄生估計 | 電路圖網表換上 Magic 萃取的 bitcell（含 cell 內寄生與接面面積）後，TT 寫入第 0 列第 0 行失敗：預充電只到 1.68 V，寫入時兩條 bitline 同時偏低，儲存節點停在約 0.4 V 後倒向錯的一邊 | 未解決：可能是真的餘量問題，也可能是只換 bitcell、周邊沒有寄生造成的不一致 | 使用者 2026-10-05 決定：記為下線前風險，Phase 6 用 OpenRAM 環境確認（ADR-0010 已知限制 4） | 同上 |
| 2026-10-05 | Phase 3.5 操作 | 重開特性化時用 `pkill -f 'ngspice -b deck.sp'`，把另一個也叫 `deck.sp` 的參考模擬一起砍掉 | 已驗證（操作失誤） | 停止程序用 PID 或父程序，不用檔名比對 | — |
| 2026-10-05 | Phase 3.5 特性化的植入錯誤 | N6（手改 .lib 必須被 `--check` 抓到）改成新餘量後，要替換的字串 `2.7500` 已不在 .lib 裡，植入什麼都沒做，`--check` 判沒有過期，N6 FAIL | 已驗證：餘量改變後 .lib 的數字跟著變 | 改成編輯 `timing_type : rising_edge;` 並檢查替換次數（規則 11）；N1–N6 6/6 PASS | `ip/sram/char/neg_char.py` |
| 2026-10-05 | Phase 3.5 ss −40°C 診斷 | 6 個各約 25 分鐘的模擬全部在最後報 `Error: no such vector xsram.xbank0.xport_data0.bl_0`，沒有波形 | 已驗證：子電路的 port 節點用上一層的網路名稱（`xsram.xbank0.bl_0_0`），只有子電路內部節點才是 `<instance>.<node>`；`wrdata` 到模擬結束才檢查名稱 | 長模擬前先跑一個 1 ns 的同一份 deck 確認每個探測節點都存在 | scratchpad `diag2.py` 的 `check_names` |
| 2026-10-05 | Phase 3.5 ss −40°C | 延遲模擬每次讀取都錯；tt −40°C、ss −40°C 到 1.95 V 都讀成前一次的值 | 已驗證（修剪網表，量 bit 0 的 column mux 輸出與 sense amp 內部節點）：sense amp 沒有預充電、column mux 只有 NMOS（規則 13）；完整網表在 ss −40°C 1.70 V 失敗的讀取與節點電壓相同（不是修剪造成） | 使用者決定：ss −40°C 用佔位 .lib，列為頭號下線風險，Phase 6 修正 | ADR-0010 |
| 2026-10-05 | Phase 3.5 harden-soc 第 1 次（`ccc536c`） | `OpenROAD.RepairDesignPostGPL` 75 分鐘後 `failed with an unexpected error`（Phase 4 同一步 44 秒） | 已驗證（單步重跑 4 種 .lib）：dout0 延遲表的負載斜率等於 60–140 kΩ 的 driver | 規則 14：負載方向取最大值 | ADR-0010 |
| 2026-10-05 | Phase 3.5 最終版圖的 what-if | dout0 transition 用 0.5 ns（使用者決定）；改成電路圖量到的值後，SRAM 半週期路徑 slack：ss −40°C 1.3 ns 時 +0.38 → +0.03，ss 100°C 3.15 ns 時 +0.92 → +0.17 | 已驗證（OpenSTA 只換 .lib） | 記入 ADR-0010 已知限制 5；macro 輸出 transition 這種沒有把握的假設，要用 what-if 量出它對 slack 的影響 | ADR-0010 |
