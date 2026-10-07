# Formal equivalence（EQY）

`make eqy-core`、`make eqy-soc` 用 YosysHQ EQY（LibreLane nix-shell 內的 Yosys 0.62）證明 **合成後的網表** 與 **最終網表** 功能等價。

- **Formal equivalence**：用數學方法證明兩份電路在所有輸入、所有狀態下行為相同。模擬只能證明「跑過的情況」正確，formal 證明的是全部情況。
- **EQY 的做法**：先把兩份網表在「名字相同的訊號」切開，切成很多小塊（分區，partition），再對每一塊證明「輸入相同時輸出也相同」。所有分區都證明成功，就等於整顆電路等價。

## 證明的範圍

| 端 | 檔案 | 內容 |
|---|---|---|
| gold（參考） | `<run>/*-yosys-synthesis/<design>.nl.v` | Yosys 合成的結果，placement 之前 |
| gate（被檢查） | `<run>/final/nl/<design>.nl.v` | OpenROAD 改過之後的最終網表：resizer 換 cell 尺寸、插 buffer、CTS、hold buffer、antenna diode、tie cell |

兩端都用 sky130_fd_sc_hd 的 Verilog 模型（`eqy.formal_pdk_proc` 轉成 formal 可用的形式）；SRAM macro 兩端都是 blackbox（只有 port，沒有內容）。

**涵蓋到的**：從合成網表到 GDS 對應網表之間的所有改動，以及任何人為或工具在最終網表上造成的錯誤。Phase 2 GL 模擬漏掉的 3 種網表錯誤（`count_cycle[45]` 卡 1、`count_instr[40]` 卡 1、bus-error IRQ 卡 0）都在這裡被抓到（見下方 negative test）。

**沒涵蓋到的**：RTL → 合成網表這一步（Yosys 合成本身）。這一段目前靠 gate-level 模擬：`make gl-core`（上游 ISA regression，RTL 與網表 bus trace 逐筆比對）與 `make gl-soc`（SoC 測試，RTL 與網表每個 cycle 比對）。RTL 對網表的 formal 證明試過、尚未成功，原因見下一節。

## 為什麼不是 RTL 對最終網表

照 `project-plan.md` §7.1 L4 原本要證 RTL 對最終網表。試做時（2026-10-03，Phase 2 的 PicoRV32 網表）遇到下列問題，前三個已解決並用在現行腳本，後兩個沒有解決：

| 問題 | 現象 | 處理 |
|---|---|---|
| EQY 切分步驟 stack 不夠 | `partition` 以 SIGSEGV（returncode −11）結束，沒有任何分區 | 用 `ulimit -s 65520`（macOS 主執行緒上限 64 MB）後，12 秒完成 |
| Yosys 0.62 攤平後保留 `$scopeinfo` cell | 同上的當機前置條件之一 | script 加 `delete t:$scopeinfo` |
| OpenROAD 在 flip-flop 與輸出 port 之間插 buffer，並把 flip-flop 的輸出線改名（Phase 2 網表 2382 顆中 198 顆） | 這些 flip-flop 對不上 RTL 的暫存器，分區變成含未知初值的狀態，induction 證不出來 | `[options] insbuf off`：buffer 兩端的線被視為同一個訊號的別名 |
| Yosys 合成把狀態機重新編碼（`cpu_state` 8-bit one-hot → 6-bit、`mem_wordsize` 2-bit → 3-bit one-hot，見合成 log 的 FSM_RECODE） | gate 的 `cpu_state[0]` 和 RTL 的 `cpu_state[0]` 名字相同、意義不同 | **未解決**。EQY 的 `[recode]` 需要整條向量的暫存器，而網表是逐 bit 命名 |
| 合成把「上電值未定、寫入後恆為常數」的暫存器換成常數（例：`mem_addr[1:0]`） | RTL 允許這些 bit 在第一次寫入前是任意值，EQY 的 induction 會走到這種狀態 | **部分解決**。gold 端加 Yosys 最佳化會連帶改動其他名稱，造成新的對不上 |

合成網表對最終網表時，兩端都是 Yosys 的輸出，狀態機編碼與暫存器名稱一致，上面兩個未解決的問題都不存在。

