# Phase 5 exit review：把 CPU 換成 Hazard3

日期：2026-10-08　結論：**PASS**（使用者 2026-10-08 確認結案）。commit `71b1454` 的兩份乾淨 checkout regression：Hazard3 `make regress` 21/21、PicoRV32 `make regress-picorv32` 26/26，三次 harden 都與 golden 逐項相同。獨立審查找到的 8 個 checker 漏洞與 IR 超標都已修正後重跑；exit criteria 第 7b 項（flow 設定只需改 design 層）未達成，使用者決定接受為與計畫不同。

Exit criteria 出處：`project-plan.md` §8 Phase 5。
- 原文：「submodule Hazard3；AHB5 寫入資料在 data phase，接 1RW SRAM 需 write buffer 或 wait state；建議用 `hazard3_cpu_2port`，SRAM port 1 負責 I-fetch；測試以 Hazard3 的 rvcpp ISS trace 比對；加裝 xPack toolchain（newlib）」
- exit 條件：「L0–L5 全 PASS；flow 設定只需改 design 層」
- §10 第 4 項：「Hazard3 以同一套 flow 設定完成 signoff」

一併帶進本階段的項目：
- Phase 4 已知限制 1–13（`docs/phase_exit/phase4.md`）；
- Phase 3.5 已知限制 1–16 與使用者決定 7、9（`docs/phase_exit/phase3_5.md`）。其中限制 16 是 12 個 checker 漏洞，決定在 Phase 5 開頭與 `run.sh` 的修改一起修。

處理結果見「帶進本階段的項目」一節。

## 正式 run

兩份 regression 都在乾淨的 worktree 執行：
- 建立方式：`git worktree add --detach` 加 `git submodule update --init --recursive`，開始時沒有修改或未追蹤的檔案。
- `.tools/` 不在 git 裡，用 `LIBRELANE_DIR`、`XPACK_DIR` 指向主 checkout 已安裝的版本。`env-check-flow` 會檢查兩者。

| regression | commit | 時間 | exit code | 結果 | 證據 |
|---|---|---|---|---|---|
| `make regress`（Hazard3，21 項） | `71b1454` | 2026-10-08，109 分鐘 | 0 | **21/21 PASS** | worktree `p5final_h3` 的 `runs/regress/summary.md`、`junit.xml`；console `runs/p5final_regress_hazard3.console` |
| `make regress-picorv32`（26 項） | `71b1454` | 2026-10-08，124 分鐘（Hazard3 那輪之後依序跑） | 0 | **26/26 PASS** | worktree `p5final_pico` 的 `runs/regress_picorv32/summary.md`、`junit.xml`；console `runs/p5final_regress_picorv32.console` |

- **重試**：PicoRV32 的 `harden-soc` 第一次嘗試在第 44 步（`ResizerTimingPostGRT`）遇到已知的 GRT-0229 而停止，依有上限的重試從該 step 接續完成（`runs/soc_top_signoff/retries.txt`）。Hazard3 沒有重試。
- **golden 比對**：三次 harden 的 metrics 都與 golden 逐項相同：Hazard3 436 個、PicoRV32 SoC 435 個、picorv32_core 325 個。
- **每次 harden 的 criteria review**（CLAUDE.md 規則 9）：
  - `p5final_h3/runs/soc_top_hazard3_signoff/criteria_review.md`；
  - `p5final_pico/runs/soc_top_signoff/criteria_review.md`；
  - `p5final_pico/runs/picorv32_core_signoff/criteria_review.md`：`harden-core` 第一次自動跑 `review_criteria.py`。

之前幾次乾淨 checkout 不當作結案證據（依時間順序）：
- `941e1cb` 的 `make regress` 在第 6 項 `core-hazard3` FAIL：乾淨 checkout 沒有 `.tools/` 下的 xPack toolchain。log 沒有保存，紀錄只在 `7348fab` 的 commit message。修正見 `7348fab`。
- `7348fab`：Hazard3 21/21、PicoRV32 26/26 都 PASS。之後的獨立審查找到 8 個 checker 漏洞與 IR 超標，使用者決定修正後重跑（「使用者決定」1、2）。
- `5aaf036`（修正與新 PDN 之後）：Hazard3 21/21 PASS；PicoRV32 在 `harden-soc` FAIL：版圖誤差依決定清空，第一次量到 run 之間的差異（diode 差 1 顆等 10 個 metric）。使用者決定再量樣本、依實測訂誤差（「使用者決定」4），並在 `71b1454` 重跑兩輪。

除非另外註明，下面的數字取自 `71b1454` 兩次乾淨 regress 的 run，它們與 golden 逐項相同。golden 的來源 run 是開發 worktree 的 `1dee974`（`PDN_HWIDTH` 4.8 後的第一次 harden），見 golden README 與 ADR-0017。

## Exit criteria

| # | 項目 | 結果 | 證據 |
|---|---|---|---|
| 1 | submodule Hazard3 | PASS：`third_party/hazard3`（v1.1.1，`8af9929`） | `.gitmodules`；ADR-0011 |
| 2 | AHB5 寫入資料在 data phase：write buffer 或 wait state | PASS，採 **wait state**：<br>• `hazard3_cpu_1port` 加轉接器 `rtl/cpu/soc_ahb2native.v`<br>• `hready` = 0 直到 `mem_ready`<br>• 轉接器的植入錯誤 H01–H04 都被抓到 | `soc_ahb2native.v` 檔頭；ADR-0011；`dv/bugs.toml` H01–H04；`neg-rtl` 36/36 |
| 3 | 以 rvcpp ISS trace 比對 | PASS：<br>• riscv-tests 65/65，2 項不支援：`rv32mi-p-pmpaddr`、`rv32ui-p-fence_i`<br>• 逐指令比對 48/48 個測試、13,881 條指令。rv32mi 不比，因為 rvcpp 的 CSR 模型是全功能設定<br>• negative test 1/1：`EXTENSION_M=0` 時 rv32um 的 8 個測試都 FAIL<br>• rvcpp 加了 `rvcpp_fence.patch`，把 `fence` 當 no-op | `make core-hazard3`；`dv/core_hazard3/run.py`；`core-migration-hazard3` 經驗紀錄 |
| 4 | xPack toolchain | PASS：15.2.0，`make xpack-fetch` 釘 sha256；`env-check` 檢查 `--version` 是 xPack、找得到 newlib 的 `libc.a`（審查第 8 項修正，`neg-regress` 8/8） | `toolchain.md`；`env/fetch_xpack.sh`、`env/check_env.sh` |
| 5 | L0–L5 全 PASS（Hazard3） | PASS，見下表 | `p5reg` 的 `runs/regress/summary.md` |
| 6 | Hazard3 完成 signoff | PASS：15 個 corner 的 setup 與 hold 都 PASS，DRC、LVS、antenna 都是 0 | `p5reg` 的 `runs/soc_top_hazard3_signoff/signoff.txt` |
| 7a | 同一套 flow 設定（§10 第 4 項） | PASS：<br>• 兩個 CPU 的 config 只差 `VERILOG_FILES`、`VERILOG_INCLUDE_DIRS`、`VERILOG_DEFINES`，每次 harden 都檢查<br>• negative test P37–P39 | 兩次乾淨 regress 的 `harden-soc.log`：`[PASS] cpu_config`；`check_inputs.py cpu_config` |
| 7b | flow 設定只需改 design 層 | **未達成**。換 CPU 後 Hazard3 的時序修不過，迫使下列改動，而且兩個 CPU 一起改：<br>• 4 項 flow 設定（ADR-0012、0013、0014、0016）<br>• 週期 43 → 44 ns<br>• flow 程式碼：`pnr/librelane_plugin_arvinsa/`（繼承 `OpenROAD.CTS` 的替換 step）、`pnr/librelane_flow.sh`（重試範圍、`PYTHONPATH`）<br>• checker：`check_signoff.py`（ADR-0015）、`signoff/limits/`<br>LibreLane 與 PDK 本身沒有改。**使用者決定 3：接受為與計畫不同** | 「與計畫不同的地方」 |
| 8 | PicoRV32 版仍 PASS（ADR-0011：移到 `make regress-picorv32`） | PASS：26/26，含 PicoRV32 單獨 harden、`gl-core`、`neg-gl-core` 2/2、`eqy-core`、`neg-eqy-core` 11/11 | `p5reg2` 的 `runs/regress_picorv32/summary.md` |
| 9 | 帶進本階段的項目 | 見「帶進本階段的項目」 | — |

