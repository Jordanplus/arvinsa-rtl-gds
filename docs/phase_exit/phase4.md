# Phase 4 exit review：signoff 收斂、一鍵 regression 與文件

日期：2026-10-04　結論：**PASS**（`make regress` 第 4 次在乾淨 checkout 25/25 PASS）。「第三人可依 README 重現」只在同一台機器驗證過，見 exit criteria 第 6 項與已知限制 12。

Exit criteria 出處：`project-plan.md` §8 Phase 4。原文：「嘗試壓到 25 ns；L4 EQY；L5 GL sim；IR drop／antenna checker；`make regress` 一鍵；README、ADR、phase_exit」，exit 條件「`make regress` 全 PASS；第三人可依 README 重現」。

一併帶進本階段、也列在下表的項目：
- Phase 3 已知限制 11–16（`docs/phase_exit/phase3.md`），其中 12–16 是獨立審查找到的 checker 漏洞，使用者決定在 Phase 4 開頭一起修。
- 使用者 2026-10-04 決定的 3 個門檻。
- `docs/notes/signoff_criteria_soc_top.md` 的「Phase 4 待辦」1–7。

正式 run：`make regress` 第 4 次，在乾淨的 worktree 執行（`git worktree add --detach` 加 `git submodule update --init`，開始時沒有修改或未追蹤的檔案），commit `b7860b7`，2026-10-04 18:21:51–20:25:16，7405 秒（123 分鐘），rc=0，25/25 target PASS（`runs/regress/summary.md`、`junit.xml`；log `runs/p4_regress_clean4.log`）。harden-soc 遇到一次已知的 OpenROAD GRT-0229，依有上限的重試從第 41 步繼續完成（`runs/soc_top_signoff/retries.txt`）。

前 3 次都在乾淨 checkout，結果不當作結案證據：
- 第 1 次（`72e5433`）：24/24 PASS，119 分鐘；之後依獨立審查修改了 checker。
- 第 2 次（`c635ffb`）：harden-soc FAIL，golden 比對的繞線器中間數字不同。
- 第 3 次（`59c6748`）：gl-soc-powered FAIL，gate-level 模擬超過牆鐘時限。

第 2、3 次的根因與修正見「Phase 4 新找到的 checker 問題」最後兩列。

除非另外註明，下面的數字取自 golden 的來源 run（Phase 4 第 5 次 `make harden-soc`，commit `e5b7a4b`，`signoff/golden/soc_top/README.md`）；第 4 次 regress 的 metrics 與它 434 個完全相同。

| # | 項目 | 結果 | 證據 |
|---|---|---|---|
| 1 | 嘗試壓到 25 ns | 做不到；soc_top 改 42 ns（使用者決定） | 「時序目標」一節 |
| 2 | L4 EQY | PASS（合成網表 vs 最終網表），另外加了 flip-flop 的結構比對 | 「EQY」一節 |
| 3 | L5 GL sim | PASS：帶電源的網表與 RTL lockstep | `make gl-soc-powered` |
| 4 | IR drop／antenna checker | IR 改成一側供電模型，判 VDD 降壓 + GND 抬升 ≤ 20 mV；antenna 沿用 Phase 3 | 「IR drop」一節 |
| 5 | `make regress` 一鍵 | PASS：第 4 次 25/25，123 分鐘（前 3 次見上） | `runs/regress/summary.md`、`junit.xml` |
| 6 | 第三人可依 README 重現 | 有條件通過：README 快速開始寫到 `make regress`；同一台機器的乾淨 checkout 跑了 4 次，最後一次 PASS，soc_top 的 metrics 有 3 次與 golden 完全相同。沒有在另一台機器試過（已知限制 12） | 「可重現性」一節 |
| 7 | Phase 3 已知限制 12–16（checker 漏洞） | 5 個全部修正，各有 negative test | 「checker 漏洞修正」一節 |
| 8 | 使用者決定的 3 個門檻 | 全部實作 | 「signoff 條件」一節 |
| 9 | signoff 條件待辦 1–7 | 全部實作；其中兩項只做到一部分：第 3 項的電壓源位置仍是假設（一側供電），第 5 項的 hold 只列出成分名稱、沒有 SI 的數值（開源工具不分析 SI） | 同上 |
| 10 | Phase 3 已知限制 11（RTL → 合成網表沒有 formal） | 補 directed 測試並證明有效；RTL vs 合成網表的 EQY 試過，抓不到部分錯誤，不採用 | 「EQY」「directed 測試」兩節 |

