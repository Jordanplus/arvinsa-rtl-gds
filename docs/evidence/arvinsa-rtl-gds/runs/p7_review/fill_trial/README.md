# fill 試跑：wrapper 單獨補 Caravel 的 fill 後的密度（ADR-0019 決定 26）

2026-10-15，限時 2 小時（09:15 開始，10:46 完成）。對象：第二輪結案 regress 的 wrapper GDS（`p7close2_caravel/runs/user_project_wrapper/final/gds/user_project_wrapper.gds`，sha1 `06b0ddc4…`，與 precheck 受檢的相同）。工具：LibreLane nix-shell 的 Magic 8.3.623、PDK `8afc834`。

## 做法

照 Caravel 的 `generate_fill.py` 與 `check_density.py`（下載在 scratchpad 的 `cf_fill/cfcar/`，只讀、沒有執行；這裡的腳本是照它重寫的）：
- `fill_gen.tcl`：`cif ostyle wafflefill(tiled)`，700 µm 區塊（5 × 6 = 30 個），每塊 flatten 的範圍外擴 1.6 µm、`comment` 層標區塊邊界，寫成 `withfill/fill/fill_X_Y.gds`（共 1.2 GB）。花 70 分鐘、最多 2.6 GB 記憶體。
- `density.tcl`：`cif ostyle density`，每 70 µm 一格（42 × 51）的 `cif list cover`（各層的覆蓋比例）。wrapper 沒補 fill 的結果在 `nofill/density.log`（286 秒、2.6 GB）。
- `density_fill.tcl` + `run_fill_density.sh`：每個 fill 區塊**單獨**量（不讀 wrapper），結果在 `withfill/fdens/`。把 1.2 GB 的 fill 和 wrapper 一起讀進 Magic 要很多記憶體，當時 swap 已經 10 GB 以上，而且 Hazard3 的 regress 在跑，所以沒有這樣做。
- 逐格相加：wrapper 的覆蓋率 + fill 的覆蓋率 → `withfill/density.log`。
- `aggregate.py`：700 µm 視窗，li1 與金屬步進 350 µm、FOM 70 µm，下限 li1、met1–4 35%，met5 45%，FOM 33%（`check_density.py` 的值）。視窗和 `check_density.py` 一樣只走固定步進，所以 die 右緣 120 µm、上緣 20 µm 不在任何視窗裡。

### 相加的驗證

把 wrapper 和 `fill_0_0.gds` 一起讀進 Magic 實量（`xcheck/`），與相加的結果比較：
- 那 100 格中，相加的值一律等於或高於實量，單格最多高 2.2 個百分點；在 700 µm 視窗 (0, 0) 上最多高 0.33 個百分點（met3）。原因應該是部分 fill 和 wrapper 的圖形在 density 樣式下重疊（推測，沒查）。
- 其他格與 wrapper 單獨量的結果完全相同。

所以這份結果對上限的判斷偏保守。對下限，只有離下限不到 0.35 個百分點的視窗可能判錯，這次沒有這種視窗。

## 結果

| 層 | 下限 | 沒補 fill：整塊／最低視窗／低於下限的視窗 | 補 fill 後：整塊／最低視窗／低於下限的視窗 | 補 fill 後最高視窗（上限 60%，met5 76%） |
|---|---|---|---|---|
| FOM | 33% | 41.1%／19.4%／90 of 1386 | 42.3%／31.5%（210, 140）／**15 of 1386** | 44.4% |
| li1 | 35% | 39.9%／25.4%／4 of 63 | 42.1%／41.4%／0 | 42.1% |
| met1 | 35% | 18.1%／17.4%／63 of 63 | 37.2%／36.0%／0 | 44.8% |
| met2 | 35% | 1.6%／0.4%／63 of 63 | 52.5%／34.8%（0, 0）／**1 of 63**（實量 34.55%） | 52.6% |
| met3 | 35% | 0.8%／0.3%／63 of 63 | 49.3%／37.9%／0 | 49.2% |
| met4 | 35% | 25.1%／10.7%／63 of 63 | 59.7%／50.0%／0 | 59.7% |
| met5 | 45% | 26.1%／21.9%／63 of 63 | 60.9%／58.1%／0 | 60.4% |

「整塊」是 die 內的平均；最右一欄和上限的比較只看視窗。

- 沒補 fill 的 li1、met1–3 與 precheck 報的相同（39.9%、18.1%、1.6%、0.8%）。met4、met5 是 25.1%、26.1%，precheck 報的是 26.7%、27.3%。precheck 的 `met_min_ca_density` 分母是 die 外框（`235/4`），分子卻包含 die 外的 wrapper 電源環；這份只算 die 內。差異的原因是推測，沒有另外驗證。
- 補 fill 後：
  - met1–5、li1 的視窗除了 met2 (0, 0) 以外都在範圍內。met2 (0, 0) 低 0.45 個百分點，位置是左下角 SoC 最密的地方。
  - FOM 有 15 個 70 µm 步進的視窗低於 33%，最低 31.5%，都在 x 140–1120、y 0–910 µm，也就是 SRAM（351, 413 起，694 × 428 µm）和它下方的 SoC 邏輯一帶。
  - met4 最高的視窗 59.7%，貼近上限 60%。
- 這次判斷不了的：
  - die 右緣與上緣的視窗：正式檢查用晶片座標，會含到 Caravel 外殼的區域。
  - ChipFoundry 實際用的 fill 參數與版本。
  - 整顆晶片的平均。

## 結論

wrapper 留下的空間，大部分夠讓 Caravel 的 fill 把 li1 與金屬補到下限以上。補不起來的集中在左下角 SoC 與 SRAM 一帶：
- FOM：15 個視窗，最低 31.5%；
- met2：1 個視窗，34.5%。

這是 tapeout 時才會跑的檢查（precheck 不查），ChipFoundry 實際怎麼判，要等書面確認（ADR-0019 決定 26 的下線前事項）。

如果要改善，方向是降低左下角的局部密度，例如把 SoC 的 placement 再分散、讓 SRAM 周圍留出可以補 fill 的空間。這次沒有試。

## 工具的意外行為

LibreLane nix-shell 裡的 Magic Tcl 沒有 `clock` 指令（`invalid command name "clock"`），第一次試跑因此 32 秒就中止、沒有輸出。改用 `exec date`。
