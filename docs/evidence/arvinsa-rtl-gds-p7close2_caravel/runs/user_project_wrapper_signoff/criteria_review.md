# criteria review：user_project_wrapper（Phase 7 結案 regress 第二輪，乾淨 worktree `p7close2_caravel`，2026-10-15）

run：worktree `arvinsa-rtl-gds-p7close2_caravel` 的 `runs/user_project_wrapper`，commit `2b04451`（審查修正後；wrapper 的 RTL、config、SDC 與 `550869c` 的確認 harden 相同，`2b04451` 改的是 checker、negative test、註解與文件），`make regress-caravel` 的 `harden-caravel`，286.6 分鐘（與另外兩條 regress 同時跑；第一輪 236 分鐘、單獨跑 182 分鐘），console `runs/p7close2_regress_caravel.console`（主目錄）。

執行期間（約 03:33–03:45）磁碟一度只剩 0.8 GiB，同時跑的 PicoRV32 regress 因此 FAIL（`flow-regression-reproducibility` 經驗紀錄 2026-10-15）。這次 run 的 `flow.log`、`warning.log` 沒有 `No space left`，而且 455 個 metrics 與 golden 逐值相同，判斷沒有受影響。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：config_applied 57 個設定、step_config 78 個步驟、uncertainty（8 個時序步驟、15 個 signoff corner）、uncertainty_applied 50,670 條路徑、signoff_corners 15 個、checkers_ran。最後一行：`criteria-review: PASS`。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：
- `check_signoff.py`：golden 455 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py`：
  - max_slew：15 個 corner 共 5,775 個違規，全在 Caravel 直接驅動的邊界 net，最多比外部 transition 多 0.001 ns（容許 0.05 ns）。
  - **審查後新加的比對**：4,800 個高於上限的 port bit 都以 SDC 的 transition 出現（15 corner × 320），C80d 的防護在正式 run 上生效。
  - pulse_width 最差 9.32 ns（`u_soc.sram0/clk0` low）。
  - magic_drc：SRAM 外 0 個；框內 5,572,955 個全部對得上 SRAM 單獨檢查。
- `ir_worst.py` PASS：max_ss_100C 4.94 mV、max_ss_n40C 4.68 mV（上限 20 mV）；Caravel pad 起算的 pattern IR 由同一條 regress 之後的 `make ir-caravel` 判。
- `provenance.py --verify`：開始與結束都是 `2b04451`，工作樹乾淨。沒有重試（沒有 `retries.txt`）。

「不分析的項目清單」：與 `550869c` 那次相同（含 `ef_decap_12` 沒有 .lib，漏電不計）。

## 合不合理

所有 metrics 與 golden（`550869c` 的確認 harden）逐值相同，實測與第一輪（`../arvinsa-rtl-gds-p7close_caravel/runs/user_project_wrapper_signoff/criteria_review.md`）一樣，判斷沿用：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold | setup +0.548 ns（min_ss_n40C，SRAM 半週期路徑）、hold +0.187 ns（max_ff_100C） | 依據仍成立；dout0 transition 改成量到的值後 setup 剩 +0.151 ns（exit review 已知限制 2） |
| hold repair 餘量 | GRT 後 +0.207 ns，signoff +0.187 ns，落差 0.020 ns（餘量 0.2 ns，決定 17） | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −3.598 ns | 依據需補充（同第一輪：約 2.7 ns 是報表算法，推測；真正多出來的是 `wb_clk_i` 到 clock root 約 1.9 ns） |
| 邊界 slew（決定 16） | 例外只用在 Caravel 驅動的 net；SDC 的 transition 確實生效（新比對 PASS） | 依據仍成立；低於上限的腳位仍沒有自動防護 |
| golden 誤差 | 0 個在誤差內 | wrapper 第四組逐值相同的比較，仍全在同一台機器；維持 hazard3 的誤差（決定 26）。同一輪 picorv32_core 第一輪有 29 個在誤差內、第二輪 0 個，說明不可重現是偶發的 |

## 學習

- 審查後的 checker 修正（H1–H8、slew）沒有改到 flow 的輸出；新的 slew 比對在正式 run 上看到 4,800 個 port bit。
- 三條平行跑時 wrapper harden 拉長到 286.6 分鐘（多了磁碟壓力），結果不變。knowledge 檔不追加新的數字。
