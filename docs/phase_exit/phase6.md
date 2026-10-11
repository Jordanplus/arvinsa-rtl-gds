# Phase 6 exit review：OpenRAM 自產 SRAM macro

日期：2026-10-11　結論：**PASS**（兩輪乾淨 worktree regress：Hazard3 23/23、PicoRV32 28/28，commit `85bfa75`）

**一段話摘要**：
- 用 OpenRAM dev `3608704c` 加 repo 內的 4 個 patch，在本機 macOS 產生 2 KB 1rw1r 32×512 macro `arv_sram_2kbyte_1rw1r_32x512_8`，取代 PDK 附的預建 macro `sky130_sram_2kbyte_1rw1r_32x512_8`。
- Phase 3.5 的頭號下線風險已解決：預建 macro 在低溫、ss 1.60 V 室溫會讀成前一次的值，自產 macro 在 7 個條件都讀對。修正方式是 sense amp 輸入端預充電（patch 0001），以及把 SRAM 的 `clk1` 接系統時脈（ADR-0018 決定 8、9）。
- 5 個 PVT 的時序與功耗都用 SPICE 量，寫成 .lib。
- 兩個 CPU 的 SoC 用自產 macro 重新完成 signoff。

ADR：`docs/decisions/0018-openram-self-generated-macro.md`（決定 1–20）。過程筆記：`docs/notes/openram_phase6_bringup.md`。

Exit criteria 出處：`project-plan.md` §8 Phase 6。
- exit 條件原文：「自產 macro DRC／LVS 結果 ≤ 預建 baseline；交給 flow 的每個 view 通過 view QA；**5 個 PVT 讀寫正確**（ADR-0010 決定 4）；SoC（Hazard3 與 PicoRV32）以自產 macro 完成 signoff」。
- 內容欄另外要求：檢查最終 GDS 裡沒有前綴的 `sky130_fd_bd_sram__openram_*` cell 只有一份定義；internal_power 也用 SPICE 量（ADR-0018 決定 10）；Colab 官方 nix 環境產生同一顆當對照。

一併帶進本階段的項目：
- Phase 5 已知限制 1–13（`docs/phase_exit/phase5.md`）。
- Phase 3.5 已知限制 1–15（`docs/phase_exit/phase3_5.md`）。Phase 5 把其中第 1 項與第 2–7、13–15 項延到 Phase 6。

處理結果見「帶進本階段的項目」一節。

## 正式 run

兩份 regression 都在乾淨的 worktree 執行：
- 建立方式：`git worktree add --detach` 加 `git submodule update --init --recursive`，開始時沒有修改或未追蹤的檔案。
- `.tools/` 不在 git 裡，用 `LIBRELANE_DIR`、`XPACK_DIR` 指向主 checkout 已安裝的版本。`env-check-flow` 會檢查兩者。

| regression | commit | 時間 | exit code | 結果 | 證據 |
|---|---|---|---|---|---|
| `make regress`（Hazard3，23 項） | `85bfa75` | 2026-10-11 18:17 起，126 分鐘 | 0 | **23/23 PASS** | worktree `p6close_h3` 的 `runs/regress/summary.md`、`junit.xml`；console `runs/p6close_regress_hazard3.console` |
| `make regress-picorv32`（28 項） | `85bfa75` | 接著跑，196 分鐘，23:45 結束 | 0 | **28/28 PASS** | worktree `p6close_pico` 的 `runs/regress_picorv32/summary.md`、`junit.xml`；console `runs/p6close_regress_picorv32.console` |

- **重試**：三次 harden 都沒有重試（沒有 `retries.txt`）。
- **golden 比對**：三次 harden 的 metrics 都與 golden 逐項相同：Hazard3 441 個、PicoRV32 SoC 435 個、picorv32_core 325 個。
- **每次 harden 的 criteria review**（CLAUDE.md 規則 9）：
  - `p6close_h3/runs/soc_top_hazard3_signoff/criteria_review.md`；
  - `p6close_pico/runs/soc_top_signoff/criteria_review.md`；
  - `p6close_pico/runs/picorv32_core_signoff/criteria_review.md`。

之前幾次乾淨 checkout 不當作結案證據（依時間順序）：
- `4713c5f`（步驟 4d）：Hazard3 23/23、PicoRV32 28/28 都 PASS。之後的獨立審查找到 7 個 checker 漏洞，使用者決定全部修正後再跑兩輪（「使用者決定」，ADR-0018 決定 19）。
- `904e18e`（審查修正與萃取試跑之後）：兩輪都在 `harden-soc` FAIL，版圖與 golden 逐項相同，原因是修審查漏洞時弄壞了 `check_inputs.py` 的 `resolved` 列（「本階段找到並修正的 checker 問題」6）。證據在 `runs/p6close_attempt1/`，兩次 harden 的 criteria review 也存在那裡。

除非另外註明，下面的數字取自 `85bfa75` 兩次乾淨 regress 的 run，它們與 golden 逐項相同。

## Exit criteria

