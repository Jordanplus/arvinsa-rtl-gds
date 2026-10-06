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
   | 哪些 corner 判 FAIL | setup 只判 `*tt*`；hold 判全部 corner（`checker.py` 第 683 行）；max slew、max cap 預設都不判 | 要全部判 FAIL 就把四個 `*_VIOLATION_CORNERS` 都設 `["*"]` |

S10. **sky130_fd_sc_hd .lib 的量測與特性化範圍**：slew 的量測門檻是 20%–80%（tt.lib 157–160）。多數延遲表的輸入 slew 只到 1.5 ns，整份 tt.lib 只有 18 張表到 5 ns（buf_8／12／16）。`default_max_transition` 為 1.5 ns。PDK 的 0.75 ns 是 1.5 的一半，這個關係是推論，沒有出處。

S12. **sky130 只能用 flat derate**：三份 .lib 都沒有 ocv／sigma／LVF 表。本版 OpenSTA 也沒有 LVF（3.0.1 之後才有）。AOCV、POCV 都不適用。

S15. **KLayout 的 sky130 DRC deck**（`sky130A_mr.drc`）：
    - 沒有 latch-up（LU）、`nwell.4`、density、antenna 規則。
    - nsdm／psdm 的寬度、間距、包覆規則只有 `sram_exclude=true` 時才跑（557–633、639–729 行），LibreLane 沒有開，所以這些只由 Magic 檢查。
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

## 溫度反轉（已驗證）

- 1.60 V 時，多數 cell 在 −40 °C 比 100 °C 慢。corner 清單要有 `ss_n40C_1v60`，resizer 也要看得到（`multicorner-sta` 規則 2、3；ADR-0013）。
- 慢多少和路徑組成有關，不是固定值：
  - PicoRV32 SoC 的 SRAM 半週期路徑：ss_100C 和 ss_n40C 只差 0.44 ns。
  - Hazard3 SoC 的長邏輯路徑（約 30 級邏輯）：資料到達時間差 5.9 ns，約 15%（ADR-0013）。
- 結論：用「另一個 corner 多留固定餘量」代替溫度反轉 corner，只對短路徑有效。

## 實測校準資料（每次 harden 檢查後追加）

每一列都要能回答：這個數字拿來校準哪一條 criterion。數字來自 `signoff/scripts/review_criteria.py` 的 `[INFO]` 列，或明寫的實驗。只有一顆設計的數字，不能當成製程通則，下一顆設計要再量一次。

| 日期 | 設計／run | 週期 | 量什麼 | 數值 | 校準哪一條 | 出處 |
|---|---|---|---|---|---|---|
| 2026-10-07 | soc_top PicoRV32（`runs/soc_top`，Phase 4 後的 golden run） | 43 ns | post-CTS hold 修完 → signoff 最差 hold | +0.301 → +0.074 ns（差 0.227） | `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 足夠 | `review_criteria.py --cpu picorv32` |
| 2026-10-07 | 同上 | 43 ns | hold buffer | 3,479 顆；post-CTS stdcell 面積 +17.6% | hold 餘量的代價（`drv-timing-closure` 規則 7） | 同上 |
| 2026-10-07 | soc_top Hazard3 第 3 次（`d00214d`） | 43 ns | post-CTS setup 修完 → signoff 最差 setup | +0.197 → −0.381 ns（差 0.578，max_ss_n40C） | `PL_RESIZER_SETUP_SLACK_MARGIN` 0.1 ns | `runs/p5_h3_harden3.log`、ADR-0013 |
| 2026-10-07 | soc_top Hazard3 第 4 次（`1292ca4`） | 44 ns | post-CTS setup 修完 → 插 hold buffer 後 → signoff | +0.112 → −0.161（繞線前估計） → −1.131 ns（差 1.243，max_ss_n40C） | `PL_RESIZER_SETUP_SLACK_MARGIN` 0.1 ns 遠小於實測差距 | `runs/soc_top_hazard3_signoff/criteria_review.txt`（p5h3 worktree） |
| 2026-10-07 | 同上 | 44 ns | post-CTS hold 修完 → signoff 最差 hold | +0.275 → +0.109 ns（差 0.166） | `PL_RESIZER_HOLD_SLACK_MARGIN` 0.3 ns 足夠 | 同上 |
| 2026-10-07 | 同上 | 44 ns | hold buffer | 2,739 顆；post-CTS stdcell 面積 +13.4% | hold 餘量的代價 | 同上 |
| 2026-10-07 | 同上 | 44 ns | 最差 setup 路徑的組成（max_ss_n40C） | 修復 buffer 22.3 ns（64 顆）、邏輯 20.6 ns（30 顆）；路徑 Manhattan 長約 4.5 mm（晶片 1.0 × 0.8 mm） | slew 上限（`pnr.sdc` `set_max_transition 0.70`、`DESIGN_REPAIR_MAX_SLEW_PCT` 30）是否過嚴：待實驗 | 同上；`drv-timing-closure` 經驗紀錄 |
| 2026-10-07 | 同上（繞線前估計） | 44 ns | flop 之間 clock latency（ss_n40C，第 1 到第 99 百分位） | 3.82–4.02 ns（約 0.2 ns）；SRAM `clk0` 2.87 ns，早 1.1 ns；ff_n40C 早 0.24 ns | skew 不是這條 setup 違規的主因（只佔 0.07 ns） | `runs/p5_h3_exp_wirelength/lat.log`（本機） |
| 2026-10-07 | 同上（單步實驗，第 32–37 步） | 44 ns | `DESIGN_REPAIR_MAX_WIRE_LENGTH` 200 → 0 或 600 µm | 長線 buffer 79 → 0 顆，ss_n40C setup −0.161 → −0.255 ns（在 run 之間的浮動內） | 長線上限不是路徑上 buffer 多的原因 | `drv-timing-closure` 經驗紀錄 |

## 待確認（推測，不能當規則用）

- hold 餘量用預設 0.1 ns 時，hold buffer 也有 2,200–2,500 顆（`drv-timing-closure` 規則 7）。修復前違反 hold 的 endpoint 數接近 flop 總數，原因還沒拆開。
- CTS 讓 SRAM 和 flop 的 clock latency 對齊（`cts-clock-tree` 規則 10），但 ss_n40C 時 SRAM 早 1.1 ns、ff_n40C 時早 0.24 ns：看起來只在某一個 corner 對齊。
