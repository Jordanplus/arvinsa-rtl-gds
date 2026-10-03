# soc_top：整合預建 SRAM macro 的 harden（Phase 3）

`make harden-soc`（`run.sh`）用釘版的 LibreLane Classic flow harden `soc_top`（PicoRV32 + 2 KB SRAM macro + Boot ROM + 周邊），目標 40 ns，再用下列 checker 判定。本機約 20–30 分鐘（正式 run 1、2 分別 28 與 18 分鐘；其中 Magic 全 GDS DRC 約 3–4.5 分鐘）。

## 檢查項

| 檢查 | 程式 | PASS 條件 |
|---|---|---|
| 輸入一致 | `check_inputs.py` | `config.json` 的 RTL 檔案清單 = `rtl/rtl.f`；`padded.lib`（ADR-0007）與 SRAM LEF（ADR-0008）是由產生腳本從釘版 PDK 產生的最新版本；`MACROS` 用這兩個檔。flow 跑完後再比對 run 實際用的（`resolved.json`） |
| LibreLane 內建 checker | flow 本身 | lint、合成、routing DRC、KLayout DRC、LVS、XOR、9 個 corner 的 setup／hold／max slew／max cap；任何一項 FAIL 時 flow 就中止。Magic DRC 例外，見下一列與「設定與理由」 |
| soc 專用 | `check_soc.py` | SRAM 只有一顆、名稱 `sram0`；最終 DEF 中 `sram0` 是 FIXED，座標與方向等於 `config.json`；port 1 有 tie-off（`csb1` 接 tie-high，`clk1`、`addr1[8:0]` 接 tie-low）；沒有任何斷線 pin；Magic DRC（完整 GDS）在 SRAM 外框之外是 0，框內只出現 SRAM 單獨檢查時也有的規則種類（`signoff/waivers/soc_top/sram_magic_drc_baseline.json`） |
| 來源追溯 | `signoff/scripts/provenance.py`（flow 開始前與結束後各一次） | 工作目錄已全部 commit（含未追蹤檔）、submodule 在記錄的 commit、LibreLane 與 PDK 是 `env/versions.mk` 釘的版本；結束時 HEAD 不變，`resolved.json` 實際用的版本也對（`project-plan.md` §7.2）。不乾淨時 flow 照跑、整體判 FAIL |
| signoff metrics | `signoff/scripts/check_signoff.py` + `signoff/limits/soc_top.toml` | 見該檔：各種違規數 = 0、9 個 corner 的 setup／hold slack ≥ 0 且 < 40 ns、nom_tt setup ≥ 4 ns、IR drop ≤ 90 mV（5% VDD）；所有 metrics 與 golden（`signoff/golden/soc_top/`）相同，只有 detailed routing 造成微小差異的族群有明確的小誤差 |

全部 PASS 時 `runs/soc_top_signoff/result.txt` 寫 `harden-soc: PASS`。後續步驟使用 harden 的結果前，都先確認這個檔案：`make eqy-soc`（formal equivalence，`signoff/eqy/README.md`）、`make gl-soc`（gate-level lockstep 模擬，`dv/gl_soc/README.md`）、`make neg-pnr`（PnR negative test P01–P13，`neg_pnr.py`）。

## 名詞

- **halo**：macro 周圍不放 standard cell 的保留區，這裡 10 µm（LibreLane 預設 `FP_MACRO_HORIZONTAL_HALO`／`VERTICAL_HALO`）。
- **padded.lib**：SRAM 的保守時序模型（ADR-0007）。PDK 原本的 .lib 是解析模型、數字過度樂觀。
- **antenna LEF**：補上 `ANTENNAGATEAREA` 的 SRAM LEF（ADR-0008）。PDK 原本的 LEF 沒有 antenna 資料，antenna 檢查看不到接到 SRAM 輸入的線。
- **abstract DRC／完整 GDS DRC**：前者只用各 cell 的 LEF 外形檢查，後者讀完整 GDS 連電晶體層一起檢查。

## 設定與理由

