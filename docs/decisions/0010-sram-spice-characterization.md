# ADR-0010：SRAM macro 的時序改用本機 ngspice 實測（Phase 3.5）

- 狀態：已採用（2026-10-05），取代 ADR-0007 的 padded.lib。做法由使用者在 2026-10-04 決定；餘量、兩個未解問題，以及 ss −40°C 讀取失敗的處理在 2026-10-05 決定。
- 範圍：`sky130_sram_2kbyte_1rw1r_32x512_8`，也就是 soc_top 的 `sram0`。只量 port 0；port 1 在設計裡 tie-off（`csb1=1`、`clk1=0`），STA 不會分析它。
- skill：`openram-macro-characterization`（Phase 3.5 開始時建立）。

## 問題

STA 現在用的 `padded.lib` 全部是工程假設（ADR-0007）。例如 clk0 下降緣到 dout0 的延遲填 10 ns、setup 1 ns、最小週期 30 ns，沒有一個是量出來的。

`project-plan.md` §8 原本的 Phase 3.5 做法是：在 x86 Linux（Colab 或 Lima VM）架好 OpenRAM，用它的 SPICE 特性化產生 TT／SS／FF 的 .lib。

## 查證結果（2026-10-04）

1. **PDK 已經附上這顆 macro 的電晶體級網表**：`$PDK_ROOT/sky130A/libs.ref/sky130_sram_macros/spice/sky130_sram_2kbyte_1rw1r_32x512_8.spice`。網表裡有 94 個 subckt，bitcell 的定義也在其中，用到的元件都在 PDK 的 ngspice 模型裡。Homebrew 的 ngspice-47 可以直接在本機（Apple Silicon）模擬它。
2. **OpenRAM 自己的 SPICE 特性化有方法上的缺陷**（VLSIDA/OpenRAM `stable` 分支的 `compiler/characterizer/`，細節見 skill 規則 3）：
   - setup/hold 只模擬輸入端那顆 DFF，而且只量第一個 corner；
   - `cell_rise` 直接抄 `cell_fall`；
   - `min_pulse_width` 取最小週期的一半；
   - 預設沒有走線 RC。

   照原計畫做，這些缺陷會原樣帶進 .lib。另外，它量的是用新版 OpenRAM 重新產生的電路，不一定和 PDK 這顆完全相同。
3. **PDK 附的所有 SRAM .lib 都是解析模型**，包括 1 KB 版本的 SS／FF 檔：延遲表每一列相同，最小週期只有 0.119–1.956 ns。所以 PDK 裡沒有任何 SPICE 實測值可以拿來對照。
4. **矽量測**（ISCAS'23，OpenRAM 團隊）：量的是 1 KB 的 32×256 macro，不是這顆 2 KB 的；論文也沒有拿量測結果去和 .lib 或特性化結果比對。
5. **本機試跑**（修剪網表、TT、輸出負載 10 fF、clock slew 0.1 ns）：
   - clk0 下降緣 → dout0 讀出 1：2.305 ns（`.tran 100p`，7 分鐘），步長縮到 10 ps 時是 2.348 ns（33 分鐘）。
   - **dout0 在每個有效週期的上升緣後 1.05–1.29 ns 就被拉回 0**。資料只在「下降緣 + 約 2.3 ns」到「下一個上升緣 + 約 1 ns」之間有效。PDK 的 .lib 和 `padded.lib` 都只有下降緣那一條時序弧，所以 STA 不會檢查接收端 `rdata_q` 的 hold；如果 `rdata_q` 的 clock 比 `sram0` 的 clk0 晚到將近 1 ns，就會抓到被拉回的 0。
   - 完整網表（約 15 萬顆 MOSFET）光讀檔就超過 35 分鐘，所以要修剪網表。
6. **從 GDS 萃取寄生電容可以在本機做**：用 LibreLane nix-shell 裡的 Magic 8.3.623，花 26 分鐘，產生 7.9 萬顆電容。

## 決策

使用者在 2026-10-04 選擇「本機 ngspice 直接量」。