| # | 項目 | 結果 | 證據 |
|---|---|---|---|
| 1 | 自產 macro 的 DRC ≤ 預建 baseline | PASS：<br>• Magic full 規則：合併相接的錯誤框後，每一種規則的塊數都 ≤ 預建，面積 ≤ 預建 × 1.0005（ADR-0018 決定 19）；總數 2,234,528 個框、29 種（預建 2,235,078、30 種）<br>• OpenRAM 自己的 DRC 0<br>• flow 用的 KLayout deck 單獨檢查 macro：0 | `make openram-macro` 的 `macro_drc.py`、`macro_klayout_drc.py`；`neg-openram` D1–D8、K0–K8 |
| 1 | 自產 macro 的 LVS ≤ 預建 baseline | PASS：OpenRAM 的 LVS match（Netgen，OpenRAM 釘的 2022 PDK，ADR-0018 決定 5）。SoC 的 LVS 把 macro 當 black box，0 | `runs/openram/arv_sram_2kbyte_1rw1r_32x512_8/`；兩次 harden 的 LVS |
| 2 | 交給 flow 的每個 view 通過 view QA | PASS：LEF、5 份 .lib、TT .lib 範本、Verilog、SPICE、GDS。審查後加上 LEF 與 GDS 的腳位位置、OBS 覆蓋、power 表的每個數字（H1、H2、H7） | `make macro-views`；`neg-macro-views` 22/22（Q1–Q20）；`check_inputs.py` 的 `macro_views`、`macro_source`、`lib_template` |
| 3 | 5 個 PVT 讀寫正確 | PASS：<br>• 電路圖網表 7 個條件都讀對：5 個 STA PVT，加 ss 25°C 1.60 V、tt −40°C 1.60 V（預建 macro 在 ss −40°C、ss 25°C、tt −40°C 讀錯）<br>• 特性化的 5 個 PVT 讀寫都正確；.lib 採用的 setup／hold／pulse width／週期上確認模擬 115 條 lane 都讀寫正確<br>• 版圖萃取網表（含寄生）在 tt 25°C、ss −40°C、ss 100°C 都讀寫正確（ss 兩點用 SoC 的 44 ns 週期） | `runs/openram/read_check_clk1_self/`；`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/char/char.json`、`confirm.json`；`runs/p6_extract_trial/` |
| 4 | SoC（Hazard3 與 PicoRV32）用自產 macro 完成 signoff | PASS：兩個 SoC 15 個 corner 的 setup／hold、DRV、DRC（繞線、KLayout）、LVS、XOR、antenna 都是 0 違規；Magic DRC 全在 SRAM 框內、每一個都對得上 SRAM 單獨檢查的位置；IR 最壞組合 ≤ 20 mV；EQY、gate-level 模擬（含電源接腳版）PASS | 「正式 run」兩輪 regress；「signoff 結果」 |
| 5 | 最終 GDS 裡沒有前綴的 `sky130_fd_bd_sram__openram_*` cell 只有一份定義 | PASS：`check_soc.py macro_gds` 比對最終 GDS 裡 macro 的 169 個 cell 與 macro GDS 逐層相同（審查後改成逐圖形比對，H6）；沒有前綴的 bitcell 名稱只有一份 | `scripts/check_macro_gds.py`；P67–P69、P75、P76 |
| 6 | internal_power 用 SPICE 量 | PASS：5 個 PVT 的讀、寫、閒置能量與待機漏電都是量測值（ADR-0018 決定 10–15） | `char/power.json`；`neg-char` N17–N21 |
| 7 | Colab 官方環境產生同一顆對照 | PASS：小 macro 兩邊 GDS 相同；2 KB 的網表與 LVS 判定相同（`project-plan.md` §9 R7） | ADR-0018 決定 1；筆記步驟 1b、2b |
| 8 | 帶進本階段的項目 | 見「帶進本階段的項目」 | — |

## signoff 結果（44 ns）

| 項目 | PicoRV32 SoC | Hazard3 SoC |
|---|---|---|
| setup 最差 | +0.769 ns（min_ss_n40C_1v60；Phase 5 +0.789） | +0.656 ns（min_ss_n40C_1v60；Phase 5 +1.114） |
| hold 最差 | +0.082 ns（min_ff_n40C_1v95） | +0.126 ns（min_ff_n40C_1v95） |
| 最差 setup 路徑 | SRAM 半週期路徑（`sram0` 在下降緣送出，flip-flop 在上升緣接收） | 同左；SRAM clk→Q 15.78 ns |
| die／core 面積 | 800,000／769,005 µm² | 800,000／769,005 µm² |
| standard cell | 32,070 顆，256,786 µm²（使用率 72.1%） | 30,406 顆，240,768 µm²（70.0%） |
| flip-flop | 2,639 | 2,152 |
| hold buffer（criteria review INFO 列） | 3,589 | 2,783 |
| `power__total`（內部＋切換＋漏電） | 9.47 mW（6.20＋2.54＋0.74） | 20.41 mW（11.02＋8.66＋0.73） |
| 繞線長度 | 886,987 µm | 813,737 µm |
| IR：VDD 降壓＋GND 抬升（nom_tt；上限 20 mV） | 2.09＋2.08＝4.17 mV | 5.23＋5.18＝10.41 mV |
| IR 最壞組合（ff 電流＋SRAM port 1 浮接電流＋ss 金屬電阻，兩個 ff corner 取大；上限 20 mV） | 6.77＋6.72＝13.49 mV（max_ff_100C） | 7.99＋7.92＝15.91 mV（max_ff_100C） |
| DRC（繞線、KLayout）／LVS／XOR／antenna／DRV | 全部 0 | 全部 0 |
| Magic DRC | 4,770,846（全在 SRAM 框內，每一個都對得上 SRAM 單獨檢查時的位置） | 同左 |

數字的出處與讀法：
- 出處：兩次 harden 的 `final/metrics.json`（與 `signoff/golden/{soc_top,soc_top_hazard3}/metrics.json` 相同）、`ir_worst.txt`、`criteria_review.txt`。IR 合計是兩個 metric 相加。
- `power__total` 是 LibreLane 最後寫入的那個 corner 的值，不是各 corner 的最大值（`librelane-run-debug` 規則 4）。比 Phase 5（8.73／19.33 mW）高：PicoRV32 漏電 +0.39 mW、內部 +0.29 mW；Hazard3 漏電 +0.40 mW、內部 +0.42 mW。推測（沒有逐項查證）來自自產 macro 的 .lib 改用 SPICE 量的功耗與漏電（決定 10–15）。
- Hazard3 的 setup 餘量比 Phase 5 少 0.46 ns，PicoRV32 少 0.02 ns；兩者的最差路徑都仍是 SRAM 半週期路徑。兩個 CPU 差這麼多的原因沒有查證。
- .lib 的 dout0 transition 偏低：改成量到的值後最差 setup +0.37 ns（Hazard3 ss −40°C），仍 MET（已知限制 1）。

