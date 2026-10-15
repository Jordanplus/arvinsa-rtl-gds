---
name: timing-constraints-sdc
description: 撰寫或修改 SDC（時序約束：clock、IO delay、false path／multicycle、derate、max transition／fanout），區分 PnR 與 signoff 的約束（`PNR_SDC_FILE`、`SIGNOFF_SDC_FILE`；signoff 的 sta.log 寫 `Reading design constraints file at .../pnr.sdc` 表示 `SIGNOFF_SDC_FILE` 沒設、改讀了 PnR 的 SDC）、讓兩份 SDC 共用同一組約束、確認約束真的生效（看 STA 報表的路徑分解，不看 SDC 有沒有被讀），或檢查未受約束的路徑（`check_setup` 報 `unconstrained endpoints`、`unclocked register/latch pin`）時使用；含 OpenSTA 容易用錯的指令（`unset_*_delay`、指定邊緣的 uncertainty、`set_clock_latency` 沒加 `-source`、設了 driving cell 的腳位 `set_input_transition` 不生效，報表腳位 slew 仍是 0.01–0.02 ns），以及放進外殼（Caravel wrapper）時用外殼抽出的邊界約束。數值怎麼定看 signoff-criteria。Use for writing/reviewing SDC constraints, PnR vs signoff SDC, checking that constraints took effect, and unconstrained-path checks (OpenSTA/LibreLane).
---

# 時序約束（SDC）

**SDC**（Synopsys Design Constraints）：告訴 STA 工具 clock、輸入輸出的時間要求與例外路徑的約束檔。修違規本身看 `drv-timing-closure`。本 repo 實例：`pnr/soc_top/pnr.sdc`、`signoff.sdc`、`sta_extra_corner.tcl`；LibreLane 的 `librelane/scripts/base.sdc`。

## 規則（已驗證）

1. **LibreLane 的 base.sdc 已經提供**：`create_clock`（`CLOCK_PORT`、`CLOCK_PERIOD`）、所有輸入／輸出的 `set_input_delay`／`set_output_delay`（週期 × `IO_DELAY_CONSTRAINT`%，預設 20%）、`set_max_fanout`／`set_max_transition`／`set_max_capacitance`、driving cell、輸出負載、clock uncertainty 與 transition、全域 derate（`TIME_DERATING_CONSTRAINT` 5%）、繞線後 propagated clock。
2. **改約束的方式**：新 SDC 先 `source $::env(SCRIPTS_DIR)/base.sdc`，再改需要的一兩項，避免重寫遺漏。`PNR_SDC_FILE` 給 PnR 各步驟（可以比簽核嚴），`SIGNOFF_SDC_FILE` 只給 `OpenROAD.STAPostPNR`。**設了 `PNR_SDC_FILE` 就一定要同時設 `SIGNOFF_SDC_FILE`**：沒設時 signoff STA 會改讀 `PNR_SDC_FILE`（`librelane/steps/openroad.py` 第 325 行 `_SDC_IN = PNR_SDC_FILE or FALLBACK_SDC`，STAPostPNR 只在有 SIGNOFF_SDC_FILE 時覆寫；實測 sta.log 讀的是 pnr.sdc），signoff 就變成用 PnR 的約束判定。這是 LibreLane 設定靜默改變行為的一例（CLAUDE.md 規則 10）：
   - **症狀**：沒有錯誤或警告；signoff 的 max transition、fanout 等於 PnR 的值（本 repo 是 0.70 ns、fanout 8，而不是 0.75 ns、10）。
   - **怎麼發現**：`runs/<tag>/resolved.json` 的 `SIGNOFF_SDC_FILE` 是 null；`*-openroad-stapostpnr/<corner>/sta.log` 的 `Reading design constraints file at ...` 那一行指向 PnR 的 SDC（經驗紀錄 2026-10-03）。`review_criteria.py` 的 INFO 列只印兩份 SDC 檔裡直接寫的 `set_max_transition`，分不出 `SIGNOFF_SDC_FILE` 沒設：只 source `base.sdc` 的 signoff SDC 平常也印 not set。
   - **怎麼繞過**：設了 `PNR_SDC_FILE` 就同時設 `SIGNOFF_SDC_FILE`，signoff 要用 base.sdc 原樣時也明確指一份只 source `base.sdc` 的檔（本 repo 的 soc_top 與 wrapper 都設了）。
   - **防復發：沒有自動防護**。`review_criteria.py` 只印 INFO，不判（470–475 行）；「設了 `PNR_SDC_FILE` 就要有 `SIGNOFF_SDC_FILE`」的 checker 需要新寫，依 ADR-0021 決定 3 留到下一個專案開始時做（ADR-0020 決定 2 的做法）。LibreLane 升版時重看 `openroad.py` 的這段 fallback。
