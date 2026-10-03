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
1. harden run 自己的所有檢查都 PASS：`<run>_signoff/result.txt` 是 `harden-core: PASS` 或 `harden-soc: PASS`（signoff 門檻與 golden、該設計的專用檢查、來源追溯）。
2. EQY 最後一行是 `DONE (PASS, rc=0)`。
3. 分區清單不是空的，而且每個分區都有 `Proved equivalence of partition` 紀錄。
4. 切分紀錄（`work/partition.log`）沒有 `found constant ... bit`。這行表示 gate 端某個 bit 是常數，EQY 會直接把 gold 端對應的 bit 換成那個常數，**之後不再證明它**。negative test `wdata3_stuck0`（把 `mem_wdata[3]` 接成 0）原本就是這樣漏掉、判 PASS 的。正向的 run 沒有出現過這一行，所以出現就 FAIL。
5. 切分紀錄沒有 `ERROR: conflicting ... for`。這表示 EQY 在切分時遇到互相矛盾的名稱對應而中止（試做時看過 `conflicting matches for gold bit eoi[0]`），沒有做任何證明。

## Negative test（`make neg-eqy-core`、`make neg-eqy-soc`）

在最終網表的複本植入錯誤，每一個都必須讓 `run_eqy.py` FAIL，且失敗原因是有分區證不出來（不是缺檔之類的其他錯誤）。案例清單在 `neg_eqy.py` 的開頭。

## 執行時間（Apple Silicon，10 核）

| 對象 | 分區數 | 時間 |
|---|---|---|
| picorv32_core（Phase 2 網表） | 15137 | 約 6.5 分鐘（`-j 8`） |
| soc_top（Phase 3 網表，正式 run 2） | 18100 | 約 5 分鐘（297 秒，`-j 10`） |
