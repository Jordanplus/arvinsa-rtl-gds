# Phase 7 exit review 草稿：帶入的已知限制對照（2026-10-14）

用途：`phase-exit-review` 規則 1（`.claude/skills/phase-exit-review/SKILL.md` 第 12 行）要求逐條對照上一階段帶過來的已知限制，也包含更早階段還沒結的項目；寫「沒變」的項目，要在新設計上重新量過才算。
範圍：`docs/phase_exit/phase6.md`「已知限制（帶到後續階段）」第 1–9 項（第 199–219 行）。第 9 項展開成 Phase 5 已知限制 1、3–8、11（`docs/phase_exit/phase5.md` 第 272–299 行）、Phase 3.5 已知限制 5–7、13、14（`docs/phase_exit/phase3_5.md` 第 138–154 行），以及「LVS 中 SRAM 是 black box」。
Phase 7 的設計 = `user_project_wrapper`，正式 run 是 `550869c` 的確認 harden（`runs/user_project_wrapper_signoff/`，`provenance.txt` 記錄 HEAD `550869c`、working tree 乾淨；同一份 criteria review 另存在 `runs/p7_decap_confirm_signoff/`）。
這份草稿只讀檔案整理，沒有另外跑 STA 或 harden。

狀態的意思：
- **已解決**：Phase 7 處理掉了。
- **部分處理**：Phase 7 處理了一部分，剩下的部分寫在同一列。
- **沒變／已重新量過**：限制本身還在，但已經在 wrapper 的 run 上量過或確認過。
- **沒變／macro 本身**：這是 SRAM macro 本身的性質，跟 wrapper 怎麼擺放無關。Phase 7 用的是同一顆 macro：`git diff --stat 85bfa75 HEAD -- ip/sram` 沒有輸出；`soc_checks.txt` 的 `macro_gds` 列顯示 169 個 cell 與 macro GDS 相同，`sram_lib` 列顯示 15 個 corner 都只讀該 PVT 的 char .lib。所以這幾條沒有重新量，要不要接受這種「確認是同一顆 macro」的判斷，由主 agent 決定。
- **沒變／需要量**：wrapper 上還沒有數字。

## 表一：帶入項目（22 列）

