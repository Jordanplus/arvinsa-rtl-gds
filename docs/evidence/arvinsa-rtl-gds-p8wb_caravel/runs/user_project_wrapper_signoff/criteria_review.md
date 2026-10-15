# criteria review：user_project_wrapper（ADR-0021 寫回後的確認 regress，乾淨 worktree `p8wb_caravel`，2026-10-15）

run：worktree `arvinsa-rtl-gds-p8wb_caravel` 的 `runs/user_project_wrapper`，commit `f02a1a0`（問題總檢討的寫回；wrapper 的 RTL、config、SDC 與 Phase 7 結案相同，`f02a1a0` 改的是 skill、文件、`scripts/check_skills.py`、`scripts/regress.py` 與 `scripts/neg_regress.py`），`make regress-caravel` 的 `harden-caravel`，259.6 分鐘，console `runs/p8wb_regress_caravel.console`（主目錄）。

這次 regress 的目的是確認新的 `regress.py`（開跑前的磁碟檢查、每個 target 的逾時）在真實 regress 上不會誤判。harden-caravel 的逾時上限是參考時間 287 分 × 3 = 861 分（`REF_MIN`），沒有觸發。同時在跑的先是 Hazard3 的 `make regress`，後是 PicoRV32 的 `make regress-picorv32`，都是兩條平行。磁碟剩餘：開跑時約 551 GiB，PicoRV32 開跑時約 477 GiB（中間沒有連續記錄）。

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS：
- config_applied：57 個設定
- step_config：78 個步驟
- uncertainty：8 個時序步驟、15 個 signoff corner
- uncertainty_applied：50,670 條路徑
- signoff_corners：15 個
- checkers_ran

最後一行：`criteria-review: PASS`。除了寫 `criteria_review.md` 的路徑，整份與 Phase 7 結案 regress（`../arvinsa-rtl-gds-p7close2_caravel/runs/user_project_wrapper_signoff/criteria_review.txt`）逐字相同。

`harden-soc: PASS`，`signoff.txt` 與 `soc_checks.txt` 沒有 FAIL 列：
- `check_signoff.py`：golden 455 個 metrics 全部逐值相同（0 個在誤差內、0 個不同）。
- `check_soc.py`：
  - max_slew：15 個 corner 共 5,775 個違規，全在 Caravel 直接驅動的邊界 net，最多比外部 transition 多 0.001 ns（容許 0.05 ns）；4,800 個高於上限的 port bit 都以 SDC 的 transition 出現。
  - pulse_width 最差 9.32 ns（`u_soc.sram0/clk0` low）。
  - magic_drc：SRAM 外 0 個；框內 5,572,955 個全部對得上 SRAM 單獨檢查。
  - inout_dont_touch：29 個 `analog_io` 都在 `RSZ_DONT_TOUCH_RX` 內。
- `ir_worst.py` PASS：max_ss_100C 4.94 mV（上限 20 mV）；Caravel pad 起算的 pattern IR 由同一條 regress 之後的 `make ir-caravel` 判。
- `provenance.py --verify`：開始與結束都是工作樹乾淨。沒有重試。

「不分析的項目清單」：與 Phase 7 結案相同（含 `ef_decap_12` 沒有 .lib，漏電不計）。

## 合不合理

所有 metrics 與 golden 逐值相同，判斷沿用 Phase 7 結案時的 review：

| criterion | 這次的實測 | 判斷 |
|---|---|---|
| setup／hold | setup +0.548 ns（min_ss_n40C，SRAM 半週期路徑）、hold +0.187 ns（max_ff_100C） | 依據仍成立；dout0 transition 改成量到的值後 setup 剩 +0.151 ns（Phase 7 exit review 已知限制 2） |
| hold repair 餘量 | GRT 後 +0.207 ns，signoff +0.187 ns，落差 0.020 ns（餘量 0.2 ns，ADR-0019 決定 17） | 依據仍成立 |
| skew metric | hold skew metric nom_ss_n40C −3.598 ns | 依據需補充（同前：約 2.7 ns 是報表算法，推測；真正多出來的是 `wb_clk_i` 到 clock root 約 1.9 ns） |
| 邊界 slew（ADR-0019 決定 16） | 例外只用在 Caravel 驅動的 net；SDC 的 transition 確實生效 | 依據仍成立；低於上限的腳位仍沒有自動防護 |
| golden 誤差 | 0 個在誤差內 | 第五組逐值相同，仍全在同一台機器 |

## 學習

- `f02a1a0` 沒有改到 flow 的輸出；wrapper 在乾淨 worktree 第五次逐值重現。
- 兩條平行時 harden 259.6 分鐘，介於第一輪三條平行的 236 分鐘與第二輪三條平行加磁碟壓力的 286.6 分鐘之間。harden 時間受同時負載影響，波動約 ±20 %；逾時取參考時間的 3 倍足夠。
- knowledge 檔不追加新的數字。
