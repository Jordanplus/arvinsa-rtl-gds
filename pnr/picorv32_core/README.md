# picorv32_core：單獨 harden PicoRV32（Phase 2）

Phase 2（`project-plan.md` §8）要做的事：用 SoC 裡 `u_cpu` 的同一組參數，把 PicoRV32 單獨（不含 SRAM）跑完 LibreLane Classic flow 到 GDS。這一步要打通流程、量出真實的面積與時序，作為決定 `soc_top` `DIE_AREA` 的依據。

```bash
make harden-core   # 約 12–15 分鐘：參數檢查 → LibreLane → signoff checker
make gl-core       # 約 2.5 分鐘：在最終網表上跑上游 testbench.v -DSYNTH_TEST（gate-level ISA regression）
make neg-gl-core   # 約 6 分鐘：在網表植入 2 個錯誤，確認 gl-core 的 checker 會 FAIL
make soc-area      # 約 10 秒：由 harden 結果估算 soc_top 的 standard cell 面積
make phase2        # env-check-flow 加上以上四項依序執行，共約 24 分鐘
```

產出位置：LibreLane run 在 `runs/picorv32_core/`（GDS 在 `final/gds/picorv32.gds`），checker 結果在 `runs/picorv32_core_signoff/`。

## 檢查項

| 檢查 | 程式 | PASS 條件 |
|---|---|---|
| CPU 參數一致 | `cpu_params.py` | `config.json` 的 `SYNTH_PARAMETERS` 與 `rtl/soc/soc_top.v` 裡 `u_cpu` 的 13 個參數逐一相同（用 Yosys 讀 RTL 取值，不是比對字串）。Yosys 看不到的寫法直接判 FAIL：`defparam`、有沒有 `SYNTHESIS` define 時參數不同、config 的 `pdk::`／`scl::` 條件區塊。flow 跑完後再比對 run 實際用的參數（`resolved.json`） |
| LibreLane 內建 checker | flow 本身 | lint、合成、power grid、DRC、LVS、XOR、setup／hold 違規等，任何一項 FAIL 時 flow 就中止 |
| signoff metrics | `signoff/scripts/check_signoff.py` + `signoff/limits/picorv32_core.toml` | 24 項必須等於指定值（DRC、LVS、antenna、slew／cap／fanout 違規 = 0 等）；9 個 corner 的 setup 和 hold worst slack 都 ≥ 0 且 < 40 ns（STA 找不到受約束的路徑時會報極大值或 inf，這要算 FAIL），少一個 corner 也算 FAIL；nom_tt setup slack ≥ 4 ns（時脈週期的 10%）；325 個 metrics 與 golden 相同，只有 detailed routing 會造成微小差異的族群（slack、線長、via、功耗、IR drop）允許明確的小誤差（見 `signoff/golden/picorv32_core/README.md`） |
| 沒接線的 pin | `check_disconnected.py` | LibreLane 的沒接線 pin 表中，`picorv32` 剛好是 35 個 PCPI 輸入（`ENABLE_PCPI=0` 時不用），沒有電源 pin，也沒有其他列。LibreLane 產生這張表時本來就跳過 tie cell（`conb_1`）與 CTS dummy load（`clkload*`），這兩類不在檢查範圍內 |
| gate-level ISA regression | `dv/gl_core/run_gl_core.py` | 所用的 harden run 必須是 signoff PASS 的那一次，且 CPU 參數與目前的 `config.json` 相同；上游 firmware 在 RTL 與最終網表上都印出 `ALL TESTS PASSED`，45 支指令測試全部 OK；兩邊的 bus transaction trace（每筆存取的 cycle、位址、資料、byte mask）完全相同 |

每個 checker 都做過 negative test（植入錯誤，確認會 FAIL），記錄在 `docs/phase_exit/phase2.md`。

## 名詞

- **corner**：STA 用的製程條件組合。名稱如 `max_ss_100C_1v60`，前半 `nom`／`min`／`max` 是繞線寄生 RC 取標準、最小、最大值，後半是電晶體條件（`tt` 標準、`ss` 慢、`ff` 快）加溫度與電壓。setup 通常最差在 `max_ss`，hold 最差在 `ff`。
- **slew**：訊號從 0 爬到 1（或反過來）花的時間。太慢會讓下一級的延遲變大，轉換期間的短路電流（動態功耗）也變多。sky130 flow 的上限是 0.75 ns（PDK 設定 `MAX_TRANSITION_CONSTRAINT`）。
- **max cap／max fanout**：一個輸出 pin 帶的負載電容上限（0.2 pF）與帶的 pin 數上限（10），同樣來自 PDK flow 設定。
- **CTS（clock tree synthesis）**：把一條 clock 分配到 2382 顆 flip-flop 的 buffer 樹。OpenROAD 用 H-tree：把晶片一直對半切，每一層在分叉點決定要不要放 buffer。
- **hold buffer**：資料路徑太快、在 clock 到之後馬上變化會違反 hold 時，插入延遲 cell 拖慢它。

