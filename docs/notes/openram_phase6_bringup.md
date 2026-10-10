# Phase 6 OpenRAM 環境建立紀錄（ADR-0018 步驟 1）

本機：Apple M4、macOS、OpenRAM dev `3608704c`、sky130_fd_bd_sram `fc63b12`、`use_nix = False`，
工具用 LibreLane nix store 的 Magic 8.3.623、Netgen 1.5.316、KLayout 0.30.7，Homebrew ngspice 47，
Python 3.14.6 venv（numpy 2.5.3、scipy 1.18.1、scikit-learn 1.9.1）。工具放在 `.tools/openram*`（不進版控）。
對照：Colab CPU VM（2 核、12 GB，x86_64 Ubuntu），Determinate nix installer `--init none`，OpenRAM 官方 `nix develop`。

## 安裝方式（本機）

- OpenRAM 與 sky130_fd_bd_sram 各自 clone 並 checkout 上面的 commit。
- `PDK_ROOT` 指向 `.tools/openram-pdk/`：`sky130A` 連到 `~/.ciel/sky130A`，`sky130_fd_bd_sram` 是上面的 clone。
- `make sky130-install` 會從 `$PDK_ROOT/skywater-pdk/libraries/sky130_fd_sc_hd/latest/cells/dlxtn/` 複製 `sky130_fd_sc_hd__dlxtn_1` 的 GDS 與 SPICE，
  但 OpenRAM 的 Python 沒有用到它（`git grep dlxtn` 只出現在 Makefile）。本機不 clone 整個 skywater-pdk，
  改從 ciel PDK 抽出這一個 cell：SPICE 用 awk 從 `sky130_fd_sc_hd.spice` 擷取，GDS 用 KLayout 從合併的 GDS 切出。

## 遇到的現象

| # | 現象（原文） | 根因 | 處理 | 狀態 |
|---|---|---|---|---|
| 1 | `make sky130-install` rc=0，但之後產生 macro 時 `ERROR: file design.py: line 44: Custom cell pin names do not match spice file: ['BL0', 'BR0', 'BL1', 'BR1', 'WL0', 'WL1', 'VDD', 'GND'] vs []` | 已驗證：OpenRAM 的 Makefile 用 `cp -va $?` 複製 cell，`$?` 只含比目標目錄新的檔案。`technology/sky130/gds_lib` 等目錄在 OpenRAM checkout 時就存在（repo 內有 custom cell），比後來 clone 的 bd_sram 檔案新，所以 bd_sram 的 260 個 GDS 都沒有被複製（`gds_lib` 只有 7 個檔）。本機 make 是 GNU Make 3.81（`-B` 沒有讓 `$?` 包含全部檔案；新版 make 是否不同沒有查證） | `touch` bd_sram 與 dlxtn 的全部檔案後重跑：`gds_lib` 267、`sp_lib` 293 個檔 | 繞過；防護：安裝後檢查 `sp_lib` 有 `openram_dp_cell` |
| 2 | 產生 macro 時 log 第一行 `ERROR: file magic.py: line 387: p6_tiny_1rw1r_8x16	LVS mismatch`，但 `sram_compiler.py` 的 exit code 是 0，GDS／LEF／.lib 照樣輸出 | 已驗證（同一次執行，rc=0） | 判斷成敗要讀 log 的 `ERROR`，不能只看 exit code | 要寫成 checker |
| 3 | 小 macro（1rw1r 8×16，34 秒）DRC 0，LVS 45 個 cell 不一致，連 `pinv` 都不一致：萃取的 NMOS 是 `sky130_fd_pr__special_nfet_01v8`，電路圖是 `sky130_fd_pr__nfet_01v8` | 已驗證（只換 PDK、Magic 同為 8.3.623）：本機 PDK（open_pdks `8afc834`）的 `sky130A.tech` 把標準 cell 區域（`scnfet`）裡 `w<0.42` 的 NMOS 萃取成 `special_nfet_01v8`（第 5951 行），2022-07 的 PDK（`e8294524`，OpenRAM 釘的版本）沒有這條規則。改用 2022 PDK（ciel release 的 `common` 與 `sky130_fd_pr`，`.tools/openram-pdk2022/`）後 `Final result: Circuits match uniquely.`、DRC 0 | 見下表 | 分支選擇待使用者決定 |

### LVS 對照（小 macro 1rw1r 8×16，本機 Magic 8.3.623）

| OpenRAM | PDK | DRC | LVS 最終結果 |
|---|---|---|---|
| dev `3608704c` | `8afc834`（SoC flow 用的） | 0 | Netlists do not match（45 個 cell） |
| dev `3608704c` | `e8294524`（2022，OpenRAM 釘的） | 0 | Circuits match uniquely |
| dev ＋ stable 的 `1123f733`（PR #304，窄 NMOS 改用 `special_nfet_01v8`；dev 沒有，手動移植到 `tech_configs/`，本機 commit `71b37610`） | `8afc834` | 0 | Netlists do not match：OpenRAM 產生的 `pinv` 對上了，但 `sky130_fd_bd_sram` 的固定 cell（dp_cell、replica、dummy、sense_amp、write_driver）萃取出的 `special_nfet_latch` 數量不同（例如 12 對 10），連帶上層 cell 也不一致 |

| dev ＋ `1123f733` ＋ 安裝目錄的 bd_sram 網表把 `special_pfet_pass` 改成 `special_pfet_latch`（23 個檔，只為了實驗） | `8afc834` | 0 | Netlists do not match：OpenRAM 產生的 `pnand2`／`pnand3`／`and2_dec`／`wordline_driver`，以及 bd_sram 的 dp_cell、dummy、replica、sense_amp、write_driver 仍不一致；dummy cell 萃取出來沒有 PMOS（`disconnected node: VDD`）。沒有再追 |

### 兩版 PDK 的元件名稱差異（已查證）

- 單獨萃取 `sky130_fd_bd_sram__openram_dp_cell`（Magic 8.3.623）：新 PDK 得到 12 顆 `special_nfet_latch`＋4 顆 **`special_pfet_latch`**；2022 PDK 得到 12＋4 顆 **`special_pfet_pass`**，和 cell 附的 `.lvs.spice` 相同。
- 模型檔：`special_pfet_pass` 在 2022 PDK 15 個檔、新 PDK 1 個檔；`special_pfet_latch` 2022 PDK 0 個、新 PDK 15 個；`special_nfet_01v8` 2022 PDK 0 個、新 PDK 25 個。
- 新 PDK `libs.ref/sky130_fd_pr/spice/sky130_fd_pr__special_pfet_latch.pm3.spice:343-354` 的原文：「"special_pfet_pass" was incorrect nomenclature and has been fixed to "special_pfet_latch". The original incorrect name is kept here to prevent breaking legacy netlists. ---Tim 7/16/2023」，並定義 `special_pfet_pass` 為轉接到 `special_pfet_latch` 的 subckt。所以用新 PDK 模擬舊名稱的網表仍可行（推測，還沒實跑）。
- PDK 附的預建 2 KB macro 網表用的是 `special_pfet_latch`（8 處）。

