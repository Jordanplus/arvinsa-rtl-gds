# ADR-0006：soc_top 的 DIE_AREA = 1000 × 800 µm

- 狀態：已採用（2026-10-03），Phase 3 實測後可依下方「重新檢討的條件」調整。
- 背景：`project-plan.md` §5.4 規定 `FP_SIZING=absolute`，`DIE_AREA` 要等 Phase 2 量到 PicoRV32 的實際面積才決定。§5.4 當時的粗估是「約 1.0 × 0.9 mm 起」。

## 輸入數據

| 項目 | 值 | 出處 |
|---|---|---|
| PicoRV32 單獨 harden 後的 standard cell 面積 | 196970 µm²（含 tap cell，不含 fill cell；core 272662 µm²，使用率 72%，40 ns 下 9 個 corner 的 setup／hold、slew／cap／fanout 全 PASS） | `signoff/golden/picorv32_core/metrics.json` 的 `design__instance__area__stdcell` |
| soc_top（不含 SRAM）／PicoRV32 的面積比 | 1.152（同一套本機 Yosys 合成流程與 TT liberty 的結果：131399 ÷ 114023） | `make soc-area`（`scripts/soc_area_estimate.py`） |
| 估計 soc_top 的 standard cell 面積 | 196970 × 1.152 ≈ 227000 µm² | 同上 |
| SRAM macro | 683.1 × 416.54 µm | `project-plan.md` §5.1（LEF） |
| SRAM 周圍保留 | 左、下各 10 µm halo（不放 cell 的隔離區）；右、上各 25 µm channel，給 port 1 的 tie-off 線與電源網路走線 | `project-plan.md` §5.4（halo 10 µm、channel ≥ 20–30 µm） |
| SRAM 加保留區 | (10 + 683.1 + 25) × (10 + 416.54 + 25) = 718.1 × 451.5 µm ≈ 324000 µm² | 計算 |
| die 到 core 的邊界 | 左右各約 5.5–6 µm、上下各約 11 µm（LibreLane 預設 margin） | Phase 2 run 的 `design__die__bbox` 與 `design__core__bbox` |

## 候選比較

本 ADR 的「使用率」一律指 **logic 區使用率** = standard cell 面積 ÷（core 面積 − SRAM 加保留區 324251 µm²），用 LibreLane metrics 計算就是 `design__instance__area__stdcell` ÷（`design__core__area` − 324251）。注意 LibreLane 自己的 `design__instance__utilization` 是（standard cell + macro 面積）÷ core 面積，會把 SRAM 本體（284539 µm²）算進去，數值不同：1000 × 800 時 logic 區使用率 51% 約等於 `design__instance__utilization` 66%。Phase 2 的 PicoRV32 沒有 macro，兩者相同，在 72% 收斂。

| DIE_AREA (µm) | logic 可用面積 µm² | 估計使用率 | SRAM 左側空間寬 | SRAM 下方空間高 |
|---|---|---|---|---|
| 850 × 800 | 328000 | 69% | 120 µm | 326 µm |
| 900 × 850 | 411000 | 55% | 170 µm | 376 µm |
| **1000 × 800** | **445000** | **51%** | **270 µm** | **326 µm** |
| 1000 × 900 | 544000 | 42% | 270 µm | 426 µm |

## 決策

`DIE_AREA = 0 0 1000 800`（0.80 mm²），SRAM 放右上角、orientation N（§5.4 的擺放規則不變；確切座標在 Phase 3 依 placement grid 與電源網路決定）。

理由：
1. **預留約 20 個百分點的使用率餘裕**：Phase 2 在 72% 收斂，但 Phase 3 會多出 Phase 2 沒有的負擔。一是 SRAM 用保守的 padded.lib，SRAM 路徑可能要多做時序修復。二是 SRAM 輸入要加 antenna diode 或 buffer（§6.4）。三是 SRAM 的 met1–met4 都被擋住，pin 附近的繞線會比較擠。51% 留下了這些空間；850 × 800 的 69% 沒有餘裕。
2. **SRAM 左側留 270 µm**：port 0 的左側 pin（clk0、csb0、web0、addr0[8:2]）面向這一塊。900 寬時只剩 170 µm，CPU 與匯流排邏輯大多要擠到下方。
3. **比 §5.4 的粗估（約 1.0 × 0.9 mm）小**：§5.4 估 SRAM 含 halo 約 0.30 mm²、logic 以 50% 密度估 0.4–0.55 mm²，合計用上限約 0.85 mm²。實測 logic 是 227000 µm² ÷ 50% ≈ 0.45 mm²，落在估計範圍中間；加上 SRAM 與保留區 0.32 mm²，約 0.77 mm²，取 1000 × 800 = 0.80 mm²。

## Phase 3 定案的 SRAM 位置（2026-10-03 補充）

`pnr/soc_top/config.json` 的 `MACROS.sram0.location = [301.76, 364.48]`、orientation N：SRAM 右緣在 x = 984.86 µm、上緣在 y = 781.02 µm，離 die 右邊 15.14 µm、上邊 18.98 µm。座標在 core 的 site 格點上（core 原點 5.52, 10.88；site 0.46 × 2.72 µm）。

與上表「右、上各 25 µm channel」的差異：第一次試跑把 SRAM 放在離 die 右、上各約 25 µm（core 邊界內還剩 6–10 µm 的 standard cell row），PDN 在這條窄 row 上放不下電源 strap，OpenROAD 報 `PDN-0179 Unable to repair all channels` 而中止。改成讓 SRAM 的 10 µm halo 蓋過 core 的右、上邊界，這兩側就沒有 standard cell row；port 1 的 tie-off 線改在 core 外、die 內的空間繞，實測 routing DRC = 0、LVS PASS。logic 區只剩 SRAM 左側（約 276 µm 寬）與下方（約 344 µm 高）的 L 形區域，使用率仍在 50% 左右（Phase 3 exit review 有實測值）。

## 重新檢討的條件（Phase 3）

- PnR 後 logic 區使用率 > 65%（上面的公式，不是 `design__instance__utilization`），或 global routing 報告 congestion overflow，就改成 1000 × 900。
- logic 區使用率 < 40%，而且 9 個 corner 的 setup／hold、DRV 都有餘裕時，可以考慮縮小。
- 調整時更新這份 ADR，並在 Phase 3 exit review 記錄原因。

## 出處

`project-plan.md` §5.1、§5.4、§6.4；`pnr/picorv32_core/README.md`；`docs/phase_exit/phase2.md`。
