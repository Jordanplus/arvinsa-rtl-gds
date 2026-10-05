# soc_top 的 signoff 條件：依據、缺口與建議（2026-10-03；Phase 4 實作狀態 2026-10-04）

推導方法與工具行為在 skill `signoff-criteria`。本文只放 soc_top 的數字。

## 怎麼做的

- 三個 agent 各查一個領域（時序；電源／IR／EM；實體與 PDK 規則），共 53 項。
- 每個領域再由一個獨立 agent 逐條打開出處核對，並在 signoff STA 的 `sta` binary 上做實驗：31 項正確，22 項部分有誤。本文只採用核對後的結論。
- 下面標「已驗證」的有兩種來源：一種是核對 agent 的實驗，另一種是本文作者重現過的實驗（DCD 那一項）。
- 實驗都是用 golden 來源 run（`runs/soc_top`）的 `OpenROAD.STAPostPNR` 做單步重跑，原 run 沒有修改。

## 總表

判斷欄：
- **OK**：條件合理，也有檢查。
- **缺口**：沒檢查，或條件本身沒有依據。
- **不一致**：兩個條件互相矛盾。

| 條件 | 現在的值與出處 | 判斷 | 建議（階段） |
|---|---|---|---|
| setup／hold uncertainty | 0.25 ns，setup 與 hold 同值，PnR 與 signoff 同值（LibreLane 預設，`base.sdc` 65–66） | 缺口：沒有成分說明。clock 來源還沒定義，jitter 未知 | **Phase 4 已做**：`pnr/soc_top/clock_uncertainty.sdc` 分開寫 setup、hold，逐項列成分（見下方「clock uncertainty 的成分」）。jitter 仍是假設值，Phase 7 確定 clock 來源後替換 |
| 半週期路徑的 duty cycle | STA 假設 50% | **缺口**：最緊的路徑就是半週期路徑（見下方第 1 點） | **Phase 4 已做**：半週期路徑用下降緣→上升緣的 uncertainty 加上 DCD 預算（假設 45/55%）；negative test P24（D = 60%）、P25（預算改 60%）都必須 FAIL。數值待 Phase 7 |
| min pulse width、minimum period | 沒有檢查；SRAM padded.lib 規定 12 ns／30 ns | **缺口** | **Phase 4 已做**：`sta_extra_corner.tcl` 每個 corner 輸出 `report_check_types -min_pulse_width -min_period`，`check_soc.py pulse_width` 要求 slack ≥ DCD + 半週期 jitter（pulse width）與 period jitter（period）；negative test P22、P23 |
| fmax | `clock.rpt` 的 `period_min` 25.4 ns | **不能用**：它排除半週期路徑；週期 32 ns 時 setup 已經 FAIL | 最小週期改從半週期路徑反推，nom_ss 約 32.8 ns（推算） |
| OCV | flat ±5%，cell、net、clock、data 全部套用 | OK（sky130 沒有更好的資料） | SRAM 的 instance derate 取代了 ±5%：ss 是 1.5 倍，不是 1.5 × 1.05。**使用者決定（2026-10-04）：改成 1.575／0.665**。**Phase 4 已做**（`sta_extra_corner.tcl`，ADR-0007 補充） |
| PVT corner | 9 個（tt／ss／ff × min／nom／max RC） | **缺口**：溫度反轉。1.60 V 下多數 cell 低溫反而比較慢（dfxtp_1 CLK→Q：ss_n40C 比 ss_100C 慢 11%），PDK 有 `ss_n40C_1v60`、`ff_100C_1v95` 但沒用 | **Phase 4 已做**：`config.json` 的 `STA_CORNERS` 加這兩個 PVT，共 15 個 corner，signoff 與大部分 PnR step 都用；resizer 只看原本 9 個（`RSZ_CORNERS`，15 個全給時 `RepairDesignPostGRT` 跑不完） |
| IR drop 上限 | 90 mV（5% VDD，`project-plan.md` §7.2，沒有推導）；實測 0.306 mV | **不一致**：ss corner 是 1.60 V，Caravel 最低供電 1.62 V，只隱含 20 mV 的預算。IR 真的到 90 mV 時，STA 的 ss 結果就不保守 | **使用者決定（2026-10-04）：上限改成 20 mV**。**Phase 4 已做**（`signoff/limits/soc_top.toml`、`picorv32_core.toml`；P07 在 VDD 降壓與 GND 抬升各植入 11 mV，合計 22 mV 必須 FAIL）。用最大電阻的 RC corner 與真實電壓源位置重算：見 Phase 4 exit review |
| IR 數字本身 | nom_tt 的電流與 RC；電壓源是 PDN 的所有 pin 形狀 | 偏樂觀：0.3 mV 只代表「上層供電理想時，block 內 rail 的壓降」 | 報告寫明這個範圍；粗估單端供電時約 8 mV（推論） |
| IO delay | input 與 output 都是 8 ns，min = max | **缺口**：IO 的 hold 等於沒檢查。但只把 `-min` 改 0 會出現 269 個假的 hold 違規（最差 −3.3 ns），因為外部 launch 被當成 0 latency | Phase 7 用 Caravel 給的 source latency 與 min／max IO delay（範本：caravel_user_project `signoff.sdc` 67–98 行） |
| SI（crosstalk） | 沒有分析；coupling cap 約占繞線電容一半（SPEF：214,162 顆、39.66 pF，接地 78.90 pF） | 缺口（開源工具沒有）。Phase 3：setup 有 3.55 ns 餘量，風險低；hold 最差 0.032 ns，只靠 0.25 ns uncertainty 涵蓋。**Phase 4（42 ns）餘量變小**：setup 最差 +0.313 ns（SRAM 半週期路徑）、hold 最差 +0.082 ns，SI 的風險不能再說低 | 在 hold uncertainty 中明列 SI 的份額；邊界分析要把 clock 與 data 分開（全域 factor 2.0 實測 setup 反而變好 0.11 ns） |
| max transition | 0.75 ns，9 corner 違規 0 | OK | `docs/decisions/0009` 有兩處描述與 .lib 不符，已更正 |
| clock net 的 slew | 沒有另外限制；ss 下 clk port 0.59 ns | 小缺口 | `-clock_path` 在 propagated clock 下無效，要另寫 checker（Phase 4，可選） |
| max cap | 0.2 pF；ss 的 pin 上限比 tt 小約 37% | OK（9 corner 都判） | — |
| SRAM pin 的限制 | `dout0` max_capacitance 0.02756 pF、min 0.0017225 pF；輸入 max_transition 0.5 ns（padded.lib 36） | 這些也是假設值（ADR-0007） | Phase 3.5／6 特性化後校正 |
| hold 的 margin | Phase 3：resizer 修到 0.100 ns，signoff 剩 0.032 ns | 餘量小。router 的變動若超過 golden 誤差（±0.01 ns）就可能變負 | 考慮 `PL_RESIZER_HOLD_SLACK_MARGIN` 0.15（推論，需實跑看面積代價）。**Phase 4 已做**：改成 0.3 ns（hold 在新 corner 變負，見 `pnr/soc_top/README.md`），42 ns 時 signoff 剩 +0.082 ns，hold buffer 多 984 顆 |
| nom_tt setup ≥ 4 ns（週期 10%） | `soc_top.toml` [min] | **沒有作用**：ss 的延遲是 tt 的 1.4–1.9 倍，「ss ≥ 0」一定比它嚴（推算） | **使用者決定（2026-10-04）：降為只報告、不判 FAIL**；餘量改放在 uncertainty 並列出成分。**Phase 4 已做**（兩個 limits 檔的 `[info]`） |
| power grid EM | 沒有分析；總電流 < 5 mA | 風險低（推論），但沒有 checker | 用 `analyze_power_grid -enable_em` 輸出電流後比對 tech LEF（Phase 4，可選） |
| signal EM | 沒有工具 | clock 實際走 met1／met2（PDK 的 `RT_CLOCK_MIN_LAYER met3` 沒有生效）；估算上界 0.39 mA，met1 最小寬度上限 0.85 mA rms，約 2.2 倍餘量 | 寫明「估算」 |
| dynamic IR、aging | 沒有工具 | 缺口 | 列入 margin 的成分 |
| antenna | 0 違規；SRAM LEF 補了 gate 面積（ADR-0008） | OK | — |
| latch-up | Magic 完整 GDS DRC 在 SRAM 外 0 違規；tap 最壞約 13.1 µm（15 µm 規則） | macro 內 OK。**chip-level 注意**：KLayout 輸出的 GDS 沒有 81/14 標記，沒有標記的區域適用 6 µm 規則 | Phase 7 確認 81/14 覆蓋 soc_top；`FP_TAPCELL_DIST` 不要調大 |
| metal density | 沒有檢查。實測全域密度：li1 42.4%、met1 25.8%、met2 14.3%、met3 7.8%、met4 3.5%、met5 2.6% | macro-level 不判；met1–met5 遠低於 35% 下限，chip-level 一定要補 fill | Phase 7 交給平台的 fill。注意 cf-precheck 只檢查上限 |
| KLayout DRC 的涵蓋範圍 | 0 違規 | 不含 latch-up、density、antenna、浮接金屬、nsdm／psdm | 這些由 Magic 完整 GDS DRC 涵蓋（latch-up、implant），其餘見上 |
| LVS | SRAM 是 black box | 已知限制 | Phase 7 的 precheck 有 device-level LVS 與 ERC |

