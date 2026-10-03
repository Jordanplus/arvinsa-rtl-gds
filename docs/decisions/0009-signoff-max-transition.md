# ADR-0009：PnR 的 max fanout 用 8；signoff max transition 放寬到 1.0 ns（已撤回）

- 狀態：第 2 點（PnR max fanout 8）採用中。第 1 點（signoff max transition 1.0 ns，2026-10-03 使用者決定）**已於同日撤回**：降低 global placement 目標密度（`PL_TARGET_DENSITY_PCT` 55）後，9 個 corner 在原本的 0.75 ns 下都沒有 max slew 違規，不再需要放寬。signoff 恢復 LibreLane 原本的 0.75 ns 與 fanout 10（`pnr/soc_top/signoff.sdc` 現在就是 `base.sdc`）。以下保留當時的紀錄。
- 範圍：只有 `soc_top`（`pnr/soc_top/`）。Phase 2 的 `picorv32_core` 不變（0.75 ns 就收斂了）。

## 背景

- **max transition（slew）**：訊號從 10% 變到 90%（或反向）所花的時間。太慢會讓延遲計算不準、短路電流變大、容易受雜訊影響，所以要設上限。
- LibreLane 對 sky130 用的上限 0.75 ns 來自 PDK 附的 OpenLane 預設設定（`$PDK_ROOT/sky130A/libs.tech/openlane/sky130_fd_sc_hd/config.tcl` 第 63 行 `MAX_TRANSITION_CONSTRAINT 0.75`），是設計上的保守值，不是 library 的限制。
- sky130_fd_sc_hd 的 .lib（tt／ss／ff 三份）：`default_max_transition` 1.5 ns；少數 pin 自己標 `max_transition` 1.0 ns，是整份 library 最嚴的值；延遲表的輸入 slew 特性化到 5 ns。

soc_top 試了下列修復設定後，ss corner 仍有 16 個 pin、5–6 條 net 停在 0.78–0.97 ns（其他 corner 都是 0）：

| 試跑 | 設定 | ss corner max slew 違規 |
|---|---|---|
| soc_explore2 | Phase 2 的設定 | 50（0.75–1.09 ns） |
| soc_explore4 | + placement 後長線切段 200 µm | 20（0.755–0.932 ns） |
| soc_explore6 | + GRT 後修復餘裕 50% | GRT 後修復跑 26 分鐘以上不結束，停掉 |
| soc_explore7 | GRT 後修復餘裕 40% | 16（0.775–0.970 ns），另 1 個 fanout |
| soc_explore8 | + placement 後長線 120 µm | GRT 後修復跑 13 分鐘以上不結束，停掉 |
| soc_explore9 | + GRT 後長線 400 µm | 與 explore7 完全相同 |
| soc_top 正式 run 1 | + `pnr.sdc` fanout 8、`signoff.sdc` 1.0 ns | 1.0 ns 下仍有 ss 違規，最慢 1.42 ns；最差兩條線大幅繞路（端點相距 117 µm、繞線 353 µm），都在 L 形 logic 區轉角 |
| soc_explore10 | + `PL_TARGET_DENSITY_PCT` 55（原本自動算出 68%） | **0**；改用 0.75 ns 重跑 STA 也是 0 |
| soc_explore11 | + `PL_TARGET_DENSITY_PCT` 50 | 0（0.75 ns 下也是 0） |

這些 net 都是 resizer 自己插的 buffer 樹（`fanout*`、`wire*`），帶 mux 的 select 腳。GRT 後的修復把它當下看到的 1237 個違規全部修完（log 最後一列 Remaining 0），違規是 detailed routing 之後才出現的；LibreLane Classic flow 在 detailed routing 之後沒有修復步驟。

**撤回的原因（後來查到的根因）**：已查證正式 run 1 最差的兩條線是繞線大幅繞路（端點相距 117 µm、繞線 353 µm；另一條 636 µm），都在 L 形 logic 區轉角附近。推測 explore7／9 殘留的違規也是同一原因（沒有逐條查證）。global placement 把 cell 擠在目標密度 68%，而 logic 區整體只用了約一半；降到 55% 後 9 個 corner 都沒有違規，代表繞路造成的負載過大已經消失。長線切段、修復餘裕這些前面的改動仍然有用（違規數 50 → 16），只是不足以處理繞路。

## 決策（當時）

1. **signoff 的 max transition 改成 1.0 ns**（`pnr/soc_top/signoff.sdc`，`SIGNOFF_SDC_FILE`，只有 `OpenROAD.STAPostPNR` 使用）。1.0 ns 是 library 本身最嚴的 pin 限制，仍遠在特性化範圍內，延遲計算有效。PnR 各步驟仍用 0.75 ns 當修復目標（`pnr.sdc` 不改 max transition）。
2. **PnR 的 max fanout 收緊成 8**（`pnr/soc_top/pnr.sdc`，`PNR_SDC_FILE`），signoff 仍是 10。原因：resizer 修完 fanout 之後，antenna repair 才在 net 上加 diode，diode 的 pin 也算一個負載（soc_explore7：一顆 buffer 帶 10 個負載再加 1 顆 diode = 11）。這是收緊實作目標，不是放寬標準。

驗證：在 soc_explore9 的版圖上只重跑 `OpenROAD.STAPostPNR` 並改用 `signoff.sdc`，max slew 違規 16 → 0，setup／hold worst slack 數值不變（其他約束沒有被改到）；fanout 違規仍是 1（由第 2 點處理）。

## 代價與限制

- 最差的 slew 0.97 ns 只比 1.0 ns 少 3%。detailed routing 不是每次都一樣，之後的 run 可能剛好超過；超過時 signoff 會 FAIL，需要再處理，不會被放過。
- 只在 ss corner（1.60 V、100 °C）出現；tt、ff 都在 0.75 ns 以內。
- 這是對 0.75 ns 這個設計保守值的放寬。後續若要回到 0.75 ns，可行的方向是 detailed routing 之後的修復（OpenROAD 可做，LibreLane Classic flow 沒有對應 step），或改 floorplan 讓 logic 區不要是細長的 L 形。

## 出處

`project-plan.md` §7.2（max slew／cap／fanout violation = 0）；`pnr/soc_top/README.md` 試跑紀錄；PDK `libs.tech/openlane/sky130_fd_sc_hd/config.tcl` 第 63–65 行；sky130_fd_sc_hd `.lib` 的 `default_max_transition` 與 `max_transition` 屬性。
