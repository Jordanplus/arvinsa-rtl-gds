# latch-up：diffusion 到 tap 的距離（6 µm／15 µm）與 81/14 標記（2026-10-15）

起因：2026-10-15 的問題總檢討（`docs/notes/problem_review/verify_and_merge.md` 2.2，A2）發現：
- 交付的 GDS（KLayout 寫出）沒有 `areaid.lowTapDensity`（81/14）；
- 整條 flow 與 precheck 都沒有檢查預設的 6 µm tap 規則。

使用者 2026-10-15 選「先量再決定 (建議)」（ADR-0021 決定 2）。

## 規則

- **SkyWater 的定義**：skywater-pdk 文件 layers 頁 Table C3 原文「areaid.ld{81:14} | areaid low tap density | 6um tap to diff rule will not be checked in this region」。GDS 層表原文「Low tap density (15um between taps) area. Must be at least 50um from padframe」。
- **Magic 的實作**：sky130A tech 檔只查 15 µm（LU.2／LU.3）。寫 GDS 時，自動在 top cell 外框內縮 250 µm 處產生 81/14：
  - `~/.ciel/sky130A/libs.tech/magic/sky130A.tech` 的 `layer LOWTAPDENSITY`／`bbox top`／`shrink 250000`／`calma 81 14`；
  - 註解寫「Clear 200um for pads + 50um for required high tap density in critical area」。
- **標準元件的 tap 間距**：PDK 給 LibreLane 的預設是 `FP_TAPCELL_DIST 13`（`~/.ciel/sky130A/libs.tech/openlane/config.tcl` 第 79 行），本 repo 沒有覆寫。所以標準元件區本來就是照 15 µm 規則放 tap，要靠 81/14 才合規。

## 量測

腳本：`tap_distance.drc`（本目錄，KLayout DRC deep mode）。
- **分類**：
  - p+ tap ＝ `tap & psdm − nwell`；n+ tap ＝ `tap & nsdm & nwell`；
  - NMOS diffusion ＝ `diff & nsdm − nwell`；PMOS diffusion ＝ `diff & psdm & nwell`。
- **計算**：每種 diffusion 扣掉同型 tap 外擴 d µm（`sized`，八角形近似），剩下的就是離 tap 超過 d 的部分。
- **輸出**：面積，SRAM 框內外分開。

指令：

```bash
cd .tools/librelane && nix-shell --run "klayout -b -rd input=<gds> -rd report=<lyrdb> \
    -rd sram=x1,y1,x2,y2 -r docs/notes/latchup/tap_distance.drc"
```

GDS 是 Phase 7 第二輪結案 run 的交付檔：
- `soc_top_hazard3`：sha1 `9d3f249e…`，SRAM 框 (290.72, 353.6)–(984.99, 782.015)，28 秒、0.8 GB；
- wrapper：sha1 `06b0ddc4…`，SRAM 框 (350.98, 413.44)–(1045.25, 841.855)，83 秒、1.7 GB。

離同型 tap 超過 d µm 的 diffusion 面積（µm²）：

| 設計 | d | NMOS（SRAM 內） | PMOS（SRAM 內） | NMOS、PMOS diffusion 總面積 |
|---|---|---|---|---|
| soc_top_hazard3 | 6 | 4,816（79） | 7,301（53） | 88,379、112,318 |
| | 7.5 | 812（47） | 1,246（34） | |
| | 10 | 379（16） | 594（14） | |
| | 15 | **0** | **0** | |
| user_project_wrapper | 6 | 113,280（79） | 178,820（53） | 1,630,559、2,551,533 |
| | 7.5 | 5,057（47） | 7,956（34） | |
| | 10 | 2,288（16） | 3,606（14） | |
| | 15 | **0** | **0** | |

兩份 GDS 都沒有 81/14（`INFO ld_area 0.0`）。

- **自我檢查**：15 µm 為 0，和 Magic 的 LU.2／LU.3（15 µm）在這兩份 GDS 0 個違規一致。這支腳本沒有植入錯誤的 negative test，所以「6 µm 的面積算得對」只靠這個一致性支持。
- **讀法**：
  - 照 15 µm 規則（有 81/14 時）是乾淨的；照預設的 6 µm 規則，SRAM 外約 7% 的 diffusion 面積違規。
  - 違規幾乎全在標準元件與 decap 區。
  - SRAM 內的少量違規（NMOS 79、PMOS 53 µm²）兩份設計相同，屬於 macro 本身。

## 推論（沒有向 ChipFoundry 或 SkyWater 確認）

- 開源 sky130 flow 的標準元件依賴 81/14：
  - 用 Magic 寫 GDS 的設計會自動帶上這個標記；
  - 本 repo 從 Phase 3 起改用 KLayout 寫最終 GDS（Magic 寫出 13 個 top cell），標記因此不見了。
- 即使改回 Magic，標記也只蓋 top cell 內縮 250 µm 的範圍。wrapper 外圈 250 µm 內也有 decap 與 tap，照 6 µm 仍會違規。這個內縮是為整顆晶片的 pad 設計的，不是為 wrapper。
- 整合方組 Caravel 全晶片時，會不會在 user area 加 81/14、SkyWater 的 PDQC 怎麼判，都查不到原文。官方文件說這一層「Should be used sparingly」「will be reviewed during PDQC」。
