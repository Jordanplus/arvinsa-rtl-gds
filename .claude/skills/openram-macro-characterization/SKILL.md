---
name: openram-macro-characterization
description: SRAM macro（OpenRAM 產生的預建 macro 或自產 macro）的時序要用 SPICE 實測、產生多 corner 的 .lib 時使用：判斷廠商 .lib 是不是解析模型、macro 在低溫或 ss 低電壓（室溫也會）讀出前一次的值（sense amp 沒有預充電、column mux 只有 NMOS）與不能動的 corner 怎麼給佔位 .lib、換上新 .lib 後 repair_design 跑很久或異常結束（延遲表的負載斜率）、用 ngspice 量 clk→dout 延遲與 dout 在上升緣後被拉回的時間、setup/hold、最小週期與 pulse width（搜尋範圍不涵蓋真值時怎麼往外找）、網表修剪與模擬步長怎麼驗證、從 GDS 萃取寄生電容（Magic）、OpenRAM 自己特性化的缺陷、量測結果怎麼寫成 .lib 並用植入錯誤證明量得對（含不 import 產生器的獨立重算、在 .lib 採用值上的確認模擬、模擬快取與量測 JSON 的檢查），以及 ngspice 讀大網表很慢、bus 節點名稱報 bad v() syntax、萃取網表報 singular matrix 或 Timestep too small 這類問題。macro 怎麼放進設計看 hard-macro-integration，餘量怎麼定看 signoff-criteria。Use for SPICE characterization of SRAM macros (ngspice + sky130), per-corner Liberty generation, netlist trimming, parasitic extraction and OpenRAM characterizer pitfalls.
---

# SRAM macro 的 SPICE 特性化與 .lib

