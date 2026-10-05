# Phase 3.5 exit review：SRAM .lib 改用 SPICE 實測

日期：2026-10-05　結論：**PASS**（`make regress` 第 2 次在乾淨 checkout 25/25 PASS）。SRAM 在 ss 1.60 V 的低溫與室溫讀取失敗，列為頭號下線風險，Phase 6 處理。

Exit criteria 出處：`project-plan.md` §8 Phase 3.5。原文：「提前建 OpenRAM 環境（Phase 6 的環境），對同一 2 KB config 跑 SPICE 特性化產 TT/SS/FF .lib，取代 padded.lib 的假設值」，exit 條件「多 corner .lib 進版控；重跑 Phase 3 signoff PASS」。做法改成本機 ngspice 量 PDK 附的網表（使用者 2026-10-04 決定，ADR-0010「與原計畫不同」）。Phase 4 已經完成，所以「重跑 signoff」是指在乾淨 checkout 把 `make regress` 跑到 PASS。

一併帶進本階段的項目：Phase 4 已知限制 1「SRAM 的時序仍是假設值……Phase 3.5／6 用 OpenRAM 特性化後要重新檢討週期」（`docs/phase_exit/phase4.md`）。

正式 run：`make regress` 第 2 次，在乾淨的 worktree `../arvinsa-rtl-gds-p35b` 執行（`git worktree add --detach` 加 `git submodule update --init`，開始時沒有修改或未追蹤的檔案）。commit `6316ea9`，2026-10-05 15:28:52–17:45:16，8188 秒（136 分鐘），rc=0，25/25 target PASS（`runs/regress/summary.md`、`junit.xml`；log `runs/p35_regress_clean2.log`）。

第 1 次（`38e85cb`）18/25 PASS 後在 neg-pnr FAIL：P17 的植入程式先清空檔案再讀（「本階段找到並修正的 checker 問題」第 4 點）。修正後重跑，第 1 次不算數；它的 harden-soc 與 golden 439/439 相同，紀錄在 `runs/p35_regress1/`。

| # | 項目 | 結果 | 證據 |
|---|---|---|---|
| 1 | 多 corner .lib 進版控 | 5 個 PVT 各一份 .lib，由 `char.json` 產生，`--check` 確認沒過期。其中 ss −40°C 1.60 V 是佔位：macro 在這個 PVT 讀取失敗（使用者決定 5） | `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`、ADR-0010 |
| 2 | 重跑 signoff PASS | PASS：乾淨 checkout 的 `make regress` 25/25。soc_top 的 439 個 metric 與 golden 完全相同（regress 1 也相同），picorv32_core 325 個中 254 個相同、71 個在誤差內；164 個植入錯誤都在預期的 checker FAIL；沒有發生 GRT-0229 重試 | `runs/regress/summary.md` |
| 3 | 特性化本身量得對 | 誤差來源逐一驗證（都偏保守）；植入錯誤 N1–N8 全部抓到 | 「量測方法的驗證」「Checker qualification」兩節 |
| 4 | Phase 4 已知限制 1：重新檢討週期 | 延遲、setup、週期、pulse width 的實測加餘量都低於 padded.lib 的下限（只有 ss 100°C 的 hold 0.53 ns 高於下限 0.5 ns），延遲仍由下限決定；新的 hold 弧讓週期改成 43 ns（使用者決定） | 「時序」一節、ADR-0004 Phase 3.5 補充 |

## 做了什麼

1. **特性化腳本**（`ip/sram/char/`，方法見 `ip/sram/char/README.md`）：
   - 修剪 PDK 網表（16384 → 1264 顆 bitcell）；
   - 用讀寫序列量讀出延遲、上升緣後 dout 開始變化的時間、5 組輸入（上升、下降各一）的 setup/hold、最小 pulse width 與週期；
   - 每個 PVT 先跑一次讀取檢查，讀錯就只記錄、不量時序。
