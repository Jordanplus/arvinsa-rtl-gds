# signoff criteria 檢查：PicoRV32 SoC，Phase 5 結案的乾淨 `make regress-picorv32`（commit `71b1454`）

- run：`../arvinsa-rtl-gds-p5final_pico/runs/soc_top`，2026-10-08
  - 第 44 步 `ResizerTimingPostGRT` 遇到 GRT-0229，重試從該步接續一次（`retries.txt`）
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: PASS`；整份 regression `regress: PASS 26/26`

## 有沒有被執行

- 腳本 6 項都 PASS：
  - config 41 個設定生效；
  - 79 個 step config 一致，含重試留下的中斷目錄；
  - `uncertainty_applied` 30,000 條路徑；
  - corner 齊全；
  - 5 個 checker 都有結果行。
- `check_signoff.py` PASS：golden 435 個**完全相同**，連版圖數量都和 golden 來源相同（diode 100）。
- `ir_worst.py` PASS：5.72 mV。
- 其他 checker 都 PASS。

## 合不合理

- setup +0.789、hold +0.080 ns，與 golden 相同。
- 新訂的版圖誤差（4 個樣本最大差異 × 5）這次沒有用到。

## 學習

PicoRV32 加寬 met5 之後，6 次 run 的版圖只出現兩種結果：
- 3 次和 golden 相同：golden 來源、這次、以及另一次；
- 3 次差 1 顆 diode。

接續重試不影響結果。