1. **量 PDK 附的網表**，也就是晶片上實際放的那顆 macro。5 個 PVT 全部實測：
   - tt 25°C 1.80 V
   - ss 100°C 1.60 V
   - ff −40°C 1.95 V
   - ss −40°C 1.60 V
   - ff 100°C 1.95 V
2. **量測項目**：
   1. clk0 下降緣 → dout0 讀出的延遲與 transition，取最大值；
   2. clk0 上升緣 → dout0 開始變化的時間，取最小值。這是新加的 `rising_edge` 時序弧，讓 STA 能檢查接收端的 hold；
   3. addr0、din0、wmask0、csb0、web0 的 setup/hold。在整顆 macro 上量，用寫入再讀回的資料判斷 PASS／FAIL，所以 macro 內部的 clock buffer 也算進去；
   4. 最小週期，以及 clock 高、低的最小 pulse width，都用功能測試做二分搜尋。
3. **修剪網表**：只留記憶體陣列的第一／最後一列與行，量測點在位址 511 的 bit 31（最後一列、最後一行），和 OpenRAM 的做法相同。採用前要和完整網表在同一個量測點比對一次；模擬步長也要用小步長的結果驗證，誤差記錄下來。
4. **寄生電容**：從 GDS 萃取，量化它對延遲的影響，再決定是直接模擬萃取後的網表，還是把影響換算成比例加進結果。
5. **產生 .lib**：
   - 由腳本產生，每個 PVT 一份。pin、電容、功耗與 memory 描述沿用 PDK 的 .lib，只換時序數字並加上新的時序弧。
   - 量測結果存成 JSON 進版控，.lib 由 JSON 產生，並有 `--check` 檢查 .lib 是否過期。
   - 特性化一次要數小時，不放進 `make regress`；regress 只從 JSON 重新產生 .lib 並比對。
6. **餘量**：量完再決定，並請使用者確認（2026-10-05 的決定見下一節）。
7. **驗證特性化腳本**：用植入錯誤證明它量得對。例如：
   - 在 sense amp 輸出加電容，量到的延遲必須變大；
   - 讓一顆 bitcell 卡住，功能檢查必須 FAIL；
   - 在 setup 時間內改變輸入，必須判成違規。
8. **OpenRAM 環境延到 Phase 6 再建**。Phase 6 要自產 macro，那時才需要它。

## 使用者決定（2026-10-05）

量完 TT 之後，有三件事要使用者決定（`ip/sram/char/gen_char_lib.py` 的常數）：

1. **餘量：取保守值**。電路圖網表沒有走線寄生（parasitic，金屬線的電阻與電容）。把 bitcell 換成從 GDS 萃取、含 cell 內寄生的版本做試驗，讀出穩定時間增加 42%，50% 延遲增加 45–65%。所以：
   - dout0 延遲、最小週期、pulse width：實測值 × 1.6；
   - setup/hold：實測值 + 0.1 ns；
   - 每個上限再和 ADR-0007 的 padded.lib 值比，取較保守的那個（padded.lib 的值當下限）。ss 的 dout 延遲下限是 10 ns × 1.5 = 15 ns，與 ADR-0007 相同；
   - 新加的 hold 弧（上升緣 → dout0 開始變化）：實測最小值 × 0.9。萃取 bitcell 的試驗裡資料開始變化得更晚，所以電路圖的值是偏早、偏保守的一側。
2. **換上萃取 bitcell 後寫入失敗：記為已知限制，Phase 6 確認**。見「已知限制」第 4 點。
3. **dout0 的 transition 維持 0.5 ns**（ADR-0007 的值）。電路圖網表量到 1.08–1.29 ns，換上萃取 bitcell 只有 0.23–0.28 ns，兩者差 5 倍，無法判斷哪一個對。
4. **ss −40°C 1.60 V 讀取失敗：用佔位 .lib，記為下線風險**（見下一節）。這個 PVT 的 .lib 用 ss 100°C 的數字（setup、週期、延遲都由 padded.lib 下限決定），hold 弧取所有量得到的 PVT 中最早的值 × 0.9；.lib 檔頭寫明「不是量測值，只讓 SRAM 周邊的邏輯仍被 STA 檢查」。Phase 6 自產 macro 必須修正這個問題，並在 5 個 PVT 都驗證讀取正確。

