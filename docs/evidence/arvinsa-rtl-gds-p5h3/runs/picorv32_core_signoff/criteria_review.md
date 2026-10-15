# signoff criteria 檢查：PicoRV32 單獨 harden（Phase 5 預跑）

- run：`../arvinsa-rtl-gds-p5h3/runs/picorv32_core`（commit `941e1cb`），2026-10-07
  - log：主 repo 的 `runs/p5_pre_harden-core.log`
  - 費時 841 s，沒有重試
- 目的：給 `neg-eqy-core` 預跑提供網表。結果是 `neg-eqy: PASS 11/11 caught`。
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」
- 腳本結果：`criteria-review: PASS`（2026-10-08 補跑：Phase 5 獨立審查後 `review_criteria.py` 加了 `--design picorv32_core`，`make harden-core` 從此會跑它；這次是在 run 完成後用新版補跑，同目錄 `criteria_review.txt`）
- 整體結果：`harden-core: PASS`、`signoff: PASS`

## 有沒有被執行

2026-10-08 補跑第一部分（`criteria_review.txt`）：config 13 個設定都生效、77 個 step config 一致、9 個 corner 共 18,000 條 signoff 路徑實際套用的 uncertainty 都是 0.25 ns（LibreLane 預設的 `CLOCK_UNCERTAINTY_CONSTRAINT`）、corner 齊全、4 個 checker 都有結果行。下面原本寫的「第一部分沒有被執行」指 harden 當時。

**第一部分沒有被執行。**
- `make harden-core` 跑的是 `pnr/picorv32_core/run.sh`，這支腳本不會呼叫 `signoff/scripts/review_criteria.py`。目前只有 `pnr/soc_top/run.sh` 會呼叫。
- Stop hook（`.claude/hooks/require_criteria_review.py`）只在找到 `criteria_review.txt` 時才要求寫 review，所以也不會擋 `harden-core`。
- 結論：規則 9「每次 harden」在 core harden 上沒有自動把關。這是覆蓋缺口，列入待辦與 Phase 5 exit review，交使用者決定要不要補上。

手動核對的部分：

| checker | 結果 | 說明 |
|---|---|---|
| LibreLane | 跑完 | 77 個 step，沒有重試 |
| `check_signoff.py` | PASS | 所有「等於」列都 PASS，包括 DRC、LVS、antenna、slew、cap、fanout 都是 0，setup／hold 違例 0 |
| | | unannotated 114，等於上限檔的值 |
| | | IR drop 合計 0.57 mV（上限 20 mV） |
| | | golden 325 個 metric：254 個完全相同、71 個在誤差內、0 個不同 |

沒有手動核對的：
- config 的每個設定是否進了 `resolved.json`、每個 step 的 config、uncertainty 是否出現在每個時序 step。這些是 `review_criteria.py` 的工作，這次沒有跑。
- 「不分析的項目清單」：core harden 的文件沒有這份清單，這次也沒寫。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| setup 餘量 | Phase 2 core harden（`pnr/picorv32_core/README.md`） | 15 個 corner 最差 +6.175 ns（max_ss_100C），週期 40 ns | 依據仍成立 |
| hold 餘量與代價 | 同上 | 最差 +0.039 ns（min_ff_n40C）<br>hold buffer 2223 顆，全部是 `dlygate4sd3_1`。和 Phase 5 的發現一致：RepairHold 全設計只用一種 cell，見 drv-timing-closure 規則 7 | 依據仍成立。2223 顆的面積代價沒有另外分析 |
| corner 清單 | `STA_CORNERS` 15 個 | 最差 setup 在 ss_100C，最差 hold 在 ff_n40C；這次沒有看到溫度反轉 | 依據仍成立 |
| uncertainty | core 沒有 SDC，用 LibreLane 預設 | 沒有 SRAM，也沒有半週期路徑；ADR-0016 的 CTS 改動不適用（config 沒有替換 CTS step，也沒有 macro） | 資料不足：沒有腳本檢查 uncertainty 是否套到每個 step |
| CTS slew／fanout | config 的 `CTS_SINK_CLUSTERING_SIZE` 8、`CTS_DISTANCE_BETWEEN_BUFFERS` 50（README） | max fanout、max slew、max cap 違例都是 0 | 依據仍成立 |
| 上限檔的 unannotated 114 | Phase 2 為這顆設計推導 | 114，等於上限 | 依據仍成立 |

## 學習

- core harden 沒有接 `review_criteria.py`，規則 9 在 core 上靠手動。是否把它接進 `pnr/picorv32_core/run.sh`（加 negative test），交使用者決定。
- golden 比對有 71 個 metric 不是完全相同但在誤差內。core 的 config 在 Phase 5 沒有改，這個差異屬於 flow 本身的不可重現範圍，與 ADR-0015 記錄的現象同類。這是推測，沒有逐步比對。
- 沒有新的製程數字要寫進 knowledge 檔。