## 時序目標：25 ns 與 42 ns

- **25 ns 做不到**：在同一份版圖只重跑 STA，25 ns 時 SRAM 路徑差約 7 ns；不含 SRAM 的路徑在 ss 100 °C 差 1.8 ns、ss −40 °C 差 4.7 ns。
- **40 ns 也不過了**：Phase 4 加嚴的條件（SRAM derate 1.575、duty cycle 預算、溫度反轉 corner）讓 SRAM 的半週期路徑在 min_ss_n40C 差 0.42 ns；這條路徑的 slack 每 1 ns 週期只變 0.45 ns，最小週期約 41 ns。
  - 這條路徑：`sram0` 在 clock 下降緣送出 `dout0`，`rdata_q` 在下一個上升緣接收，只有半個週期；SRAM 延遲用的是 padded.lib 的假設值 10 ns × 1.575。
- **使用者決定（2026-10-04）：soc_top 改 42 ns**，不放寬任何假設或檢查（ADR-0004 Phase 4 補充）。picorv32_core 維持 40 ns。
- 42 ns 的結果（15 個 corner）：setup 最差 +0.313 ns（min_ss_n40C），hold 最差 +0.082 ns（min_ff_n40C），max slew／cap／fanout 0。

## signoff 條件（Phase 4 實作）

| 項目 | 做法 | 結果 | negative test |
|---|---|---|---|
| IR 上限 20 mV（使用者決定） | `[max_sum]`：VDD 降壓 + GND 抬升 ≤ 20 mV（LibreLane 的 `ir__drop__worst` 只有 VDD） | 4.04 + 4.03 = 8.07 mV | P07（兩個 net 各 11 mV） |
| IR 的供電模型 | 每條 met5 strap 一側一點（`VSRC_LOC_FILES`）；`check_soc.py ir_sources` 確認每個點在對應的 strap 上 | 同上；最壞組合（ff 電流＋ss 電阻）11.46 mV（IR 研究，在 Phase 3 的版圖上算） | P26（點移出 strap） |
| SRAM derate 乘進 OCV（使用者決定） | ss 1.575、ff 0.665（ADR-0007 補充） | — | P04 |
| nom_tt 10% 規則（使用者決定） | 降為只報告 | nom_tt setup 7.133 ns | — |
| uncertainty 分成 setup／hold、列出成分 | `pnr/soc_top/clock_uncertainty.sdc`：setup 0.25、hold 0.25 | — | P01、P02 |
| 半週期路徑的 duty cycle 預算 | 下降緣↔上升緣的 uncertainty 2.35 ns（jitter 0.15 + DCD 2.1 + margin 0.10；45/55% 是假設） | 見上 | P24（duty 60%）、P25（預算 60%） |
| min pulse width、min period | STA hook 每個 corner 輸出報告，`check_soc.py pulse_width` 要求 slack ≥ DCD＋半週期 jitter | 最差 8.24 ns（`sram0/clk0` 低電位）、min period 12.0 ns | P22、P23 |
| 溫度反轉 corner | `ss_n40C_1v60`、`ff_100C_1v95`，共 15 個 corner；resizer 只看原本 9 個（`RSZ_CORNERS`，見「收斂過程」） | 全部 PASS | — |

## checker 漏洞修正（Phase 3 已知限制 12–16）