## ss −40°C 讀取失敗（2026-10-05）

ss −40°C 1.60 V 的延遲模擬中，每次讀取都錯（`char.json` 的 `read_fail`）。用同一個讀寫序列（4 次寫入、7 次讀取，週期 20 ns）在其他條件模擬，並量 bit 0 的 sense amp 內部節點：

| 條件 | 讀取 | 錯在哪裡 |
|---|---|---|
| tt 25°C 1.80 V | PASS | — |
| ss 100°C 1.60 V（特性化） | PASS | — |
| ff −40°C 1.95 V、ff 100°C 1.95 V（特性化） | PASS | — |
| ss 60°C 1.60 V、ss 25°C 1.80 V | FAIL 2 次 | 只有 bit 1–30。bit 0、31 正確（見下方「修剪」） |
| tt −40°C 1.60 V | FAIL 3 次 | 含 bit 0：讀成前一次的值 |
| ss −40°C 1.70 V、1.95 V | FAIL 3 次 | 含 bit 0：讀成前一次的值 |
| ss −40°C 1.60 V | FAIL 7 次 | 每次都錯，dout 一直不動 |

**機制（bit 0 的內部節點，已用模擬確認）**：
- sense amp（`sky130_fd_bd_sram__openram_sense_amp`）是一個 latch，沒有自己的預充電或等化電路。每次讀取前，它靠兩顆 PMOS 接回 bitline，把上一次被拉低的那個內部節點拉回去。
- 但 sense amp 和 bitline 之間的 column mux（`column_mux`）只有一顆 NMOS，傳高電位最多只到 VDD − Vt。ss −40°C 1.70 V 時，sense amp 輸入端只有 0.95 V，tt 25°C 1.80 V 時是 1.13 V。
- 低溫時 Vt 高，0.95 V 讓那顆 PMOS 幾乎不導通，上一次被拉低的節點（`dint_bar`）拉不回來；latch 自己的 PMOS 又把舊值鎖住，新讀取的 bitline 電壓差蓋不過它。
- 第 5 個週期（讀 508，bit 0 應從 1 變 0）在 sense amp 啟動前 0.3 ns，`dint` 應該已經偏低、`dint_bar` 偏高：

  | 條件 | `dint` | `dint_bar` | 讀出 |
  |---|---|---|---|
  | tt 25°C 1.80 V | 0.79 V | 1.79 V | 正確 |
  | tt −40°C 1.60 V | 1.27 V | 0.22 V | 前一次的值 |
  | ss −40°C 1.70 V | 1.53 V | 0.00 V | 前一次的值 |
  | ss −40°C 1.95 V | 1.12 V | 0.90 V | 前一次的值 |

- 所以只有「連續兩次讀取的值不同」時會錯；ss −40°C 把電壓提高到 1.95 V 也救不回來。

**修剪的影響**：bit 1–30 的 bitline 在修剪網表裡只有 2 顆 bitcell（原本 128 顆），電容小很多。和 sense amp 內部節點分電荷後，電壓又更低，所以 ss 25°C、60°C 只有這些 bit 出錯。這部分是修剪造成的、比實際電路悲觀；bit 0、31 的 bitline 是完整的。**完整網表確認**：ss −40°C 1.70 V 用未修剪的 PDK 網表重跑同一個序列，失敗的讀取完全相同（第 5、6、10 次），第 5 次讀取前 `dint` 1.53 V、`dint_bar` 0.01 V（修剪網表 1.53／0.00 V）。所以 bit 0 的失敗不是修剪造成的。ss −40°C 1.60 V 的完整網表在 169.7 ns 因 `Timestep too small` 中止，之前的第 4–7 次讀取全部讀成 0（修剪網表也是每次都錯）。

**和矽量測的關係**：OpenRAM 團隊對 1 KB macro 的量測是「≥ 1.7 V 才不出錯」（查證結果第 4 點，室溫）。和這個機制的方向一致：VDD − Vt 的餘量越小越容易錯。但量測沒有低溫資料，無法直接對照。


## 結果

量測值（電路圖網表、修剪後，`ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/char.json`）與產生的 .lib 數值（`<macro>__<pvt>.lib`）。單位 ns。

