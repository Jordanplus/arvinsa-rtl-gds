---
name: formal-equivalence-eqy
description: 用 YosysHQ EQY 證明兩份網表（或 RTL 與網表）等價時使用：必要設定（stack、`insbuf off`、`$scopeinfo`）、EQY 會靜默略過而要另外補的情況（被換成常數的 bit、flip-flop 本身的種類、clock 接線）、EQY 當機（SIGSEGV）或分區證不出來（`Failed to prove equivalence of partition`，好網表也會發生：切分點遺失邏輯關係，用 amend 重試；amend 併入 flip-flop 會變成空洞證明）、OpenROAD 對調等價輸入（pin swap，`RSZ-0043 Swapped pins`）後 EQY 在切分步驟停下（`conflicting matches for gold bit _10711_.A`，一個分區都沒證）、換了名稱不是 `sky130_` 開頭的 macro 後 macro 的 clock 檢查被悄悄略過、RTL 對合成網表為什麼還做不到、EQY 的 negative test 與 FAIL 位置檢查（`eqy FAILed, but not at the injection`，含被接成常數的 reset 腳；改到 reset 連接的錯誤一律在分區步驟被拒絕、不會走到證明，negative test 要斷言抓到的機制）。Use for formal equivalence checking with EQY, its silent holes (constant bits, flip-flops, clock wiring), OpenROAD pin swaps and qualifying it by bug injection.
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
4. **時間**：picorv32 約 4 分（15137 分區，249 秒，`-j 10`；Phase 2 用 `-j 8` 約 6.5 分）、soc_top 約 5 分（18100 分區，295 秒，`-j 10`）。negative test（Phase 4 regress 4，`neg_eqy.py -j 3`）：soc_top 9 個 931 秒、picorv32 11 個 1314 秒。PDR 找到反例時，SBY 需要 `yices` 轉波形（nix-shell 沒有），只影響除錯，不影響 FAIL 判定。
5. **EQY 的 `sat` strategy 證不到 flip-flop 本身的行為**（Phase 4，已驗證）：
   - 把最終網表的一顆 `dfxtp_2` 換成 `dfrtp_2`、RESET_B 接 `resetn` port（reset 時會被清掉，合成網表的那顆不會），EQY 仍是 18100/18100 個分區證明通過（`neg_eqy.py flop_async_reset`）。
   - 原因（agent 實驗）：含 flip-flop 的分區，EQY 用的 `sat -tempinduct -set-init-undef -set-def-formal ...` 的初始狀態約束本身就無解（只放約束不放斷言也是 `no model found`），base case 什麼都沒證；手動展開也找得到 induction 沒抓到的反例。PDR 抓得到，但分區的輸入彼此獨立給值，好設計也會報假 FAIL。
   - 處理：flip-flop 周圍的邏輯（D 端與 Q 之後）仍由 EQY 的組合邏輯分區證明；flip-flop cell 本身用結構比對（`run_eqy.py` 的 `sequential_cells`）。soc_top 與 picorv32 的合成網表與最終網表，flip-flop 的名稱與功能完全相同（2639／2382 顆 `dfxtp`），所以這個比對沒有假 FAIL。
   - 輸出改成反相（`dfxbp` 的 Q_N）會在切分時被名稱矛盾拒絕，不會走到證明，所以不能拿它來測證明步驟。
   - **clock 接線也證不到**（Phase 4 獨立審查，已驗證）：`sat` strategy 先做 `formalff -clk2ff`，所有 flip-flop 變成同一個隱含 clock；切分出的分區沒有一個以 CLK 為邊界。一顆 flip-flop 的 CLK 改經過反相器（下降緣取樣），EQY 與只比 cell 種類的結構比對都 PASS。處理：`run_eqy.py` 的 `clock_sources` 從每個 clock pin（含 macro 的 `clk*`）往回追，只穿過 buffer／inverter，兩份網表必須追到同一個 port 或常數、反相次數奇偶相同；negative test `flop_clk_inverted`、`clk0_inverted`。
   - **網表解析要涵蓋任何名稱的 macro**（Phase 6，已驗證）：instance 解析原本只認 `sky130_` 開頭，自產 macro `arv_sram_*` 整個被略過，`sram0/clk0`、`clk1` 沒檢查而 `eqy-soc` 照樣 PASS。解析改成任何 cell 名稱，並要求 config `MACROS` 的每個 instance 在兩份網表都被解析到（否則 FAIL）。用 cell 名稱前綴認東西的腳本，換 macro 時都要重查（`hard-macro-integration`）。
