---
name: backend-flow
description: Backend（LibreLane harden、PnR 與實體 signoff）的入口，先讀這份再找細部 skill。用在 floorplan 與壅塞（`PDN-0179`、`GPL-0052`、繞路）、macro 接進設計（`MACROS`、`DRT-0418`）、PDN 與 IR（`PSM-0069`、`PSM-0075`、max power pattern、EM 沒檢查）、CTS（`delaybuf_*`、skew）、setup／hold 與 slew／cap 收斂（`Setup violations found`、`RSZ-0064`、`repair_design` 停不下來）、多 corner STA（`STA_CORNERS`、`RSZ_CORNERS`）、antenna（`GRT-0243`）、DRC／XOR／streamout（`nwell.4`、multiple top cells、latch-up 81/14）、LVS 與 disconnected pin、gate-level 模擬（`Unable to bind`、`wall-clock timeout`）、每次 harden 後的 criteria review（Stop hook 擋下回報）、signoff 上限怎麼定，以及跑 LibreLane 與除錯（`--from`、`GRT-0229`、`RSZ-0074`、某一步停不下來）。這份 skill 是情況與錯誤訊息對照到細部 skill 檔案的表。RTL、SDC、macro 準備看 middle-end-flow，晶片層級與下線看 package-flow。Use as the entry point for backend work (LibreLane harden, PnR, timing closure, IR, DRC/LVS/antenna signoff, gate-level simulation, run debugging).
---

# Backend 入口

**這份 skill 只是索引。** 依下表找到情況，用 Read 讀對應的 `SKILL.md`，照裡面的規則與已知陷阱做。細部 skill 在 skill 清單裡只列名稱（專案 `.claude/settings.json` 的 `skillOverrides`，ADR-0021 決定 6），所以要從這裡進去。

範圍：用 LibreLane 把 netlist 做成 GDS，以及每次 harden 之後的實體與時序 signoff：
- floorplan → PDN → placement → CTS → routing → fill；
- STA、IR、DRC、LVS、antenna；
- gate-level 模擬。

對應流程文件 `arvinsa-rtl-gds-flow.md` 4.4（floorplan 試跑）、4.5 的 signoff 條件、4.6（harden 與 signoff）、4.7 的 netlist 模擬。

**每次 harden 跑完（PASS 或 FAIL），回報前一定先讀 `signoff-criteria`**：`CLAUDE.md` 規則 9，Stop hook 強制。

## 情況 → 細部 skill

