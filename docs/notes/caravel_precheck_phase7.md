# Phase 7 調查：ChipFoundry Caravel precheck（2026-10-12）

目的：Phase 7 只做到 precheck PASS、不下線，CPU 用 Hazard3，SoC 用扁平放法放進 `user_project_wrapper`（使用者 2026-10-12）。這份筆記記錄開工前的查證，決定寫在 ADR-0019。

調查方式：一個 subagent 唯讀 clone 下面四個 repo、讀原始碼（沒有執行 clone 下來的程式或 deck，沒有安裝軟體）；我抽查了第 1、3、5 項與 Docker Hub 的架構（標「已抽查」）。

| repo | commit | 日期 |
|---|---|---|
| github.com/chipfoundry/cf-precheck（pip 套件 `cf-precheck` 1.3.7） | `6c401ed5134a` | 2026-09-15 |
| github.com/chipfoundry/cf-cli（pip 套件 `chipfoundry-cli` 2.6.0，`cf` 指令） | `88025a8fe921` | 2026-09-14 |
| github.com/chipfoundry/caravel_user_project | `b510613cec36` | 2026-04-23 |
| github.com/chipfoundry/caravel_user_sram | `adf59a8fec3f` | 2026-09-25 |

## 1. `cf precheck` 一定用 Docker，image 只有 amd64（已抽查）

- `cf-cli` `chipfoundry_cli/main.py`：沒有 `docker` 就停止（第 4887 行）；image `chipfoundry/mpw_precheck:latest`（第 4893 行）；`docker pull`／`docker run` 都帶 `--platform linux/amd64`（第 4916、4947 行）。容器裡每次先 `pip3 install --upgrade cf-precheck`，所以實際版本是 PyPI 上最新的，執行時要有網路。
- Docker Hub（2026-10-12 查 `hub.docker.com/v2/repositories/chipfoundry/mpw_precheck/tags/latest`）：只有 `linux amd64`，壓縮後 1,802,793,544 bytes，更新於 2026-09-15。macOS arm64 只能用模擬（Rosetta 或 QEMU）。
- image 釘的版本（`dependencies/Dockerfile`）：Magic 8.3.471、KLayout 0.29.12、Netgen 1.5.272、CVC v1.1.7；PDK open_pdks `3e0e31dc`（ChipFoundry 的 fork：上游 2024-08 的 `0fe599b2` 加 3 個 decap cell commit）。本 repo：Magic 8.3.623、KLayout 0.30.7、Netgen 1.5.316、PDK `8afc834`（`toolchain.md`）。
- 也有 `cf precheck --remote`，交給 ChipFoundry 平台跑（要帳號、`cf link`、GDS 在 GitHub 的 commit 裡）；費用與條件原始碼看不出來。

## 2. 檢查項目（`src/cf_precheck/check_manager.py` 第 46–63 行，`build_sequence()` 第 66–93 行）

sky130A、`digital` 類型（`gds/user_project_wrapper.gds`）預設 13 項，全部要 PASS：

| 檢查 | 工具 | 內容 |
|---|---|---|
| `topcell_check` | KLayout `pya` | GDS 只有一個 top cell |
| `gpio_defines` | `pyverilog` | `verilog/rtl/user_defines.v` 的 GPIO 5–37 都有定義、不是 `GPIO_MODE_INVALID`（範本全是 INVALID） |
| `xor` | Magic＋KLayout＋ruby | die（0–2920 × 0–3520 µm）外那一圈和官方空 wrapper 的 XOR 為 0 |
| `klayout_feol`、`klayout_beol`、`klayout_offgrid` | KLayout，precheck 自帶的 `sky130A_mr.drc` | 違規數 0 |
| `klayout_met_min_ca_density` | KLayout | 只有密度上限：li1–met4 ≤ 60%、met5 ≤ 76% |
| `klayout_pin_label_purposes_overlapping_drawing`、`klayout_zeroarea`、`spike_check` | KLayout | pin／label 與 drawing 重疊、零面積圖形、自折的 path |
| `illegal_cellname_check` | KLayout `pya` | cell 名稱沒有 `#`、`/`（自產 macro 169 個 cell，0 個不合法） |
| `lvs` | Magic 萃取＋Netgen（CVC ERC 失敗只算警告） | wrapper 的 transistor-level LVS，設定在 `lvs/user_project_wrapper/lvs_config.json` |
| `oeb` | CVC＋gawk | 萃取網表上 `io_out`／`io_oeb` 的實際接線符合 `user_defines.v` 的 GPIO 模式 |