L0–L5 與 Hazard3 regression 的對應（層級定義見 `project-plan.md` §7.1）：

| 層級 | target | 結果 |
|---|---|---|
| L0 Lint | `lint`（另有 `env-check-flow`、`py-check`） | PASS |
| L1a Core ISA regression | `core-hazard3` | 65/65、trace 48/48 |
| L1b SoC RTL sim | `regress-rtl`、`neg-rtl` | 30/30、36/36 |
| L2 合成與 gate-level 模擬 | `synth-check`、`gl-soc` | PASS、15/15 |
| L3 PnR signoff | `harden-soc`、`neg-pnr` | PASS、63/63 |
| L4 Equivalence | `eqy-soc`、`neg-eqy-soc` | PASS、13/13 |
| L5 Post-layout GL sim | `gl-soc-powered`、`neg-gl-soc` | 15/15、8/8 |

- L4 的 EQY 範圍沿用 Phase 4：比的是合成網表 vs 最終網表，不是計畫寫的 RTL vs 最終網表（Phase 4「與計畫不同的地方」第 2 點）。
- L2 的 `gl-soc` 用的是最終網表，沿用 Phase 3 的做法。

## signoff 結果（44 ns）

| 項目 | PicoRV32 SoC | Hazard3 SoC |
|---|---|---|
| setup 最差 | +0.789 ns（min_ss_n40C_1v60） | +1.114 ns（min_ss_n40C_1v60） |
| hold 最差 | +0.080 ns（min_ff_n40C_1v95） | +0.109 ns（min_ff_n40C_1v95） |
| 最差 setup 路徑 | SRAM 半週期路徑（`sram0` 在下降緣送出，flip-flop 在上升緣接收） | 同左 |
| die／core 面積 | 800,000／769,005 µm² | 800,000／769,005 µm² |
| standard cell | 31,966 顆，254,358 µm² | 30,423 顆，238,995 µm² |
| flip-flop | 2,639 | 2,152 |
| hold buffer（網表中的 `dlygate4sd3_1`） | 3562 | 2721 |
| `power__total`（內部＋切換＋漏電） | 8.73 mW（5.91＋2.47＋0.35） | 19.33 mW（10.60＋8.39＋0.33） |
| PDN | met5 strap 4.8 µm（`PDN_HWIDTH`，ADR-0017），met4 1.6 µm | 同左 |
| 繞線長度 | 863,205 µm | 796,279 µm |
| IR：VDD 降壓＋GND 抬升（nom_tt、一側供電；上限 20 mV） | 2.03＋2.03＝4.06 mV | 5.02＋4.96＝9.98 mV |
| IR 最壞組合（ff 電流＋ss 金屬電阻，`ir_worst.py`；上限 20 mV） | 5.72 mV | 14.13 mV |
| DRC（繞線、KLayout）／LVS／XOR／antenna | 全部 0 | 全部 0 |
| Magic DRC | 4,746,079（全在 SRAM 框內，每一個都對得上 SRAM 單獨檢查時的位置；met5 加寬前是 4,665,810） | 同左 |

數字的出處與讀法：
- 出處：`signoff/golden/{soc_top,soc_top_hazard3}/metrics.json`，與兩次乾淨 regress 相同。hold buffer 數取自 criteria review 的 INFO 列；IR 合計是兩個 metric 相加。
- `power__total` 是 LibreLane 最後寫入的那個 corner 的值，不是各 corner 的最大值（`librelane-run-debug` 規則 4）。
- Hazard3 的功耗約為兩倍，其中切換功耗是 3.4 倍（8.39 對 2.47 mW），原因沒有查證。

**IR：獨立審查後發現超標，已修正**（使用者決定 1，ADR-0017）：
- Phase 4 允許 flow 只用 nom_tt 判 IR，依據是「最壞組合（ff 電流＋ss 金屬電阻）在 PicoRV32 版圖是 11.46 mV，仍低於 20 mV」（`docs/notes/ir_worst_case_soc_top.md` 第 36 行）。
- Hazard3 的 nom_tt 已到 18.28 mV。照 Phase 4 的比例 1.40 推算，最壞組合約 25.6 mV。
- 用 Phase 4 的同一方法（`docs/notes/ir_study/`，模型 C 一側供電，LibreLane 單步重跑 `OpenROAD.IRDropReport`）在兩次乾淨 regress 的版圖上實測（2026-10-08）：

| design | 組合 | VDD 降壓 | GND 抬升 | 合計 | EM 最高（via4，假設單一 cut） |
|---|---|---|---|---|---|
| Hazard3 | nom_tt（重現檢查，等於 flow 的 9.18／9.09 mV） | 9.18 | 9.09 | 18.28 | — |
| Hazard3 | ff 電流＋ss 金屬電阻 | 12.94 | 12.81 | **25.75（超過 20 mV）** | 78.4% |
| PicoRV32 | nom_tt | 3.72 | 3.68 | 7.40 | — |
| PicoRV32 | ff 電流＋ss 金屬電阻 | 5.20 | 5.15 | 10.36 | 30.2% |

