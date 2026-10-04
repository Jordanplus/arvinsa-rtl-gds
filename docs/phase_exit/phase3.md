# Phase 3 exit review：整合預建 SRAM macro

日期：2026-10-04　結論：**PASS**。exit criteria 5 項與 EQY（範圍縮小為合成網表 vs 最終網表）全部 PASS；`make phase3` 在乾淨 checkout 從頭到尾跑完（rc=0，91 分鐘）。這是第四次：第一次的隨機錯誤用有上限的重試繞過（重試只用模擬測試與一次手動接續驗證過），後兩次的問題已修正。與計畫不同的做法（13 項）和帶到後續階段的已知限制（16 項）列在文末。結案後有兩個獨立審查，結果見「獨立審查」一節。

Exit criteria 出處：`project-plan.md` §8 Phase 3。原文為：GDS 含 macro；§7.2 全 PASS（含 9 corner）；full-GDS DRC 只在 SRAM 內且 ≤ baseline；L2 GL sim（含 SRAM 模型）PASS；P01–P12 全部在預期 checker FAIL。另外依使用者在 Phase 2 的決定，formal equivalence（EQY）提前到本階段做（`docs/phase_exit/phase2.md` 已知限制第 7 點）。

正式結果來自 `make phase3`：
- 執行位置：commit `53529c6` 的乾淨 checkout（git worktree `../arvinsa-rtl-gds-phase3d`）。
- 前三次沒有跑完：
  - 第一次（commit `654c303`）在 harden-soc 隨機中止，見「怎麼收斂」第 6 點。
  - 第二次（commit `658b6dd`）harden-soc、eqy-soc、neg-eqy-soc 都 PASS，但 gl-soc 在乾淨 checkout 找不到 firmware。
  - 第三次（commit `acbc126`）跑到 gl-soc 都 PASS，neg-gl-soc 有一個植入錯誤的網表 Icarus 編譯不過。
  - 後兩次的問題見「本階段找到的 checker 問題」最後兩列。
- 執行時間：2026-10-04 00:50:06–02:21:29（5483 秒，約 91 分鐘），rc=0；跑完後工作目錄沒有任何未提交的變動。
- 證據檔案：在該 checkout 的 `runs/` 之下。

除非另外註明，下表數字取自 golden 的來源 run（`signoff/golden/soc_top/README.md`）。`make phase3` 那次與 golden 的比對結果見「可重現性」。

| # | Exit criterion | 結果 | 證據 |
|---|---|---|---|
| 1 | GDS 含 macro | PASS | `check_soc.py macro`：最終網表只有一顆 `sram0`。GDS 只有 `soc_top` 一個 top cell，161 個 SRAM cell 都接得到（一次性的手動檢查，獨立審查在第四次的 GDS 上重做一次，結果相同；沒有自動 checker）；KLayout 與 Magic 兩份 GDS 的 XOR = 0 |
| 2 | §7.2 全 PASS（9 corner） | PASS，做法與計畫不同的項目見「與計畫不同的地方」第 2、3、4、11、12 點 | `signoff/limits/soc_top.toml` 每一列 PASS，320 個 metrics 與 golden 比對 PASS |
| 3 | full-GDS DRC 只在 SRAM 內且 ≤ baseline | PASS | Magic 完整 GDS DRC：SRAM 外框外 0 個；框內 4,665,810 個，30 種規則，SRAM 單獨檢查時同樣是這 30 種，單獨檢查共 5,579,161 個。兩邊的框切法不同，數量不能逐一比對，所以 checker 比的是規則種類，總數由 golden 鎖住。獨立審查另外逐一比過位置，0 個無法解釋（已知限制 14） |
| 4 | L2 GL sim（含 SRAM 模型）PASS | PASS | `make gl-soc`：13/13 支測試 PASS。RTL 與網表每個 cycle 比對 soc_top 的輸出與 SRAM port 0 的輸入腳，沒有任何不一致（比對範圍見「與計畫不同的地方」第 7 點） |
| 5 | P01–P12 在預期 checker FAIL | PASS（有調整） | `make neg-pnr`：P01–P20 全部在預期的 checker FAIL。P05–P09、P12 的植入方式與計畫不同，P13–P20 是新增的，見下方 checker qualification |
| + | EQY（Phase 2 決定提前） | PASS（範圍縮小） | soc_top：18100/18100 個分區證明等價；picorv32_core：15137/15137。兩者證明的都是合成網表 vs 最終網表，RTL → 合成網表沒有 formal 證明，見「與計畫不同的地方」第 1 點與已知限制 11 |

## §7.2 signoff metrics

