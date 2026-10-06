# ADR-0014：global routing 後再修一次 setup（`RUN_POST_GRT_RESIZER_TIMING`）

- 狀態：已採用（2026-10-07，使用者決定），等 Hazard3 第 5 次 harden 確認
- 背景：ADR-0013 之後，Hazard3 版第 3 次 harden（43 ns）只剩 max_ss_n40C setup −0.381 ns，週期改成 44 ns（ADR-0004 Phase 5 補充）。第 4 次 harden（44 ns）反而變差：max_ss_n40C −1.131 ns（22 條）、nom_ss_n40C −0.187 ns。

## 原因（已驗證）

第 4 次 harden 後第一次做 signoff criteria 檢查（skill `signoff-criteria`「每次 harden 後的檢查」，`runs/soc_top_hazard3_signoff/criteria_review.md`，p5h3 worktree）：

1. CTS 後的 setup 修復（`ResizerTimingPostCTS`）結束時 WNS +0.112 ns；插完 hold buffer 後，繞線前估計是 −0.161 ns；繞線後 signoff 是 −1.131 ns。從修完到 signoff 共差 1.243 ns，其中約 0.97 ns 出現在繞線之後。第 3 次的差距是 0.578 ns。
2. `PL_RESIZER_SETUP_SLACK_MARGIN` 0.1 ns 遠小於這個差距，但不能單純調大：ADR-0013 的實驗 1 顯示，0.6 ns 會擋住 hold 修復。
3. 週期多 1 ns 沒有用：週期一變，placement 與修復 buffer 鏈也跟著變，每次 run 之間差約 1 ns（第 4 次最差路徑的修復 buffer 比第 3 次多 3.4 ns）。

已排除的原因：
- 長線上限 `DESIGN_REPAIR_MAX_WIRE_LENGTH` 200 µm：單步重跑第 32–37 步，改成不設或 600 µm，只少 79 顆 buffer，setup 沒有改善（`runs/p5_h3_exp_wirelength/`）。
- clock skew：flop 之間的 latency 分佈約 0.2 ns，最差路徑兩端只差 0.07 ns。

## 實驗（Hazard3，44 ns，只跑到 signoff STA）

| signoff STA | 第 4 次（現行設定） | A：開 `RUN_POST_GRT_RESIZER_TIMING` | B：`pnr.sdc` `set_max_transition` 0.70 → 0.75 |
|---|---|---|---|
| 從哪裡開始 | — | 第 4 次 run 第 43 步之後接續（前 43 步完全相同） | 從 floorplan 重跑 |
| max_ss_n40C setup | −1.131（22 條） | +0.636 | +0.242 |
| 全部 corner 最差 setup | −1.131 | +0.530（min_ss_n40C） | +0.242 |
| 最差 hold | +0.109 | +0.107 | +0.127 |
| slew／cap／fanout／繞線 DRC／antenna | 0 | 0 | 0 |
| stdcell 數 | 30,414 | 30,474 | 29,857 |

- A 的 `ResizerTimingPostGRT`：找到 65 個 setup 違規 endpoint，修完 WNS +0.002 ns、剩 1 個（`RSZ-0062`）；1 分 49 秒，記憶體最高 1.6 GB。用 global routing 寄生估計的結果偏保守：修完 +0.002 ns，signoff +0.530 ns。
- A 的差異只來自這一步，可以直接歸因。B 從 floorplan 重跑，改善量和 run 之間的浮動分不開。
- 資料：`runs/p5_h3_exp_postgrt_slew/`（本機）。

## 決策

1. `pnr/soc_top/config.json` 與 `config_hazard3.json` 一起加 `RUN_POST_GRT_RESIZER_TIMING: true`（`check_inputs.py` 的 `cpu_config` 仍只允許差 3 個設計相關的 key）。`GRT_RESIZER_SETUP_SLACK_MARGIN`、`GRT_RESIZER_HOLD_SLACK_MARGIN` 用 LibreLane 預設（0.025、0.05 ns）。
2. 週期維持 44 ns（使用者決定）。
3. slew 上限維持 0.70（B 先不採用），之後在 A 的基礎上另外評估。

## 影響

- 兩個 CPU 的 PnR 結果都會改變。PicoRV32 版本來就要重跑，並更新 `signoff/golden/soc_top/`。
- LibreLane 說明這個步驟是實驗性的，可能卡住或跑很久（`librelane/flows/classic.py` 159–163 行）。實驗中只花 1 分 49 秒，正式 harden 仍會監看記憶體與時間。

## 限制

- 實驗只跑到 signoff STA，GDS、Magic DRC、LVS 與 repo 的 checker 要等正式 harden 確認。
- 只有一次實驗，餘量（+0.530 ns）會隨 run 浮動。

## 出處

- `runs/p5_h3_harden4.log`；`../arvinsa-rtl-gds-p5h3/runs/soc_top_hazard3_signoff/criteria_review.md`
- skill `drv-timing-closure` 經驗紀錄（第 4 次 harden、實驗 A、B）；`signoff-criteria` 的 knowledge 檔「實測校準資料」