- 最差的 cell 在兩種條件下都是 `fanout1522`（Hazard3）。最壞組合對 nom_tt 的比例：Hazard3 1.41、PicoRV32 1.40，與 Phase 4 相同。
- 結論：**Phase 4「flow 只用 nom_tt 判 IR」的依據對 Hazard3 不成立**（skill `signoff-criteria` 的判斷：依據不成立）。flow 的 checker 判 PASS，是因為它只看 nom_tt。
- 限制同 Phase 4 研究：只做 static IR；switching activity 用 OpenSTA 預設值；「ff 電流＋ss 金屬電阻」是人為組合的上限，不是真實存在的 corner；供電位置仍是假設（Phase 7 才確定）。
- 量測與 PDN what-if 的結果存在 `docs/notes/ir_study/phase5/`。
- 修正：met5 strap 1.6 → 4.8 µm（`PDN_HWIDTH`，兩個 CPU 共用）；flow 每次 harden 都判最壞組合（`pnr/soc_top/ir_worst.py`，P61、P62）。修正後見上表：Hazard3 14.13 mV、PicoRV32 5.72 mV，via4 EM 約 18%（what-if）。

## 收斂過程

### Hazard3（開發 worktree `p5h3`）

| 次 | commit | 結果與處理 |
|---|---|---|
| 1 | `4461661`（43 ns） | `RepairDesignPostGPL` 跑約 108 分鐘被停，記憶體 92.9 GB。這個數字是當時觀察到的、含 swap 的 physical footprint，不在 run 目錄裡（`docs/notes/repair_design_loop.md`）<br>原因：UART 的 `a2111oi_2` 被換成驅動力很弱的 `a2111oi_1` 後一直修不完<br>→ ADR-0012：resizer 排除弱 cell，harden 前加 `pnr/check_weak_cells.py` |
| 2 | `2251c4a`（43 ns） | ss_n40C setup −4.158 ns（81 條）<br>→ ADR-0013：resizer 也看 ss_n40C，setup 餘量 0.1 ns |
| 3 | `d00214d`（43 ns） | 只剩 max_ss_n40C −0.381 ns<br>→ 使用者決定週期改 44 ns（ADR-0004 Phase 5 補充） |
| 4 | `1292ca4`（44 ns） | −1.131 ns（22 條）<br>→ ADR-0014：開繞線後的 resizer 修復 |
| 5 | `3a28d54` | signoff 時序 PASS（+0.530 ns），但 `harden-soc` FAIL：<br>• unannotated 125 ≠ 上限 133，上限是從 PicoRV32 抄來的<br>• golden 尚未建立<br>→ 上限改為 Hazard3 自己推導的值，建 golden（`d6f3074`） |
| 6、7 | `d6f3074`、`4d309de` | signoff PASS，golden 比對 FAIL（分別 61、11 個 metric 不同）<br>→ ADR-0015：golden 加版圖誤差與「只出現在一邊的 key」 |
| 8 | `9ef0be7` | 440 個完全相同 |
| 9 | `adac1a9` | GRT-0229 在 `ResizerTimingPostGRT` 停止<br>→ `2caad0e`：重試範圍擴大 |
| 10 | `2caad0e` | ADR-0016 的正式 harden：setup +1.116／hold +0.106 ns<br>`harden-soc` FAIL：unannotated 126 ≠ 125，且與舊 golden 不符<br>→ 依使用者決定改上限，從這次 run 重建 golden（`1d13775`） |
| 11 | `1d13775` | 確認 run：434 個完全相同，PASS |
| 12 | `1dee974` | 獨立審查後：`PDN_HWIDTH` 4.8、最壞組合 IR 檢查。最壞組合 25.75 → 14.13 mV，setup +1.114／hold +0.109 ns；只有與舊 golden 比對 FAIL → 重建 golden（`5aaf036`） |

### PicoRV32 SoC（同一份 config 改動後）

| 次 | commit | 結果與處理 |
|---|---|---|
| 1 | `c976976` | min_ss_n40C setup −0.113 ns（9 個 endpoint）<br>原因：CTS 為了讓 SRAM 與 flip-flop 的 clock 到達時間對齊，在 `sram0/clk0` 前插了 10 顆 `delaybuf`。它們的下降緣比上升緣慢，吃掉半週期路徑的時間<br>→ 實驗 A–D，ADR-0016 |
| 2 | `adac1a9` | GRT-0229 停止 |
| 3 | `2caad0e` | setup +0.765／hold +0.079 ns；unannotated 上限 133 → 118，golden 來源 |
| 4 | `1d13775` | 確認 run：436 個完全相同（第 44 步 GRT-0229 接續一次） |
| 5 | `1dee974` | `PDN_HWIDTH` 4.8：最壞組合 10.36 → 5.72 mV，setup +0.789／hold +0.080 ns；重建 golden |
| 6–9 | `5aaf036` | 版圖誤差的樣本：乾淨 regress、樣本 3、樣本 5 三次逐項相同（與 golden 差 1 顆 diode）；樣本 4 在第 44 步因 GRT-0116 中止（見「本階段找到並修正的 checker 問題」第 6 點） |

ADR-0016 的實驗（`docs/decisions/0016-cts-no-macro-latency-balancing.md`）：
- A：hold 餘量 0.1；
- B：`RSZ_DONT_TOUCH_RX`；
- C1、C2：排除 `dlygate`，結果以 `RSZ-0060 Max buffer count reached` 停止；
- D：CTS 加 `-no_insertion_delay`。兩個 CPU 都 PASS，`sram_dout0` 上的 32 顆 hold delay cell 也消失。

LibreLane 3.0.14 沒有變數可以關掉這個行為，所以用 repo 的 plugin 換掉 CTS step，不改 LibreLane 本身。

## 帶進本階段的項目

### Phase 4 已知限制

