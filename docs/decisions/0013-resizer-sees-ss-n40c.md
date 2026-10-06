# ADR-0013：resizer 也看溫度反轉的 ss_n40C corner，setup 餘量改回 0.1 ns

- 狀態：已採用（2026-10-07，使用者決定）；Hazard3 第 3 次 harden 確認效果，剩 0.381 ns 由週期 44 ns 處理（ADR-0004）
- 背景：Phase 5 第 2 次 `make harden-soc CPU=hazard3`（commit `2251c4a`，修好 ADR-0012 的記憶體失控之後）跑完，但 signoff setup 在 ss_n40C_1v60 FAIL。

## 原因（已驗證）

1. Phase 4 起，resizer（`RSZ_CORNERS`）只看 LibreLane 原本的 9 個 corner，溫度反轉的 ss_n40C 只在 signoff 判定。改用 `PL_RESIZER_SETUP_SLACK_MARGIN` 0.6 ns，也就是「resizer 看得到的 ss_100C 多留 0.6 ns」，來代替 ss_n40C。
2. PicoRV32 版最緊的是 SRAM 半週期路徑，ss_100C 和 ss_n40C 只差 0.44 ns，所以這樣夠用。Hazard3 版從乘除法單元的運算元暫存器到 register file 讀出暫存器（`regs.rdata1[8]`）的整週期路徑，signoff 時同一條在 ss_100C 是 +1.48 ns、ss_n40C 是 −4.16 ns，資料到達時間差 5.9 ns（約 15%）。resizer 看到 +1.48 ns 大於 0.6 ns，判斷不用修。
3. corner 之間的延遲差和路徑長度成比例（這條路徑的 `or4` 在 ss_n40C 每顆約 2 ns），固定幾 ns 的餘量只蓋得住短路徑。
4. signoff：ss_n40C 三個 corner 共 81 條 setup 違規（max −4.158、nom −3.248、min −2.209 ns），其他項目都 PASS。Magic DRC 4,665,810 和 golden 相同，全部在 SRAM 框內。

## 單步實驗（同一份 `ResizerTimingPostCTS` 輸入，用繞線前的估計量各 corner）

量法：把 resizer step 匯出（`eject`），換成自己的 Tcl，用和 resizer 相同的寄生估計，以 `worst_slack -corner` 量各 corner（skill `multicorner-sta` 規則 8）。這是估計值：對照組用這個量法是 −7.32 ns，繞線後 signoff 是 −4.16 ns。

| max corner | 對照：9 個 corner、餘量 0.6 | 實驗 1：加 ss_n40C、餘量 0.6 | 實驗 2：加 ss_n40C、餘量 0.1 |
|---|---|---|---|
| ss_n40C setup | −7.32 ns（TNS −230） | +0.33 | −0.21（3 個 endpoint，TNS −0.36） |
| ss_n40C hold | +0.069 | −0.263（約 21 個） | +0.622 |
| ff_n40C hold | +0.292 | +0.030 | +0.294 |
| ss_100C setup | +0.43 | +1.07 | +0.64 |
| 時間／記憶體 | 68 秒／588 MiB | 284 秒／836 MiB | 189 秒／758 MiB |

- 實驗 1 的 hold 違規全部在 SRAM 讀出暫存器（`sram0` 上升緣 dout0 → `mux2` → flop）。對照組在這些路徑上有 hold buffer（例如 `_21020_` 前的 `hold6334`），實驗 1 沒有：這些路徑在 ss_n40C 的 setup 剛好在 0.6 ns 餘量上，看得到 ss_n40C 後 hold 修復就不插了。實驗 2 把餘量降到 0.1，hold buffer 插回來（網表 2715 顆），hold 恢復。SRAM 在 ss_n40C 的 hold 弧是佔位值（ADR-0010）。
- 0.6 ns 是為了代替 ss_n40C 而設；resizer 直接看得到 ss_n40C 之後，就不需要用它代替了。
- 實驗 2 的 setup 修復最多到 +0.021 ns（`RSZ-0062 Unable to repair all setup violations`），插 hold buffer 與合法化之後剩 −0.21 ns。繞線後會不會通過要跑完整 flow 才知道。