| 4 | Colab 官方環境用預設 `use_nix = True` 產生 macro：`ERROR ... magic.py ... Unable to find the total error line in Magic output`，`drc.err` 是 `path "/tmp/openram_root_6499_temp" does not contain a 'flake.nix' ... error: could not find a flake.nix file` | 已驗證：`use_nix = True` 時每次呼叫 Magic 等工具都在暫存目錄包一層 `nix develop`，暫存目錄沒有 flake | 已經在 `nix develop` 裡面時設 `use_nix = False`（工具仍是官方 flake 的版本） | 繞過 |
| 5 | 官方 devShell 的 venv（`compiler/.venv`）是空的：`ModuleNotFoundError: No module named 'numpy'` | 已驗證：flake 的 shellHook 只建 venv，不裝套件 | 進 devShell 後 `python3 -m pip install -r requirements.txt` | 繞過 |
| 6 | 同一份設定連跑兩次，GDS 的 met2（70/20）、met3（71/20）、via2（70/44）不同（XOR 面積約 42.5／2.7／0.7 µm²），網表與 LEF 只有輸出順序不同 | 已驗證：Python 的 hash 隨機化。設 `PYTHONHASHSEED=0` 後本機連跑兩次 GDS、網表、LEF 逐位元相同；Colab（Python 3.13）與本機（3.14）的 GDS XOR 0、LEF 相同、網表排序後相同（subckt 順序不同） | 產生 macro 一律設 `PYTHONHASHSEED=0` | 繞過；防護：重跑比對 sha256 |

### 步驟 1 結論（2026-10-08）

- 本機 macOS 原生（`use_nix = False`）可以產生 macro。用 OpenRAM 釘的 2022 PDK：小 macro DRC 0、LVS `Circuits match uniquely`。
- Colab 官方環境（Magic 8.3.629、Netgen 1.5.318、2022 PDK）同一份設定：DRC 0、LVS `Circuits match uniquely`。設 `PYTHONHASHSEED=0` 時和本機的 GDS XOR 0、LEF 相同、網表內容相同。所以本機的 Magic 8.3.623／Netgen 1.5.316 沒有造成差異（小 macro 的範圍）。
- 用 SoC flow 的 PDK（`8afc834`）驗證 macro 時 LVS 不過，原因是兩版 PDK 之間的元件名稱與萃取規則改變（上一節），不是版圖錯誤；要讓 `8afc834` 也通過，還有 bd_sram 固定 cell 的萃取差異沒查清。

Colab 官方環境：Magic 8.3.629、Netgen 1.5.318、KLayout 0.30.7、ngspice 45、Xyce 7.10.0；GNU Make 4.3 裝出的 `gds_lib`／`sp_lib` 是 267／293 個檔，和本機 `touch` 後相同。安裝（`nix develop` 1 分 24 秒、`make sky130-pdk` 1 分 17 秒、`make sky130-install` 4 秒）。

## 步驟 2a：2 KB 1rw1r（預建 macro 的設定，2026-10-08，本機）

設定 `ip/sram/openram/configs/arv_sram_2kbyte_1rw1r_32x512_8.py`；2022 PDK、`PYTHONHASHSEED=0`；手動執行（`.tools/openram-work/m2k/`，腳本完成前）。

| 項目 | 自產 `arv_sram_2kbyte_1rw1r_32x512_8` | 預建 `sky130_sram_2kbyte_1rw1r_32x512_8`（2021 log） |
|---|---|---|
| 時間 | 40.5 分鐘（繞線 261 s、DRC／LVS 2164 s），記憶體峰值 1.3 GB | 4.4 小時（繞線 2624 s、DRC／LVS 13100 s） |
| 尺寸 | 694.27 × 423.545 µm | 683.1 × 416.54 µm |
| OpenRAM 的 LVS | Circuits match uniquely | LVS matches |
| OpenRAM 的 DRC（bd_sram cell 用 maglef 抽象版圖） | 5：met2 間距 < 0.14 µm（met2.2，13 個方框）、met3 間距 < 0.3 µm（met3.2，12 個）、via2 間距 < 0.12 µm（2 個），都是繞線 | 32（種類未記錄） |
| bitcell 數（網表 `Xbit_r`） | 16640 | 16512 |
| bitcell PMOS 名稱 | `special_pfet_pass` | `special_pfet_latch` |

另外兩個現象：
- DRC 錯誤在 log 只記成 `WARNING: file magic.py: line 254: DRC Errors ...\t5`，不是 `ERROR`。
- 設定檔的 `openram_temp` 沒有生效，報告仍在 `/tmp/openram_<user>_<pid>_temp/`：`read_config` 只採用 `OPTS` 還沒有的鍵（`compiler/globals.py:361`）；要用環境變數 `OPENRAM_TMP`（`gen_macro.py` 已改）。

### 整顆 GDS 的 Magic DRC（`drc style drc(full)`，2026-10-08）

兩顆 macro 單獨從 GDS 讀入，Magic 8.3.623：

| | 自產 | 預建 |
|---|---|---|
| 總數（PDK `8afc834`，SoC flow 用的） | 2,234,537 | 2,235,078 |
| 錯誤種類 | 33 | 30 |

- 29 種兩邊都有，都是 bitcell 的 SRAM 特殊規則（diff/tap.9、li.1、licon.8 …），數量差幾百。
- **只有自產有的 4 種**（PDK `e8294524` 的 full 規則也一樣抓到，所以和 PDK 版本無關）：
  - met2.2 間距 13 個方框，在 (91.7, 19.0) µm；met3.2 間距 12 個，在 (136.6, 78.4) µm；via2.2 間距 2 個，在 (557.8, 381.8) µm：OpenRAM 繞線。
  - nwell.5a（N-well 包 Deep N-well：外 0.4、內 1.03 µm）10 個方框，繞 macro 一圈：Deep N-well 的 N-well 保護環內側只有 0.42 µm。預建 macro 的保護環是外 0.42、內 1.03 µm（KLayout 量）。OpenRAM `add_dnwell`（`compiler/base/hierarchy_layout.py`）用一條寬 `nwell_width` 的 path 沿 Deep N-well 邊界畫，內外各一半；stable 與 dev 寫法相同。