| 類別 | 計畫門檻 | 結果 |
|---|---|---|
| setup | 9 corner ≥ 0；nom_tt ≥ 週期 10%（4 ns） | 最差 +3.553 ns（min_ss）；nom_tt +8.670 ns |
| hold | 9 corner ≥ 0 | 最差 +0.032 ns（min_ff） |
| max slew／cap／fanout | 0 | 9 corner 都是 0（signoff 用 LibreLane 原本的 0.75 ns、fanout 10） |
| STA 完整性 | unannotated = 0；沒有未受約束的 endpoint | unannotated 134（組成固定，見下方第 4 點）；`check_setup` 在 9 corner 只有預期的 `sram0/clk1`（port 1 的 clock 接 0） |
| 防止邏輯被優化掉 | instance 數 golden ±10%；FF 數；SRAM = 1 | 比計畫更嚴：所有 count／area 必須與 golden 完全相同；SRAM = 1 |
| 實體 | route DRC 0；antenna 0；IR ≤ 5% VDD；最長線 ≤ 門檻 | route DRC 0；antenna 0（SRAM LEF 補上 antenna 資料後，checker 看得到 SRAM 輸入線，ADR-0008）；IR drop 最差 0.306 mV；最長線 619.53 µm，是 SRAM port 1 的 tie-off 線（tie cell 到 `sram0/addr1[7]`）；沒有另訂門檻，由 golden 鎖住（見「與計畫不同的地方」第 11 點） |
| 擺放 | `sram0` 座標方向不漂移 | `check_soc.py placement`：FIXED (301.76, 364.48) N，與 config 相同 |
| signoff | DRC／LVS／XOR | LVS 0、KLayout DRC 0、XOR 0、Magic DRC 見 exit 第 3 項 |
| 來源追溯 | 記錄 git sha、LibreLane 版本、PDK hash；工作目錄有未提交修改即 FAIL | `signoff/scripts/provenance.py`：flow 開始前與結束後各檢查一次（Phase 2 延到本階段，本階段收尾時補做） |

## 實測面積與時序

| 項目 | 值 |
|---|---|
| die／core | 1000 × 800 µm；core 769,005 µm² |
| 合成後（Yosys） | 12,515 顆 cell（含 SRAM black box 1 顆），153,800 µm²（SRAM 不計面積） |
| PnR 後 standard cell | 27,932 顆（含 tap 6,635 顆、antenna diode 78 顆，不含 filler 68,905 顆），227,740 µm²。logic 區使用率 51%，用 ADR-0006 的公式：standard cell 面積 ÷（core 面積 − SRAM 加 halo 324,251 µm²）。LibreLane 的 `design__instance__utilization__stdcell` 是 0.470，它的分母只扣 SRAM 本體 |
| 其中 | flip-flop 2,639 顆；timing repair buffer 8,117 顆（56,621 µm²，含 hold buffer 2,468 顆）；clock buffer 551 顆；antenna diode 78 顆（global routing 後的修復插 29 顆，detailed routing 時插 49 顆；`antenna_diodes_count` 這個 metric 只記到後面的 49 顆） |
| SRAM | 284,538 µm²（683.1 × 416.54 µm） |
| setup worst slack | tt +8.66～+8.69 ns；ss +3.55～+3.63 ns；ff +8.87～+8.89 ns。最差路徑：`sram0` 在 clock 下降緣送出 `dout0`，經 padded.lib 的 10 ns 延遲 × ss derate 1.5，到 rdata 暫存器（上升緣接收），只有半個週期可用 |
| hold worst slack | ff +0.032～+0.035 ns；tt +0.20 ns；ss +0.70 ns |
| clock skew（setup，含 0.25 ns uncertainty） | 各 corner 0.69–1.55 ns，最大在 max_ss（1.546 ns）。注意總值 `clock__skew__worst_setup` 0.685 是各 corner 的最小值，不是最差值（LibreLane 的彙總方式，同 `power__total` 要注意） |
| 功耗（OpenSTA，沒有 switching activity 檔，用預設值） | `power__total` 9.03 mW（max_ff，9 個 corner 依序寫入後留下的最後一個值，同 Phase 2 說明） |
| IR drop（static） | 最差 0.306 mV、平均 0.039 mV |
| 繞線 | 總長 877,463 µm；via 156,675 個；最長一條 619.53 µm |
| 執行時間（第四次 `make phase3`） | harden-soc 21.6 分（含來源追溯與 soc 專用檢查）；eqy-soc 295 秒；neg-eqy-soc 439 秒；gl-soc 464 秒（另外先編 firmware 約 4 秒）；neg-gl-soc 251 秒；neg-pnr 517 秒；harden-core 14.5 分；eqy-core 249 秒；neg-eqy-core 1090 秒；env-check-flow、neg-provenance、test-flow-retry 合計不到 10 秒。harden 的時間取自 `runs/<tag>_signoff/` 的檔案時間，其餘取自各 target 印出的秒數 |

## 怎麼收斂（細節在 `pnr/soc_top/README.md` 試跑紀錄）

