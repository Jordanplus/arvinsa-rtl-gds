# signoff criteria 檢查：PicoRV32 單獨 harden，Phase 5 結案的乾淨 `make regress-picorv32`（commit `71b1454`）

- run：`../arvinsa-rtl-gds-p5final_pico/runs/picorv32_core`，2026-10-08，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`。這是第一次由 `pnr/picorv32_core/run.sh` 自動跑（`--design picorv32_core`，Phase 5 獨立審查後加的）。
- 整體結果：`harden-core: PASS`

## 有沒有被執行

- 腳本 5 項都 PASS：
  - config 13 個設定生效；
  - 77 個 step config 一致；
  - `uncertainty_applied`：9 個 corner 共 18,000 條路徑都是 0.25 ns（`CLOCK_UNCERTAINTY_CONSTRAINT`）；
  - corner 齊全；
  - 4 個 checker 都有結果行。
- core 沒有自己的 SDC，所以沒有 `uncertainty` 那一列。
- `check_signoff.py` PASS：golden 325 個**完全相同**。之前兩次 Phase 5 的 run 都有 71 個在 Phase 2 訂的誤差內，這次一個都沒有。

## 合不合理

setup +6.175、hold +0.039 ns，與 golden 相同；判斷同預跑那次的 review。

## 學習

- 規則 9 在 core harden 上第一次自動把關，Stop hook 也會檢查。
- 沒有新的製程數字。