macro 整合清單看 `hard-macro-integration`；量到的數字要加多少餘量看 `signoff-criteria`；corner 清單看 `multicorner-sta`。本 repo 實例：ADR-0010、`ip/sram/char/`（腳本與方法）、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`（結果）。

名詞：
- **特性化（characterization）**：用電路模擬量出 macro 的延遲、setup/hold、最小週期等，寫成 STA 讀的 Liberty（.lib）。
- **解析模型（analytical model）**：OpenRAM 不跑 SPICE、用公式（Elmore RC 估算）算出的 .lib。
- **修剪（trim）**：模擬時只保留記憶體陣列的第一／最後一列，以及被量測的 bit（0、31）所在的全部行，其他 bitcell 拿掉（sky130 2 KB：每個 bit 4 行共 8 行，16384 → 1264 顆）；被量測的 bit 那條 bitline 與 wordline 的負載完整。

## 規則（已驗證）

1. **先判斷廠商 .lib 是不是 SPICE 量的**。OpenRAM 解析模型的特徵：
   - macro 的產生 log 寫 `Analytical model enabled`、`Characterization is disabled`；
   - 延遲表每一列相同（不隨 input slew 變）；
   - `minimum_period` = 最大延遲 × 2 × 1.85（OpenRAM `compiler/characterizer/elmore.py`）。
   sky130 PDK 內附 `libs.ref/sky130_sram_macros/lib/` 的全部 .lib（含 `sram_1rw1r_32_256_8_sky130` 的 SS／FF 檔）都是這種，最小週期 0.091–1.956 ns，不可用於 signoff。
2. **量 macro 隨附的網表**（`libs.ref/sky130_sram_macros/spice/`，與 GDS 同一顆電路），不要用 OpenRAM 重新產生的電路代替（OpenRAM 版本不同，電路可能不同）。先確認網表自足：bitcell 等 subckt 都有定義，用到的元件都在 PDK 模型裡。sky130 SRAM 用 `special_nfet_latch`、`special_pfet_latch`、`special_nfet_01v8`，它們隨 corner 變的參數在 `libs.tech/ngspice/corners/<c>/specialized_cells.spice`，要用 `.lib sky130.lib.spice <corner>` 整段載入。
3. **OpenRAM 自己的 SPICE 特性化（`-c`）不能直接當 signoff 依據**（VLSIDA/OpenRAM `stable` 的 `compiler/characterizer/`）：
   - setup/hold 只模擬輸入端那顆 DFF，沒算 macro 內部 clock buffer；只在第一個 corner 量，其他 corner 沿用；clock 的 slew 沒有施加。
   - `cell_rise`／`rise_transition` 用 fall 的值覆蓋（`delay.alter_lh_char_data`）。
   - `min_pulse_width` 直接取 `min_period / 2`。
   - 預設不含走線 RC（`use_pex=False`）；不測兩個 port 同時存取。
4. **ngspice＋sky130 的設定與速度**：
   - 把 PDK 的 `libs.tech/ngspice/spinit` 複製成工作目錄的 `.spiceinit`（`ngbehavior=hsa`、KLU）。
   - ngspice-47 讀 2 KB macro 的完整網表（約 15 萬顆 MOSFET）時，光是解析元件（`INP2M`）就超過 35 分鐘還沒開始模擬。早期試跑的修剪（bitcell 16384 → 508）讀檔加模擬 440 ns 共 7 分鐘；正式版保留 1264 顆（見名詞「修剪」）。
   - 修剪的結果要和完整網表在同一個量測點比對一次再採用。
5. **`.tran` 的 TSTEP 會壓住最大步長**：`.tran 10p` 跑 33 分鐘，`.tran 100p` 跑 7 分鐘，延遲差 1.8%（TT 2.348 vs 2.305 ns）。換步長要用小步長的結果驗證一次，並把誤差記下來算進餘量。
6. **ngspice 控制語言的兩個陷阱**：
   - 節點名稱有 `[ ]`（bus）時，`wrdata v(dout0[31])` 報 `bad v() syntax`（`[ ]` 被當成向量索引）；用 `E` 電壓源接到沒有括號的節點名稱再輸出。
   - `meas tran ... TARG ... FALL=1` 從 t=0 起算，不是從觸發點之後；要加 `TD=<觸發時間>`。
7. **OpenRAM SRAM 的 dout 在每個有效週期（`csb=0`）的上升緣後約 1 ns 就被拉回 0**，讀 1 時要到下降緣之後才升上來（sky130 2 KB、TT：上升緣後 1.02–1.29 ns 拉低，下降緣後 2.2–2.3 ns 讀出 1）。
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
    - 誤差來源逐一比對：模擬步長（100 ps 對 10 ps）、修剪對完整網表、UIC 對直流工作點、延遲表只模擬十字 5 點時四角的推算。四項都要偏保守的方向，數字寫進 ADR。方向要對 .lib 實際用的那個量逐一判斷：sky130 2 KB 的讀出穩定時間四項都偏保守，但 dout 開始變化（hold 弧）在延遲表兩個 5 fF 角偏晚 0.5–1.0%，是樂觀的方向，要由 hold 弧的係數（× 0.9）涵蓋（2026-10-05 獨立審查）。
    - 和完整網表或小步長比對時，記下比的是哪個量、用的是哪一版修剪網表；換了修剪範圍要重比。
    - 植入錯誤至少涵蓋：延遲變大（sense amp 加電容）→ 量到的延遲必須變大；bitcell 卡住 → 讀出檢查 FAIL；搜尋的「移動轉態時間」失效 → 必須報錯而不是給一個數字；網表數量、JSON 缺項、.lib 被手改 → FAIL／STALE（`make neg-char`）。
    - 植入的字串要先確認在檔案裡找得到、而且改到預期的次數；否則植入什麼都沒做，測不到要測的東西（N6 第一版：`--check` 判沒有過期，N6 FAIL，見經驗紀錄）。
12. **.lib 的時序弧要和實測行為對得上**：dout 在上升緣後會變化（規則 7），所以除了 `falling_edge` 弧還要 `rising_edge` 弧；接進 SoC 後要有 negative test 證明 STA 真的用到它（本 repo 的 P32：把它設成 0，hold 必須 FAIL）。
13. **每個 PVT 先證明讀寫正確，再量時序**（sky130 2 KB，PDK 網表；ADR-0010「ss −40°C 讀取失敗」）：
    - OpenRAM 的 sky130 sense amp（`sky130_fd_bd_sram__openram_sense_amp`）是沒有自己預充電的 latch，每次讀取前靠 bitline 經過只有 NMOS 的 column mux 把內部節點拉回去，最多只到 VDD − Vt。低溫或慢製程時拉不回來，連續兩次讀取的值不同時讀成前一次的值。
    - 實測（修剪網表，bit 0 的內部節點）：tt −40°C 1.60 V、ss −40°C 1.60–1.95 V、ss 25°C 1.60 V 失敗；ss 60°C 1.60 V、tt 25°C 1.80 V、ss 100°C 1.60 V、ff 正常。所以不只低溫：ss 低電壓在室溫也會失敗，界線在 25–60°C 之間。STA corner 只有 −40°C 與 100°C 時，中間溫度要另外模擬。
    - 整理多組條件的結果時，每一列都寫完整的製程、溫度、電壓。ss 25°C 1.60 V（全部 bit 錯）曾和 ss 25°C 1.80 V（只有修剪的 bit 錯）混在一起，漏列了室溫失敗（獨立審查發現）。
    - 測試序列要有「連續讀取不同值」的讀取，否則看不到這個錯；每個 PVT 先跑一次，有錯就只記下錯的讀取（`read_fail`），不量時序。
    - 不能動的 PVT 仍要給 STA 一份 .lib（`hard-macro-integration` 第 5 項）：用同製程、能動的 PVT 的數字，hold 弧取所有 PVT 最早的值，檔頭寫明 PLACEHOLDER；並列為下線風險。
    - 修剪後只剩 2 顆 bitcell 的 bitline 電容太小，會讓這個錯更早出現（ss 25°C 1.80 V、ss 60°C 1.60 V 只有這些 bit 錯），判斷時要看完整 bitline 的那幾個 bit。
14. **.lib 延遲表的負載斜率會被 OpenROAD 當成 driver 的強度**（sky130 2 KB；ADR-0010「延遲表為什麼不隨負載變化」）：
    - 讀出穩定時間是 dout 進入有效電壓範圍的時刻，不是 RC 延遲，會隨負載跳動（ss 100°C 5 → 20 fF 跳 1.3 ns）。直接寫進表裡，等於 60–140 kΩ 的 driver。
    - 這樣的表讓 `repair_design` 停不下來：同一份輸入單步重跑，卡在第 9000 個 driver 之後；加大輸出 pin 的 `max_transition` 沒用；延遲表與 hold 弧表一起在負載方向攤平後 52–98 秒完成（差別是機器負載；沒有分開測是哪一張表）。插在輸出 net 上是推論（`sample` 看不到 net 名稱）。
    - 做法：每列（clock slew）取負載中的最大延遲、hold 弧取最小值，`max_capacitance` 設成特性化過的最大負載。產生 .lib 後先用單步重跑 `OpenROAD.RepairDesignPostGPL` 確認時間正常，再跑完整流程（`librelane-run-debug` 規則 3）。
15. **搜尋範圍不涵蓋真值時，往外一次多測幾點，不要整個重新二分**（`ip/sram/char/characterize.py` 的 `bisect`）：
    - 其他 PVT 的搜尋以 tt 結果為中心，但 ss 的高、低電位時間與週期比 tt 大 1 ns 以上，ff 的低電位時間與週期小 1 ns 以上，都在範圍外。
    - 舊做法每往外移一次範圍就從頭二分 6 輪（每輪約 50 分鐘，約 5 小時）；ss 的最小週期若往外移 3 次，將近 20 小時。
    - 現在的做法：二分縮到解析度後，某一側（FAIL 或 PASS）還沒看到，就在那一側一次模擬 `EXTEND_POINTS`（2）個點、涵蓋一個初始寬度，最多 `MAX_EXTEND`（3）次，仍看不到就報錯；看到之後在最近的 FAIL 與 PASS 之間接著二分。結果不單調（大的值 FAIL、小的值 PASS）也報錯。clock 的高、低電位時間不探測到 `PULSE_FLOOR`（0.4 ns）以下。
    - 改搜尋法之前，先用假的模擬器（給定真值的函式）比對新舊版：範圍內的探測點完全相同，所以已跑完的模擬可以直接沿用。
16. **產生 .lib 的程式本身也要有 checker，而且要獨立於它**（2026-10-05 獨立審查找到 9 個漏洞，Phase 5 開頭修；`ip/sram/char/`）：
    - `--check` 只比「同一支程式的輸出」，公式寫錯（取最大與取最小弄反、少乘係數）照樣一致。另寫一支不 import 產生器的程式，從量測 JSON 重算 .lib 的每個數字再比對（`check_char_lib.py`），用改壞公式的產生器（M1–M5）證明抓得到（N12）。
    - 測試用的假資料每格要不同、部分高過下限：每格相同又全被下限蓋過時，公式錯誤產生的 .lib 一模一樣（N5–N8 原本的 `fake_doc`）。
    - 量測 JSON 是 regress 不會重跑的信任起點：檢查每筆紀錄是它的 PVT、數值有限且 pass > fail 不超過解析度（NaN 經 `max()` 會變成下限），以及來源欄位（網表 sha256、PDK 版本、ngspice 版本、修剪數、步長與搜尋設定，N9–N11）。
    - 二分搜尋只在探到的點檢查單調：最後要在 .lib 採用的值上各跑一次確認模擬，全部讀寫正確（`confirm_char_lib.py` → `confirm.json`，N14）。
    - 模擬快取：只有 log 沒有錯誤、波形涵蓋到 `.tran` 結束時間才重用；讀出檢查的時間點超過波形結尾要報錯（`value_at` 超過結尾會回傳最後一個值，N15）。
    - 有 PVT 失敗就不寫量測 JSON，避免新舊紀錄混合（N16）。
    - 範本替換的次數要每支 pin、每個 rise／fall 分開數（N13）。

## 待補

- 寄生：萃取網表無法收斂（經驗紀錄 2026-10-05），寄生的影響目前只有「換上萃取 bitcell」的估計；Phase 6 用 OpenRAM 環境再量。
- 其他 PVT 的步長與修剪誤差只在 TT 驗證過。
- hold 弧的值和週期有關（週期 10–16 ns 時「讀之後接寫」比 .lib 早變化），.lib 只對週期 ≥ 20 ns 量過（ADR-0010 已知限制 11）。
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
| 2026-10-05 | Phase 3.5 驗證（TT，delay 序列） | 步長 100 ps 對 10 ps：穩定時間 +1.6%、開始變化 −0.7%；修剪對完整網表：讀出延遲 +2.0%；UIC 對直流工作點 +0.5%；十字 5 點推算四角 ≤ 1% | 已驗證：讀出穩定時間的誤差都偏保守；dout 開始變化在兩個 5 fF 角偏晚 0.5–1.0%（樂觀，2026-10-05 獨立審查更正）；修剪那一項用的是早期 508 顆的網表、量的是 50% 延遲 | 記入 ADR-0010 的餘量；規則 11 | `docs/phase_exit/phase3_5.md` |
| 2026-10-05 | Phase 3.5 TT 特性化 | setup 為負、hold 為正（規則 9）；最小 high 0.80 ns、low 2.80 ns、週期 5.62 ns | 已驗證（二分搜尋到 0.02–0.04 ns） | 規則 9 | `ip/sram/.../char/char.json` |
| 2026-10-05 | Phase 3.5 萃取網表 | 修剪後 singular matrix（VSUBS、被修剪 cell 的儲存節點）；處理後、加 rshunt，暫態仍在第一個 clock 邊緣報 `Timestep too small`（出事的節點每次不同） | 前半已驗證（規則 10）；後半未解決 | 萃取網表暫不用於特性化 | 同上 |
| 2026-10-05 | Phase 3.5 寄生估計 | 電路圖網表換上 Magic 萃取的 bitcell（含 cell 內寄生與接面面積）後，TT 寫入第 0 列第 0 行失敗：預充電只到 1.68 V，寫入時兩條 bitline 同時偏低，儲存節點停在約 0.4 V 後倒向錯的一邊 | 未解決：可能是真的餘量問題，也可能是只換 bitcell、周邊沒有寄生造成的不一致 | 使用者 2026-10-05 決定：記為下線前風險，Phase 6 用 OpenRAM 環境確認（ADR-0010 已知限制 4） | 同上 |
| 2026-10-05 | Phase 3.5 操作 | 重開特性化時用 `pkill -f 'ngspice -b deck.sp'`，把另一個也叫 `deck.sp` 的參考模擬一起砍掉 | 已驗證（操作失誤） | 停止程序用 PID 或父程序，不用檔名比對 | — |
| 2026-10-05 | Phase 3.5 特性化的植入錯誤 | N6（手改 .lib 必須被 `--check` 抓到）改成新餘量後，要替換的字串 `2.7500` 已不在 .lib 裡，植入什麼都沒做，`--check` 判沒有過期，N6 FAIL | 已驗證：餘量改變後 .lib 的數字跟著變 | 改成編輯 `timing_type : rising_edge;` 並檢查替換次數（規則 11）；N1–N6 6/6 PASS | `ip/sram/char/neg_char.py` |
| 2026-10-05 | Phase 3.5 ss −40°C 診斷 | 6 個各約 25 分鐘的模擬全部在最後報 `Error: no such vector xsram.xbank0.xport_data0.bl_0`，沒有波形 | 已驗證：子電路的 port 節點用上一層的網路名稱（`xsram.xbank0.bl_0_0`），只有子電路內部節點才是 `<instance>.<node>`；`wrdata` 到模擬結束才檢查名稱 | 長模擬前先跑一個 1 ns 的同一份 deck 確認每個探測節點都存在 | scratchpad `diag2.py` 的 `check_names` |
| 2026-10-05 | Phase 3.5 ss −40°C | 延遲模擬每次讀取都錯；tt −40°C、ss −40°C 到 1.95 V 都讀成前一次的值 | 已驗證（修剪網表，量 bit 0 的 column mux 輸出與 sense amp 內部節點）：sense amp 沒有預充電、column mux 只有 NMOS（規則 13）；完整網表在 ss −40°C 1.70 V 失敗的讀取與節點電壓相同（不是修剪造成） | 使用者決定：ss −40°C 用佔位 .lib，列為頭號下線風險，Phase 6 修正 | ADR-0010 |
| 2026-10-05 | Phase 3.5 harden-soc 第 1 次（`ccc536c`） | `OpenROAD.RepairDesignPostGPL` 75 分鐘後 `failed with an unexpected error`（同一步正常約 40 秒；這個 run 的 log 在重跑時被刪，訊息是當時看到的） | 已驗證（單步重跑 4 種 .lib）：dout0 延遲表的負載斜率等於 60–140 kΩ 的 driver | 規則 14：負載方向取最大值 | ADR-0010 |
| 2026-10-05 | Phase 3.5 最終版圖的 what-if | dout0 transition 用 0.5 ns（使用者決定）；改成電路圖量到的值後，SRAM 半週期路徑 slack：ss −40°C 用 tt 量到的 1.3 ns（這個 PVT 讀取失敗、沒有量測）時 +0.38 → +0.03，ss 100°C 3.15 ns 時 +0.92 → +0.17 | 已驗證（OpenSTA 只換 .lib） | 記入 ADR-0010 已知限制 5；macro 輸出 transition 這種沒有把握的假設，要用 what-if 量出它對 slack 的影響 | ADR-0010 |
| 2026-10-05 | Phase 3.5 非 tt 的 PVT | ss、ff 的最小 pulse 寬度與週期都在以 tt 為中心的搜尋範圍外；舊版每往外移一次就從頭二分 6 輪，預估 ss 的最小週期要近 20 小時 | 已驗證（假模擬器比對新舊版：範圍內探測點相同） | 規則 15：往外一次測 2 點，最多 3 次；ss 100°C、ff −40°C、ff 100°C 用新版重開，沿用已跑完的模擬 | `ip/sram/char/characterize.py`、`ip/sram/char/README.md` |
| 2026-10-05 | Phase 3.5 獨立審查（兩個 agent） | 文件：ss 25°C 1.60 V 的讀取失敗漏列（和 1.80 V 混在一起）、寄生數字（+42%）重算是 +45–48%、「誤差都偏保守」不成立（hold 弧兩角偏樂觀 ≤ 1%）、`max_capacitance` 0.02756 → 0.05 pF 沒寫；checker：12 個漏洞，其中 9 個在特性化流程（見「待補」） | 已驗證（波形重算、獨立重算 5 份 .lib、改壞的輸入實際跑 checker） | 文件更正；規則 11、13 補充；漏洞列為已知限制，Phase 5 開頭修（使用者決定）；獨立重算確認這次的 .lib 正確 | `docs/phase_exit/phase3_5.md`「獨立審查」 |
| 2026-10-05 | Phase 5 開頭：修 Phase 3.5 審查的特性化漏洞 | 9 個漏洞（見規則 16） | 已驗證：每個新植入錯誤在修正前的程式上抓不到、修正後抓到（N9、N11、N13、N15、N16；N12 的 5 種公式錯誤全部抓到）；新的 `check_char_lib.py` 對現有 5 份 .lib PASS | 規則 16；`make sram-confirm` | `ip/sram/char/README.md` |