1. **PDN 失敗**：SRAM 離 die 右、上邊各約 25 µm 時，SRAM 上方只剩約 6 µm 的 row，PDN 報 `PDN-0179 Unable to repair all channels`。把 SRAM 移到 (301.76, 364.48)，讓 10 µm halo 正好蓋過 core 的右、上邊界（ADR-0006 Phase 3 補充）。
2. **heuristic diode 插太多**：`RUN_HEURISTIC_DIODE_INSERTION` 在所有超過 90 µm 的線上加 diode，共 10,231 顆，global routing 跑了 10 分鐘以上還不收斂。改用 antenna LEF（ADR-0008）。
3. **Magic GDS 有 13 個 top cell**：KLayout.Render 失敗。改 `PRIMARY_GDSII_STREAMOUT_TOOL=klayout`。
4. **abstract DRC 的假錯誤**：每條 row 報 `nwell.4`（416 個）。改用完整 GDS，並由 `check_soc.py magic_drc` 判定。
5. **ss corner 的 max slew**：
   - 長線切段（200 µm）、修復餘裕（30／40%）之後，違規從 50 個降到 16 個（explore7）；之後又加 PnR fanout 8，修掉 1 個 fanout 違規。
   - 剩下的違規是繞線大幅繞路造成的：最差一條端點相距 117 µm，實際繞了 353 µm，位置都在 L 形 logic 區的轉角。
   - 根因是 global placement 的目標密度自動算成 68%，cell 擠在轉角；改成 55% 後 9 corner 都是 0。
   - 中途曾把 signoff max transition 放寬到 1.0 ns（ADR-0009），找到這個根因後撤回。
6. **`OpenROAD.RepairDesignPostGRT` 隨機中止**：
   - 第一次 `make phase3`（乾淨 checkout）在這一步報 `GRT-0229 ... (79, 0) usage=65534` 而中止。
   - 第 39 步（global routing）以前的 DEF 與 golden 來源 run 逐 byte 相同；拿同一份輸入單獨重跑這一步 4 次（同時跑），2 次中止、2 次通過，兩次通過的結果完全相同。證據與指令在 `docs/notes/grt0229_repro.md`。
   - 處理：`pnr/librelane_flow.sh` 只對這一個訊息從該步接續，總共最多跑 3 次（最多重試 2 次），並記錄重試次數。
   - 這也表示 explore3 把這個錯誤歸因到 `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH` 是不可靠的（只跑一次），已更正（`pnr/soc_top/README.md` 已知限制 4）。

## 可重現性

| run | 與 golden 比較 |
|---|---|
| 試跑 soc_explore10（密度 55% 由命令列 `-c` 給，signoff SDC 是當時 1.0 ns 的版本，PnR 部分與定案相同） | 320 個 metrics 完全相同（兩種 slew 門檻下違規都是 0） |
| golden 來源 run（定案設定的第 1 次 `make harden-soc`） | 本身 |
| 第一次 `make phase3`（乾淨 checkout，commit 654c303） | harden-soc 在 `RepairDesignPostGRT` 隨機中止（見上方第 6 點）。同一個 run 從該步接續（`--from OpenROAD.RepairDesignPostGRT`）跑完後與 golden 比對：320 個 metrics 完全相同，`check_soc.py` 全部 PASS |
| 第二次 `make phase3`（乾淨 checkout，commit 658b6dd，加上重試） | harden-soc 一次跑完，沒有觸發重試（`runs/soc_top_signoff/` 沒有 `retries.txt`）；320 個 metrics 與 golden 完全相同 |
| 第三次 `make phase3`（乾淨 checkout，commit acbc126） | harden-soc 一次跑完，沒有重試；320 個 metrics 與 golden 完全相同 |
| 第四次 `make phase3`（乾淨 checkout，commit 53529c6，正式結果） | harden-soc 一次跑完，沒有重試；320 個 metrics 與 golden 完全相同。harden-core 的 325 個 metrics 也與 picorv32_core 的 golden 完全相同 |

## Checker qualification（植入錯誤後，checker 會不會 FAIL）

「抓到」的意思是：在**預期的** checker、以**預期的原因** FAIL（`project-plan.md` §7.3）。

### PnR 與 signoff（`make neg-pnr`）

