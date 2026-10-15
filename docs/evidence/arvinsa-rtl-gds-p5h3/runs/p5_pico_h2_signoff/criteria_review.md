# signoff criteria 檢查：PicoRV32，ADR-0016 第 1 次正式 harden（LibreLane 中止）

- run：`../arvinsa-rtl-gds-p5h3/runs/p5_pico_h2`（跑的時候 tag 是 `soc_top`，之後改名）（commit `adac1a9`，自訂 CTS step `Arvinsa.CTSNoInsertionDelay`），2026-10-07；log `runs/p5_pico_harden2.log`，約 7 分鐘
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: FAIL`（`uncertainty` 只缺 signoff STA、`signoff_corners` 沒有任何 corner：LibreLane 沒跑到 signoff）
- 整體結果：`harden-soc: FAIL`

## 有沒有被執行

LibreLane 在第 44 步 `OpenROAD.ResizerTimingPostGRT` 中止：`[ERROR GRT-0229] Vertical edge usage exceeds the maximum allowed. (79, 0) usage=65534 limit=2200`。之後的 checker 都是因為 metric 缺漏而 FAIL（`<missing>`），不是設計違規；`provenance`、`soc-inputs` PASS。

- `config_applied`、`step_config` PASS（44 個 step config）。
- `uncertainty`：第 35 步自訂 CTS step 的 log 找得到 `clock_uncertainty.sdc` 那一行（`review_criteria.py` 依 `substituting_steps` 找到 `35-arvinsa-ctsnoinsertiondelay`）；只缺 signoff STA。
- 第 35 步 log 有 `[INFO] arvinsa: clock_tree_synthesis -no_insertion_delay`；CTS 輸出與接續實驗 D 的 DEF 相同（PicoRV32 已比對）。

## 合不合理

沒有 signoff 數字可以判斷；criteria 沒有變。

## 學習

- GRT-0229 的隨機中止也會出現在 `ResizerTimingPostGRT`（ADR-0014 開的 step）；PicoRV32 同一份輸入單步重跑 4 次，1 次中止、3 次通過（`docs/notes/grt0229_repro.md`）。重試規則原本只認 `RepairDesignPostGRT`，已擴大並更新 `make test-flow-retry`（`librelane-run-debug`）。
- 沒有新的製程數字，knowledge 檔不需要新增。