2. **5 個 PVT 的結果**（ADR-0010「結果」）：tt 46 次模擬；其他 4 個以 tt 為中心搜尋，ss 100°C 40 次、ff −40°C 38 次、ff 100°C 38 次。ss −40°C 讀取失敗（見下一節）。
3. **.lib 產生**（`gen_char_lib.py`）：
   - 餘量依使用者決定：延遲、週期、pulse width × 1.6，setup/hold + 0.1 ns，padded.lib 的值當下限；
   - 新增 dout0 的 `rising_edge` hold 弧（實測最早變化 × 0.9）；
   - dout0 transition 維持 0.5 ns；
   - 延遲表在負載方向取最大值（見「時序」一節）。
4. **接進 SoC**：
   - `config.json` 的 MACROS 每個 PVT 指向自己的 .lib，拿掉 SRAM 的 instance derate；
   - `check_inputs.py char_lib` 檢查 .lib 沒過期，`check_soc.py sram_lib` 檢查每個 corner 只讀到自己 PVT 的 .lib；
   - neg-pnr 改 P04／P17／P20／P30，新增 P32。

## 量測方法的驗證

| 項目 | 結果 |
|---|---|
| 模擬步長 100 ps 對 10 ps | 讀出穩定 +1.6%、dout 開始變化 −0.7% |
| 修剪對完整網表 | bit 31 讀出 1 的 50% 延遲 +2.0%（早期試跑的 508 顆修剪網表；正式的 1264 顆沒有再比） |
| UIC 對直流工作點 | +0.5%（替代設定比正式設定大多少，不是正式量法的誤差） |
| 延遲表只模擬十字 5 點、四角相加推算 | 和 tt 9 點全模擬比，誤差 ≤ 1%：讀出穩定偏大；dout 開始變化在兩個 5 fF 角偏晚 0.5%、1.0% |
| 寄生（只換萃取的 bitcell） | 讀出穩定最多 +48%、50% 延遲 +45–73%（.lib 用讀出穩定時間，× 1.6 涵蓋） |

都只在 tt 驗證。.lib 用的讀出穩定時間，誤差都偏保守；dout 開始變化（hold 弧）在延遲表兩個角偏晚 0.5–1.0%，也就是偏樂觀，由 × 0.9 涵蓋。原本寫「誤差方向都偏保守」說得太滿，2026-10-05 獨立審查更正，寄生的數字也由審查重算更正（原寫 +42%、+45–65%）。

## ss −40°C 讀取失敗

詳見 ADR-0010「ss −40°C 讀取失敗」。重點：
- 讀取失敗的條件：tt −40°C 1.60 V、ss −40°C 1.60–1.95 V，以及 **ss 25°C 1.60 V**（獨立審查發現，原本漏列；ss 60°C 1.60 V 正常，界線在 25–60°C 之間，沒有再模擬）。失敗方式是連續兩次讀到不同值時，讀成前一次的值。所以不只是低溫，ss 低電壓在室溫也會失敗。
- 原因已用 bit 0 的 sense amp 內部節點確認：sense amp 沒有自己的預充電電路，column mux 只有 NMOS，Vt 高時（低溫、慢製程）內部節點拉不回去。
- 用完整網表確認：ss −40°C 1.70 V 失敗的讀取和節點電壓都和修剪網表相同；1.60 V 在 169.7 ns 不收斂，之前的讀取全錯。
- 使用者決定（5）：這個 PVT 用佔位 .lib，列為頭號下線風險，Phase 6 自產 macro 要修正。使用者決定（8）：25°C 的失敗只改文件與風險說明，不再模擬找界線。

## 時序

harden-soc 跑了 3 次（開發目錄）：

| 次 | commit | 結果 | 處理 |
|---|---|---|---|
| 1 | `ccc536c` | `RepairDesignPostGPL` 75 分鐘後異常結束（正常約 40 秒） | 單步重跑 4 種 .lib：第一版卡住，延遲表與 hold 弧表一起攤平後正常，原因是負載斜率（等於 60–140 kΩ 的 driver）；改成每列取負載中的最大值（`3e9b011`），單步 52 秒（攤平版 98 秒的差別是機器負載）。這個 run 的目錄在第 2 次開跑時被 `run.sh` 刪掉，只剩 ADR-0010 的摘要 |
| 2 | `3e9b011`（42 ns） | min_ss_n40C setup −0.066 ns | 新的 hold 弧加上 resizer 0.3 ns 的 hold 餘量，在每個 `rdata_q` 的 D 前各插一顆 delay cell（`dlygate4sd3`，ss −40°C 1.17 ns），它也在 SRAM 半週期 setup 路徑上；推算不插時 ff 的 hold 仍有約 +0.18 ns（hold slack 減 delay cell 延遲，沒有拿掉 cell 重跑）。使用者決定改 43 ns（`edb7d63`）。這個 run 已被第 3 次覆蓋，數字來自當時的 STA 報告，沒有保存 |
| 3 | `edb7d63`（43 ns） | 只有 golden 比對 FAIL（預期）；其他 limits、`check_soc.py`、輸入、來源追溯全 PASS | 逐項檢視 148 個改變的值與 5 個新 key 後更新 golden（`50526cf`，`signoff/golden/soc_top/README.md`） |