- 只有預建有的 1 種：「Can't overlap those layers」161 個。
- **OpenRAM 自己的 DRC 只報 5（繞線那 3 種），沒有 nwell.5a**：它用的不是 full 規則。所以 macro 要另外跑 full 規則的 DRC，不能只看 OpenRAM 的數字。

### 用 repo 腳本重產（`make openram-macro OPENRAM_DRC_MAX=5`，2026-10-08）

- `make openram-setup` 第一次 FAIL：既有的 venv 是 `uv venv` 建的，沒有 pip（`No module named pip`）；改成沒有 pip 時先 `ensurepip`（不吃 `-q`）。修正後 PASS（cell 庫檢查 PASS）。
- `gen_macro: PASS`，40.9 分鐘，DRC 5、LVS `Circuits match uniquely.`。
- 和手動那次比：LEF、SPICE、LVS 網表、Verilog 的 sha256 相同；GDS 的 sha256 不同，但 KLayout XOR 0 層不同，948 個位元組的差異都在時間戳記（檔頭 BGNLIB 與各 cell 的 BGNSTR）。所以版圖可重現；GDS 要用 XOR 比，不能比 sha256。

## 步驟 2b：Colab 官方環境產生同一顆 2 KB（2026-10-08）

- 第一次（session `p6-m2k`，含 DRC／LVS）：約 1 小時時 `colab exec` 回 401／404，CLI 判定 session 遺失、刪掉本機紀錄，VM 卻仍在伺服器上（`colab sessions` 顯示 `[?]`）。用 CLI 內部的 `state.client.unassign(endpoint)` 釋放（`/colab` skill 已記錄）。
- 第二次（`p6-m2k2`，`check_lvsdrc = False`，只產生）：23 分 54 秒（本機約 5 分鐘）。和本機 `make openram-macro` 的產出比：**GDS XOR 0 層不同、LEF 與 Verilog sha256 相同、SPICE 與 LVS 網表排序後相同**。所以本機 macOS 與官方 x86 Linux 環境產生的 2 KB macro 是同一個版圖，上一節的 DRC 錯誤是 OpenRAM 本身產生的。VM 已關。

### 整顆 DRC 的 checker（`macro_drc.py`，ADR-0018 決定 6）

- baseline（`ip/sram/openram/drc_baseline_sky130_sram_2kbyte_1rw1r_32x512_8.json`）：PDK 預建 macro，open_pdks `8afc834`，2,235,078 個、30 種，4.8 分鐘。
- 自產 2 KB：**FAIL**，2,234,537 個，4 種不在 baseline（met2.2 13、met3.2 12、nwell.5a 10、via2.2 2），和手動檢查相同；依決定 6 列為已知未修。
- 第一次跑自產時判「Magic DRC did not finish」：輸出路徑是相對路徑，Magic 在 LibreLane 目錄執行時找不到 Tcl 檔。checker 判 FAIL（沒有誤判 PASS）；改成絕對路徑後正常。`neg-openram` D1–D3 加上後 19/19。

## 步驟 3a：讀取正確性（`ip/sram/openram/read_check.py`，2026-10-08）

方法：Phase 3.5 的 `characterize.read_fails`（delay 序列，週期 20 ns，中間的 clock slew 與負載；連續讀取不同值），PDK `8afc834` 的 ngspice 模型，修剪網表（保留 1264 顆 bitcell）。自產網表先把 8 處 `special_pfet_pass` 改成 `special_pfet_latch`。
`sramchar.py` 為此改了三處，預建 macro 的修剪結果與修改前逐位元組相同：macro 名稱可由 `SRAM_CHAR_MACRO` 指定；`trim_schematic` 認得 `<macro>_bitcell_array`、名稱後直接換行的 `.SUBCKT` 行與跨行的 instance；`subckt_ports` 去掉單獨的 `+`。

| 條件 | 自產（預設設定，words per row 4） | 預建（對照，同一支程式） |
|---|---|---|
| tt 25°C 1.80 V | 讀對 | 讀對 |
| ss 100°C 1.60 V | 讀對 | — |
| ff −40°C 1.95 V | 讀對 | — |
| ff 100°C 1.95 V | 讀對 | — |
| ss −40°C 1.60 V | 讀錯 3 筆 | 讀錯 7 筆 |
| ss 25°C 1.60 V | 讀錯 3 筆 | 讀錯 3 筆 |
| tt −40°C 1.60 V | 讀錯 7 筆 | — |

結論：對照組重現了 ADR-0010 的失敗（程式抓得到錯）；自產 macro 在同樣三個條件讀錯，錯法同樣是連續讀取不同值時讀成前一次的值。和開工前的原始碼查證一致：預設設定的 sense amp 與 column mux 和預建相同。

## 步驟 3b：words_per_row = 1（`configs/arv_sram_2kbyte_1rw1r_32x512_8_wpr1.py`，2026-10-08）

| 項目 | wpr1 | 預設（wpr4） | 預建 |
|---|---|---|---|
| 陣列 | 512 列 × 32 行，沒有 column mux | 128 × 128 | 128 × 128 |
| 時間 | 57.6 分鐘（繞線 1198 s、驗證 2193 s） | 40.9 分鐘 | — |
| 尺寸 | **446.99 × 1152.58 µm** | 694.27 × 423.545 µm | 683.1 × 416.54 µm |
| OpenRAM DRC／LVS | 0／Circuits match uniquely | 5／match | 32／match |
| 整顆 full DRC（`8afc834`） | **FAIL**：2,317,896（> 預建 2,235,078），32 種；不在 baseline 的 3 種：LU.2.1（N-diff 離 Deep N-well 裡的 P-tap > 15 µm）80、LU.3（P-diff 離 N-tap > 15 µm）80、nwell.5a 14 | FAIL：2,234,537，4 種新（繞線 3 種＋nwell.5a） | baseline |

- 繞線間距錯誤沒有出現；Deep N-well 保護環的問題（nwell.5a）仍在；多了 latch-up 的 tap 距離錯誤（LU.2.1、LU.3）。
- **尺寸放不進現在的 SoC**：die 1000 × 800 µm（ADR-0006），這顆高 1152.58 µm，轉 90 度寬也是 1152.58 µm。
- 網表沒有 column mux；第 b 個 sense amp 接 `bl_<b>`，所以 column = bit，和 `sramchar` 的假設一致。

### wpr1 的讀取正確性（`read_check.py --words-per-row 1`，週期 20 ns）

修剪保留第 0、3、508、511 列與第 0、31 行（1144 顆；陣列外的 replica／dummy 64 顆不動）。

