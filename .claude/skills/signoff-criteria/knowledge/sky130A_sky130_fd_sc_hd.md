# sky130A + sky130_fd_sc_hd：signoff criteria 的製程知識

適用：PDK `sky130A`（open_pdks `8afc8346`，`env/versions.mk`）、標準元件庫 `sky130_fd_sc_hd`、LibreLane 3.0.14、OpenROAD dcf36133、OpenSTA 857316ff。PDK 或工具升版時，S 開頭的每一條都要重新確認（`../SKILL.md`「用完後」）。

格式與更新方式見 [README.md](README.md)。

## 已驗證的製程事實

編號沿用 `SKILL.md`「已驗證的工具行為」的原編號（S2 = 原規則 2），舊引用都還找得到。

S2. **LibreLane 對 sky130 的預設**（`librelane/config/pdk_compat.py`、`librelane/scripts/base.sdc`、PDK `libs.tech/openlane/sky130_fd_sc_hd/config.tcl`）：

   | 項目 | 值 | 說明 |
   |---|---|---|
   | clock uncertainty | 0.25 ns，setup 與 hold 同值 | pdk_compat 327–328；base.sdc 65–66；沿用 OpenLane 1 的常數，沒有成分說明 |
   | clock transition | 0.15 ns | 只在 ideal clock 時使用；signoff（propagated clock）不使用，改用實際算出的 slew |
   | timing derate | early 0.95、late 1.05，套用到 cell、net、clock 與 data path 全部 | base.sdc 71–73；這是唯一的 OCV 建模 |
   | IO delay | 週期 × 20%，input 與 output 都是，min = max | base.sdc 19–20、44–45 |
   | 輸入驅動／輸出負載 | `inv_2/Y`／33.442 fF（= inv_16 的 A pin） | PDK config 27–31 |
   | max transition／cap／fanout | 0.75 ns／0.2 pF／10 | PDK config 62–64 |
   | 哪些 corner 的違規會判 FAIL | setup 只有 `*tt*` 會；hold 全部 corner 都會（`checker.py` 第 683 行）；max slew、max cap 預設都不會 | 要所有 corner 都判 FAIL，就把四個 `*_VIOLATION_CORNERS` 都設 `["*"]` |

S10. **sky130_fd_sc_hd .lib 的量測與 characterization 範圍**：slew 的量測門檻是 20%–80%（tt.lib 157–160）。多數延遲表的輸入 slew 只到 1.5 ns，整份 tt.lib 只有 18 張表到 5 ns（buf_8／12／16）。`default_max_transition` 為 1.5 ns（PDK 的 0.75 ns 和它的關係見「待確認」）。pin 的 `max_capacitance` 每個 corner 不同：ss 比 tt 小約 37%（原在 `../SKILL.md` 規則 9；`docs/notes/signoff_criteria_soc_top.md` 第 33 行）。

S12. **sky130 只能用 flat derate**：三份 .lib 都沒有 ocv／sigma／LVF 表。本版 OpenSTA 也沒有 LVF（3.0.1 之後才有）。AOCV、POCV 都不適用。

S15. **KLayout 的 sky130 DRC deck**（`sky130A_mr.drc`）：
    - 沒有 latch-up（LU）、`nwell.4`、density、antenna 規則。
    - nsdm／psdm 的寬度、間距、包覆規則在 `sram_exclude` 的兩個分支都會跑（557–633、639–729 行）；`true` 只是先排除名稱符合 `*sky130_sram_*kbyte_*` 的 cell，LibreLane 用預設 `false`，全部形狀都查（2026-10-11 更正：原本誤讀成只在 `true` 時跑；Phase 6 在 OpenRAM 產生的 SRAM 裡報了 psdm.1）。`nwell.6` 不論設定都排除這種名稱的 cell。
    - LibreLane 傳的 `floating_metal`、`topcell`、`threads` 和 deck 讀的變數名對不上（`$floating_met`、`$top_cell`、`$thr`），所以浮接金屬檢查開不起來。
    - 結論：「KLayout DRC = 0」不代表 latch-up、density、antenna 合格。

S16. **latch-up**：
    - SkyWater 的預設規則是 tap 到 diffusion 6 µm。只有 `areaid.lowTapDensity`（81/14）覆蓋、且距 padframe ≥ 50 µm 的區域，才能用 15 µm（skywater-pdk `rules/layers.html`）。
    - Magic 寫 GDS 時會自動產生 81/14，KLayout 的 GDS 沒有。
    - `FP_TAPCELL_DIST 13` 的意思是每列 tap 間距 2 × 13 µm，相鄰列錯開半格，最壞約 13 µm。

S17. **metal density**：
    - Classic flow 不插 metal fill，也不檢查 density。`FillInsertion` 只放 standard cell filler 與 decap。
    - 下限 35%（met5 45%）只寫在 PDK 的 Magic `check_density.py` 裡。
    - ChipFoundry 的 cf-precheck 只檢查上限（`met_min_ca_density.lydrc`）。
    - slotting（m1–m4 .11／.12）與 m*.13 是銅製程專用規則，sky130 是鋁後段，不適用。