3. **驗證約束只改了想改的**：同一份版圖只重跑 STAPostPNR，比對 setup／hold worst slack 是否不變（soc_top：改 signoff max transition 後兩者完全不變）。
4. **macro 的 derate**：`STA_EXTRA_CORNER_TCL_FILE` 依 corner 名稱對 instance 設 `set_timing_derate`（instance 層級會覆蓋全域 derate），只在 STA 生效（ADR-0007）。
5. **未受約束的路徑**：LibreLane 的 STA 每個 corner 都跑 `check_setup -unconstrained_endpoints -no_clock -no_input_delay -loops ...`（`corner.tcl` 121–123 行），結果在 `checks.rpt`，但沒有變成 metric、也沒有 checker。本 repo 用 `check_soc.py sta_setup` 在每個 signoff corner 檢查：soc_top 不允許任何警告；Caravel wrapper 只允許外殼範本的 29 支 `analog_io` 列為未受約束的 endpoint（沒接類比電路），而且警告與腳位都要剛好是這些（`check_soc.py` 開頭說明 53–58 行）。Phase 6 之前曾允許 `sram0/clk1` 沒有 clock（port 1 的 clock 接地），ADR-0018 決定 9 把 `clk1` 接到系統時脈之後拿掉了這個例外，不要再加回去。
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

11. **PnR 與 signoff 共用的約束放一個檔，兩份 SDC 都 source 它**（soc_top 的 `clock_uncertainty.sdc`）：`source [file join [file dirname [info script]] <檔名>]`；OpenSTA 的 `read_sdc` 下 `[info script]` 是 SDC 自己的路徑（實測）。SDC 在全域範圍執行，裡面設的變數 STA hook 也讀得到（`multicorner-sta` 規則 4）。
12. **`write_sdc` 會保留指定邊緣的 uncertainty**（`-fall_from ... -rise_to ... -setup`，實測），所以 PnR 後段讀的是寫回的 SDC 時仍有效。
13. **複製 SDC 做植入時要先把 `source` 展開**：`[info script]` 會變成複本所在的目錄，找不到被 source 的檔（`neg_pnr.py` 的 `flat_sdc()`）。改 clock 波形時編輯原本的 `create_clock` 那一行，不要在檔尾再定義一次同名 clock。

14. **設了 driving cell 的腳位，`set_input_transition` 不會生效**（OpenSTA 的行為；工具意外行為的防護，CLAUDE.md 規則 10）：
    - **症狀**：SDC 裡寫了 `set_input_transition -max 0.84`，`report_checks -fields {slew}` 在 `(in)` 那一行仍是 driving cell 推出來的 0.01–0.02 ns；sta.log 沒有任何警告。
    - **怎麼發現**：對每類輸入腳位 `report_checks -from [get_ports <p>] -path_delay max|min -fields {slew}`，看 `(in)` 那一行的 slew 是不是 SDC 的值。只看 SDC 有沒有被讀到不夠（規則 3、經驗紀錄 2026-10-08）。
    - **原因（實驗確認）**：同一份網表上，沒有 driving cell 時 slew = 設定值；先設 transition 再設 driving cell、或先 driving cell 再設 transition，都是 driving cell 的值；`set_drive 0` 不會清掉 driving cell。LibreLane 的 `base.sdc` 對時脈以外的所有輸入都設 `SYNTH_DRIVING_CELL`，所以 source `base.sdc` 之後再寫 `set_input_transition` 一律無效。
    - **怎麼繞過**：source `base.sdc` 時暫時把 `set_driving_cell` 換成空的 proc（`rename`），其餘約束照用；需要 driving cell 的腳位自己再設（`pnr/user_project_wrapper/caravel_base.sdc`）。不改 LibreLane 的 `base.sdc`。
    - **防復發**（部分）：`check_soc.py max_slew` 要求外部 transition 高於 slew 上限的腳位（Caravel 的 `la_oenb`、`la_data_in`、`wbs_adr_i`、`wbs_dat_i`），每個 bit 在每個 corner 都以違規出現，slew 等於 SDC 的值（±0.05 ns）；driving cell 蓋掉 transition 時這些腳位會從報表消失，FAIL（negative test `neg_pnr.py --cpu caravel` C80d；Phase 7 審查後加）。**低於上限的腳位（`wb_clk_i` 0.61、`io_in` 0.38 ns 等）不在 `checks.rpt` 裡，沒有自動防護**：改 SDC 後照上面「怎麼發現」手動查。OpenSTA 或 LibreLane 升版時重做一次對照實驗。