| 條件 | 預設（wpr4） | wpr1 |
|---|---|---|
| tt 25°C 1.80 V | 讀對 | 讀對 |
| ss 100°C 1.60 V | 讀對 | 讀對 |
| ff −40°C 1.95 V | 讀對 | 讀對 |
| ff 100°C 1.95 V | 讀對 | 讀對 |
| ss −40°C 1.60 V | 讀錯 3 筆 | **讀對** |
| ss 25°C 1.60 V | 讀錯 3 筆 | **讀對** |
| tt −40°C 1.60 V | 讀錯 7 筆 | **讀錯 2 筆**：只有位址 511（最後一列）的 bit 31，該讀 0 讀成 1（`cycle 4 r511`、`cycle 8 r511`） |

- 拿掉 column mux 後，Phase 3.5 的失敗（整個字讀成前一次的值）在 ss −40°C 與 ss 25°C 消失，符合「純 NMOS column mux 讓 sense amp 內部節點拉不回來」的機制。
- tt −40°C 1.60 V 剩下的錯法不同（單一 bit、單一位址），而且較慢的 ss −40°C 反而讀對。週期實驗（`runs/openram/read_check_wpr1/period_exp.py`）：20、30、44 ns 的錯法完全相同（同兩筆、同 bit 31、同 1.60 V），**和週期無關**，所以不是讀取時序的競爭。推測是那顆 cell（第 511 列、bit 31，離寫入電路最遠）寫不進去或被干擾，未驗證（要量 storage node）。

## 步驟 3：網表 what-if（只改電路圖，不是版圖；`runs/openram/whatif/make_whatif.py`，2026-10-08）

在預設版（wpr4）2 KB 的網表（已改 `special_pfet_latch`）上，只改 port 0：
- **W1 transmission gate**：column mux 每顆 NMOS 旁並聯一顆 PMOS（w 2.88 µm），閘極是理想的 `vccd1 − sel`（E 電壓源，只為驗證機制）。
- **W2 sense amp 輸入端預充電**：`port_data` 的每個 bit 在 `bl_out`／`br_out` 加一個 OpenRAM 的 `precharge_0` cell（兩顆上拉＋一顆等化 PMOS，w 0.55 µm），接同一個 `p_en_bar`。

| 條件 | 預設 | W1 | W2 |
|---|---|---|---|
| tt 25°C 1.80 V | 讀對 | 讀對 | 讀對 |
| ss −40°C 1.60 V | 讀錯 3 | **讀對** | **讀對** |
| ss 25°C 1.60 V | 讀錯 3 | **讀對** | **讀對** |
| tt −40°C 1.60 V | 讀錯 7 | **讀對** | **讀對** |

結論（已驗證，單一變因的電路圖實驗）：讓 sense amp 的輸入端回到滿 VDD 就消除讀取失敗，兩種做法都有效。確認了 ADR-0010 的機制（純 NMOS column mux 只能把 sense amp 內部節點拉回 VDD − Vt）。時序影響還沒量。

## 步驟 3p1：sense amp 輸入端預充電的版圖（OpenRAM patch，2026-10-08）

做法（`ip/sram/openram/patches/0001-sense-amp-input-precharge.patch`，改 3 個檔）：
- `port_data.py`：有 column mux 的讀取 port（port 0 讀寫、port 1 唯讀）多一個 `precharge_array`（`sense_precharge_array<port>`），每個資料 bit 一個 cell，位置是 sense amp 的位置（`bit_offsets[b × words_per_row]`），接 `bl_out_<b>`／`br_out_<b>`、`p_en_bar`、`vdd`；疊在 column mux 與 sense amp 之間；bitline 改成 column mux → 新陣列 → sense amp 兩段 `connect_bitlines`；新陣列的 `en_bar` 也輸出成一支 `p_en_bar` 接腳。沒有 column mux 或有 spare column 時不加。
- `precharge_array.py`：加 `mirror_stride`（預設 1，行為不變）。cell 的左右鏡像原本依序號奇偶交替，但新陣列每 `words_per_row` 行才一個 cell，要用 `i × words_per_row` 的奇偶，和 sense amp 陣列相同。
- `bank.py`：`p_en_bar` 改成逐一連接 port_data 的每一支同名接腳（原本用 `get_pin`，同名接腳有兩支時 OpenRAM 會報 `Should use a pin iterator since more than one pin`）。

小 macro 驗證（1rw1r、8 bit × 64 word、write size 2、words per row 4；`runs/openram/p3p1_small/`，未套 patch 的版本用 `.tools/openram-base` 的 git worktree 同時產生）：

| | 未套 patch | 套 patch |
|---|---|---|
| OpenRAM DRC／LVS | 12／Circuits match uniquely | 2／Circuits match uniquely |
| 整顆 full DRC（`8afc834`） | 78,984，32 種 | 78,974，31 種；**沒有新種類**（met3.2 的 26 個消失，met2.2 21 → 13） |
| 新陣列位置 | — | port 0 在 y 63.8–67.6 µm（sense amp 49.9–62.7、column mux 68.8–79.8 之間）；port 1 在 149.4–153.2 µm（column mux 與 sense amp 之間） |

- 網表：兩個 port 都有 `sense_precharge_array`，接 `bl_out_0..7`／`br_out_0..7`、`p_en_bar`、`vdd`。LVS 通過也表示新陣列的 `p_en_bar` 在版圖上接到了控制線。
- 剩下的 met2.2 在 (72.3, 19.0–19.6) µm，和 2 KB 預設版 (91.7, 19.0–19.6) µm 的形狀相同，是 OpenRAM 原有的繞線錯誤，離新陣列很遠。
- 沒有 column mux（wpr1）時行為不變：未套與套 patch 的 netlist-only 網表排序後相同。
- `make openram-setup` 會偵測 OpenRAM 不是「釘選 commit＋patch」，回到 `3608704c` 再套 patch（第二次執行不重套）；`gen_macro.py` 的 `summary.json` 記錄 patch 檔名與 sha256；`neg-openram` 加 T1–T3 後 23/23。

## 步驟 3p2：2 KB 套 patch 0001（sense amp 輸入端預充電，2026-10-08）

`make openram-macro OPENRAM_DRC_MAX=5`（預設設定，words per row 4；沒套 patch 的那次被 `gen_macro.py` 改名保留為 `.old-<時間>`）：