| 漏洞 | 修正 | negative test 與結果 |
|---|---|---|
| 12：下游不確認 run 是哪個 commit 產生的 | `signoff/scripts/run_guard.py`：9 個下游步驟都要求 `result.txt` PASS 且 `provenance.json` 的 commit 等於 HEAD，檢查前先刪自己的輸出；Makefile 加 `.NOTPARALLEL` | `neg_run_guard.py` 37/37：guard 本身的 positive control 1 個，加 9 個下游步驟 × 4（3 種壞 run：沒 PASS、別的 commit、沒有來源紀錄；1 個 positive control） |
| 13：來源追溯不看 LibreLane 與 PDK 的內容 | LibreLane clone 不能有改過的檔；PDK 6 個目錄（2109 個檔）的內容摘要與 `env/pdk_content.sha256` 相同（參考值從下載的壓縮檔算）；`resolved.json` 讀的 PDK 檔都要在這些目錄內；`make regress` 最後再檢查一次 HEAD 與工作目錄 | `neg_provenance.py` 19/19（獨立審查後加了 2 個 symlink 案例），每個 negative case 只有預期的列 FAIL（`pdk` 案例預期 `pdk` 與 `pdk_content` 兩列） |
| 14：Magic DRC 在 SRAM 框內只比規則種類 | 逐一比位置：框內每個違規都要落在 SRAM 單獨檢查的同規則違規範圍內（容許 0.1 µm，用 Phase 3 的 run 量出來）；SRAM 單獨的報告每次 harden 重新產生（兩次逐 byte 相同） | P21：SRAM 框內植入一個 `li.3`（SRAM 單獨時也有的規則）違規，舊的比對會漏、新的抓到 |
| 15：neg-pnr 假 run 沒有 positive control | 假 run 連 STA 目錄；P00 positive control；斷言「FAIL 的列剛好是被植入的那幾列」；P13 走 `check_soc.py` 的主判定；`sram0` 找不到時 port1_tieoff 判 FAIL | neg-pnr 32/32（P00–P31；P00 是 positive control，未修改的假 run 必須 PASS） |
| 16：neg-eqy 不檢查 FAIL 的位置 | 從 EQY 紀錄取出 FAIL 牽涉的名稱，必須在植入點附近（遇到 buffer 繼續往下走）；加 `nand2_to_nor2` | 每個案例的 FAIL 名稱都在自己的範圍內；植入點不同的任兩個案例，A 的 FAIL 名稱放到 B 的範圍判不符（獨立審查後改成 `neg_eqy.py` 每次自動檢查，bus pin 逐 bit）；`nand2_to_nor2` 在 soc_top、picorv32 都是 1 個分區證明失敗 |

## Phase 4 新找到的 checker 問題（已修正）

| 問題 | 怎麼發現 | 修正 |
|---|---|---|
| EQY 的 `sat` strategy 證不到 flip-flop 本身的行為：一顆 `dfxtp_2` 換成 reset 時會清除的 `dfrtp_2`，18100/18100 個分區照樣證明通過 | agent 試 RTL vs 合成網表時發現植入的 reset 值錯誤沒被抓到；我在最終網表植入 `flop_async_reset` 重現 | `run_eqy.py` 另外比對兩份網表的 sequential cell（同名、同功能，只允許 drive strength 不同）；`neg_eqy.py` 加 `flop_async_reset`、`flop_q_inverted` |
| IR 判定只看 VDD，而且供電模型把所有 pin 當理想電源（0.3 mV，任何門檻都會 PASS） | IR 研究（agent，16 種組合） | 規則改成兩個 net 合計；供電改一側模型（`docs/notes/ir_worst_case_soc_top.md`） |
| P21 第一版植入的錯誤，舊的 checker 也抓得到，沒有測到漏洞 | 看 FAIL 的規則名稱（`li.c1` 不在 SRAM 基準裡） | 改植入 `li.3` |
| P09、P14 植入後有兩列 FAIL | 加上「只有被植入的列 FAIL」的斷言後 | 寫明連動的列與原因 |
| golden 比對要求繞線器中間各輪的 DRC 數（`route__drc_errors__iter:*`）完全相同，但多執行緒 detailed routing 每次不完全一樣 | `make regress` 第 2 次（乾淨 checkout，`c635ffb`）在 harden-soc FAIL：最後一次重繞的第 2 輪剩 14 個、golden 11 個；第 45 步輸入逐 byte 相同，最終 DRC 兩次都是 0（`signoff/golden/soc_top/README.md`） | 使用者決定兩個設計都給 ±100，最終 `route__drc_errors` 仍要完全相同；P31 |
| gate-level 模擬的牆鐘時限照 RTL 速度算（每秒 4000 cycle），gate-level 只有每秒約 1200–1600 cycle，餘裕約 2 倍 | `make regress` 第 3 次（乾淨 checkout，`59c6748`）在 gl-soc-powered FAIL：Spotlight 索引 `runs/` 造成負載（load 17–21），boot_uart_max 在 620 秒被停掉（regress 1 只要 304 秒）；用新時限在負載 12–15 下單獨重跑（與 hello 兩支並行）PASS，249 秒 | `run_gl_soc.py` 的 `gl_timeout`：120 秒 + cycle 上限 ÷ 400，比實測多 10–50 倍；firmware 卡住仍由 cycle 上限判 FAIL；強制時限 1 秒時 hello 被停掉，證明時限有傳到模擬器 |

## EQY