S18. **antenna**：
    - OpenROAD 的比值與 tech LEF 一致。
    - Magic 的 via1 參數比較嚴（3＋18×A，tech LEF 與 SkyWater 是 6＋36×A；`sky130A.tech` 第 5087 行）。
    - `diode_2` 本身帶 `ANTENNAGATEAREA` 0.4347，OpenROAD 會把它加進閘極面積。
    - OpenROAD 不讀 `ANTENNAPARTIALMETAL*AREA`，所以 macro 階層之間的 antenna 只能靠 port diode。

S19. **PDK 的 `RT_CLOCK_MIN_LAYER met3` 在 LibreLane 3 沒有生效**（`resolved.json` 為 None），clock 實際走 met1／met2。要讓 clock 走粗金屬，必須在專案 config 明確設定。

## temperature inversion（已驗證）

- 1.60 V 時，多數 cell 在 −40 °C 比 100 °C 慢。corner 清單要有 `ss_n40C_1v60`，resizer 也要看得到（`multicorner-sta` 規則 2、3；ADR-0013）。
- 慢多少和路徑組成有關，不是固定值：
  - PicoRV32 SoC 的 SRAM 半週期路徑：ss_100C 和 ss_n40C 只差 0.44 ns。
  - Hazard3 SoC 的長邏輯路徑（約 30 級邏輯）：資料到達時間差 5.9 ns，約 15%（ADR-0013）。
- 結論：用「另一個 corner 多留固定 margin」代替 temperature inversion 的 corner，只對短路徑有效。

## 實測校準資料（每次 harden 檢查後追加）

每一列都要能回答：這個數字拿來校準哪一條 criterion。數字來自 `signoff/scripts/review_criteria.py` 的 `[INFO]` 列，或明寫的實驗。只有一顆設計的數字，不能當成製程通則，下一顆設計要再量一次。