43 ns 的結果（第 3 次，golden 來源）：
- 最差 setup +0.384 ns（min_ss_n40C，SRAM 半週期路徑）；ss 100°C +0.921 ns。
- 最差 hold +0.074 ns（max_ss_n40C：佔位 .lib 的 hold 弧取 ff 的值）。
- 功耗 9.24 mW，IR 7.88 mV（上限 20 mV）。

Phase 4 已知限制 1 的回答：
- ss 實測讀出穩定 5.7 ns × 1.6 = 9.1 ns，仍低於下限 15 ns。setup、週期、pulse width 都還是由 padded.lib 的下限決定，所以時序弧沒有因為實測而放寬。唯一放寬的是 dout0 的 `max_capacitance`：0.02756 → 0.05 pF（特性化過的最大負載）；最終版圖 `dout0[1]` 用到 0.031 pF，在舊 .lib 下會是 max cap 違規（ADR-0010「結果」）。
- 週期從 42 改成 43 ns，原因是新的 hold 弧，不是 SRAM 變慢。

dout0 transition 的敏感度（ADR-0010 已知限制 5）：在最終版圖只換 .lib 做 what-if，SRAM 半週期路徑的 slack（輸出存於 `runs/p35_whatif/`，2026-10-05 重跑，數字相同）：

| PVT | transition | slack |
|---|---|---|
| ss −40°C | 0.5 → 1.3 ns（tt 量到的最大值；這個 PVT 讀取失敗、沒有量測，ss 100°C 量到 1.22–3.15 ns，所以可能偏樂觀） | +0.38 → +0.03 ns |
| ss 100°C | 0.5 → 3.15 ns（50 fF 的最差值） | +0.92 → +0.17 ns |

仍 PASS，但餘量幾乎用完。

## Checker qualification

| 植入 | 預期抓到的地方 | 結果 |
|---|---|---|
| N1 sense amp 輸出加 100 fF | 讀出穩定時間至少 +0.2 ns | PASS（+0.72 ns） |
| N2 兩顆 bitcell 卡 0 | 讀取檢查 FAIL | PASS |
| N3 setup 搜尋的移動失效 | 搜尋報錯「passed everywhere」 | PASS |
| N4 網表少一顆 bitcell | 修剪數量檢查 | PASS |
| N5 `char.json` 少 pulse | `gen_char_lib` FAIL | PASS |
| N6 手改 .lib | `--check` STALE | PASS |
| N7 佔位 .lib 的來源也讀取失敗（先做正向對照） | `gen_char_lib` FAIL，指名 PVT 與來源 | PASS |
| N8 `char.json` 少一個 PVT | `gen_char_lib` FAIL | PASS |
| P04 `sram0` 延遲 × 10 | setup FAIL | PASS：`Checker.SetupViolations`，hook 印出 derate 10 |
| P17 .lib 的 hold 弧被改 | `check_inputs.py char_lib` | PASS：`check_inputs.py char_lib` |
| P20 MACROS 的 lib 指回 PDK 的 TT .lib | `check_inputs.py` | PASS：`check_inputs.py --resolved` |
| P30 某個 corner 讀到別的 PVT 的 .lib | `check_soc.py sram_lib` | PASS：`check_soc.py sram_lib`（nom_ff_n40C_1v95 讀到 tt 的 SRAM .lib；只有這一列 FAIL） |
| P32 hold 弧設成 0 | `Checker.HoldViolations` | PASS：`Checker.HoldViolations` |

