# signoff criteria 檢查：Hazard3，Phase 5 結案的乾淨 `make regress`（commit `71b1454`）

- run：`../arvinsa-rtl-gds-p5final_h3/runs/soc_top_hazard3`，2026-10-08，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`
- 整體結果：`harden-soc: PASS`；整份 regression `regress: PASS 21/21`

## 有沒有被執行

- 腳本 6 項都 PASS：
  - config 42 個設定生效；
  - 78 個 step config 一致；
  - `uncertainty` 與 `uncertainty_applied`（50,670 條路徑）都 PASS；
  - corner 齊全；
  - 5 個 checker 都有結果行。
- `check_signoff.py` PASS：golden 436 個**完全相同**。
- `ir_worst.py` PASS：14.13 mV。
- `check_soc.py`、`check_inputs.py --resolved`、`provenance.py` 都 PASS。

## 合不合理

數字與 golden 來源完全相同：setup +1.114、hold +0.109 ns，最壞組合 IR 14.13 mV。判斷同來源 run（`p5h3/runs/p5_h3_pdn`）的 review，沒有新資料。

## 學習

- 新 golden 在乾淨 checkout 第二次重現：第一次是 `5aaf036`，有 14 個連續量在誤差內；這次完全相同。
- 沒有新的製程數字。