## clock uncertainty 的成分（Phase 4，`pnr/soc_top/clock_uncertainty.sdc`）

數字以 soc_top 的週期 43 ns 計（使用者 2026-10-05 決定由 42 ns 改 43 ns，原因見 ADR-0004 Phase 3.5 補充；2026-10-04 由 40 ns 改 42 ns，見 Phase 4 補充）；DCD 與它相關的兩列隨 `CLOCK_PERIOD` 自動計算。

PnR（`pnr.sdc`）與 signoff（`signoff.sdc`）都 source 同一個檔案。clock 是 propagated，skew 由 STA 算，不放進 uncertainty（skill `signoff-criteria` 時序表）。

| 項目 | 值（ns） | 成分 | 依據 |
|---|---|---|---|
| setup（整週期路徑） | 0.25 | period jitter 0.15（**假設**）＋ 工具沒分析的效應 0.10（SI 的延遲變化、dynamic IR、aging） | jitter 待 Phase 7 的 clock 規格；總數與 LibreLane 原本的 0.25 相同 |
| hold | 0.25 | 0.25：SI 造成的加速、capture clock 的 dynamic IR、寄生萃取誤差。同一個 edge 送出又接收，period jitter 互相抵銷，所以不含 jitter | hold 最緊的是 ff corner |
| 半週期路徑的 setup（下降緣送、上升緣收，以及反方向） | 2.40 | 半週期 jitter 0.15（**假設**，取整週期 jitter）＋ DCD 2.15 ＋ 0.10。DCD =（55% − 50%）× 43 ns，duty cycle 範圍 45/55% 是**假設** | 指定邊緣的 uncertainty 會**取代**一般值，不是相加（skill 規則 3），所以要含完整的 jitter 與 margin。`write_sdc` 會保留這兩行，PnR 後段讀的 SDC 也有 |
| min pulse width 需要的 slack | 2.30 | DCD 2.15 ＋ 半週期 jitter 0.15 | STA 用理想的 50% 波形量脈寬，看不到 DCD |
| min period 需要的 slack | 0.15 | period jitter | 同上 |

