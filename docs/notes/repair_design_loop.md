# `repair_design` 無窮迴圈、記憶體暴增的重現紀錄（2026-10-06）

Phase 5 第一次 `make harden-soc CPU=hazard3`（commit `4461661`，worktree `../arvinsa-rtl-gds-p5h3`）在 `OpenROAD.RepairDesignPostGPL`（global placement 後的 DRV 修復）失控。這份紀錄保存單步重跑的證據；原始輸出在 session 暫存目錄，之後會消失。結論經一個獨立 agent 對照原始碼、log 與 .lib 反向驗證過，下面已依它的意見修正。

## 現象

- 這一步跑了約 108 分鐘（`32-openroad-repairdesignpostgpl/openroad-repairdesignpostgpl.process_stats.json`：runtime 1:47:50、平均 CPU 33%、取樣到的峰值 RSS 6 GiB）。2026-10-05 22:12 手動停止，console 只報 `OpenROAD.RepairDesignPostGPL failed with an unexpected error`（`runs/soc_top_hazard3_signoff/console.log`）。
- 停止前不到 1 分鐘（22:11:48）的 `vmmap --summary`：physical footprint（程序實際占用的記憶體，含被換到 swap 的部分）92.9 GB，幾乎全是 `MALLOC_SMALL`（大量小物件）；機器 24 GB，swap 28.0／28.7 GB。同一時間 `ps -o rss` 只顯示 418 MB：RSS 只算還留在實體記憶體的部分。這幾個數字只在前一個 session 的輸出與它的筆記（`~/claude_prjs/arvinsa-open-eda/notes/phase5_lessons.md` 第 6 條）裡，run 目錄沒有存。
- 停止前進度：7000／12341 個 driver、插了 1595 顆 buffer。CPU 使用率低：大部分時間在等 swap，不是在計算。
- 對照：PicoRV32 版同一步 43 秒、峰值 590 MB。

## 重現方法

LibreLane 可以把單一 step 匯出成不經 LibreLane 的 shell script（`python3 -m librelane.steps eject`），之後可以直接改 Tcl：

```
mkdir <exp> && cp <run>/32-openroad-repairdesignpostgpl/{config.json,state_in.json} <exp>/
cd .tools/librelane && nix-shell --run "cd <exp> && python3 -m librelane.steps eject -c config.json -i state_in.json -o run.sh"
# <exp>/run.sh 設好環境變數後執行 openroad；<exp>/scripts/ 是 LibreLane Tcl 的複本，輸入讀原 run 的 ODB（唯讀），輸出寫在 <exp>
```

在複本 `scripts/openroad/repair_design.tcl` 的 `repair_design` 前加：

```
set_debug_level RSZ repair_net 1   ;# 每個 driver 開始修時印 "repair net <driver pin>"；3 會印每一顆插入的 buffer
set_debug_level RSZ memory 1       ;# 每段進度印 RSS
```

執行時用 `script -q /dev/null ./run.sh` 讓輸出不被緩衝，每行加時間戳；另一個迴圈每 5 秒讀 `top -l 1 -pid <pid> -stats mem`，超過上限或超時就停掉 openroad，超過 2 GB 時先 `sample` 一次。

## 結果（輸入：p5h3 run 第 28 步的 ODB）

| 實驗 | 改動 | 結果 |
|---|---|---|
| 基準 | 只加除錯輸出，上限 4 GB | 修復開始後約 9 秒修完 7000 個 driver，接著停在 `repair net _19257_/Y`；記憶體每秒約多 80 MB，程序 66 秒時 4.4 GB 被停掉 |
| 除錯等級 3 | 同上，`repair_net` 3，上限 2 GB | 迴圈開始後 27 秒內，同一行 `wire wire sky130_fd_sc_hd__clkbuf_1 (108.9 237.1)` 出現 331,756 次；程序 37 秒、2.3 GB 時被停掉（監看腳本的輸出，記憶體 log 已被後續實驗覆蓋） |
| A | `set_dont_touch [get_nets _05248_]`（只讓 resizer 跳過這條 net） | `repair_design` 21 秒完成，記憶體最後一筆約 410 MB；`Inserted 4606 buffers in 1009 nets`、`Resized 406 instances` |
| B | `DESIGN_REPAIR_MAX_SLEW_PCT` 30 → 20（LibreLane 預設） | 16 秒完成，約 405 MB；`Inserted 4246 buffers in 943 nets`、`Resized 313 instances` |
| C | `set_dont_use [get_lib_cells */sky130_fd_sc_hd__a2111oi_1]`（只禁止 resizer 用 `a2111oi_1`） | 22 秒完成，約 420 MB；`Inserted 4607 buffers in 1010 nets`。`_19257_` 保留 `a2111oi_2`（driver 等效電阻 26.1 kΩ），電容上限約 0.005 pF，切段 0.7 µm 插一顆 `clkbuf_1` 後 slew 0.105 ns，結束 |

