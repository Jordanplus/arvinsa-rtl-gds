---
name: formal-equivalence-eqy
description: 用 YosysHQ EQY（或 Yosys equiv_*）證明兩份網表、或 RTL 與網表等價，或 EQY 當機、分區證不出來、需要設計 EQY 的 negative test 時使用。Use for formal equivalence checking with EQY, including known pitfalls and checker holes.
---

# Formal equivalence（EQY）

**formal equivalence**：用數學證明兩份電路在所有輸入與狀態下行為相同。EQY 先在「名字相同的訊號」把兩邊切成很多小分區，再逐一證明。模擬證據看 `gate-level-simulation`。本 repo 實例：`signoff/eqy/run_eqy.py`、`neg_eqy.py`、`README.md`。

## 規則（已驗證）

1. **目前可用的組合**：合成網表（gold）vs 最終網表（gate），兩邊都用 `eqy.formal_pdk_proc` 處理過的 sky130 cell 模型，macro 用 blackbox。
2. **必要設定**：
   - `ulimit -s 65520`：切分步驟遞迴很深，8 MB stack 會 SIGSEGV（returncode −11）。
   - `delete t:$scopeinfo`：Yosys 0.62 攤平後保留的 cell。
   - `[options] insbuf off`：OpenROAD 在 flip-flop 與輸出 port 之間插 buffer 並改名輸出線；不關 insbuf 時這些線變成獨立且對不上的狀態。
   - strategy：`sat`（depth 5）加 `pdr` 後援。
3. **判定**：`DONE (PASS, rc=0)`；每個分區都有 `Proved equivalence`；partition log 出現 `found constant ... bit` 一律 FAIL（EQY 漏洞：輸出被植入卡 0 時，所有分區照樣證明通過）；植入後 EQY 以 `conflicting matches` 拒絕切分，也算抓到；**sequential cell（flip-flop、latch、clock gate）兩邊必須是同樣的 instance、同樣的功能**（只允許 drive strength 不同），在 EQY 之外用腳本比對（規則 5）。
5. **EQY 的 `sat` strategy 證不到 flip-flop 本身的行為**（Phase 4，已驗證）：
   - 把最終網表的一顆 `dfxtp_2` 換成 `dfrtp_2`、RESET_B 接 `resetn` port（reset 時會被清掉，合成網表的那顆不會），EQY 仍是 18100/18100 個分區證明通過（`neg_eqy.py flop_async_reset`）。
   - 原因（agent 實驗）：含 flip-flop 的分區，EQY 用的 `sat -tempinduct -set-init-undef -set-def-formal ...` 的初始狀態約束本身就無解（只放約束不放斷言也是 `no model found`），base case 什麼都沒證；手動展開也找得到 induction 沒抓到的反例。PDR 抓得到，但分區的輸入彼此獨立給值，好設計也會報假 FAIL。
   - 處理：flip-flop 周圍的邏輯（D 端與 Q 之後）仍由 EQY 的組合邏輯分區證明；flip-flop cell 本身用結構比對（`run_eqy.py` 的 `sequential_cells`）。soc_top 與 picorv32 的合成網表與最終網表，flip-flop 的名稱與功能完全相同（2639／2382 顆 `dfxtp`），所以這個比對沒有假 FAIL。
   - 輸出改成反相（`dfxbp` 的 Q_N）會在切分時被名稱矛盾拒絕，不會走到證明，所以不能拿它來測證明步驟。
   - **clock 接線也證不到**（Phase 4 獨立審查，已驗證）：`sat` strategy 先做 `formalff -clk2ff`，所有 flip-flop 變成同一個隱含 clock；切分出的分區沒有一個以 CLK 為邊界。一顆 flip-flop 的 CLK 改經過反相器（下降緣取樣），EQY 與只比 cell 種類的結構比對都 PASS。處理：`run_eqy.py` 的 `clock_sources` 從每個 clock pin（含 macro 的 `clk*`）往回追，只穿過 buffer／inverter，兩份網表必須追到同一個 port 或常數、反相次數奇偶相同；negative test `flop_clk_inverted`、`clk0_inverted`。
4. **時間**：picorv32 約 4 分（15137 分區，249 秒，`-j 10`；Phase 2 用 `-j 8` 約 6.5 分）、soc_top 約 5 分（18100 分區，295 秒，`-j 10`）。negative test：soc_top 4 個 439 秒、picorv32 7 個 1090 秒（`neg_eqy.py -j 3`）。PDR 找到反例時，SBY 需要 `yices` 轉波形（nix-shell 沒有），只影響除錯，不影響 FAIL 判定。

## RTL vs 網表：尚未解決

LibreLane 的合成一定會跑 Yosys 的 `fsm`（`librelane/scripts/pyosys/synthesize.py` 第 186 行，沒有開關），PicoRV32 又不能改（`third_party/` 唯讀，不能加 `fsm_encoding = "none"`），所以合成網表的狀態機編碼一定和 RTL 不同。合成這一步目前由 gate-level 模擬加 directed 測試補（`dv-directed-tests`）。

Phase 4 agent 再試一次（gold 端照 LibreLane 的順序跑到 `memory_map`、`$alu` 先 techmap、flip-flop 拆成 1-bit）：soc_top 2642/2642 分區證明通過（102 秒），兩邊的 FSM 編碼一致。但在 gold 端植入 4 種錯誤，UART 除頻器的 reset 值、FSM 轉移改錯這 2 種**照樣 PASS**（規則 5 的同一個原因）；只用 PDR 則好設計也報假 FAIL。結論：不加成 checker。