| # | 原限制（一句話） | Phase 7 有沒有處理或影響 | 狀態 | 證據出處 |
|---|---|---|---|---|
| 6-1 | SRAM .lib 的時序沒有走線寄生，靠下限蓋住：`min_pulse_width` 下限 12 ns 對萃取的讀出時間（10.9 ns）只剩約 10%；dout0 transition 寫 0.5 ns，實際 1.4–2.2 ns | 決定 1 明確不做「用平面萃取網表重新特性化」（下線前才做）。pulse width 已在 wrapper 上量過：最差 slack 9.32 ns（`u_soc.sram0/clk0` low）。**dout0 transition 的 what-if 沒有在 wrapper 上重做**。wrapper 的 SRAM 半週期 setup 是 +0.548 ns，比 soc_top 的 +0.656 ns 少 0.108 ns，差距全部在 clock 端。Phase 6 的 what-if 把 transition 改成量到的值後，slack 掉了約 0.39 ns（+0.763 → +0.37）。照這個量估，wrapper 可能只剩約 +0.15 ns（**推測，沒量**） | 沒變／需要量（pulse width 已量） | ADR-0019 第 12 行；`runs/p7_decap_confirm_signoff/soc_checks.txt` `pulse_width` 列；`signoff/golden/user_project_wrapper/README.md`「主要數字」timing；ADR-0018 第 127 行；`runs/p7_skew_analysis/README.md` 第 5 行 |
| 6-2 | SRAM port 1 浮接的穿透電流不在 .lib 裡（ff 100°C 5.34 mW），flow 的功耗數字不含它 | IR 已經在 wrapper 上把它加進去：`ir_worst.py` 的 ff 100°C +5.338 mW、ss 100°C +0.151 mW；正式的 `ir-caravel` 也含 +0.151 mW。flow 的 `power__total` 18.19 mW 仍不含。晶片上這些節點的電壓仍然無法預測 | 沒變／已重新量過 | `runs/p7_decap_confirm_signoff/ir_worst.txt`；`runs/p7_formal2_ir.log` 第 40 行；golden README「功耗」 |
| 6-3 | .lib 的漏電不是穩態值，tt 25°C 可能偏低 26% 以上 | 沒有處理。wrapper 的 leakage 0.740 mW，而且另外不含 `ef_decap_12` 的漏電（它沒有 .lib，見表二 N13） | 沒變／macro 本身 | phase6.md 第 207 行；golden README「功耗」 |
| 6-4 | macro DRC 的面積容許 0.05%：接在既有違規上、又小於該規則總面積 0.05% 的新違規看不到 | 判法沿用。wrapper 上 SRAM 外 0 個；SRAM 框內 5,572,955 個，其中 5,567,755 個框與 SRAM 單獨檢查完全相同，5,200 個落在同規則框的聯集裡 | 沒變／已重新量過 | `soc_checks.txt` 的 `magic_drc`、`sram_drc_ref` 列 |
| 6-5 | clock skew 變大（ss −40°C 多約 0.2–0.4 ns，clock inverter 增加），推測是 `clk1` 成為新的 sink，沒有做實驗 | wrapper 的 hold skew metric 是 −3.598 ns（soc_top −1.540 ns），已有 agent 做唯讀分析：其中約 2.7 ns 是報表算法造成的（**推測**，沒讀 OpenSTA 原始碼）；真正多出來的是 `wb_clk_i` 到 clock root 約 910 µm、6 顆 buffer、1.8 ns。分析提出的建議都還沒實作。Phase 6 的「`clk1` 是原因」仍然沒有做實驗 | 部分處理 | `runs/p7_skew_analysis/README.md`；golden README「clock」（README 還寫「成因沒有查」，已經過期） |
| 6-6 | `DRT-0418 ... has no pins on routing grid`：SRAM 的 25 支腳位，根因沒查（推測是腳位沒對齊繞線格點） | wrapper 上同樣 25 次，全部在 `u_soc.sram0`（例如 `addr1[3]`）；最終 DRC、LVS 都是 0。根因仍然沒查 | 沒變／已重新量過 | `runs/user_project_wrapper/46-openroad-detailedrouting/openroad-detailedrouting.log`（`grep -c` = 25，非 sram0 = 0）；golden README |
| 6-7 | `neg-char`（特性化的 negative test）不在 regress 裡；`sram-extract` 也不在 | `regress-caravel` 的清單沒有 `neg-char`。Phase 7 沒有改 `ip/sram`，所以 Phase 6 結案時那次 22/22 仍然適用 | 沒變／已重新確認（輸入沒改） | `scripts/regress.py` 第 69–71 行；Makefile `neg-char`；phase6.md 第 117 行（`runs/p6close_negchar.console`） |
| 6-8 | OpenRAM 的已知問題：internal_power 數量級錯（#294）、LVS 失敗時 exit 0、1RW 產不出乾淨 layout | Phase 7 沒有重新產生 macro。另外，precheck 的新 deck 又找到 OpenRAM bitcell 的兩條規則（見表二 N1） | 沒變／macro 本身 | phase6.md 第 212–215 行；筆記第 7 節 |
| 5-1 | duty cycle 45/55%（DCD 2.2 ns）與 jitter 0.15 ns 是假設；Phase 7 確定 Caravel 的 clock 後要重算 | 決定 15：查了 Caravel 的時脈來源（開機時用外部時脈，之後是 PLL 經 `clock_div` 除頻），沒有找到官方的 duty 與 jitter 數字，所以**維持假設，記成下線風險**，並寫明使用限制：管理端時脈 ≤ 22.7 MHz。skew 分析估計 duty 在 sink 端失真約 0.57 ns（soc_top 0.28 ns，**推測**） | 部分處理 | ADR-0019 決定 15（第 64–66 行）；`pnr/soc_top/clock_uncertainty.sdc` 第 8–15 行；`runs/p7_skew_analysis/README.md` 第 5 行 |
| 5-3 | IR 的供電位置是假設（每條 met5 strap 左端一點）；EM 沒有 flow 檢查 | **供電位置已解決**：決定 18 用 Caravel 真實的 pad 模型（一顆 vccd1 pad、一顆 vssd1 pad、met4 ring、左右兩側的跨接線）；決定 19 改用慢 corner 判；決定 20 改用 max power pattern 的實際切換活動。`550869c` 的 `ir-caravel` 19.56 mV（上限 20 mV）；harden 內 `ir_worst.py` 4.94 mV。**EM 仍然沒有任何檢查**；ff corner 照跑只是印 INFO，沒有讀 EM | 部分處理（EM：沒變／需要量） | ADR-0019 決定 18–20；`runs/p7_formal2_ir.log` 第 44 行；`ir_worst.txt`；`.claude/skills/pdn-ir-drop/SKILL.md` 第 65–68 行 |
| 5-4 | 有些步驟不可重現：第 41 步 global routing 偶發不同、多執行緒 detailed routing 多插 diode、沒試過 `DRT_THREADS=1` | 在 wrapper 上量過兩組：`f721cff`→`f4ea9de` 455 個 metrics 逐值相同；`7eff65a`→`550869c` 455 個逐值相同；`p7_exp_pl_dens` 共有的 429 個也逐值相同。全部是同一台機器的 run。乾淨 checkout 的 `regress-caravel` 還在跑。`DRT_THREADS=1` 仍沒試 | 沒變／已重新量過 | golden README「可重現性」；ADR-0019 第 145、150、188 行；`runs/p7close_regress_caravel.console` |
| 5-5 | GRT-0229、GRT-0116 只用重試繞過，根因沒查 | wrapper 4 次正式 harden 都沒有觸發重試：`runs/*_signoff/` 沒有 `retries.txt`，log 也沒有 `attempts (known GRT`。`p7_harden3` 的 GRT-0116 是真正的壅塞（溢位 771），不在重試範圍內。根因沒變 | 沒變／已重新確認 | `pnr/librelane_flow.sh` 第 5–18、66 行；`pnr/soc_top/run.sh` 第 89 行；ADR-0019 第 76 行 |
| 5-6 | golden 誤差內的改變抓不到（standard cell 少於約 70 顆、slack 小於約 0.2 ns；繞線器各輪 DRC ±1310） | 決定 22：wrapper 的誤差**直接沿用 soc_top_hazard3 的**，還沒在 wrapper 上量。上限檔註明了這件事，校正排在步驟 8h。到目前為止，wrapper 所有的重跑都是 0 個落在誤差內 | 部分處理（待步驟 8h） | ADR-0019 決定 22（第 140–142 行）；`signoff/limits/user_project_wrapper.toml` 第 115–117 行；`runs/todo.md` 8h |
| 5-7 | ADR-0016 留下的項目：讀出 flip-flop 自己繞回自己的路徑還有 1 顆 hold delay cell、沒試 useful skew、PicoRV32 SRAM 輸入腳的 hold 變緊 | wrapper 上沒有量。只有間接數字：各輸入最差 hold 路徑上的 hold cell，wrapper 451 顆、soc_top 139 顆。PicoRV32 那一項跟 wrapper（Hazard3）無關；Phase 6 量的 Hazard3 是 +0.28 ns | 沒變／需要量 | phase5.md 第 288–291 行；`runs/p7_skew_analysis/README.md` 第 5 行；`runs/p6_extract_trial/sta_whatif/sram_hold.tcl` |
| 5-8 | RepairHold 全設計只用一種 hold buffer（`dlygate4sd3_1`，ss_n40C 的延遲約是 ff 的 3 倍） | 沒變。wrapper 的網表有 3,159 顆 `dlygate4sd3_1` 和 46 顆 `dlymetal6s2s_1`（後者推測不是 hold 修復插的，沒有查證）。Caravel 輸入路徑上已經有 5 顆 `dlygate4sd3_1`；決定 17 把 hold 餘量改成 0.2 ns，多插了延遲 cell | 沒變／已重新量過 | `runs/user_project_wrapper/final/nl/user_project_wrapper.nl.v`（數 cell 種類）；ADR-0019 決定 17（第 74、78 行） |
| 5-11 | 沒有分析的項目：Hazard3 功耗兩倍的原因、resizer 多修 buffer 的原因、四項設定變更沒有分開做實驗、2port／riscv-arch-test／formal | Phase 7 沒有分析這些。另外新增了一項沒分析的：`RSZ_CORNERS` 加 ff_100C 後 resizer 不放大 `a221oi_1`，原因沒找到（見表二 N6） | 沒變／需要量（分析項目） | phase5.md 第 295–299 行；ADR-0019 第 76 行 |
| 3.5-5 | 沒有 Monte Carlo、只在 bit 0／31 量時序、port 1 時序沿用解析值、沒有矽量測對照 | 沒有處理。`clk1` 仍然接系統時脈（`wb_clk_i`），STA 用的是 port 1 的解析值 | 沒變／macro 本身 | phase3_5.md 第 144 行；`soc_checks.txt` 的 `port1_tieoff` 列 |
| 3.5-6 | 修剪網表後的功能檢查偏悲觀（bit 1–30 的 bitline 只有 2 顆 bitcell） | 沒有處理 | 沒變／macro 本身 | phase3_5.md 第 145 行；phase6.md 第 114 行 |
| 3.5-7 | 模擬誤差只在 tt 驗證過 | 沒有處理 | 沒變／macro 本身 | phase3_5.md 第 146 行 |
| 3.5-13 | SRAM 的 hold 弧跟週期有關，只對 ≥ 20 ns 量過；43／44 ns 是照趨勢判斷安全，沒有直接模擬 | wrapper 的週期仍是 44 ns（決定 8），論證不變 | 沒變／已重新確認 | `pnr/user_project_wrapper/config.json` 第 55 行；ADR-0019 決定 8 |
| 3.5-14 | dout0 最小負載 3.35 fF 低於特性化範圍的 5 fF，STA 不會警告 | wrapper 上沒有量。wrapper 的 dout0 接 `buf_4` 和 `mux2_1`（CVC 報表），繞線也跟 soc_top 不同 | 沒變／需要量 | phase6.md 第 122 行；筆記第 10a 節；`runs/p6_extract_trial/sta_whatif/dout_load.tcl` |
| LVS | LVS 中 SRAM 是 black box | 決定 7：precheck 的 LVS 也把 SRAM 當 black box（ChipFoundry 自己的範例也這樣做）。正式結果 `Circuits match uniquely`；代價是 CVC 報 74 個 HI-Z 輸入，全部來自 SRAM 的 `dout0`。SRAM 內部由 view QA 和 `check_macro_gds.py` 負責（169 個 cell 相同） | 沒變／已重新確認 | ADR-0019 決定 7；筆記第 10a、10b 節；`soc_checks.txt` 的 `macro_gds` 列 |

