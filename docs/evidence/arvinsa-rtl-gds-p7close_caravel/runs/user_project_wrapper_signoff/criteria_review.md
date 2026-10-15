# criteria review：user_project_wrapper（Phase 7 結案 regress，乾淨 worktree `p7close_caravel`，2026-10-14）

run：worktree `arvinsa-rtl-gds-p7close_caravel` 的 `runs/user_project_wrapper`，commit `84fe505`（Phase 7 步驟 8；wrapper 的 RTL、config、SDC 與 `550869c` 的確認 harden 相同，之後改的是 checker、negative test 與 regress 清單），`make regress-caravel` 的 `harden-caravel`，236 分鐘（與另外兩條 regress 同時跑，本機 swap 約 3 GB；單獨跑時 182 分鐘），console `runs/p7close_regress_caravel.console`（主目錄）。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS，與 `550869c` 那次相同：config_applied 57 個設定、step_config 78 個步驟、uncertainty（8 個時序步驟、15 個 signoff corner）、uncertainty_applied 50,670 條路徑、signoff_corners 15 個、checkers_ran。最後一行：`criteria-review: PASS`。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：
- `check_signoff.py`：golden 455 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py` 13 項 PASS：max_slew 15 個 corner 共 5,775 個違規全在 Caravel 直接驅動的邊界 net（最多比外部 transition 多 0.001 ns，容許 0.05 ns，決定 16）；pulse_width 最差 9.32 ns（`u_soc.sram0/clk0` low）；magic_drc SRAM 外 0 個，框內 5,572,955 個全部對得上 SRAM 單獨檢查的位置。
- `ir_worst.py` PASS：max_ss_100C 4.94 mV、max_ss_n40C 4.68 mV（上限 20 mV）；Caravel pad 起算的 pattern IR 由同一條 regress 之後的 `make ir-caravel` 判。
- `provenance.py --verify`：開始與結束都是 `84fe505`，工作樹乾淨。沒有重試（沒有 `retries.txt`）。

「不分析的項目清單」：與 `550869c` 那次相同（含 `ef_decap_12` 沒有 .lib，漏電不計）。

## 合不合理

所有 metrics 與 golden（`550869c` 的確認 harden）逐值相同，各 criterion 的判斷沿用 `runs/p7_decap_signoff/criteria_review.md` 與 `runs/p7_decap_confirm_signoff/criteria_review.md`（主目錄）：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold | setup +0.548 ns（min_ss_n40C，SRAM 半週期路徑）、hold +0.187 ns（max_ff_100C） | 依據仍成立。dout0 transition 改成量到的值後 setup 剩 +0.151 ns（`runs/p7_exit_draft/dout0_whatif.md`，主目錄），列入 exit review 的已知限制 |
| hold repair 餘量 | GRT 後修完 +0.207 ns，signoff +0.187 ns，落差 0.020 ns（餘量 0.2 ns，決定 17） | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −3.598 ns | 依據需補充：Phase 7 的分析（`runs/p7_skew_analysis/README.md`）顯示約 2.7 ns 是報表把 source latency 差與共同路徑 derate 算成扣分（推測，沒讀 OpenSTA 原始碼）；真正多出來的是 `wb_clk_i` 到 clock root 約 1.9 ns。暫不改 checker，寫進 exit review |
| golden 誤差 | 0 個落在誤差內 | 這是 wrapper 第三組逐值相同的比較（`f721cff`→`f4ea9de`、`7eff65a`→`550869c`、`550869c`→這次；`7eff65a` 改了 fill，golden 依程序更新），全部在同一台機器；誤差的處理寫在 exit review（決定 22） |

## 學習

- wrapper 在乾淨 worktree 逐值重現 golden，並且是與另外兩條 regress（soc_top 的 harden、EQY 等）同時跑；負載只讓時間從 182 分鐘拉長到 236 分鐘，沒有改到結果。
- 沒有新的工具行為，沒有依據不成立的 criterion。knowledge 檔不追加新的數字。