## 收斂過程

依時間順序（細節在筆記，每一步的決定在 ADR-0018）：
1. **本機產生**（步驟 1–2）：`use_nix=False` 用本機的 Magic、Netgen、KLayout、ngspice，小 macro 與 2 KB 都產生到 GDS、LEF、網表，DRC／LVS 能跑。新版 PDK 的元件改名讓 OpenRAM 的 LVS 不一致，所以 macro 的產生與 DRC／LVS 用 OpenRAM 釘的 2022 PDK（決定 5）。
2. **讀取失敗重現**（步驟 3a、3b）：預設設定（words per row 4）的自產 macro 和預建一樣，在 ss −40°C、ss 25°C、tt −40°C（都是 1.60 V）讀成前一次的值。words per row 1 的版本讀得對，但 446.99 × 1152.58 µm 放不進 die（決定 7）。
3. **修讀取電路**（步驟 3w、3p1、3p2）：網表 what-if 比較 transmission gate 與 sense amp 輸入端預充電，兩者都讓 3 個失敗條件讀對，選後者（patch 0001，決定 8）。2 KB 的 tt 25°C 接著讀錯，根因是閒置的 port 1 的 chip-select DFF 從沒被時脈鎖存，`clk1` 改接系統時脈後 7 個條件都讀對（決定 9）。
4. **特性化與功耗**（步驟 3c、3e）：5 個 PVT 的時序、.lib、確認模擬、view QA 都 PASS；internal power 與漏電改用 SPICE 量，處理 port 1 浮接的穿透電流、半穩態 bitcell、gmin 等問題（決定 10–15）。
5. **換進 SoC**（步驟 4a）：LEF 的資料庫單位 2000 讓 OpenROAD 丟掉整份 LEF（`ODB-0205`），改成 1000（座標都在 0.005 µm 格點上，無損）。
6. **harden 三輪**（步驟 4b、3m）：
   - 第一輪：KLayout 寫出的最終 GDS 裡 SRAM 是空的。OpenRAM 的 LEF 沒有 `FOREIGN`，LibreLane 的 stream-out 沒有合併 macro 的 GDS，log 卻寫 `All LEF cells have matching GDS cells`。加 `FOREIGN` 與 `check_macro_gds.py`。
   - 第二輪：SRAM 真的進了 GDS 之後，flow 的 KLayout DRC 在 SRAM 裡報 27 個（nwell.6、psdm.1、m2.2）。預建 macro 是 0，因為 deck 依名稱排除 `*sky130_sram_*kbyte_*`。用 OpenRAM patch 0002–0004 修（決定 17），Magic 的 licon.14 加進位置比對的 100 nm 容許清單。
   - 第三輪：全部 PASS，重建 golden 與 SRAM DRC 參考檔（決定 16）。
7. **下游驗證**（步驟 4c）：EQY 的網表解析只認 `sky130_` 開頭的 cell，自產 macro 整個被略過，SRAM 的 clock 來源檢查從 4a 起沒有執行；修正後才看到 Hazard3 有 OpenROAD 對調等價輸入（`RSZ-0043 Swapped pins`）造成的 EQY 失敗，改成只排除被對調的腳位名稱（決定 18）。neg-pnr P05 的外框座標寫死成預建 macro 的，改成從 config 與 LEF 讀。
8. **第一次乾淨 regress**（步驟 4d，`4713c5f`）：Hazard3 23/23、PicoRV32 28/28，三次 harden 與 golden 逐項相同。
9. **獨立審查與修正**（步驟 5）：見「獨立審查」。修正後重建 SRAM DRC 參考檔的新格式、IR 改判兩個 ff corner，再跑最後兩輪 regress。
10. **版圖萃取試跑**（步驟 5d）：整顆 SRAM 版圖萃取的網表在 3 個條件讀寫正確，延遲是電路圖的 2.0 倍；Magic 階層萃取的負值修正電容讓 ngspice `Timestep too small`，加 checker 與 neg-char N22（決定 20）。
11. **結案 regress**（步驟 5e）：`904e18e` 兩輪都在 harden-soc FAIL（checker 的 bug，見「本階段找到並修正的 checker 問題」6）；修正後 `85bfa75` 兩輪 PASS。

## 帶進本階段的項目

### Phase 3.5 已知限制

