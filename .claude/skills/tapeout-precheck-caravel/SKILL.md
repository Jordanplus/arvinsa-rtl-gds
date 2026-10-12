---
name: tapeout-precheck-caravel
description: 把設計放進 ChipFoundry Caravel 的 user_project_wrapper（2920 × 3520 µm，固定 DEF 範本 `FP_DEF_TEMPLATE`），或要跑 ChipFoundry 收件前的自動檢查（precheck、`cf precheck`、`cf-precheck`、`mpw_precheck`）時使用：precheck 一定用 Docker 跑只有 linux/amd64 的官方 image（Apple Silicon 要用 colima＋Rosetta 模擬），容器每次都 `pip install --upgrade cf-precheck`；precheck 自帶的 KLayout deck 比 flow 用的新，flow 的 KLayout DRC 是 0 不代表 precheck 的 `klayout_feol`／`klayout_beol` 會過；pad 與 wrapper 腳位固定，先定 block 位置再挑最近的 GPIO（0–14 右緣、15–23 上緣、24–37 左緣，Wishbone 在下緣左段）；OpenRAM bitcell（包括 PDK 預建的 `sky130_sram_*`）在新 deck 報 `MR_mcon.CON.10`（mcon should covered by li）與 `MR_licon.SP.6`，因為 2026-05 拿掉了 `areaid.ce` 的豁免；LVS 是 transistor-level，SRAM 要用 `EXTRACT_ABSTRACT` 當 black box；`gpio_defines` 範本全是 `GPIO_MODE_INVALID`、`oeb` 檢查實體接線；XOR 要求 die 外那圈與官方空 wrapper 相同；`lvs_config.json` 路徑要以 `$PDK_ROOT`／`$UPRJ_ROOT` 開頭；`wb_clk_i` 是管理用 CPU 的核心時脈（外部時脈或 PLL 除頻），設計的週期就是管理端時脈的下限，邊界約束用官方 wrapper SDC 的數值。Use for ChipFoundry Caravel user_project_wrapper integration and cf-precheck (docker amd64 image, KLayout deck newer than the flow's, OpenRAM bitcell MR_mcon.CON.10, LVS black box, GPIO/OEB checks).
---

# Caravel 整合與 ChipFoundry precheck

macro 本身的整合（view QA、LEF、`FOREIGN`）看 `hard-macro-integration`；DRC 的一般判讀看 `drc-signoff`；LVS 的一般做法看 `lvs-signoff`；floorplan 看 `floorplan-congestion`。本 repo 實例：ADR-0019、`docs/notes/caravel_precheck_phase7.md`（Phase 7 進行中）。

名詞：
- **Caravel**：ChipFoundry（2025 年接手 Efabless 的 sky130 共乘下線）的載具晶片。pad、電源與一顆管理用的 RISC-V 都做好了，使用者的設計放在 `user_project_wrapper` 裡。
- **precheck**：ChipFoundry 收件前的自動檢查。現在是 pip 套件 `cf-precheck`，由 `cf` 指令（pip 套件 `chipfoundry-cli`）用 Docker 呼叫。
- **扁平放法**：CPU 的 standard cell 與 SRAM macro 直接放在 wrapper 層繞線，不先把 SoC harden 成 macro（`project-plan.md` §5.5）。官方範例都是先 harden 成 macro。

## 規則（已驗證）

1. **precheck 的判定只認官方 image 的結果，並記下實際版本**。
   - `cf precheck` 沒有 Docker 就停止；image 是 `chipfoundry/mpw_precheck:latest`，只有 linux/amd64（cf-cli `main.py` 第 4887、4893、4916 行；Docker Hub 2026-10-12）。Apple Silicon 要用模擬（colima `--vm-type vz --vz-rosetta`）。
   - 容器每次先 `pip install --upgrade cf-precheck`，同一個 image 不同天跑，版本可能不同。每次記下 image digest 與 cf-precheck 版本。
   - image 的工具版本（Magic 8.3.471、KLayout 0.29.12、Netgen 1.5.272、PDK open_pdks `3e0e31dc`）和 flow 的不同；本機用 flow 的工具跑出來的結果只能加快修 bug，不能當判定。
2. **flow 的 KLayout DRC 是 0，不代表 precheck 的 KLayout DRC 會過**：precheck 用自帶的 `drc_scripts/sky130A_mr.drc`（2026-10 時是 release `2026.03.30_01.00`），flow 用 PDK 的 deck（`8afc834` 是 `2024.2.11_01.09`），規則名稱與內容都不同。每一顆 macro 交給 wrapper 之前，先用 precheck 的 deck 單獨跑 `feol`／`beol`／`offgrid`（參數照 `checks/klayout_drc.py`：`input`、`topcell`＝GDS 檔名、`report`、`thr`），幾十秒就有結果。
   - 先讀過 deck 再執行：它是第三方的 Ruby 腳本。
3. **OpenRAM bitcell 在新 deck 的兩條規則**（工具缺陷的防護，CLAUDE.md 規則 10）：
   - **症狀**：`klayout_beol` 報 `MR_mcon.CON.10 : mcon should covered by li`、`klayout_feol` 報 `MR_licon.SP.6 : poly_licon minimum space to psdm`，位置在 `sky130_fd_bd_sram__openram_dp_cell*` 與 `*_replica_column*`。PDK 預建的 `sky130_sram_2kbyte_1rw1r_32x512_8` 與 OpenRAM 自產的 macro 一樣，BEOL 264、FEOL 3（依 cell 計）。
   - **怎麼發現**：precheck 的 `outputs/reports/klayout_{feol,beol}_check.xml` 的 `<category>` 與 `<cell>`；或規則 2 的 macro 單獨檢查。
   - **原因**：cf-precheck commit `08f559e30a`（2026-05-07）把 `mconnotace.not(li)`（不檢查 SRAM 核心區 `areaid.ce`，81/2）改成 `mcon.not(li)`；`MR_licon.SP.6` 是新規則。`$sram_exclude` 只管 nsdm／psdm，而且只認 `sky130_sram_*` 名稱，關不掉這兩條。
   - **怎麼繞過**：沒有能讓官方結果 PASS 的設定。本 repo 的判定（ADR-0019 決定 5）：這兩項只允許這兩條規則，每一個違規都在 SRAM 外框內，而且 PDK 預建 macro 單獨檢查時同一個 cell、同一個相對位置也有；並向 ChipFoundry 反映。
   - **防復發**：比對 checker 與 negative test 在 Phase 7 實作時加（還沒有自動防護）。deck 升版時重跑規則 2 的兩顆對照。
4. **SRAM 的 LVS 用 black box**：precheck 的 LVS 是 Magic 萃取到電晶體層級加 Netgen。ChipFoundry 的 PDK `3e0e31dc` 對 bitcell 的元件命名和 `8afc834` 相同（`special_pfet_latch`、`special_nfet_01v8`），OpenRAM 的網表（2022 PDK 的命名）對不上。在 `lvs/user_project_wrapper/lvs_config.json` 的 `EXTRACT_ABSTRACT` 加入 SRAM 的 cell 名稱，ChipFoundry 自己的 `caravel_user_sram` 範例也這樣做。代價：SRAM 內部不檢查，要靠 view QA 與 `check_macro_gds.py`。

5. **先定 block 位置，再選 GPIO**（使用者 2026-10-12：「block擺放位置應該在後段開始前就應該先確認之後出pin決定好」）。Caravel 的 pad 與 wrapper 腳位位置都固定（`xor` 檢查 die 外那圈），能選的只有用哪幾支 GPIO、接什麼訊號、什麼模式，訊號也可以改走 logic analyzer 或 Wishbone。順序：
   - 依有時序要求的介面定 block 位置：Wishbone（含 `wb_clk_i`、`wb_rst_i`）與 logic analyzer 在下緣左段 x = 0–870 µm；
   - 再依範本 DEF 的座標挑最近的 GPIO：0–14 在右緣（0–4 系統保留），15–23 在上緣，24–37 在左緣由上往下，37 在 y = 162 µm；
   - 最後才寫 wrapper RTL 的腳位對應與 `user_defines.v`。
   - 規劃文件、使用者核准、checker 與 hook 的做法在 `chip-floorplan-pin-planning`（ADR-0019 決定 13）。
6. **`wb_clk_i` 是管理用 CPU 的核心時脈**：Caravel `verilog/rtl/caravel_clocking.v` 第 93–94 行，開機時是外部時脈 `ext_clk`（duty 由板子的振盪器決定），firmware 啟用 PLL 後是 `clock_div` 除頻的輸出（設計成 50% duty；除數 0 時直通 PLL）。所以：
   - 設計用 `wb_clk_i` 時，設計的週期就是管理端時脈的下限，要寫成使用限制（測試 firmware、板子）。本 repo：44 ns，管理端不能超過 22.7 MHz（ADR-0019 決定 15）。
   - duty cycle 與 jitter 沒有官方數字，`clock_uncertainty.sdc` 的假設要記成下線風險。
   - wrapper 邊界的約束（clock source latency、Wishbone／LA delay、transition、負載）用 caravel_user_project 的 wrapper SDC 數值，做法與 OpenSTA 的 driving cell 陷阱看 `timing-constraints-sdc` 規則 14、15。
   - Phase 7 先在 RTL 選了 GPIO 8–20，到 floorplan 才發現離 block 2–3 mm，RTL、`user_defines.v`、testbench 與文件都要重做（ADR-0019 決定 10）。

## 待確認（讀過原始碼，還沒實跑）

- `xor`：die（0–2920 × 0–3520 µm）外那一圈要和 caravel-lite 的空 wrapper 一樣，所以要用 `FP_DEF_TEMPLATE`（`openlane/user_project_wrapper/fixed_dont_change/user_project_wrapper.def`），core ring（寬 3.1 µm、offset 12.45 µm）不能改。
- `gpio_defines`：`verilog/rtl/user_defines.v` 的 GPIO 5–37 都要有值、不能是 `GPIO_MODE_INVALID`；範本全是 INVALID。
- `oeb`：CVC 在萃取網表上追 `io_out`／`io_oeb` 的實際接線，和 GPIO 模式比；user output 模式要真的接 `io_out` 與 `io_oeb`。RTL 對了不代表 PASS。
- `lvs_config.json` 裡的路徑必須以 `$PDK_ROOT` 或 `$UPRJ_ROOT` 開頭（cf-precheck `config.py` 第 206–219 行）。
- `klayout_met_min_ca_density` 只有上限（li1–met4 ≤ 60%、met5 ≤ 76%）；SRAM 內部與電源區要量。
- `magic_drc` 是選用，預設不跑；只有 PDK 的 `sky130_sram_*` 會換成 maglef，自產 SRAM 用完整規則會 FAIL。下線時 ChipFoundry 怎麼看要另外問。
- 官方範例的 flow 是 LibreLane 2.4.6（ChipFoundry fork `CI2511`）；LibreLane 3.0.14 支援 `FP_DEF_TEMPLATE`，舊的 `FP_PDN_*` 名稱會自動轉換。

## 用完後

1. 新的現象加進「經驗紀錄」，根因標明已驗證／推測。
2. 「待確認」的項目實跑確認後搬進規則；同一現象出現兩次或用實驗確認才寫成規則（CLAUDE.md 規則 3）。
3. precheck 或 deck 升版時，逐條重看規則 3 的防護是否還成立（CLAUDE.md 規則 10）。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-12 | arvinsa-rtl-gds Phase 7 開始（查證） | precheck 的 deck 檢查 SRAM：自產 macro 與 PDK 預建 macro 都是 FEOL 3（`MR_licon.SP.6`）、BEOL 264（`MR_mcon.CON.10`）、offgrid 0；flow 的舊 deck 兩顆都是 0 | 已驗證：比對兩份 deck 與 cf-precheck commit `08f559e30a` 的 diff | ADR-0019 決定 5：這兩條比對預建 macro；向 ChipFoundry 反映的草稿由使用者決定是否送出 | `docs/notes/caravel_precheck_phase7.md` 第 7 節 |
| 2026-10-12 | arvinsa-rtl-gds Phase 7 步驟 3–4 | 寫 wrapper RTL 時先選 GPIO 8–20（沒看位置），到 floorplan 才發現在右緣與上緣，離左下角的 block 2–3 mm；我原本用「慢速訊號加 buffer 就好」帶過 | 已驗證（範本 DEF 座標）；流程順序錯誤，使用者指出 | 改成 GPIO 33–37（左緣最下面）、`gpio_out` 只走 LA；RTL、`user_defines.v`、testbench 重做，regress-rtl caravel 30/30、neg 42/42；寫成規則 5 | ADR-0019 決定 10、12 |
| 2026-10-12 | `p7_floorplan4`（扁平 wrapper，跑到 global placement） | `OpenROAD.GeneratePDN` 報 `[WARNING PDN-0239] Ring shape falls outside the die bounds.` | 已驗證：Caravel 的 core ring（4 組電源 × 2，寬 3.1 µm、offset 12.45 µm）本來就畫到 die 外，最外到 x = -43.63 µm；8 組 net 的 ring 座標與官方範例 `user_project_wrapper.def` 完全相同，官方範例的 precheck XOR 是 PASS | 預期中的警告，不處理；之後 harden 的 checker 可以比對 ring 與官方 DEF 一致（第 5、6 項） | ADR-0019；`runs/p7_floorplan4/21-openroad-generatepdn/` |
| 2026-10-12 | `p7_harden2`（wrapper 探索 harden） | 第 41 步 `RepairDesignPostGRT` 中止：`[ERROR RSZ-0074] failed to build tree from gloubal routes: found route to 1 pins, expected 0`，停在 `analog_io[9]` | 已驗證：沒接東西的 inout 腳位被 OpenROAD 同時算成 driver 和 load；官方範例沒開 `RUN_POST_GRT_DESIGN_REPAIR`，所以沒遇到 | `RSZ_DONT_TOUCH_RX` 設 `analog_io`；四項防護在 `librelane-run-debug` 已知陷阱 | `runs/p7_harden2/41-*` |
| 2026-10-12 | `p7_harden2` 第 38 步（hold 修完後的 STA） | tt corner 有 384 個 max slew 違規（soc_top 是 0）：`la_oenb`、`la_data_in` 各 128 支腳位、`wbs_adr_i`、`wbs_dat_i` 各 32 支，以及接在這兩組腳位上的第一顆 cell（64 個，多是 hold delay cell） | 已驗證：全部在 Caravel 直接驅動的 net 上，slew 是 Caravel SDC 給的 input transition（0.84–0.97 ns），超過本 repo 的上限 0.70／0.75 ns（ADR-0009）；官方範例的上限是 1.5 ns（`MAX_TRANSITION_CONSTRAINT`），所以不算違規。wrapper 內部修不掉 | 使用者決定「內部照舊，邊界另判」（ADR-0019 決定 16）：`check_soc.py max_slew` 只允許這些 pin，到 Caravel 的 transition + 0.05 ns；wrapper 的 `MAX_SLEW_VIOLATION_CORNERS` 改回預設；P80 | `runs/p7_harden2/38-*/checks.rpt` |
| 2026-10-12 | `p7_harden2`（wrapper 探索 harden）global routing 起的每一步 | `[WARNING GRT-0036] Pin io_oeb[0] is outside die area.`（and 1000 similar warnings） | 已驗證：固定範本 DEF 的腳位形狀一半在 die 外，例如 `io_oeb[0]` 在 x = 2921.2 µm、met3 從 −3.6 到 +3.6 µm，die 寬 2920 µm；官方設計就是這樣，precheck 的 `xor` 比的就是這圈 | 不用處理，不要為了消警告改腳位（會被 `xor` 抓） | `pnr/user_project_wrapper/fixed_dont_change/user_project_wrapper.def` |
| 2026-10-12 | `p7_harden2` 第 51 步 `Odb.ReportDisconnectedPins` | `Found 327 disconnected pin(s), of which 0 are critical.`；soc_top 是 0，`check_soc.py disconnected` FAIL | 已驗證：全部是 wrapper 最上層沒用到的 Caravel 腳位：`analog_io` 29、`io_in` 35（用到的只有 GPIO 33／34／36）、`la_data_in`／`la_oenb` 各 128、`user_clock2`，加上沒有 cell 用到的 6 支電源腳位（只有 vccd1／vssd1 有 cell）；沒有 cell 的 pin 浮接 | `disconnected` 改成 wrapper 判法（`DESIGNS unused_ports`）：表上必須剛好是「不是 Wishbone、也不是 `pin_plan.toml` 輸入模式 GPIO 的輸入／inout 腳位」加「沒有 cell 用的電源腳位」，只在頂層、0 個 critical。四種植入錯誤（用到的輸入、cell pin、應該沒接的腳位被接上、critical 1）手動確認都 FAIL；正式 negative test 等 `neg_pnr` 支援 wrapper（步驟 8） | `pnr/soc_top/check_soc.py` |
| 2026-10-12 | `p7_harden2`（wrapper 探索 harden，從第 41 步接續後跑完） | signoff 只剩 1 條 hold 違規：`wbs_adr_i[4]` → `_21509_`，`max_ff_100C` −0.071、`max_ff_n40C` −0.043 ns；post-GRT 的 hold 修復修完估計 +0.058 ns | 已驗證（STA 報表）：官方約束下 Caravel 輸入的 min input delay 0.79 ns 掛在 4.65 ns 的 latency，wrapper 暫存器在 5.57 ns 加內部約 2 ns 的 clock tree 取樣，ff 下資料要延遲約 2.4 ns；global routing 的估計對這條路徑樂觀約 0.1 ns。soc_top 沒有這類路徑 | `GRT_RESIZER_HOLD_SLACK_MARGIN` 0.2 ns（ADR-0019 決定 17）；試過把 ff_100C 加進 resizer 的 corner，`RepairDesignPostGRT` 壅塞失敗（`drv-timing-closure` 經驗紀錄）。驗證中（`p7_harden4`） | `runs/p7_harden2_out/attempt2_margin005/` |