| # | 限制 | Phase 5 結果 |
|---|---|---|
| 1 | SRAM 時序是假設值 | Phase 3.5 已改成 SPICE 特性化的 .lib。ss_n40C 讀取失敗，那個 corner 仍是佔位值（ADR-0013「限制」）。Phase 6 再檢討 |
| 2 | duty cycle 與 jitter 是假設 | 沒變。週期 44 ns 時 DCD 預算 2.20 ns，半週期 uncertainty 2.45 ns。待 Phase 7 |
| 3 | IR 供電位置是假設 | **變差後已修正**：Hazard3 最壞組合 25.75 mV 超過 20 mV；met5 加寬後 14.13 mV，flow 每次都判最壞組合（ADR-0017）。供電位置仍是假設 |
| 4 | 溫度反轉 corner 沒給 resizer | **已改變**（ADR-0013）：`RSZ_CORNERS` 加 3 個 ss_n40C；`ff_100C_1v95` 仍只在 signoff 判定 |
| 5 | CTS 把 SRAM clock 延到與 flip-flop 一樣晚 | **已解決**（ADR-0016）：網表 `delaybuf_*` 為 0，由 `check_soc.py cts_macro_latency` 檢查（P52–P54）。這個檢查的漏洞見審查第 2 項 |
| 6 | EQY 只涵蓋組合邏輯 | 沒變；Hazard3 版 neg-eqy 13 案 |
| 7 | `counters` 抓不到計數器高半部卡 0 | 沒變 |
| 8 | LVS 中 SRAM 是 black box、金屬密度不合格、golden 只在同一環境比對、GRT-0229 用重試繞過 | GRT-0229 出現第二個位置（`ResizerTimingPostGRT`），重試範圍擴大（`2caad0e`，`docs/notes/grt0229_repro.md`）；其餘沒變 |
| 9 | 下游單獨執行不檢查工作目錄 | 沒變 |
| 10 | `py-check` 只看同一檔案的名稱 | 沒變（`4461661` 只擴充了 open() 寫法的檢查） |
| 11 | neg-eqy 位置範圍在大扇出 net 太大 | 部分改善（`c976976`）：常數不算名稱，接成常數的腳只往上游追，`reset_b_tied1` 從 1,449 個名稱降到 37 個；`flop_async_reset` 仍含整棵 reset 樹 |
| 12 | 第三人重現只在同一台機器驗證 | 沒變 |
| 13 | 繞線器中間各輪只比 key | key 的部分已改變（ADR-0015 `[golden_optional]`）。數值誤差 Hazard3 給 ±1310（`signoff/limits/soc_top_hazard3.toml`），比 PicoRV32 的 ±100 更寬，等於更不比數值 |

### Phase 3.5 已知限制

| # | 限制 | Phase 5 結果 |
|---|---|---|
| 1 | PDK SRAM 在低溫、ss 1.60 V 室溫讀取失敗（頭號下線風險） | 沒變，Phase 6 |
| 2–7、13–15 | 特性化的方法限制：寄生、萃取網表、dout0 transition、Monte Carlo、修剪、只在 tt 驗誤差、hold 弧與週期、最小負載、ss −40°C 只在 20 ns 判定 | 沒變，Phase 6。週期改 44 ns 對第 13 項是往安全方向：週期 20 ns 以上時，dout 的變化晚於 .lib 的 hold 弧 |
| 8 | resizer 的 hold 餘量與半週期路徑衝突（`rdata_q` 前的 delay cell） | **已解決**（ADR-0016）：`sram_dout0` 上的 32 顆 hold delay cell 變 0 |
| 9 | `neg-char` 不在 `make regress` 裡 | 沒變。Phase 5 新增的 N9–N16 只在主 checkout 跑過（2026-10-05，`runs/sram_char/neg_char_full2.log`，16/16），乾淨 checkout 沒跑 |
| 10 | `GRT-0243` 警告 | 仍出現；修補後與繞線後的 antenna 檢查都是 0 |
| 11 | 繞線器中間各輪的 key | 同 Phase 4 限制 13 |
| 12 | Phase 4 限制 2–13 不變 | 見上表 |
| 16 | 12 個 checker 漏洞 | 全部修正（`4461661`），見下表 |

Phase 3.5 的 12 個 checker 漏洞（原始清單：`docs/phase_exit/phase3_5.md`「獨立審查」）：

| # | 漏洞 | 修正 | negative test |
|---|---|---|---|
| 1、12 | SRAM .lib 多讀一份，或讀到另一個 checkout 的同名檔 | `check_soc.py sram_lib` 讀三種 library 訊息並比對真實路徑；`check_inputs.py other_libs` 與 `--resolved` 檢查 `LIB`／`EXTRA_LIBS` | P33–P36 |
| 2 | `char.json` 兩個 PVT 的紀錄對調 | `gen_char_lib.py` 檢查每筆的 PVT | N9 |
| 3 | `gen_char_lib.py` 公式錯 | `check_char_lib.py` 從 `char.json` 獨立重算每個數字 | N12（M1–M5） |
| 4 | 來源欄位沒人檢查 | `check_char_lib.py` 檢查 provenance | N10 |
| 5 | NaN、pass < fail 被接受 | 數值檢查 | N11 |
| 6 | 替換次數只數總和 | 每支 pin、clk0 rise／fall 各自計數 | N13 |
| 7 | 二分搜尋有「PASS 窗口」；.lib 採用的值沒有再確認 | `confirm_char_lib.py` 在 .lib 的值上做確認模擬（92 條） | N14 |
| 8 | 模擬快取不確認上次成功 | 快取有效性檢查 | N15 |
| 9 | 部分 PVT 失敗時留下新舊混合的紀錄 | 有失敗就不寫檔 | N16 |
| 10 | py-check 漏掉多種「先清空再讀」的寫法 | `check_py_names.py` 支援更多 open() 寫法 | 自我測試 |
| 11 | 斷言太寬（P17、N7、N8、P32） | 斷言收緊；P32 加 positive control | P32、N7、N8 |

出處：`4461661` 的 commit message、`ip/sram/char/neg_char.py` 檔頭。N9–N16 之中，N9、N11、N13、N16 是舊程式抓不到的。

## 可重現性

| run | 與 golden 比對 |
|---|---|
| Hazard3 第 12 次 harden（`1dee974`，開發 worktree，`PDN_HWIDTH` 4.8） | 本 golden 的來源 |
| Hazard3 乾淨 regress（`5aaf036`，一次 GRT-0229 接續） | 422 個相同、14 個連續量在誤差內 |
| Hazard3 乾淨 regress（`71b1454`） | 436 個完全相同 |
| PicoRV32 第 5 次 harden（`1dee974`，開發 worktree） | 本 golden 的來源 |
| PicoRV32 乾淨 regress、樣本 3、樣本 5（`5aaf036`） | 三次彼此逐項相同；與 golden 差 1 顆 diode、`global_route__vias` 20 對 11 → 依這 4 個樣本訂版圖誤差（使用者決定 4） |
| PicoRV32 乾淨 regress（`71b1454`，一次 GRT-0229 接續） | 435 個完全相同 |
| picorv32_core 乾淨 regress（`71b1454`） | 325 個完全相同（之前兩次是 254 個相同、71 個在 Phase 2 訂的誤差內） |
| 下列為 ADR-0016 golden 的紀錄 | |
| Hazard3 確認 run（`1d13775`）、乾淨 regress（`7348fab`，一次 GRT-0229 接續） | 都是 434 個完全相同 |
| PicoRV32 確認 run（`1d13775`）、乾淨 regress（`7348fab`） | 都是 436 個完全相同 |

