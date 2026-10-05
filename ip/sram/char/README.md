# SRAM 的 SPICE 特性化（Phase 3.5）

用 ngspice 量 PDK 附的 `sky130_sram_2kbyte_1rw1r_32x512_8` 電晶體級網表，產生 STA 用的每個 PVT 一份 .lib，取代 ADR-0007 的假設值（`padded.lib`）。決策與理由見 [ADR-0010](../../../docs/decisions/0010-sram-spice-characterization.md)；方法上的規則與陷阱見 skill `openram-macro-characterization`。

## 檔案

| 檔案 | 用途 |
|---|---|
| `sramchar.py` | 共用：網表修剪、測試序列（`Seq`）與 deck、執行 ngspice、波形量測、讀出檢查 |
| `characterize.py` | 量測主程式：延遲表、setup/hold、最小週期與 pulse width，結果併入 `char.json` |
| `gen_char_lib.py` | 由 `char.json` 和 PDK 的 TT .lib（當格式範本）產生 5 份 .lib；`--check` 檢查是否過期；先檢查 `char.json` 每筆紀錄是它的 PVT、數值合理（有限、pass > fail 且差距不超過解析度） |
| `check_char_lib.py` | 獨立檢查（不 import `gen_char_lib.py`）：從 `char.json` 重算 .lib 的每個數字並比對；檢查 `char.json` 來自釘版的 PDK 網表與 `characterize.py` 的設定；檢查 `confirm.json` |
| `confirm_char_lib.py` | 確認模擬：每個量得到的 PVT，用 .lib 最終採用的 setup／hold／pulse width／週期跑一次，全部要讀寫正確，結果寫進 `confirm.json` |
| `neg_char.py` | 特性化本身的植入錯誤 N1–N16 |
| `extract_sram.py` | 用 Magic 從 GDS 萃取含走線電容的網表（寄生的影響比較用） |
| `../sky130_sram_2kbyte_1rw1r_32x512_8/char/` | 進版控的結果：`char.json`、`confirm.json` 與 5 份 `<macro>__<pvt>.lib` |

## 怎麼跑

```bash
make sram-lib      # 由 char.json 重新產生 5 份 .lib（幾秒）；make harden-soc 會檢查它們沒有過期
make neg-char      # 特性化的植入錯誤（約 40 分鐘）
make sram-char     # 重新特性化：先 tt，再以 tt 為中心跑其他 4 個 PVT，最後 sram-lib（數小時，不在 make regress 裡）
```

需要 ngspice（`toolchain.md`）與 PDK（`env/versions.mk` 的版本）。每次模擬存在 `runs/sram_char/<netlist>/<pvt>/<名稱>/`（deck、log、波形）；同一個 deck 已經跑過、而且那次的 log 沒有錯誤、波形涵蓋到 `.tran` 的結束時間，就不會重跑。中途失敗的模擬可能留下半截的波形，不能重用；讀出檢查要看的時間點超過波形結尾時直接報錯（Phase 3.5 審查）。有任何 PVT 失敗時 `characterize.py` 不改 `char.json`（避免新舊紀錄混在一起），已跑完的模擬留在快取裡。

`make harden-soc` 開頭的 `check_inputs.py` 會跑 `gen_char_lib.py --check`（.lib 沒過期）與 `check_char_lib.py`（數字獨立重算、來源、確認模擬）。重新特性化或改 `gen_char_lib.py` 之後，要再跑 `confirm_char_lib.py` 更新 `confirm.json`（4 個 PVT、20 次模擬，約 1 小時）。

## 量什麼、怎麼量

**網表**：PDK 的 `libs.ref/sky130_sram_macros/spice/<macro>.spice`。完整網表（約 15 萬顆 MOSFET）在 ngspice 光讀檔就要 35 分鐘以上，所以修剪成只留記憶體陣列的第 0、127 列，以及資料 bit 0 和 bit 31 用到的 8 行（bit b、word w 在第 4b+w 行，見 `column_mux_array`）。

