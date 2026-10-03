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
3. **判定**：`DONE (PASS, rc=0)`；每個分區都有 `Proved equivalence`；partition log 出現 `found constant ... bit` 一律 FAIL（EQY 漏洞：輸出被植入卡 0 時，所有分區照樣證明通過）；植入後 EQY 以 `conflicting matches` 拒絕切分，也算抓到。
4. **時間**：picorv32 約 6.5 分（15137 分區，`-j 8`）、soc_top 約 5 分（18100 分區，297 秒，`-j 10`）。PDR 找到反例時，SBY 需要 `yices` 轉波形（nix-shell 沒有），只影響除錯，不影響 FAIL 判定。

## RTL vs 網表：尚未解決

| 問題 | 嘗試 | 結果 |
|---|---|---|
| Yosys `fsm_recode` 把 `cpu_state`、`mem_wordsize` 改成 one-hot，名字相同、意義不同 | EQY `[recode]` | 需要整條向量，網表是逐 bit 命名 |
| 上電值未定、寫入後恆為常數的暫存器（`mem_addr[1:0]`），合成換成常數 | gold 端 `opt_dff -sat`、`opt -full`、`wreduce` | 修掉一些，但改動其他名稱，造成新的對不上 |
| gold 端也跑 `fsm` | 編碼與合成相同 | 仍有分區證不出；且與合成共用同一套轉換，有共模風險 |

## negative test（`neg_eqy.py`）

- picorv32_core（7 個）：輸出 buffer 輸入接 0、輸出 buffer 換成反相器、`count_cycle[45]`／`count_instr[40]` 卡 1、bus-error IRQ 卡 0（這三個是 GL 模擬漏掉的）、暫存器 bit 卡 0、mux 兩輸入對調。
- soc_top（4 個）：SRAM `din0[5]` 卡 0、`csb0` 反相、`host_rdata[7]` 反相、mux 兩輸入對調。
- **被抓到的機制要分開記**（看 `summary.json` 的 `proved`、`constant_matches`、`conflicting_matches`）。EQY 的 FAIL 有三種來源：(a) 分區證明失敗；(b) 常數規則（`found constant ... bit`）；(c) 切分時名稱對應互相矛盾而拒絕（`conflicting matches`），這時一個分區都沒證。
  - 2026-10-03 實測：soc_top 的 `csb0_inverted`、`host_rdata7_inverted`、`mux_swap` 與 picorv32 的 `instr_inverted`、`mux_swap` 都是 (c)；`wdata3_stuck0` 只靠 (b)（15136/15136 分區照樣證明通過）；`din5_stuck0` 是 (a)+(b)（18099/18100）。
  - 只有 (a) 證明「證明本身有效」。qualification 報告要寫出每個案例是哪一種，並確保 (a) 有案例。為什麼反相器、mux 對調會造成 (c)：推測與 `insbuf off` 的別名處理有關，尚未查證。

## 用完後

更新「經驗紀錄」；Yosys／EQY 升版時重跑 negative test，確認常數漏洞的偵測仍有效。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-03 | arvinsa-rtl-gds eqy1 | `partition: finished (returncode=-11)` | 已驗證：stack 不足 | `ulimit -s 65520` | `signoff/eqy/README.md` |
| 2026-10-03 | neg-eqy | 輸出卡 0 仍 PASS | 已驗證：`found constant gate bit` 不證明 | 判定規則 3 | `runs/neg_eqy_picorv32_core` |
| 2026-10-03 | neg-eqy-soc（正式 run 2 網表） | 4/4 抓到，其中 `csb0_inverted`、`host_rdata7_inverted`、`mux_swap` 是 `partition step refused: conflicting name matches` | 已驗證（`runs/neg_eqy_soc_top/*/eqy/summary.json`） | 見 negative test 一節；`make phase3` 重跑完整 neg-eqy-core 後補記各案例的機制 | `runs/p3_neg_eqy_soc.log` |