- 讀出穩定：clk0 下降緣 → dout0 最後一次進入有效範圍（≥ 0.8 或 ≤ 0.2 VDD），取 bit 0、31 的最大值；範圍是 3×3 延遲表（clk0 slew 0.05／0.2／0.5 ns × dout0 負載 5／20／50 fF）。
- dout 開始變化：clk0 上升緣 → 前一次讀出的值偏離 0.1 VDD，取最小值。
- setup/hold：5 組輸入 × 上升／下降，第一個 PASS 的位移；負的 setup 表示輸入可以在 clock 上升緣之後才變。
- 二分搜尋的解析度 0.02–0.04 ns。

**量測值**（ns）：

| PVT | 讀出穩定（下降緣後） | dout 開始變化（上升緣後，最早） | setup | hold | 最小 high | 最小 low | 最小週期 |
|---|---|---|---|---|---|---|---|
| tt_025C_1v80 | 2.67 ～ 3.05 | 1.18 ～ 1.31 | −0.22 ～ −0.16 | 0.20 ～ 0.24 | 0.80 | 2.80 | 5.62 |
| ss_100C_1v60 | 3.93 ～ 5.70 | 2.70 ～ 3.38 | −0.39 ～ −0.28 | 0.33 ～ 0.43 | 1.83 | 4.67 | 9.37 |
| ss_n40C_1v60 | 讀取失敗（7 次讀取都錯，`read_fail`），不量時序 |||||||
| ff_n40C_1v95 | 1.63 ～ 1.87 | 0.71 ～ 0.77 | −0.13 ～ −0.10 | 0.11 ～ 0.16 | 0.47 | 1.74 | 3.50 |
| ff_100C_1v95 | 1.30 ～ 1.77 | 0.73 ～ 0.79 | −0.14 ～ −0.13 | 0.14 ～ 0.18 | 0.63 | 1.43 | 2.90 |

**.lib 的數值**（ns；ss −40°C 是佔位，見使用者決定 4）：

| PVT | dout0 下降緣延遲 | dout0 上升緣（hold 弧） | setup | hold | min_pulse_width | minimum_period |
|---|---|---|---|---|---|---|
| tt_025C_1v80 | 10.00 ～ 10.07 | 1.06 ～ 1.08 | 1.00 | 0.50 | 12.00 | 30.00 |
| ss_100C_1v60 | 15.00 ～ 15.12 | 2.43 ～ 2.56 | 1.00 | 0.50 ～ 0.53 | 12.00 | 30.00 |
| ss_n40C_1v60（佔位） | 15.00 ～ 15.12 | 0.64 ～ 0.65 | 1.00 | 0.50 ～ 0.53 | 12.00 | 30.00 |
| ff_n40C_1v95 | 10.00 ～ 10.06 | 0.64 ～ 0.65 | 1.00 | 0.50 | 12.00 | 30.00 |
| ff_100C_1v95 | 10.00 ～ 10.04 | 0.66 ～ 0.67 | 1.00 | 0.50 | 12.00 | 30.00 |

**怎麼讀**：
- setup、最小週期、pulse width 全部由 padded.lib 的下限決定（實測值加餘量都比它小），所以這些檢查和 Phase 4 一樣嚴格。hold 只有 ss 的 0.53 ns（實測 0.43 + 0.1）超過下限 0.5 ns。
- dout0 延遲表**不隨負載變化**：每一列（clock slew）取所有負載中最大的延遲 × 1.6，再整張上移到最小值等於下限（tt／ff 10 ns、ss 15 ns）。hold 弧反過來，每一列取所有負載中最早的變化 × 0.9。理由見下方「延遲表為什麼不隨負載變化」。Phase 4 的 SoC 裡 `sram0` 的 clock slew 約 0.065 ns、dout0 負載 0.004–0.010 pF，延遲和 Phase 4 差不多（ss 15.0 ns）。
- 和 Phase 4 的實質差別有三個：
  1. 新的 hold 弧：STA 第一次檢查 `sram0` → `rdata_q` 的 hold（ff 只有 0.64–0.71 ns）；
  2. 每個 PVT 一份 .lib，PnR 的 resizer 在 ss corner 也看得到 SRAM 的慢延遲（以前的 derate 只在 signoff STA 生效，ADR-0007「corner 與 derate」）；
  3. SRAM 不再有 instance derate，所以 `base.sdc` 的 ±5% OCV 直接套到 SRAM（OpenSTA 的 instance derate 會取代 global derate，ADR-0007「Phase 4 補充」）。

