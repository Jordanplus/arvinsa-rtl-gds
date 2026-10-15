# signoff criteria 檢查：PicoRV32 Phase 5 第 1 次 harden（新設定）

- run：`../arvinsa-rtl-gds-p5h3/runs/soc_top`（commit `c976976`；設定與 Hazard3 第 8 次相同：44 ns、resizer 看得到 ss_n40C（ADR-0013）、`RUN_POST_GRT_RESIZER_TIMING`（ADR-0014）），2026-10-07
- 依據：skill `signoff-criteria`「每次 harden 後的檢查」；製程知識 `.claude/skills/signoff-criteria/knowledge/sky130A_sky130_fd_sc_hd.md`
- 腳本結果（`criteria_review.txt` 最後一行）：`criteria-review: PASS`
- 整體結果：`harden-soc: FAIL`（signoff 4 列 FAIL，加上 golden 比對；log `runs/p5_pico_harden1.log`，約 24 分鐘）

## 有沒有被執行

腳本 5 項都 PASS（40 個設定、78 個 step config、8 個時序 step 與 15 個 corner 的 uncertainty、corner 齊全、4 個 checker 都有結果行）。

| checker | 結果 | FAIL 列 | 是設計問題還是 criteria 問題 |
|---|---|---|---|
| LibreLane | 跑完 | — | DRC、LVS、slew、cap、antenna 都是 0；setup 有 9 個違規 endpoint |
| `check_signoff.py` | FAIL | `timing__setup_vio__count` 9；`nom_ss_n40C` setup −0.012、`min_ss_n40C` −0.113 ns | **設計問題**：SRAM 半週期路徑 setup 不夠（見下一節） |
| 同上 | FAIL | `timing__unannotated_net__count` 119 ≠ 133 | **criteria 問題**：上限是 Phase 4 版圖的數字。119 = 76 個 CTS dummy load（`clkload*`）+ 32 個沒用到的 SRAM 讀出 port（`sram0/dout1[31:0]`）+ 11 個 tie cell 沒接的輸出（10 個 `conb_1` 用 LO、1 個用 HI），15 個 corner 都是 119（`57-openroad-stapostpnr/*/checks.rpt`）。結構與 133（90 + 32 + 11）相同，只有 clock tree 的 dummy load 少 14 個。要等 setup 修好、版圖定下來再改上限 |
| 同上 | FAIL | golden：247 相同、38 在誤差內、153 不同 | 預期：golden 是 Phase 4 的 43 ns、沒有 ADR-0013／0014 的舊設定 |
| `sram_drc_alone`、`check_soc.py`、`check_inputs.py --resolved`、`provenance.py` | 全部 PASS | — | — |

「不分析的項目清單」：這次沒有寫，Phase 5 exit review 時要逐條寫。

## 合不合理

### setup 違規：SRAM 半週期路徑上多了一顆 hold buffer

最差路徑（min_ss_n40C）：`sram0` 下降緣（22 ns）送出 → `sram_dout0[3]` → `hold7844`（`dlygate4sd3_1`）→ `_17032_`（mux2）→ `hold7845`（`dlygate4sd3_1`）→ `_21860_/D`，上升緣（44 ns）接收。

| 段 | 延遲（ns） |
|---|---|
| 送出端 clock latency（SRAM `clk0` 前 10 顆 `delaybuf_*_clk`） | 3.81 |
| SRAM clk→dout0 | 15.76 |
| `hold7844`（mux 前） | 1.42 |
| mux | 0.81 |
| `hold7845`（mux 後） | 1.15 |
| 接收端 clock latency | 3.64 |
| uncertainty（含 DCD 2.2）／setup time | 2.45／0.35 |
| slack | −0.113 |

- Phase 4 的 PicoRV32 golden（43 ns）同一類路徑只有 mux 後那顆 hold buffer（1.17 ns），slack +0.384（knowledge 檔第 79、80 列）。這次 32 條 `sram_dout0` 各直接接 1 顆 `dlygate4sd3_1`，與 Hazard3 相同；mux 後的 hold buffer 也還在。週期多 1 ns（半週期多 0.5 ns）抵不過多出來的 1.42 ns。
- `hold7844`、`hold7845` 都是 CTS 後的 hold 修復（第 37 步，placement 寄生估計，餘量 `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns）插的；第 44 步 `ResizerTimingPostGRT` 只再插 3 顆。
- signoff 的 hold：經過 `hold7844` 的 hold 路徑 min_ff_n40C slack +0.838 ns，`hold7844` 在這個 corner 只佔 0.421 ns；這個 endpoint 最差 hold 是另一條 mux 輸入 +0.429 ns。也就是以 signoff 寄生來看，拿掉 `hold7844` hold 仍有約 +0.42 ns（直接相減，沒有考慮負載改變）。setup 這邊直接相減約 +1.3 ns。兩個數字都是估計，沒有實際拿掉重算。
- 第 44 步 `ResizerTimingPostGRT` 沒有做 setup 修復（log：`No setup violations found`，RSZ_CORNERS 含 3 個 ss_n40C corner）；signoff 是 −0.113 ns。也就是對這條路徑，global routing 寄生的估計比 signoff 樂觀至少 0.14 ns（修復餘量 `GRT_RESIZER_SETUP_SLACK_MARGIN` 0.025 ns）。Hazard3 第 5–8 次是反過來（估計 +0.002、signoff +0.53，但那是另一條長邏輯路徑）。這條路徑估計值是多少沒有量。
- **為什麼這次 PicoRV32 的 `sram_dout0` 也插了 hold buffer（Phase 4 沒有）沒有查**。這次與 Phase 4 golden 的差異有 ADR-0013（resizer 看 ss_n40C、setup 餘量 0.6 → 0.1）、ADR-0014、44 ns 三項，沒有分開試。

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| uncertainty：半週期路徑的 DCD 預算 2.2 ns | `docs/notes/signoff_criteria_soc_top.md` | 這條路徑 −0.113 ns；DCD 預算佔 2.2 ns | 依據沒變；FAIL 來自 hold buffer，不是 criteria 太嚴 |
| `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns | `cts-clock-tree` 規則 10 | post-CTS hold +0.300 → GRT 後 +0.104 → signoff +0.080 ns | hold 本身 PASS；但它在 SRAM 讀出路徑上的代價（ADR-0014 已知限制）這次讓 setup FAIL。**已知限制變成實際 FAIL** |
| `RUN_POST_GRT_RESIZER_TIMING` | ADR-0014（Hazard3 實測 GRT 估計比 signoff 悲觀 0.5 ns） | 這條路徑估計比 signoff 樂觀（沒修、signoff −0.113） | ADR-0014 的「悲觀」只在 Hazard3 的長邏輯路徑量過；半週期路徑不一定成立 |
| `timing__unannotated_net__count` 133 | Phase 4 版圖推導 | 119，組成相同 | 上限要依新版圖重推（criteria 問題，不是設計問題） |
| corner、slew、skew | Phase 4 | slew／cap／fanout 0；skew INFO 同結構 | 依據仍成立 |

## 學習

- 寫進 knowledge 檔：PicoRV32 在新設定下的半週期路徑組成（兩顆 hold buffer、−0.113 ns）、post-CTS → GRT → signoff 的 hold、GRT 估計對這條路徑偏樂觀。
- ADR-0014 的已知限制（`sram_dout0` 上的 hold buffer）在 PicoRV32 造成 signoff FAIL，Phase 5 exit 前要處理；選項交使用者決定。
- `timing__unannotated_net__count` 的上限在設計改完之後重推，不在這次改。
