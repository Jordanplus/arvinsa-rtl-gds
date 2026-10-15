# criteria review：soc_top_hazard3（Phase 6 第三輪 harden，2026-10-10）

## 有沒有被執行

`criteria_review.txt` 第一部分 6 項全部 PASS（config_applied、step_config、uncertainty、uncertainty_applied、signoff_corners、checkers_ran）。最後一行：`criteria-review: PASS`。

這是 Phase 6 第三輪 harden（commit `ad184f5`：OpenRAM patch 0002–0004 重產的 SRAM）。上一輪（`3ceca55`，`.prev`）的 KLayout DRC 27 都在 SRAM 裡，這輪是 0。

各 checker 的 FAIL 列：
- `timing__unannotated_net__count` 152（上限 126）：**上限是預建 macro 時推導的數字，要為這顆 macro 重算**。逐一分類（15 個 corner 都是 152）：CTS 假負載（`clkload*`）109 + `sram0/dout1[31:0]` 32 + tie cell 空端 11（10 個用 LO 空 HI：`addr1[8:0]` 9 個與 core 的 `_21857_` 1 個；1 個用 HI 空 LO：`csb1`）。三類都在推導裡。照決定 16 重算成 152。
- golden 比對 100 列：**設計改變**（同 PicoRV32），golden 用這一輪重建。
- `check_soc` 的 `sram_drc_ref`：參考檔是預建 macro 的；SRAM 單獨 5,576,010、29 種，與 PicoRV32 相同（同一份 GDS），用這一輪重建。
- 其餘 PASS：KLayout DRC 0、XOR 0、LVS 0、antenna 0、`magic_drc`、`macro_gds`、`port1_tieoff`、`sta_setup`、`ir_worst`。

「不分析的項目清單」這次沒有新增。

## 合不合理

| criterion | 當初的依據（出處） | 這次的實測 | 判斷 |
|---|---|---|---|
| resizer setup 餘量（0.1／0.025 ns） | 最後一次修復到 signoff 的差距（ADR-0014） | setup 修復沒有違規表；signoff 最差 +0.656 ns | 依據仍成立 |
| resizer hold 餘量（0.3／0.05 ns） | 同上 | ResizerTimingPostGRT 修完 +0.133，signoff +0.126 ns，差距 0.007 ns（< 0.05） | 依據仍成立 |
| hold 餘量的代價 | hold buffer 數與面積 | final 網表 hold buffer 2783 顆；stdcell 面積 240,768 µm² | 依據仍成立 |
| slew 上限與餘量 | Phase 3 長線 slew 問題 | 15 個 corner max slew／cap／fanout 都是 0 | 依據仍成立 |
| corner 清單（15 個，溫度反轉） | ss −40°C 最差 | 最差 setup 在 min_ss_n40C_1v60（+0.656 ns），最差 hold 在 min_ff_n40C_1v95（+0.126 ns） | 依據仍成立 |
| uncertainty（半週期 2.45 含 DCD 2.2 ns） | `clock_uncertainty.sdc` | 最差半週期路徑 sram0 → `_21042_` +0.656 ns（扣 2.45 ns）；DCD 仍是假設值 | 依據仍成立（DCD 仍是假設） |
| skew | skill 規則 4 | hold skew nom_ff_n40C −0.438、nom_ss_n40C −1.290 ns（扣掉 hold uncertainty） | 依據仍成立 |
| 上限檔依設計結構推導的數字（unannotated） | `signoff/limits/soc_top_hazard3.toml`：為 Hazard3 推導（不是抄 PicoRV32） | 152 = 109 + 32 + 11；舊的 126 是預建 macro 的 | **依據成立，數字為這顆 macro 重算成 152**（決定 16 授權） |
| 最壞組合 IR（≤ 20 mV） | Phase 5 決定（ADR-0017；Hazard3 的最壞組合曾到 25.75 mV） | VDD 7.41 + GND 7.33 = 14.74 mV | 依據仍成立（餘量 5.3 mV，比 PicoRV32 小，持續注意） |

## 學習

- 工具行為（觀察，未查根因）：detailed routing 報 25 行 `[WARNING DRT-0418] Term sram0/<pin> has no pins on routing grid`（`addr0` 3、`addr1` 2、`clk0`、`web0`、沒繞線的 `dout1` 18）。自產 SRAM 的第一輪就有（上一輪也是 25），預建 macro 沒有；最終 DRC、LVS 都是 0。推測是 OpenRAM 腳位座標沒有對齊 sky130 的繞線格點；寫進 `hard-macro-integration` 經驗紀錄。
- Hazard3 最差 setup 仍是 SRAM 半週期讀出（+0.656 ns，上一輪 +0.643），SRAM 修 DRC 沒有改變時序。
- unannotated：假負載 109（上一輪 108），組成穩定。
- 新數字沒有超出 knowledge 檔的範圍，不另寫；沒有依據不成立的 criterion，沒有提案。
