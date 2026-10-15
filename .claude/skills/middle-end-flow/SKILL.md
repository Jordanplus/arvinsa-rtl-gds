---
name: middle-end-flow
description: Middle-end（RTL 到網表、約束、macro 與 IP 準備、網表等價）的入口，先讀這份再找細部 skill。用在 Yosys 合成與 lint（`Recoding FSM`、`cpu-params` FAIL、latch）、RTL 模擬與 directed 測試補缺口、換 CPU core（PicoRV32 換 Hazard3、AHB5、`bus_assert`）、寫或改 SDC（`PNR_SDC_FILE`／`SIGNOFF_SDC_FILE`、`unconstrained endpoints`、`set_input_transition` 不生效）、EQY 等價證明（`Failed to prove equivalence of partition`、`conflicting matches for gold bit`、`returncode=-11`）、選定或收到 hard macro 的 view QA 與 go／no-go（`check_macro_views` FAIL、`ODB-0292`、`LEF has no FOREIGN`）、用 OpenRAM 產生 SRAM（`Netlists do not match`、`ERROR` 但 exit 0）、SRAM 的 SPICE 特性化與 .lib（ngspice、`no such vector`、低溫讀成前一次的值）、SRAM 版圖萃取（`singular matrix`、`Timestep too small`）。本文是情況與錯誤訊息對照到細部 skill 檔案的表。PnR 與實體 signoff 看 backend-flow，晶片層級與下線看 package-flow。Use as the entry point for middle-end work (synthesis, RTL verification, SDC, formal equivalence, macro qualification, OpenRAM generation, SRAM characterization).
---

# Middle-end 入口

**這份 skill 只做導覽。** 依下表找到情況，用 Read 讀對應的 `SKILL.md`，照裡面的規則與已知陷阱做。細部 skill 在 skill 清單裡只列名稱（專案 `.claude/settings.json` 的 `skillOverrides`，ADR-0021 決定 6），所以要從這裡進去。

範圍：RTL 寫好之後到交給 PnR 之前：
- 合成與 lint、RTL 驗證；
- 換 core；
- 時序約束；
- 網表等價；
- hard macro 的取得、產生、QA 與特性化。

對應流程文件 `arvinsa-rtl-gds-flow.md` 4.2（RTL 與 RTL 驗證）、4.3（macro）、4.5 的 SDC 部分、4.7 的等價證明。

## 情況 → 細部 skill

| 情況、錯誤訊息 | 細部 skill |
|---|---|
| Yosys 合成設定、lint 警告數變了、latch、`Recoding FSM ... one-hot`、暫存器被換成常數、`cpu-params` FAIL（`defparam`、`SYNTHESIS` define、config 的 `pdk::` 條件區塊）、為縮短週期調整合成 | `.claude/skills/rtl-synthesis-lint/SKILL.md` |
| regression 沒用到某個功能、植入錯誤沒被抓到而要補 directed firmware 測試 | `.claude/skills/dv-directed-tests/SKILL.md` |
| 換 CPU core（PicoRV32 → Hazard3、AHB5 接 1RW SRAM）、`core_haddr_d` 沒有 driver、`bus_assert` 報 `addr/wdata/wstrb changed`、`exc`／`irq` 或 cycle 下限 FAIL、rvcpp 逾時、新 core 的 PnR 要重新驗證 | `.claude/skills/core-migration-hazard3/SKILL.md` |
| 寫或改 SDC、PnR 與 signoff 的 SDC 分開（sta.log 讀到 `pnr.sdc`）、約束有沒有生效、`unconstrained endpoints`、`unclocked register/latch pin`、driving cell 讓 `set_input_transition` 失效、外殼的邊界約束 | `.claude/skills/timing-constraints-sdc/SKILL.md` |
| EQY：`returncode=-11`、`Failed to prove equivalence of partition`（amend 重試、空洞證明）、`conflicting matches for gold bit`（`RSZ-0043 Swapped pins`）、`found constant ... bit`、negative test `eqy FAILed, but not at the injection`、換了非 `sky130_` 開頭的 macro 後中止於 KeyError `'sram0'` | `.claude/skills/formal-equivalence-eqy/SKILL.md` |
| 選定、自建、收到或更換 hard macro：view QA（`check_macro_views` FAIL、`ODB-0292`、`LEF has no FOREIGN`、最終 GDS 的 macro 是空的）、選定前的 go／no-go、`.lib` 驅動能力、換 macro 檢查單（`CLAUDE.md` 規則 12） | `.claude/skills/macro-qualification/SKILL.md` |
| 用 OpenRAM 產生 SRAM：`Netlists do not match`、log 有 `ERROR` 但 exit 0、`make sky130-install` 少複製 cell 卻 exit 0、`Custom cell pin names do not match spice file`、GDS 每次不同、`flake.nix`、macro 內 `nwell.6`／`psdm.1`／`m2.2`、1RW 的 `even number of cols` | `.claude/skills/openram-macro-generation/SKILL.md` |
| SRAM 的 SPICE 特性化與 `.lib`：ngspice 停在 `INP2M`、`bad v() syntax`、`no such vector`、`FALL=1`、低溫或 ss 低電壓讀成前一次的值、`.lib` 負載斜率讓 `repair_design` 跑很久或 `failed with an unexpected error`、`doAnalyses` out of memory、完整網表平行跑時每步慢 10–40 倍、漏電與 gmin | `.claude/skills/openram-macro-characterization/SKILL.md` |
| SRAM 版圖萃取：Magic 沒有 `PDK_ROOT` 時沒輸出、`singular matrix`、`Timestep too small`（負值電容）、寄生倍數 | `.claude/skills/sram-layout-extraction/SKILL.md` |

## 跨段共用（照舊列在清單上）

- 新寫或修改 checker、golden 與誤差、植入錯誤：`signoff-checker-qualification`。
- 一鍵 regression、乾淨 checkout、來源追溯、機器資源與逾時：`flow-regression-reproducibility`。
- Phase 收尾：`phase-exit-review`。

## 交界

- 把 macro 接進 LibreLane（`MACROS`、per-corner `.lib`、tie-off、macro clock）是 Backend：`backend-flow` → `hard-macro-integration`。
- gate-level 模擬與 signoff 條件的推導在 Backend：`backend-flow`。

## 維護

- 新增或改名 Middle-end 的 skill 時，同一個 commit 更新這張表、`.claude/settings.json` 的 `skillOverrides`（新 skill 設 `name-only`）、README 的 skill 一節。
- `make skill-check` 會檢查三件事：每個細部 skill 剛好在一個入口的表裡而且設成 `name-only`、入口表列的檔案存在、description 的長度上限。