## 設定與理由

`config.json` 每個設定旁邊都有 `"//KEY"` 說明，這裡是完整理由。數字來自下一節的試跑。

| 設定 | 值 | 為什麼 |
|---|---|---|
| `SYNTH_PARAMETERS` | 13 個，與 `u_cpu` 相同 | Phase 2 量的是 SoC 裡真正那顆 CPU。`PROGADDR_RESET` 是 `32'h00010000`（Boot ROM），所以 GL regression 要在記憶體位址 0x10000 放一條跳回 0 的指令（`dv/gl_core/gl_core_boot.v`） |
| `CLOCK_PERIOD` | 40 ns | ADR-0004 的 silicon 目標 |
| `SETUP_VIOLATION_CORNERS`、`HOLD_VIOLATION_CORNERS` | `["*"]` | LibreLane 對 sky130 的預設只在 `tt` corner 判 setup FAIL（LibreLane 3.0.14 `librelane/config/pdk_compat.py` 第 320 行 `TIMING_VIOLATION_CORNERS = ["*tt*"]`，`librelane/steps/checker.py` 第 500 行起以它當 setup corner 的預設）；exit criteria 要求 9 個 corner 都乾淨 |
| `EXTRA_EXCLUDED_CELLS` | `clkdlybuf4s25_1/_2`、`clkdlybuf4s50_1/_2` | PDK 的排除清單（`drc_exclude.cells`）只排除 `clkdlybuf4s15_1`、`clkdlybuf4s18_1`。沒有排除時，resizer 拿 `clkdlybuf4s25_1`（clock 延遲 cell，驅動力很弱）當一般 buffer 用在 port 與 fanout 緩衝上，slew 大量超標 |
| `CTS_SINK_CLUSTERING_SIZE` | 8 | CTS 預設每顆末端 clock buffer 帶 10 顆 flop，之後為了平衡負載再加 dummy load（假負載 cell），末端 fanout 變成 11–12，超過上限 10。設 8 之後末端最多 9 |
| `LAYERS_RC` | sky130 每層金屬的 R、C（tt／ff／ss 三組） | 沒設定時，繞線前的寄生估算從 tech LEF 推 C，約 0.08 fF/µm；繞線後 RCX 實際萃取平均 0.178 fF/µm，差一倍多，resizer 因此低估負載、修得不夠。數值取自 LibreLane 3.0.14 `librelane/config/pdk_compat.py` 第 262–296 行（LibreLane 寫好但註解掉的 sky130 表） |
| `RUN_POST_GRT_DESIGN_REPAIR` | true | 預設只在 global placement 後修一次 slew／cap，之後 CTS、約 2200 顆 hold buffer、繞線又加了負載。這個選項在 global routing 之後再修一次。LibreLane 標為 experimental（可能卡住或跑很久），這裡約 25 秒 |
| `GRT_DESIGN_REPAIR_MAX_SLEW_PCT` | 30 | 上面那次修復預留的 slew 餘裕，預設 10%。10% 時 detailed routing 之後還有 2 條 net 在 `max_ss` 超過 0.75 ns |
| `CTS_DISTANCE_BETWEEN_BUFFERS` | 50 µm | H-tree 只在長的層放 buffer。這顆 core 約 520 µm 見方，第 3–6 層的線段只有約 27–54 µm，CTS 不放 buffer，結果第 2 層的 4 顆 clock buffer 各自透過一大片沒有 buffer 的線，直接帶 16 顆下游 buffer（fanout 16 > 10，其中 2 顆的負載電容 0.206、0.203 pF > 0.2 pF）。設 50 µm 後 CTS 在那幾層也放 buffer，clock buffer 最大 fanout 變成 9；clock 路徑從 3–4 級 buffer 變 9–10 級，時序仍有很大餘裕 |

沒有改的重要預設值：`FP_CORE_UTIL` 50%（合成後面積 ÷ 50% 決定 core 大小）、hold 修復餘裕 0.1 ns（`PL_RESIZER_HOLD_SLACK_MARGIN`）、clock uncertainty 0.25 ns、IO delay 為週期的 20%（8 ns）、timing derate 5%。

## 試跑紀錄（2026-10-03）