統計：已解決 0；部分處理 4（6-5、5-1、5-3、5-6）；沒變／已重新量過或確認 9（6-2、6-4、6-6、6-7、5-4、5-5、5-8、3.5-13、LVS）；沒變／macro 本身 5（6-3、6-8、3.5-5、3.5-6、3.5-7）；沒變／需要量 4（6-1、5-7、5-11、3.5-14），另外 5-3 的 EM 部分也要量。

## 表二：Phase 7 新產生、應該帶到後續的限制候選

| # | 限制（一句話） | 出處 |
|---|---|---|
| N1 | 官方 precheck 的 `klayout_feol`／`klayout_beol` 結果仍是 FAIL（OpenRAM bitcell 違反 `MR_licon.SP.6`、`MR_mcon.CON.10`），PASS 是本 repo 依決定 5 判的：所有違規位置都要和 PDK 預建 macro 單獨檢查時一致。下線時 ChipFoundry 收不收，不知道 | ADR-0019 決定 5（第 24 行）；筆記第 7 節 |
| N2 | 向 ChipFoundry 反映的草稿由使用者決定要不要送；目前狀態沒有記錄 | ADR-0019 決定 6；`runs/todo.md` 1b |
| N3 | precheck 的判定 checker 只允許設計裡有一顆 OpenRAM SRAM（bitcell cell 沒有 macro 前綴）；有第二顆會 FAIL，不會誤判 PASS | 筆記第 9 節「限制」 |
| N4 | Magic DRC（precheck 的選用項目）沒有跑：自產 SRAM 用完整規則檢查約 220 萬個違規，加上這個選項一定 FAIL；下線時 ChipFoundry 怎麼看要另外問 | ADR-0019「後果」第 211 行；筆記第 2 節；skill 待確認第 69 行 |
| N5 | 本機與官方 image 的工具版本不同（Magic、KLayout、Netgen、PDK `8afc834` 對 `3e0e31dc`）；容器每次都 `pip install --upgrade cf-precheck`，換版本時 checker 會 FAIL，regress 也依賴 lima VM 和網路 | ADR-0019 決定 4、25，「後果」第 210 行 |
| N6 | resizer 沒有直接看 ff_100C，只靠 GRT hold 餘量 0.2 ns 蓋；`RSZ_CORNERS` 加 ff_100C 後 `RepairDesignPostGRT` 不放大 `a221oi_1`、改插長串 buffer，原因沒找到 | ADR-0019 決定 17（第 76、78 行） |
| N7 | 邊界 slew 另外判：Caravel 直接驅動的 net 可以到「外部 transition + 0.05 ns」（最高約 0.97 ns），每個 corner 385 個違規（15 個 corner 共 5,775 個）都在這類 net 上；內部 net 照舊 0.75 ns | ADR-0019 決定 16；`soc_checks.txt` `max_slew` 列 |
| N8 | `io_in`／`io_out`／`io_oeb` 的邊界時序是 `base.sdc` 的 20% delay 假設，不是 Caravel 的實際數值（官方是 `IO_SYNC = 0`，不約束）；沒有用 multicycle | ADR-0019 決定 14（第 61 行） |
| N9 | 使用限制：44 ns 的週期代表管理端時脈 ≤ 22.7 MHz；PLL 的 jitter 不知道；duty 與 jitter 是假設（跟表一 5-1 同源） | ADR-0019 決定 15（第 66 行）；skill 規則 6 |
| N10 | 使用限制：`host_en` 的 reset 值是 1，晶片上一定要由管理用韌體寫 0 才會放開 CPU；`gpio_out` 只走 LA，從晶片外看不到 | ADR-0019 決定 9（第 33 行）、決定 10（第 49 行） |
| N11 | pattern IR 19.56 mV，離上限 20 mV 只剩 0.44 mV；cell 分布一變就可能超過 | `runs/p7_formal2_ir.log` 第 44 行；`runs/todo.md` 5g |
| N12 | max power pattern 的限制：沒有包含 Wishbone 主機端的存取；零延遲的 gate-level 模擬不含 glitch 造成的切換；「最耗電」是三種 pattern 取最大，不是證明。板子在 pad 端最低 1.62 V 是假設，Caravel 穩壓器的精度沒查證 | ADR-0019 決定 20（第 114、116 行）、決定 18（第 95 行） |
| N13 | `ef_decap_12` 沒有 .lib，漏電不進功耗報告；li1 密度在 harden 時沒有自動檢查，要等 precheck（約 1 小時）才抓得到 | ADR-0019 決定 24（第 184 行）；skill 規則 8 防復發（第 60 行） |
| N14 | 把供電點直接放在 Caravel 跨接線的位置時，OpenROAD PSM 會 Signal 11，原因沒查，改放在 ring 與 strap 的交點 | ADR-0019 決定 18（第 94 行） |
| N15 | 密度改 50% 是繞過：繞線後的 ECO 在釘版 OpenROAD 做不到（`RSZ-0074`）；熱點那一欄的 met2 占用沒有重數 | ADR-0019 決定 21（第 128、138 行） |
| N16 | wrapper 的 golden 誤差還不是在 wrapper 上量的（同表一 5-6） | ADR-0019 決定 22；上限檔第 116 行 |
| N17 | EQY 的 amend 重試：只對組合邏輯驅動的輸入寫規則，被 amend 的分區有 flip-flop 就 FAIL；同一個分區（`_10122_.B`）每次都要靠重試才證得出來 | ADR-0019 決定 23；`runs/p7_formal2_eqy.log` |
| N18 | wrapper 的 negative test 只植入 wrapper 特有的判斷；共用的 checker 在 wrapper 上的特殊組合沒有逐一植入錯誤 | ADR-0019 決定 25（第 197 行） |
| N19 | CVC 的 HI-Z 警告沒有自動判定：cf-precheck 和 `make precheck-check` 都不讀它，SRAM 以外如果真的有浮接的輸入，也不會被抓到 | skill 規則 4（第 38 行）；筆記第 10a 節 |
| N20 | precheck 的幾項只看過 PASS，沒有用植入錯誤確認會 FAIL：`oeb` 接錯、`xor`、`gpio_defines` 違反時；met1–5 的密度上限從來沒接近過 | skill「待確認」第 66–68 行 |
| N21 | clock 的結構：`wb_clk_i` 到 root 約 910 µm、6 顆 buffer，wrapper 的 hold cell 比 soc_top 多出至少 312 顆在 Caravel 輸入路徑上；`review_criteria` 用 skew metric 當品質指標會誤導。三項建議都還沒實作（**推測成分**見分析） | `runs/p7_skew_analysis/README.md` 第 3–6 行 |
| N22 | pin 規劃的 hook 看不到用 Bash 改的檔案，只靠 `make pin-plan` 在 harden 與 regress 時擋 | ADR-0019 決定 13（第 57 行） |
| N23 | 扁平放法（SoC 的 cell 直接放在 wrapper 層）沒有官方範例可以對照；ChipFoundry 收件時會不會有額外要求，不知道（**推測**的風險） | ADR-0019 決定 2（第 15 行）；筆記第 5 節 |