- `magic_drc` 是選用的（`--magic-drc` 才跑）。只有 PDK 的 `sky130_sram_*` 會先換成抽象視圖（maglef），自產 macro 整顆用完整規則檢查，約 220 萬個違規，加這個選項一定 FAIL。它不擋 precheck PASS；下線時 ChipFoundry 怎麼處理，原始碼看不出來（cf-cli 有 `drc_checks_waived` 這個狀態）。
- precheck 不檢查 README、info.yaml、模擬、時序。

## 3. KLayout deck 比 flow 用的新（已抽查）

- precheck：`drc_scripts/sky130A_mr.drc`，`release = "2026.03.30_01.00"`（第 40 行），歷史紀錄到 2026-03-17「fixed MR_mcon.CON.10」。
- LibreLane flow 用 PDK `8afc834` 的 deck，release `2024.2.11_01.09`。新 deck 多了最小面積（`MR_met*.AR.*`）、via 包覆、`MR_mcon.CON.10`（mcon 要被 li 蓋住）等規則。
- 依名稱排除 SRAM 的只有一處：`select("-*sky130_sram_*kbyte_*")`（第 317 行，`MR_nwell.ENC.1`）；`$sram_exclude` 預設 `false`（第 78–79 行），precheck 沒有傳。自產 macro（`arv_sram_*`、`sky130_fd_bd_sram__openram_*`）每一條規則都照常檢查。
- **自產 macro 用舊 deck 是 0 個違規，用新 deck 還沒跑過**：這是扁平計畫最可能卡住的地方。

## 4. LVS 與 SRAM

- ChipFoundry 的 PDK `3e0e31dc` 的 Magic tech 檔，元件命名和 `8afc834` 相同（已抽查：`special_pfet_latch` 3 處、`special_pfet_pass` 0、`special_nfet_01v8` 1；OpenRAM 用的 2022 版 `e8294524` 是 `special_pfet_pass` 3 處）。Phase 6 遇到的 OpenRAM cell LVS 不一致（`docs/notes/openram_phase6_bringup.md`）在 precheck 也會出現。
- 可行做法：`lvs_config.json` 的 `EXTRACT_ABSTRACT` 加入 SRAM，當 black box 只比腳位。這是 ChipFoundry 的 `caravel_user_sram` 範例的做法，也和本 repo SoC LVS 的做法相同（ADR-0018）。
- `lvs_config.json` 裡的路徑必須以 `$PDK_ROOT` 或 `$UPRJ_ROOT` 開頭（`config.py` 第 206–219 行）。

## 5. wrapper 規格

- `DIE_AREA [0, 0, 2920, 3520]`；腳位與 core ring 用固定的 DEF 範本 `openlane/user_project_wrapper/fixed_dont_change/user_project_wrapper.def`（`FP_DEF_TEMPLATE`），645 支腳位：訊號 met2（上下）／met3（左右），電源 met4／met5；core ring 寬 3.1 µm、offset 12.45 µm，不能改（XOR 會 FAIL）。
- 電源 net：`vccd1 vccd2 vdda1 vdda2`、`vssd1 vssd2 vssa1 vssa2`。
- 介面：Wishbone slave（`wb_clk_i`、`wb_rst_i`、`wbs_*`）、logic analyzer 128 × 3、`io_in/io_out/io_oeb[37:0]`、`analog_io[28:0]`、`user_clock2`、`user_irq[2:0]`。
- 官方範例的 flow 是 LibreLane 2.4.6（ChipFoundry fork tag `CI2511`），而且是「先 harden 成 macro 再放進 wrapper」，沒有扁平放法的範例。本 repo 的 LibreLane 3.0.14 支援 `FP_DEF_TEMPLATE`。
- precheck 需要的檔案：`gds/user_project_wrapper.gds`、`verilog/rtl/user_defines.v`、`lvs/user_project_wrapper/lvs_config.json`、`verilog/gl/user_project_wrapper.v`（powered）、golden 的 caravel-lite；用 `cf` 時還要 `.cf/project.json`。