| 日期 | 設計／run | 週期 | 量什麼 | 數值 | 校準哪一條 | 出處 |
|---|---|---|---|---|---|---|
| 2026-10-07 | soc_top PicoRV32（`runs/soc_top`，Phase 4 後的 golden run） | 43 ns | post-CTS hold 修完 → signoff 最差 hold | +0.301 → +0.074 ns（差 0.227） | `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 足夠 | `review_criteria.py --cpu picorv32` |
| 2026-10-07 | 同上 | 43 ns | hold buffer | 3,479 顆；post-CTS stdcell 面積 +17.6% | hold margin 的代價（`drv-timing-closure` 規則 7） | 同上 |
| 2026-10-07 | soc_top Hazard3 第 3 次（`d00214d`） | 43 ns | post-CTS setup 修完 → signoff 最差 setup | +0.197 → −0.381 ns（差 0.578，max_ss_n40C） | `PL_RESIZER_SETUP_SLACK_MARGIN` 0.1 ns | `runs/p5_h3_harden3.log`、ADR-0013 |
| 2026-10-07 | soc_top Hazard3 第 4 次（`1292ca4`） | 44 ns | post-CTS setup 修完 → 插 hold buffer 後 → signoff | +0.112 → −0.161（繞線前估計） → −1.131 ns（差 1.243，max_ss_n40C） | `PL_RESIZER_SETUP_SLACK_MARGIN` 0.1 ns 遠小於實際跑出來的差距 | `runs/p5_h3_h4_signoff/criteria_review.txt`（p5h3 worktree） |
| 2026-10-07 | 同上 | 44 ns | post-CTS hold 修完 → signoff 最差 hold | +0.275 → +0.109 ns（差 0.166） | `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 足夠 | 同上 |
| 2026-10-07 | 同上 | 44 ns | hold buffer | 2,739 顆；post-CTS stdcell 面積 +13.4% | hold margin 的代價 | 同上 |
| 2026-10-07 | 同上 | 44 ns | 最差 setup 路徑的組成（max_ss_n40C） | 修復 buffer 22.3 ns（64 顆）、邏輯 20.6 ns（30 顆）；路徑 Manhattan 長約 4.5 mm（晶片 1.0 × 0.8 mm） | slew 上限（`pnr.sdc` `set_max_transition 0.70`、`DESIGN_REPAIR_MAX_SLEW_PCT` 30）是否過嚴：待實驗 | 同上；`drv-timing-closure` 經驗紀錄 |
| 2026-10-07 | 同上（繞線前估計） | 44 ns | flop 之間 clock latency（ss_n40C，第 1 到第 99 百分位） | 3.82–4.02 ns（約 0.2 ns）；SRAM `clk0` 2.87 ns，早 1.1 ns；ff_n40C 早 0.24 ns | skew 不是這條 setup 違規的主因（只佔 0.07 ns） | `runs/p5_h3_exp_wirelength/lat.log`（本機） |
| 2026-10-07 | 同上（只重跑第 32–37 步的實驗） | 44 ns | `DESIGN_REPAIR_MAX_WIRE_LENGTH` 200 → 0 或 600 µm | 長線 buffer 79 → 0 顆，ss_n40C setup −0.161 → −0.255 ns（在 run 之間的浮動內） | 長線上限不是路徑上 buffer 多的原因 | `drv-timing-closure` 經驗紀錄 |
| 2026-10-07 | soc_top Hazard3 實驗 A（第 4 次 run 第 43 步之後接續，開 `RUN_POST_GRT_RESIZER_TIMING`） | 44 ns | `ResizerTimingPostGRT` 修完（global routing 寄生估計）→ signoff 最差 setup | +0.002 → +0.530 ns（signoff 比估計好 0.53；CTS 後估計則是比 signoff 好 1.24） | 繞線後 setup 修復的 margin（`GRT_RESIZER_SETUP_SLACK_MARGIN` 預設 0.025 ns 已足夠）；`PL_RESIZER_SETUP_SLACK_MARGIN` 不必加大 | `runs/p5_h3_exp_postgrt_slew/`（本機） |
| 2026-10-07 | soc_top Hazard3 第 5 次（`3a28d54`，開 `RUN_POST_GRT_RESIZER_TIMING`） | 44 ns | `ResizerTimingPostGRT` 修完 → signoff 最差 setup | +0.002 → +0.530 ns（min_ss_n40C）；這一步拿掉 12 顆 buffer、放大 54 個 cell，不新增 buffer。與實驗 A 完全相同 | `GRT_RESIZER_SETUP_SLACK_MARGIN` 預設 0.025 ns 足夠（第 2 次觀察） | `runs/p5_h3_h5_signoff/criteria_review.md`（p5h3 worktree） |
| 2026-10-07 | 同上 | 44 ns | post-CTS hold 修完 → signoff 最差 hold | +0.275 → +0.107 ns（差 0.168） | `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 足夠 | 同上 |
| 2026-10-07 | 同上 | 44 ns | 最差 setup 路徑（min_ss_n40C） | 半週期路徑：`sram0` 在下降緣 launch，clk→dout0 15.76 ns、hold buffer 1.44 ns、邏輯 0.83 ns；扣 2.45 ns uncertainty（DCD 2.2）；launch 端 clock 比 capture 端晚 0.67 ns（SRAM clock 前 9 顆 delay buffer） | 44 ns 下的 slack 取決於 DCD 預算（duty cycle 55% 的假設） | 同上；`runs/p5_h3_h5/57-openroad-stapostpnr/min_ss_n40C_1v60/max.rpt`（p5h3 worktree） |
| 2026-10-07 | 同上 | 44 ns | `sram_dout0` 上的 hold buffer | 32 條各直接接 1 顆 `dlygate4sd3_1`（PicoRV32 版插在 mux 之後、flop 的 D 之前，最差路徑上 1.17 ns）；經過它的 hold slack min_ff_n40C +0.679 ns。來源是 ADR-0010 的 `rising_edge` hold arc | hold margin 的代價會落在半週期路徑上 | 同上 |
| 2026-10-07 | 半週期路徑（`sram0` 下降緣 launch → flop 上升緣 capture）的最差 setup slack，三個 run 比較（`review_criteria.py` 新的 INFO 列） | 43／44 ns | PicoRV32（`runs/soc_top`，43 ns，DCD 2.15）+0.384 ns，也是全晶片最差路徑；Hazard3 第 4 次（44 ns，DCD 2.2）+0.552；第 5 次 +0.530 | 兩個 CPU 的最差 setup 都落在 SRAM 讀出的半週期路徑上（第 4 次因為長路徑違規才不是）；兩次 Hazard3 run 之間只差 0.02 ns，比一般路徑穩定。DCD 預算是這顆 SoC 週期的主要限制之一 | `review_criteria.py` 對三個 run 的輸出 |
| 2026-10-07 | soc_top Hazard3 第 6 次（`d6f3074`，flow 設定與第 5 次相同） | 44 ns | `ResizerTimingPostGRT` 修完 → signoff 最差 setup；hold；半週期路徑 | +0.041 → +0.556 ns（全修完，66 個違規 endpoint）；hold +0.275 → +0.109；半週期 `sram0` → `_21021_` +0.556 | 與第 5 次一致：global routing 估計比 signoff 保守約 0.5 ns（第 2 次觀察）。這次第 41 步的 global routing 與第 5 次不同（偶發，見 `flow-regression-reproducibility` 經驗紀錄），所以這組數字是另一組繞線的結果 | p5h3 worktree `runs/p5_h3_h6_signoff/criteria_review.md` |
| 2026-10-07 | soc_top Hazard3 第 7 次（`4d309de`，flow 設定相同；第 41 步與第 5 次相同，只有 detailed routing 不同） | 44 ns | `ResizerTimingPostGRT` 修完 → signoff；hold；半週期路徑 | +0.002 → +0.529 ns；hold +0.275 → +0.107；半週期 `sram0` → `_21021_` +0.529 | global routing 估計比 signoff 保守約 0.5 ns（第 3 次觀察）。半週期路徑的最差 setup 四次 run（第 4–7 次）在 +0.529～+0.556 ns，最穩定 | p5h3 worktree `runs/p5_h3_h7_signoff/criteria_review.md` |
| 2026-10-07 | soc_top Hazard3，golden（第 5 次）對 4 組 run（第 6、7 次與兩組第 41 步不同的接續 run） | 44 ns | 同設定 run 之間的最大差異 | slack 0.040（setup）／0.063（hold）ns、skew 0.048 ns、stdcell 14 顆、diode 11 顆（golden 100）、繞線總長 0.10%、中間輪 DRC 262 | 這些差異是 flow 不可重現造成的，不是設計改變；golden 誤差以它們的約 5 倍訂（ADR-0015）。PicoRV32 Phase 4 的差異小得多（regress 第 2 次：slack 等連續量都在 0.01 ns／0.1% 的誤差內、中間輪 DRC 差 3） | ADR-0015；`signoff/limits/soc_top_hazard3.toml` |
| 2026-10-07 | soc_top PicoRV32 Phase 5 第 1 次（`c976976`，設定與 Hazard3 第 8 次相同：ADR-0013、ADR-0014） | 44 ns | 最差 setup 路徑（min_ss_n40C） | −0.113 ns（nom_ss_n40C −0.012，9 個違規 endpoint）：半週期路徑 `sram0` → `_21860_`，clk→dout0 15.76、mux 前 hold buffer 1.42、mux 0.81、mux 後 hold buffer 1.15 ns；32 條 `sram_dout0` 各直接接 1 顆 `dlygate4sd3_1`（Phase 4 只有 mux 後那顆，+0.384 ns @43 ns） | hold margin 在 SRAM 讀出路徑的代價（ADR-0014 已知限制）在 PicoRV32 造成 FAIL；原因沒有分開試 | p5h3 worktree `runs/p5_pico_h1_signoff/criteria_review.md` |
| 2026-10-07 | 同上 | 44 ns | post-CTS hold 修完 → GRT 後 → signoff 最差 hold；經過 mux 前 hold buffer 的 hold 路徑 | +0.300 → +0.104 → +0.080 ns；min_ff_n40C 經過 `hold7844` 的 hold slack +0.838 ns，`hold7844` 佔 0.421 ns | 以 signoff 寄生看，mux 前那顆不是 hold 必需的（直接相減，未實際拿掉重算） | 同上 |
| 2026-10-07 | 同上 | 44 ns | `ResizerTimingPostGRT`（global routing 寄生）→ signoff，半週期路徑 | 估計沒有 setup 違規（沒修，slack 0.025）→ signoff −0.113 ns：這條路徑估計偏樂觀至少 0.14 ns（Hazard3 長邏輯路徑是偏悲觀 0.5） | ADR-0014「GRT 估計偏悲觀」不能套到半週期路徑 | 同上 |
| 2026-10-07 | 同上 | 44 ns | `timing__unannotated_net__count` | 119 = 76 dummy load + 32 `dout1` + 11 tie cell（Phase 4：133 = 90 + 32 + 11） | 上限隨 clock tree 變；設計改完後重推 | 同上 |
| 2026-10-08 | soc_top 兩個 CPU：乾淨 regress layout（`7348fab`），以及 Hazard3 加寬 met5 後（`1dee974`，p5h3 `runs/soc_top_hazard3`） | 44 ns | static IR（VDD 與 VSS 兩端 IR drop 的合計；電壓源位置是 ir_study 的模型 C，只從一側供電）nom_tt 對「ff 電流＋ss 金屬電阻」 | met5 1.6 µm：Hazard3 18.28 → 25.75 mV（比 1.41）、PicoRV32 7.40 → 10.36（1.40）；met5 4.8 µm：Hazard3 9.98 → 14.13（1.42），via4 EM 78 % → 約 18 %（PDN what-if） | IR 上限只檢查 nom_tt 不夠：比值約 1.4，所以 nom_tt 必須 ≤ 約 14 mV，worst-case 組合才會在 20 mV 內；現在由 `pnr/soc_top/ir_worst.py` 直接檢查 worst-case 組合 | `docs/notes/ir_study/phase5/`、`docs/phase_exit/phase5.md` |
| 2026-10-07 | soc_top 兩個 CPU，接續實驗 D（CTS `-no_insertion_delay`，p5h3 worktree `runs/exp_p_d`、`runs/exp_h_d`） | 44 ns | SRAM `clk0` 前的 delay buffer 拿掉後：最差 setup；hold；SRAM 輸入腳 hold（min_ff） | PicoRV32 −0.113 → +0.765、hold +0.080 → +0.079、SRAM 輸入 +0.197 → +0.093；Hazard3 +0.530 → +1.116、+0.107 → +0.106、+0.338 → +0.320 ns | 半週期路徑的 DCD 預算 2.2 ns 下 44 ns 的 slack；`PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 仍保住 SRAM 輸入腳 | ADR-0016 |
| 2026-10-07 | sky130_fd_sc_hd `.lib`（slew 0.1 ns、負載 3 fF 插值） | — | delay cell／buffer 的 ss_n40C_1v60 ÷ ff_n40C_1v95 延遲比 | `dlygate4sd3_1` 1.116／0.389（2.87）、`dlygate4sd1_1` 3.03、`dlymetal6s6s_1` 3.30、`buf_1` 2.47 | 在 data 端補 hold 的 setup 代價約 3 倍（`cts-clock-tree` 規則 12） | `drv-timing-closure` 經驗紀錄 |
| 2026-10-07 | soc_top 兩個 CPU，ADR-0016 正式 harden（`2caad0e`，p5h3 worktree `runs/p5_pico_h3`、`runs/p5_h3_h10`） | 44 ns | 最差 setup／hold；post-CTS → GRT 後 → signoff 的 hold | PicoRV32 +0.765／+0.079（hold +0.300 → +0.069 → +0.079）；Hazard3 +1.116／+0.106（+0.293 → 無 → +0.106）；與接續實驗 D 相同 | 半週期路徑 DCD 預算 2.2 ns 下 44 ns 的 slack；hold margin 0.3 ns 足夠 | 兩個 run 的 `criteria_review.md` |
| 2026-10-07 | 同上 | 44 ns | `timing__unannotated_net__count` | PicoRV32 118 = 75 dummy load + 32 `dout1` + 11 tie；Hazard3 126 = 82 + 32 + 12（15 個 corner 相同） | 上限隨 CTS 改變；結構不變 | 同上 |
| 2026-10-13 | Caravel user_project_wrapper（Hazard3 SoC 平放，die 2920 × 3520 µm，density 50；`f721cff`，`runs/user_project_wrapper`） | 44 ns | `ResizerTimingPostGRT` 修完 → signoff 最差 setup；hold（post-CTS → post-GRT → signoff） | setup +0.047 → +0.548 ns（min_ss_n40C，差 0.50）；hold +0.292 → +0.207 → +0.187 ns（max_ff_100C） | global routing 估計比 signoff 保守約 0.5 ns，wrapper 也成立（第 4 次觀察）；`GRT_RESIZER_HOLD_SLACK_MARGIN` 0.2 足夠 | `runs/p7_formal_signoff/criteria_review.md` |
| 2026-10-13 | 同上 | 44 ns | hold buffer；clock latency 與 hold skew（nom_ss_n40C） | 3,291 顆（soc_top Hazard3 2,783）；wb_clk_i 外部 latency 5.57 ns（Caravel SDC）＋pin 到 block 長線 buffer 約 2 ns，葉端 latency 9.4–11.4 ns；skew metric −3.598 ns（soc_top −1.540），扣 hold uncertainty −3.348 | block 放在大 die 角落、clock 從 wrapper 邊緣進來時，葉端 latency 差變大、hold buffer 變多；skew metric 裡不平衡的成因是推測，見「待確認」。彙總的 `clock__skew__worst_hold` 是各 corner 取最大（最不負）的值，不是最差值 | 同上；`*-openroad-stapostpnr/nom_ss_n40C_1v60/skew.min.rpt` |
| 2026-10-13 | 同上，與 density 55 的 `p7_harden5` 比較 | 44 ns | density 55 → 50：內部 net 最差 slew；setup | 0.779 → 0.576 ns（上限 0.75，max_ss_n40C）；setup +0.630 → +0.548 ns；繞線總長 +0.2% | 局部 met2 熱點的繞路用降低 placement 密度解決（`drv-timing-closure` 規則 13、ADR-0019 決定 21） | ADR-0019 決定 21 |
| 2026-10-13 | 同上 | 44 ns | `timing__unannotated_net__count`；`design__disconnected_pin__count` | 667（組成見 `signoff/limits/user_project_wrapper.toml`；density 55 時 661）；327 = 321 個沒用到的訊號 port + 6 個電源 port | 上限隨 CTS 改變，wrapper 要自己推導，不能抄 soc_top | limits 檔 |
| 2026-10-13 | 同上 | 44 ns | 從 Caravel pad 算的 IR（max-power pattern 對 vectorless，slow corner，met4 strap 4.8 µm） | pattern 最差 19.58 mV（max_ss_100C，VDD 11.93 + GND 7.65），vectorless 45.57 mV，比值 0.43；density 55 時 19.71／45.87 mV | vectorless 會高估約 2.3 倍；20 mV 上限要用 pattern 的結果檢查（ADR-0019 決定 20）。density 55 → 50 對 IR 影響 0.13 mV | `runs/p7_formal_signoff/criteria_review.md`；ADR-0019 決定 22 |
| 2026-10-13 | Caravel user_project_wrapper，Phase 7 IR 研究（`p7_harden2` netlist；pattern 與 vectorless 的比較用 met4 4.8 µm 的 what-if layout） | 40／44 ns | IR 檢查方式各步驟的量測（原在 `../SKILL.md`「IR 用多大的電流」第 2、4、5、6 項，2026-10-15 移入） | 功耗拆解（nom_tt 13.7 mW）：邏輯 45%、修復 buffer 32%、clock tree 14%、hold 5%、SRAM 4%；只按功耗比例縮放的粗估 35 mV，實際跑出來 45 mV；vectorless 約是 pattern 的 2.2 倍（max_ss_100C 11.4 對 5.1 mW）；固定 toggle rate（nom_tt）：pattern 5.88 mW，每個 net 10%／20%／50% 為 6.66／8.62／14.50 mW，OpenSTA 預設 13.70 mW，clock tree 與 flip-flop 時脈腳約 2 mW 各種 toggle rate 都相同；手算核對：7.6 mA、35.8 mV → 4.7 Ω，與 Caravel ring（約 26 Ω）並聯 wrapper grid 的數量級相符；電壓源位置（同一 layout、同一 worst-case 組合）：wrapper pin 理想 0.3 mV、wrapper ring 左右兩側 8.4 mV、加上 Caravel 網路 104 mV；電壓源放回原處的對照組，DEF 轉 ODB 來回本身差約 0.01%，容許值用 0.1% | `../SKILL.md`「IR 用多大的電流」：先拆解功耗、電流用該 corner 的電壓換算、用 pattern、電壓源從 pad 起算 | ADR-0019 決定 19（第 101 行：104.2、45.2 mV）、決定 20（第 109、111 行：11.4／5.1 mW、固定 toggle rate）；拆解比例、35 mV 粗估、4.7／26 Ω、約 2 mW、0.3／8.4 mV、0.01% 在 repo 裡沒有找到另外的出處（只有 SKILL.md 原文） |
| 2026-10-14 | user_project_wrapper（`7eff65a`，signoff 目錄另存 `runs/p7_decap_signoff/`，`DECAP_CELLS` 改 `ef_decap_12`） | 44 ns | 空白區 2,458,784 個 `decap_3`（netlist 共 2,461,688 個，含 row 兩端的 2,904 個 endcap，endcap 沒換） → 543,617 個 `ef_decap_12` + fill；fill 類 instance、leakage、IR | fill 類 2,608,464 → 974,801；leakage 0.7506 → 0.7396 mW（−0.0110，= 少掉的 decap_3 × ff_100C 4.379 pW 的 98%）；li1 密度 75.1% → 39.9%（`li1.pd.1d` 上限 60%）；IR 最差 0.00205633 → 0.00205617 V；timing、DRC、LVS 每個值都完全相同；harden 240 → 約 182 分鐘 | 沒有 .lib 的 decap 不進功耗報告（S29）；decap 換種類不影響 timing 與靜態 IR | `runs/p7_decap_signoff/criteria_review.md`、ADR-0019 決定 24 |