- 範圍與 Phase 3 相同：合成網表 vs 最終網表。第 4 次 regress：
  - soc_top：18100/18100 個分區證明等價，2639 顆 sequential cell 功能相同，2641 個 clock pin 接到同一個來源（`clk`，以及 SRAM 不用的 `clk1` 接 `1'b0`），233.5 秒。
  - picorv32：15137/15137 個分區證明等價，2382 顆 sequential cell 功能相同，2382 個 clock pin 都接 `clk`，189.7 秒。
- flip-flop 結構比對：兩份網表的 sequential cell 同名、同功能（soc_top 2639 顆、picorv32 2382 顆 `dfxtp`）；只允許 drive strength 不同，最終網表有 104 顆（soc_top）、12 顆（picorv32）被 resizer 從 `dfxtp_2` 換成 `dfxtp_4`。
- **RTL vs 合成網表**（Phase 3 已知限制 11）：agent 讓 gold 端照 LibreLane 的順序跑到 `memory_map`，soc_top 2642/2642 個分區證明通過，但植入 4 種錯誤有 2 種（UART 除頻器的 reset 值、FSM 轉移）照樣 PASS，原因同上一節；只用 PDR（另一種證明方法）時，沒有植入錯誤的設計只證明 1514/2642 個分區，EQY 以 ERROR 結束（不是找到反例）。這組實驗的紀錄只在當時的暫存目錄，沒有存進 repo。不加成 checker（`formal-equivalence-eqy` skill 規則 5）。

## L5 與 directed 測試

- **L5**（`make gl-soc-powered`）：帶電源網表（`final/pnl`）加 `-DUSE_POWER_PINS`，每顆 cell 的輸出都經過 power-good primitive。tap cell 的 LEF 只有 VPWR／VGND，它的 Verilog model 多出的 VPB／VNB 會讓 Icarus 對每顆 tap 報兩行警告（6635 顆），只對這個 cell 的這兩個 port 放行。negative test：推動 `host_rdata[7]` 的 cell 的 VPWR 改接 vssd1，`hello` 就報 lockstep 不一致。
- **directed 測試**（補 Phase 2 已知限制 7）：
  - `counters`：`rdcycleh`、`rdinstreth` 必須是 0，計數器要遞增。抓得到高半部「卡 1」；「卡 0」要 2^32 個 cycle，抓不到。
  - `buserr`：打開 bus-error IRQ，做一次非對齊 `lw`、`sw`（inline assembly；用 C 寫的話 GCC 會拆成 byte 存取）。PicoRV32 只把 IRQ 設成 pending，存取照樣送出（`picorv32.v` 382、403–406、1922–1935），測試檢查的是這個實際行為。
  - 在網表植入 Phase 2 漏掉的 3 個錯誤（`count_cycle[45]`、`count_instr[40]` 卡 1、bus-error IRQ 卡 0），新測試的 lockstep 比對都抓到。

## 收斂過程（harden-soc 第 1–5 次）

1. **第 1 次**（15 個 corner 全給 PnR）：`OpenROAD.RepairDesignPostGRT` 35 分鐘以上沒結束，依 `librelane-run-debug` 的規則停掉。同一份輸入只把 resizer 改成 9 個 corner 單步重跑，58 秒完成 → `RSZ_CORNERS` 用原本 9 個；9 個再加 1 個 `max_ss_n40C`（用第 2 次 run 的輸入）也是 4 分鐘以上不結束。
2. **第 2 次**：setup 在 ss_n40C 差 0.41 ns（SRAM 半週期路徑），hold 在 ff 差 0.09 ns（SRAM 輸入腳），max_ss_n40C 有 7 個 slew 違規（最多超過 0.016 ns）。
3. **第 3 次**（`CTS_DELAY_BUFFER_DERATE_PCT` 0）：時序與 DRV 的結果與第 2 次完全相同（只有 14 個 IR metric 不同，因為一側供電模型在這兩次之間加入）。CTS 仍插 10 個 delay buffer（設 1% 也一樣），這個選項管不到 OpenROAD 把 SRAM 與 flip-flop latency 對齊的那一步。
4. **第 4 次**（resizer hold 餘裕 0.3、setup 餘裕 0.6）：hold 通過（+0.082 ns）；setup 仍差 0.42 ns（推測原因：resizer 只看 9 個 corner，這條路徑在 ss_100C 的 slack 已經足夠，它不會去修；這次沒有保留 resizer 的 log 可以確認）；max_ss_n40C 有 8 個 max slew 違規。→ 請使用者決定，選 42 ns。
5. **第 5 次**（42 ns、clock pin 的線每 150 µm 切段、PnR 的 max transition 0.70 ns）：15 個 corner 全部通過。limits 有兩類 FAIL：與舊 golden 比對（預期，設定改了）；沒有寄生值的 driver 133 個，當時上限寫「剛好 134」（CTS 的 dummy load 少一顆，檢視後上限改成 133，`d09de0e`）。`check_soc.py`、輸入一致、來源追溯 PASS → 更新 golden。