| # | 植入 | 預期 FAIL 的 checker | 與計畫的差異 |
|---|---|---|---|
| P01 | signoff SDC 加 `set_clock_uncertainty -setup 30` | `Checker.SetupViolations` | 同計畫；植入加在 run 實際用的 signoff SDC 後面（直接改 config 變數會被 SDC 蓋掉） |
| P02 | signoff SDC 加 `-hold 5` | `Checker.HoldViolations` | 同上 |
| P03 | signoff SDC 加 `set_max_transition 0.05` | `Checker.MaxSlewViolations` | 同上 |
| P04 | SRAM derate 改 10 | ss corner 的 `Checker.SetupViolations`，且 hook 印出 10 | 同計畫 |
| P05 | 刪掉 SRAM 電源環上的 via（最終 DEF，8 個） | `Checker.LVS` | 計畫是 `PDN_CONNECT_MACROS_TO_GRID=false` 並移除 RTL 電源連接：只試了前者，產生的電源網路與原本逐字相同（core 的 strap 本來就跨過 SRAM 電源環），植入沒有生效。刪 via 之後沒有重跑 `Checker.PowerGridViolations`，所以不知道它會不會也 FAIL |
| P06 | SRAM LEF 的 gate 面積除以 1000 | OpenROAD `check_antennas`：59 個違規（正常 LEF：0） | 計畫是關掉 antenna repair；改成證明 antenna 檢查看得到接到 SRAM 輸入的線。這是在 LibreLane 外面直接用 OpenROAD 讀 LEF 與最終 DEF 檢查，沒有經過 LibreLane 的 step、metrics 與 `check_signoff.py` |
| P07 | metrics 的 IR drop 改 0.2 V | `check_signoff.py [max]` | 計畫是 PDN pitch 放大 4 倍：目前 IR drop 只有 0.3 mV，門檻 90 mV，推估放大 4 倍仍遠低於門檻，植入不會讓 checker FAIL；所以只測 checker 本身 |
| P08 | 最終網表 `csb1` 浮接 | `check_soc.py port1_tieoff` | 計畫預期 `Checker.DisconnectedPins`；改由專用 checker 判 |
| P09 | 最終 DEF 的 `sram0` 移 10 µm | `check_soc.py placement` | 計畫還包括 halo 設 0 → overlap／DRC，沒有做 |
| P10 | GDS 在 SRAM 外加一條 0.05 µm 寬的 met2 | `Checker.KLayoutDRC` 與 `check_soc.py magic_drc`（框外 1 個） | 計畫的 `Checker.MagicDRC` 換成 `check_soc.py magic_drc`（見「與計畫不同的地方」第 2 點）。第一版只測了 KLayout，說明卻寫兩個都測，收尾自查時補上 |
| P11 | 只改 KLayout 那份 GDS | `Checker.XOR` | 同計畫 |
| P12 | metrics 的 instance 數減 10% | `check_signoff.py` golden 比對 | 計畫是讓某個輸出變常數；改成只測 checker 本身 |
| P13 | signoff SDC 刪掉 `set_output_delay` | `check_soc.py` 的 check_setup 讀取函式（9 corner 各報 42 個未受約束的輸出）；`neg_pnr.py` 呼叫 `read_check_setup` 後自己套用同一份允許清單，不是執行 `check_soc.py sta_setup` 那一列 | 新增（§7.2 的未受約束 endpoint）。用 `unset_output_delay` 植入無效，見下方「本階段找到的 checker 問題」 |
| P14 | 最終網表 `sram0` 改名 | `check_soc.py macro` | 新增 |
| P15 | 斷線 pin 報告改成 1 個 critical | `check_soc.py disconnected` | 新增 |
| P16–P19 | config 少一個 RTL 檔、padded.lib 改一個延遲表、SRAM LEF 少一行 antenna 資料、MACROS 改用 PDK 原本的 .lib | `check_inputs.py` 的 rtl_files／padded_lib／antenna_lef／macro_lib | 新增 |
| P20 | `resolved.json` 的 SRAM .lib 改成 PDK 原本的 | `check_inputs.py --resolved` | 新增 |

### 其他

| checker | 植入 | 結果 |
|---|---|---|
| `run_eqy.py`（soc_top） | SRAM `din0[5]` 卡 0、`csb0` 反相、`host_rdata[7]` 反相、mux 兩輸入對調 | 4/4 FAIL。其中 3 個是 EQY 在切分時因為名稱對應互相矛盾而拒絕，沒有走到證明階段；只有 `din5_stuck0` 是分區證明失敗（18099/18100）加上常數規則 |
| `run_eqy.py`（picorv32_core） | 與 Phase 2 同類的 7 個網表錯誤，重新植入在本階段的網表上（Phase 2 共 10 個；`mux_swap` 選的是第一個推 flip-flop D 的 mux2_1，不一定是 Phase 2 那一顆）。其中 3 個是 Phase 2 GL 模擬漏掉的那一類 | 7/7 FAIL（1090 秒）。被抓到的方式：<br>• 4 個是分區證明失敗，加上常數規則：`count_cycle45_stuck1`、`count_instr40_stuck1`、`buserr_irq_stuck0`、`x8_bit24_stuck0`，各有 1 個分區沒證明。GL 模擬漏掉的 3 個都在其中。<br>• 2 個是 EQY 在切分時拒絕：`instr_inverted`、`mux_swap`。<br>• 1 個只靠常數規則：`wdata3_stuck0`，其餘 15136 個分區照樣證明通過 |
| `run_gl_soc.py`（lockstep） | 與 EQY soc_top 相同的 4 個網表錯誤，每個跑 11 支測試（不含最長的 memtest、boot_uart_max） | 4/4 FAIL，都是 RTL 與網表不一致（`make neg-gl-soc`）。`din5_stuck0`、`csb0_inverted`、`host_rdata7_inverted` 在 11/11 支測試都不一致；`mux_swap` 只有 `muldiv` 這 1 支抓到，其他 10 支沒用到那顆 mux 所在的邏輯，這就是 GL 模擬覆蓋範圍受 firmware 限制的例子 |
| `librelane_flow.sh`（重試） | 用假的 nix-shell 模擬 7 種情況：一次成功、GRT-0229 後成功（1 次、2 次重試）、連續 3 次 GRT-0229、其他錯誤、同一步但不同訊息、GRT-0229 後接其他錯誤 | 7/7 符合預期：只有 GRT-0229 會重試、總共最多跑 3 次，其他錯誤直接 FAIL（`make test-flow-retry`）。真的 LibreLane 上只手動接續過一次，第二到第四次 `make phase3` 都沒有觸發重試 |
| `provenance.py`（來源追溯） | 未追蹤檔、修改過的檔、submodule 沒初始化、LibreLane 版本不符、PDK 版本不符、run 中 HEAD 改變、`resolved.json` 的 PDK／LibreLane 不符、紀錄檔不見 | 9 個 negative test 都在預期的那一列 FAIL，2 個 positive test（乾淨 clone 的 record 與 verify）PASS，共 11/11（`make neg-provenance`） |