S20. **sky130_fd_sc_hd 有 drive 太弱、推不動負載的 cell**（Phase 5，只重跑那一步確認；ADR-0012、0013）：
    - 在 resizer 看的最慢 corner，有些驅動力 `_1`（少數 `_2`）的 cell 連最小負載都推不到 slew 上限內。resizer 修 slew 時會把 driver 換成它們，然後停不下來：Hazard3 第一次 harden 為了修 ss_100C 的 slew 違規換上 `a2111oi_1`，記憶體漲到 92.9 GB（ADR-0012；當時 resizer 還沒看 ss_n40C_1v60）。ss_n40C_1v60 加進 resizer 的 corner 之後，又多出 6 種（ADR-0013）。
    - 這次因此排除的 7 種（`EXTRA_EXCLUDED_CELLS`）：`a2111oi_1`、`a2111oi_2`、`o41ai_1`、`nor4b_1`、`a222oi_1`、`o311ai_1`、`nor4_1`。
    - 同一份 `EXTRA_EXCLUDED_CELLS` 另外排除的 4 種 `clkdlybuf4s*` 不屬於這一類：它們是延遲 cell，推得動 `clkbuf_1`，`check_weak_cells.py` 不會列出（拿掉這 4 個排除後 8 列全部 PASS）。排除的理由是 PDK 的排除清單漏了它們，resizer 會拿來當一般 buffer（`drv-timing-closure` 規則 2 第 1 項）。
    - 合成時禁用沒有用：resizer 照樣會換上去。
    - 清單依 corner 與 slew 上限而定，要用 `pnr/check_weak_cells.py` 在最慢的 corner 重新列，不要抄這份。