| # | 限制 | Phase 6 結果 |
|---|---|---|
| 1 | PDK SRAM 在低溫、ss 1.60 V 室溫讀取失敗（頭號下線風險） | **已解決**：自產 macro 在 7 個條件（5 個 STA PVT、ss 25°C 1.60 V、tt −40°C 1.60 V）都讀對；版圖萃取網表在 tt 25°C、ss −40°C、ss 100°C 也讀對（決定 8、9、20） |
| 2 | 走線寄生沒有模擬（× 1.6） | **量了，× 1.6 不夠**：整顆平面萃取的讀出穩定時間是電路圖的 2.00–2.03 倍。.lib 不改，靠下限蓋住（tt 10 ns 對萃取 5.32 ns、ss 15 ns 對 10.88 ns），列為已知限制 1（決定 20） |
| 3 | 萃取網表無法模擬；換上萃取 bitcell 後寫入失敗 | **根因已確認**：Magic 階層式輸出的負值修正電容讓 263 個節點總電容為負；平面輸出可以模擬。`extract_sram.py` 現在對負值 FAIL（`neg-char` N22）。寫入失敗沒有重現：整顆萃取的寫入都正確 |
| 4 | dout0 transition 兩個模型差 5 倍 | **電路圖那一邊對**（萃取 ss 100°C 2.09 ns、電路圖 2.16 ns）。.lib 寫 0.5 ns；改成量到的值後最差 setup slack +0.37 ns（Hazard3 ss −40°C），仍 MET。列為已知限制 1 |
| 5 | 沒有 Monte Carlo、只在 bit 0／31 量時序、port 1 與功耗沿用解析值、沒有矽量測 | 功耗改成 SPICE 量測（決定 10–15）；port 1 的時序仍是 OpenRAM 解析值，`clk1` 接時脈後 STA 會用它（ADR-0018 決定 9）。其他沒變 |
| 6 | 修剪後的功能檢查偏悲觀（bit 1–30 只有 2 顆 bitcell） | 沒變：自產 macro 用同樣的修剪（1264 顆 bitcell） |
| 7 | 誤差驗證只在 tt 做過 | 沒變。功耗量測改用完整網表，不受修剪影響 |
| 8 | resizer hold 餘量與半週期路徑衝突 | Phase 5 已解決 |
| 9 | `neg-char` 不在 `make regress` 裡 | 沒變（N1–N3 要跑 SPICE，約 40 分鐘）。結案時在主 checkout（`85bfa75`）跑全部 22 個案例：22/22 PASS（`runs/p6close_negchar.console`） |
| 10 | `GRT-0243` 警告 | 沒變：Hazard3 的 detailed routing log 出現 1 次（`Unable to repair antennas on net with diodes.`），PicoRV32 0 次；兩個 SoC 最終 antenna 違規都是 0 |
| 11 | 繞線器中間各輪的 key | Phase 5 改成 optional key（ADR-0015），沒變 |
| 12 | Phase 4 已知限制 2–13 | 見 Phase 5 已知限制的表 |
| 13 | hold 弧的值和週期有關（只對 ≥ 20 ns 量過） | 沒變；SoC 週期 44 ns |
| 14 | dout0 最小負載 3.35 fF 低於特性化的 5 fF | **重新量過，沒變**：Phase 6 版圖的最小負載 Hazard3 3.5 fF、PicoRV32 3.4 fF（min RC），最大 26.4 fF（.lib 上限 50 fF）。`runs/p6_extract_trial/sta_whatif/dout_load.log` |
| 15 | ss −40°C 的讀取失敗只在 20 ns 週期判定 | 自產 macro 在 ss −40°C 20 ns（電路圖）與 44 ns（萃取網表）都讀對。注意：萃取網表在 20 ns 週期 FAIL，因為 10 ns 的低電位比讀出時間（10.9 ns）短，也比 .lib 的 `min_pulse_width` 12 ns 短 |

### Phase 5 已知限制

| # | 限制 | Phase 6 結果 |
|---|---|---|
| 1 | duty cycle 與 jitter 是假設 | 沒變，Phase 7 |
| 2 | SRAM 的時序與讀取 | 見上表第 1–7、13–15 項 |
| 3 | IR 供電位置是假設 | **重新量過**：最壞組合改判兩個 ff corner，SRAM 漏電加上 port 1 浮接電流（決定 19）。最差 Hazard3 15.91 mV、PicoRV32 13.49 mV（上限 20 mV），比 Phase 5 的 14.13／5.72 mV 高。兩輪結案 regress 的值相同。供電位置仍是假設 |
| 4 | 不可重現的步驟 | 4d 的兩輪 regress 與 golden 逐項相同，網表與 DEF 逐位元相同，GDS 清掉日期後相同。結案的兩輪（`85bfa75`）也和 4d 逐位元相同（「可重現性」）。 |
| 5 | GRT-0229、GRT-0116 只用重試繞過 | 沒變：結案的三次 harden 都沒有重試，重試仍是唯一的繞過方式 |
| 6 | golden 誤差內的改變抓不到 | 沒變 |
| 7 | ADR-0016 留下的項目 | 重新量過：PicoRV32 SRAM 輸入腳的最差 hold（min_ff_n40C）+0.09 ns（Phase 5 +0.093）、Hazard3 +0.28 ns。`runs/p6_extract_trial/sta_whatif/sram_hold.log` |
| 8 | RepairHold 只用一種 hold buffer | 沒變 |
| 9 | `harden-core` 沒接 criteria review | Phase 5 已修 |
| 10 | `neg-char` 不在 regress 裡 | 同 Phase 3.5 第 9 項 |
| 11 | 沒有分析的項目 | 沒變；另加 Phase 6 的 clock skew 變大（已知限制） |
| 12 | 照舊帶到後續階段的 | LVS 中 SRAM 是 black box：Phase 6 補了 view QA 的腳位位置與 OBS 比對（H1、H2），LEF 與 GDS 不一致時 LVS 看不到的問題由 view QA 擋。其他沒變 |
| 13 | 獨立審查的 checker 漏洞 | Phase 5 已修 |

## 可重現性

| 比較 | 結果 |
|---|---|
| 三次 harden 與 golden | metrics 逐項相同（441／435／325 個），沒有用到誤差 |
| 與 `4713c5f`（步驟 4d）的 run | 最終網表、DEF 逐位元相同；GDS 清掉 `BGNLIB`／`BGNSTR` 的日期後相同（`soc_top` 兩個 CPU、`picorv32_core`） |
| 重試 | 沒有 |

- 從 `4713c5f` 到 `85bfa75` 之間沒有改設計輸入（改的是 checker、文件、萃取試跑的腳本），所以版圖相同是預期的；這也表示 Phase 5 的不可重現步驟（global routing、detailed routing 的 diode）這幾次沒有出現差異。
- GDS 的日期比對是手動做的（沒有自動防護，見「規則 10 稽核」）。