| D | 實驗目錄的 `scripts/openroad/common/io.tcl` 改成先讀 `max_ss_100C_1v60` 的 .lib（`define_corners` 不變），其他不動 | 正常完成；`_19257_` 報出 ss 的 slew 違規後換一次尺寸就修好（之後沒有 load slew 違規、沒有進長線修復），候選中 ss 下唯一不違規的是 `_4`。整體：`Resized 711 instances`、`Inserted 6464 buffers in 840 nets` |

A、B 只是確認手段，不是修正。C 是決定性的實驗：唯一的差別是 resizer 不能換成 `a2111oi_1`。D 證明 resizer 用「第一個讀進來的 .lib」評估候選尺寸：同一份輸入只改讀取順序，挑的尺寸就從 `_1` 變成 `_4`。

### 卡住的那條 net

- driver `_19257_`：`sky130_fd_sc_hd__a2111oi_2`，UART 的 `send_divcnt` 比較邏輯；輸出 net `_05248_` 只有一個負載 `_19258_/B`（`nand2_2`），兩顆 cell 相距約 2 µm，線長 2.6 µm。
- STA（同一份 ODB，`estimate_parasitics -placement`，nom／max_ss_100C_1v60）：輸入腳 `D1` 的 slew 0.182 ns，輸出 `Y` 推 0.005 pF 時上升 slew **0.509 ns**。上限 0.70 ns 扣 30% 餘量是 0.490 ns，所以 driver 本身就違規。把 `_19257_` 手動換成 `_4`／`_1` 後同一條路徑是 0.405／0.704 ns。
- 除錯等級 3 的開頭（之後無限重複最後三行）：

```
drvr slew violation pin=_19257_/Y slew=0.509 max_slew=0.490
load slew violation pin=_19257_/Y load_slew=0.704 max_slew=0.490
wire (108.66, 234.74) cap 0.005 slack 0.000 buffers 0 load sl 0.700
 load _19258_/B (108.87, 237.13) cap 0.005 slack 0.000 load sl 0.700
wl=2.6 l=2.6
load_slew=0.370 r_drvr=47.467 max_load_slew=0.700 r_wire=1.72 ref_cap=4.617e-15 layer=-1 wire_res=664596
max cap violation 0.005 > 0.002
split length=0.0
wire wire sky130_fd_sc_hd__clkbuf_1 (108.9 237.1)
l=2.6 post buffer slew=0.190
max cap violation 0.003 > 0.002
split length=0.0
wire wire sky130_fd_sc_hd__clkbuf_1 (108.9 237.1)
...
```

## 機制（OpenROAD `dcf36133`，`src/rsz/src/RepairDesign.cc`）

1. driver 本身 slew 違規時，`repairDriverSlew`（909 行起）評估同功能的各尺寸：只要有尺寸不違規，就挑其中面積最小的；全部違規才挑違規最小的（959–961 行的排序）。這次它把 `a2111oi_2` 換成**更弱的 `a2111oi_1`**（已驗證）：
   - 兩行除錯輸出之間只有 `repairDriverSlew`（1100 行）會換 cell；換後 `load_slew=0.704` 與手動換成 `_1` 的 STA 結果相同。
   - `r_drvr` 47.467 kΩ（基準）與 26.115 kΩ（實驗 C）分別等於 tt .lib 的 `_1` 與 `_2` 的等效電阻。
   - 禁止 `a2111oi_1` 後就保留 `_2`（實驗 C）。
   - `a2111oi_1` 在 PDK 的 `no_synth.cells`（只禁止合成）；PnR 的排除清單是 `drc_exclude.cells` 加 `EXTRA_EXCLUDED_CELLS`（LibreLane `steps/openroad.py` 333–335 行、`steps/pyosys.py` 343–347 行），沒有它，所以 resizer 可以用。
