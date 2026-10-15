# criteria review：soc_top（Phase 6 第三輪 harden，2026-10-10）

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS（config_applied、step_config、uncertainty、uncertainty_applied、signoff_corners、checkers_ran）。最後一行：`criteria-review: PASS`。

這是 Phase 6 第三輪 harden（commit `ad184f5`：OpenRAM patch 0002–0004 重產的 SRAM，macro 單獨 KLayout 0、Magic full 對預建 PASS）。上一輪（`3ceca55`，現在是 `.prev`）的 KLayout DRC 27 都在 SRAM 裡，這輪是 0。

各 checker 的 FAIL 列：
- `timing__unannotated_net__count` 144（上限 118）：**上限是預建 macro 時推導的數字，要為這顆 macro 重算**。逐一分類（`57-openroad-stapostpnr/*/checks.rpt`，15 個 corner 都是 144）：CTS 假負載（`clkload*`）102 + `sram0/dout1[31:0]` 32 + tie cell 空端 10（9 個用 LO 空 HI：`addr1[8:0]`；1 個用 HI 空 LO：`csb1`）。三類都在推導裡，沒有別的 driver。CTS 假負載比預建 macro 時多（時脈樹也驅動 `clk1`，決定 9），tie 少一個（`clk1` 不再接 tie-low）。照 ADR-0018 決定 16「依設計結構推導的上限照推導規則重算」改成 144。
- golden 比對 134 列：**設計改變**（macro 換成自產、尺寸與位置變、`clk1` 接時脈、這輪 SRAM 腳位右移 0.42 µm），不是 flow 不可重現；golden 用這一輪重建（決定 16）。
- `check_soc` 的 `sram_drc_ref`：**參考檔是預建 macro 的**（5,579,161、30 種）；SRAM 單獨 5,576,010、29 種（met2.2、nwell.5a 已修掉；少了預建才有的 `Can't overlap those layers`）。用這一輪重建參考檔。
- 其餘 PASS：`klayout__drc_error__count` 0、`design__xor_difference__count` 0、LVS 0、antenna 0、`magic_drc`（SRAM 外 0；框內 4,770,846 個都對得上 SRAM 單獨的位置）、`macro_gds`（169 個 cell 與 macro GDS 相同）、`port1_tieoff`、`sta_setup`（15 個 corner 沒有警告）、`ir_worst`。

「不分析的項目清單」這次沒有新增。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer setup 餘量（`PL_RESIZER_SETUP_SLACK_MARGIN` 0.1、`GRT_RESIZER_SETUP_SLACK_MARGIN` 0.025 ns） | 最後一次修復到 signoff 的差距（skill signoff-criteria「resizer 的 slack margin」、ADR-0014） | setup 修復沒有違規表（RSZ corner 沒有 setup 違規）；signoff 最差 +0.769 ns | 依據仍成立 |
| resizer hold 餘量（`PL_RESIZER_HOLD_SLACK_MARGIN` 0.3、`GRT_RESIZER_HOLD_SLACK_MARGIN` 0.05 ns） | 同上 | ResizerTimingPostGRT 修完 +0.068，signoff +0.082 ns，差距 −0.014 ns（沒有變差） | 依據仍成立 |
| hold 餘量的代價 | hold buffer 數與面積（skill「hold 餘量」） | final 網表 hold buffer 3589 顆（上一輪 3521）；stdcell 面積 256,786 µm²（上一輪 256,412） | 依據仍成立 |
| slew 上限與餘量（PnR `set_max_transition` 0.70、`DESIGN_REPAIR_MAX_SLEW_PCT` 30、GRT 40） | Phase 3 長線 slew 問題（`pnr/soc_top/README.md`） | 15 個 corner max slew／cap／fanout 都是 0 | 依據仍成立 |
| corner 清單（15 個，溫度反轉） | ss −40°C 最差（knowledge S 系列） | 最差 setup 在 min_ss_n40C_1v60（+0.769 ns），最差 hold 在 min_ff_n40C_1v95（+0.082 ns） | 依據仍成立 |
| uncertainty（setup 0.25、hold 0.25、半週期 2.45 含 DCD 2.2 ns） | `clock_uncertainty.sdc` 的成分 | 30000 條路徑都套到；最差半週期路徑 sram0 → `_21857_` +0.769 ns（扣 2.45 ns）；DCD 2.2 ns 仍是假設值 | 依據仍成立（DCD 仍是假設） |
| skew（metric 含 uncertainty 與 5 % derate） | skill 規則 4 | hold skew nom_ff_n40C −0.479、nom_ss_n40C −1.429 ns（扣掉 hold uncertainty） | 依據仍成立 |
| 上限檔依設計結構推導的數字（unannotated） | `signoff/limits/soc_top.toml`：CTS 假負載＋`dout1` 32＋tie cell 空端 | 144 = 102 + 32 + 10，三類都對得上；舊的 118 是預建 macro 的 | **依據成立，數字為這顆 macro 重算成 144**（決定 16 授權） |
| 最壞組合 IR（≤ 20 mV） | Phase 5 決定（ADR-0017） | VDD 2.93 + GND 2.93 = 5.87 mV | 依據仍成立 |

## 學習

- 工具行為（觀察，未查根因）：detailed routing 報 25 行 `[WARNING DRT-0418] Term sram0/<pin> has no pins on routing grid`（`addr0` 3、`addr1` 2、`clk0`、`web0`、沒繞線的 `dout1` 18）。自產 SRAM 的第一輪就有（上一輪也是 25），預建 macro 沒有；最終 DRC、LVS 都是 0。推測是 OpenRAM 腳位座標沒有對齊 sky130 的繞線格點；寫進 `hard-macro-integration` 經驗紀錄。
- SRAM 修好 DRC 後（patch 0002–0004），SoC 的 KLayout DRC、XOR、LVS 都是 0，`clk1` 接系統時脈下最差 setup 仍是 SRAM 半週期讀出（+0.769 ns），與上一輪（+0.716）同一條路徑。
- unannotated 的組成和上一輪同一套推導，只是假負載數隨時脈樹變（106 → 102）；這個數字會隨 CTS 變，上限檔的註解要寫出組成，不能只寫總數。
- 新量到的數字（IR 5.87 mV、hold buffer 3589）沒有超出 knowledge 檔的範圍，不另寫。
- 沒有依據不成立的 criterion，沒有提案。
