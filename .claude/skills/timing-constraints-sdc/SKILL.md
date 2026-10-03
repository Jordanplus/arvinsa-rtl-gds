---
name: timing-constraints-sdc
description: 撰寫或修改 SDC（時序約束：clock、IO delay、false path／multicycle、derate、max transition／fanout），區分 PnR 與 signoff 的約束，或檢查 STA 有沒有未受約束的路徑（unconstrained endpoints）時使用。Use for writing/reviewing SDC constraints, PnR vs signoff SDC, and unconstrained-path checks.
---

# 時序約束（SDC）

**SDC**（Synopsys Design Constraints）：告訴 STA 工具 clock、輸入輸出的時間要求與例外路徑的約束檔。修違規本身看 `drv-timing-closure`。本 repo 實例：`pnr/soc_top/pnr.sdc`、`signoff.sdc`、`sta_extra_corner.tcl`；LibreLane 的 `librelane/scripts/base.sdc`。

## 規則（已驗證）

1. **LibreLane 的 base.sdc 已經提供**：`create_clock`（`CLOCK_PORT`、`CLOCK_PERIOD`）、所有輸入／輸出的 `set_input_delay`／`set_output_delay`（週期 × `IO_DELAY_CONSTRAINT`%，預設 20%）、`set_max_fanout`／`set_max_transition`／`set_max_capacitance`、driving cell、輸出負載、clock uncertainty 與 transition、全域 derate（`TIME_DERATING_CONSTRAINT` 5%）、繞線後 propagated clock。
2. **改約束的方式**：新 SDC 先 `source $::env(SCRIPTS_DIR)/base.sdc`，再改需要的一兩項，避免重寫遺漏。`PNR_SDC_FILE` 給 PnR 各步驟（可以比簽核嚴），`SIGNOFF_SDC_FILE` 只給 `OpenROAD.STAPostPNR`。**設了 `PNR_SDC_FILE` 就一定要同時設 `SIGNOFF_SDC_FILE`**：沒設時 signoff STA 會改讀 `PNR_SDC_FILE`（`librelane/steps/openroad.py` 第 325 行 `_SDC_IN = PNR_SDC_FILE or FALLBACK_SDC`，STAPostPNR 只在有 SIGNOFF_SDC_FILE 時覆寫；實測 sta.log 讀的是 pnr.sdc），signoff 就變成用 PnR 的約束判定。
3. **驗證約束只改了想改的**：同一份版圖只重跑 STAPostPNR，比對 setup／hold worst slack 是否不變（soc_top：改 signoff max transition 後兩者完全不變）。
4. **macro 的 derate**：`STA_EXTRA_CORNER_TCL_FILE` 依 corner 名稱對 instance 設 `set_timing_derate`（instance 層級會覆蓋全域 derate），只在 STA 生效（ADR-0007）。
5. **未受約束的路徑**：LibreLane 的 STA 每個 corner 都跑 `check_setup -unconstrained_endpoints -no_clock -no_input_delay -loops ...`（`corner.tcl` 121–123 行），結果在 `checks.rpt`，但沒有變成 metric、也沒有 checker。soc_top 用 `check_soc.py sta_setup` 檢查：只允許已知例外（`sram0/clk1` 沒有 clock，port 1 接地）。
   - 沒有 `-no_output_delay`，但 `-unconstrained_endpoints` 會把「沒有參考 clock 的 output delay、也沒有 `set_max_delay`」的輸出 port 列出來（OpenSTA `search/CheckTiming.cc` `checkUnconstrainedOutputs`）。實測：SDC 少寫 `set_output_delay` 時報 `There are 42 unconstrained endpoints`。
6. **`unset_input_delay`／`unset_output_delay` 的陷阱**（OpenSTA）：
   - 不加 `-clock` 時只刪「沒有參考 clock」的 delay（`sdc/Sdc.tcl` `unset_port_delay`：`set clk "NULL"`），base.sdc 設的 delay 都有參考 clock，所以什麼都沒刪。
   - 加了 `-clock` 之後那些路徑不再被檢查（`report_checks` 為 `No paths found`），但 `check_setup` 仍當作 port 有 output delay，不報警告。也就是說，用 unset 拿掉約束時，STA 的完整性檢查看不出來。