N1–N8：commit `ccc536c` 上 8/8 PASS（22 分鐘，`runs/sram_char/neg_char2.log`）；`3e9b011` 改了 .lib 的表格形狀後，N5–N8 重跑 4/4 PASS（N1–N4 不經過 `gen_char_lib`；當時沒有保存 log，`6316ea9` 重跑並保存：`runs/sram_char/neg_char_n5n8_6316ea9.log`）。`neg-char` 的 N1–N4 要跑 ngspice（約 22 分鐘），所以不在 `make regress` 裡（已知限制 9）。

### Checker qualification 總表

regress 2 的結果。每一案都要在**預期的** checker FAIL，FAIL 在別處或沒 FAIL 都算該案沒抓到：

| target | 植入的錯誤 | 結果 |
|---|---|---|
| `neg-rtl` | RTL／firmware 的 bug | 33/33 |
| `neg-pnr` | PnR、STA、PDN、IR、DRC、XOR、擺放、輸入一致、golden、SRAM .lib（P00–P32，P00 是 positive control） | 33/33 |
| `neg-eqy-soc` | 最終網表改 1 處 | 9/9；位置交叉檢查 60 組 |
| `neg-eqy-core` | 同上，picorv32 | 11/11；位置交叉檢查 104 組 |
| `neg-gl-soc` | 網表植入錯誤（含帶電源網表） | 8/8 |
| `neg-gl-core` | picorv32 網表植入錯誤 | 2/2 |
| `neg-provenance` | 來源追溯 | 19/19 |
| `neg-run-guard` | 9 個下游步驟 × 3 種壞 run，加 positive control | 37/37 |
| `neg-regress` | `make regress` 本身 | 5/5 |
| `test-flow-retry` | GRT-0229 重試的判斷 | 7/7 |

合計 164 案（Phase 4 是 163 案，加上 P32）。`make py-check` 每次執行時先用兩段會出錯的程式做自我測試（未定義名稱、寫檔前先清空），沒抓到就 FAIL，不列入這個計數。不在 regress 裡的 `neg-char` N1–N8 見上一段。獨立審查另外找到 12 個沒有植入錯誤保護的漏洞，見「獨立審查」。

## 本階段找到並修正的 checker 問題

1. **N6 的植入什麼都沒改到**：要替換的字串在新 .lib 裡已不存在，N6 判 FAIL。改成編輯一定存在的 `timing_type : rising_edge;`，並檢查替換次數（`signoff-checker-qualification` 漏洞類型「植入沒有生效」）。
2. **N7 第一版抓到的原因不對**：本來要測「佔位來源也讀取失敗」，報錯的卻是來源 PVT 沒有佔位設定。改成一次列出所有 PVT 的問題，並要求訊息指名 ss −40°C 與它的來源。
3. **`gen_char_lib --check` 只比對 `char.json` 裡有的 PVT**：少一個 PVT 時，舊的 .lib 留在目錄裡不會被發現。改成必須剛好 5 個 PVT，並補 N8。
4. **P17 的植入程式先清空檔案再讀**：`open(f, "w").write(edit_once(open(f).read(), ...))`，Python 先執行 `open(f, "w")`，讀到的是空字串。植入點檢查（`edit_once`）因此報「找不到植入點」，P17 判 FAIL，而不是什麼都沒改就 PASS。`ccc536c` 改寫 P17 後沒有先跑過，到乾淨 checkout 的 `make regress` 第 1 次（`38e85cb`）第 19 個 target 才發現（18/25 PASS，neg-pnr 32/33）。修正：先讀再寫；`make py-check` 加這個寫法的檢查，舊版 `neg_pnr.py` 第 756 行被抓到、自我測試改錯時 FAIL；P00＋P17 在 regress 1 的 run 上 2/2 PASS；再用乾淨 checkout 重跑 regress（`flow-regression-reproducibility` 規則 9、經驗紀錄）。

## 與計畫不同的地方

