# Phase 6 文件核對（獨立審查，2026-10-11）

審查範圍：HEAD `e19ef5a`，結案證據 = commit `4713c5f` 的兩個乾淨 worktree（`arvinsa-rtl-gds-p6final_h3`、`arvinsa-rtl-gds-p6final_pico`）。只讀，沒有改 repo 檔案。

## 結論

核對 44 列說法（每列常含好幾個數字）：
- 23 列正確；
- 11 列錯誤（大多是 Phase 6 改了東西，文件沒有同步而過期）；
- 8 列說法不完整，不完整到會誤導；
- 2 列無法核對（證據檔已被覆蓋，或計算過程沒有存檔）。

結案證據本身成立：
- 兩輪 regression 都在乾淨 worktree、commit `4713c5f` 上跑（Hazard3 23/23、PicoRV32 28/28）。
- `4713c5f..e19ef5a` 之間只改了文件與 skill（8 個檔），沒有動到 flow 或 checker。
- 三次 harden 的 golden 都逐值相同。網表與 DEF 的 sha256 相同；GDS 把 BGNLIB／BGNSTR 的日期記錄清成零之後，sha256 也相同（我另外重算確認）。

最嚴重的兩個問題，都和功耗／IR 有關，而且都是「Phase 6 改變了前提，但文件沒有交代」：

1. **ADR-0018 的已知限制低估了 port 1 浮接造成的靜態電流**（port 1 沒有用到，它的 sense amp 輸入沒有電路驅動，sense amp 輸出反相器上下同時導通）：
   - 文件只寫 tt「約 0.2 mW、估計約 0.5 mW」。
   - `power.json` 的 ff 100°C 是 2.69 mW（時脈停住後），整段序列中最大 5.34 mW。這和 PicoRV32 整顆 SoC 的 9.47 mW 同一個數量級。
   - 這個電流不在 .lib 裡，所以 IR 最壞組合的檢查（`ir_worst.py`）與功耗數字都沒有算到它。
2. **golden README 與筆記把 `power__total` 的增加歸因錯了，而且沒有說明這個 metric 的意思**：
   - `power__total` 是最後寫入的 corner（max_ff_100C），不是 nominal。
   - PicoRV32 8.73 → 9.47 mW（+8.5%）的主因，是自產 SRAM 在 ff 100°C 的漏電：17.7 µW 變成 409 µW，多了 0.39 mW。internal power 只多 0.22 mW。
   - 在 nom_tt 只多 1.1%（6.93 → 7.00 mW）。
   - 另外，`ir_worst.py` 的「ff 電流」用的是 ff_n40C，但 Phase 6 之後 ff_100C 的總功耗比 ff_n40C 高 10–14%（Phase 5 時是 7–8%）。

其他問題多半是 Phase 6 改了東西，相關文件沒有同步，例如：
- `pnr/soc_top/README.md` 的容許規則清單沒有加上 licon.14；
- `ip/sram/char/README.md` 仍寫「STA 沒有 clk1 的 clock」；
- ADR-0018 已知限制仍寫 internal_power 用 13.8；
- 筆記 3c 對 .lib setup／hold 公式的描述與程式不符；
- golden README 的「可重現性」表沒有更新。

## 核對表

判斷欄：正確／錯誤／無法核對／說法不完整（不完整到會誤導）。路徑前綴：
- `H3` = `~/claude_prjs/arvinsa-rtl-gds-p6final_h3`
- `PICO` = `~/claude_prjs/arvinsa-rtl-gds-p6final_pico`
- `MAIN` = `~/claude_prjs/arvinsa-rtl-gds`

### A. 錯誤、說法不完整、無法核對