| 設定 | 值 | 為什麼 |
|---|---|---|
| `FP_SIZING`、`DIE_AREA` | absolute、1000 × 800 µm | ADR-0006 |
| `MACROS` | GDS 用 PDK 原檔；LEF 用 antenna LEF；`lib: {"*": padded.lib}`；`sram0` 在 (301.76, 364.48)、N | 9 個 corner 都要有 SRAM 時序模型，少一個 corner 會被當 black box 且不報錯（`project-plan.md` §6.2）。座標見 ADR-0006 的 Phase 3 補充：讓 halo 蓋過 core 右、上邊界，避免留下 PDN 接不到的窄 row |
| `VDD_NETS`／`GND_NETS`、`PDN_MACRO_CONNECTIONS` | `vccd1`／`vssd1`；`sram0 vccd1 vssd1 vccd1 vssd1` | 與 SRAM 電源 pin 及 RTL 的 `USE_POWER_PINS` port 同名 |
| `IO_PIN_ORDER_CFG` | `pin_order.cfg`：pin 只在左、下兩邊；`clk` 在下邊中段 | 遠離 SRAM（§5.4）。`clk` 原本在左邊最下方，到第一級 clock buffer 有 660 µm 的線，ss corner 的 slew 0.92 ns 超標 |
| `SETUP/HOLD/MAX_SLEW/MAX_CAP_VIOLATION_CORNERS` | `["*"]` | 9 個 corner 都判 FAIL（LibreLane 對 sky130 預設只判 tt 的 setup） |
| `STA_EXTRA_CORNER_TCL_FILE` | `sta_extra_corner.tcl` | ss／ff corner 對 `sram0` 加 derate（ADR-0007）；P04 證明它有作用 |
| `ERROR_ON_MAGIC_DRC` | false | Magic 讀完整 GDS 檢查時，SRAM 自己的 GDS 有約 466 萬個標準規則違規（bitcell 用 SRAM 專用規則），全部在 SRAM 外框內；由 `check_soc.py` 的 magic_drc 列取代 LibreLane 的判定。abstract 模式（`MAGIC_DRC_USE_GDS=false`，規劃 §6.3 原案）試過：每一條 standard cell row 都報 `nwell.4`（共 416 個），因為 abstract cell 沒有 tap；完整 GDS 模式沒有 |
| `PRIMARY_GDSII_STREAMOUT_TOOL` | klayout | Magic 寫出的 GDS 有 13 個 top cell：它用改名的 `T2_*` 子 cell 放 SRAM，又把 160 個原名子 cell 沒有引用地寫出來，KLayout.Render 因此失敗。KLayout 的 GDS 只有 `soc_top` 一個 top cell，161 個 SRAM cell 都接得到；兩份 GDS 的 XOR = 0 |
| `DESIGN_REPAIR_MAX_WIRE_LENGTH` | 200 µm | placement 後的修復把超過 200 µm 的線切段加 buffer。沒有它時：ss corner 50 個 max slew 違規（300–700 µm 的線）、antenna 修復在單一長線上插 10–11 顆 diode 造成 7 個 max fanout 違規、SRAM 輸入線最長 355 µm |
| （不設）`GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH` | — | global routing 後的修復也設 200 µm 時，OpenROAD 在 clk pin 所在的 GCell 報 `GRT-0229 Vertical edge usage exceeds the maximum allowed ... usage=65534` 而中止（數值像是無號整數下溢，推測是增量繞線的 bug） |
| `DESIGN_REPAIR_MAX_SLEW_PCT`、`GRT_DESIGN_REPAIR_MAX_SLEW_PCT` | 30、40 | 兩次修復預留的 slew 餘裕（預設 20 與 10，Phase 2 用 20 與 30）。GRT 後用 30 時，detailed routing 之後還有 5 條線在 ss corner 超標（0.755–0.932 ns），因為繞線後萃取的負載比 global routing 的估計大。用 50 時這次修復單執行緒跑了 26 分鐘以上還沒結束（soc_explore6，停掉）；40 約 1 分鐘 |
| `PL_TARGET_DENSITY_PCT` | 55 | global placement 的目標密度。LibreLane 自動算出 68%，但 L 形 logic 區整體只用約一半，cell 擠在 SRAM 左下角的轉角，那裡的線大幅繞路（正式 run 1：端點相距 117 µm、繞線 353 µm，ss slew 1.42 ns）。55%（soc_explore10）時 9 個 corner 的 slew／cap／fanout 都是 0 |
| `PNR_SDC_FILE`、`SIGNOFF_SDC_FILE` | `pnr.sdc`（max fanout 8）、`signoff.sdc`（= LibreLane `base.sdc`） | antenna repair 在 resizer 修完 fanout 之後才加 diode，diode 也算負載，所以 PnR 先修到 8（ADR-0009）。signoff 用原本的 0.75 ns 與 fanout 10；一定要明確設 `SIGNOFF_SDC_FILE`，沒設時 signoff STA 會改讀 `PNR_SDC_FILE`（實測：sta.log 讀的是 pnr.sdc）。曾經把 signoff 放寬到 1.0 ns，找到密度這個根因後撤回 |
| `EXTRA_EXCLUDED_CELLS`、`CTS_SINK_CLUSTERING_SIZE`、`LAYERS_RC`、`RUN_POST_GRT_DESIGN_REPAIR`、`CTS_DISTANCE_BETWEEN_BUFFERS` | 與 Phase 2 相同 | 同一個 standard cell library 的問題，理由見 `pnr/picorv32_core/README.md` |
| （不用）`RUN_HEURISTIC_DIODE_INSERTION` | — | 規劃 §6.4 的選項之一。它對整個設計所有超過 90 µm 的線加 diode（10231 顆），之後 global routing 反覆跑壅塞迭代超過 10 分鐘，停掉。改用 antenna LEF（ADR-0008） |