2. 為什麼挑 `_1`（已驗證，實驗 D）：違規是在 ss 100°C 抓到的（上限、負載、輸入 slew 都是 ss 的），但候選尺寸用候選 cell 自己的 `arc->model()` 查表（`checkDriverArcSlew`，881 行），而候選只來自第一個讀進來的 .lib（`Resizer.cc` 1052 行 `isLinkCell`）。傳進去的 ss PVT 只會套用 .lib 的縮放係數，sky130 的 .lib 沒有，等於沒作用。LibreLane 依 Tcl 陣列的雜湊順序讀各 corner 的 .lib（`scripts/openroad/common/io.tcl` 339–347 行），這個 run 第一個是 `max_tt_025C_1v80`。tt 表裡 `a2111oi_1/_2/_4` 推 0.005 pF 是 0.404／0.306／0.254 ns，都不超過 0.49 ns，所以挑面積最小的 `_1`；ss 100°C 下它是 0.70 ns。改成先讀 ss 的 .lib（實驗 D），它就改挑 ss 下唯一不違規的 `_4`。也就是說，**sizing 在判斷換尺寸的影響時，沒有用發生違規的那個 corner 的資料**。OpenROAD 上游 master（2026-10-06 抓取）這兩個函式仍是同樣寫法。
3. 換完仍違規，就用「driver slew 剛好等於上限時能推多少電容」（`findSlewLoadCap`）當這條 net 的電容上限（1107–1115 行）。用 `a2111oi_1` 算出 0.002 pF。
4. 長線修復的迴圈（1490 行起）在「負載電容 > 上限」時切段插 buffer，切段長度是 `max((上限 − 下游電容) / 單位長度電容, 0)`（1527–1528 行），這裡是 0：buffer 放在負載那一端。
5. 插完之後，下游電容變成這顆 buffer（`clkbuf_1`，ss 約 0.0021 pF）的輸入電容，仍然不小於 0.002 pF，所以下一次切段長度還是 0；迴圈沒有「插了沒改善就停」的保護，於是在同一位置一直插下去，每插一顆都為新的 net 估一份 RC 網路，記憶體無上限地漲。

結論（已驗證）：這次是 resizer 用 tt 的表評估、在 ss 下把 driver 換成更弱的尺寸，使推算的電容上限不大於插入的 buffer 的輸入電容。拿掉這個條件（禁止那個弱尺寸、跳過這條 net、或放寬餘量），同一份輸入就正常完成。

## 哪些 cell 有這個風險

### 迴圈出不來的條件

由 1527–1528 行推得（讀程式的推論，與兩次觀察一致）：**電容上限 ≤ 插入的 buffer 的輸入電容**時，切段長度永遠是 0。插入的 buffer 是 resizer 最小驅動力的 buffer，這裡是 `clkbuf_1`（ss_100C 輸入電容約 0.0021 pF；`buf_2` 0.0017、`dlygate4sd3_1` 0.0016 pF 更小，但不是它選的）。

- 基準：上限 0.002 ≤ 0.0021，出不來。實驗 C：上限約 0.005 > 0.0021，第一顆切 0.7 µm，結束。
- 換算成 cell 的條件：在 resizer 的某個 corner，cell 推 0.0021 pF 的輸出 slew 已超過扣掉餘量的上限。
- 這是必要條件，不是充分條件：PicoRV32 版的 `_11460_` 合成時是 `a2111oi_2`，在第 41 步（`RepairDesignPostGRT`，餘量 40%）被換成 `a2111oi_1`，run 卻正常結束（golden 成品網表裡就是這顆）。為什麼沒進迴圈沒有查。

resizer 可用的 cell（只扣 `drc_exclude.cells` 與 `EXTRA_EXCLUDED_CELLS`）推 0.0021 pF 時的輸出 slew（輸入 slew 0.182／0.49 ns 取大者，各 timing arc 的上升與下降取最大值）：

| resizer 最慢的 corner | 餘量 30%（0.49 ns） | 餘量 40%（0.42 ns） | 餘量 50%（0.35 ns） |
|---|---|---|---|
| ss_100C_1v60（現在的 9 個 corner） | `a2111oi_1`（0.495） | `a2111oi_1` | 9 種：`a2111oi_1`、`o41ai_1`、`a2111oi_2`、`a222oi_1`、`nor4b_1`、`o311ai_1`、`nor4_1`、`a221oi_1`、`a2111oi_4` |
| ss_n40C_1v60（若加進 resizer 的 corner） | `a2111oi_1`、`o41ai_1` | 10 種 | 17 種 |

現在的設定下，會讓迴圈出不來的只有 `a2111oi_1`。

### 會讓 resizer 去換尺寸的 cell

推一個 `_2` 輸入加短線（0.005 pF，這次的實際負載，本案建議值）時就超過上限的 cell，resizer 會去換它的尺寸，而依上面第 2 點可能換成最弱的那個。ss_100C_1v60，resizer 可用的 cell 有 14 種：