- bit 0、31 的 bitline 上仍有完整的 128 個 bitcell，時序只在這兩個 bit 上量。
- 其他 30 個 bit 只用來檢查讀出值對不對。
- 讀寫只用第 0、127 列的 8 個位址。

**測試序列**：一串讀寫週期。每個輸入在前一個週期較長那一半的中間轉態；讀出值在下一個上升緣前 0.05 ns 取樣，相當於 SoC 裡 `rdata_q` 抓資料的時間點。

- 1 要高於 0.8 VDD，0 要低於 0.2 VDD，否則 FAIL。
- 測試資料用 0x5A5AA5A5 這種混合圖樣：被修剪掉的列讀出來不會剛好等於它。

| 量測 | 定義 | 寫進 .lib |
|---|---|---|
| 讀出穩定時間 | 下降緣 → bit 最後一次進入有效範圍（≥ 0.8 或 ≤ 0.2 VDD） | dout0 `falling_edge` 的 cell_rise／cell_fall；每列（clock slew）取負載中的最大值，表不隨負載變化（ADR-0010「延遲表為什麼不隨負載變化」） |
| 轉換時間 | 讀 1 時 dout 的 10–90% | rise／fall_transition |
| 資料開始變化 | 上升緣 → 前一次讀出的值偏離 0.1 VDD | 新增的 dout0 `rising_edge` 弧（hold 檢查用）；每列取負載中的最小值 |
| setup/hold | 在測試週期把一組輸入的轉態時間往前或往後移，看寫入或讀回的資料是新值還是舊值；二分搜尋 | 各輸入的 setup_rising／hold_rising |
| 最小 pulse width、週期 | 縮短 clock 高（或低、或兩者）的時間，直到讀寫出錯；二分搜尋 | clk0 的 min_pulse_width、minimum_period |

**dout 在上升緣後會變化**：每個有效週期（`csb0=0`），dout 在上升緣後約 1.2 ns 開始偏離上一次讀出的值；有時是拉到 0，有時停在約 0.8 V 的中間電位，要到下降緣後讀出新值才穩定。PDK 的 .lib 沒有這條時序弧，所以 STA 不會檢查接收端的 hold，新 .lib 加上了。

**PVT**：tt 25°C 1.80 V、ss 100°C 1.60 V、ff −40°C 1.95 V、ss −40°C 1.60 V、ff 100°C 1.95 V，和 STA 的 5 個 PVT 相同（`pnr/soc_top/config.json`）。tt 用完整的搜尋範圍與 3×3 延遲表。其他 4 個 PVT 的搜尋以 tt 結果為中心（setup/hold ± 0.5 ns、pulse ± 1 ns）。結果超出範圍時，往外一次模擬 2 個點、涵蓋一個初始寬度，最多 3 次，找到另一側後再繼續二分；clock 的高或低電位時間不探測到 0.4 ns 以下（週期 0.8 ns）。ss 的高、低電位時間與週期都比 tt 大 1 ns 以上，ff 的低電位時間與週期則小 1 ns 以上，所以都會用到這一步；延遲表只模擬中間那一列與那一行，四個角的值假設 slew 和負載的影響可以相加來推算。

**讀取失敗的 PVT**：每個 PVT 先跑延遲表中間那一點的模擬（和延遲表共用）。只要有一次讀取錯，就只記下錯的讀取（`char.json` 的 `read_fail`），不量時序；`gen_char_lib.py` 為它產生佔位 .lib（`PLACEHOLDER_FROM` 的數字，hold 弧取所有 PVT 最早的值，檔頭寫明）。目前 STA 的 PVT 中只有 ss −40°C 1.60 V：PDK 這顆 macro 在低溫，以及 ss 1.60 V 的室溫（25°C）會讀成前一次的值（25°C 不是 STA corner），原因與證據見 ADR-0010「ss −40°C 讀取失敗」。