| 問題 | 嘗試 | 結果 |
|---|---|---|
| Yosys `fsm_recode` 把 `cpu_state`、`mem_wordsize` 改成 one-hot，名字相同、意義不同 | EQY `[recode]` | 需要整條向量，網表是逐 bit 命名 |
| 上電值未定、寫入後恆為常數的暫存器（`mem_addr[1:0]`），合成換成常數 | gold 端 `opt_dff -sat`、`opt -full`、`wreduce` | 修掉一些，但改動其他名稱，造成新的對不上 |
| gold 端也跑 `fsm` | 編碼與合成相同 | 仍有分區證不出；且與合成共用同一套轉換，有共模風險 |

## negative test（`neg_eqy.py`）

- picorv32_core（7 個）：輸出 buffer 輸入接 0、輸出 buffer 換成反相器、`count_cycle[45]`／`count_instr[40]` 卡 1、bus-error IRQ 卡 0（這三個是 GL 模擬漏掉的）、暫存器 bit 卡 0、mux 兩輸入對調。
- soc_top（4 個）：SRAM `din0[5]` 卡 0、`csb0` 反相、`host_rdata[7]` 反相、mux 兩輸入對調。
- **被抓到的機制要分開記**（看 `summary.json` 的 `proved`、`constant_matches`、`conflicting_matches`）。EQY 的 FAIL 有三種來源：(a) 分區證明失敗；(b) 常數規則（`found constant ... bit`）；(c) 切分時名稱對應互相矛盾而拒絕（`conflicting matches`），這時一個分區都沒證。
  - 2026-10-03 實測：soc_top 的 `csb0_inverted`、`host_rdata7_inverted`、`mux_swap` 與 picorv32 的 `instr_inverted`、`mux_swap` 都是 (c)；`wdata3_stuck0` 只靠 (b)（15136/15136 分區照樣證明通過）；`din5_stuck0` 是 (a)+(b)（18099/18100）。picorv32 的 `count_cycle45_stuck1`、`count_instr40_stuck1`、`buserr_irq_stuck0`、`x8_bit24_stuck0` 是 (a)+(b)，各 1 個分區沒證明（2026-10-04 第四次 `make phase3` 重現，GL 模擬漏掉的 3 個都在其中）。
  - 只有 (a) 證明「證明本身有效」。qualification 報告要寫出每個案例是哪一種，並確保 (a) 有案例。
  - **(a) 的案例也要有非常數的錯誤**：「卡成常數」的 (a) 案例，失敗的分區正好就是被換成常數的那個 bit；反相器、mux 對調都落在 (c)。`neg_eqy.py nand2_to_nor2`（Phase 4）：第一顆 nand2（依 instance 名稱）換成同尺寸的 nor2，名稱與接線不動 → soc_top 18100 個分區中 1 個證明失敗、picorv32 15137 個中 1 個，沒有常數也沒有名稱衝突，證明步驟有效。
  - **抓到的位置要對**（`neg_eqy.py` 的 `fail_names()`、`neighborhood()`，Phase 4）：從 EQY 紀錄取出 FAIL 牽涉的名稱（沒證明的分區、常數 bit、名稱矛盾的兩邊），每一個都要在植入點附近：被改的 cell、被改的腳上的 net、這些 net 上的 cell，遇到 buffer／inverter 繼續往下走（EQY 報的是合成網表的名稱，最終網表在 flip-flop 與 port 之間插了好幾級 buffer，只看一層會誤判）；clock net 不走。用 Phase 3 的 11 個案例驗證：都在自己的範圍內，任兩個案例交換後都判不符。為什麼反相器、mux 對調會造成 (c)：推測與 `insbuf off` 的別名處理有關，尚未查證。

## 用完後

更新「經驗紀錄」；Yosys／EQY 升版時重跑 negative test，確認常數漏洞的偵測仍有效。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | arvinsa-rtl-gds eqy1 | `partition: finished (returncode=-11)` | 已驗證：stack 不足 | `ulimit -s 65520` | `signoff/eqy/README.md` |
| 2026-10-03 | neg-eqy | 輸出卡 0 仍 PASS | 已驗證：`found constant gate bit` 不證明 | 判定規則 3 | `runs/neg_eqy_picorv32_core` |
| 2026-10-04 | Phase 4 agent（RTL vs 合成）與 `flop_async_reset` | 植入改 reset 行為的錯誤，EQY 全部分區證明通過 | 已驗證：sat strategy 對含 flip-flop 的分區是空洞證明 | 規則 5：sequential cell 改在 EQY 外比對；RTL vs 合成不加 checker | `signoff/eqy/run_eqy.py`、`neg_eqy.py` |
| 2026-10-03 | neg-eqy-soc（正式 run 2 網表） | 4/4 抓到，其中 `csb0_inverted`、`host_rdata7_inverted`、`mux_swap` 是 `partition step refused: conflicting name matches` | 已驗證（`runs/neg_eqy_soc_top/*/eqy/summary.json`） | 見 negative test 一節；`make phase3` 重跑完整 neg-eqy-core 後補記各案例的機制 | `runs/p3_neg_eqy_soc.log` |
| 2026-10-04 | Phase 4 獨立審查 | flip-flop 的 CLK 改接反相 clock：EQY 與 sequential cell 結構比對都 PASS | 已驗證（審查者在最終網表植入；`partition.list` 0 個分區含 CLK） | 加 clock 來源追蹤（規則 5）與 2 個 negative test；位置檢查改逐 bit 並加交叉檢查 | `signoff/eqy/README.md` 判定第 7 點 |