15. **放進外殼（Caravel wrapper）時，邊界約束用外殼抽出的數值**：clock source latency（外殼的 clock tree 到 wrapper 腳位）、clock 腳位 transition、每組介面腳位的 input／output delay 與 input transition、輸出負載（Caravel：caravel_user_project 的 `openlane/user_project_wrapper/signoff.sdc`，get_cup_sdc.py 產生）。只取數值，例外路徑（multicycle）要確認自己的電路在第一個 cycle 不取樣才能用；本 repo 不用（ADR-0019 決定 14）。外殼沒給數值、但會接到電路的腳位（Caravel 的 GPIO），保留 `base.sdc` 的 delay，不要留成未受約束；不接的腳位（`analog_io`）在未受約束的檢查裡列為例外。外殼給的 input transition 可能超過自己的 max transition（Caravel 的 `la_oenb` 0.97 ns 等）：數值照用，不要為了過 slew 檢查改小；判法見 `signoff-criteria` 的「max slew（外殼的邊界 net）」（ADR-0019 決定 16）。
16. **約束有沒有生效，看 STA 報表的路徑分解，不看 SDC 有沒有被讀**（已驗證，出現兩次：2026-10-08 Phase 5 exit 獨立審查的 uncertainty，2026-10-12 Phase 7 的 input transition；經驗紀錄）
    - 為什麼：SDC 印出的那一行或 sta.log 讀到檔案，不能證明後面沒有別的指令蓋掉它，也不能證明工具沒有靜默忽略它（規則 14）。數值剛好等於工具預設時更看不出來（soc_top 的 setup／hold uncertainty 0.25 ns 等於 LibreLane 的 `CLOCK_UNCERTAINTY_CONSTRAINT` 預設）。
    - 做法：改了約束，就在報表裡找它應該出現的地方逐條核對：uncertainty 看每條路徑的 `clock uncertainty`／`inter-clock uncertainty` 那一列（半週期路徑寫成 `inter-clock uncertainty`），input transition 看 `(in)` 那一行的 slew，derate 看 cell 延遲是否乘上去。
    - 防復發：`review_criteria.py uncertainty_applied` 解析每個 corner 的 `max.rpt`／`min.rpt`，逐條路徑比對 clock 邊緣與 uncertainty 的值（negative test `neg_pnr.py` P56：只把最差半週期路徑的 uncertainty 改回 0.25 ns 就 FAIL）；input transition 見規則 14 的防復發與它的缺口。其他種類的約束沒有逐條核對的 checker，靠上面的做法手動查。

## negative test

P01／P02／P03（在 run 實際用的 signoff SDC 後面追加 uncertainty 或 max transition；直接改 config 變數會被後讀的 SDC 蓋掉）；P13（signoff SDC 展開後刪掉 `set_output_delay` 那一行 → check_setup 在每個 corner 報 42 個未受約束的輸出 → `check_soc.py` 的 `sta_setup` 是唯一 FAIL 的列；不用 unset 的原因見規則 6）；P22／P23（clock 波形 {0 10}、週期 29 ns → `pulse_width` FAIL）；P24／P25（duty cycle 60%、duty 預算改 60% → setup FAIL，最差路徑從 sram0 下降緣送出）。

## 待補