1. **OpenRAM 環境沒有提前建**，改用本機 ngspice 量 PDK 的網表（ADR-0010；OpenRAM 環境留到 Phase 6）。
2. **ss −40°C 沒有實測 .lib**：macro 在那裡讀取失敗，用佔位 .lib（使用者決定 5）。
3. **週期 42 → 43 ns**（使用者決定，ADR-0004 Phase 3.5 補充）。
4. **dout0 延遲表不隨負載變化**：實測的斜率會讓 OpenROAD resizer 失控（ADR-0010「延遲表為什麼不隨負載變化」）。

## 已知限制（帶到後續階段）

1. **PDK 這顆 SRAM 在低溫、以及 ss 1.60 V 室溫時讀取失敗**：頭號下線風險（ADR-0010 已知限制 1）。ss 25°C 不是 STA corner，STA 完全看不到。Phase 6 自產 macro 要修正讀取電路，並在 5 個 PVT 與中間溫度驗證讀寫。
2. **走線寄生沒有模擬**：只用 × 1.6 補，依據是只換 bitcell 的試驗（ADR-0010 已知限制 2）。
3. **萃取網表無法模擬**（Timestep too small），以及**換上萃取 bitcell 後寫入失敗**（ADR-0010 已知限制 3、4）：Phase 6 用 OpenRAM 環境確認。
4. **dout0 transition 兩個模型差 5 倍**：用電路圖的值，43 ns 的半週期路徑餘量幾乎用完（見「時序」一節）。
5. **沒有 Monte Carlo、只在 bit 0／31 量時序、port 1 與功耗沿用 PDK 解析值、沒有矽量測對照**（ADR-0010 已知限制 6–9）。
6. **修剪後的功能檢查偏悲觀**：bit 1–30 的 bitline 只有 2 顆 bitcell（ADR-0010 已知限制 10）。
7. **誤差驗證只在 tt 做過**；其他 PVT 的步長與修剪誤差沒有量。
8. **resizer 的 hold 餘量與半週期路徑互相衝突**：0.3 ns 的 hold 餘量會在 `rdata_q` 前插 delay cell。設計再變大或週期再壓時，要先處理這點（`drv-timing-closure` 經驗紀錄 2026-10-05）。
9. **`neg-char` 不在 `make regress` 裡**：改特性化腳本或 `gen_char_lib.py` 後要手動跑 `make neg-char`。
10. **新的 `GRT-0243` 警告**：antenna 修補時有一條 net 用 diode 修不掉；修補後與繞線後的檢查都是 0 個違規（golden README）。
11. **繞線器中間各輪的 key**：這次多跑到第 7 輪，golden 的 key 跟著變；如果之後輪數不同，比對會 FAIL（Phase 4 已知限制 13 仍在）。
12. Phase 4 已知限制 2–13 不變（duty cycle 與 jitter 假設、IR 供電位置、溫度反轉 corner 不給 resizer 看等）。
13. **hold 弧的值和週期有關**：週期 10–16 ns 時，「讀之後接寫」的 dout 比 .lib 的 hold 弧早變化；20 ns 以上晚於 .lib。43 ns 依趨勢安全，但沒有直接模擬（ADR-0010 已知限制 11）。
14. **dout0 最小負載 3.35 fF 低於特性化的 5 fF**，STA 不會警告（ADR-0010 已知限制 12）。
15. **ss −40°C 的讀取失敗只在 20 ns 週期判定**（ADR-0010 已知限制 13）。
16. **獨立審查找到 12 個 checker 漏洞**（見「獨立審查」），沒有一個讓這次結果變成假 PASS；Phase 5 開頭與 `run.sh` 的修改一起修（使用者決定 7）。（2026-10-05 補記：已在 Phase 5 開頭修正，紀錄見 `docs/phase_exit/phase5.md`。）

## 使用者決定

2026-10-04：
1. 本機 ngspice 直接量 PDK 的網表；OpenRAM 環境留到 Phase 6。

2026-10-05：
2. 餘量取保守值：延遲、週期、pulse width × 1.6，setup/hold + 0.1 ns，padded.lib 的值當下限；hold 弧 × 0.9。
3. 換上萃取 bitcell 後寫入失敗：記為已知限制，Phase 6 確認。
4. dout0 transition 維持 0.5 ns。
5. ss −40°C 讀取失敗：用佔位 .lib，列為下線風險。
6. 時序收斂：週期 42 → 43 ns。
7. 獨立審查的 12 個 checker 漏洞：以乾淨 checkout 的 regress 2 結案，漏洞列為已知限制，Phase 5 開頭和 `run.sh` 的修改一起修。
8. ss 25°C 1.60 V 也讀取失敗：只改文件與風險說明，不再模擬找界線，Phase 6 確認。
9. `run.sh` 重跑會刪掉上一次 run：改成搬走，留到 Phase 5 開頭（避免 Phase 3.5 的 regress 重跑）。