每次只改一兩項，用 signoff checker 看結果。面積是 `design__instance__area__stdcell`（standard cell 面積，含 tap cell、不含最後填空隙的 fill cell），slack 與 slew／cap／fanout 違規數都是 9 個 corner 中最差那一個 corner 的值。

| # | 相對前一次的變更 | 面積 µm² | setup WS ns | hold WS ns | slew 違規 | cap 違規 | fanout 違規 | 結果 |
|---|---|---|---|---|---|---|---|---|
| 1 | 只設參數、40 ns、9 corner 判定 | 189133 | 3.29 | 0.110 | 5544 | 71 | 83 | DRV（slew／cap／fanout）大量超標 |
| 2 | 用命令列 `-c` 加排除 cell 與 clustering 8 | — | — | — | — | — | — | list 參數經 nix-shell 引號處理後變形，CutRows 的 Tcl 報錯；改寫進 `config.json` |
| 3 | 同 #2，寫進 `config.json` | 184607 | 4.66 | 0.109 | 5519 | 115 | 8 | fanout 大幅下降；slew 仍多。gate-level ISA regression 在這個網表上 PASS |
| 4 | 再排除 `buf_1`、`clkbuf_1` | 191217 | **−3.54** | 0.107 | 5274 | 68 | 12 | resizer 改用延遲 cell `dlygate4sd3_1` 當 buffer，`ss` corner setup 違規 30 條；退回 |
| 5 | #3 + `LAYERS_RC` | 191706 | 5.81 | 0.104 | 1653 | 2 | 5 | slew 違規降到 1/3 |
| 6 | + `RUN_POST_GRT_DESIGN_REPAIR` | 193656 | 5.87 | 0.058 | 15 | 2 | 4 | 剩 2 條資料 net 的 slew 與 clock tree 第 2 層 |
| 7 | + `GRT_DESIGN_REPAIR_MAX_SLEW_PCT 30`、`CTS_MAX_CAP 0.15` | 195704 | 6.16 | 0.027 | 0 | 2 | 4 | slew 清零；`CTS_MAX_CAP` 沒有作用（CTS 後的 DEF 與 #6 逐 byte 相同），定案時拿掉 |
| 8 | + `CTS_SINK_CLUSTERING_SIZE 9` | — | — | — | — | — | — | CTS 分成 319 群（比 8 還多），第 2 層仍帶 16；CTS 後就停掉 |
| 9 | #7 + `CTS_DISTANCE_BETWEEN_BUFFERS 50` | 196970 | 6.18 | 0.039 | 0 | 0 | 0 | signoff 全 PASS |

定案設定 = #9 拿掉 `CTS_MAX_CAP`；正式結果見 `signoff/golden/picorv32_core/`。

## 已知限制

1. **hold buffer 的面積成本**：hold 修復前，真正 slack < 0 的路徑很少（WNS −0.059 ns，插約 46 顆 buffer 後 TNS 就是 0）。但 resizer 要把 2100 個 endpoint 都推到 0.1 ns 的修復餘裕（`PL_RESIZER_HOLD_SLACK_MARGIN`），最後插了 2230 顆 `dlygate4sd3_1`（每顆 3.68 × 2.72 µm），約占 standard cell 面積的 11%（`37-openroad-resizertimingpostcts` 的 log）。Phase 3 若面積吃緊，主要可調的是這個 0.1 ns 餘裕；clock uncertainty 0.25 ns 對 buffer 數的影響沒有量過。
2. **CTS 的 dummy load 不能關**：OpenROAD 有 `-dont_use_dummy_load`，但 LibreLane 3.0.14 沒有對應變數；目前用 clustering 8 讓末端 fanout 留在 10 以內。
3. **489 個 lint warning**：446 個是 `TIMESCALEMOD`，來自 LibreLane 為 standard cell 產生的 blackbox 檔沒有 `` `timescale ``，而 `picorv32.v` 有；其餘 43 個在上游 `picorv32.v`（`BLKSEQ` 21、`UNUSEDSIGNAL` 15、`GENUNNAMED` 7）。不改 submodule，只當資訊記錄；lint error 為 0。
4. **`RUN_POST_GRT_DESIGN_REPAIR` 是 experimental**：LibreLane 文件說可能卡住或跑很久；這裡穩定約 25 秒。這一步修了 881 個 slew 違規（插 506 顆 buffer），之後的增量 global routing 印出 `EST-0026 Missing route to pin` 警告，印到 OpenROAD 的上限 1000 次就停止（印出的部分涉及 113 條 net），實際數量不明。最終的 detailed routing、LVS 和 STA（用繞線後萃取的寄生值）都 PASS，所以判斷沒有影響結果，但升級 LibreLane 時要重看。