| # | 文件與行號 | 文件的說法 | 證據（檔案＋原文） | 判斷 | 建議修正 |
|---|---|---|---|---|---|
| A1 | `docs/decisions/0018-openram-self-generated-macro.md:129`（已知限制） | port 1 浮接的穿透電流「tt 約 0.2 mW（13/32 bit），32 bit 全部出現時估計約 0.5 mW」 | `ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/char/power.json`：`ff_100C_1v95 static_mw 2.6917`、`static_max_mw 5.3383`；`ff_n40C_1v95 0.2539／1.3422`；tt `0.0068／0.1879`。skill `openram-macro-characterization` 規則 25 也寫「ff 100°C 0.4 升到 2.7 mW」 | 說法不完整（主要數字低估約 10 倍） | 列出每個 PVT 的 `static_mw`／`static_max_mw`，標明 ff 100°C 最大 5.3 mW；說明 IR 與功耗都沒有算到這個電流，以及要不要處理（交由使用者決定） |
| A2 | `signoff/golden/soc_top/README.md`「與 Phase 5 golden 的差異」；`signoff/golden/soc_top_hazard3/README.md:22`；`docs/notes/openram_phase6_bringup.md` 步驟 4b 第三輪「功耗」 | power__total 8.73 → 9.47 mW（+8.5%：SRAM 的 internal power 換成實測值，clk1 也打時脈）；Hazard3 19.33 → 20.41（+5.6%，同原因） | `PICO/runs/soc_top/final/metrics.json` 的 `power__total` 0.0094733 = `57-openroad-stapostpnr/max_ff_100C_1v95/power.rpt` 的 Total 9.473327e-03（所以是 max_ff_100C）。Macro 一列：Phase 5（`arvinsa-rtl-gds-p5final_pico`）0.645 mW，其中漏電 1.77e-05；Phase 6 1.255 mW，其中漏電 4.091e-04。nom_tt Total 6.925 → 7.002 mW。Hazard3 nom_tt 15.33 → 15.68 mW | 說法不完整（歸因漏了主因，metric 容易誤讀） | 註明 `power__total` 是 max_ff_100C；拆成：SRAM 漏電 +0.39 mW（ff 100°C 409 µW）、SRAM internal +0.22 mW、standard cell +0.13 mW（Hazard3 +0.47）；並附上 nom_tt 的變化 |
| A3 | ADR-0018 `:127`（已知限制） | 「特性化範本改用預建 macro 的值 13.8；兩者都是解析值，IR drop 分析的 SRAM 電流仍不可信」 | 5 份 `char/*.lib` 的 internal_power 是量測值（例如 ss_n40C 10.01／6.52／9.51／4.38 pJ，ff_100C 15.99／19.23…），漏電等於 `power.json`；ADR-0018 決定 10–15 | 錯誤（已過期，和決定 10–15 矛盾） | 改寫為：範本的 13.8 只是過渡，交給 flow 的 .lib 是 SPICE 量測值；剩下的限制是 port 1 浮接電流（A1）與漏電不是穩態值 |
| A4 | `docs/notes/openram_phase6_bringup.md:267`（步驟 3c） | port 0 的延遲、setup／hold、最小週期、pulse width 的量測值「×1.6 都低於 ADR-0010 的下限（…setup／hold 1.0 ns），所以採用下限；量測值直接決定的是 dout0 的 hold 弧」 | `ip/sram/char/gen_char_lib.py:35-36,63,66`：setup／hold = `max(FLOOR, 量測值 + CONSTRAINT_ADD 0.10)`，不是 ×1.6；`FLOOR` 的 hold 是 0.5，不是 1.0。`…__ss_n40C_1v60.lib:147` 的 din0 hold_rising 是 0.6837（= 0.5837 + 0.10）；ss_100C 的 hold 有 0.5075–0.5387 | 錯誤（ss 兩個 PVT 的 hold 限制由量測值決定） | 改成：延遲、週期、pulse width 採用下限；setup 採用下限；hold 在 ss_100C、ss_n40C 由量測值 + 0.10 ns 決定，其他 PVT 採用下限 0.5 ns |
| A5 | 同上 `:265`（3c 表 ss −40°C 列） | setup／hold 最大「→ 0.40」 | `char/char.json` 的 `ss_n40C_1v60.constraints.din_hold_rise.pass = 0.5837`（csb 0.5637、addr 0.5525…） | 錯誤 | 改成 0.58 |
| A6 | 筆記步驟 4b 第三輪（`:403`） | 「比預建少的只有 `Can't overlap those layers` 161」 | 新、舊 `signoff/waivers/soc_top/sram_magic_drc_baseline.json` 逐規則比較：新檔少了 `Can't overlap` 這一種；另外 18 種比預建少；3 種比預建多：diff/tap.1 366384 對 366254、licon.5a 354395 對 354135、poly.2 59280 對 59215 | 錯誤 | 改成：「少了一種（Can't overlap，161）；3 種比預建多（+130、+260、+65），其他較少」 |
| A7 | `arvinsa-rtl-gds-flow.md:170`；ADR-0018 決定 6；`project-plan.md` §8 Phase 6 的 exit criteria「自產 macro DRC ≤ 預建 baseline」 | 「逐種類和已知 baseline 比較，不只比總數」 | `ip/sram/openram/macro_drc.py:11`：「PASS needs: no rule category missing from the baseline, and total <= baseline total」。`MAIN/runs/openram/arv_sram_2kbyte_1rw1r_32x512_8/macro_drc.json` 對 baseline：同樣 3 種規則的數量比預建多（+130、+260、+65） | 說法不完整（容易被讀成「每一種都 ≤」） | 寫明 checker 只比「有沒有多出新的規則種類」與總數；exit review 列出這 3 種規則的數量比預建多 |
| A8 | `signoff/golden/soc_top/README.md:76-90`、`soc_top_hazard3/README.md:64-79`（可重現性） | 第一列「Phase 5 …（commit `1dee974`）\| 本檔來源」，其餘列都是和 Phase 5 golden 比 | 出處表寫明本檔來源是 `ad184f5`（第三輪）。沒有 `940e395`（4b 確認 harden）與 `4713c5f`（4d）的列 | 錯誤（表格過期） | 把舊列移到「下列為 Phase 5 golden 的紀錄」；新增 `ad184f5` 本檔來源、`940e395` 441／435 個逐值相同、`4713c5f` 乾淨 worktree 逐值相同 |
| A9 | 兩份 golden README「與 Phase 5 golden 的差異（逐項檢視過）」 | 列了 timing、功耗、cell、clock buffer，沒有提到 clock skew | 舊／新 golden `metrics.json`：Hazard3 `clock__skew__worst_hold__corner:nom_ss_n40C_1v60` −1.214 → −1.540、`worst_setup` 同 corner 0.921 → 1.155；PicoRV32 −1.292 → −1.679、0.936 → 1.168；clock inverter 56 → 101（Hazard3）、49 → 87（PicoRV32） | 說法不完整 | 補上 skew 的變化（多了約 0.3–0.4 ns），推測的原因（`clk1` 成為 clock sink）標成推測 |
| A10 | `pnr/soc_top/README.md:11`（soc 專用 checker 一列） | `magic_drc`「只有 li.5 與 diff/tap.9 容許 0.1 µm」 | `pnr/soc_top/check_soc.py:176` 的 `DRC_POS_TOL_RULES = ("(li.5)", "(diff/tap.9)", "(licon.14)")`；`H3/runs/soc_top_hazard3_signoff/soc_checks.txt`「100 nm wider for (li.5) (diff/tap.9) (licon.14)」 | 錯誤（已過期） | 加上 licon.14（ADR-0018 決定 17，195 個框長 60–90 nm） |
| A11 | `pnr/soc_top/README.md:110-112`（已知限制 1、2） | 「SRAM 的時序數字是工程假設（ADR-0007）」；SRAM 單獨 5,579,161、soc_top 內 4,665,810、30 種規則 | Phase 3.5 起是特性化 .lib；Phase 6：`soc_checks.txt`「SRAM alone: 5576010 violations in 29 rule types」、框內 4770846 | 錯誤（已過期） | 更新為 Phase 6 的數字與 .lib 來源，或註明數字屬於哪一個 Phase |
| A12 | `ip/sram/char/README.md:74` | 「port 1：SoC 裡 tie-off，STA 沒有 clk1 的 clock，沿用 PDK 的解析數字」 | ADR-0018 決定 9；`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/README.md:36`「`clk1` 接了時脈，STA 會用這些數字檢查它」；`gen_char_lib.py` 檔頭說明已改 | 錯誤（和同一 Phase 的另兩處矛盾） | 分成預建 macro（tie-off）與自產 macro（`clk1` 打時脈，STA 用範本的解析數字）兩種情況寫 |
| A13 | `arvinsa-rtl-gds-flow.md:172` | `check_char_lib.py`「預建 macro 由 `harden-soc` 開頭的 `check_inputs.py` 執行，自產 macro 用 `make openram-check-lib`」 | `H3/runs/soc_top_hazard3_signoff/inputs.txt`「[PASS] char_values: check_char_lib.py PASS (values recomputed independently, provenance, confirmation simulations)」，用的是自產 macro | 錯誤 | 改成：兩種 macro 都由 harden 前的 `check_inputs.py` 執行；`openram-check-lib` 是產生 .lib 後的單獨檢查 |
| A14 | ADR-0018 決定 17「結果（2026-10-10，patch 0001–0004，51 分鐘）：OpenRAM DRC 0、LVS…；Magic full …PASS；KLayout 0」 | 這次重新產生的結果全部 PASS | `MAIN/runs/p6_openram_macro_fix2.log`：`check_macro_views: FAIL … internal_power 1.036316e+11`、`make: *** [openram-macro] Error 1`、`rc=2`（51:12）。`macro_klayout_drc.json`（17:14）、`views.json`（17:20，檢查的是範本）是事後另外跑的 | 說法不完整（筆記有提到，ADR 沒有） | 註明那 51 分鐘的 `make openram-macro` 本身 FAIL（view QA）；KLayout 與範本 QA 是之後單獨跑的；改過的 `make openram-macro` 還沒有完整跑通一次 |
| A15 | 筆記步驟 4b 第一輪（`:374`） | 「golden 152／88 列不同」 | `MAIN/runs/p6_4b_harden_pico.log`「golden 438 metrics: run=254 identical, 32 within tolerance, 3 optional…, 149 different」「signoff: FAIL (152 rows)」；Hazard3「85 different」「signoff: FAIL (88 rows)」 | 錯誤（152／88 是 signoff 的 FAIL 總列數） | 改成「signoff FAIL 152／88 列，其中 golden 不同 149／85」 |
| A16 | ADR-0018 `:128`（已知限制） | 「`words_per_row = 1` 的形狀與時序未知，可能放不進現在的 floorplan」 | 決定 7：wpr1 已量過，446.99 × 1152.58 µm，放不進 die | 錯誤（已過期） | 刪除，或改成「已量：放不進，沒有採用」 |
| A17 | `.claude/skills/hard-macro-integration/SKILL.md` 經驗紀錄（2026-10-10 第一輪）；`signoff-checker-qualification` 經驗紀錄 | 證據 `runs/soc_top.prev`，commit `3ceca55`（SRAM 是空的那一輪；加 50% 下限後 FAIL） | `MAIN/runs/soc_top_signoff.prev/provenance.txt`「repo_head: ad184f5…」：`.prev` 已被第三輪覆蓋（`keep_prev_run` 只留一層）。第一輪只剩 `runs/p6_4b_harden_{pico,h3}.log`，裡面是 `magic_drc … inside 0` PASS，沒有加下限後重判 FAIL 的紀錄 | 無法核對（證據已被覆蓋） | 證據改指 log；「加下限後 FAIL」若有存檔要補上路徑，沒有的話要寫明證據已不存在 |
| A18 | ADR-0018 決定 17；skill `drc-signoff` 規則 2 | licon.14 可能藏住新違規的面積：SRAM 的 0.65% → 3.32%（li.5 1.29%、diff/tap.9 8.71%） | repo 與 `runs/` 都找不到這個計算的程式或輸出 | 無法核對 | 把計算腳本與輸出存檔（例如 `runs/` 或 `docs/notes`），文件附上路徑 |
| A19 | `docs/notes/openram_phase6_bringup.md:270`；todo 3e | `make neg-char` 16/16（2026-10-09） | `MAIN/runs/sram_char/neg_char_20261010.log`「neg-char: PASS 21/21」（10-10 12:36），只寫在 commit `1a28c50` 的訊息裡；之後 `ad184f5` 改了 `ip/sram/char/check_char_lib.py`（來源檢查改用內容雜湊），沒有再跑 `neg-char`。`neg-char` 不在 regression 裡，乾淨 worktree 沒跑過 | 說法不完整 | 文件補上 21/21 的時間與 log；說明 `check_char_lib.py` 改過之後只有 `neg-openram` C1–C5 涵蓋（它在 regression 裡），`neg-char` 本身沒有重跑 |
| A20 | 筆記 3c `:267`「ss 100°C 的最早變化比預建早 0.6 ns，接收端的 hold 餘量會變少，步驟 4a 的 STA 要看」 | 之後的步驟沒有追蹤結果 | 我量了 4d 的 run，`57-openroad-stapostpnr/min_ss_100C_1v60/min.rpt` 中 `sram0` 出發的最差 hold：PicoRV32 +1.656 ns、Hazard3 +1.674 ns；ff 兩個 corner 是 +0.361 至 +0.389 | 說法不完整（沒有結案；實測沒問題） | 在 4b 或 exit review 補一句結果 |
| A21 | `H3…/criteria_review.md:13`、`PICO…/soc_top_signoff/criteria_review.md:13` | 「和 golden run（`runs/soc_top_hazard3`，4b）相同」 | `MAIN/runs/soc_top_hazard3_signoff/provenance.txt` repo_head `940e395`（4b 確認 harden），golden 來源是 `ad184f5`（現在在 `.prev`）。三者的網表 sha256 都是 `43bc964f…`（PicoRV32 `7df82512…`） | 說法不完整（結論對，指錯 run） | 改成「4b 確認 harden（`940e395`）與 golden 來源（`ad184f5`）」 |