## 6. 本機原生能跑多少

repo 的 LibreLane nix-shell 有 Magic、KLayout（含 `pya`）、Netgen、ruby、bash 5.3、iverilog；沒有 `cvc_rv`、GNU awk、GNU sed、`pyverilog`、`numpy`、`strsimpy`（2026-10-12）。`oeb` 要 CVC，`lvs` 的 shell script 用 GNU sed 的 `\n`。所以完整 precheck 不能原生跑；版本也和官方不同，原生結果只能加快修 bug，不能當判定。

## 7. 實驗：precheck 的 KLayout deck 檢查兩顆 SRAM（2026-10-12，使用者同意後執行）

做法：先讀過 deck（只用 KLayout DRC 語法，log 印到 stdout、報告寫到 `$report`，沒有外部指令、其他檔案或網路），再照 `checks/klayout_drc.py` 的參數（`input`、`topcell`＝GDS 檔名、`report`、`thr`，加 `feol`／`beol`／`offgrid=true`）用 repo 的 KLayout 0.30.7 跑。deck 的 sha256 開頭 `aeba6ab5137923f2`。

| macro | FEOL | BEOL | offgrid |
|---|---|---|---|
| 自產 `arv_sram_2kbyte_1rw1r_32x512_8` | 3（`MR_licon.SP.6`） | 264（`MR_mcon.CON.10`） | 0 |
| PDK 預建 `sky130_sram_2kbyte_1rw1r_32x512_8`（對照） | 3（`MR_licon.SP.6`） | 264（`MR_mcon.CON.10`） | 0 |

- 兩顆完全一樣。違規都在 OpenRAM 共用的 bitcell（`sky130_fd_bd_sram__openram_dp_cell`、`_replica`、`_dummy`）與 replica column（各 128 個）。KLayout 依 cell 回報，展開到全晶片的位置數會多很多。
- 根因（已驗證，比對兩份 deck）：
  - 舊 deck（PDK `8afc834`，release `2024.2.11_01.09`）第 936、975 行：`mconnotace = mcon.not(areaid_ce)`、`mconnotace.not(li).output("ct.4", ...)`，SRAM 核心區（`areaid.ce`，81/2）不檢查「mcon 要被 li 蓋住」。
  - 新 deck 第 1154 行：`mcon.not(li).output("MR_mcon.CON.10", ...)`，沒有排除 `areaid_ce`。這是刻意的：cf-precheck commit `08f559e30a`（2026-05-07）「Update the bundled sky130A DRC deck to the latest master release so MR_mcon.CON.10 violations are correctly detected」，diff 正是把 `mconnotace.not(li)` 改成 `mcon.not(li)`。
  - `MR_licon.SP.6`（poly 上的 licon 與 psdm 至少 0.11 µm，不可重疊，新 deck 第 939–943 行）在舊 deck 沒有。
- 影響：**任何用 OpenRAM bitcell 的 SRAM，包括 PDK 預建的那顆，在目前的 precheck 都過不了 `klayout_feol` 與 `klayout_beol`**。`$sram_exclude` 只管 nsdm／psdm，也只認 `sky130_sram_*` 的名稱，救不了這兩條。
- 相關 issue（2026-10-12 查）：cf-precheck #108（open，2026-04-20）「Expose sram_exclude flag」，留言指出 `sram_exclude=true` 對商用 SRAM 的違規數沒有影響；#51「Precheck crash with SRAM DRC」（open）；#119「Auto-abstract catalog hard macros for LVS」（open）。沒有找到針對 OpenRAM bitcell 與 `MR_mcon.CON.10` 的 issue。
