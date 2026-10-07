# ADR-0015：golden 比對允許版圖數量與面積的小誤差（`[golden_layout_tolerance]`、`[golden_optional]`）

- 狀態：已採用（2026-10-07，使用者決定「改 golden 規則」，兩個 CPU 都改）；等 Hazard3 第 8 次 harden 確認
- 背景：Hazard3 版的 golden 由第 5 次 harden 建立（`signoff/golden/soc_top_hazard3/`）。第 6、7 次 harden 用相同的 flow 設定，signoff 全部 PASS，但 golden 比對都 FAIL：第 6 次 61 個 metric 不同，第 7 次 11 個不同，其中包含 cell 數、diode 數、面積。原規則（`signoff-checker-qualification` 規則 5）的前提是「不可重現的只有多執行緒 detailed routing，而且它只改變連續量與中間輪的 DRC 數」，所以數量與面積一律不給誤差。

## 原因（已驗證）

兩個不可重現的來源，都會改變數量：

1. **第 41 步 `RepairDesignPostGRT` 最後一次 `global_route`**：修完的 DEF 相同，global routing 的結果偶爾不同。用同一份輸入單步重跑：合計 27 次裡 22 次與 golden 相同，其餘 5 次分成 3 種結果；沒有一次出現 `GRT-0229`（同一個呼叫已知會隨機中止，`librelane-run-debug`）。之後的 antenna 修補（找到的違規 109 對 103）、`ResizerTimingPostGRT`、detailed routing 全部跟著改變。第 6 次 harden 就是這種情況。
2. **第 46 步 detailed routing（10 個執行緒）**：第 7 次 harden 第 44 步以前與 golden 完全相同。detailed routing 後的 antenna 修補前兩輪也相同，第 2 輪後重繞剩 1 個違規（golden 剩 0），多跑一輪、多插 1 顆 diode。PicoRV32 版 Phase 4 只看過它改變中間輪的 DRC 數。

## 量測

golden（第 5 次）對 4 組 run：第 6 次 harden、第 7 次 harden，以及兩組「從第 41 步重跑得到的不同結果」接著跑完後面所有步驟的 run（p5h3 worktree `runs/exp_t41_r4`、`runs/exp_t41_r17`，各約 23 分鐘，metrics 在各自目錄的 `metrics.json`）。

| metric | 最大差異 | 誤差 |
|---|---|---|
| setup／hold slack（含各 corner、r2r） | 0.040／0.063 ns | 0.2／0.32 ns |
| skew | 0.048 ns | 0.25 ns |
| 繞線總長、中間輪線長、最長線、估計線長、global routing 線長 | 0.101%、0.117%、0.297%、0.046%、0.086% | 約 5 倍（rel） |
| via、功耗、power grid、IR | 0.064%、0.060%、0.040%、0.108% | 約 5 倍（rel） |
| detailed placement 位移 | 14% | 70% |
| 中間輪的 DRC 數 | 262（原誤差 ±100） | ±1310 |
| antenna diode 數／antenna cell 數 | 11（golden 100）／13 | ±55／±65 |
| stdcell 數／面積 | 14（30,474 顆）／42 µm² | ±70／±210 µm² |
| 全部 instance 數、fill cell 數 | 6、17 | ±30、±85 |
| timing repair buffer 數／面積、setup buffer 數 | 6／30 µm²、2 | ±30／±150 µm²、±10 |
| utilization（全部／stdcell） | 0.000055／0.000088 | ±0.0003／±0.00045 |
| 繞線 net 數、最後一次 global routing 的 via 數 | 6、63 | ±30、±320 |

一邊有、一邊沒有的 key：`route__drc_errors__iter:6`、`:7` 與對應的線長（繞線器跑 5 輪或 7 輪）、`flow__warnings__count:RSZ-0062`（`ResizerTimingPostGRT` 剩一個違規）、`flow__warnings__count:GRT-0243`（antenna 修補有一條線用 diode 修不掉）。

## 決策