### B. 正確（有原文對得上）

| # | 文件 | 文件的說法 | 證據 | 判斷 |
|---|---|---|---|---|
| B1 | 筆記 4d、ADR 決定 18、`flow-regression-reproducibility` 經驗紀錄 | 4713c5f，Hazard3 23/23、PicoRV32 28/28，依序跑，沒有重試 | `H3/runs/regress/summary.md`、`PICO/runs/regress_picorv32/summary.md`；`MAIN/runs/p6final_summary.txt`（00:14–05:06，152＋135 分鐘）。註：summary.md 寫 153 min，摘要與文件寫 152（四捨五入的差別） | 正確 |
| B2 | 同上 | 結案證據不是開發目錄的結果 | worktree 的 `provenance.txt` repo_head `4713c5f`；`git diff --stat 4713c5f e19ef5a` 只有 8 個文件／skill 檔 | 正確 |
| B3 | 筆記 4d | golden：Hazard3 441、PicoRV32 435、core 325 個全部逐值相同 | 三份 `signoff.txt`「golden … identical, 0 within tolerance … 0 different」 | 正確 |
| B4 | 筆記 4d、criteria_review、`flow-regression-reproducibility` | 網表、DEF 的 sha256 相同；GDS 清除 BGNLIB／BGNSTR 後相同 | 我重算：網表 `43bc964f`／`7df82512`／`dec6e9f9` 相同；清除日期後 GDS 都是 `081662c4…`（Hazard3）、`717e6974…`（PicoRV32） | 正確 |
| B5 | `signoff/limits/soc_top.toml`、`soc_top_hazard3.toml` 的註解 | 144 = 102 CTS 假負載 + 32 `dout1` + 10 tie 空端（9 LO＋1 HI）；152 = 109 + 32 + 11；15 個 corner 相同 | worktree `57-openroad-stapostpnr/*/checks.rpt` 分類：clkload 102／109、dout1 32、tie 10／11（`sram0_8007/LO`＝csb1）；15 個 corner 的清單 md5 相同 | 正確 |
| B6 | golden README Phase 6 差異 | setup +0.789→+0.769、+1.114→+0.656；hold +0.080→+0.082、+0.109→+0.126；IR 2.03→2.09、5.02→5.23；cell 31,966→32,070、30,423→30,406；clock buffer 508→521、445→454；antenna 120→140、108→99；面積、utilization；Magic DRC 4,746,079→4,770,846；metric 數與 253/181、256/180 | 舊（`git show ccd0a49:…`）與新 `metrics.json` 逐項比較 | 正確 |
| B7 | 筆記 4b 第三輪、criteria review | `ir_worst` PicoRV32 5.87、Hazard3 14.74 mV | worktree `ir_worst.txt`「VDD 2.93 + GND 2.93 = 5.87」「7.41 + 7.33 = 14.74」 | 正確 |
| B8 | knowledge S23 | 最壞組合約是 nom_tt 的 1.4 倍 | Phase 6：14.74／10.41 = 1.42、5.87／4.17 = 1.41 | 正確 |
| B9 | 筆記 4c／4d、ADR 決定 18、`formal-equivalence-eqy` | EQY 16222／18156／15137 全部證明；pin swap 是 `_10787_` A↔B、`_10793_` A1↔A2；`o21ai_swap` 位置；交叉檢查 170／78／126；neg-eqy 14／10／12 | worktree `eqy-soc.log`「2 cell(s) with swapped equivalent inputs … _10787_.A, _10787_.B, _10793_.A1, _10793_.A2」；`neg-eqy-*.log` 的對應列 | 正確 |
| B10 | 筆記 4c／4d | `neg-pnr` 71/71，P05 拿掉 8 個 via 後 LVS FAIL | 兩份 `neg-pnr.log`「P05: FAIL at Checker.LVS: LVS errors found (8 vias removed)」 | 正確 |
| B11 | 筆記 4b 第一輪、`hard-macro-integration` | XOR 5,691,003／5,690,757；unannotated 148／151；SRAM 單獨 5,576,033、31 種；空的 SRAM 時 `magic_drc` 框內 0 個仍 PASS；KLayout、LVS 是 0 | `MAIN/runs/p6_4b_harden_{pico,h3}.log` | 正確 |
| B12 | 筆記 4b 第二輪、ADR 決定 17 | KLayout 27；licon.14 有 195 個框；位置在 SRAM 內 y = 157.255 µm；Hazard3 setup +0.643 | `p6_4b_harden2_*.log`「195 not at the position…」「at (439.28, 510.855)」；510.855 − 353.6 = 157.255；「timing__setup__ws: run=0.6431797」 | 正確 |
| B13 | 筆記 4b 第三輪、golden README | golden 134／100 列；SRAM 參考檔 5,576,010、29 種 | `runs/p6_3m_*_signoff/signoff.txt`「133 different＋1 optional」、「99 different＋…」，soc_checks | 正確 |
| B14 | ADR 決定 17、SRAM README | patch 0001–0004；OpenRAM DRC 0、LVS match；repo 的 `.sp` 是 `368c74be…`，靠內容雜湊對上 `summary.json` | `openram/summary.json`；`shasum` 結果；`inputs.txt`「macro_source … SPICE: same subcircuits, other order/comments」 | 正確 |
| B15 | ADR 決定 17、knowledge S27 | Magic full 2,234,528／29 種，對預建 2,235,078／30 種；每種只差幾百 | `macro_drc.json`；逐規則差距 −325 到 +260 | 正確（「≤」的意思見 A7） |
| B16 | ADR 決定 15、knowledge S28 | 整顆漏電 tt 462 nW、ss 100°C 1256、ff −40°C 252、ss −40°C 81 nW、ff 100°C 409.1 µW；舊值的倍數 2.4／1.4／4／7；單顆 bitcell 0.53／1.01／0.37／0.21／556 pW | `power.json` 與 5 份 .lib 的 `cell_leakage_power` | 正確 |
| B17 | 筆記 3c | 確認模擬：5 個 PVT、115 條 lane、25 次模擬全部 PASS；5 個 PVT 的 settle_max、depart_min、最小週期 | `confirm.json`、`char.json` | 正確（ss −40°C 的 setup／hold 那一格除外，見 A5） |
| B18 | SRAM README、ADR-0006 補充、pnr README | LEF 59 支輸入腳位的 antenna 資料 0.6／0.222 µm²；`FOREIGN`；DBU 1000；694.27 × 428.415；(290.72, 353.6)；第 620 個 site、第 126 條 row；右緣 984.99、上緣 782.015 | flow 用的 LEF；`config.json`；計算 | 正確 |
| B19 | 三份 `criteria_review.md` | 設定 42／41／13 個生效；78／77 個 step 設定；路徑數 50,670／30,000／18,000；hold 差距、hold buffer 2,783／3,589／2,230；面積 +13.5／+16.5／+13.1 %；skew −0.438／−1.290、−0.479／−1.429 | 各自的 `criteria_review.txt` | 正確 |
| B20 | Hazard3 `criteria_review.md:12` | 4c 只改 EQY 與 neg-pnr 腳本，沒有動 flow 設定 | `git diff --stat 940e395 4713c5f`：Makefile 只改 help 文字 | 正確 |
| B21 | core `criteria_review.md:12` | 和 Phase 5 結案那次完全相同 | 兩份 `criteria_review.txt` 去掉路徑後相同；網表、DEF 的 sha256 相同 | 正確 |
| B22 | 筆記 4a、`hard-macro-integration` | soc-checks：`port1_tieoff` 的 `clk1` 追到 `clk`、`sta_setup` 沒有警告、`sram_lib` 15 個 corner、`macro_gds` 169 個 cell | worktree `soc_checks.txt` | 正確 |
| B23 | README skill 一節 | 21 個 skill 的格式與索引 | `python3 scripts/check_skills.py`「PASS 21 skills」 | 正確 |