## Checker qualification（本階段新增）

| negative test | 植入的錯誤 | 預期的 checker | 結果 |
|---|---|---|---|
| `neg-openram` O1–O8 | OpenRAM 的 log 有 `ERROR ... LVS mismatch` 但 exit 0（2026-10-08 實際遇到）、DRC／LVS 報告、輸出檔 | `gen_macro.judge` | 兩輪都抓到（`neg-openram` 50/50） |
| `neg-openram` I1–I4、T1–T3 | `make sky130-install` 少複製 cell 卻 exit 0；OpenRAM 工作樹不是「釘選 commit＋patch」 | `check_install.py` | 兩輪都抓到（`neg-openram` 50/50） |
| `neg-openram` D1–D8 | 自產 macro 的 Magic DRC：新種類、合併後多一塊、面積多 0.1%（多 0.03% 要 PASS）、框數多但合併後相同（要 PASS）、真的跑 Magic 加一個 li.3 | `macro_drc.py` `compare()`、`merge()` | 兩輪都抓到（`neg-openram` 50/50） |
| `neg-openram` K0–K8 | flow 的 KLayout deck：macro 裡的違規、cell 名稱符合 deck 的排除樣式（SRAM、2 種 IO cell）、deck 解析 | `macro_klayout_drc.py` | 兩輪都抓到（`neg-openram` 50/50） |
| `neg-openram` L1–L2、C1–C7（含 C6a） | .lib 範本的 internal_power 1e11、power 表的每個數字（NaN、多值表）；特性化來源 | `gen_char_lib.py`、`check_char_lib.py` | 兩輪都抓到（`neg-openram` 50/50） |
| `neg-macro-views` Q1–Q20 | view QA：數值範圍、單位、面積、外框、腳位、`FOREIGN`、LEF 與 GDS 的腳位位置對調、少了 OBS、power 表多值 | `check_macro_views.py` | 兩輪都抓到（22/22） |
| `neg-pnr` P63–P78 | macro 的來源（P63、P70、P74）、行為模型（P64）、`clk1` 接常數（P65）、LEF 尺寸（P66）、最終 GDS 的 macro 內容（P67、P68、P75、P76）、框內 DRC（P69）、腳位位置與 OBS（P71、P72）、範本（P73）、IR 的浮接電流與兩個 corner（P77、P78） | `check_inputs.py`、`check_soc.py`、`ir_worst.py` | 兩輪都抓到（`neg-pnr` 79/79；P00 positive control PASS） |
| `neg-eqy-soc` `o21ai_swap`、`din5_stuck0` | 對調後功能不同的腳位、跳脫名稱 | `run_eqy.py` `pin_swaps()`、`partition_reads()` | 兩輪都抓到，FAIL 的位置在植入點（Hazard3 14/14、PicoRV32 10/10） |
| `neg-char` N17–N22 | 功耗量測、漏電量測窗、gmin、萃取網表的負值電容 | `power.py`、`gen_char_lib.py`、`check_char_lib.py`、`extract_sram.py` | 主 checkout `85bfa75`：N1–N22 22/22（2026-10-12） |

## 本階段找到並修正的 checker 問題

開發過程中（審查之前）：
1. `run_eqy.py` 只解析 `sky130_` 開頭的 cell：自產 macro 被略過，SRAM 的 clock 來源檢查從 4a 起沒有執行（`KeyError: 'sram0'` 才發現）。
2. `magic_drc` 在 SRAM 框內 0 個違規仍 PASS（比對的集合是空的）：加框內下限 50%。
3. neg-pnr P05 的 SRAM 外框寫死成預建 macro 的座標，自產 macro 只拿掉 4 個多餘的 via，LVS 不會 FAIL。
4. `din5_stuck0` 的植入程式弄壞跳脫名稱；checker 正確判成沒抓到。
5. `check_soc.py --make-drc-baseline` 的 `source` 寫錯成「PDK GDS」。

獨立審查找到的 7 個漏洞（H1–H7）見「獨立審查」。

結案 regress 第 1 次（`904e18e`，兩輪都在 harden-soc FAIL，證據在 `runs/p6close_attempt1/`）：

6. **`check_inputs.py` 的 `resolved` 列對每個 run 都 FAIL**：修 H3 時（`37c99b4`）在 `macro_source` 區塊把變數 `files` 改成 view 檔名的字典，後面的 `resolved` 拿它去比 RTL 檔案清單。
   - 版圖本身沒問題：Hazard3 的 441 個、PicoRV32 的 435 個 golden metric 逐項相同，其他 checker 全部 PASS。
   - 修正前沒被抓到的原因：`--resolved` 只被 P20、P36、P39、P42 呼叫，四個都是「植入後必須 FAIL」，checker 永遠 FAIL 時照樣「抓到」。`37c99b4` 之後沒有跑過完整的 harden。
   - 修正：字典改名；`resolved` FAIL 時列出不符的欄位；neg-pnr P00（positive control）加上「`check_inputs.py --resolved` 在 run 自己的 resolved.json 上必須 PASS」。
   - 驗證：修正版在兩個 worktree 的 run 上 PASS；P00、P16、P20、P36、P39、P42 在兩個 CPU 都符合預期；換回修正前的 checker，新的 P00 FAIL。
   - 漏洞類型寫進 `signoff-checker-qualification`：checker 的某個模式只有植入錯誤的案例在跑。

## 與計畫不同的地方

