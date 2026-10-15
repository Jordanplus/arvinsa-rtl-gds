# 文件核對的處理（2026-10-14，主 checkout，未提交）
全部 28 列（錯誤 5、誤導 23）已修：
- ADR-0019：A01 neg-precheck 24→25；A06 決定 5 補 precheck PDK 的預建 SRAM 另有 10 個 nsdm/psdm；A08 決定 12 補「後來改 50%」；A12 決定 9 讀取時序（第三個上升緣，wb_host_bridge.v 16–18、100–108）；A15 決定 16 補 C80a–c 已做；A20 0.6→0.5 倍（附算式）；A21 決定 19 的 50 mV 標「決定 20 取消」；A33 decap_3 2,461,688 含 2,904 endcap；A42 neg-pnr 71→82、neg-eqy 18→16；A44 錄波的植入在 soc_top 做。
- 筆記：A49 dmesg 原文沒存檔與旁證。
- golden README：A50 誤差改由決定 25；A51 產生方式／來源 run 分清建立時（f721cff）與現在（7eff65a）；A53 clock 一列改寫（彙總值意思、skew 分析標推測）；A58 0.576 ns 標出處；A61 對現版 425 相同 4 不同；decap_3 兩個數字說明。
- skill／README／流程：S03 colima→lima；S06 記憶體歸因標「沒分開實驗」；S09、S12、S13、S14 最壞組合標成已只當參考、估法改慢 corner／pattern；S10 54 mV 換成 ADR 的數字；S16 tap cell 寫結果；S18 neg_ir 案例分設計；S21 C80a–c；S22、S23 knowledge 證據路徑改 p7_formal_signoff／p7_decap_signoff；S24 cts 規則 6 與 phase-exit-review 規則 3 加 worst_hold 彙總值（LibreLane library.py 166–173 已核對）；S30 流程文件 ir_caravel 改 pattern 20 mV；S31 低估倍數改同條件 4.94→45.56 mV（約 9 倍）；S36 timing-constraints-sdc 改成「沒有自動防護」（列已知限制）。
- 程式說明：neg_precheck.py 三個 positive control；ir_caravel.py make neg-ir-caravel；neg_run_guard.py 列出 wrapper 的 5 個步驟。
- 無法核對：A04（本機沒有 cf-precheck 原始碼）、A49、S10、S13（已在文件標明）。