- 超過 0.49 ns（30% 餘量）：`a2111oi_1` 0.697、`o41ai_1` 0.599、`nor4b_1` 0.576、`nor4_1` 0.530、`a222oi_1` 0.528、`nor4bb_1` 0.524、`a2111oi_2` 0.503、`o311ai_1` 0.498
- 另外超過 0.42 ns（40% 餘量）：`a221oi_1` 0.484、`o32ai_1` 0.476、`a311oi_1` 0.460、`o31ai_1` 0.443、`a211oi_1` 0.429、`o41ai_2` 0.424

除了 `a2111oi_2`、`o41ai_2`，都是 `no_synth.cells` 裡的 `_1`：合成不會產生，只有 resizer 換尺寸時會換上。PicoRV32 版的 golden 成品網表（`runs/soc_top/final/nl/soc_top.nl.v`）有 `a2111oi_1` 1 顆、`nor4_1` 3 顆、`o311ai_1`、`a221oi_1`、`o31ai_1` 各 1 顆；`picorv32_core` 的 golden 也有 `a2111oi_1` 1 顆。`no_synth.cells` 也包含 clock buffer、`dlygate4sd3_1`、decap、diode 等 PnR 必須用的 cell，所以不能整份套用到 PnR。

只看允許合成的 cell（合成網表會出現哪些），同樣 0.005 pF：30% 餘量只有 `a2111oi_2`（0.498／0.503）；40% 多了 `o41ai_2`（0.420／0.424，臨界）；50% 有 10 種。PDK 的 `no_synth.cells` 排除 `a2111oi_1`、`drc_exclude.cells` 排除 `a2111oi_0`，`_2` 沒有排除。兩個 SoC 的合成網表：PicoRV32 版 `a2111oi_2` 1 顆、`o41ai_2` 1 顆；Hazard3 版 `a2111oi_2` 2 顆、`o41ai_2` 0 顆。UART 的 RTL 兩版相同（`third_party/picorv32/picosoc/simpleuart.v`，兩個檔案清單共用、不在 `SOC_CPU_HAZARD3` 下），換 CPU 後整顆設計重新合成，結果跟著改變。

## 過去的「修復停不下來」（推測是同一機制，未重現）

| 時間 | 情況 | 和這次的關聯（推測） |
|---|---|---|
| Phase 3 soc_explore6 | `GRT_DESIGN_REPAIR_MAX_SLEW_PCT` 50，post-GRT 修復 26 分鐘以上不結束 | 50% 時有 9 種 cell 符合「迴圈出不來」的條件 |
| Phase 3.5 第 1 次 harden-soc | SRAM .lib 的 dout0 延遲表負載斜率等於 60–140 kΩ 的 driver，`RepairDesignPostGPL` 75 分鐘後異常結束；`sample` 看到 `repairNetWire`／`insertBufferBeforeLoads` | 很弱的 driver 推最小負載就超過上限；同樣的 call stack |
| Phase 4 第 1 次 harden-soc | resizer 看 15 個 corner（加 ss_n40C 等），post-GRT 修復 35 分鐘以上不結束；改回 9 個 58 秒 | ss_n40C 下 40% 餘量有 10 種 cell 符合條件 |

當時都沒有記下記憶體用量與卡住的 net，原 run 已刪，無法確認。

## 處理

使用者決定（2026-10-06，ADR-0012）：

- `pnr/soc_top/config.json` 與 `config_hazard3.json` 的 `EXTRA_EXCLUDED_CELLS` 加上 `a2111oi_1`（合成本來就不用它，只影響 resizer）。PicoRV32 版 SoC 的 golden 有一顆 `a2111oi_1`，它的 harden 結果會改變，要重跑並更新 golden。`pnr/picorv32_core/config.json` 不改。
- harden 前的弱 cell 檢查：`pnr/check_weak_cells.py`，由 `check_inputs.py` 的 `weak_cells`（設定檔）與 `weak_cells_run`（`resolved.json`）執行；植入錯誤 P40–P42。
- skill：`drv-timing-closure` 規則 10（這個迴圈）與規則 11（修哪個 corner 就用那個 corner 的資料判斷修法；換工具或升版時用對照實驗確認，使用者要求寫成規則，不只寫在腳本）、`multicorner-sta` 規則 2、`librelane-run-debug` 規則 3 與已知陷阱、`core-migration-hazard3` 經驗紀錄。