「最慢 corner 的餘量」的意思：setup uncertainty 對每個 corner 都一樣，但 setup 只會在 ss corner 被用到（tt、ff 的 slack 大很多），所以這筆餘量實際上只作用在最慢的 corner。

假設值（jitter 0.15 ns、duty cycle 45/55%）在 Phase 7 確定 Caravel 的 clock 來源（`wb_clk_i` 或 `user_clock2`）後，改 `clock_uncertainty.sdc` 開頭的變數即可，其他公式不動。

## 細節

### 1. 半週期路徑與 duty cycle（已驗證，本文作者重現）

9 個 corner 的最差 setup 路徑都是同一類：`sram0` 在 clock 下降緣送出 `dout0`，rdata 暫存器在上升緣接收，只有低電位那半個週期可用。

把 `base.sdc` 的 `create_clock` 加上 `-waveform {0 <高電位時間>}`，在 nom_ss 單步重跑 signoff STA：

| 高電位比例 D | nom_ss setup slack |
|---|---|
| 50%（20 ns） | +3.578 ns |
| 59%（23.6 ns） | −0.022 ns |
| 60%（24 ns） | −0.422 ns |

- 每偏 1% 少 0.4 ns；min_ss 在 D 約 58.9% 時用完。
- 只有 D > 50%（下降緣變晚）會讓這條路徑變差，D < 50% 對它有利。D 變小時，風險轉到另一個 phase 的 min pulse width。
- clock tree 本身造成的 rise／fall 不對稱 STA 已經算到；nom_ss 下 SRAM `clk0` 的 fall 與 rise latency 差約 0.30 ns（核對 agent）。