7. **半週期路徑要算 duty cycle**：clock 下降緣送出、上升緣接收的路徑（soc_top 的 SRAM `dout0`）只有半個週期可用；STA 預設 50% duty，`set_clock_uncertainty` 的預設值不含 duty cycle 偏移。clock 來源確定後要把偏移算進約束，算法見 `signoff-criteria`。
8. **放寬簽核上限要使用者決定並寫 ADR**（ADR-0009）。
9. **LibreLane 預設哪些 corner 判 FAIL**：setup 只判 `*tt*`（`TIMING_VIOLATION_CORNERS`）；hold 判全部 corner（`checker.py` 第 683 行 `corner_override = ["*"]`）；max slew、max cap 預設都不判（661、672 行）。
10. **約束的數值怎麼定**（uncertainty 的成分、DCD、IO delay 與 source latency、derate、corner）看 `signoff-criteria`。幾個容易用錯的指令：
    - 指定邊緣的 `set_clock_uncertainty -fall_from ... -rise_to ...` 會取代一般的值，不是相加。
    - 不加 `-source` 的 `set_clock_latency` 會把 clock 變回 ideal。
    - `set_max_transition -clock_path` 在 propagated clock 下沒有作用。
    - 同名 clock 用 `create_clock` 重新定義之後，之前設的 inter-clock uncertainty 仍然有效。要改約束時，重新產生整份 SDC，不要逐行修補。

## negative test

P01／P02／P03（在 run 實際用的 signoff SDC 後面追加 uncertainty 或 max transition；直接改 config 變數會被後讀的 SDC 蓋掉）；P13（signoff SDC 把 base.sdc 展開後刪掉 `set_output_delay` 那一行 → check_setup 在 9 個 corner 報 42 個未受約束的輸出 → `sta_setup` FAIL；不用 unset 的原因見規則 6）。

## 待補

例外路徑（`set_false_path`、`set_multicycle_path`）的使用準則；非同步 reset 的處理；Phase 7 Caravel／Wishbone 介面的 IO 約束（clock 來自 Caravel 的 `wb_clk_i`／`user_clock2`，duty cycle 待查）。clock uncertainty、derate、IR／SI margin 這些數字怎麼決定，放在 `signoff-criteria`。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_top | check_setup：`There is 1 unclocked register/latch pin. sram0/clk1`（9 corner） | 已驗證：SRAM port 1 的 clock 接 0 | 列為唯一允許的例外 | `runs/soc_top/56-openroad-stapostpnr/*/checks.rpt` |
| 2026-10-03 | sdc075_10／11（單步重跑 STA） | `SIGNOFF_SDC_FILE` 設為空時 sta.log：`Reading design constraints file at .../pnr.sdc` | 已驗證：fallback 到 PNR_SDC_FILE | soc_top 的 `signoff.sdc` 明確等於 base.sdc | `runs/sdc075_10/out/max_ss_100C_1v60/sta.log` |
| 2026-10-03 | neg-pnr P13 | `unset_output_delay` 植入後 check_setup 沒有任何新警告 | 已驗證：見規則 6（OpenSTA 單步探針） | 改成產生少一行的 SDC | `runs/neg_pnr/P13/neg.sdc` |
| 2026-10-03 | soc_top 討論 clock 來源 | 最差 setup 路徑是 SRAM 下降緣 → 上升緣的半週期路徑（min_ss 剩 3.55 ns），0.25 ns uncertainty 不含 duty cycle | 已驗證（`max.rpt` 起點 `clock clk (fall edge)` 20 ns） | 規則 7；數字待 Phase 7 確定 clock 來源後再算 | `runs/soc_top/56-openroad-stapostpnr/min_ss_100C_1v60/max.rpt` |
| 2026-10-03 | signoff 條件調查（核對 agent 實驗） | inter-clock uncertainty 取代一般值（設 1.0 → slack 少 0.75）；`-clock_path` 在 propagated clock 下 0 筆違規 | 已驗證（`sta` binary 單步實驗） | 規則 9、10 | `docs/notes/signoff_criteria_soc_top.md` |