| 項目 | 套 patch | 沒套 patch |
|---|---|---|
| 時間 | 38.9 分鐘 | 40.9 分鐘 |
| 尺寸 | 694.27 × **428.415** µm | 694.27 × 423.545 µm |
| OpenRAM DRC／LVS | 2／Circuits match uniquely | 5／match |
| 整顆 full DRC（`8afc834`） | FAIL：2,234,534，31 種；不在 baseline 的 2 種：met2.2 13、nwell.5a 10 | FAIL：2,234,537，33 種；4 種（met2.2、met3.2、via2.2、nwell.5a） |
| `summary.json` 的 patch 紀錄 | `0001-sense-amp-input-precharge.patch`，sha256 `8eb4c4a7…` | — |

- 高度多 4.87 µm（兩個 port 各多一排 precharge cell）。
- met3.2、via2.2 消失、met2.2 仍在：繞線位置跟著版面改變；met2.2 的根因仍沒查（ADR-0018 決定 6：選定後再修）。

### 套 patch 版本的讀取正確性（`read_check.py`，7 個條件，週期 20 ns）

| 條件 | 沒套 patch | 套 patch 0001 |
|---|---|---|
| tt 25°C 1.80 V | 讀對 | **讀錯 3 筆**（只有 bit 0、31：`cycle 6 r3` bit 31 讀成 0、`cycle 7 r0` bit 0 讀成 0、bit 31 讀成 1） |
| ss 100°C 1.60 V | 讀對 | 讀對 |
| ff −40°C 1.95 V | 讀對 | 讀對 |
| ff 100°C 1.95 V | 讀對 | 讀對 |
| ss −40°C 1.60 V | 讀錯 3 | **讀對** |
| ss 25°C 1.60 V | 讀錯 3 | **讀對** |
| tt −40°C 1.60 V | 讀錯 7 | **讀對** |

- 錯的都是 bit 0 與 31（修剪後只有這兩行掛著完整的 128 顆 cell），位址 0 與 3（第 0 列）。ngspice log 沒有收斂問題。
- 網表比對：port 0 新加的預充電排和 what-if W2 的接法、尺寸相同；控制電路沒有改變（subckt 逐一比較，只有 `port_data`、`port_data_0` 不同，precharge array 只是重新編號）。和 W2 的差別是 **patch 連 port 1（唯讀，SoC 不用，模擬時 `csb1=1`、`clk1=0`、`addr1=0`）也加了預充電排**。
- 實驗 E1（單一變因）：在套 patch 的網表裡只拿掉 port 1 的預充電排，tt 25°C 讀對。兩份網表只差這 12 行。

### 根因：閒置 port 1 的 chip-select DFF 從沒被時脈鎖存（探針 + E2 已驗證）

`runs/openram/whatif/{probe,probe_e1,e2}/`（同一份 tt 25°C deck，每個節點各輸出一個檔；`probe_analyze.py` 逐週期整理）：

| | 套 patch（讀錯） | E1：拿掉 port 1 預充電排（讀對） | E2：套 patch，`clk1` 和 `clk0` 同波形、`csb1=1`（讀對） |
|---|---|---|---|
| `wl_en1` | **整段 1.8 V** | 0 V | 只在第一個 `clk1` 上升前是 1.8 V，之後 0 V |
| `wl_1_0`（port 1 第 0 列 wordline） | **整段 1.8 V** | 0 V | 同上 |
| `p_en_bar1`（port 1 預充電，低電位有效） | 整段 1.8 V（不預充電） | 1.8 V | 1.8 V |
| 第 0 列讀取（週期 6、7、9） | bitline 本身就是錯的值（例：週期 7 讀位址 0，column 0 `bl`=0.01 V、`br`=1.90 V，存的是 0） | 對 | 對 |
| 7 筆讀取 | 錯 3 筆 | 全對 | **全對** |

- 機制（`control_logic_r` 的網表）：`cs` 是 `csb` 經 DFF（時脈 `clk_buf`）鎖存的值；`wl_en = clk_bar AND cs`；`p_en_bar = NAND(clk_buf AND cs, rbl 延遲)`。OpenRAM 在 clk 低的半週期開 wordline。`clk1` 一直是 0 時 `clk_bar=1`，`wl_en1` 就等於 DFF 的初始狀態；位址 DFF 也沒鎖存過。
- 模擬裡的初始狀態由 t=0 的 DC 解決定。多一排預充電改變了 DC 解，`cs` 落在 1，port 1 第 0 列的 wordline 就一直開著、port 1 的 bitline 又沒預充電。port 0 寫第 0 列時，cell 同時被 port 1 那一側的 bitline 拉住，寫入失敗。所以讀錯的是**存進去的資料**，不是 sense amp 停在前一筆的值（後者是 Phase 3.5 與步驟 3a 的失敗）。
- 不是 patch 接錯：E2 只改 `clk1` 激勵就讀對。沒套 patch 的版本、預建 macro、其他 PVT 會讀對，是 DC 解剛好落在 `cs=0`。
- **對晶片的意義**：`rtl/soc/soc_top.v:261-263` 把 port 1 接成 `clk1=1'b0`、`csb1=1'b1`、`addr1=9'd0`，`sramchar.py` 的激勵照這個接法。實際上電後 DFF 的狀態不確定：落在 `cs=1` 時，port 1 某一列的 wordline 會一直開著，該列的寫入可能失敗。預建 macro 也是同一套 control logic（Phase 3.5 起一直用這個接法）。讓 `clk1` 打時脈（`csb1=1`）後，第一個上升邊緣就把 `cs` 清成 0（E2）。


### 決定 9 之後：`clk1` 打時脈的讀取正確性（`read_check.py`，`sramchar.py` 的 `clk1` 與 `clk0` 同波形，2026-10-08）

`runs/openram/read_check_clk1_self/`、`read_check_clk1_pre/`：

| 條件 | 自產＋patch 0001（`clk1=0`） | 自產＋patch 0001（`clk1` 打時脈） | 預建（`clk1=0`，步驟 3a 只跑 3 個） | 預建（`clk1` 打時脈） |
|---|---|---|---|---|
| tt 25°C 1.80 V | 錯 3 | **對** | 對 | 對 |
| ss 100°C 1.60 V | 對 | 對 | — | 對 |
| ff −40°C 1.95 V | 對 | 對 | — | 對 |
| ff 100°C 1.95 V | 對 | 對 | — | 對 |
| ss −40°C 1.60 V | 對 | 對 | 錯 7 | 錯 7 |
| ss 25°C 1.60 V | 對 | 對 | 錯 3 | 錯 3 |
| tt −40°C 1.60 V | 對 | 對 | — | 錯 3 |

- 套 patch 0001 的自產 macro 在 7 個條件全部讀對：步驟 3p2 完成。
- 預建 macro 的讀錯和 `clk1=0` 時相同（輸出停在前一筆的值，ADR-0010），`clk1` 的接法不影響這個問題。

