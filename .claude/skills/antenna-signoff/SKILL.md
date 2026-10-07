---
name: antenna-signoff
description: antenna 違規（OpenROAD `check_antennas`）、diode 插入與它造成的 fanout／slew 副作用，或 macro 的 LEF 沒有 antenna 資料（`ANTENNAGATEAREA`，`Odb.CheckMacroAntennaProperties` 警告）時使用：從 macro 的 SPICE 算閘極面積補進 LEF、允許長度估算、不要用 heuristic diode insertion、OpenROAD 與 Magic 的差異、Classic flow 沒有 antenna checker。長線修復的設定值看 drv-timing-closure。Use for antenna violations and repair, diode side effects, and macros whose LEF lacks antenna data (OpenROAD/LibreLane; sky130 numbers).
---

# Antenna signoff

**antenna 效應**：製造時金屬線在接上上層之前會收集電荷；只接到閘極又夠長時會擊穿閘極氧化層。規則看「金屬面積（sky130 用側面積）÷ 閘極面積」，所以必須知道閘極面積。長線修復的設定值在 `drv-timing-closure`。本 repo 實例：ADR-0008、`ip/sram/.../gate_area.py`、`gen_antenna_lef.py`。

## 規則（已驗證）

1. **macro 沒有 `ANTENNAGATEAREA` 時**，antenna 檢查看不到接到 macro 輸入的線（LibreLane `Odb.CheckMacroAntennaProperties` 會警告）。做法：從 macro 自己的 SPICE 算閘極面積（攤平階層、加總閘極接在該 pin 上的電晶體 W×L），產生補上資料的 LEF。2 KB SRAM：57 個 pin 是 0.6 µm²（OpenRAM DFF 的 D），`clk0/1` 是 0.168 µm²。
2. **估算允許長度**（sky130 tech LEF，無 diode 時側面積比 400）：0.6 µm² 閘極時 met1／met2（厚 0.35 µm）約 340 µm，met3／met4（厚 0.8 µm）約 150 µm。單用「線總長」判斷不正確。
3. **不要用 `RUN_HEURISTIC_DIODE_INSERTION`**：它對全設計所有超過 90 µm 的線加 diode（soc_top 插了 10231 顆），之後 global routing 反覆壅塞迭代不收斂。
4. **副作用**：antenna repair 在 resizer 修完之後才加 diode，diode 的 pin 也算 fanout；單一長線可能被插 10–11 顆（soc_explore2）。對策：長線修復讓線變短（diode 224 → 61 顆），PnR 的 fanout 目標收緊到 8（ADR-0009）。
5. **ODB 快取 LEF**：要用不同 LEF 驗證時，直接 `openroad` 讀 tech LEF、cell LEF、macro LEF 加最終 DEF，再跑 `check_antennas`。
6. **報告的 Required 欄不一定是 400**：節點透過下層連到 driver 的擴散區時，上限依 diff PWL 提高（soc_top post-GRT 報告有 3 列在 met5，Required 2956.40）。
7. **`diode_2` 本身帶 `ANTENNAGATEAREA` 0.4347**（`sky130_fd_sc_hd.lef` 18185），OpenROAD 會把它加進閘極面積（`AntennaChecker.cc` 483–487）。所以插 diode 之後，可容許的長度放寬得比「比值上限」本身更多；手算時要用（閘極 + 0.4347）。`conb_1` 的 HI／LO 沒有 `ANTENNADIFFAREA`，不會被當成放電路徑。
8. **OpenROAD 不讀 `ANTENNAPARTIALMETAL*AREA`**：macro 階層之間的 antenna 只能靠 port diode（`DIODE_ON_PORTS`）或在上層插 diode。
9. **Magic 的 antenna 參數和 tech LEF 不完全一樣**：via1 在 Magic 是 3＋18×A，tech LEF 與 SkyWater via.1 是 6＋36×A（`sky130A.tech` 第 5087 行對照 `nom.tlef` 第 140 行），而且 Magic 不模擬 diode。拿 PDK 的 `check_antenna.py`（Magic）當第二意見時要知道這兩點。
10. **LibreLane 的 antenna checker**：Classic flow 沒有 antenna 的 Checker（`Checker.KLayoutAntenna` 只在 Chip flow，`chip.py` 44–45）。`DRT_ANTENNA_REPAIR_MARGIN` 有宣告但沒有被使用，`drt.tcl` 第 105 行傳的是 `GRT_ANTENNA_REPAIR_MARGIN`。本 repo 的 antenna 判定在 `signoff/limits/*.toml`。

## negative test

P06：SRAM LEF 的閘極面積除以 1000 → `check_antennas` 違規從 0 變 58 個（證明檢查看得到 SRAM 輸入）。

## 用完後

更新「經驗紀錄」；換 macro 時重算閘極面積，不要沿用舊值。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_explore1 | `Inserted 10231 diodes.`，GRT 不收斂 | 已驗證：heuristic 對全設計長線加 diode | 不用 heuristic，改 antenna LEF | ADR-0008 |
| 2026-10-03 | soc_explore2 | 7 個 max fanout 違規 | 已驗證：每條線 10–11 顆 diode | 長線修復 200 µm | `pnr/soc_top/README.md` |
| 2026-10-03 | signoff 條件調查（核對 agent） | 規則 6–10 的工具行為 | 已驗證（讀 OpenROAD dcf36133 原始碼與 PDK 檔案、比對報告） | 寫進規則 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-07 | Phase 5 Hazard3 第 6、7 次 harden 與 golden（第 5 次）比較 | antenna diode 數 100（golden）／94／101，最後 antenna 違規都是 0。第 7 次：detailed routing 後的 antenna 修補前兩輪與 golden 相同（找到 70、插 95；找到 5、插 5），第 2 輪後重繞剩 1 個（golden 剩 0），多跑一輪多插 1 顆；第 6 次是更早的 global routing 不同，第 43 步一開始就找到 103 個（golden 109） | 已驗證：diode 數跟著繞線結果走，不是固定的；detailed routing（多執行緒）與第 41 步的 global routing 都不可重現 | golden 的 diode 數給誤差（±55，ADR-0015）；antenna 違規數仍必須是 0 | p5h3 worktree `runs/p5_h3_h6_signoff/`、`runs/p5_h3_h7_signoff/` 的 `criteria_review.md` |