### 本階段找到的 checker 問題（已修正）

| 問題 | 怎麼發現 | 修正 |
|---|---|---|
| EQY 把對應到常數的 bit 直接換成常數、不證明：輸出被植入卡 0 時，15136 個分區照樣全部證明通過 | `neg_eqy.py wdata3_stuck0` | partition log 出現 `found constant ... bit` 就 FAIL（正向 run 沒有這一行） |
| P05 第一版植入沒有生效 | 比對 PDN 輸出逐字相同 | 改刪 via → LVS |
| P06 第一版：換 LEF 重跑 antenna check，讀的仍是 ODB 裡舊的 antenna 資料 | 結果與換之前完全相同 | 直接用 OpenROAD 讀 LEF 與 DEF 檢查 |
| P13：`unset_output_delay` 不加 `-clock` 什麼都沒刪；加了 `-clock` 之後路徑不再被檢查，但 `check_setup` 仍當作有設，不報警告 | 植入後 check_setup 沒有新警告；單步重跑 STA 探針確認 | 改成產生真的少一行的 SDC，check_setup 報 42 個未受約束的輸出 |
| P10 的說明與程式不符 | 收尾自查 | 補 Magic DRC 重跑與 `magic_drc` 斷言 |
| 下游步驟（`run_eqy.py`、`run_gl_soc.py`）只看 `signoff.txt`，soc 專用檢查或輸入一致性 FAIL 的 run 也會被拿去用 | 收尾自查 | harden 把整體判定寫進 `result.txt`，下游只認 `harden-<x>: PASS` |
| §7.2 來源追溯沒做（Phase 2 延到本階段） | 收尾對照 Phase 2 exit review | `provenance.py` + `neg_provenance.py`；`phase3` 加跑 harden-core，讓 eqy-core 用的 run 也有來源追溯 |
| `check_soc.py` 的 macro、disconnected 兩列，`check_inputs.py` 整支，以及 GL lockstep，都沒有可重跑的 negative test | 收尾自查 | P14–P20、`make neg-gl-soc` |
| `make gl-soc`、`make neg-gl-soc` 沒有宣告要先編 firmware（`fw/build/` 不在版控）。開發目錄有舊的 firmware，所以只有乾淨 checkout 會出錯 | 第二次 `make phase3`：13 支測試有 12 支報找不到 firmware，checker 正確判 FAIL | 兩個 target 加上依賴 `fw`（commit `acbc126`） |
| neg-gl-soc 的 `csb0_inverted`：植入腳本（與 EQY 共用）把新 wire 宣告在 module 最後，Yosys 接受、Icarus 編譯失敗。`neg_gl_soc.py` 寫好後沒有單獨跑過就加進 `make phase3` | 第三次 `make phase3`：3/4，checker 正確地不把編譯失敗算成抓到 | 宣告移到 `sram0` 前（commit `53529c6`）；修正後 GL 11/11 支測試報不一致，EQY 照樣 FAIL |

## 與計畫不同的地方