### 延遲表為什麼不隨負載變化（2026-10-05）

第一版 .lib 保留了實測的負載斜率，Phase 3.5 第 1 次 `make harden-soc` 在 `OpenROAD.RepairDesignPostGPL`（global placement 後的 DRV 修復）跑了 75 分鐘後異常結束（Phase 4 同一步 44 秒）。單步重跑同一份輸入比較：

| .lib | 結果 |
|---|---|
| 第一版（保留負載斜率） | 卡在 12736 個 driver 的第 9000 個之後 |
| 第一版 + dout0 `max_transition 1.5` | 一樣卡住 |
| 負載方向攤平 | 98 秒完成 |
| Phase 4 的 padded.lib | 98 秒完成（插入 buffer 數與上一列只差 3 個） |
| 本版（每列取負載中的最大值） | 52 秒完成，插入 5013 個 buffer |

原因：讀出穩定時間量的是 dout 進入有效電壓範圍的時刻，不是 RC 延遲，ss 100°C 從 5 fF 到 20 fF 跳了 1.3 ns。把它當負載斜率，等於告訴 OpenROAD 這個 driver 有 60–140 kΩ（PDK 解析模型約 5.6 kΩ），resizer 就一直在 dout0 的 net 上插 buffer。改成每列取最大值後：在特性化過的負載範圍內（`max_capacitance` 50 fF）延遲是上限、hold 弧是下限，兩邊都偏保守；因為下限主導，工作點的延遲沒有變小。

## 驗證

| 項目 | 結果 | 說明 |
|---|---|---|
| 模擬步長 | 100 ps 對 10 ps：讀出穩定 +1.6%、dout 開始變化 −0.7% | TT delay 序列；兩者都是偏保守的方向 |
| 網表修剪 | 修剪對完整網表：讀出延遲 +2.0% | 同一量測點 |
| 初始條件 | UIC 對直流工作點：+0.5% | |
| 延遲表推算 | 其他 4 個 PVT 只模擬十字形 5 點，四角用相加推算；在 TT 與 9 點全模擬比，誤差 ≤ 1% | |
| 植入錯誤 N1–N8（`make neg-char`） | N1–N6 6/6 PASS（改搜尋邏輯前）；N4–N8 5/5 PASS（改後）；改後的完整重跑見 `docs/phase_exit/phase3_5.md` | sense amp 加 100 fF → 穩定時間 +0.72 ns；bitcell 卡住 → 讀出檢查 FAIL；setup 搜尋失效 → 報錯不給數字；網表少一顆 bitcell、JSON 缺 pulse、.lib 被手改、佔位 .lib 的來源也讀取失敗、少一個 PVT → FAIL／STALE（`ip/sram/char/README.md`） |
| 接進 SoC 的植入錯誤 | P04、P17、P30、P32 | `pnr/soc_top/neg_pnr.py`；結果見 `docs/phase_exit/phase3_5.md` |

## 已知限制