### 2. IR drop 的預算（已驗證規格與 .lib；結論是推算）

- ss 的 .lib 在 1.60 V 特性化（`sky130_fd_sc_hd__ss_100C_1v60.lib` 153–154）。
- Caravel 的 VCCD 最低 1.62 V（caravel-harness maximum-ratings）。
- 所以 IR 加上電源雜訊的總預算只有 20 mV。`soc_top.toml` 的 90 mV 上限比它大 4.5 倍。
- 目前實測 0.306 mV，沒有違規，但條件本身不一致。

### 3. IO delay 的實驗（核對 agent，nom_ss）

所有 input／output 的 `-min` 改成 0（`-max` 不變），結果 hold 最差 −3.30 ns、269 個違規端點。

原因是 capture 端 flop 的 clock 插入延遲約 3.4 ns，外部 launch 端卻是 0。這不代表真實晶片：外部 flop 也在一棵 clock tree 後面。所以 IO 的 min／max 必須和上層的 clock latency 一起給。

### 4. SI 邊界分析的實驗（核對 agent，nom_ss）

| `read_spef -coupling_reduction_factor` | setup WS | hold WS |
|---|---|---|
| 1.0（預設，鄰線不動） | 3.578 | — |
| 2.0 | 3.693 | 0.714 |
| 0.0 | 3.444 | 0.6905 |

factor 2.0 也讓 capture clock 變慢，而這對 setup 有利，所以全域 factor 不是上界。

## 建議的 Phase 4 待辦（依優先順序）

標「決定」的 3 項，使用者已在 2026-10-04 決定（寫在各項後面）。第 1–7 項 Phase 4 已實作，結果與驗證在 `docs/phase_exit/phase4.md`。其中兩項只做到一部分：第 3 項的電壓源位置仍是假設（一側供電，`docs/notes/ir_worst_case_soc_top.md`）；第 5 項的 hold 0.25 ns 只列出成分名稱，沒有拆出 SI 的數值（開源工具不分析 SI）。

1. **DCD**：建立「來源 DCD + J_half」的 uncertainty 寫法（`-fall_from clk -rise_to clk -setup`），加 D = 60% 必須 FAIL 的 negative test；數值待 Phase 7 的 clock 規格。
2. **min pulse width／minimum period checker**：加檢查與 negative test。
3. **IR 上限改成與 corner 電壓一致**（決定：20 mV）。另用最大電阻的 corner 與真實的電壓源位置重算。
4. **加 corner** `ss_n40C_1v60`、`ff_100C_1v95`（溫度反轉）。
5. **uncertainty 分成 setup／hold**，每個數字附成分表；hold 中明列 SI 的份額。
6. **SRAM derate 保留 OCV**（決定：1.5 改 1.575、0.7 改 0.665）。要重跑 harden-soc 並更新 golden；估計最差 setup slack 從 +3.55 ns 降到約 +2.8 ns（推算）。
7. **nom_tt 10% 規則**（決定：降為只報告、不判 FAIL）。
8. **可選**：clock slew checker、power grid EM 比對、hold margin 0.15。

Phase 7 才能處理的：IO delay 與 source latency、chip-level latch-up 標記、metal fill 與 density、device-level LVS／ERC、供電與封裝的 L·di/dt。