## 步驟 3c：自產 macro 的 SPICE 特性化（2026-10-09 開始）

- 輸入：`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/openram/`（網表 sha256 `368c74be…` = `summary.json` 記錄的值）。`make openram-char`，模擬在 `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/schematic/`，log `runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/char.log`。
- 修剪：保留 1,264 顆 bitcell（和預建相同），`special_pfet_pass` 8 處改名；預建網表的修剪結果不變（sha256 `ee987fbb…`）。
- .lib 範本：OpenRAM 的 TT .lib 和預建 .lib 同結構（逐行比對只差面積、一個腳位電容、port 1 解析時序、`timing_type` 的空格），但 12 個 internal_power 全是 1.036316e+11；其他自產 macro 也一樣（2 KB wpr1 9.966369e+10、8×16 1.098946e+09、3p1 小 macro 4.395783e+09），預建是 13.8。改用 `lib_template.py` 換成預建的值；`gen_char_lib.py` 拒收超過 1000 的範本（`neg-openram` L1–L2）。
- 結果（2026-10-09 06:10，tt 46 次模擬 1 小時 35 分，其他 4 個 PVT 158 次 4 小時 36 分）：**5 個 PVT 都讀寫正確**（預建 macro 在 ss −40°C 1.60 V 讀錯，只能用佔位 .lib）。和預建 macro 比（`char.json`）：

  | PVT | 讀出 `settle_max`（ns，預建 → 自產） | `depart_min` | 最小週期 | setup／hold 最大 |
  |---|---|---|---|---|
  | tt 25°C 1.80 V | 3.05 → 2.91 | 1.18 → 1.13 | 5.62 → 5.32 | 0.24 → 0.24 |
  | ss 100°C 1.60 V | 5.70 → 5.47 | 2.70 → **2.08** | 9.37 → 8.445 | 0.43 → 0.44 |
  | ff −40°C 1.95 V | 1.87 → 1.79 | 0.71 → 0.70 | 3.495 → 3.32 | 0.16 → 0.16 |
  | ss −40°C 1.60 V | 預建讀錯 → 5.98 | → 2.65 | → 10.445 | → 0.40 |
  | ff 100°C 1.95 V | 1.77 → 1.67 | 0.73 → 0.73 | 2.90 → 2.66 | 0.18 → 0.18 |

- `.lib`（`make openram-lib`）：port 0 的延遲、setup／hold、最小週期與 pulse width 量測值 ×1.6 都低於 ADR-0010 的下限（padded.lib：延遲 10 ns、ss 15 ns，週期 30 ns，setup／hold 1.0 ns），所以採用下限；量測值直接決定的是 dout0 的 hold 弧（最早變化 ×0.9）。ss 100°C 的最早變化比預建早 0.6 ns，接收端的 hold 餘量會變少，步驟 4a 的 STA 要看。
- view QA（`scripts/check_macro_views.py`，LEF／5 份 .lib／Verilog／SPICE／GDS）PASS。
- 確認模擬（`make openram-confirm`，51 分鐘）：5 個 PVT、115 條 lane、25 次模擬，在 .lib 採用的 setup／hold／pulse width／週期上全部讀寫正確（`confirm.json`）。`make openram-check-lib`：來源（網表 sha256＝`summary.json` 記錄的值）、5 個 PVT 的數值獨立重算、確認模擬全部 PASS。來源檢查的自產 macro 分支有 negative test（`neg-openram` C1–C2）。
- `make neg-char`（改過 `sramchar.py`、`gen_char_lib.py`、`check_char_lib.py` 之後重跑，2026-10-09，16 分鐘）：16/16 PASS。步驟 3c 完成。

## 步驟 3e：internal power 與漏電（`ip/sram/char/power.py`，ADR-0018 決定 10、11，2026-10-09）

- 方法：同一個序列（寫、讀、閒置，port 1 `csb1=1`、`clk1` 與 `clk0` 同波形），量 `i(vvdd)` 積分成每次時脈邊緣的能量；修剪網表保留 2 個 bit（b2）與 4 個 bit（b4）的完整 column，外插到 32 bit。`make openram-power`。
- tt 試跑（`runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/power_try.json`）：動態能量 b2 與 b4 相差 < 3%（寫入上升邊緣 8.86／9.11 pJ），但序列最後兩個時脈都停住後量的漏電 b2 0.2032 mW、b4 0.0033 mW，外插 −2.80 mW。

### 漏電：port 1 浮接的 sense amp 上下同時導通（探針已驗證）

- 電流分解（`runs/.../leakdbg/split.py`，bank 與 top 的每個 instance 電源串 0 V 電壓源）：電流全在 `port_data1`（port 1 的 precharge、column mux、sense amp）。同一個 b2／b4 網表加了電壓源之後，DC 解改變，變成 b2 24 µA、b4 110 µA，兩者互換。
- 網表（`control_logic_r`）：`p_en_bar = NAND(clk_buf AND cs, rbl_bl_delay)`，`cs=0` 時恆為 1；bitline 端與 sense amp 端（patch 0001）的 precharge 都接 `p_en_bar1`。sense amp 在 `EN=0` 時隔離 PMOS 導通，`dint`／`dint_bar` 直接接 `bl_out`／`br_out`，輸出反相器的輸入是 `dint_bar`。
- 電壓探針（b4，`leakdbg/b4v`，`volts.py`）：t < 1.5 ns 時 32 顆 sense amp 的 `dint`=1.8 V、`dint_bar`=0 V；第一個時脈邊緣（約 3 ns）之後，13 顆的 `dint_bar` 變成 0.748 V、3 顆的 `dint` 變成 0.793 V，一直維持到模擬結束；port 1 bitline 停在 0.79–1.30 V。`sel1_0`=1.8 V、`sel1_1`=0 V，符合 `addr1=0`。
- （當時的推論，後來證實是錯的，見下面「正式量測」）這個電流從第一個邊緣起就固定，所以每個 run 扣掉自己的靜態電流後，動態能量不受影響。實際上它會隨動作改變；當時只看了節點電壓，沒有用電流驗證。
- 對照（`leakdbg/park.py`）：`csb1=0`，最後一個週期 port 0 讀取，兩個時脈在它的上升邊緣之後停在高電位（兩個 port 都在 precharge、wordline 都關）：b2 0.00044 mW、b4 0.00045 mW，一致。同一份 deck 中 port 1 每個週期都讀取、port 0 閒置的週期約 18.3–18.8 pJ（含 port 0 時脈與漏電）。
- 處理（決定 11）：.lib 漏電改用上面的待機狀態另跑一份 deck（`power.leak_sequence`，`sramchar.deck` 的 `clk_park`、`csb1`）；原本的靜態電流改名 `static_mw`，只用來扣除並記錄（扣除方法由決定 12 修改）。N19 加了漏電 deck 的已知答案（停住邊緣的 50 pJ 突波不能進量測窗）；植入「量測窗包含停住的邊緣」與「靜態電流不扣」兩種錯誤，N19 都 FAIL。