## 獨立審查

2026-10-05，regress 2 執行期間請兩個沒參與實作的 agent 反向檢查。兩者都限定只讀檔案、只做幾秒內的小實驗，以免拖慢有牆鐘時限的 gate-level 模擬。

**文件核對**：約 90 項核對正確，包括特性化結果表、.lib 數值與公式、golden 差異筆數、harden 3 的 slack／功耗／IR、43 ns 的 uncertainty 拆解、ss −40°C 的節點電壓。找到的問題都已更正：

- 寫錯 6 項：
  - **ss 25°C 1.60 V 的讀取失敗漏列**：32 個 bit 全錯，含 bitline 完整的 bit 0、31。我用審查的腳本重算波形確認。原因是整理時把它和 ss 25°C 1.80 V（只有修剪的 bit 錯）混在一起；「只有低溫失敗」因此不成立，下線風險改寫（使用者決定 8）。
  - 「實測加餘量都低於下限」漏了 ss 100°C 的 hold（0.53 > 0.5 ns）。
  - ADR 的 ff hold 弧範圍寫錯。
  - PDK .lib 的最小週期範圍是 0.091 ns 起，原寫 0.119 ns。
  - char README 寫 N1–N6，實際是 N1–N8。
  - 寄生的數字：讀出穩定最多 +48%、50% 延遲 +45–73%，原寫 +42%、+45–65%。我排除失敗的讀取後重算確認。
- 說得不準確 11 項：
  - dout0 `max_capacitance` 從 0.02756 放寬到 0.05 pF 沒有寫；我在 STA 報告確認最終版圖 `dout0[1]` 用到 0.031 pF。
  - 「誤差都偏保守」：hold 弧在兩個角偏樂觀 ≤ 1%。
  - 修剪的 +2.0% 是用早期 508 顆的網表、量的是 50% 延遲。
  - resizer 實驗的 98 對 52 秒其實是機器負載，而且兩張表是一起攤平的。
  - hold buffer 淨增 27，不是「插一顆」：每個 `rdata_q` 各一顆。
  - what-if 的 ss −40°C 用的是 tt 的 transition。
  - `cts-clock-tree` 的 clock 到達差歸因不完整。
  - 「不插 delay cell 時 ff hold +0.18 ns」是推算。
  - `signoff-criteria` 沒有餘量的推導：已補。
  - 3 份文件停在 Phase 4。
  - 幾處編號與措辭。
- 找不到證據 5 項：
  - what-if 的輸出沒存：重跑後數字相同，存到 `runs/p35_whatif/`。
  - N5–N8 改表格後的結果沒有 log：重跑 4/4 PASS 並保存。
  - harden 1、2 的 run 已被 `run.sh` 刪掉：文件標明數字來自當時的報告（`librelane-run-debug` 規則 6）。
  - 「Phase 4 同一步 44 秒」：證據是 42 秒，改寫成約 40 秒。
  - Phase 4 的 dout0 負載：改用 Phase 3.5 的數字。

**找 checker 漏洞**：找到 12 項，每項都實際做出壞掉的輸入、跑 checker、看到判 PASS。沒有一項讓這次的結果變成假 PASS，審查用三個實驗確認：

- 另寫、不 import `gen_char_lib` 的程式從 `char.json` 重算 5 份 .lib，全部一致；
- 用 committed 的程式與快取的波形重播 `char.json`，逐位相同；
- golden run 的每個 STA corner 都只讀進兩份 .lib（std cell 與自己 PVT 的 SRAM）。

使用者決定（7）：列為已知限制，Phase 5 開頭與 `run.sh` 的修改一起修。