## 判定（`run_eqy.py`）

PASS 需要全部成立：
1. harden run 自己的所有檢查都 PASS：`<run>_signoff/result.txt` 是 `harden-core: PASS` 或 `harden-soc: PASS`（signoff 門檻與 golden、該設計的專用檢查、來源追溯），而且 run 是從目前的 commit 產生的（`provenance.json` 的 `repo_head` 等於 HEAD；`signoff/scripts/run_guard.py`，Phase 4）。判定前先刪掉輸出目錄，被拒絕時不會留下上一次的結果。
2. EQY 最後一行是 `DONE (PASS, rc=0)`。
3. 分區清單不是空的，而且每個分區都有 `Proved equivalence of partition` 紀錄。
4. 切分紀錄（`work/partition.log`）沒有 `found constant ... bit`。這行表示 gate 端某個 bit 是常數，EQY 會直接把 gold 端對應的 bit 換成那個常數，**之後不再證明它**。negative test `wdata3_stuck0`（把 `mem_wdata[3]` 接成 0）原本就是這樣漏掉、判 PASS 的。正向的 run 沒有出現過這一行，所以出現就 FAIL。
5. 切分紀錄沒有 `ERROR: conflicting ... for`。這表示 EQY 在切分時遇到互相矛盾的名稱對應而中止（試做時看過 `conflicting matches for gold bit eoi[0]`），沒有做任何證明。
6. **兩份網表的 sequential cell（flip-flop、latch、clock gate）是同樣的 instance、同樣的功能**，只允許 drive strength 不同（Phase 4）。這一項在 EQY 之外比對，因為 EQY 的 `sat` strategy 證不到 flip-flop 本身的行為：把一顆 `dfxtp_2` 換成 reset 時會清除的 `dfrtp_2`（RESET_B 接 `resetn`），EQY 仍是 18100/18100 個分區證明通過（`neg_eqy.py flop_async_reset`）。原因推測是含 flip-flop 的分區，初始狀態的約束本身無解，base case 什麼都沒證（agent 實驗，紀錄沒有存進 repo）；soc_top 的 2639 個含 flip-flop 的分區每個都只有 2 顆 `$dff`。flip-flop 周圍的邏輯仍由 EQY 證明。
7. **每個 sequential cell 的 clock pin 與 macro 的 `clk*` pin，在兩份網表追到同一個來源**（Phase 4 獨立審查後加）：從 pin 往回走，只穿過 buffer／inverter（含 CTS 的 clkbuf、delay buffer），走到 input port、常數或其他 cell 的輸出為止，並記下反相次數的奇偶。EQY 也看不到 clock：`sat` strategy 會先做 `formalff -clk2ff`，把所有 flip-flop 改成同一個隱含的 clock；第 6 點只比 cell 種類。審查者實測：讓一顆 flip-flop 的 CLK 經過一顆新加的反相器（變成下降緣取樣），第 6 點照樣 2639/2639 相同，切分出的 18100 個分區沒有一個以 CLK 為邊界。soc_top 是 2639 個 CLK 與 `sram0/clk0` 都追到 `clk`、`sram0/clk1` 追到常數 0；picorv32 是 2382 個 CLK 都追到 `clk`。

## Negative test（`make neg-eqy-core`、`make neg-eqy-soc`）

在最終網表的複本植入錯誤，每一個都必須讓 `run_eqy.py` FAIL，且失敗原因是有分區證不出來、常數規則、名稱對應矛盾、sequential cell 不同或 clock 來源不同（不是缺檔之類的其他錯誤）。案例清單在 `neg_eqy.py` 的開頭。

