# criteria review：Hazard3 soc_top（Phase 6 結案 regress 第 1 次，commit 904e18e，乾淨 worktree）

結果：harden-soc **FAIL**，只因 `soc-inputs` 的 `resolved` 列 FAIL；其他 checker 全部 PASS。

## 有沒有被執行

- signoff、soc-checks、ir-worst、provenance、criteria-review 都有結論列，PASS。
- golden 比對：441 個 metric 逐項相同，0 個在誤差內、0 個不同。
- `soc-inputs`：`resolved` 列 FAIL。原因是 checker 的 bug，不是 run 的問題。`37c99b4` 在 `macro_source` 區塊把變數 `files` 改成 view 檔名的字典，後面 `resolved` 拿它去比 RTL 檔案清單，所以每個 run 都 FAIL。修正版在這個 run 的 resolved.json 上 PASS，見 `docs/phase_exit/phase6.md`「與計畫不同的地方」。

## 合不合理

- 最差 setup +0.656 ns（min_ss_n40C_1v60，SRAM 半週期路徑），最差 hold +0.126 ns（min_ff_n40C_1v95），和 golden 相同。
- hold：GRT 最後修到 +0.133 ns，差 0.007 ns，小於 GRT_RESIZER_HOLD_SLACK_MARGIN 0.05。這和 golden 一樣，不是新現象。
- clock skew metric（hold）-0.688 ns（nom_ff_n40C），和 golden 相同；cts-clock-tree 經驗紀錄已有一列。
- 最差 IR：15.91 mV（max_ff_100C），在 20 mV 預算內。

## 學習

- 這次的數字和 golden 逐項相同，沒有新的製程數字要寫進 knowledge 檔。
- checker 的某個模式只有植入錯誤的案例在跑，checker 改壞成永遠 FAIL 時看不出來。已寫進 signoff-checker-qualification 的漏洞類型表，neg-pnr P00 加上 `check_inputs.py --resolved` 必須 PASS。