## 表一之二：Phase 5 已知限制 12 的子項（Phase 6 第 9 項沒有逐條帶到）

來源：`docs/phase_exit/phase5.md` 第 300–304 行。Phase 6 的對照表只寫了「LVS black box 補了 view QA，其他沒變」（phase6.md 第 140 行）。LVS black box 已經在表一的「LVS」那一列，這裡不重複。編號 X1–X3 是我另外找到、看起來也沒有逐條帶下來的子項。

| # | 原限制（一句話） | Phase 7 有沒有處理或影響 | 狀態 | 證據出處 |
|---|---|---|---|---|
| 4-6 | EQY 的證明只涵蓋組合邏輯：flip-flop 的 cell 種類和 clock 接線由 EQY 以外的結構比對負責；RTL → 合成網表沒有 formal 證明 | 在 wrapper 上跑過：`eqy-caravel` 16149/16149；結構比對也確認 2238 個 flip-flop 種類相同、2240 個 clock pin 都追回同一個來源 `wb_clk_i`。RTL → 合成網表仍然沒有 formal，靠 gate-level 模擬（`gl-caravel` 16/16，每個 cycle 做 RTL／網表 lockstep 比對）。決定 23 另外加了 amend 重試，限制見 N17 | 沒變／已重新確認 | phase4.md 第 168 行；ADR-0019 第 152、190–191 行 |
| 4-7 | `counters` 測試抓不到計數器高半部「卡 0」（要跑 2^32 個 cycle） | 這是測試本身的缺口，跟擺放無關。wrapper 的 gate-level 模擬用同一套 firmware，沒有補 directed 測試 | 沒變（測試缺口，wrapper 上不用量） | phase4.md 第 169 行 |
| 4-9 | 下游步驟單獨執行時不檢查工作目錄是否乾淨（`run_guard.py` 只比 commit） | Phase 7 把 wrapper 的 5 個下游步驟加進 `neg_run_guard`（57 個案例），檢查的仍然只有 commit；`run_guard.py` 裡沒有檢查工作目錄的程式。`regress-caravel` 有開頭與結尾的檢查（`provenance-final`），不受影響 | 沒變／已重新確認 | phase4.md 第 171 行；ADR-0019 第 203 行；`scripts/regress.py` 第 69–71 行；`signoff/scripts/run_guard.py`（grep `dirty`／`clean`／`status` 沒有結果） |
| 4-10 | `make py-check` 只檢查同一個檔案裡的名稱，跨模組 import 的名稱改了要到執行時才會發現 | 沒變。Phase 7 新增的 Python（`ir_caravel.py`、`check_precheck.py`、`ir_pattern.py` 等）也在檢查範圍內，`regress-caravel` 的 py-check 91 個檔案 PASS | 沒變／已重新確認 | phase4.md 第 172 行；`scripts/check_py_names.py` 開頭的 docstring；`runs/p7close_regress_caravel.console` |
| 4-12 | 「第三人重現」只在同一台機器驗證過，CPU 核心數不同時，多執行緒繞線可能超出 golden 誤差（推測） | wrapper 所有的 run，包括乾淨 worktree 的 `regress-caravel`，都在同一台 Mac 上跑；precheck 的 VM 也在同一台。**需要量**：在另一台機器，或用 GitHub Actions 的 x86 runner（決定 4 的備案）跑一次 `make harden-caravel`，再跟 golden 比對 | 沒變／需要量 | phase4.md 第 174 行；golden README「出處」（Apple Silicon macOS） |
| 金屬密度 | 金屬密度沒有 checker，實測低於下限：met1–4 35%、met5 45%（Phase 3 實測 met1 25.8% … met5 2.6%），chip-level 一定要補 metal fill | **有新資料**：precheck 的 `klayout_met_min_ca_density` **只查上限**（li1–met4 ≤ 60%、met5 ≤ 76%），而且 PASS。用 precheck log 的 ca 值換算（覆蓋率 = 1 − ca，跟 li1 39.9% 的算法相同），整個 wrapper 的覆蓋率是 li1 39.9%、met1 18.1%、met2 1.6%、met3 0.8%、met4 26.7%、met5 27.3%，都低於 Phase 3 寫的下限。repo 裡沒有下限的 checker；下線時 ChipFoundry 會不會幫忙補 fill，沒查（**推測**：要問） | 沒變／已重新量過（仍低於下限） | phase3.md 第 164 行；`../arvinsa-rtl-gds-p7precheck/formal_550869c/precheck_results/14_OCT_2026___06_40_55/logs/klayout_met_min_ca_density_check.log`（`m1_ca_density is 0.819` 等）；筆記第 2 節 |
| flop_async_reset | neg-eqy 的位置範圍在大扇出 net 上很大：`flop_async_reset` 的範圍包含整棵 reset 樹；Phase 5 審查也指出，只往上游追的範圍會落在共用的 reset 同步器上 | soc_top 的 neg-eqy 照舊在 `make regress` 裡跑。決定 25 讓 wrapper 的 neg-eqy 只有 1 個案例（`nand2_comb_to_nor2`），所以 wrapper 上沒有 `flop_async_reset` 這個案例，這個限制在 wrapper 上不適用 | 沒變（wrapper 沒有這個案例） | phase4.md 第 173 行；phase5.md 第 303、305 行；ADR-0019 第 197、203 行 |
| GRT-0243 | antenna 修補時有一條 net 用 diode 修不掉（`GRT-0243`）；修補後與繞線後的檢查都是 0 | wrapper 上一樣：detailed routing log 出現 1 次 `Unable to repair antennas on net with diodes.`；最終 antenna 違規 0（net、pin、route 三種都是 0） | 沒變／已重新量過 | phase3_5.md 第 149 行；`runs/user_project_wrapper/46-openroad-detailedrouting/openroad-detailedrouting.log`；`runs/p7_decap_confirm_signoff/signoff.txt` 第 10–12 行 |
| X1 | （另外找到的）golden 只在同一環境下逐項比對，換平台要重建（Phase 3 限制 8、Phase 4 限制 8）；Phase 5 限制 12 沒列這一項 | 沒變。跟 4-12 同一個量法 | 沒變／需要量（同 4-12） | phase3.md 第 167 行；phase4.md 第 170 行 |
| X2 | （另外找到的）IR 只做 static：電流來自 OpenSTA 的預設切換率（Phase 3 限制 6）。Phase 4 以後沒有逐條帶這一項 | 決定 20 改用 max power pattern 的實際切換活動（VCD），預設切換率只當參考；Phase 6 也把 SRAM 電流改成 SPICE 量測。仍然是 static，沒有做 dynamic IR（沒看 glitch，見 N12） | 部分處理 | phase3.md 第 165 行；ADR-0019 決定 20（第 107–116 行） |
| X3 | （另外找到的）Phase 4 限制 8 裡的 GRT-0229 重試 | 跟表一 5-5 相同，不另外算 | 見 5-5 | phase4.md 第 170 行 |