## 步驟 3f：1RW 可行性（`runs/openram_try/arv_sram_2kbyte_1rw_32x512_8.py`，2026-10-09）

- 設定：和 1rw1r 相同，只把 `num_r_ports` 改成 0。第一次在 0.1 分鐘失敗：`ERROR: file sky130_replica_bitcell_array.py: line 30: must have an even number of cols including replica cols; you can add a spare col to fix this`（128 個資料 column＋1 個 replica column）。上游的 sky130 1RW 範例設定都有 `num_spare_cols = 1`。
- 加 `num_spare_cols = 1` 後 30 分鐘產出 GDS／LEF／網表（多出 `spare_wen0`、`din0[32]`、`dout0[32]`），但：
  - OpenRAM 自己的 DRC：657（1rw1r 是 0）。
  - LVS：不一致。`.lvs.json` 中真正的差異在 column cap 的 array：layout 中 `sp_colend`／`sp_colenda` 的 `bl` 與 `br` 接到同一個 net（每個 column 的 BL、BR，以及 replica bitline），gnd／vdd 對調（badelements 1）。其餘子電路只是 vdd 被拆成好幾個 net。上游 `ec28bc6d`（2026-02-22「Fix sky130 1rw LVS mismatch by correcting col_cap pin order」）已在本版本內。
  - 整顆 Magic DRC（`macro_drc.py`）：212 萬個錯誤、41 種（預建 223 萬、30 種），16 種預建沒有。大部分在單 port bitcell 內（`li.5`、`li.6`、`diff/tap.2`、`diff/tap.8`、`poly.5`、`licon.9`），也有繞線類（`met1.1` 262、`met1.2` 1338、`met2.2` 13、`met3.2` 12、`mcon.1` 650、`nwell.5a` 10）。
- 上游 `compiler/tests/Makefile` 的 `BROKEN_STAMPS` 把 sky130 單 port 的 `19_single_bank_*`、`20_sram_1bank_*` 都列為壞掉，對應的 `*_1rw_1r` 版本沒有列。
- 結論：釘住的版本產不出 DRC／LVS 乾淨的 sky130 1RW；使用者選擇維持 1rw1r（決定 11）。

### 正式量測（修剪＋外插，2026-10-09 11:25）與方法修正（ADR-0018 決定 12）

- `make openram-power OR_POWER_ARGS=--calibrate`（5 個 PVT × b2／b4 × 2 份 deck，加 tt 完整網表）判 PASS，但外插值：ff 100°C 讀寫能量全為負（寫入 −30.67 pJ／週期）、port 1 閒置 12 pJ（其他 PVT 約 1 pJ）；ff −40°C read_fall −0.6 pJ。power.py 當時沒有檢查負值（gen_char_lib 才擋），已改成自己判 FAIL。
- 每個週期邊緣前 3 ns 的靜止電流（mW，每兩個週期取一個）：

  | 波形 | phase A（寫、讀、閒置） | phase B（只有 clk1） | phase C |
  |---|---|---|---|
  | tt b2 | 0.24–0.28 | 0.20 | 0.203 |
  | tt b4 | 0.06–0.08 | 0.002 | 0.003 |
  | ff −40°C b4 | 0.31–0.33 | 0.002 → 0.087 | 0.087 |
  | ff 100°C b2 | 0.40–0.52 | 1.46 → 2.68 → 0.89 | 0.818 |

  靜態電流隨動作改變，整段扣 phase C 的值會扣錯。
- 局部基準（每個窗口扣起點前、終點前各 3 ns 靜止電流連成的直線）用同一批波形重算：5 個 PVT 都是正值、b2／b4 一致；tt 外插對完整網表的誤差 write_fall 4.2%、其他 ≤ 0.8%（原方法最大 11%）。內插點要取兩段靜止區間的中點：取在邊界上會落後 1.5 ns，N19 的線性上升靜態電流量到 idle1 多 0.02 pJ（3%）。
- 外插的另外兩個問題：ff −40°C read_fall 的 b4 比 b2 少 0.1 pJ，×15 外插成 −21%；tt 待機漏電外插 0.0005 mW、完整網表 0.0011 mW（−54%，原因未查）。
- 完整網表的實際時間（7 個模擬同時跑）：讀寫 deck 86 分鐘、漏電 deck 36 分鐘。使用者選擇局部基準，5 個 PVT 都用完整網表（決定 12）。

### 半穩態 bitcell 與快速量法（ADR-0018 決定 13，2026-10-10）

- 完整網表 ss −40°C 的漏電量測窗裡功率突然上升（0.5 µW → 尖峰 0.2 mW → 0.28 µW）。修剪網表存全部節點（`runs/sram_char/arv_sram_2kbyte_1rw1r_32x512_8/leakdbg/drift.py`、`drift_scan.py`）：翻轉前 6 顆沒寫過的 bitcell `Q = Q_bar = 0.638 V`，翻轉後 `Q=0`、`Q_bar=1.6 V`。deck 不用 `uic` 時 ngspice 的 DC 工作點給對稱鎖存器平衡解。處理：`sramchar.bitcell_ic()`，N20。
- 快速量法（`leakdbg/fast.py`）：修剪網表待機 deck ＋ 單顆 bitcell（`power.cell_deck()`）× 被拿掉的顆數。b2／b4 兩種修剪的總和：tt 1.216／1.123 µW（停住 12／3 個週期，不同窗口）、同窗口差 2–2.5%。

### DC 工作點量漏電（不可行，2026-10-10，`leakdbg/dcop.py`、`leakdbg/dcop/tt_025C_1v80/`）