6. **OpenROAD 的 pin swap**（Phase 6，已驗證：排除前後各跑一次 EQY）。
   - **症狀**：EQY 在切分步驟停下，`ERROR: conflicting matches for gold bit \_10711_.A: \_10711_.A vs \_10711_.B`，`partitions: 0`；同一個 harden 的 `resizertimingpostcts`／`postgrt` log 有 `RSZ-0043 Swapped pins on N instances`。原因：`repair_timing`（move 序列含 `SwapPinsMove`）把可互換的輸入對調（Hazard3 的 `_10787_` or2 A↔B、`_10793_` o21ai A1↔A2），EQY 用展平後的「instance.腳位」名稱對應，gold 一個訊號對到 gate 兩個。是否發生取決於當次時序修復，同一個設計的不同 harden 不一定都有。
   - **怎麼發現**：`summary.json` 的 `conflicting_matches` > 0 且 `partitions` 0；比對兩份網表同一個 cell 各輸入往回追（穿過非反相 buffer）到的來源，只差在順序。
   - **怎麼繞過**：`run_eqy.py` 的 `pin_swaps()` 找出這種 cell，把被改的腳位名稱寫成 `gold-nomatch`／`gate-nomatch`（每行一個名稱；一行多個是語法錯誤），cell 的輸出仍照名稱證明。另一個做法是 `repair_timing -skip_pin_swap`（OpenROAD 2026-02 有，LibreLane 沒開放，要 plugin），使用者選了 EQY 端（ADR-0018 決定 18）。
   - **防復發**：negative test `o21ai_swap`：把 o21ai 的 A1 與 B1 對調（功能不同、但同一組來源），它一定會被當成 pin swap 排除，`REQUIRE` 規定必須是分區證明失敗。挑的 o21ai 要沒有別的 cell 同時讀它的 A1、A2 來源：EQY 的 `opt` 會合併兩個 cell 裡相同的 OR，對調後變成內部節點的名稱衝突（`conflicting matches for gold bit \_10082_.or0_out`），走不到證明。`mux_swap` 也會被當成 pin swap，但 mux2 模型有別名 wire（`mux_2to10.A0`），仍在切分步驟被拒，證明不了這件事。正向檢查：有 pin swap 的 harden 必須 PASS（Hazard3 `940e395`，16222/16222）。

7. **切分點遺失邏輯關係：好網表也有分區證不出來**（Phase 7，已驗證：同一份網表加減 amend 規則各跑一次 EQY；ADR-0019 決定 23）。
   - **症狀**：`Failed to prove equivalence of partition <top>._10122_.B`，只有一兩個分區，沒有常數對應或名稱衝突；分區 log 有 `Partition ... contains N unused gold inputs`／`unused gate inputs`；SAT 的反例裡某個分區輸入只有一邊用到。同一份網表的 gate-level 模擬 PASS。
   - **機制**：EQY 在每個對應名稱切開，分區輸入一律當獨立的值。gate 端經由一條另有對應名稱的 net 計算（Phase 7：or4 輸入被 OpenROAD 對調後，展開的模型與相鄰的 or2 共用同一個 OR，`_06100_`），gold 端沒有；切開後「這條 net 等於其他輸入的函數」不見了，SAT 找到不可能出現的反例。把那條 net 的名稱排除在對應之外沒用：EQY 改用它的另一個名稱（`_10119_.X` ↔ `_10120_.B`）。共用在哪一個 Yosys 步驟產生沒有查。
   - **怎麼發現**：`run_eqy.py` 第一輪的沒證明分區；看 `work/partitions/<分區>.il` 兩邊的 cell（gate 端讀了 gold 端沒讀的輸入），與 `work/strategies/<分區>/sat/run.log` 的反例。
   - **怎麼繞過**：EQY `[partition]` 段的 `amend <驅動的名稱> <分區>`：把驅動該輸入的分區併進來（參數順序反了會 `no PI/PO link ... re-queue` 而沒有作用）。`run_eqy.py` 的 `amend_rules()`：第一輪只有「分區沒證明」（不超過 `MAX_AMEND` 20 個）時，對每個沒證明分區、每個由組合邏輯驅動的輸入寫一條規則，整個 EQY 重跑一次，只看第二輪；名稱不是單純字元的輸入不寫規則（那個分區就維持 FAIL）。
   - **amend 不能併入 flip-flop**（已驗證，negative test 抓到）：輸入是 flip-flop 輸出（`_20986_.dff0.Q`）時，amend 把那顆 flip-flop 併進分區，規則 5 的空洞證明讓錯誤的 nor2 被「證明」等價（Hazard3 `nand2_to_nor2`，`eqy: PASS`）。所以 sequential cell 的輸出不寫規則，第二輪再檢查被 amend 的分區 RTLIL 沒有 `$dff`／`$sdff`／latch（`amended_sequential()`），有就 FAIL（只拿掉前一道時，這一道對 `nand2_flop_to_nor2` 的網表判 FAIL，已驗證）。凡是會改變分區範圍的 EQY 設定（amend、merge、group），都要先確認不會把 flip-flop 帶進要靠 `sat` 證明的分區。
   - **防復發**：negative test `nand2_comb_to_nor2`（兩個輸入都來自組合邏輯，一定走重試）`REQUIRE` 重試後仍沒證明；`nand2_flop_to_nor2`（兩個輸入都來自 flip-flop）`REQUIRE` 分區沒證明，重試若又併入 flip-flop 就會被抓到。正向檢查：wrapper `f721cff` 的網表必須 PASS，INFO 列出靠重試證明的分區。EQY 升版時重看 `amend` 的語法、參數順序與它併入的範圍。