1. **PDK 這顆 SRAM 在低溫讀取會失敗**（「ss −40°C 讀取失敗」一節）：tt −40°C 1.60 V、ss −40°C 1.60–1.95 V 都會讀成前一次的值。STA 的 ss −40°C corner 用佔位 .lib（使用者決定 4），所以那個 corner 的 STA PASS 不代表 SRAM 能動。**這是頭號下線風險**：用這顆 macro 的晶片只在模擬確認過的條件（tt 25°C 1.80 V、ss 100°C 1.60 V、ff）能正確讀取；Phase 6 自產 macro 要修正讀取電路並在 5 個 PVT 驗證。
2. **走線寄生沒有模擬**。用 × 1.6 補。依據只是「換上萃取 bitcell」的試驗（+42–65%）；周邊電路（decoder、sense amp、控制邏輯）的走線寄生沒有算進去。
3. **Magic 萃取的完整網表無法模擬**：處理浮接節點、加 `rshunt` 之後，暫態仍在第一個 clock 邊緣報 `Timestep too small`（修剪或完整都一樣），原因未解。
4. **換上萃取 bitcell 後，TT 寫入第 0 列第 0 行失敗**（20 ns 與 40 ns 週期都失敗）。寫入脈衝由 macro 內部自己產生；預充電只到 1.68 V，寫入時兩條 bitline 同時偏低。可能是真的寫入餘量不足，也可能是只換 bitcell、周邊沒有寄生造成的不一致。**這是下線前的風險**：使用者決定記為已知限制，在 Phase 6 用 OpenRAM 環境（含寄生的特性化）確認，Phase 7 下線前必須有結論。
5. **dout0 transition 兩個模型差 5 倍**（見使用者決定 3）。如果電路圖的 1.1–1.3 ns 才是對的，`rdata_q` 的輸入 slew 被低估；這條是半週期路徑。用 OpenSTA 在 Phase 3.5 的最終版圖做 what-if（只換 .lib 的 dout0 transition，min RC）：ss −40°C 從 0.5 改 1.3 ns，最差 setup slack 從 +0.38 降到 +0.03 ns；ss 100°C 改成實測最差的 3.15 ns（50 fF），從 +0.92 降到 +0.17 ns。兩者都仍 PASS，但如果電路圖的 transition 才是對的，43 ns 的餘量幾乎用完（Phase 6 確認）。
6. **沒有模擬元件的隨機誤差（mismatch／Monte Carlo）**：sense amp 的 offset 會影響讀出時間，目前只靠 × 1.6 與 padded.lib 下限涵蓋。
7. **只在 bit 0、31 量時序、只用 8 個位址**；其他 30 個 bit 只檢查讀出值對不對。
8. **port 1 與功耗沿用 PDK 的解析值**。現在 port 1 tie-off，不影響 STA；Phase 5 如果用 port 1 做 instruction fetch（`project-plan.md` §8 的建議），port 1 也要特性化。
9. **沒有矽量測可以對照**：ISCAS'23 量的是 1 KB macro（查證結果第 4 點）。
10. **修剪後的功能檢查偏悲觀**：bit 1–30 的 bitline 只有 2 顆 bitcell，ss 25°C、60°C 只有這些 bit 讀錯（「ss −40°C 讀取失敗」一節）。setup/hold、pulse width 的搜尋用全部 32 個 bit 判斷 PASS／FAIL，所以結果可能偏大（偏保守）。

## 與原計畫不同

`project-plan.md` §8 的 Phase 3.5 原本寫「提前建 OpenRAM 環境（Phase 6 的環境），對同一 2 KB config 跑 SPICE 特性化」。改成本機 ngspice 的理由：
- 量的是晶片上實際放的那顆 macro；
- 避開 OpenRAM 特性化的方法缺陷；
- 不需要 x86 機器，也不用處理 Colab 斷線或 Lima 模擬 x86 很慢的問題。

代價是特性化腳本要自己寫，所以一定要用植入錯誤證明它量得對（決策第 7 點）。exit criteria「多 corner .lib 進版控；重跑 Phase 3 signoff PASS」不變。Phase 4 已經完成，所以「重跑 signoff」指的是在乾淨 checkout 上把 `make regress` 跑到 PASS。

## 出處

- PDK：`$PDK_ROOT/sky130A/libs.ref/sky130_sram_macros/{spice,lib,gds}/`、`$PDK_ROOT/sky130A/libs.tech/ngspice/`；PDK 版本見 `env/versions.mk`。
- OpenRAM：github.com/VLSIDA/OpenRAM `stable`，`compiler/characterizer/{delay,setup_hold,lib,elmore}.py`。
- 矽量測：Cirimelli-Low 等，"SRAM Design with OpenRAM in SkyWater 130nm"，ISCAS 2023。
- 試跑與驗證紀錄：`docs/phase_exit/phase3_5.md`；方法與檔案：`ip/sram/char/README.md`。