**port 1**：SoC 裡 tie-off，STA 沒有 clk1 的 clock，沿用 PDK 的解析數字；功耗也沿用 PDK 的數字。

## 植入錯誤（`make neg-char`）

| 案例 | 植入 | 必須抓到的地方 |
|---|---|---|
| N1 | 所有 sense amp 輸出加 100 fF | 讀出穩定時間至少增加 0.2 ns |
| N2 | 兩顆 bitcell（第 127 列、第 124 與 127 行）的 Q 接地 | 讀出檢查 FAIL |
| N3 | setup 搜尋的「移動轉態時間」失效 | 搜尋報錯「passed everywhere」，不給數字 |
| N4 | 網表少一顆 bitcell | 修剪的數量檢查 FAIL |
| N5 | `char.json` 少了 pulse 的結果 | `gen_char_lib.py` FAIL |
| N6 | 手改一份產生的 .lib | `gen_char_lib.py --check` STALE |
| N7 | 讀取失敗的 PVT，它的佔位來源也讀取失敗（先做正向對照：來源正常時要寫出標明 PLACEHOLDER 的 .lib） | `gen_char_lib.py` FAIL，指名該 PVT 與來源 |
| N8 | `char.json` 少一個 PVT | `gen_char_lib.py` FAIL，報出缺的正是那一個 |
| N9 | `char.json` 兩個 PVT 的紀錄對調 | `gen_char_lib.py` FAIL「is the record of」 |
| N10 | `char.json` 的來源欄位逐一改掉（網表 sha256、PDK、ngspice 版本、修剪數、步長、解析度） | `check_char_lib.py` provenance FAIL，指名該欄位 |
| N11 | 不合理的數值：setup 是 NaN、hold 的 pass < fail、週期 NaN、hold 弧有 NaN | `gen_char_lib.py` FAIL（每一種） |
| N12 | `gen_char_lib.py` 的公式錯誤 M1–M5：延遲每列取最小、hold 弧每列取最大、佔位 hold 弧不取最小、少乘 1.6、少乘 0.9（先做正向對照：原程式 PASS） | `check_char_lib.py` values FAIL（每一種） |
| N13 | PDK 範本的格式變化：clk0 pulse width 寫成 `rise_constraint (scalar)`；csb0 少 setup 弧、din0 多一個 | `gen_char_lib.py` FAIL「change counts」 |
| N14 | `confirm.json` 的值與 .lib 不同、某條沒有 PASS、來自另一份 `char.json`（先做正向對照） | `check_char_lib.py` confirm FAIL（每一種） |
| N15 | 中途失敗的模擬快取（log 有錯誤、波形被截斷） | 快取不被重用；讀出檢查報錯而不是判對 |
| N16 | 特性化時一個 PVT 失敗 | `characterize.py` FAIL，`char.json` 不變 |

N5–N16 只要幾秒；N1–N3 要跑 ngspice。這些新案例都在修正前的程式上確認過抓不到（N15 在舊程式上沒有對應的檢查函式）。

把 .lib 接進 SoC 之後的植入錯誤在 `pnr/soc_top/neg_pnr.py`：
- P04（sram0 延遲 ×10 → setup FAIL）；
- P17（.lib 的 hold 弧被改掉 → `check_inputs.py char_lib`，訊息必須是 STALE 並指名那份 .lib）；
- P30（某個 corner 讀到別的 PVT 的 .lib → `check_soc.py sram_lib`）；
- P32（hold 弧設成 0 → hold FAIL；先確認未修改的複本沒有 hold 違規）；
- P33（某個 corner 另外以 extra library 讀進 PDK 的 SRAM .lib）、P34（同檔名但來自另一個 checkout）→ `check_soc.py sram_lib`；
- P35（config 的 `EXTRA_LIBS` 或 `LIB` 帶進 SRAM .lib）→ `check_inputs.py other_libs`；P36（`resolved.json` 有 `EXTRA_LIBS`）→ `check_inputs.py --resolved`。