## RTL vs 網表：尚未解決

LibreLane 的合成一定會跑 Yosys 的 `fsm`（`librelane/scripts/pyosys/synthesize.py` 第 186 行，沒有開關），PicoRV32 又不能改（`third_party/` 唯讀，不能加 `fsm_encoding = "none"`），所以合成網表的狀態機編碼一定和 RTL 不同。合成這一步目前由 gate-level 模擬加 directed 測試補（`dv-directed-tests`）。

Phase 4 agent 再試一次（gold 端照 LibreLane 的順序跑到 `memory_map`、`$alu` 先 techmap、flip-flop 拆成 1-bit）：soc_top 2642/2642 分區證明通過（102 秒），兩邊的 FSM 編碼一致。但在 gold 端植入 4 種錯誤，UART 除頻器的 reset 值、FSM 轉移改錯這 2 種**照樣 PASS**（規則 5 的同一個原因）；只用 PDR 則好設計也報假 FAIL。結論：不加成 checker。

| 問題 | 嘗試 | 結果 |
|---|---|---|
| Yosys `fsm_recode` 把 `cpu_state`、`mem_wordsize` 改成 one-hot，名字相同、意義不同 | EQY `[recode]` | 需要整條向量，網表是逐 bit 命名 |
| 上電值未定、寫入後恆為常數的暫存器（`mem_addr[1:0]`），合成換成常數 | gold 端 `opt_dff -sat`、`opt -full`、`wreduce` | 修掉一些，但改動其他名稱，造成新的對不上 |
| gold 端也跑 `fsm` | 編碼與合成相同 | 仍有分區證不出；且與合成共用同一套轉換，有共模風險 |

## negative test（`neg_eqy.py`）