## 試跑紀錄（2026-10-03）

| # | 相對前一次的變更 | 結果 |
|---|---|---|
| explore1-a | 初版設定（SRAM 離 die 右、上各約 25 µm；heuristic diode） | PDN 失敗：`PDN-0179 Unable to repair all channels`（SRAM 上方只剩約 6 µm 的 row） |
| explore1-b | SRAM 改到 (301.76, 364.48) | heuristic diode 插了 10231 顆，global routing 不收斂，手動停掉 |
| explore2 | 拿掉 heuristic diode | 跑到 KLayout.Render 失敗（Magic GDS 多 top cell）；改 `PRIMARY_GDSII_STREAMOUT_TOOL=klayout` 從 Magic.StreamOut 接續跑完：setup／hold 9 corner 全 ≥ 0、LVS／KLayout DRC／XOR／antenna 全 0；剩 abstract Magic DRC 416（nwell.4）、max slew 50、max fanout 7 |
| explore3 | 完整 GDS Magic DRC、placement 與 GRT 後都設長線 200 µm、clk 移到下邊 | GRT-0229 中止（見上表） |
| explore4 | 拿掉 GRT 後的長線限制 | 只剩 ss corner 5 條線的 max slew（20 個 pin）；fanout 0、diode 224 → 61 顆 |
| explore5 | slew 餘裕 30／50 | 未跑完即停掉，改與 antenna LEF 一起做 |
| explore6 | + antenna LEF（ADR-0008） | GRT 後的修復以 50% 餘裕跑 26 分鐘以上不結束，停掉 |
| explore7 | GRT 後的餘裕改 40 | ss corner 16 個 slew（0.775–0.970 ns）、1 個 fanout（10 負載 + 1 diode）；其他全 PASS |
| explore8 | + placement 後長線 120 µm | GRT 後修復跑 13 分鐘以上不結束，停掉 |
| explore9 | + GRT 後長線 400 µm | 與 explore7 完全相同 |
| harden-soc 1 | + `pnr.sdc` fanout 8、`signoff.sdc` 1.0 ns（ADR-0009） | 1.0 ns 下仍 FAIL：ss slew 最慢 1.42 ns，最差兩條線在 L 形轉角大幅繞路 |
| explore10 | + `PL_TARGET_DENSITY_PCT` 55 | slew／cap／fanout 全 0（0.75 ns 下也是 0），其他全 PASS |
| explore11 | + `PL_TARGET_DENSITY_PCT` 50 | 全 0；fanout 在 PnR 的 8 下有 1 個，signoff 的 10 下為 0 |
| harden-soc 2 | 採用 55，signoff 恢復 0.75 ns | flow 全 PASS；signoff 只差 golden 尚未建立與 unannotated 的暫定值 135（查證組成後改為 134），建立 golden 後重判 PASS。golden 來源（`signoff/golden/soc_top/README.md`）。這次 run 早於來源追溯，Phase 3 的正式結果以 `make phase3` 為準 |

## 已知限制

1. SRAM 的時序數字是工程假設（ADR-0007），不是特性化結果。
2. Magic 的 SRAM 內部 DRC 數量無法和 SRAM 單獨檢查的數量直接比較：同一個錯誤在 soc_top 裡被切成不同的框（單獨 5,579,161 個、soc_top 內 4,665,810 個，30 種規則相同）。所以只比規則種類，數量由 golden 鎖定。
3. LVS 中 SRAM 是 black box（`MAGIC_EXT_USE_GDS=false`），只驗 pin 的連接。