S21. **`dlygate*` 在 .lib 的 footprint 是 `buf`**（Phase 5，讀 .lib 與 OpenROAD 原始碼確認）：
    - OpenROAD 的 hold 修復因此把它當成一般 buffer，挑「hold 延遲 ÷ 面積」最高的 `dlygate4sd3_1`，整顆晶片只用這一種。
    - 它在 ss_n40C 的延遲是 ff 的 2.87 倍（ff 0.39、ss 1.12 ns）：在 ff 補 hold，到 ss 會吃掉約 3 倍的 setup。
    - 排除它會換成延遲很小的 cell，插的數量多好幾倍，碰到上限就 `RSZ-0060`（`drv-timing-closure` 規則 7）。

S22. **`clkbuf_16` 的下降緣比上升緣慢**（Phase 5，STA 報表）：min_ss_n40C 每顆約 0.31 對 0.21 ns。
    - clock 路徑上串很多級時（CTS 的 macro latency 對齊插了 10 顆），從下降緣 launch 的半週期路徑會被多扣約 1 ns。
    - 有半週期路徑的設計，clock 路徑的級數要少（`cts-clock-tree` 規則 10、ADR-0016）。

S23. **LibreLane 對 sky130 的預設 PDN 與 IR**（Phase 5，what-if 與兩次 harden 實際跑出來的結果；ADR-0017）：
    - **預設 PDN**：met4、met5 strap 都是 1.6 µm 寬，間距約 153 µm；met4–met5 交叉處的 via4 只有 1 個 cut，via4 的 EM 上限是 2.49 mA／cut。
    - **worst-case 組合**（ff 電流＋ss 金屬電阻，met5 每平方 0.037 Ω）的 IR 約是 nom_tt 的 1.4 倍：兩個設計、一側供電、strap 寬 1.6 與 4.8 µm 都量過，1.40–1.42。所以 20 mV 的預算下，nom_tt 要低於約 14 mV。
    - **壓降主要在 met5 strap 本身**。用掉同樣的 met5 金屬量時，加寬比增加 strap 密度有效：4.8 µm 寬時 via4 有 3 個 cut。
    - **只改 met4 幫助很小**。
    - **電流密度上限與片電阻**（原在 `../SKILL.md` 規則 14 與「IR 用多大的電流」第 5 項，2026-10-15 移入）：tech LEF 的 EM 上限例如 met1 DC／AC 2.8／6.1 mA/µm（`docs/notes/ir_study/results_raw.txt` 用 2.8 mA/µm 比對）；met5 每平方電阻 tt 0.0285、ss 0.0370、ff 0.0199 Ω（`docs/notes/ir_worst_case_soc_top.md` 第 28 行）；met4 0.047 Ω／sq（原文沒附出處，也沒寫是哪個 corner），5 µm 寬的 met4 每 mm 約 9.4 Ω（200 個方塊 × 0.047）。