- GRT-0229 中斷後從該 step 接續，最終 metrics 與沒有中斷的 golden 完全相同（兩個 CPU 各一次）。
- PicoRV32 SoC 的 `[golden_layout_tolerance]`：獨立審查證明暫用 Hazard3 的值會放過真的版圖改變（審查第 6 項），先清空；`5aaf036` 的乾淨 regress 第一次量到差異後，依 4 個樣本的最大差異 × 5 重訂（diode 5、cell 5、面積 15 µm²、`global_route__vias` 45；`signoff/limits/soc_top.toml`）。

## Checker qualification（本階段新增）

| checker | 植入的錯誤 | 預期 FAIL 的地方 | 結果 | 與計畫的差異 |
|---|---|---|---|---|
| `neg-pnr` | P33–P36：SRAM .lib 的來源 | `check_soc.py sram_lib`、`check_inputs.py` | 兩個 CPU 都 63/63（整組，`71b1454`） | Phase 3.5 審查新增 |
| | P37–P39：兩個 CPU 的 config 差異 | `check_inputs.py cpu_config` | | 計畫沒有 |
| | P40–P42：弱 cell | `check_weak_cells.py` | | ADR-0012 |
| | P43–P49：criteria review | `review_criteria.py` | | 規則 9 |
| | P50–P51：golden 版圖誤差 | `check_signoff.py` | | ADR-0015 |
| | P52–P54：CTS macro latency | `check_soc.py cts_macro_latency` | | ADR-0016 |
| | P55：重試留下的中斷 step 代替完成的 step | `review_criteria.py uncertainty` | | 本階段發現 |
| | P56：報表裡半週期路徑的 uncertainty 被改小 | `review_criteria.py uncertainty_applied` | | 獨立審查 |
| | P57：core 模式的 criteria 檢查 | `review_criteria.py --design picorv32_core` | | 獨立審查 |
| | P58–P60：改名的延遲鏈、帶字尾的 CTS 目錄 | `check_soc.py cts_macro_latency`（結構判斷） | | 獨立審查 |
| | P61、P62：最壞組合 IR 超標、`ir_worst.txt` 缺少 | `ir_worst.py`、`review_criteria.py checkers_ran` | | 獨立審查、ADR-0017 |
| `neg-eqy-soc` | Hazard3 版加 `mcycleh13_stuck1`、`minstreth8_stuck1`、`irq0_stuck0`、`reset_b_tied1` | EQY 證明、位置檢查（`reset_b_tied1` 實際上不是靠證明抓到，見審查第 5 項） | Hazard3 13/13（交叉檢查 144 組）；PicoRV32 9/9 | — |
| `neg-eqy-core` | 沿用 | 同上 | 11/11（104 組） | — |
| `neg-gl-soc` | Hazard3 版把 3 個 PicoRV32 的 flip-flop 案例換成 Hazard3 的 | gate-level 模擬 | 兩個 CPU 都 8/8 | — |
| `neg-gl-core` | 沿用 | gate-level 模擬 | 2/2 | — |
| `neg-rtl` | Hazard3 版，含轉接器 H01–H04 | RTL 模擬的 checker | 36/36（PicoRV32 33/33） | — |
| `core-hazard3` | `EXTENSION_M=0` | riscv-tests | rv32um 8/8 FAIL | — |
| `neg-char` | N9–N16 | 特性化腳本與 `check_char_lib.py` | 16/16（只在主 checkout 跑過，不在 regress） | Phase 3.5 審查新增 |
| `neg-regress`、`test-flow-retry`、`test-review-hook` | regress 的拒絕條件與 xPack；GRT-0229 第二個位置、GRT-0116、守門條件本身；Stop hook 的觸發條件 | 各自的腳本 | 8/8、15/15、12/12 | 獨立審查擴充 |

## 本階段找到並修正的 checker 問題

1. **repo 的 checker 在 LibreLane FAIL 時沒跑**：Hazard3 連續三次 LibreLane FAIL，上限檔與 `check_soc.py` 都沒跑。
   - 修正（`0b67b76`）：`pnr/soc_top/run.sh` 在 LibreLane FAIL 時仍執行 checker，並新增 `review_criteria.py`。
   - Stop hook `.claude/hooks/require_criteria_review.py` 要求每次 harden 後寫 criteria review（CLAUDE.md 規則 9）。
   - negative test：P43–P49、`test-review-hook`。
2. **重試留下的中斷 step 目錄被當成完成的 step**：PicoRV32 確認 run 的 neg-pnr P49 沒抓到（54/55）。
   - 修正：只算有 `state_out.json` 的目錄，加 P55（`941e1cb`）。
3. **neg-eqy 把常數當名稱**：`reset_b_tied1` 的範圍有 1,449 個名稱，會接受別的案例的 FAIL（`c976976`）。
4. **乾淨 checkout 找不到 xPack**：`core-hazard3` 直接讀 `.tools/`，在乾淨 checkout 才發現。
   - 修正：加 `XPACK_DIR`，並在 `env-check-flow` 檢查（`7348fab`）。
   - 審查第 8 項：原本只看版本字串，已改成檢查產品本身，並加 negative test（`neg-regress xpack_fake`）。
5. **獨立審查的 8 個 checker 漏洞**：見「獨立審查」一節，全部修正並各有 negative test（`1dee974`）。
6. **GRT-0116 的重試，以及重試腳本的 `set -euo pipefail` 陷阱**（`71b1454`）：
   - PicoRV32 樣本 4 在第 44 步因 `GRT-0116 Global routing finished with congestion` 中止，溢位只有 2；同一份輸入單步重跑 4 次都通過，所以是隨機的。重試範圍加入「GRT-0116，而且總溢位 ≤ 10」。
   - 加這段程式時，新的 `grep` 在 GRT-0229 的 log 上找不到內容，在呼叫端的 `set -euo pipefail` 下會讓整支腳本結束。`test-flow-retry` 當場抓到；若沒被抓到，正式 harden 一走到重試路徑就會中斷。已修正。

## 與計畫不同的地方

1. **用 `hazard3_cpu_1port` 加轉接器（wait state）**，不用計畫建議的 `hazard3_cpu_2port`（使用者決定，ADR-0011）。
2. **週期 44 ns**：Phase 3.5 是 43 ns（`edb7d63`）。Hazard3 第 1–3 次都在 43 ns 跑，ss_n40C 的 setup 修不過（使用者決定，ADR-0004 Phase 5 補充）。
3. **flow 設定的變更兩個 CPU 共用**：
   - resizer 排除弱 cell（ADR-0012）；
   - resizer 也看 ss_n40C（ADR-0013）；
   - 繞線後再做一次 resizer 修復（ADR-0014）；
   - CTS 不做 macro latency 對齊（ADR-0016）。
4. **golden 比對加版圖誤差**（ADR-0015）。
5. **PicoRV32 版改用 `make regress-picorv32`**，`make regress` 改成 Hazard3（ADR-0011）。

## 已知限制（帶到後續階段）