## 前一階段帶過來、或 Phase 6 應重新量的項目

| # | 項目（來源） | Phase 6 文件怎麼說 | 實際證據 | 判斷 |
|---|---|---|---|---|
| 1 | SRAM 在低溫、ss 室溫讀取失敗（Phase 3.5 限制 1，Phase 5 限制 2；頭號下線風險） | ADR-0018 決定 7–9：patch 0001 加上 `clk1` 打時脈 | 筆記 3p2 的表：7 個條件都讀對（含 ss 25°C 1.60 V、tt −40°C 1.60 V）；`char.json` 5 個 PVT 讀寫正確；`confirm.json` 115/115 | 已處理。限制：只在電路圖（沒有版圖寄生）、週期 20 ns 下判定（Phase 3.5 限制 15 仍在），exit review 要寫明 |
| 2 | ss_n40C 用佔位 .lib（ADR-0013） | 5 個 PVT 都有量測的 .lib | `sram_lib: 15 corners, each read only the char .lib of its PVT`；.lib 檔頭沒有 PLACEHOLDER | 已處理 |
| 3 | Phase 3.5 限制 2–7、13–15（特性化方法的限制：寄生、萃取網表、dout0 transition、Monte Carlo、只在 bit 0／31 量、修剪、只在 tt 驗證誤差、hold 弧與週期、dout0 最小負載） | ADR-0018 與筆記沒有逐項交代。只有 SRAM README 提到「公式與預建相同」，ADR 已知限制寫「公式與下限沿用 ADR-0010」 | Phase 3.5 限制 3 明寫「Phase 6 用 OpenRAM 環境確認」（萃取網表），Phase 6 沒有紀錄（ADR 查證 8 只引用上游 issue #281）。dout0 transition 仍是 0.5 ns（`gen_char_lib.py:65`） | **文件沒有交代**。exit review 要逐項寫：哪些沿用、哪些因為換了 macro 要重量（例如萃取網表、最小負載）、哪些沒做 |
| 4 | `neg-char` 不在 regression 裡（Phase 3.5 限制 9，Phase 5 限制 10） | 沒有提到 | 21/21 只在主 checkout 跑過（10-10），之後 `check_char_lib.py` 又改過（見 A19） | 沒變，要照舊列為限制，並補上最新一次執行的紀錄 |
| 5 | IR 最壞組合（Phase 5 限制 3，ADR-0017） | 重新量：5.87／14.74 mV，PASS | (a) `ir_worst.py:34` 固定 `CORNER = "max_ff_n40C_1v95"`。Phase 6 的 power.rpt：PicoRV32 max_ff_100C 9.47 對 max_ff_n40C 8.28 mW（+14%），Hazard3 20.41 對 18.58（+10%）；Phase 5 時是 +8%／+7%。SRAM 這個 macro 在 ff_100C 是 1.255 mW、ff_n40C 是 0.744 mW。(b) port 1 浮接電流不在 .lib：ff_100C 2.69–5.34 mW、ff_n40C 0.25–1.34 mW，而且集中在 SRAM，SRAM 離左側供電點最遠 | **前提改變，沒有重新量**。推測（粗略按總功耗線性放大，沒有考慮電流的位置）：Hazard3 用 ff_100C 的電流約 16.2 mV；再加 2.7 mW 約 18.3 mV；加 5.3 mW 約 20.4 mV，超過 20 mV。建議列成選項讓使用者決定：用 ff_100C 重跑 `ir_worst`、在 SRAM 位置加上電流源模擬浮接電流，或寫進已知限制 |
| 6 | 時序餘量 | golden README：Hazard3 最差 setup +1.114 → +0.656 ns（SRAM 半週期讀出） | 有寫。但 skew 多了 0.3–0.4 ns（A9）沒有寫；DCD 2.2 ns 仍是假設（Phase 5 限制 1，Phase 7 處理） | 部分交代 |
| 7 | ADR-0016 留下的「PicoRV32 SRAM 輸入腳的 hold 變緊」（Phase 5 限制 7） | 沒有提到 | 我量了 4d 的 run，進入 `sram0` 的最差 hold：PicoRV32 min_ff_n40C +0.090 ns（Phase 5 是 +0.093）；Hazard3 +0.284 | 沒變，文件沒有重新寫；exit review 要更新數字 |
| 8 | 接收 SRAM dout0 的 hold（筆記 3c：ss 100°C 最早變化提早 0.6 ns） | 只寫「步驟 4a 的 STA 要看」 | min_ss_100C 從 `sram0` 出發的最差 hold +1.656／+1.674 ns | 實際沒問題，但沒有結案紀錄（A20） |
| 9 | .lib 的 corner 涵蓋 | 5 個 PVT 都量了；port 1 用範本的解析數字 | `sram_lib` PASS。`clk1` 現在打時脈，5 份 .lib 裡 port 1 的弧與 pulse width 都是 TT 範本的解析值，STA 會用它們；`pulse_width` 的輸出只列 `sram0/clk0` | SRAM README 有交代；char README 矛盾（A12）。`clk1` 的 pulse width 有沒有被檢查，我沒有核對 |
| 10 | antenna（ADR-0008） | antenna LEF 用新的網表重新產生；signoff antenna 0 | flow 用的 LEF 有 59 個 `ANTENNAGATEAREA`；兩個 run 的 antenna 違規都是 0；`DRT-0418` 25 行的根因是推測，已標明 | 已處理 |
| 11 | LVS 把 SRAM 當 black box（Phase 4 限制 8） | 新增 `macro_gds` 與框內 DRC 下限 | soc_checks `macro_gds` 169 個 cell 相同 | 改善，black box 本身沒變 |
| 12 | EQY 的 SRAM clock 檢查（Phase 4 加的） | 步驟 4a–4c 之間被悄悄略過，已修 | `eqy-soc.log` 的 clock pin 2154／2641（含 SRAM 兩支） | 已處理，也有寫 |
| 13 | 功耗（Phase 5 限制 11「Hazard3 功耗兩倍的原因沒有分析」） | 只寫 power__total 的變化 | 見 A2；SRAM 功耗現在分 PVT（Phase 5 每個 corner 都是 0.645 mW） | 誤讀風險，見 A2 |
| 14 | Phase 4／5 其他限制（DCD、供電位置、GRT-0229、golden 只在同一台機器、`flop_async_reset` 範圍等） | 沒有提到 | 這次沒有變 | 預期沿用，exit review 照舊列出即可 |

## 方法備註

- 數字一律從證據檔取原文：`signoff.txt`、`soc_checks.txt`、`ir_worst.txt`、`criteria_review.txt`、`metrics.json`、`57-openroad-stapostpnr/*/{checks,min,power}.rpt`、`char.json`、`confirm.json`、`power.json`、`summary.json`、`macro_drc.json`、regression log。
- 自己做的小計算：
  - GDS 清除日期記錄後的 sha256（腳本 `gdshash.py`，放在本報告同目錄）；
  - golden 新舊逐項比較（`cmp.py`）；
  - unannotated 驅動端的分類；
  - SRAM 出發與進入的 hold slack（從 `min.rpt` 每個 corner 的前 1000／1689 條路徑取）。
- 沒有跑 LibreLane、EQY、模擬。A1／項目 5 的 IR 估算是粗略推測，沒有實際模擬。