| # | 漏洞 | 嚴重度 | 本次有沒有中招 | Phase 5 的修法與 negative test |
|---|---|---|---|---|
| 1 | `check_soc.py sram_lib` 只認 `Reading cell library` 一種 log 訊息、只比路徑結尾；經 `EXTRA_LIBS` 或 `LIB` 多讀一份 SRAM .lib，`sram_lib` 與 `check_inputs.py` 都 PASS | 中 | 沒有：15 份 sta.log 都剛好 2 行 lib，`EXTRA_LIBS` 是 None | 抓所有 lib 行，打開檔案看哪些定義 SRAM cell，必須剛好一份且 realpath 相符；check_inputs 要求 `EXTRA_LIBS` 空、`LIB` 不含 SRAM。P30、P19、P20 各加變體 |
| 2 | `char.json` 某個 PVT 的紀錄換成別的 PVT，`gen_char_lib` 與 `check_inputs` 都 PASS（hold 弧樂觀 0.4 ns） | 中 | 沒有：5 筆紀錄的製程、電壓、溫度都對 | 每筆的 `pvt`、model、vdd、temp 要等於 `sramchar.PVTS`。新增 N9 |
| 3 | `gen_char_lib` 的公式錯（攤平取最大／最小弄反、佔位 hold 弧不取最小、少乘 1.6、少乘 0.9），N5–N8 與 `--check` 都 PASS | 中 | 沒有：獨立重算 5/5 一致 | 獨立重算放進 check_inputs，或每格不同、高過下限的測試資料；5 種改壞都必須 FAIL |
| 4 | `char.json` 的來源欄位（網表 sha256、PDK、ngspice 版本、修剪數、步長）沒有人檢查 | 低～中 | 沒有：網表 sha256、PDK hash、ngspice 47、1264 都對 | 比對這些欄位。新增 N10 |
| 5 | NaN、pass < fail 都被接受（NaN 經 `max()` 變成下限，或寫進 .lib） | 低 | 沒有 | 數值有限、pass > fail、差 ≤ 解析度、表格維度。新增 N11 |
| 6 | 替換次數只數總和：PDK template 的格式稍變時，clk0 pulse width 留在 PDK 值；某支 pin 少一個 setup 弧而另一支多一個也 PASS | 低（只在 PDK 升級時） | 沒有 | 每支 pin、clk0 rise／fall 各自計數 |
| 7 | 二分搜尋只在探到的點檢查單調，有「PASS 窗口」時回傳錯的值；最終 .lib 採用的值沒有再模擬確認 | 低 | 沒有：值都由下限決定；重播 4 個 PVT 結果相同 | 在 .lib 採用的值上各做一次確認模擬 |
| 8 | 模擬快取不確認上次 ngspice 成功；波形太短時讀取一律判對 | 低 | 沒有：198 個快取的 log 都沒有錯誤；重新量測差 0 | 有完成標記才重用；波形要涵蓋檢查時間點 |
| 9 | 特性化部分 PVT 失敗時，`char.json` 留下新舊混合的紀錄 | 低 | 沒有：5 筆都能重播 | 有失敗就不寫檔；每筆記程式 hash |
| 10 | 新的 py-check「先清空再讀」只抓到 17 種寫法中的 5 種（例如 `with`、分兩行、`io.open`） | 低 | 沒有：較寬的掃描在 45 個 .py 找到 0 處 | 支援 `file=`、attribute 形式、`with` 陳述式；變體加進自我測試 |
| 11 | 斷言太寬：P17 在 char 目錄多一個 `.DS_Store` 也判成立；N8 的名稱一定出現在清單裡；N7 不檢查佔位 hold 弧的值；P32 沒有 positive control | 低 | 沒有 | 斷言訊息含 STALE 與檔名；解析缺少的 PVT；N7 比對 hold 弧；P32 加 positive control |
| 12 | `sram_lib` 單獨使用時只比路徑結尾（另一個 checkout 的同名檔 PASS；`check_inputs --resolved` 會擋） | 低 | 沒有 | 併入第 1 項 |

審查另外指出三點，不是 checker 漏洞，但會影響 .lib 的適用範圍，已列為 ADR-0010 已知限制 11–13（本文件已知限制 13–15）：hold 弧和週期有關、實際最小負載低於特性化範圍、ss −40°C 的讀取失敗只在 20 ns 週期判定。

