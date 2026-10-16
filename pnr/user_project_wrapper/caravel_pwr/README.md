# Caravel 的 vccd1／vssd1 供電網路（wrapper 外面那一段）

`ir_caravel.py` 用這些資料，把 Caravel 從 pad 到 wrapper core ring 的電源形狀加進 IR 用的 DEF 複本，量含 Caravel 網路的靜態 IR（ADR-0019 決定 18、19）。

## 來源

ChipFoundry 現用的 Caravel：`chipfoundry/caravel_user_project` `b510613c` 的 `Makefile` 第 53 行 `MPW_TAG ?= CC2509`，tag `CC2509` = `chipfoundry/caravel` `a0b50ad14f144510dcd529accaf3af54fdec1608`。下列檔案的 git blob hash 已用 GitHub API 核對（2026-10-13），與 `efabless/caravel` `27cbe49c` 相同：

| 檔案 | blob | 用途 |
|---|---|---|
| `def/caravel_core.def.gz` | `4d52c37f825986f2b0383759ffb66b33ede12a46` | vccd1／vssd1 的 caravel_core ring 與 strap（`shapes.txt`）、via 定義（`vias.def`）；wrapper `mprj` 在 caravel_core 的 (121.74, 1037.0) µm |
| `lef/manual_power_connections.lef` | `bfa82a46b0626c99029b6470a879518d6ab90e36` | met3 電源連接線（`bridges.txt`）、pad 的 met5 strap（`pads.txt`） |
| `def/chip_io.def` | `9af4f4037af382bb01eb3ff256e4a251a585ce6a` | 第 17057–17058 行 `user1_vccd_lvclamp_pad` (3390.035, 4538)、第 16653–16654 行 `user1_vssd_lvclamp_pad` (3390.035, 2299)：vccd1、vssd1 各只有這一顆 pad，都在右側 |

`shapes.txt`、`bridges.txt`、`vias.def` 由 `extract.py` 產生：`python3 extract.py <caravel_core.def.gz> <manual_power_connections.lef> .`。`pads.txt` 是手寫的（LEF 的 met5 區段，例如 vccd1 pad 的 strap 在 y 4327.795–4351.745、4378.05–4402.0 µm）。

## 模型

- 座標從 caravel_core 平移 (−121.74, −1037.0) µm 到 wrapper 座標。
- 加進去的：caravel_core 中 vccd1／vssd1 在 wrapper 範圍外的 met4／met5 形狀與 met4–met5 via；兩端落在 caravel_core ring 與 wrapper ring 上的 met3 電源連接線（每個 net 左 54、右 53 條），兩端各一個 2 × 11 cut 的 met3–met4 via（LEF 的 via3 區域 4.72 × 1.12 µm）；pad 的 met5 strap，在 ring 上加 met4–met5 via。
- 沒加的：caravel_core 中 met3–met4 的 via 堆疊（接到 gpio 控制 cell，不在電流路徑上）；pad 本身與 padframe（pad 端當成理想電壓源）。
- 驗證：同一份 ODB、電壓源放回 wrapper ring，IR 與 run 自己的 IR 步驟相同到 0.1% 以內（`ir_caravel.py` 每次都做這個對照；`p7_harden2` 差 0.01–0.02%，是 DEF 轉 ODB 的來回造成的）。
- 已知限制：每個形狀屬於哪個 net 是依座標判斷（LEF 只有 OBS、沒有 net 名稱）；pad 到 strap 之間（clamp 與 padframe）的電阻沒有算。