## 決策

1. `pnr/soc_top/config.json` 與 `config_hazard3.json` 一起改（`check_inputs.py` 的 `cpu_config` 仍然只允許差 3 個設計相關的 key）：
   - `RSZ_CORNERS` 加 `nom_ss_n40C_1v60`、`min_ss_n40C_1v60`、`max_ss_n40C_1v60`。`ff_100C_1v95` 仍只在 signoff 判定（那裡沒有 hold 違規：Hazard3 第 2 次 harden 最差 +0.153 ns，PicoRV32 golden +0.087 ns）。
   - `PL_RESIZER_SETUP_SLACK_MARGIN` 0.6 → 0.1 ns。
   - `EXTRA_EXCLUDED_CELLS` 加 `check_weak_cells.py` 在 ss_n40C 列出的 6 種 cell：`o41ai_1`（placement 後的餘量 30%）、`a2111oi_2`、`nor4b_1`、`a222oi_1`、`o311ai_1`、`nor4_1`（繞線後的餘量 40%）。加入後 `weak_cells` 8 列全部 PASS（358 個 cell）。
2. 這 6 種 cell 也不會用在合成（`EXTRA_EXCLUDED_CELLS` 同時給合成與 PnR，LibreLane `steps/pyosys.py` 343 行、`steps/openroad.py` 333 行），合成改用較大的尺寸。
3. `pnr.sdc` 的 `set_max_transition 0.70` 不改：它當初是為了 resizer 看不到 ss_n40C 而設，現在 resizer 看得到了，但改回去會讓弱 cell 的上限一起改變，等這次 harden 的結果再評估。

## 影響

- Hazard3 與 PicoRV32 兩版的合成與 PnR 結果都會改變。PicoRV32 版本來就要重跑，並更新 `signoff/golden/soc_top/`（ADR-0012 的影響一節）。
- resizer 多看 3 個 corner，PnR 會變慢（單步實驗的 post-CTS 修復 68 → 189 秒）。Phase 4 時 15 個 corner 讓繞線後的修復停不下來，推測是 ADR-0012 的弱 cell 迴圈（未確認），所以這次跑 harden 時監看記憶體與時間。

## 結果：Hazard3 第 3 次 harden（commit `d00214d`，週期 43 ns）

- 跑完約 33 分鐘。三個修復步驟：56 秒／558 MiB、6 分 15 秒／834 MiB、41 秒／1 GiB，沒有記憶體或時間問題。
- signoff 只剩 `max_ss_n40C_1v60` setup −0.381 ns（9 個 endpoint，TNS −1.40 ns）；`nom_ss_n40C_1v60` +0.129、`min_ss_n40C_1v60` +0.076 ns。第 2 次是 81 條、最差 −4.158 ns。
- hold 最差 +0.107 ns；slew、cap、LVS、antenna、繞線 DRC 都是 0；Magic DRC 4,665,810 和 golden 相同。stdcell 30,404 顆。
- 剩下的最差路徑：`alu.funct7_32b[6]` → `regs.rdata1[17]`，終點前有 1 顆 hold buffer（`hold10171`，約 1.2 ns）。
- 使用者決定週期 43 → 44 ns（2026-10-07，ADR-0004 Phase 5 補充），commit `1292ca4`。

## 限制

- 實驗的數字是繞線前的估計，繞線後由第 3 次 harden 的 signoff 確認（上一節）。
- SRAM 在 ss_n40C 讀取會失敗（ADR-0010），它在這個 corner 的時序弧是佔位值，所以 SRAM 路徑在 ss_n40C 的 setup 與 hold 結果只代表佔位值。

## 出處

- `runs/p5_h3_harden2.log`、`runs/p5_h3_harden3.log`；`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3/56-openroad-stapostpnr/max_ss_n40C_1v60/`
- skill `multicorner-sta` 規則 2、3、7、8；`drv-timing-closure` 規則 9、11 與經驗紀錄
