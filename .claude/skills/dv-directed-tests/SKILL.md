---
name: dv-directed-tests
description: 找出 regression 沒用到的功能（gate-level 模擬或 formal 的植入錯誤漏掉的地方、上游測試沒碰到的指令或 IRQ），寫 directed firmware 測試補上，並用植入錯誤證明新測試抓得到時使用。Use when closing verification coverage gaps with directed firmware tests and qualifying them by bug injection.
---

# 用 directed 測試補驗證缺口

testbench 與 checker 的架構以 `dv/README.md`、`docs/spec/soc_spec.md` §6–7 為準；網表模擬看 `gate-level-simulation`；植入錯誤的通則看 `signoff-checker-qualification`。本 repo 實例：`fw/tests/counters/`、`fw/tests/buserr/`（Phase 4）、`dv/gl_soc/neg_gl_soc.py`。

名詞：**directed 測試**：針對一個特定功能寫的測試，明確檢查它的結果；相對於「跑一般程式、順便用到」。**coverage 缺口**：regression 從沒用到的功能，那裡壞掉不會有任何測試 FAIL。

## 規則（已驗證）

1. **缺口從「漏掉的植入錯誤」找**：每個沒被抓到的植入錯誤都指向一個沒被用到的功能。Phase 2 的 gl-core 漏掉 `count_cycle[45]`／`count_instr[40]` 卡 1、bus-error IRQ 卡 0，原因是上游 firmware 從不讀 `rdcycleh`／`rdinstreth`、從不做非對齊存取。formal（EQY）只證明合成網表 → 最終網表，合成這一步仍要靠模擬，所以這類缺口不能只靠 formal 補（`docs/phase_exit/phase3.md` 已知限制 11）。
2. **檢查的是規格上的實際行為，不是自己以為的行為**：先讀 RTL 原始碼，引用行號寫進測試檔頭。PicoRV32 對非對齊存取只把 `irq[2]` 設成 pending，存取照樣以清掉低 2 bit 的 word 位址送上 bus，寫入也照寫（`picorv32.v` 382、403–406、1922–1935）。第一版 `buserr` 假設寫入會被擋下，RTL 模擬就報 fail code `0x22`。
3. **編譯器會改寫存取**：GCC 知道位址是非對齊時，會把 `*(volatile uint32_t *)` 拆成 byte／halfword 存取，測試就什麼都沒測到。要測特定指令時用 inline assembly，並看反組譯（`riscv64-elf-objdump -d`）確認指令真的是 `lw`／`sw`。
4. **寫出測不到的部分**：只跑幾千個 cycle，64-bit 計數器高半部「卡 0」要 2^32 個 cycle 才看得到，只能抓「卡 1」；寫在測試檔頭與 README。
5. **新測試要登記在每一個地方**：`fw/Makefile` 的 `TESTS`、`dv/tests.toml`（`expect_uart`、`sig_rule`、`expect_gpio`、`max_cycles` ≥ 實測 5 倍）、spec 的測試清單；測試若刻意違反 spec 的某條預設（例如 `irq[2]` 預設要遮蔽），spec 那一條也要改。
6. **每個新測試都要證明抓得到它要補的錯誤**：
   - RTL 層不能改第三方原始碼（`third_party/` 唯讀），所以在網表植入那個錯誤（`neg_gl_soc.py`：flip-flop 的 D 接常數），只跑新測試，必須在 RTL／網表 lockstep 比對 FAIL。
   - 再跑一次完整 `make regress-rtl` 與 `make neg-rtl`，確認既有的測試與植入案例沒有被影響。
7. **測試名稱、fail code 與 UART 輸出固定**：UART 文字要固定（不要印計數器值之類每次可能不同的數字），失敗時用 fail code 區分是哪一項。

## 用完後 / 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-04 | `buserr` 第一版 | 反組譯看到 `lhu`、`lbu`／`sb`，沒有 `lw`／`sw` | 已驗證：GCC 依已知的對齊拆開存取 | 改 inline assembly（規則 3） | `fw/build/buserr.lst`（建置產物） |
| 2026-10-04 | `buserr` 第二版 | RTL 模擬 fail code `0x22`：非對齊 `sw` 改到了記憶體 | 已驗證：PicoRV32 照樣送出存取（規則 2） | 測試改成檢查實際行為：IRQ 一次、pending `1<<2`、寫入對齊的 word | `third_party/picorv32/picorv32.v` 382、403–406、1922–1935 |
| 2026-10-04 | Phase 4 | 3 個 Phase 2 漏掉的錯誤，在新測試上全部被 lockstep 抓到 | 已驗證 | `neg_gl_soc.py` 加 3 個案例 | `docs/phase_exit/phase4.md` |
