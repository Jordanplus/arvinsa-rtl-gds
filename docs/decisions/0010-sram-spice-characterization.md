# ADR-0010：SRAM macro 的時序改用本機 ngspice 實測（Phase 3.5）

- 狀態：進行中。做法由使用者在 2026-10-04 決定；完成後取代 ADR-0007 的 padded.lib。
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
6. **餘量**：量完再決定，並請使用者確認。實測值可能比 padded.lib 的 10 ns 小很多，換上之後 signoff 會比現在寬鬆，所以這是 signoff 條件的變更。
7. **驗證特性化腳本**：用植入錯誤證明它量得對。例如：
   - 在 sense amp 輸出加電容，量到的延遲必須變大；
   - 讓一顆 bitcell 卡住，功能檢查必須 FAIL；
   - 在 setup 時間內改變輸入，必須判成違規。
8. **OpenRAM 環境延到 Phase 6 再建**。Phase 6 要自產 macro，那時才需要它。

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
- 試跑紀錄：`docs/phase_exit/phase3_5.md`（Phase 3.5 收尾時整理）。
