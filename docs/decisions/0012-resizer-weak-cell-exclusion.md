# ADR-0012：resizer 不准用推不動一顆 buffer 的弱 cell（排除 `a2111oi_1`），harden 前檢查

- 狀態：已採用（2026-10-06，使用者決定）
- 背景：Phase 5 第一次 `make harden-soc CPU=hazard3` 在 `OpenROAD.RepairDesignPostGPL` 跑了約 108 分鐘，記憶體用到 92.9 GB（機器 24 GB）才被停掉。單步重跑的證據、機制與實驗在 `docs/notes/repair_design_loop.md`。

## 原因（已驗證）

1. 合成出的 `a2111oi_2`（UART 的比較邏輯）在 ss 100°C 推一個 `nand2_2` 輸入時 slew 0.509 ns，略超過修復的上限 0.70 ×（1 − 30%）= 0.49 ns。
2. resizer 修 driver 的 slew 時換尺寸，但評估候選尺寸用的是第一個讀進來的 .lib（這個 flow 是 tt），不是發生違規的 ss corner。tt 下三個尺寸都「不違規」，它就挑面積最小的 `a2111oi_1`；這顆在 ss 下是 0.704 ns，比原本更糟（實驗 D：只改成先讀 ss 的 .lib，它就改挑 `a2111oi_4`）。
3. `a2111oi_1` 推不動一顆 `clkbuf_1` 的輸入電容（ss 下 0.50 ns），推算的電容上限 0.002 pF 不大於 buffer 的輸入電容，長線修復於是在同一點無限插 buffer。
4. PDK 的 `no_synth.cells` 有 `a2111oi_1`，但那份清單只擋合成（LibreLane `SYNTH_EXCLUDED_CELL_FILE`）；P&R 只排除 `drc_exclude.cells` 與 `EXTRA_EXCLUDED_CELLS`。`no_synth.cells` 也包含 clock buffer、hold 用的 delay cell、decap、diode，不能整份套到 P&R。

## 試過但不採用的做法

| 做法 | 結果 |
|---|---|
| `DESIGN_REPAIR_MAX_SLEW_PCT` 30 → 20 | 單步重跑 16 秒完成，但 resizer 用 tt 表換尺寸的行為還在；30 是為了 ss corner 繞線後的 slew 違規而調的（`pnr/soc_top/README.md` 設定表），改回去那些違規可能回來，影響面比較大 |
| 讓 resizer 先讀 ss 的 .lib | 實驗 D 證明可行，但 LibreLane 用 Tcl 陣列的雜湊順序讀各 corner，沒有設定可以控制；改 LibreLane 的 Tcl 會讓來源追溯 FAIL（LibreLane clone 不能有修改）。整體修復結果也會大幅改變（resize 711 對 406 顆） |
| 只讓 resizer 跳過那條 net（`set_dont_touch`） | 只是確認手段：違規還在，net 名稱也會隨合成改變 |

## 決策

1. `pnr/soc_top/config.json` 與 `config_hazard3.json` 的 `EXTRA_EXCLUDED_CELLS` 加上 `sky130_fd_sc_hd__a2111oi_1`（合成本來就不用它，所以只影響 resizer）。兩份設定一起改，`check_inputs.py` 的 `cpu_config` 仍然只允許差 3 個設計相關的 key。單步重跑（實驗 C）：22 秒、約 420 MB 完成，driver 保留 `a2111oi_2`，插一顆 buffer 就修好。
2. 新增 `pnr/check_weak_cells.py`，由 `check_inputs.py` 在 harden 前（`weak_cells`）與 flow 跑完後（`--resolved` 的 `weak_cells_run`）執行。它在 resizer 的每個 corner、兩個修復步驟各自的餘量下，用 .lib 查表確認 resizer 可用的每個 cell 推「resizer 最小 buffer 的輸入電容」時 slew 不超過上限。現行設定（ss 100°C 是 resizer 最慢的 corner，餘量 30%／40%）下，原本只有 `a2111oi_1` 超過（0.501 ns）。
3. negative test：P40（設定拿掉 `a2111oi_1`）、P41（placement 後的餘量改 50%，抓到 10 種 cell）、P42（`resolved.json` 拿掉 `a2111oi_1`），都必須在對應的列 FAIL。
4. `pnr/picorv32_core/config.json` 不改（使用者決定）：它的 golden 也有一顆 `a2111oi_1`，但那次 run 正常結束。

## 影響

- PicoRV32 版 SoC 的 golden 成品網表有一顆 resizer 換上的 `a2111oi_1`（`_11460_`，第 41 步），所以 PicoRV32 版的 harden 結果會改變，要重跑並逐項檢視後更新 `signoff/golden/soc_top/`（Phase 5 結案時兩個 regression 本來就要重跑）。
- 這只擋住現在已知會讓迴圈出不來的 cell。檢查是必要條件不是充分條件，而 resizer 用 tt 表判斷換尺寸的行為沒有改變；改 slew 餘量、加 resizer corner、換 cell library 時，`weak_cells` 會列出新的需要排除的 cell。

## 限制

- 上游 OpenROAD（2026-10-06 的 master）`repairDriverSlew`／`checkDriverArcSlew` 仍是同樣寫法，是否回報上游由使用者決定。
- 檢查用的負載、輸入 slew 與 buffer 選擇是依 OpenROAD `dcf36133` 的程式推得，換 OpenROAD 版本要重新確認（`check_weak_cells.py` 開頭的說明）。

## 出處

- `docs/notes/repair_design_loop.md`（實驗 A–D、原始碼行號、查表結果）
- skill `drv-timing-closure` 規則 10、11