## 實測面積與時序（42 ns）

| 項目 | 值 |
|---|---|
| die／core | 1000 × 800 µm；core 769,005 µm² |
| PnR 後 standard cell | 29,352 顆（含 tap 6,635 顆、antenna diode 85 顆，不含 filler 66,351 顆），237,644 µm²；logic 區使用率 53.4%（ADR-0006 的算法：÷（core − SRAM 加 halo 324,251 µm²）） |
| 其中 | flip-flop 2,639 顆；timing repair buffer 9,525 顆（含 hold buffer 3,452 顆）；clock buffer 531 顆 |
| setup worst slack | tt +7.10～+7.17；ss_100C +0.79～+0.92；ss_n40C +0.31～+0.54；ff +7.45～+7.55 ns |
| hold worst slack | ff_n40C +0.082～+0.086；ff_100C +0.088～+0.092；tt +0.28；ss +0.81 以上 |
| clock skew（setup，含 uncertainty） | 各 corner 0.67–1.88 ns，最小在 min_ff_n40C、最大在 max_ss_n40C |
| min pulse width／min period | 最差 slack 8.24 ns（`sram0/clk0` 低電位，需要 ≥ 2.25）、12.0 ns（需要 ≥ 0.15） |
| IR（static，一側供電，nom_tt） | VDD 降壓 4.04 mV、GND 抬升 4.03 mV，合計 8.07 mV |
| 功耗（OpenSTA 預設 activity） | `power__total` 9.45 mW（max_ff_100C_1v95，15 個 corner 中最高） |
| 繞線 | 總長 894,480 µm；via 162,762 個；最長 619.53 µm（SRAM port 1 的 tie-off 線） |

## 可重現性

4 次乾淨 checkout 的 `make regress` 與 golden 逐項比對（同一台機器、同樣設定）：

| run | commit | soc_top（434 個 metrics） | picorv32_core（325 個） |
|---|---|---|---|
| 第 1 次 | `72e5433` | 434 個完全相同 | 254 個相同、71 個在誤差內 |
| 第 2 次 | `c635ffb` | 349 個相同、84 個在誤差內、`route__drc_errors__iter:2` 14 vs 11 → FAIL（新規則下 85 個在誤差內，PASS） | 沒跑到 |
| 第 3 次 | `59c6748` | 434 個完全相同；GRT-0229 重試 1 次 | 沒跑到 |
| 第 4 次 | `b7860b7` | 434 個完全相同；GRT-0229 重試 1 次 | 325 個完全相同 |

- 第 2 次與第 1 次的 `OpenROAD.DetailedRouting` 輸入逐 byte 相同，差異來自多執行緒繞線（`signoff/golden/soc_top/README.md`），與 Phase 2 在 picorv32 量到的現象相同。
- 不同的地方都在允許誤差的族群內：slack、skew、線長、via、功耗、IR，以及繞線器中間各輪的 DRC 數。cell 數、面積、各種違規數、最終 DRC、LVS 每次都完全相同。
- GRT-0229 在第 3、4 次各出現一次（第 1、2 次沒有），都由有上限的重試處理（`pnr/librelane_flow.sh`）。

## Checker qualification 總表

第 4 次 regress 的結果。每一案都要在**預期的** checker FAIL，FAIL 在別處或沒 FAIL 都算該案沒抓到：