Phase 4 加了三件事（前兩件是 `docs/phase_exit/phase3.md` 已知限制 4、16）：
- **`nand2_to_nor2`**：第一顆 nand2（依 instance 名稱排序）換成同尺寸的 nor2，名稱與接線不動。這種錯誤不是常數、也不會造成名稱矛盾，只有證明步驟抓得到。soc_top 與 picorv32_core 都是 1 個分區證不出來。
- **`flop_q_inverted`、`flop_async_reset`**：第一顆 `dfxtp_2` 換成輸出反相的 `dfxbp_2`（Q_N）或 reset 會清除的 `dfrtp_2`。前者在切分時就因名稱矛盾被拒絕；後者 EQY 全部證明通過，只有判定第 6 點抓得到。
- **FAIL 的位置要對得上植入點**：從 EQY 的紀錄取出 FAIL 牽涉的名稱（證不出來的分區、被換成常數的 bit、名稱矛盾的兩邊），每一個都必須落在植入點附近：被改到的 cell、它被改到的腳上的 net（bus pin 只算改到的那幾個 bit），以及這些 net 上的 cell；遇到 buffer／inverter 時繼續往下走（placement 與 routing 會在合成網表的 flip-flop 和 port 之間插好幾級 buffer，EQY 報的是合成網表的名稱）。clock net 不往下走（否則整棵 clock tree 都算「附近」），只把它的源頭算進來：沿 clock buffer 往回追到的 port（`clk`）。`clk0_inverted` 第一次預跑時 EQY 報的正是 `clk` 與反相後的線名稱衝突，沒有這條規則會被判成「不在植入點附近」。
- **位置檢查要分得出不同案例**（Phase 4 獨立審查後加）：`neg_eqy.py` 最後對每一對改到不同 instance 的案例檢查，A 的 FAIL 名稱不能全部落在 B 的植入點附近，否則「在植入點附近」等於什麼都接受。改到同一顆 flip-flop 的 `flop_*` 案例之間不比。審查前 bus pin 整條一起算，`din5_stuck0` 的範圍有 224 個名稱、包含全部 32 個 `din0` bit；改成逐 bit 後是 10 個。已知限制：新接上 reset 這類大扇出 net 的案例（`flop_async_reset`），範圍仍包含整棵 reset buffer 樹（291 個名稱）。
- **被接成常數的腳只往上游追**（Phase 5）：Hazard3 版 `reset_b_tied1` 把一顆 flip-flop 的 RESET_B 接成 1。EQY 報的是 reset 同步器 `_21925_`（那條 reset 線經過 17 級 buffer／delay cell 的源頭）與常數 `1'1`。原本的範圍從 RESET_B 原來的 net 往兩個方向走，走遍整棵 reset 樹，共 1,449 個名稱；把常數拿掉後，交叉檢查發現這個範圍也接受 `mcycleh13_stuck1`、`minstreth8_stuck1` 的 FAIL 名稱。現在 `fail_names()` 不把常數當名稱；被接成常數的腳，原來的 net 只沿 buffer／inverter 往上游追到 driver，不往下游擴散。`reset_b_tied1` 的範圍變成 37 個名稱，Hazard3 版完整重跑 13/13、交叉檢查 144 組都分得開（2026-10-07，`runs/p5_h3_neg-eqy-soc_fix.log`）。PicoRV32 的兩個設計還沒有用這個版本重跑。

Phase 4 獨立審查後再加兩個案例：
- **`flop_clk_inverted`**（兩個設計）：第一顆 `dfxtp_2` 的 CLK 改經過一顆新加的 `clkinv_1`。EQY 的分區全部證明通過，第 6 點也相同，只有第 7 點抓得到。
- **`clk0_inverted`**（soc_top）：`sram0` 的 `clk0` 改經過一顆新加的 `clkinv_1`。

Phase 5 的 Hazard3 版（`make neg-eqy-soc CPU=hazard3`，`--design soc_top_hazard3`，13 個）：soc_top 的 9 個，加上 `mcycleh13_stuck1`、`minstreth8_stuck1`、`irq0_stuck0`（CSR flip-flop 的 D 接成常數，對應 picorv32_core 那三個 GL 模擬漏掉的案例），以及 `reset_b_tied1`（第一顆 `dfrtp` 的 RESET_B 接 1，永遠不 reset；cell 種類與 clock 都沒變，第 6、7 點抓不到，只能靠證明）。

## 執行時間（Apple Silicon，10 核）

| 對象 | 分區數 | 時間 |
|---|---|---|
| picorv32_core（Phase 2 網表） | 15137 | 約 6.5 分鐘（`-j 8`） |
| soc_top（Phase 3 網表，正式 run 2） | 18100 | 約 5 分鐘（297 秒，`-j 10`） |