- 做法：暫態跑到停住狀態，取最後一點的所有節點電壓當 `.nodeset`，輸入改成最終的 DC 值，跑 `.op`。
- 第一次失敗訊息是 `doAnalyses: out of memory`，伴隨 `Warning: The needed element doesn't exist in the matrix, but KLU mode cannot create a new element. Please specify an existing element for .nodeset`：頂層 157 個由電壓源直接驅動的節點（`addr0[0]`、`clk0`…）矩陣沒有對角元素，KLU 不能新增。元件內部節點（名稱含 `#`，例如 `...msky130_fd_pr__pfet_01v8#sbody`）報 `Nodeset on non-existent node`。只留 `xsram.` 內部 6233 個節點後 `.op` 可以跑完。
- 結果不能用（tt，暫態結尾 0.25 µA）：

  | deck（`dcop/tt_025C_1v80/`） | ngspice 走的路 | I(VDD) | 與暫態不同的節點（> 0.5 VDD） |
  |---|---|---|---|
  | `dc3`：nodeset | 直接疊代失敗 → dynamic gmin stepping | 3.8 mA | 1776（bitcell 也翻） |
  | `dc4`：＋`itl1=2000 gminsteps=0 srcsteps=0` | → transient op | 1.76 µA | 505（`cs`、`we`、`sel`、data DFF 翻） |
  | `dc5_1e14`／`dc5_1e12`：＋`rshunt` | → transient op | 5.5／9.6 µA | 533／525 |
  | `two`：用 `ic_rail` 的 DC 解當 nodeset | → transient op | 7.2 µA | 505 |
  | `ic_all`／`ic_rail`：`.ic` 固定 6233／5192 個節點（`tran` 不加 uic） | 直接收斂 | 1.41 mA | — |

  `.ic` 固定時 µV 級的差經強驅動器放大成 mA。dummy row cell 的節點 1–4 只接兩顆關閉的 NMOS 的 drain，DC 值由次臨界漏電的比例決定，gmin stepping 後出現 4.8 V 這類不合理的值。
- 結論：ngspice 放掉 nodeset 後直接疊代不收斂（原因未查），退回的方法會改變鎖存器狀態，解不唯一。

### 長時間停住（2026-10-10，`leakdbg/longpark.py`、`longpark_scan.py`）

- ss −40°C 暫態結尾有 295 個節點低於 −50 mV（272 個 dummy row cell 內部節點、NAND 串聯中間節點，最低 −0.36 V），讀寫動作把它們耦合到地以下，靠接面漏電慢慢回升。
- 停住 10 個週期、步長上限 2 ns（280 秒）：停住 20 ns 之後與 100 ps 步長的正式波形差 0.5–1.7%（停住後 10–20 ns 內 −20% 到 −51%，大步長抓不到停住邊緣的尖峰）。修剪 deck 的漏電：100–120 ns 112 nW、140–160 ns 78 nW、200–300 ns 55 nW、300 ns 50 nW；最後 20 ns 前後半只差 1.6%，最後 200 ns 差 38%。
- 步長：停住後 100–150 ns 用到 2 ns 上限，之後中位數 250 ps；時間點呈「放大到 2 ns → 突然縮到約 8 ps → 再放大」（推測是 Newton 失敗後砍步長），停住後平均約 0.7 ns。停住 100 個週期（2.1 µs）的三組（2n／5n／100p）跑 30 分鐘都沒完，使用者改選絕對門檻後中止。
- tt 的舊資料（`leakdbg/fast/tt_025C_1v80_b2_p12.out`，停住 12 個週期）：修剪 deck 每 20 ns 0.417 → 0.463（150 ns）→ 0.540（250 ns）→ 0.566 µW（330 ns），**往上升**；正式量測窗 0.454 µW。

### 絕對門檻（ADR-0018 決定 14，2026-10-10）

- 5 個 PVT 正式量測窗（修剪 deck，100 ps）前後半：tt 448.1／459.5 nW（+2.5%）、ss 100°C 1239／1243（+0.3%）、ff −40°C 244.8／247.9（+1.2%）、ss −40°C 79.8／75.2（−6.0%）、ff 100°C 400.5／401.0 µW（+0.13%）。
- `power.unsettled()`：差 > 5% 時只放行下降 ≤ 10 nW。`make openram-power` 5 個 PVT PASS（沿用快取波形）。N20 加三個案例；植入「不看方向」與「沒有上限」兩種錯誤，N20 都 FAIL。

### gmin（ADR-0018 決定 15，2026-10-10，`leakdbg/gmin.py`）

- 單顆 bitcell 待機漏電（Q=0 與 Q=1 相同），pW：

  | PVT | gmin 1e-12（ngspice 預設） | 1e-13 | 1e-15 | 1e-16 | 1e-17 | 1e-18 |
  |---|---|---|---|---|---|---|
  | tt 25°C 1.80 V | 42.65 | 4.74 | 0.574 | 0.537 | 0.533 | 0.532 |
  | ss 100°C 1.60 V | 34.29 | 4.33 | 1.039 | 1.009 | 1.006 | 1.006 |
  | ff −40°C 1.95 V | 49.81 | 5.32 | 0.422 | 0.377 | 0.373 | 0.373 |
  | ss −40°C 1.60 V | 33.49 | 3.54 | 0.241 | 0.211 | 0.208 | 0.208 |
  | ff 100°C 1.95 V | 605.7 | 561.2 | 556.3 | 556.26 | 556.25 | 556.25 |

  1e-12 時漏電 ÷ VDD² 都是 13.1 pS（ff 100°C 除外），約 13 個反向偏壓接面 × 1 pS。單顆 deck 拉長到 200 ns 數值不變（不是沒穩定）。
- 修剪網表的 deck 也改 1e-15（5 個平行）：tt 449.5 nW（原 453.8，468 秒）、ss 100°C 1206.6（1241.2，305 秒）、ff 100°C 400.66 µW（400.73，259 秒）、ff −40°C 166.3 nW（246.3，1392 秒）、ss −40°C `doAnalyses: TRAN:  Timestep too small; time = 1.57627e-09, timestep = 1.25e-22: trouble with node "vwm3#branch"`。tt 的 1264 顆保留 bitcell 照單顆結果應少約 54 nW，實際少 4.3 nW（原因未查；這份 deck 的工作點也走了 dynamic gmin stepping）。
- 完整網表舊波形（無 bitcell `.ic`，`power/full/<pvt>/leak`）對快速量法（當時 gmin 預設）：ff 100°C 404.3 對 409.9 µW（+1.4%）；ff −40°C 0.760 對 0.999 µW（+31%）；ss −40°C 量測窗前後半差 166%（半穩態 bitcell），不能比。
- 處理：單顆 deck `gmin=1e-17`，再以 1e-18 跑 Q=0 核對（`power.cell_gmin_problem()`，差 > 1% FAIL），N21。`make openram-power` PASS（1 分鐘）、`make openram-lib`、view QA（`check_macro_views.py`，LEF／5 份 .lib／Verilog／SPICE／GDS）PASS、`make openram-check-lib` PASS。整顆漏電：tt 461.9 nW、ss 100°C 1256.4、ff −40°C 252.0、ss −40°C 80.7、ff 100°C 409.14 µW。