- picorv32_core（11 個）：輸出 buffer 輸入接 0、輸出 buffer 換成反相器、`count_cycle[45]`／`count_instr[40]` 卡 1、bus-error IRQ 卡 0（這三個是 GL 模擬漏掉的）、暫存器 bit 卡 0、mux 兩輸入對調；Phase 4 加 `nand2_to_nor2`（非常數的邏輯錯誤）、`flop_q_inverted`、`flop_async_reset`（flip-flop 換種類）、`flop_clk_inverted`（clock 接線）。
- 三個設計都有的 `o21ai_swap`（Phase 6，規則 6）。
- Phase 7 三個設計各加 `nand2_comb_to_nor2`、`nand2_flop_to_nor2`（規則 7）：soc_top 12 個、Hazard3 版 16 個、picorv32_core 14 個。
- soc_top（9 個，Phase 6 起 10 個）：SRAM `din0[5]` 卡 0、`csb0` 反相、`host_rdata[7]` 反相、mux 兩輸入對調；Phase 4 加 `clk0_inverted`（SRAM clock 反相）與上面 4 個 Phase 4 案例。Hazard3 版（13 個，Phase 6 起 14 個）再加 3 個 CSR flip-flop 的 D 卡成常數，以及 `reset_b_tied1`（RESET_B 接 1，cell 種類與 clock 都沒變；實際上是被 (b)＋(c) 抓到，不是證明，見下）。
- **被抓到的機制要分開記**（看 `summary.json` 的 `proved`、`constant_matches`、`conflicting_matches`）。EQY 的 FAIL 有三種來源：(a) 分區證明失敗；(b) 常數規則（`found constant ... bit`）；(c) 切分時名稱對應互相矛盾而拒絕（`conflicting matches`），這時一個分區都沒證。
  - 2026-10-03 實測：soc_top 的 `csb0_inverted`、`host_rdata7_inverted`、`mux_swap` 與 picorv32 的 `instr_inverted`、`mux_swap` 都是 (c)；`wdata3_stuck0` 只靠 (b)（15136/15136 分區照樣證明通過）；`din5_stuck0` 是 (a)+(b)（18099/18100）。picorv32 的 `count_cycle45_stuck1`、`count_instr40_stuck1`、`buserr_irq_stuck0`、`x8_bit24_stuck0` 是 (a)+(b)，各 1 個分區沒證明（2026-10-04 第四次 `make phase3` 重現，GL 模擬漏掉的 3 個都在其中）。
  - 只有 (a) 證明「證明本身有效」。qualification 報告要寫出每個案例是哪一種，並確保 (a) 有案例。
  - **改到 reset 連接的錯誤一律落在 (c)**（Phase 5 獨立審查，2026-10-08 實測）：
    - RESET_B 接常數 1（`reset_b_tied1`）是 (b)＋(c)，0 個分區；
    - 改用 `conb_1` tie cell 接 1，結果相同：Yosys 把 tie cell 化成常數；
    - 改接同步器之前的原始 reset（繞過同步器，不是常數），也是 (c)：同步器輸出的 bit 對應到兩個 gate bit。
    - 所以這類錯誤一定判 FAIL，但沒有案例能證明「證明本身」抓得到 reset 錯誤，文件要照實寫，不能寫「只有證明抓得到」。
    - 繞過同步器那個實驗沒有留成案例：它的位置範圍走遍整棵 reset 樹，會接受別的案例的 FAIL 名稱。
  - **案例要斷言抓到它的機制**：`neg_eqy.py` 的 `REQUIRE` 寫出某個案例必須是哪個原因；別的機制碰巧 FAIL，不算抓到（`reset_b_tied1` 要求「mapped to a constant」）。
  - **(a) 的案例也要有非常數的錯誤**：「卡成常數」的 (a) 案例，失敗的分區正好就是被換成常數的那個 bit；反相器、mux 對調都落在 (c)。`neg_eqy.py nand2_to_nor2`（Phase 4）：第一顆 nand2（依 instance 名稱）換成同尺寸的 nor2，名稱與接線不動 → soc_top 18100 個分區中 1 個證明失敗、picorv32 15137 個中 1 個，沒有常數也沒有名稱衝突，證明步驟有效。
  - **抓到的位置要對**（`neg_eqy.py` 的 `fail_names()`、`neighborhood()`，Phase 4）：從 EQY 紀錄取出 FAIL 牽涉的名稱（沒證明的分區、常數 bit、名稱矛盾的兩邊），每一個都要在植入點附近：被改的 cell、被改的腳上的 net、這些 net 上的 cell，遇到 buffer／inverter 繼續往下走（EQY 報的是合成網表的名稱，最終網表在 flip-flop 與 port 之間插了好幾級 buffer，只看一層會誤判）；bus pin 逐 bit 算；clock net 不往下走，只把它往回穿過 buffer 找到的來源加進範圍（`clk0_inverted`）。`neg_eqy.py` 每次自動做交叉檢查：植入點不同的任兩個案例，A 的 FAIL 名稱不能全部落在 B 的範圍內（Phase 4 regress：soc_top 60 組、picorv32 104 組）。沒證明的分區，輸入（分區 `.sv` 的 `__pi_<名稱>__assume`）讀到被改 instance 的節點也算在植入點：被改 cell 的內部節點可能被 EQY 的 `opt` 拿去和別的 cell 共用（Phase 6 `o21ai_swap`：`_17299_.C` 讀 `_10077_.or0_out`），只看 net 會誤判；交叉檢查用同一規則。被接成常數的腳（例如 RESET_B 接 1）不能往兩個方向走：原來的 net 是大扇出的 reset 樹時，範圍會大到接受別的案例的 FAIL；只沿 buffer／inverter 往上游追到 driver（EQY 報的是那個 driver），常數本身不算名稱（Phase 5 Hazard3 `reset_b_tied1`，完整重跑後交叉檢查確認）。為什麼反相器、mux 對調會造成 (c)：推測與 `insbuf off` 的別名處理有關，尚未查證。

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
| 2026-10-04 | Phase 4 預跑（dev fixture） | `clk0_inverted: eqy FAILed, but not at the injection: clk` | 已驗證：EQY 報 `conflicting matches for gold bit \clk: \clk vs \neg_eqy_inv`；位置範圍刻意不走 clock net，所以不含 `clk` | 範圍加入 clock net 的源頭（沿 buffer 往回追）；插反相器的案例各用不同名稱，交叉檢查才會比到它們 | `runs/neg_eqy_dev6/clk0_inverted/` |
| 2026-10-07 | Phase 5 Hazard3 `neg-eqy-soc`（第 8 次 harden 的網表） | `reset_b_tied1: eqy FAILed, but not at the injection`（12/13） | 已驗證：EQY 報 reset 同步器 `_21925_` 與常數 `1'1`；checker 把 `1'1` 當名稱。只拿掉常數後，範圍從 RESET_B 舊 net 往兩邊走遍 reset 樹（1,449 個名稱），交叉檢查發現它接受 `mcycleh13_stuck1`、`minstreth8_stuck1` 的 FAIL | 常數不算名稱；被接成常數的腳只往上游追到 driver（範圍 37 個名稱）。完整重跑 13/13、交叉檢查 144 組 PASS；PicoRV32 兩個設計待重跑確認 | `runs/p5_h3_neg-eqy-soc.log`、`runs/p5_h3_neg-eqy-soc_fix.log`、`signoff/eqy/README.md` |
| 2026-10-07 | Phase 5 ADR-0016 確認 harden（`1d13775`） | 新的範圍（常數不算名稱、接成常數的腳只往上游追）在 PicoRV32 版 soc_top 9/9、Hazard3 13/13，交叉檢查都 PASS | 已驗證 | picorv32_core（`neg-eqy-core`）也用新範圍重跑：11/11、交叉檢查 104 組 PASS（`941e1cb` 的 `harden-core` 網表） | `runs/p5_pico_neg-eqy-soc.log`、`runs/p5_h3_neg-eqy-soc.log`、`runs/p5_pre_neg-eqy-core.log` |
| 2026-10-08 | Phase 5 exit 的獨立審查（`summary.json`）與實驗（p5reg 版圖） | `reset_b_tied1` 說明寫「只有證明抓得到」，實際上 `partitions: 0`、`conflicting matches for gold bit \_21925_.dff0.Q: ... vs 1'1`；改用 tie cell、或改接未同步的 `cpu_resetn`，也都在分區步驟就被拒絕 | 已驗證：三種植入各跑一次 EQY | 說明更正；`REQUIRE`；繞過同步器的版本因位置範圍太大，沒有留成案例 | `signoff/eqy/README.md`、`signoff/eqy/neg_eqy.py` |
| 2026-10-10 | Phase 6 step 4c（`940e395`） | `neg-eqy-soc` 與 `neg-gl-soc` 兩個 CPU 都中止：`KeyError: 'sram0'`；同時 PicoRV32 `eqy-soc` PASS 但 `clock_pins` 不含 `sram0` | 已驗證：`run_eqy.py` 的 instance 解析只認 `sky130_\w+`，自產 macro `arv_sram_*` 沒被解析（從 step 4a 換 macro 起）；`clk0_inverted` 因此找不到 `sram0` | 解析改成任何 cell 名稱（排除 Verilog 關鍵字，5 份網表只多出 `sram0`）；`MACROS` 的 instance 必須被解析到。修正後 `sram0/clk0`、`clk1` 兩個 CPU 都追到 `clk` | `runs/p6_4c_neg-eqy-soc_*.log`、`signoff/eqy/README.md` 判定第 8 點 |
| 2026-10-10 | Phase 6 step 4c，Hazard3 `eqy-soc` | `EQY partition step refused: conflicting matches for gold bit \_10711_.A: \_10711_.A vs \_10711_.B` | 已驗證：OpenROAD pin swap（`RSZ-0043`），見規則 6；只排除 4 個腳位名稱後 16222/16222 證明（scratchpad 實驗 224 秒、正式 308 秒） | 規則 6；`o21ai_swap` | `runs/p6_4c_eqy-soc_h3.log`、`runs/p6_4c2_eqy-soc_h3.log` |
| 2026-10-10 | Phase 6 step 4c，Hazard3 `neg-eqy-soc` | `din5_stuck0: eqy did not FAIL on a partition`，EQY 讀檔 `syntax error, unexpected TOK_ID` | 已驗證：植入程式把 `\sram_din0[31] ` 結尾的空白去掉，逗號併進跳脫名稱 | 跳脫名稱後保留空白；checker 正確判成沒抓到（12/13） | `runs/p6_4c2_neg-eqy-soc_h3.log` |
| 2026-10-10 | Phase 6 step 4c，Hazard3 `neg_eqy.py --cases din5_stuck0,o21ai_swap` | `o21ai_swap: eqy FAILed, but not at the injection: _10099_, _17299_ not connected to the edited cells`（3/16222 沒證明） | 已驗證：三個沒證明的分區輸入都讀 `_10077_.or0_out`（分區 `.sv` 的 `__pi_*__assume`）；`_17299_.C` 是與 o21ai 共用 OR 的 or3 | 使用者選「分區輸入讀被改 cell 也算」：`partition_reads()`，交叉檢查同一規則；`din5_stuck0` 修正後 PASS（1/16222 沒證明＋常數） | `runs/p6_4c3_neg-eqy-2cases_h3.log` |
| 2026-10-13 | Phase 7 wrapper 正式 harden（`f721cff`），查證用 EQY（run guard 關掉） | `Failed to prove equivalence of partition user_project_wrapper._10122_.B`（1/16149），反例 `_10120_.B = 1`：gold 0、gate 1 | 已驗證：or4 `_10121_` pin swap 後 gate 端與 `_10119_` 共用 OR，分區在 `_10120_.B` 切開；排除名稱兩次仍 FAIL，`amend _10119_.X _10122_.B` 16149/16149；gate-level 模擬 16/16 PASS | 規則 7；使用者選「沒證明時自動 amend 重試一次」 | scratchpad `eqy_f`、`eqy_x1`–`eqy_x5`；ADR-0019 決定 23 |
| 2026-10-13 | 同上，amend 重試第一版的 negative test（Hazard3 `--cases`，run guard 關掉） | `nand2_to_nor2: eqy FAILed without 'partitions not proved after the amend retry'`；run.log 是 `eqy: PASS`（16221/16221） | 已驗證：兩條 amend 規則的輸入都是 flip-flop 輸出，第二輪分區 RTLIL 多 2 個 `$sdff`，規則 5 的空洞證明；wrapper 的那次 PASS 也有 3 個 `$sdff` | 不對 sequential 輸出寫規則，第二輪檢查被 amend 分區沒有 sequential cell；新增 `nand2_flop_to_nor2`、`nand2_comb_to_nor2` | scratchpad `neg_eqy_amend`；ADR-0019 決定 23 |
| 2026-10-10 | Phase 6 step 4c，PicoRV32 `neg-eqy-soc`（10 個） | `o21ai_swap: eqy FAILed without 'partitions not proved' (partition step refused: conflicting name matches)`，衝突 `\_10082_.or0_out vs \_19506_.or0_out` | 已驗證：EQY 的 `opt` 把 `_10082_` 與 `_19506_` 相同的 OR 合併；「別的 cell 同時讀 A1、A2 來源」的條件也預測到 Hazard3 的 `_10043_` | 使用者選「挑不共用 OR 的 o21ai」，REQUIRE 不變；其餘 9 個與交叉檢查 60 組 PASS | `runs/p6_4c3_neg-eqy-soc_pico.log` |
| 2026-10-14 | arvinsa-rtl-gds Phase 7 步驟 8（`neg_eqy.py --design user_project_wrapper`，dev fixture） | wrapper 植入 flip-flop D 綁常數：`eqy: FAIL`，但 FAIL 名單除了植入點還有 `_10122_.B`，negative test 的位置檢查判「not at the injection」；flip-flop 驅動的 nand2 改 nor2 在 partition step 被 `conflicting matches` 擋下 | 已驗證：有常數對應時 `run_eqy.py` 依規則 7 不做 amend 重試，這份網表靠重試才證明的分區（決定 23）就留在名單裡；第一個符合條件的 nand2（`_09878_`）直接驅動 flip-flop D，名稱衝突 | checker 本身沒有漏抓（兩例都 FAIL）。改成 D 接反相器也不行：反相器輸入沿用原 D 的 net 名稱，EQY 把同一個 gold bit 對到兩處，在 partition step 拒絕。wrapper 只留 `nand2_comb_to_nor2`（重試照跑、只剩植入點）；其他留在 soc_top 的設計驗證。教訓：設計有「靠重試才證明」的分區時，阻止重試的植入（常數、名稱衝突）會連帶列出它 | `signoff/eqy/neg_eqy.py`、ADR-0019 決定 25 |