| 情況、錯誤訊息 | 細部 skill |
|---|---|
| die／core 尺寸、使用率、placement 密度（`PL_TARGET_DENSITY_PCT`、`GPL-0052`）、繞線壅塞或大幅繞路、macro 旁的窄 row（`PDN-0179 Unable to repair all channels`）、GCell overflow、floorplan 試跑 | `.claude/skills/floorplan-congestion/SKILL.md` |
| 把 macro 接進設計：`MACROS` 與 view 來源、每個 corner 只能一份 macro `.lib`、沒用到的 port 怎麼 tie-off、電源連接、macro 在每個 corner 能不能動、macro clock（`delaybuf_*`）、`DRT-0418 ... has no pins on routing grid` | `.claude/skills/hard-macro-integration/SKILL.md` |
| PDN 產生失敗、IR drop（`PSM-0069`、`PSM-0075 Expected four values on line`、PSM Signal 11、結果小得或大得不合理）、IR 的檢查方式（slow corner、CPU max power pattern、電壓源從晶片的 pad 起算）、`ir_worst.py`／`make ir-soc`／`make ir-caravel`、strap what-if、decap、EM（目前沒有檢查） | `.claude/skills/pdn-ir-drop/SKILL.md` |
| CTS：clock buffer 的 fanout／cap、skew metric、clock 輸入長線、CTS 把 macro clock 對齊（`delaybuf_*`、`-no_insertion_delay`）、hold delay cell 吃掉 setup、`CTS_MAX_CAP`、`RT_CLOCK_MIN_LAYER` 沒生效 | `.claude/skills/cts-clock-tree/SKILL.md` |
| setup／hold 違規（`Setup violations found in the following corners`）、max slew／cap／fanout、`*_VIOLATION_CORNERS`、resizer 與 drive 太弱的 cell（`a2111oi_1`、`repair_design` 停不下來）、`LAYERS_RC`、`RSZ_CORNERS`、`RUN_POST_GRT_RESIZER_TIMING`、hold 修復 log（`RSZ-0064`、`RSZ-0060`、`RSZ-0032`） | `.claude/skills/drv-timing-closure/SKILL.md` |
| 增減 STA corner、`LIB`／`STA_CORNERS`／`PNR_CORNERS`、per-corner hook、時序 what-if、推最小週期、`STA-0562`、`STAMidPNR` 只看預設 corner、flow 中途 state 裡其他 corner 的 metrics 是舊值、corner 增加後 PnR 時間暴增 | `.claude/skills/multicorner-sta/SKILL.md` |
| antenna 違規與修補、diode 副作用、`GRT-0243`、`DRT_ANTENNA_REPAIR_MARGIN` 沒作用、macro LEF 沒有 `ANTENNAGATEAREA` | `.claude/skills/antenna-signoff/SKILL.md` |
| Magic／KLayout DRC、XOR、GDS streamout：`nwell.4`（abstract DRC）、macro 內部的 DRC 違規算不算數、`multiple top cells`、改名 macro 後 `nwell.6`／`psdm.1`、latch-up 81/14 與 6 µm 規則、`floating_metal` 傳不進 deck、密度 | `.claude/skills/drc-signoff/SKILL.md` |
| LVS、電源與訊號 pin 的實體連接、disconnected pin（`Found 0 disconnected pin(s)`、wrapper 頂層幾百個 disconnected pin）、macro 在 LVS 是 black box | `.claude/skills/lvs-signoff/SKILL.md` |
| gate-level 模擬：`Unable to bind wire/reg/memory`、`dangling input port ... floating`、`wall-clock timeout`、`firmware image ... not found`、RTL 與 netlist lockstep、PG netlist、dump max power pattern 的 VCD | `.claude/skills/gate-level-simulation/SKILL.md` |
| 每次 harden 後的 criteria review（`review_criteria.py`、Stop hook）、signoff 上限與 margin 怎麼定（uncertainty、derate、corner 與 temperature inversion、IR drop 預算、EM、SI、density、latch-up）、`The checker will be skipped`、knowledge 檔 | `.claude/skills/signoff-criteria/SKILL.md` |
| 跑 LibreLane、run 失敗、`--from`／`--with-initial-state`、單獨重跑某個 step、某一步卡住或停不下來（最後只報 `failed with an unexpected error`）、`GRT-0229`、`GRT-0116`、`RSZ-0074`、plugin 不在 `PYTHONPATH`、工具升版要重看的綁定 | `.claude/skills/librelane-run-debug/SKILL.md` |

## 跨段共用（照舊列在清單上）

- 新寫或修改 checker、golden 與誤差、植入錯誤：`signoff-checker-qualification`。
- 一鍵 regression、乾淨 checkout、來源追溯、機器資源與逾時：`flow-regression-reproducibility`。
- Phase 收尾：`phase-exit-review`。

## 與其他段的分工

- SDC 怎麼寫、macro 的 view QA 與 characterization、EQY：`middle-end-flow`。
- pad、block、pin 的規劃與核准（`CLAUDE.md` 規則 14）、放進 wrapper、precheck：`package-flow`。

## 維護

- 新增或改名 Backend 的 skill 時，同一個 commit 更新這張表、`.claude/settings.json` 的 `skillOverrides`（新 skill 設 `name-only`）、README 的 skill 一節。
- `make skill-check` 會檢查三件事：每個細部 skill 剛好在一個入口的表裡而且設成 `name-only`、入口表列的檔案存在、description 的長度上限。