| target | 植入的錯誤 | 結果 |
|---|---|---|
| `neg-rtl` | RTL／firmware 的 bug（R01–R07 與 Phase 1 qualification 補的案例） | 33/33 |
| `neg-pnr` | PnR、STA、PDN、IR、DRC、XOR、擺放、輸入一致、golden（P00–P31，P00 是 positive control） | 32/32 |
| `neg-eqy-soc` | 最終網表改 1 處（stuck-at、反相、mux 對調、NAND→NOR、flip-flop 換種類、clock 反相） | 9/9；位置交叉檢查 60 組 |
| `neg-eqy-core` | 同上，picorv32 | 11/11；位置交叉檢查 104 組 |
| `neg-gl-soc` | 網表植入錯誤（4 種用 11 支測試、3 種用 directed 測試、1 種把 cell 的電源接錯，用帶電源網表） | 8/8 |
| `neg-gl-core` | picorv32 網表植入錯誤 | 2/2 |
| `neg-provenance` | 未提交的修改、少 submodule、LibreLane 版本或內容不對、PDK 版本或內容不對、HEAD 改變、`resolved.json` 讀範圍外或經 symlink 的檔、沒有來源紀錄；加 3 個 positive control | 19/19 |
| `neg-run-guard` | 9 個下游步驟 × 3 種壞 run，加 positive control | 37/37 |
| `neg-regress` | `make regress` 本身：髒的工作目錄、`make -i`、中途換 commit、target FAIL，加 positive control | 5/5 |
| `test-flow-retry` | GRT-0229 重試的判斷：最多重試 2 次、其他錯誤不重試 | 7/7 |

合計 163 案，全部符合預期。

## 與計畫不同的地方

1. **時序目標**：計畫的 40 ns（silicon 目標）與 25 ns（stretch）都沒有達成；soc_top 改 42 ns（使用者決定，ADR-0004 補充）。
2. **EQY 的範圍**仍是合成網表 vs 最終網表；RTL vs 合成網表由 gate-level 模擬加 directed 測試涵蓋。另加 flip-flop 結構比對。
3. **SDF 時序模擬沒做**：計畫的 L5 寫「SDF 只作參考」；Icarus 不能當時序證據，時序以 15 個 corner 的 STA 為準。
4. **`make harden D=<design>`**：run 的目錄名稱仍是設計名稱，不用 git sha；run 的 commit 由 `provenance.json` 記錄，下游步驟逐一比對 HEAD。
5. **resizer 只看 9 個 corner**：溫度反轉的 2 個 PVT 只在 signoff STA 判定（15 個全給 resizer 時跑不完）。
6. **IR 的判定改成 VDD＋GND 合計**，供電模型改一側供電；picorv32_core 保留 LibreLane 的預設模型。
7. **新增 4 個 skill**（使用者要求）：`flow-regression-reproducibility`、`multicorner-sta`、`dv-directed-tests`、`phase-exit-review`；其他 10 個 skill 寫回本階段的經驗。`cts-clock-tree` 與 `drv-timing-closure` 的 Phase 4 經驗（SRAM clock 的 latency 對齊、clock pin 的線切段、resizer 看不到的 corner 用 PnR 餘量補）是使用者在結案後再問時才補上的。沒有更新的 5 個（`antenna-signoff`、`floorplan-congestion`、`hard-macro-integration`、`lvs-signoff`、`rtl-synthesis-lint`）在 Phase 4 沒有新的做法或發現。

## 已知限制（帶到後續階段）