1. **EQY 的範圍**：計畫 §7.1 L4 要證 RTL vs 最終網表。實際證的是合成網表 vs 最終網表。RTL vs 網表遇到兩個問題：Yosys 把狀態機重新編碼（`cpu_state` 8-bit one-hot → 6-bit、`mem_wordsize` → 3-bit one-hot，未解決），以及上電值未定、寫入後恆為常數的暫存器被換成常數（部分解決）（`signoff/eqy/README.md`）。RTL → 合成網表這一段只有 gate-level 模擬（gl-core、gl-soc），覆蓋範圍受 firmware 限制，見已知限制 11。
2. **Magic DRC**：計畫 §6.3 用 abstract DRC 並保留 `ERROR_ON_MAGIC_DRC=true`。abstract 模式每條 row 都有 `nwell.4` 假錯誤，所以改用完整 GDS。SRAM 的 GDS 在標準規則下有大量違規（放在 soc_top 裡、SRAM 外框內約 466 萬個；單獨檢查約 558 萬個），只好設 `ERROR_ON_MAGIC_DRC=false`。計畫擔心這樣會蓋掉 top-level 的真錯誤，改由 `check_soc.py magic_drc` 判定：框外必須是 0，框內只能出現 SRAM 單獨檢查時也有的規則。P10 證明框外的違規會被抓到。
3. **Antenna**：計畫 §6.4 用 heuristic diode insertion，加上自寫的線長 checker。實際是 heuristic diode 插了 10,231 顆、繞線不收斂，改成在 SRAM LEF 補上 `ANTENNAGATEAREA`（ADR-0008），讓 OpenROAD 的 antenna 檢查看得到 SRAM 輸入線（P06 在 LibreLane 外直接用 OpenROAD 證明）。沒有另寫線長 checker：port 0 的輸入線最長約 202 µm（`DESIGN_REPAIR_MAX_WIRE_LENGTH` 200 µm）；port 1 的 tie-off 線最長 620 µm，靠 antenna LEF 涵蓋。
4. **unannotated net = 134**，不是 0：91 個 CTS dummy load 輸出、32 個沒用的 SRAM 讀取埠輸出（`dout1`）、11 個沒用的 tie cell 輸出。這些都沒接到繞線，所以沒有寄生值可以標註。limits 設成「剛好 134」。
5. **max slew**：ADR-0009 曾把 signoff 放寬到 1.0 ns，已撤回；保留 PnR 的 fanout 8。
6. **GDS 輸出工具**：改用 KLayout（Magic 的 GDS 有 13 個 top cell）。
7. **GL 模擬的比對方式**：計畫 §7.1 L2 是比對 bus transaction trace。實際是把 RTL 與網表兩份 SoC 放在同一個 testbench（lockstep），每個 cycle 比對 soc_top 所有輸出，以及 SRAM port 0 的輸入腳：`csb0` 每個 cycle 比；`web0`、`addr0`、`wmask0` 只在存取時（`csb0`=0）比；`din0` 只比寫入的 byte；RTL 是 X 的 bit 不比；`dout0` 不比（`dv/monitors/gl_lockstep.v` 檔頭）。
8. **SRAM 位置**：計畫 §5.4 是右上角留 20–30 µm channel。實際讓 halo 蓋過 core 邊界，不留窄 row（ADR-0006 補充）。
9. **negative test**：P05–P09、P12 的植入方式改了，P13–P20 是新增的（見上表）。
10. **`make phase3` 也重跑 harden-core**：讓 eqy-core 用到的 run 也有來源追溯。
11. **§7.2 的「最長線 ≤ 門檻」沒有訂門檻**：最長線由 golden 鎖住；flow 的 `Checker.WireLength` 因為沒有設門檻而略過。
12. **`check_setup` 允許 `sram0/clk1` 沒有 clock**：port 1 的 clock 接 0，這是唯一允許的警告（`check_soc.py` 的 `CHECK_SETUP_ALLOWED`）。
13. **計畫 §7.5 的 `make harden D=<design>`（tag = git sha）沒有做**：Phase 2 決定和來源追溯一起延到本階段（`docs/phase_exit/phase2.md` 限制段），本階段只做了來源追溯；tag 仍是固定的 `soc_top`／`picorv32_core`，run 的來源由 `provenance.json` 記錄。通用的 harden target 留到 Phase 4 做 `make regress` 時處理。

## 已知限制（帶到後續階段）