例外路徑（`set_false_path`、`set_multicycle_path`）的使用準則；非同步 reset 的處理；Caravel 的 PLL jitter 與實際 duty cycle 有量測資料後，替換 `clock_uncertainty.sdc` 開頭的假設值（ADR-0019 決定 15 先維持假設）。clock uncertainty、derate、IR／SI margin 這些數字怎麼決定，放在 `signoff-criteria`。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | soc_top | check_setup：`There is 1 unclocked register/latch pin. sram0/clk1`（9 corner） | 已驗證：SRAM port 1 的 clock 接 0 | 當時列為唯一允許的例外；Phase 6 `clk1` 接系統時脈後拿掉（ADR-0018 決定 9，規則 5） | `runs/soc_top/56-openroad-stapostpnr/*/checks.rpt` |
| 2026-10-03 | sdc075_10／11（單步重跑 STA） | `SIGNOFF_SDC_FILE` 設為空時 sta.log：`Reading design constraints file at .../pnr.sdc` | 已驗證：fallback 到 PNR_SDC_FILE | soc_top 的 `signoff.sdc` 明確等於 base.sdc | `runs/sdc075_10/out/max_ss_100C_1v60/sta.log` |
| 2026-10-03 | neg-pnr P13 | `unset_output_delay` 植入後 check_setup 沒有任何新警告 | 已驗證：見規則 6（OpenSTA 單步探針） | 改成產生少一行的 SDC | `runs/neg_pnr/P13/neg.sdc` |
| 2026-10-03 | soc_top 討論 clock 來源 | 最差 setup 路徑是 SRAM 下降緣 → 上升緣的半週期路徑（min_ss 剩 3.55 ns），0.25 ns uncertainty 不含 duty cycle | 已驗證（`max.rpt` 起點 `clock clk (fall edge)` 20 ns） | 規則 7；數字待 Phase 7 確定 clock 來源後再算 | `runs/soc_top/56-openroad-stapostpnr/min_ss_100C_1v60/max.rpt` |
| 2026-10-03 | signoff 條件調查（核對 agent 實驗） | inter-clock uncertainty 取代一般值（設 1.0 → slack 少 0.75）；`-clock_path` 在 propagated clock 下 0 筆違規 | 已驗證（`sta` binary 單步實驗） | 規則 9、10 | `docs/notes/signoff_criteria_soc_top.md` |
| 2026-10-08 | Phase 5 exit 的獨立審查 | SDC 有沒有生效，要看 STA 報表的結果，不能看 SDC 有沒有被讀：`clock_uncertainty.sdc` 印出的那一行，不能證明後面沒有別的 `set_clock_uncertainty` 蓋掉它；setup／hold 的 0.25 又剛好等於 LibreLane 預設的 `CLOCK_UNCERTAINTY_CONSTRAINT` | 已驗證（刪掉報表的 uncertainty 後，舊檢查仍 PASS） | 由 `review_criteria.py uncertainty_applied` 逐條路徑核對（`multicorner-sta` 經驗紀錄）；半週期路徑的 uncertainty 在報表裡寫成 `inter-clock uncertainty` | `signoff/scripts/review_criteria.py` |
| 2026-10-12 | `p7_floorplan4` 網表＋OpenSTA 單獨實驗 | wrapper SDC 加了官方 Caravel 的 `set_input_transition`（`wbs_dat_i` 0.84 ns），報表 `wbs_dat_i[3] (in)` 的 slew 仍是 0.019 ns，log 沒有警告 | 已驗證（對照實驗：無 driving cell 0.840；transition 後設 driving cell 0.008；driving cell 後再設 transition 0.008；`set_drive 0` 不清除） | 規則 14：`caravel_base.sdc` 暫時停用 `set_driving_cell`；修正後每類輸入腳位 slew 都等於官方值，PnR 與 signoff 報表相同 | ADR-0019 決定 14；`pnr/user_project_wrapper/caravel_base.sdc` |
| 2026-10-12 | 同上 | 單獨跑 `sta` 時 `base.sdc` 印 `Setting input delay to: 8`（週期 44 × 20%） | 已驗證：我在腳本裡把 `CLOCK_PERIOD` 設成整數 `44`，Tcl 整數除法；LibreLane 傳浮點數，`soc_top` 的 signoff log 是 8.8 | 自己跑 STA 實驗時，環境變數的數值寫成浮點數（`44.0`） | `arvinsa-rtl-gds-p6final_h3/runs/soc_top_hazard3/57-openroad-stapostpnr/*/sta.log` |