## Skill 分析（`phase-exit-review` 規則 8）

本階段的重大任務與對應的 skill：

| 任務 | skill | 寫回 |
|---|---|---|
| SRAM 的 SPICE 特性化、.lib 產生、特性化的植入錯誤 | `openram-macro-characterization`（Phase 3.5 開始時新建，CLAUDE.md 規則 7） | 規則 1–15（規則 1–8 在 Phase 3.5 開始時寫；規則 15 是搜尋範圍不涵蓋真值時往外找的方法）、經驗紀錄 15 列 |
| 讀取失敗的電路層除錯（量 sense amp 內部節點、完整網表確認） | 同上 | 規則 13；不另建 skill：步驟（探測節點、短模擬確認名稱、修剪與完整網表比對）都是特性化的一部分 |
| 把特性化 .lib 接進 SoC（每個 PVT 一份、佔位 .lib、輸入檢查） | `hard-macro-integration`、`multicorner-sta` | 整合清單第 5 項、view 表、negative test；P30 與 hook |
| `repair_design` 失控的除錯 | `librelane-run-debug`、`drv-timing-closure` | `librelane-run-debug` 經驗紀錄（log 有緩衝、用 `sample` 與單步重跑判斷）與規則 6（重跑前保存失敗的 run：第 1 次 harden 的 run 目錄被 `run.sh` 刪掉）；`drv-timing-closure` 規則 10（resizer 停不下來時也查 macro .lib）與「退回過的做法」1 列；原因寫在 `openram` 規則 14 |
| hold 弧造成的 setup FAIL、週期改 43 ns | `drv-timing-closure`、`cts-clock-tree` | 經驗紀錄各 1 列 |
| 餘量的決定（× 1.6、下限、hold 弧） | `signoff-criteria` | 「實作範本」1 列；推導表加「macro 的 SPICE 特性化值」1 列（獨立審查發現原本沒寫推導） |
| 植入錯誤 N6–N8 的漏洞與 golden 更新 | `signoff-checker-qualification` | 「植入沒有生效」的例子、經驗紀錄 |
| 週期與合成 | `rtl-synthesis-lint` | 開頭的週期說明 |
| 乾淨 checkout 的 regress | `flow-regression-reproducibility` | 規則 9（改過的 negative test 先單獨跑；`make py-check` 加「寫檔前先清空」）、規則 10（等長 run 用 PID）、經驗紀錄 2 列 |
| 收尾 | `phase-exit-review` | 經驗紀錄 |

沒有更新的 skill 與理由：`antenna-signoff`（新的 `GRT-0243` 最後沒有留下違規，記在 golden README）、`drc-signoff`、`lvs-signoff`、`pdn-ir-drop`、`floorplan-congestion`（結果與 Phase 4 相同或只隨週期微變）、`timing-constraints-sdc`（SDC 沒改，週期由 config 帶入）、`formal-equivalence-eqy`、`gate-level-simulation`、`dv-directed-tests`（RTL 與網表功能沒變，只在 regress 重跑）。README 的 skill 說明與 `description` 已隨規則改動同步，`make skill-check` PASS。

## 交付物

- `ip/sram/char/`：`sramchar.py`、`characterize.py`、`gen_char_lib.py`、`neg_char.py`、`extract_sram.py`、`README.md`
- `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/char/`：`char.json` 與 5 份 `.lib`
- `pnr/soc_top/`：`config.json`（MACROS lib、43 ns）、`check_inputs.py`、`check_soc.py`、`neg_pnr.py`（P32）、`sta_extra_corner.tcl`
- `signoff/golden/soc_top/`（`metrics.json`、`README.md`）、`signoff/limits/soc_top.toml`
- `scripts/check_py_names.py`（`make py-check` 加「寫檔前先清空」的檢查）
- ADR-0010（新）、ADR-0004 補充、ADR-0007 標為已取代
- skill：`openram-macro-characterization`（新，規則 1–15）；`hard-macro-integration`、`drv-timing-closure`、`cts-clock-tree`、`multicorner-sta`、`signoff-criteria`、`signoff-checker-qualification`、`librelane-run-debug`、`flow-regression-reproducibility`、`rtl-synthesis-lint` 更新