1. **讀取電路**：計畫是「先試 words per row 1」。它讀得對但放不進 die，改用 sense amp 輸入端預充電（OpenRAM patch 0001），並把 `clk1` 接系統時脈。後者改了 RTL（`soc_top.v`），計畫原本寫「RTL 不改」（決定 4、8、9）。
2. **OpenRAM 用 repo 內的 patch**（0001–0004）：讀取電路、保護環、DFF 間距、tap 接點高度。`make openram-setup` 檢查工作樹恰好是釘選 commit 加 patch。
3. **macro 的產生與 DRC／LVS 用 OpenRAM 釘的 2022 PDK**，SoC flow 用 `8afc834`（決定 5）。
4. **macro DRC 的「≤ 預建」改成比合併後的違規區域**：Magic 會在 cell 座標每 157.28 µm 切開錯誤框，框數隨陣列位置變。每種規則合併後的塊數嚴格、面積容許 0.05%（決定 19）。
5. **Magic 的 licon.14 加進位置比對的 100 nm 容許清單**（決定 17）。
6. **EQY 排除 OpenROAD 對調的等價輸入腳位名稱**（決定 18）。
7. **.lib 的走線餘量沿用 × 1.6 與下限**：萃取量到 2.0 倍，使用者選擇不改 .lib（決定 20）。
8. **1RW 沒有採用**：釘住的 OpenRAM 產不出 DRC／LVS 乾淨的 sky130 1RW，維持 1rw1r（決定 11）。

## 已知限制（帶到後續階段）

1. **SRAM .lib 的時序沒有走線寄生，靠下限蓋住**（決定 20）：
   - 整顆版圖萃取的讀出穩定時間是電路圖的 2.0 倍，× 1.6 不夠；.lib 的延遲下限比萃取值大 4.1–4.8 ns。
   - `min_pulse_width` 下限 12 ns 對萃取的 ss 讀出時間（約 10.9 ns）只剩約 10%；SoC 的低電位是 22 ns。
   - dout0 transition 寫 0.5 ns，實際約 1.4–2.2 ns；改成實際值後最差 setup slack 仍有 +0.37 ns。
   - ff、tt −40°C、ss 25°C 沒有跑含寄生的模擬。換製程、換 macro 或下線前，用平面萃取網表重新特性化。
2. **port 1 浮接的穿透電流不在 .lib 裡**（決定 11）：ff 100°C 最大 5.34 mW。IR 最壞組合已加上（決定 19），flow 的功耗數字沒有。實際晶片上這些節點的電壓無法準確預測。
3. **.lib 的漏電不是穩態值**（決定 14、15）：tt 25°C 可能偏低 26% 以上，絕對值都小於 1 µW（ff 100°C 409 µW 除外）。
4. **macro DRC 的面積容許 0.05%**（決定 19）：接在既有違規上、又小於該規則總面積 0.05% 的新違規看不到。新的獨立違規一定會多一塊，抓得到。
5. **clock skew 變大**：ss −40°C 的 skew metric 大了約 0.2–0.4 ns，clock inverter 49 → 87（PicoRV32）、56 → 101（Hazard3）。推測是 `clk1` 成為新的 clock sink，沒有分開做實驗；最差 setup／hold 仍 PASS（golden README）。
6. **`DRT-0418 ... has no pins on routing grid`**：detailed routing 對 SRAM 的 25 支腳位報這個 warning（預建 macro 沒有），最終 DRC／LVS 0；根因沒有查（推測是腳位沒有對齊繞線格點）。
7. **`neg-char` 不在 regress 裡**（Phase 3.5 限制 9）。萃取（`make sram-extract`）也不在，而且照現在的階層式輸出會 FAIL（預期，決定 20）。
8. **OpenRAM 的已知問題**：
   - dev 產生的 .lib internal_power 數量級錯（1e9–1e11，上游 issue #294 未修），範本改用 `lib_template.py`；
   - LVS 失敗時 exit 0，要讀 log 判斷；
   - 1RW 產不出乾淨的 sky130 layout。
9. **照舊帶到後續階段**：
   - Phase 5 已知限制 1、3–8、11（duty cycle 與 jitter、IR 供電位置、不可重現的步驟、GRT 重試、golden 誤差、ADR-0016 的項目、hold buffer、沒有分析的項目）；
   - Phase 3.5 已知限制 5–7、13、14（Monte Carlo、修剪、只在 tt 驗誤差、hold 弧與週期、最小負載）；
   - LVS 中 SRAM 是 black box。

## 獨立審查（2026-10-11）

兩個沒參與實作的 agent，審查 `e19ef5a`（第一次乾淨 regress 與 skill 寫回之後）。報告：`runs/p6_review/doc_check.md`、`checker_holes.md`，實驗在 `runs/p6_review/holes/`。

### 文件核對

核對 44 列：11 列錯誤、8 列說法不完整到會誤導，大多是 Phase 6 改了東西、文件沒有同步而過期。例如：
- ADR-0018 的已知限制還寫「internal power 是解析值」，實際已是量測值；
- golden README 把 `power__total` 的增加歸因錯了，也沒說明它是最後寫入的 corner（max_ff_100C）的值；
- golden README 的可重現性表沒有 4b、4d 的 run；
- 結案條件「逐種類和預建比較」與 `macro_drc.py` 的實際判法（只比總數與種類）不符。

全部在 `03a796d` 修正。

### 找 checker 漏洞

做了 12 個植入錯誤實驗加 4 個對照組，確認 7 個漏洞。每一個都是「植入錯誤後，應該 FAIL 的 checker 仍然 PASS」：

