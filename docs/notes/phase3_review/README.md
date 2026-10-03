# Phase 3 獨立審查的實驗紀錄（2026-10-04）

找 checker 漏洞的審查 agent 做的實驗，原始輸出在 session 暫存目錄（會消失），這裡保存結論需要的部分。對應 `docs/phase_exit/phase3.md` 已知限制 4、14。

| 檔案 | 內容 |
|---|---|
| `drc_position_compare.py` | 逐一比對 soc_top 的 Magic DRC 報告（SRAM 外框內）與 SRAM 單獨檢查的報告（平移到 `sram0` 的位置 (301.76, 364.48)）。用法：`python3 drc_position_compare.py <SRAM 單獨的 drc.magic.rpt> <soc_top 的 drc.magic.rpt>`（審查時用的是 `runs/sram_drc_baseline` 與第四次 `make phase3` 的報告，約需數分鐘）。結果：4,665,810 個錯誤框中 4,651,644 個位置完全相同、7,192 個落在同規則的框內、6,974 個與同規則的框相接或重疊、0 個無法解釋。Phase 4 改寫 `check_soc.py magic_drc` 時參考 |
| `eqy_nand2nor.log` | 最終網表裡 `_14294_` 從 `sky130_fd_sc_hd__nand2_2` 改成 `nor2_2`（只改這一行，名稱不動）後跑 `run_eqy.py --netlist`：18100 個分區中 1 個沒證明（`soc_top._14295_.B`），沒有常數也沒有名稱衝突。這是第一個由證明步驟抓到的非常數錯誤 |
| `eqy_dout_swap.log` | `sram0` 的 `dout0[3]`、`dout0[4]` 接線對調：EQY 在切分時拒絕（名稱對應矛盾），也算抓到，但沒有走到證明 |