統計（X3 不算）：沒變／已重新量過或確認 5 列（4-6、4-9、4-10、金屬密度、GRT-0243）；沒變，但在 wrapper 上不適用或不用量 2 列（4-7、flop_async_reset）；沒變／需要量 2 列（4-12、X1，可以一起量）；部分處理 1 列（X2）。

## 需要主 agent 決定或補量的項目

1. **6-1 dout0 transition 的 what-if（優先）**：在 wrapper 的最終版圖上重跑 Phase 6 的 `runs/p6_extract_trial/sta_whatif/whatif.tcl`（只換 SRAM .lib：`*_B.lib`、`*_C.lib`、`*_tran2p5.lib`）。wrapper 的半週期 setup 比 soc_top 少 0.108 ns，照 Phase 6 掉約 0.39 ns 推，餘量可能只剩約 +0.15 ns（推測）。
2. **3.5-14 dout0 最小負載**：在 wrapper 版圖上重跑 `dout_load.tcl`（min RC），跟特性化範圍的 5 fF 與 .lib 上限 50 fF 比。
3. **5-7 SRAM 輸入腳 hold 與自迴路的 hold cell**：在 wrapper 上重跑 `sram_hold.tcl`（min_ff_n40C），並數讀出 flip-flop 自迴路上的 hold delay cell。
4. **5-3 EM**：flow 從來沒有檢查。可以用 PSM 的 `analyze_power_grid -enable_em` 對含 Caravel 網路的 ODB 量一次（pdn-ir-drop 規則 8），或明確寫成「沒有自動防護」並帶到下線前。
5. **5-6／N16 golden 誤差**：等乾淨的 `regress-caravel` 跑完（`runs/p7close_regress_caravel.console` 還在跑），依決定 25 用它加上同機的 4 次 run 校正。
6. **「macro 本身」5 列（6-3、6-8、3.5-5、3.5-6、3.5-7）**：要不要接受「確認是同一顆 macro」就算重新確認，還是在 exit review 裡標成「沒變、沒量（與設計無關）」，請主 agent 決定。
7. **漏帶的項目**：Phase 6 第 9 項只列了 Phase 5 已知限制第 12 項裡的「LVS black box」。第 12 項其他的子項，Phase 6 表裡只寫「其他沒變」（phase6.md 第 140 行），沒有逐條帶到 Phase 7，包括：Phase 4 已知限制 6（EQY 只涵蓋組合邏輯）、7（計數器高半部）、9（下游單獨執行不檢查工作目錄）、10（`py-check` 範圍）、12（第三人重現只在同一台機器驗證）、金屬密度、`flop_async_reset` 的範圍、`GRT-0243`（phase5.md 第 300–304 行）。依規則 1 要逐條補對照。已經補在「表一之二」。要決定的事：(a) 金屬密度整個 wrapper 都低於下限（met2 1.6%、met3 0.8%），precheck 只查上限。要寫成下線前的已知限制，還是先問 ChipFoundry 會不會在下線時補 fill。(b) 4-12／X1 換機器重現要不要在 Phase 7 內做。
8. **文件過期**：golden README「clock」一列還寫「成因沒有查」，`runs/p7_skew_analysis/README.md` 已經有分析；exit review 寫完前要同步。
9. **N2**：ChipFoundry 的 issue 草稿送了沒有，需要問使用者，並記到 exit review。
10. **N6、N14、N15、5-11**：都是「原因沒找到」的工具行為。要決定是帶成已知限制，還是在 Phase 7 內限時再查。