| # | 漏洞 | 修正 | negative test |
|---|---|---|---|
| H1 | view QA 不比對 LEF 與 GDS 的腳位位置：LEF 的 `din0[0]`／`din0[1]` 對調，`check_inputs.py` 12 列全部 PASS；LVS 把 macro 當 black box 也看不到 | `scripts/gds_view.py` 讀 GDS 的腳位標籤與金屬，`check_macro_views.py` 逐支比對 | Q14–Q17、P71 |
| H2 | LEF 沒有 OBS（繞線障礙）仍 PASS | OBS 與腳位之外的金屬要被覆蓋 | Q17a、P72 |
| H3 | .lib 範本與 OpenRAM 的 TT .lib 沒有來源追溯 | `macro_source` 加 TT .lib，`lib_template` 重新產生後要等於範本 | P73、P74 |
| H4 | `macro_drc.py` 只比總數與種類 | 每種規則比合併後的塊數與面積（決定 19） | D1–D8 |
| H5 | KLayout deck 依名稱排除的 cell 只防 SRAM 一種 | 從 deck 解析所有名稱排除樣式 | K4、K7、K8 |
| H6 | GDS 比對只算圖形數與座標和 | 每層逐圖形的雜湊 | P75、P76 |
| H7 | power 表只讀第一個數字；NaN 通過 `abs(v - want) > tol` | 讀整張表；比較改成 `not abs(..) <= tol` | C6、C6a、C7、Q19、Q20 |

另外做了驗證，確認這次交付的 SRAM 不受這些漏洞影響：125 支腳位的 LEF 與 GDS 位置都一致；macro DRC 多出的三種（diff/tap.1、licon.5a、poly.2）是 Magic 切框造成的，合併後 XOR 為 0。

審查也指出兩件設計上要決定的事，使用者都選了建議選項（ADR-0018 決定 19）：
- IR 最壞組合只用 max_ff_n40C，但自產 SRAM 讓 max_ff_100C 的功耗高約 10%，port 1 浮接電流也不在 .lib 裡：改成兩個 ff corner 都跑、加上浮接電流。
- Phase 3.5 限制 3（萃取網表）沒有做：限時 3 小時試跑（結果見決定 20）。

## 使用者決定

ADR-0018 有每個決定的選項、理由與使用者原話。本階段的決定：
1. 2026-10-08：本機 macOS 原生、Colab 對照；OpenRAM dev `3608704c`；先重現讀取失敗再試 words per row 1；規格維持 2 KB 1rw1r（決定 1–4）。
2. 2026-10-08：macro 用 OpenRAM 釘的 2022 PDK（決定 5）；DRC 先做 SPICE 再修（決定 6）；sense amp 輸入端預充電（決定 7、8）；`clk1` 接系統時脈（決定 9）。
3. 2026-10-09～10：internal power 與漏電的量法（決定 10–15）；維持 1rw1r（決定 11）。
4. 2026-10-10：步驟 4–5 的事先授權（決定 16）；DRC 用 patch 修、licon.14 容許（決定 17）；EQY 排除對調腳位（決定 18）。
5. 2026-10-11：審查後全部修正、IR 兩個 ff corner 加浮接電流、macro DRC 比合併區域（塊數嚴格、面積 0.05%）、萃取限時試跑（決定 19）。
6. 2026-10-11：萃取試跑之後，44 ns 重跑 ss 兩點、.lib 不改寫已知限制、加負值電容 checker（決定 20）。

## Skill 分析（`phase-exit-review` 規則 8）

本階段的重大任務與對應的 skill（`git diff --stat 71b1454 HEAD -- .claude/skills`）：

| 任務 | skill | 寫回 |
|---|---|---|
| OpenRAM 自產 macro、讀取電路、特性化、功耗、萃取 | `openram-macro-characterization`（Phase 3.5 建立，Phase 6 沿用，CLAUDE.md 規則 7） | 規則 10 加三條（負值電容、整顆萃取、讀取檢查的低電位）；規則 17–28（自產 macro：PDK、exit 0、安裝、`PYTHONHASHSEED`、DRC、patch、範本、漏電、1RW、量測順序、gmin）；經驗紀錄 |
| macro 換進 SoC、view QA、`FOREIGN`、LEF 單位、`clk1` | `hard-macro-integration` | 清單第 0 項（view QA 加腳位位置與 OBS）、規則 3（OpenRAM 的時脈腳位不能接常數）；經驗紀錄 |
| macro 的 DRC、KLayout deck 名稱排除、Magic 切框、licon.14 | `drc-signoff` | 規則 2、5、6；經驗紀錄 |
| LVS 把 macro 當 black box | `lvs-signoff` | 規則 1 |
| EQY 的 cell 解析、OpenROAD 對調腳位 | `formal-equivalence-eqy` | 規則 6（pin swap 的四項防護）、網表解析涵蓋任何 macro 名稱 |
| IR 兩個 ff corner、浮接電流 | `pdn-ir-drop` | 規則 12 |
| checker 漏洞類型（腳位位置、OBS、範本來源、NaN 等） | `signoff-checker-qualification` | 漏洞類型表加 5 種；結案 regress 再加 1 種（checker 的某個模式只有植入錯誤的案例在跑） |
| criteria review、sky130 的事實 | `signoff-criteria` 與 knowledge 檔 | S15、S25–S27 |
| GDS 檔頭日期、乾淨 worktree regress | `flow-regression-reproducibility` | 經驗紀錄 |
| clock skew 變大（`clk1` 成為 clock sink） | `cts-clock-tree` | 經驗紀錄（根因推測） |
| `ODB-0205`、stream-out 沒合併 GDS | `librelane-run-debug` | 經驗紀錄 |
| 收尾 | `phase-exit-review` | 規則 2 補：開結案 regress 前，最後改過的 checker 先在現有的 run 上跑 positive control（Phase 3.5 P17 與本階段 `check_inputs.py`，第二次出現）；經驗紀錄一列 |