1. `check_signoff.py` 新增兩個表：
   - `[golden_layout_tolerance]`：只給會隨繞線變動的數量與面積。pattern 只要碰到 `[equal]` 的 key，或名稱含違規、錯誤類字眼的 metric（`VIOLATION_WORDS`：violat、_vio_、error、drc、lvs、xor、unannotated、disconnected、unmapped、illegal、lint、latch），checker 就判 FAIL。
   - `[golden_optional]`：可以只出現在一邊的 key，限於每輪的 key（含 `__iter:`）與個別 warning 的計數（`flow__warnings__count:<id>`），不能碰 `[equal]` 的 key。兩邊都有時照常比對。
   - 原本的 `[golden_tolerance]` 仍只給連續量，仍拒絕 count／area。
2. 誤差的訂法：**實測最大差異的約 5 倍**。原規則 5 的「實測差異的 30–200 倍」是針對 PicoRV32 那種很小的繞線雜訊；Hazard3 的差異大得多，照 30 倍訂的話，slack 誤差會到 1.9 ns，等於不比。5 倍是在「4 組樣本可能低估」與「仍抓得到設定或工具改變」之間的取捨。
3. Hazard3（`signoff/limits/soc_top_hazard3.toml`）用上面的數字。PicoRV32（`signoff/limits/soc_top.toml`）兩個新表**暫用 Hazard3 的數字**，原本的 `[golden_tolerance]`（PicoRV32 Phase 4 的實測）不動；PicoRV32 在新設定（ADR-0014）重跑時，用它自己的 run 重新量測並更新。
4. 違規數、DRC、LVS、antenna、slew／cap、setup／hold 違規、unannotated 等仍必須與 golden 完全相同（多數也由 `[equal]` 鎖在 0 或固定值）。

## negative test（`pnr/soc_top/neg_pnr.py`）

- P50：stdcell 數 golden + 誤差 → PASS，+ 誤差 + 1 → FAIL；上限檔加一個會碰到違規計數的 pattern（`"*__count"`）→ FAIL。
- P51：拿掉最後一輪的 `route__drc_errors__iter:N` → PASS；拿掉一般的 key（`design__instance__count__class:inverter`）→ FAIL；`[golden_optional]` 加 corner key 的 pattern → FAIL。
- P31 改成從上限檔讀中間輪 DRC 的誤差（Hazard3 1310、PicoRV32 100），最終 DRC 數 +1 仍 FAIL。P12（instance 數 −10%）不變。
- 兩個 CPU 各跑一次 P12、P31、P50、P51：8 個全部抓到（2026-10-07，Hazard3 用第 7 次 run，PicoRV32 用 Phase 4 golden run）。

## 影響與限制

- golden 抓不到「誤差範圍內」的改變：例如 stdcell 數少於 70 顆的變化、slack 小於 0.2 ns 的變化。單看一個 metric 不夠：ADR-0014 的改動只讓 stdcell 多 60 顆（在誤差內），但 max_ss_n40C setup 從 −1.131 變成 +0.636 ns，仍會被抓到。一個改動如果所有 metric 都只動在誤差內，golden 就抓不到。
- 誤差只用 5 組 run 訂出來，之後的 run 可能超出。超出時要先查是不是真的改變，不能直接加大誤差（`signoff-checker-qualification` 規則 5 的分類方法仍適用）。
- 不可重現的根因（global routing 偶發不同、detailed routing 多執行緒）沒有解決；`DRT_THREADS=1` 能不能讓 detailed routing 可重現沒有試過。
- 4 組 run 的 signoff 全部 PASS；第 4–7 次 harden 的最差 setup 在 +0.529～+0.556 ns 之間（44 ns）。

## 出處

- 第 6、7 次 harden 的 `criteria_review.md`（p5h3 worktree `runs/p5_h3_h6_signoff/`、`runs/p5_h3_h7_signoff/`）
- `signoff/golden/soc_top_hazard3/README.md` 可重現性一節
- skill `flow-regression-reproducibility`、`signoff-checker-qualification`、`librelane-run-debug` 的經驗紀錄