S24. **Magic 對 SRAM macro 內部的 DRC 計數，會隨 macro 上方的金屬改變**（Phase 5）：met5 strap 從 1.6 加寬到 4.8 µm 後，SRAM 範圍內的 Magic DRC 從 4,665,810 變成 4,746,079。每一個違規仍對得上 SRAM 單獨檢查時的位置。macro 內部的 DRC 要用位置比對判斷，不能看總數（`drc-signoff`）。

S25. **sky130 的 OpenRAM SRAM 在低溫、ss 低電壓會讀成前一次的值；機制與有效的修正方式已用 schematic 實驗確認**（Phase 3.5 PDK 附的 macro、Phase 6 OpenRAM 產生的 macro；ADR-0010、ADR-0018 決定 7、8；`docs/notes/openram_phase6_bringup.md`）：
    - 機制：sense amp `sky130_fd_bd_sram__openram_sense_amp` 沒有自己的預充電，每次讀取前靠 bitline 經過只有 NMOS 的 column mux 把內部節點拉回去，最高只到 VDD − Vt。
    - 失敗條件（2 KB 1rw1r，words per row 4，週期 20 ns；PDK 附的與 OpenRAM 產生的相同）：tt −40°C 1.60 V、ss −40°C 1.60 V（Phase 3.5 到 1.95 V 也錯）、ss 25°C 1.60 V。tt 25°C 1.80 V、ss 100°C 1.60 V、ff −40／100°C 1.95 V 正常。STA corner 只有 −40 與 100°C，ss 25°C 這種中間溫度要另外模擬。
    - 有效的修正方式（schematic what-if，單一變因）：讓 sense amp 的輸入端能回到 full VDD。column mux 並聯 PMOS（transmission gate），或在 column mux 輸出端（sense amp 輸入）加一排 PMOS 預充電，都讓上面三個條件讀對。拿掉 column mux（`words_per_row = 1`）也讓 ss 兩個條件讀對，但 2 KB 變成 446.99 × 1152.58 µm。