1. **duty cycle 45/55%（DCD 2.2 ns）與 jitter 0.15 ns 是假設**：兩個 CPU 的最差路徑都是半週期路徑。Phase 7 確定 Caravel 的 clock 後要重算。
2. **SRAM 的時序與讀取**，都在 Phase 6 處理：
   - ss_n40C 的時序是佔位值（ADR-0013）；
   - 低溫與 ss 室溫讀取失敗（Phase 3.5 限制 1，頭號下線風險）；
   - Phase 3.5 限制 2–7、13–15 的特性化方法限制。
3. **IR 供電位置是假設**：最壞組合已修到 14.13 mV（Hazard3），每次 harden 都判；但供電點仍是「每條 met5 strap 左端一點」的假設，EM 沒有 flow 檢查（ADR-0017 限制）。Phase 7 確定 Caravel 的接法後要重算。
4. **不可重現的步驟**（ADR-0015）：
   - 第 41 步 global routing 偶發不同；
   - detailed routing 多執行緒會多插 diode；
   - `DRT_THREADS=1` 沒試。
5. **GRT-0229 與 GRT-0116 只用重試繞過**，根因沒有查證：GRT-0229 已知出現在兩個 step；GRT-0116（hold 修復後的增量 global routing 剩下個位數的溢位）在 `ResizerTimingPostGRT` 出現一次，單步重跑 4 次都通過，重試只在總溢位 ≤ 10 時接手（`docs/notes/grt0229_repro.md`）。
6. **golden 誤差內的改變抓不到**（ADR-0015）：
   - standard cell 少於約 70 顆、slack 小於約 0.2 ns 的變化；
   - 繞線器中間各輪的 DRC 數，Hazard3 的誤差給到 ±1310。
7. **ADR-0016 留下的項目**：
   - 讀出 flip-flop 自己繞回自己的路徑仍有 1 顆 hold delay cell；
   - useful skew 沒試；
   - PicoRV32 SRAM 輸入腳的 hold 變緊（min_ff 從 +0.197 降到 +0.093 ns）。
8. **RepairHold 全設計只用一種 hold buffer**（`dlygate4sd3_1`，ss_n40C 的延遲約是 ff 的 3 倍）。排除它會停在 `RSZ-0060`（drv-timing-closure 規則 7）。
9. ~~`harden-core` 沒有接 `review_criteria.py`~~：已修正（`--design picorv32_core`，Stop hook 改用 `result.txt` 觸發；P57、`test-review-hook`）。
10. **`neg-char` 不在 regress 裡**（Phase 3.5 限制 9）：N9–N16 沒在乾淨 checkout 跑過。
11. **沒有分析的項目**：
    - Hazard3 功耗為兩倍的原因；
    - resizer 多修 buffer 的原因；
    - Phase 5 的四項設定變更沒有逐項分開做實驗；
    - 2port、riscv-arch-test、formal（`core-migration-hazard3`「待補」）。
12. **照舊帶到後續階段**：
    - Phase 4 已知限制 6、7、9、10、12；
    - 限制 8 的 LVS black box、金屬密度；
    - 限制 11 的 `flop_async_reset` 範圍；
    - Phase 3.5 的 `GRT-0243`。
13. 獨立審查找到的 8 個 checker 漏洞：已全部修正，見「獨立審查」。審查另外列的三個疑點（P55 的中斷目錄形狀已改；`substituting_steps` 為 `null` 時當掉已修；neg-eqy 只往上游追的範圍會落在共用的 reset 同步器上）中，最後一項保留，交叉檢查目前都分得開。

## 獨立審查（2026-10-08）

兩次乾淨 regress 結束後，請兩個沒參與實作的 agent 反向檢查。

### 文件核對

找到 17 項問題，本版已依它更正：
- 第 7 項判定的說法不誠實：改拆成 7a／7b；
- Phase 3.5 限制 1–15 沒有延續：已補；
- L2／L3 分層寫錯；
- 週期歷史寫錯：Phase 3.5 已是 43 ns；
- 收斂表漏寫第 5、10 次的 FAIL，第 6、7 次的 commit 也沒寫；
- IR 只看 nom_tt：補上最壞組合，並另外實測（見 signoff 結果）；
- 證據改引乾淨 checkout 的 run；
- 交付物與 skill 分析不完整；
- `power__total` 沒寫是哪個 corner 的值；
- 92.9 GB 的出處沒寫。

核對無誤的部分：signoff 表的每個數字、兩次 regress 的 commit、時間與結果、golden 比對的筆數、riscv-tests 與 trace 數、ADR-0016 實驗、neg-eqy 範圍 1,449 → 37。

### 找 checker 漏洞

找到 8 項，每項都在 run 的副本上做出壞掉的輸入、實際跑 checker 確認。沒有一項讓本階段兩次 regress 的結果變成假 PASS：審查在 Hazard3 run 的副本上重跑各 checker，結果與原本一致；半週期路徑的 uncertainty 在 STA 報表裡確實是 2.450 ns。但這些漏洞在下次換設定或換工具時會漏抓。

| # | 漏洞 | 實驗結果 | 本階段有沒有中招 | 建議修法與 negative test |
|---|---|---|---|---|
| 1 | `review_criteria.py` 的 uncertainty 檢查只確認 SDC 印出了那一行，不確認 STA 真的套用 | 刪掉 15 個 corner 報表裡所有 uncertainty，仍判 PASS。另外 setup／hold 的 0.25 剛好等於 LibreLane 預設值，單看數字分不出來 | 沒有 | 從每個 corner 的報表核對實際套用的值：半週期 2.45、同緣 setup 0.25、hold 0.25。negative test：在 signoff SDC 之後蓋掉 uncertainty |
| 2 | `cts_macro_latency` 靠名稱判斷 | `delaybuf_` 改名 `clkdly_` 仍 PASS；目錄名多一個 `-1` 字尾（`*-openroad-cts-1`）仍 PASS；「剛好一個 CTS 目錄」沒有 negative test | 沒有：網表裡 SRAM clock 前是正常的 clock tree | 改用結構判斷：從 `sram0/clk0` 往回追的 buffer 級數不得多於 flip-flop。目錄比對容許字尾。補 4 個 negative test |
| 3 | `check_signoff.py` 對誤差表的保護不完整 | floating net 從 2 變 40、多一種新 warning，在改過的 limits 下仍 PASS：受保護字沒有 `floating`、`warning`；`[golden_optional]` 接受萬用字元 | 沒有：limits 裡沒有這兩種寫法 | 補受保護字；optional 只接受列明的 message ID。補 2 個 negative test |
| 4 | Stop hook 沒有涵蓋每次 harden | `harden-core` 沒有 `criteria_review.txt`，hook 放行；`review_criteria.py` 當掉、md 只有三個空標題，hook 也放行 | **有**：PicoRV32 regress 的 `harden-core` 可以不做 review 就回報，本階段靠手動補寫 | `harden-core` 也跑 review；hook 遇到「有 signoff 結果、沒有 review 結果行」時擋下。`test-review-hook` 補 2 個 negative test |
| 5 | `reset_b_tied1` 證明的事與說明不同 | `summary.json` 的 `partitions` 是 0：EQY 在名稱比對時就拒絕，沒有做證明。「flip-flop 永遠不 reset」能不能被證明抓到，沒有被驗證 | 說明寫錯；這個案例仍然是 FAIL | 改用 tie cell 的 net 接 RESET_B，並要求確實有分區沒被證明。同步更正 `signoff/eqy/README.md` 的說明 |
| 6 | PicoRV32 的版圖誤差暫用 Hazard3 的值 | 在 PicoRV32 的 metrics 加上 diode +54、standard cell +69 等改變，判 PASS | 沒有：本階段 3 次 run 完全相同 | 量到 PicoRV32 的實測差異前，先不給版圖誤差（必須完全相同）。仿 P50 補 negative test |
| 7 | `test_librelane_flow.sh` 沒測兩道重試條件 | 把「只在 `usage=65534` 時重試」或「只在 step 沒完成時重試」拿掉，測試仍 11/11 | 沒有 | 補兩個情境：真正的壅塞（`usage=2300`）不得重試；已完成的 step 不得重試 |
| 8 | xPack 檢查只看 `-dumpversion` | 一支只會印 `15.2.0` 的假 gcc，`env-check` 判 PASS | 低：用錯工具鏈時，測試多半會 FAIL，不會變成假 PASS | 檢查 `--version` 裡的 xPack 字樣與 newlib；把工具鏈路徑與版本記進 `core-hazard3` 的 summary |