1. **SRAM 的時序是工程假設**：padded.lib 的數字（例如 clk→dout 10 ns、setup 1 ns）不是特性化結果（ADR-0007）。同一份 .lib 也套到 FF corner，所以 SRAM→flop 的 hold 分析偏樂觀（`project-plan.md` §6.2 第 4 點要求明示）。Phase 3.5／6 用 OpenRAM 特性化校正。
2. **LVS 中 SRAM 是 black box**：只驗 pin 的連接，不驗 SRAM 內部。
3. **clock duty cycle 沒有算進約束**：最差 setup 路徑是半週期路徑（SRAM 下降緣送出、上升緣接收），min_ss 剩 3.55 ns。STA 假設 duty cycle 是 50%。duty 每偏 1% 少 0.4 ns，偏到約 59% 時餘裕就用完。0.25 ns 的 clock uncertainty 是 LibreLane 預設值，不含 duty cycle 偏移。clock 來源在 Phase 7 確定（Caravel 的 `wb_clk_i`／`user_clock2`）後重算。
4. **EQY 的證明步驟只在「卡成常數」的錯誤上驗證過**：
   - 5 個分區證明失敗的案例（soc_top 的 `din5_stuck0`，picorv32 的 4 個），失敗的分區正好就是被換成常數的那個 bit。
   - 反相器、mux 對調這 5 個非常數的錯誤，全部在切分時因為名稱對應矛盾而被拒絕，沒有走到證明。
   - `wdata3_stuck0` 只靠常數規則。
   - 獨立審查另外做了一個實驗：把一顆 `nand2_2` 換成 `nor2_2`、名稱不動，EQY 正常切分，18100 個分區中 1 個證明失敗（`soc_top._14295_.B`，sat 給出反例），沒有常數也沒有名稱衝突。所以證明步驟抓得到非常數的錯誤，但這個案例還沒加進 `neg_eqy.py`（Phase 4）。
5. **金屬密度沒有 checker，實測不合格**：Classic flow 不檢查 density（`KLayout.Density` 只在 Chip flow）。實測 met1 25.8%、met2 14.3%、met3 7.8%、met4 3.5%、met5 2.6%，都低於下限 35%（met5 45%），chip-level 一定要補 metal fill（`drc-signoff` skill 的 density 一節）。
6. **IR drop 只做 static**：電流來自 OpenSTA 的預設 switching activity，SRAM 的電流來自解析模型 .lib，只能當粗估。
7. **多數 PnR negative test 不重跑工具**：P06–P09、P12–P20 是在檔案副本上植入、只重跑 checker（`neg_pnr.py` docstring）。其中 P07、P12、P15 改的是報告或 metrics，只測 checker 本身，不是從版圖或合成植入錯誤。
8. **golden 只在同一環境下逐項比對**：換平台需要重建（同 Phase 2）。
9. **`RepairDesignPostGRT` 的隨機中止**是 OpenROAD 的問題，用重試繞過，沒有解決。位置都在 clk pin 所在的 GCell；推測與 die 邊緣的 clk pin 和 CTS 的 non-default rule 有關，尚未用實驗確認。重試次數記在 `runs/<tag>_signoff/retries.txt`。重試路徑在真的 LibreLane 上只手動接續過一次（`docs/notes/grt0229_repro.md`）。
10. **signoff 條件本身的依據**：目前用的是 LibreLane 與 PDK 的預設值，多數沒有成分說明。逐項檢討在 `docs/notes/signoff_criteria_soc_top.md`（方法在 skill `signoff-criteria`）。主要缺口：
    - 半週期路徑沒有 duty cycle 預算：nom_ss 下 duty 59% 時 slack 就變負（已重現）。
    - 沒有 min pulse width 檢查。
    - IR 上限 90 mV 與 ss corner 電壓隱含的 20 mV 預算不一致。
    - 溫度反轉的 corner 沒跑。
    - IO hold 等於沒檢查。
    - SI 沒有分析。

    建議的處理順序列在該文件的「Phase 4 待辦」，其中改門檻的項目要由使用者決定。
11. **RTL → 合成網表沒有 formal 證明，Phase 2 的覆蓋缺口還在**：
    - Phase 2 決定提前做 EQY，是為了補 GL 模擬漏掉的 `rdcycleh`／`rdinstreth`、bus-error IRQ（`docs/phase_exit/phase2.md` 限制 7）。
    - 但 EQY 證的是合成之後那一段，合成這一步本身仍只靠 gate-level 模擬；firmware 沒用到的邏輯（例如 `mux_swap` 只有 `muldiv` 抓到）沒有任何檢查。
    - 處理方向：解決 RTL vs 網表的狀態機重新編碼問題（`signoff/eqy/README.md`），或補 firmware 測試。留到 Phase 4。
12. **下游步驟不確認 run 是不是現在這個 commit 產生的**：
    - `run_eqy.py`、`run_gl_soc.py`、`run_gl_core.py`、`neg_pnr.py` 只要求 harden 的 `result.txt` 是 PASS。
    - 在 commit A harden 之後改了 RTL（commit B），單獨跑 `make eqy-soc` 仍會用 A 的網表而 PASS；`provenance.json` 有記 commit，但沒有程式拿它來比。
    - 「harden 判 FAIL 時下游會拒絕」也沒有 negative test。
    - `make phase3` 依序執行，不受影響；`make -j phase3` 會互相刪檔，結果是 FAIL 而不是假 PASS（Makefile 沒有 `.NOTPARALLEL`）。
13. **來源追溯不檢查 LibreLane 與 PDK 的內容**：
    - LibreLane 只比 clone 的 commit；clone 裡改過的檔案不會被發現（獨立審查實測：改 `base.sdc` 後 `provenance: PASS`）。signoff 的 SDC 會 `source` clone 裡的 `base.sdc`，LVS／DRC 腳本也在 clone 裡。
    - PDK 只比路徑裡的版本 hash，不比檔案內容。