1. **SRAM 的時序仍是假設值**（ADR-0007），而且現在直接決定週期：42 ns 時 ss_n40C 只剩 +0.31 ns。Phase 3.5／6 用 OpenRAM 特性化後要重新檢討週期。
2. **duty cycle 45/55%、jitter 0.15 ns 是假設**（`clock_uncertainty.sdc`），Phase 7 確定 Caravel 的 clock 後替換。
3. **IR 的供電位置是假設**（一側供電）。如果 Caravel 只從一點供電，20 mV 與 EM 都不過（`docs/notes/ir_worst_case_soc_top.md`）。
4. **溫度反轉 corner 沒有給 resizer 看**：目前靠較大的 PnR 餘量（max transition 0.70 ns、hold 0.3 ns）在 signoff 通過；設計再變大或更緊時可能不夠。
5. **CTS 會把 SRAM 的 clock 延到與 flip-flop 一樣晚**，這對半週期路徑與 SRAM 輸入的 hold 都不利；目前沒有可用的設定關掉。
6. **EQY 的證明只涵蓋組合邏輯**：flip-flop 的 cell 種類與 clock 接線由 EQY 之外的結構比對涵蓋（`run_eqy.py` 判定第 6、7 點）；RTL → 合成網表沒有 formal 證明，靠 gate-level 模擬與 directed 測試，firmware 沒用到的功能沒有檢查。
7. **`counters` 抓不到計數器高半部「卡 0」**（要 2^32 個 cycle）。
8. **LVS 中 SRAM 是 black box、金屬密度不合格、golden 只在同一環境下逐項比對、GRT-0229 用重試繞過**：同 Phase 3 已知限制 2、5、8、9。
9. **下游步驟單獨執行時不檢查工作目錄是否乾淨**（`run_guard.py` 只比 commit）：單獨 `make gl-soc` 時，RTL 與測試可能來自未 commit 的修改。`make regress` 有開頭與結尾的檢查，不受影響。不在 guard 加這項，是因為開發時要能用未 commit 的修改在 dev fixture 上測試（獨立審查第 5 項）。
10. **`make py-check` 只檢查同一個檔案內的名稱**：從別的模組 import 的名稱改名後，要到執行時才會發現（獨立審查第 9 項）。
11. **neg-eqy 的位置範圍在大扇出的 net 上仍然很大**：`flop_async_reset` 新接上 `resetn`，範圍包含整棵 reset buffer 樹（291 個名稱）。交叉檢查仍分得出它與其他案例。
12. **「第三人重現」只在同一台機器驗證過**：4 次乾淨 checkout 都在這台 Mac；沒有在另一台機器試過。另一台機器的 CPU 核心數不同時，多執行緒繞線的結果可能超出 golden 的誤差範圍（推測，沒有實測）。
13. **繞線器中間各輪的 DRC 數只比 key**：誤差 ±100 等於不比數值；如果某次繞線多跑或少跑幾輪，key 會多或少，golden 比對仍會 FAIL（到目前每次都是同一組 key）。

## 獨立審查（2026-10-04）

結案前請兩個沒參與實作的 agent 反向檢查，都限定只讀檔案與做幾秒內的小實驗（另一個 worktree 正在跑 regress）：

- **文件核對**：逐項比對 Phase 4 文件的數字與說法和 run 的證據。找到 13 項寫錯（例如第 5 次 harden 的 limits 其實還有一列 FAIL：沒有寄生值的 driver 133 vs 上限 134；`pnr/soc_top/README.md` 有 4 個數字停在 40 ns）、19 項說得不準確、4 項找不到證據，都已更正或標明（`ba2b1bc`）。
  - 找不到證據的 4 項：
    - 「Phase 3 的 11 個案例交換後判不符」：改成每次 `neg_eqy.py` 自動做交叉檢查。
    - 第 4 次 harden 的 resizer 原因：改標推測。
    - picorv32 在 Phase 4 的 EQY：由 regress 補上。
    - agent 的 EQY 實驗：標明紀錄沒有保存。
  - 順帶找到 `check_signoff.py` 的 golden 摘要列算錯，已修正。
- **找 checker 漏洞**：找到 10 項，沒有一項讓這次的結果變成假 PASS。使用者決定（2026-10-04）修正後再跑一次 regress。8 項已修正並各有 negative test（`6367393`），2 項列為已知限制 9、10：

| # | 漏洞 | 修正 | negative test |
|---|---|---|---|
| 1 | flip-flop 與 SRAM 的 clock pin 接線沒有人檢查：EQY 的 `sat` 先把所有 flip-flop 改成同一個隱含 clock，結構比對只比 cell 種類 | `run_eqy.py` 判定第 7 點：從每個 clock pin 往回追，兩份網表要追到同一個 port、反相次數相同 | `flop_clk_inverted`（兩個設計）、`clk0_inverted` |
| 2 | IR 電壓源只檢查點在 strap 上：大小改成 2000 µm 或移到 strap 中間都 PASS | 大小 ≤ strap 寬度、在 strap 左端 | P27、P28 |
| 3 | provenance 只比 PDK_ROOT 字串：另一份同名的版本目錄、或經 `~/.ciel/sky130A` symlink 讀範圍外的檔都 PASS | 解開 symlink 後比對 | `resolved_other_install`、`resolved_symlink` |
| 4 | `make regress` 只在結尾讀一次 HEAD：中途 commit 時，前段 target 跑的是舊 commit | 開始前要求工作目錄乾淨並記下 HEAD，結束時必須相同 | `neg_regress.py` 的 `dirty`、`head_changed` |
| 5 | 下游步驟不檢查工作目錄 | 不修，已知限制 9 | — |
| 6 | `make -i regress` 讓 FAIL 的子 make 回 0，結果是假的 `regress: PASS` | 開始前拒絕 `-i`／`-n`／`-q`／`-t` | `neg_regress.py ignore_errors` |
| 7 | 幾個 negative test 沒證明它聲稱的事：P21、P23 只看第一個問題；neg-eqy 的位置範圍把整條 bus 算進去；`flop_q_inverted`、P07 的說明寫錯；ff 的 SRAM derate 沒有測 | checker 印出全部問題的種類，斷言看全部；位置範圍逐 bit，並加交叉檢查；說明改正；`check_soc.py sram_derate` | P30；交叉檢查 |
| 8 | `[max_sum]` 接受負值：VDD 19 mV + GND −15 mV 判 PASS | 每一項都要 ≥ 0 | P29 |
| 9 | `py-check` 不看跨檔案的名稱 | 不修，已知限制 10 | — |
| 10 | DRC 位置比對的 100 nm 容許值套到全部 30 種規則 | 只給量到需要的 li.5、diff/tap.9；golden run 仍是 0 個無法解釋的框 | P21（之前已有） |