沒有更新的 skill 與理由：
- `cts-clock-tree`：只加一列經驗紀錄（clock skew 變大，根因推測是 `clk1` 成為新的 clock sink）。沒有做實驗，依 CLAUDE.md 規則 3 不進規則本文（已知限制 5）。
- `drv-timing-closure`、`multicorner-sta`、`timing-constraints-sdc`：時序收斂與 corner 設定沿用 Phase 5，沒有新現象。
- `gate-level-simulation`：SRAM 的行為模型換成自產 macro 的，方法相同。
- `antenna-signoff`：antenna LEF 用同一支 `gen_antenna_lef.py` 產生，結果 0。
- `floorplan-congestion`：SRAM 擺放座標改了（ADR-0006 補充），沒有壅塞問題。
- `core-migration-hazard3`、`dv-directed-tests`、`rtl-synthesis-lint`：RTL 只改 `clk1` 一條連線。

### 規則 10 稽核：本階段的工具缺陷與防護

| 工具缺陷或意外行為 | 症狀寫在 | 怎麼發現 | 怎麼繞過 | 防復發 |
|---|---|---|---|---|
| OpenRAM 的 DRC 只報 WARNING、不是 full 規則 | `openram-macro-characterization` | `macro_drc.py`（Magic full）、`macro_klayout_drc.py` | 另跑 full 規則與 flow 的 deck | `neg-openram` D、K 系列 |
| OpenRAM LVS 失敗時 exit 0 | 同上（規則 18） | 讀 log 與報告 | `gen_macro.judge` 判斷 | `neg-openram` O1 |
| `make sky130-install` 少複製 cell 卻 exit 0 | 同上（規則 19） | `check_install.py` | 逐一檢查安裝結果 | `neg-openram` I1–I4 |
| OpenRAM dev 的 .lib internal_power 1e9–1e11 | 同上 | `gen_char_lib.py` 拒收、view QA | `lib_template.py` 換成預建的值 | L1–L2、Q1 |
| 同一設定兩次產生的 GDS 不同 | 同上（規則 20） | KLayout XOR | `PYTHONHASHSEED=0` | **沒有自動防護**：重產比對要等有基準值再加（規則 20） |
| LibreLane stream-out 沒合併沒有 `FOREIGN` 的 macro GDS，log 寫 `All LEF cells have matching GDS cells` | `hard-macro-integration` | `check_macro_gds.py`、XOR | `add_foreign()` | Q13、P67–P69 |
| OpenROAD 讀 LEF 資料庫單位 2000 時丟掉整份 LEF（`ODB-0205`、`ODB-0292`） | `hard-macro-integration` | floorplan log | LEF 改成 1000 | view QA 檢查 `DATABASE MICRONS`（Q12） |
| KLayout deck 依 cell 名稱排除規則 | `drc-signoff` | `macro_klayout_drc.py` | macro 單獨跑 deck，名稱符合排除樣式就 FAIL | K4、K7、K8 |
| Magic DRC 每 157.28 µm 切開錯誤框 | `drc-signoff` | `macro_drc.py` 的合併比較 | 比合併後的區域 | D5、D8、D8a |
| Magic 在晶片裡的 licon.14 框比單獨檢查長 60–90 nm | `drc-signoff` | `check_soc.py magic_drc` | 100 nm 容許清單 | P09、P21 |
| LVS 用 LEF 抽象圖萃取 macro，看不到 LEF 與 GDS 不一致 | `lvs-signoff` | view QA 的腳位位置 | — | Q14–Q17、P71、P72 |
| OpenROAD 對調等價輸入，EQY 名稱對應矛盾 | `formal-equivalence-eqy` | EQY log 的 `conflicting matches` | 排除被對調的腳位名稱 | `o21ai_swap` |
| Magic 階層式萃取的負值修正電容（`Timestep too small`） | `openram-macro-characterization` | `extract_sram.py` | 平面輸出 | N22 |
| ngspice 預設 gmin 讓單顆 bitcell 漏電偏高 | `openram-macro-characterization` | `cell_gmin_problem()` | `gmin=1e-17` | N21 |
| GDS 檔頭存日期，sha256 每次不同 | `flow-regression-reproducibility`、`openram-macro-characterization` 規則 20 | 比 sha256 | 清掉 BGNLIB／BGNSTR 或用 XOR | **沒有自動防護**：regress 比的是 metrics，不比 GDS 的 sha256；`check_macro_gds.py` 逐圖形比對，不受日期影響 |

## 交付物

- **macro**：`ip/sram/arv_sram_2kbyte_1rw1r_32x512_8/`（GDS、LEF、Verilog、SPICE、5 份 .lib、`char.json`、`confirm.json`、`power.json`、README）。
- **產生 macro**：`ip/sram/openram/`（patch 0001–0004、`gen_macro.py`、`check_install.py`、`macro_drc.py`、`drc_merge.py`、`macro_klayout_drc.py`、`lib_template.py`、DRC baseline、`neg_openram.py`）。
- **特性化與功耗**：`ip/sram/char/` 的自產 macro 分支、`power.py`、`extract_sram.py` 的負值電容 checker、`neg_char.py` N17–N22。
- **view QA**：`scripts/check_macro_views.py`、`scripts/gds_view.py`、`scripts/check_macro_gds.py`、`scripts/gds_cells.py`、`scripts/neg_macro_views.py`。
- **flow 與 checker**：`pnr/soc_top/` 的 config、`check_inputs.py`、`check_soc.py`、`ir_worst.py`、`neg_pnr.py` P63–P78；`signoff/eqy/run_eqy.py`、`neg_eqy.py`。
- **golden 與參考檔**：`signoff/golden/soc_top/`、`soc_top_hazard3/`；`signoff/waivers/soc_top/sram_magic_drc_baseline.json`。
- **文件**：ADR-0018、ADR-0006 Phase 6 補充、ADR-0010 已知限制的 Phase 6 更新、`docs/notes/openram_phase6_bringup.md`。
- **狀態列進度**：`scripts/progress.py` 補上 `done`、`doing_detail`，以及 scratchpad 裡直接跑的腳本。