14. **Magic DRC 在 SRAM 外框內只比規則種類**：外框內多出一個已有規則的新錯誤，`check_soc.py magic_drc` 照樣 PASS（獨立審查用假報告實測），只剩 golden 的總數擋得住，而 golden 每次改設計都要重建。這次的報告已經逐一比過位置：4,665,810 個錯誤都對得回 SRAM 單獨檢查的同規則錯誤，0 個無法解釋（審查 agent 的實驗），所以本次結果沒有藏錯。
15. **部分 PnR negative test 的「整體 FAIL」斷言沒有作用**：P08、P09、P10 的 Magic 部分、P14、P15 用的假 run 沒有 STA 結果，`sta_setup` 那一列永遠 FAIL，所以只證明了「被植入的那一列印出 FAIL」，沒有證明「這一列會讓 `soc-checks` 判 FAIL」；也沒有「沒植入時假 run 判 PASS」的 positive control。P13 沒有跑到 `check_soc.py` 的主判定。
16. **neg-eqy 不檢查 FAIL 的位置**：任何一個分區沒證明、任何常數或名稱衝突都算抓到，沒有確認和植入的 instance 有關。

    12–16 是獨立審查找到的 checker 漏洞，都不影響本次結果（理由見各點）。修正會改到 `make phase3` 用的程式，依規則要在乾淨 checkout 重跑一次，所以留到 Phase 4 開頭一起做。

## 使用者決定（2026-10-04）

- checker 漏洞（已知限制 12–16）：Phase 4 開頭一起修。
- IR drop 上限：90 mV 改成 20 mV，與 ss corner 的 1.60 V 和 Caravel 最低供電 1.62 V 一致。
- SRAM 的 instance derate：1.5／0.7 改成 1.575／0.665，把 ±5% 的 OCV 乘進去。
- 「nom_tt setup ≥ 週期 10%」：降為只報告、不判 FAIL；時序餘量改放在最慢 corner 的 uncertainty，並列出成分。
- 以上門檻都在 Phase 4 和漏洞修正一起實作，再在乾淨 checkout 完整跑一次。細節在 `docs/notes/signoff_criteria_soc_top.md`。

## 獨立審查（2026-10-04）

結案前請兩個沒參與實作的 agent 反向檢查：

- **文件核對**：逐條比對本文的數字與說法和第四次 run 的證據。找到 6 個寫錯的數字或事實（來源追溯的案例數、clock skew、logic 區使用率、cell 組成、最長線的來源、密度），以及多處說得太滿或該講沒講的地方，都已更正；漏寫的限制補進已知限制 11–13（12、13 兩份審查都有提到）。
- **找 checker 漏洞**：找到 5 個漏洞，列為已知限制 12–16。沒有一個會讓本次結果變成假 PASS。實驗紀錄在 `docs/notes/phase3_review/`。

## 交付物

- `pnr/librelane_flow.sh`（GRT-0229 重試）、`pnr/test_librelane_flow.sh`。
- `pnr/soc_top/`：`config.json`、`pin_order.cfg`、`pnr.sdc`、`signoff.sdc`、`sta_extra_corner.tcl`、`run.sh`、`check_inputs.py`、`check_soc.py`、`neg_pnr.py`、README。
- `ip/sram/sky130_sram_2kbyte_1rw1r_32x512_8/`：`gen_padded_lib.py`、`padded.lib`、`gate_area.py`、`gen_antenna_lef.py`、antenna LEF。
- `signoff/`：
  - `limits/soc_top.toml`、`golden/soc_top/`、`waivers/soc_top/sram_magic_drc_baseline.json`
  - `eqy/`（`run_eqy.py`、`neg_eqy.py`、README）
  - `scripts/provenance.py`、`scripts/neg_provenance.py`
- `dv/gl_soc/`（`run_gl_soc.py`、`neg_gl_soc.py`、README）、`dv/monitors/gl_lockstep.v`；修改：`dv/tb/tb_soc.v`、`dv/scripts/dvlib.py`、`dv/gl_core/run_gl_core.py`（只認 `result.txt`）。
- 修改：`pnr/picorv32_core/run.sh`（來源追溯與 `result.txt`）、`signoff/scripts/check_signoff.py`（`[max]` 上限）。
- `docs/notes/signoff_criteria_soc_top.md`、`docs/notes/grt0229_repro.md`。
- ADR-0006 補充、ADR-0007～0009。
- `.claude/skills/`（流程 skill 與經驗紀錄）。
- Makefile 新增的 target：`harden-soc`、`eqy-soc`、`neg-eqy-soc`、`gl-soc`、`neg-gl-soc`、`neg-pnr`、`neg-provenance`、`test-flow-retry`、`eqy-core`、`neg-eqy-core`、`phase3`。