只讀程式碼得到、沒有做實驗的疑點：
- config 用 `null` 表示移除某個 step 時，`review_criteria.py` 會當掉。harden 會判 FAIL，但 hook 會放行（同第 4 項）。
- P55 造出來的「中途停掉的那次」，目錄長相和真實重試不同。Hazard3 的乾淨 regress 本身有真實的重試，所以 Hazard3 上其實測到了真實情況。
- neg-eqy「只往上游追」的範圍會落在共用的 reset 同步器上；目前的交叉檢查都分得開。

實驗用的副本在 session 暫存目錄，沒有改動 repo、worktree 或 `runs/`。

**處理**（使用者決定 2）：8 項全部修正，各有 negative test（`1dee974`），並在 `71b1454` 的兩輪乾淨 regress 裡全部通過（neg-pnr 63/63、test-flow-retry 15/15、test-review-hook 12/12、neg-regress 8/8、neg-eqy 13/13 與 9/9、11/11）。

## 使用者決定

2026-10-08，看完獨立審查與 IR 實測後：

1. **IR 在 Phase 5 內修好**：
   - flow 加「最壞組合（ff 電流＋ss 金屬電阻）IR」的正式檢查，含 negative test；
   - 調 PDN，讓 Hazard3 通過；
   - 兩個 CPU 重新 harden、重建 golden，再跑兩輪乾淨 regress。
   - 沒有採用的選項：只報告不判 FAIL，等 Phase 7；只列已知限制。
2. **8 個 checker 漏洞全部修正**，各補 negative test，與第 1 點共用同一次重跑。
   - 包括 `harden-core` 接 `review_criteria.py`；
   - 包括 PicoRV32 的版圖誤差在量到差異前先不給。
3. **第 7b 項接受為與計畫不同**：
   - 這條 criteria 原本假設 flow 設定夠通用，實際換 core 就要重新調。
   - 改用「兩個 CPU 共用同一份 flow 設定、只差 RTL」（第 7a 項）當替代判準。
   - project-plan.md 不改。

4. **PicoRV32 的版圖誤差依實測訂**（`5aaf036` 的 regress 第一次量到差異之後）：再跑 2 次 harden 收集樣本，用最大差異 × 5（ADR-0015 的方法），不沿用 Hazard3 的值。其中一次因 GRT-0116 中止，補跑一次；4 個有效樣本中 3 個逐項相同。
5. **確認 Phase 5 結案**，以 `71b1454` 的兩輪乾淨 regress 為結案證據；commit 並推到兩個 remote。

本階段已做的決定：
- ADR-0011：1port 加轉接器、`make regress` 換成 Hazard3；
- 週期 44 ns；
- ADR-0016：自訂 CTS step；
- 依 ADR-0016 重建兩個 golden 並改 unannotated 上限；
- CLAUDE.md 規則 9、10、11。

## Skill 分析（`phase-exit-review` 規則 8）

本階段的重大任務與對應的 skill（對照方法見 `phase-exit-review` 規則 8；`git diff --stat e16465b HEAD -- .claude/skills` 加上收尾的修改）：

| 任務 | skill | 寫回 |
|---|---|---|
| 換 CPU：wrapper、AHB 轉接、設定參數、上游測試與 ISS 比對 | `core-migration-hazard3`（Phase 5 開始時新建，CLAUDE.md 規則 7） | 規則與經驗紀錄；收尾補「換 core 要重量最壞組合 IR」 |
| resizer 失控、弱 cell、resizer 看的 corner、繞線後修復 | `drv-timing-closure` | 規則 7（hold buffer 只有一種，補上「沒有自動防護」）、9–12；ADR-0012–0014 |
| CTS 把 macro 的 clock 延後 | `cts-clock-tree`、`hard-macro-integration` | 規則 10（防護改成結構判斷）、12 |
| golden 誤差、重跑結果不同、checker 漏洞 | `signoff-checker-qualification` | 規則 5（版圖誤差）、規則 7 加兩條；漏洞類型表加 9 種 |
| criteria 檢查（每次 harden 後） | `signoff-criteria` 與 knowledge 檔 | 第一部分加 `uncertainty_applied`、`ir_worst`、core 模式；判斷原則加「依據要在這個設計上重量」 |
| IR 的最壞組合、PDN what-if | `pdn-ir-drop` | 規則 12、13（新）；待補更新 |
| EQY 的 negative test | `formal-equivalence-eqy` | reset 連接的錯誤都在分區步驟被拒絕；`REQUIRE` |
| LibreLane plugin、GRT-0229 第二個位置、單步 what-if | `librelane-run-debug` | 規則 1、3；已知陷阱 |
| 乾淨 checkout 的 regress、xPack、進度與剩餘時間 | `flow-regression-reproducibility` | 規則 2；經驗紀錄 |
| 多 corner STA 的 uncertainty 核對 | `multicorner-sta`、`timing-constraints-sdc` | 經驗紀錄 |
| Magic DRC 數在 SRAM 內改變 | `drc-signoff` | 經驗紀錄 |
| 收尾 | `phase-exit-review` | 規則 1 補兩點；經驗紀錄 |
| SRAM 特性化（Phase 3.5 漏洞修正） | `openram-macro-characterization` | Phase 5 開頭寫回 |