## 使用者決定（2026-10-04）

1. soc_top 的週期改 42 ns，不放寬任何假設或檢查（「時序目標」一節；ADR-0004 Phase 4 補充）。
2. Phase 4 的重要任務也要分析並建立對應的 skill：新增 4 個（「與計畫不同的地方」第 7 點）；`phase-exit-review` 規則 8 規定以後每個 Phase 收尾都做這個分析。
3. 獨立審查找到的 checker 漏洞先修正，再在乾淨 checkout 跑一次 `make regress`，以第二次的結果結束 Phase 4。第二次在 harden-soc FAIL（見第 5 點）。
4. 開始前已決定（2026-10-04，Phase 3 收尾時）：IR 上限 20 mV、SRAM derate 1.575／0.665、nom_tt 10% 規則只報告、Phase 3 的 5 個 checker 漏洞在 Phase 4 開頭修。
5. `make regress` 第 2 次因繞線器中間各輪的 DRC 數不同而 FAIL：這組數字給 ±100 的誤差（兩個設計），最終 DRC 數仍要完全相同；補 negative test P31，再在乾淨 checkout 跑第 3 次，以第 3 次的結果結束 Phase 4（第 3 次在 gl-soc-powered 因牆鐘時限 FAIL，修正見「Phase 4 新找到的 checker 問題」，由第 4 次結束）。另一個選項（單執行緒 detailed routing，估計每次多 30–50 分鐘、golden 要重做、是否真的每次一樣未知）沒有採用。

## 交付物

- `scripts/regress.py`（`make regress`）、`scripts/neg_regress.py`、`scripts/check_py_names.py`（`make py-check`）。
- `signoff/scripts/run_guard.py`、`neg_run_guard.py`；`provenance.py`（LibreLane clone、PDK 內容、解開 symlink、`--final`）、`neg_provenance.py`；`env/pdk_content.sha256`；`check_signoff.py` 的 `[max_sum]`。
- `pnr/soc_top/`：`clock_uncertainty.sdc`、`vsrc/`、`sram_drc_alone.py`；修改 `config.json`（42 ns、15 個 corner、`RSZ_CORNERS`、resizer 餘量、`CTS_CLK_MAX_WIRE_LENGTH`、`VSRC_LOC_FILES`）、`pnr.sdc`、`signoff.sdc`、`sta_extra_corner.tcl`、`check_soc.py`、`neg_pnr.py`（P00–P31）、`run.sh`、README。
- `signoff/eqy/run_eqy.py`（sequential cell 與 clock 來源比對）、`neg_eqy.py`（新案例、位置檢查、交叉檢查）、README。
- `dv/gl_soc/`（`--powered`、新的 negative test）、`dv/tb/tb_soc.v`、`dv/log_whitelist.txt`、`dv/tests.toml`；`fw/tests/counters`、`fw/tests/buserr`。
- `signoff/limits/`（含繞線器中間各輪 DRC 數的誤差）、`signoff/golden/soc_top/`（42 ns）。
- 文件：`docs/notes/signoff_criteria_soc_top.md`（Phase 4 實作狀態）、`docs/notes/ir_worst_case_soc_top.md`、`docs/notes/ir_study/`；ADR-0004、ADR-0007 補充；README、toolchain.md。
- `.claude/skills/`：新增 4 個（共 19 個），其他寫回本階段的經驗。
- Makefile 新增的 target：`regress`、`py-check`、`neg-regress`、`neg-run-guard`、`gl-soc-powered`、`provenance-final`、`harden D=`。