S26. **兩版 PDK 之間 SRAM 特殊元件改名，影響 LVS 與 SPICE**（open_pdks `e8294524`〔2022-07，OpenRAM 釘的版本〕→ `8afc8346`；只換 PDK 的對照實驗）：
    - bitcell 的 PMOS 從 `sky130_fd_pr__special_pfet_pass` 改名 `sky130_fd_pr__special_pfet_latch`（新 PDK `libs.ref/sky130_fd_pr/spice/sky130_fd_pr__special_pfet_latch.pm3.spice` 第 343 行起的註記，2023-07-16）。舊名稱留了一個轉接 subckt，但用 `.lib sky130.lib.spice tt` 載入時 ngspice 報 `unknown subckt`，不能用。
    - 標準 cell 區域（`scnfet`）裡 `w < 0.42` µm 的 NMOS，新 PDK 萃取成 `sky130_fd_pr__special_nfet_01v8`（`sky130A.tech` 第 5951 行）；舊 PDK 沒有這條。在新 PDK 的 tt 模型下，0.36 µm 的 `nfet_01v8` 與 `special_nfet_01v8` 都能模擬，同一個操作點結果相同。
    - sky130_fd_bd_sram（`fc63b12`）的 cell netlist 仍用舊名，所以用新 PDK 跑 OpenRAM macro 的 LVS 會 `Netlists do not match`；PDK 附的 macro netlist 已是新名。
S27. **sky130 SRAM macro 的整顆 Magic DRC（`drc style drc(full)`）**（Phase 6，PDK `8afc8346`；`ip/sram/openram/drc_baseline_sky130_sram_2kbyte_1rw1r_32x512_8.json`）：
    - bitcell 陣列本來就有大量 SRAM 專用規則的「錯誤」：2 KB PDK 附的 macro 2,235,078 個、30 種（diff/tap.9、li.1、licon.8、poly.8 …），OpenRAM 產生的同規格 macro 有其中 29 種，數量只差幾百。所以 macro 的 DRC 要按規則種類分別比對參考 macro，不能看總數（同 S24）。
    - Deep N-well 的 N-well 保護環要包住 Deep N-well 邊界：外 0.4、內 1.03 µm（nwell.5a）。PDK 附的 macro 剛好是 0.42／1.03 µm；OpenRAM 的預設 DRC 不是 full 規則，抓不到這條。
    - latch-up：diff 到 tap 不能超過 15 µm（LU.2.1：Deep N-well 裡的 N-diff 到 P-tap；LU.3：P-diff 到 N-tap）。2 KB 改成 512 列的瘦長陣列時出現各 80 個。

