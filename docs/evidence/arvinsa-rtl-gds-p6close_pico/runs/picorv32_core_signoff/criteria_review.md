# criteria review：picorv32_core（Phase 6 結案 regress，乾淨 worktree 的 `make regress`，2026-10-11）

- run：`../arvinsa-rtl-gds-p6close_pico/runs/picorv32_core`，commit `85bfa75`，沒有重試
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`
- 整體結果：`harden-core: PASS`，`regress: PASS 28/28`

## 有沒有被執行

- 第一部分全部 PASS（config_applied、step_config、uncertainty、uncertainty_applied、signoff_corners、checkers_ran）。
- signoff、cpu-params、disconnected-pins、provenance 都有結果行，全部 PASS。
- golden 比對：325 個 metrics 全部逐值相同，0 個在誤差內、0 個不同。
- 可重現性：最終網表與 DEF 的 sha256 和 4d 的結案 run（`4713c5f`）相同；GDS 把 BGNLIB／BGNSTR 的日期清成零後 sha256 相同。`4713c5f` 到 `85bfa75` 只改 checker、文件與萃取試跑的腳本，沒有動 flow 設定。
- 沒有 FAIL 列；「不分析的項目清單」沒有新增。
- 前一次結案 regress（`904e18e`）停在 harden-soc（`check_inputs.py` 的 bug），core 的 harden 沒有跑到。

## 合不合理

數字與 4d 的結案 harden 完全相同，結論不變：

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer hold 餘量 0.1 ns | skill「resizer 的 slack margin」 | 最後一次修復（PostCTS）+0.100 → signoff +0.039 ns，差距 0.061 < 0.1 ns | 依據仍成立 |
| resizer setup 餘量 | 同上 | 沒有 setup 違規可修；signoff 最差 +6.175 ns（max_ss_100C_1v60） | 依據仍成立 |
| hold 餘量的代價 | skill「hold 餘量」 | hold buffer 2,230 個，PostCTS 面積 +13.1 %，與 Phase 5、4d 相同 | 依據仍成立 |
| slew 上限 | PDK 預設（core 沒有自訂） | `set_max_transition` 未設、slew 修復 20 %／30 %，與 Phase 5、4d 相同 | 依據仍成立 |
| corner 清單 | `STA_CORNERS`（9 個） | 最差 setup 在 max_ss_100C_1v60；core 的最差路徑是 I/O 路徑 `resetn -> mem_la_addr[30]` | 依據仍成立 |
| uncertainty 0.25 ns | `CLOCK_UNCERTAINTY_CONSTRAINT` | 9000 條路徑沒有半週期路徑，DCD 不適用 | 依據仍成立 |
| 上限檔（`signoff/limits/picorv32_core.toml`） | Phase 2 為這顆 core 推導 | golden 逐值相同 | 依據仍成立 |

## 學習

- 自產 SRAM 版本的 picorv32_core harden 跨 `4713c5f` → `85bfa75` 仍逐位元重現（網表、DEF 相同，GDS 只差日期）。
- 沒有新數字要寫進 knowledge 檔；沒有依據不成立的 criterion，沒有提案。
