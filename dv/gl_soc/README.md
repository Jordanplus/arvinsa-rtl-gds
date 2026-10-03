# gl_soc：soc_top 的 gate-level 模擬（`make gl-soc`）

`project-plan.md` §7.1 L2：最終網表（含 SRAM 模擬模型）跑 SoC 測試，且 RTL 與網表的行為逐 cycle 一致。

## 做法：RTL 與網表 lockstep

同一個 testbench（`dv/tb/tb_soc.v`，define `GL_LOCKSTEP`）裡放兩份 SoC，輸入完全相同：

| instance | 內容 |
|---|---|
| `dut` | RTL `soc_top`（`rtl/rtl.f`），與 `make regress-rtl` 相同 |
| `dut_gl` | `make harden-soc` 的最終網表 `runs/soc_top/final/nl/soc_top.nl.v`，module 改名為 `soc_top_gl`；sky130 cell 用 `-DFUNCTIONAL -DUNIT_DELAY=#1` 的 Verilog 模型（只有 flip-flop 有 1 ns 延遲，組合邏輯無延遲），SRAM 用與 RTL 相同的模擬模型 |

`dv/monitors/gl_lockstep.v` 在每個 clock 下降緣（兩份都穩定後）比對：
- soc_top 的所有輸出：`uart_tx`、`gpio_out`、`trap`、`host_rdata`
- SRAM port 0 的輸入腳：`csb0` 每個 cycle 都比；`web0`、`addr0`、`wmask0` 在 `csb0=0`（有存取）時比；`din0` 在寫入時比 `wmask0` 為 1 的 byte

**X 的規則**：只比 RTL 是 0 或 1 的 bit，這時網表必須完全相同（網表是 X 或 Z 也算不同）。RTL 是 X 的 bit（例如沒有 reset、還沒被寫過的暫存器）不比，因為合成可以合法地替它選一個值。

Phase 1 的其他 checker（測試結束協定、trap、timeout、UART、bus assertion、X checker、SRAM port、IRQ、coverage……）照常看 RTL 那一份。所以：
- RTL 那一份 PASS 代表測試本身通過；
- lockstep 沒有任何不一致，代表網表在這些測試裡，每個 cycle 的輸出與 SRAM 存取都和 RTL 相同。

## 判定（`run_gl_soc.py`）

PASS 需要全部成立：
1. harden run 自己的所有檢查都 PASS：`runs/soc_top_signoff/result.txt` 是 `harden-soc: PASS`（signoff 門檻與 golden、soc 專用檢查、輸入一致、來源追溯）。
2. `dv/tests.toml` 中所有不是 `negative_only` 的測試（13 支）在這個 build 上都 PASS（Phase 1 的全部 checker）。
3. 每支測試的 `tb_result.txt` 有 `fail.gl_lockstep=0`，而且 `gl_compares` > 0（比對真的有執行）。

## Negative test（`make neg-gl-soc`，`neg_gl_soc.py`）

在最終網表的複本植入錯誤（與 `signoff/eqy/neg_eqy.py` 的 soc_top 案例相同：SRAM `din0[5]` 卡 0、`csb0` 反相、`host_rdata[7]` 反相、mux 兩輸入對調），每一個都要讓 gl-soc FAIL，而且原因必須是至少一支測試的 `fail.gl_lockstep` > 0（不是編譯錯誤或其他原因）。為了節省時間，只跑最長的兩支（memtest、boot_uart_max）以外的 11 支測試。所有案例共用同一個建置目錄，所以一次只跑一個案例。

## 限制

- 只看得到 soc_top 的輸出與 SRAM port 0。內部錯誤若在這些測試中沒有傳到這些點，就不會被發現。formal equivalence 只證明合成網表與最終網表等價（`signoff/eqy/README.md`）；RTL 到合成網表這一段只有這裡的模擬，firmware 沒用到的邏輯沒有檢查（`docs/phase_exit/phase3.md` 已知限制 11）。
- `UNIT_DELAY` 模擬不檢查時序；時序由 9 個 corner 的 STA 負責。
