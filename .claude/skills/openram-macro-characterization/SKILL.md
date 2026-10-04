---
name: openram-macro-characterization
description: SRAM macro（OpenRAM 產生的預建 macro 或自產 macro）的時序要用 SPICE 實測、產生多 corner 的 .lib 時使用：判斷廠商 .lib 是不是解析模型、用 ngspice 量 clk→dout 延遲與 dout 在上升緣後被拉回的時間、setup/hold、最小週期與 pulse width、網表修剪與模擬步長怎麼驗證、從 GDS 萃取寄生電容（Magic）、OpenRAM 自己特性化的缺陷、量測結果怎麼寫成 .lib 並用植入錯誤證明量得對，以及 ngspice 讀大網表很慢、bus 節點名稱報 bad v() syntax 這類問題。macro 怎麼放進設計看 hard-macro-integration，餘量怎麼定看 signoff-criteria。Use for SPICE characterization of SRAM macros (ngspice + sky130), per-corner Liberty generation, netlist trimming, parasitic extraction and OpenRAM characterizer pitfalls.
---

# SRAM macro 的 SPICE 特性化與 .lib

macro 整合清單看 `hard-macro-integration`；量到的數字要加多少餘量看 `signoff-criteria`；corner 清單看 `multicorner-sta`。本 repo 實例：ADR-0010、`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`（Phase 3.5 建立中）。

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

## 待補（Phase 3.5 進行中，驗證後才搬進規則）

- 量測項目與方法：延遲與 transition 的表格軸怎麼選、setup/hold 在整顆 macro 上用讀回資料判定、最小週期與高低 pulse width 用功能測試二分搜尋。
- 修剪與步長在每個 PVT 的誤差、寄生電容造成的延遲差。
- 特性化腳本的植入錯誤（例如在 sense amp 輸出加電容，延遲必須變大；讓一顆 bitcell 卡住，功能檢查必須 FAIL）。
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