沒有更新的 skill 與理由：
- `antenna-signoff`：只改了一行，antenna 修補照舊，`GRT-0243` 記在 golden README。
- `lvs-signoff`、`floorplan-congestion`：結果與 Phase 4 相同。
- `gate-level-simulation`：Hazard3 的 GL 測試沿用同一套方法，沒有新現象。
- `dv-directed-tests`：轉接器的植入錯誤 H01–H04 是一般的 RTL negative test，沒有新的缺口類型。
- `rtl-synthesis-lint`：合成沒有新問題。

另外兩個全域的自動化，使用者 2026-10-08 決定做成全域：
- `~/.claude/skills/overnight-run/`：夜間連續任務的 skill；
- `~/.claude/skills/progress-pane/`：`/progress` 進度面板 mod。

這兩個不在本 repo，本 repo 只提供 `.claude/statusline-progress` 與 `.claude/guard.json`。

### 規則 10 稽核：本階段的工具缺陷與防護

| 工具缺陷或意外行為 | 症狀（寫進 description） | 怎麼發現 | 怎麼繞過 | 防復發 |
|---|---|---|---|---|
| OpenROAD GRT-0229 隨機中止（兩個位置） | `librelane-run-debug` | `retries.txt`、console | 有上限的重試，從中止的 step 接續 | `test-flow-retry` 15/15，含「條件拿掉就 FAIL」的情境 |
| OpenROAD GRT-0116：hold 修復後的增量 global routing 剩個位數溢位 | `librelane-run-debug` | step log 最後的 `Total` 壅塞列 | 總溢位 ≤ 10 才重試，大溢位是真的壅塞 | `test-flow-retry` 的 `cong`、`congbig` |
| CTS 把 macro 的 clock 延後（latency 對齊） | `cts-clock-tree`、`hard-macro-integration` | `check_soc.py cts_macro_latency` | repo 的 plugin 加 `-no_insertion_delay`（ADR-0016） | P52–P54、P58–P60，結構判斷 |
| resizer 換上推不動的弱 cell，停不下來 | `drv-timing-closure` | `check_weak_cells.py`、記憶體監看 | 排除弱 cell（ADR-0012） | P40–P42 |
| RepairHold 全設計只用一種 hold buffer | `drv-timing-closure` | INFO 列的網表 hold buffer 數 | 在 clock 端修 | **沒有自動防護**：這是工具挑 cell 的策略，不影響正確性；已寫明 |
| `RSZ-0032` 的 hold buffer 數不是總數 | `librelane-run-debug` | 數網表 | 不讀那個數字 | `review_criteria.py` 改數網表；golden 比對 cell 數 |
| 只判 nom_tt 的 IR 步驟（LibreLane 的預設做法） | `pdn-ir-drop` | `ir_worst.py` | 最壞組合每次判 | P61、P62 |
| EQY 對 reset 連接的修改一律在分區步驟拒絕 | `formal-equivalence-eqy` | `summary.json` 的 `partitions` | 照實寫進文件 | `REQUIRE` |
| Magic DRC 在 macro 內的計數隨上方金屬改變 | `drc-signoff` | golden 比對 | 用位置比對判斷，不看總數 | `check_soc.py magic_drc`（P09、P21） |

每一條防護都沒有綁在 step 編號上；用到 step 名稱的地方（`ResizerTimingPostGRT`、CTS 的替換）都容許 `-<n>` 字尾，並由 `substituting_steps` 對照。

## 交付物

- **RTL 與驗證**：
  - `rtl/cpu/soc_cpu_hazard3.v`、`rtl/cpu/soc_ahb2native.v`；
  - `fw/` 的 Hazard3 版；
  - `dv/core_hazard3/`：riscv-tests 與 rvcpp trace 比對、`rvcpp_fence.patch`；
  - `dv/bugs.toml` H01–H04；
  - `dv/gl_soc/` 的 Hazard3 版。
- **flow**：
  - `pnr/soc_top/config_hazard3.json`；
  - `pnr/librelane_plugin_arvinsa/`（ADR-0016）；
  - `pnr/librelane_flow.sh`：GRT-0229 第二個位置、`keep_prev_run`；
  - `pnr/check_weak_cells.py`（ADR-0012）。
- **checker**：
  - `signoff/scripts/review_criteria.py`、`.claude/hooks/require_criteria_review.py`；
  - `check_soc.py` 的 `cts_macro_latency`、`sram_lib`；`check_inputs.py` 的 `cpu_config`、`other_libs`；
  - `neg_pnr.py` P33–P55；
  - `signoff/eqy/neg_eqy.py` 的 Hazard3 案例與新的位置範圍；
  - `ip/sram/char/check_char_lib.py`、`confirm_char_lib.py`、`neg_char.py` N9–N16；
  - `scripts/check_py_names.py`。
- **golden 與上限**：
  - `signoff/golden/soc_top_hazard3/`；
  - `signoff/golden/soc_top/`（ADR-0016 後重建）；
  - `signoff/limits/`。
- **regression 與環境**：
  - `scripts/regress.py --cpu`（`make regress`、`make regress-picorv32`）；
  - `env/check_env.sh` 的 xPack 檢查、`env/fetch_xpack.sh`（`make xpack-fetch`）。
- **文件**：
  - ADR-0011–0016、ADR-0004 Phase 5 補充；
  - `docs/notes/grt0229_repro.md`、`docs/notes/repair_design_loop.md`；
  - `signoff-criteria` 的 knowledge 檔。
- **狀態列進度**：`scripts/progress.py`、`.claude/statusline-progress`（CLAUDE.md 規則 11）。結案 commit 前要確認已納入版控。
- **獨立審查後（`1dee974`、`5aaf036`、`71b1454`）**：
  - `pnr/soc_top/ir_worst.py`、`PDN_HWIDTH` 4.8、`pnr/soc_top/vsrc/vssd1.vsrc`、ADR-0017、`docs/notes/ir_study/phase5/`；
  - `review_criteria.py` 的 `uncertainty_applied` 與 `--design picorv32_core`、`pnr/picorv32_core/run.sh`；
  - `check_soc.py` 的結構判斷 `sram_clock_chain`、`check_signoff.py` 的保護字與 optional 規則；
  - Stop hook 的觸發條件、`neg_eqy.py` 的 `REQUIRE`、`test_librelane_flow.sh`（15 個情境，含 GRT-0116）、`env/check_env.sh` 的 xPack 檢查；
  - `neg_pnr.py` P56–P62；PicoRV32 的版圖誤差（`signoff/limits/soc_top.toml`）；兩個 golden 重建。
- **skill**：新增 `core-migration-hazard3`（Phase 5 開始時建立）；其他見「Skill 分析」。