S28. **sky130 OpenRAM dp bitcell（`sky130_fd_bd_sram__openram_dp_cell`）的待機漏電與 ngspice gmin**（Phase 6，ngspice-47，PDK `8afc8346`；ADR-0018 決定 15、`docs/notes/openram_phase6_bringup.md` 步驟 3e「gmin」）：
    - 待機（4 條 bitline 接 VDD、wordline 接地，Q=0 與 Q=1 相同）每顆漏電，gmin 1e-17：tt 25°C 0.53 pW、ss 100°C 1.01 pW、ff −40°C 0.37 pW、ss −40°C 0.21 pW、ff 100°C 556 pW。
    - ngspice 預設 gmin（1e-12 S）時每顆多約 13.1 pS × VDD²（約 13 個反向偏壓接面），tt 量成 42.7 pW；除了 ff 100°C，量到的幾乎都是 gmin。
    - 2 KB 1rw1r OpenRAM 產生的 macro 整顆待機漏電（縮減版 netlist＋單顆 × 15120）：tt 462 nW、ss 100°C 1.26 µW、ff −40°C 252 nW、ss −40°C 81 nW、ff 100°C 409 µW；tt 與 −40°C 不是穩態值（ADR-0018 已知限制）。

S29. **sky130_fd_sc_hd 的 decap／fill 與 li1 密度**（PDK `8afc8346` 的 GDS，li1 = 67/20 合併面積 / cell 面積；ADR-0019 決定 24、`docs/notes/caravel_precheck_phase7.md` 第 10 節）：
    - li1 比例：`decap_3` 87%、`decap_4` 90%、`decap_12` 97%、`sky130_ef_sc_hd__decap_12` 52%、`fill_1`–`fill_8` 12.5%、`tapvpwrvgnd_1` 56%。
    - PDK 預設 `DECAP_CELL` 只有 `decap_3`（`libs.tech/openlane/sky130_fd_sc_hd/config.tcl` 第 45 行）。大片空白（例如 Caravel wrapper）全部填 `decap_3` 時 li1 約 75%，超過 ChipFoundry precheck `li1.pd.1d` 的 60%（分母是 235/4，整個 wrapper）；改 `ef_decap_12`（加 fill_8／4／2／1）後實際量到 39.9%（本機 KLayout flat 合併面積；同一計算方式在舊 layout 得 75.08%，與 precheck log 的 `li1_ca_density is 0.2492` 一致）。
    - `ef_decap_12` 有 LEF（`sky130_ef_sc_hd.lef`）與 SPICE，沒有 .lib：STA 沒有任何錯誤訊息，但它的漏電不進功耗報告（Phase 7 wrapper：報告的 leakage 少了 0.011 mW，正好是被換掉的 `decap_3` 的 .lib 漏電）。實際的閘極漏電沒有數字，下線的功耗要另外估。

## 待確認（推測，不能當規則用）

- PDK 的 max transition 0.75 ns（S2）剛好是 sky130_fd_sc_hd `default_max_transition` 1.5 ns 的一半；推論 0.75 是由它減半而來，沒有出處（原在 S10，2026-10-15 依 `docs/notes/problem_review/review_skills.md` 1.3 移來）。
- Caravel wrapper 的 hold skew metric（nom_ss_n40C −3.598 ns，扣 hold uncertainty 後 −3.348）裡約 2.7 ns，推測是 `report_clock_skew -hold` 把 Caravel 的 source latency 上下限差與共同路徑 derate 算成扣分，真正影響 hold 的 skew 約 −0.632 ns（soc_top −0.678）。只在現有的 run 上分析，沒有改設定做實驗，也沒讀 OpenSTA 原始碼確認（2026-10-13，`runs/p7_skew_analysis/README.md`；原在校準表 2026-10-13 的 hold buffer 列，2026-10-15 移來）。

- 2 KB 1rw1r 改成 `words_per_row = 1`（沒有 column mux）後，tt −40°C 1.60 V 仍有 2 筆讀錯：只有最後一列（位址 511）的 bit 31，該讀 0 讀成 1；週期 20、30、44 ns 結果相同，所以不是讀取時序的競爭。推測是離寫入電路最遠的 cell 寫不進去或被干擾，沒有量 storage node（Phase 6，`docs/notes/openram_phase6_bringup.md`）。

- hold margin 用預設 0.1 ns 時，hold buffer 也有 2,200–2,500 顆（`drv-timing-closure` 規則 7）。修復前違反 hold 的 endpoint 數接近 flop 總數，原因還沒拆開。
- CTS 讓 SRAM 和 flop 的 clock latency 對齊（`cts-clock-tree` 規則 10），但 ss_n40C 時 SRAM 早 1.1 ns、ff_n40C 時早 0.24 ns：看起來只在某一個 corner 對齊。（Phase 5 之後已用 `-no_insertion_delay` 關掉對齊，ADR-0016，這一條不再影響設計；對齊用哪個 corner 仍沒有查證。）
