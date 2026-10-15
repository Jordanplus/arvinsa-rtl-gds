---
name: package-flow
description: Package（晶片層級整合、外殼與下線）的入口，先讀這份再找細部 skill。用在開新的頂層或外殼設計、決定用哪幾支 pad／GPIO、搬動 macro 或 block（pad、block、pin 要先規劃並經使用者核准，`CLAUDE.md` 規則 14；hook 擋下「這份 pad／block／pin 規劃還沒經使用者核准」、`plan_sha256 differs`）、放進 ChipFoundry Caravel 的 user_project_wrapper（`FP_DEF_TEMPLATE`、`PDN-0239`、`GRT-0036`、`li1.pd.1d`、vccd1 只有一顆 pad、fill 與密度下限、邊界 SDC、平台試算表），以及跑與判定 ChipFoundry precheck（`cf-precheck`、`MR_mcon.CON.10`、`MR_licon.SP.6`、`stat=-9` OOM、`the results directory checked this GDS`、lima VM）。本文是情況與錯誤訊息對照到細部 skill 檔案的表。RTL、SDC、macro 準備看 middle-end-flow，PnR 與實體 signoff 看 backend-flow。Use as the entry point for chip-level work (pad/block/pin planning and approval, Caravel wrapper integration, ChipFoundry precheck).
---

# Package 入口

**這份 skill 只做導覽。** 依下表找到情況，用 Read 讀對應的 `SKILL.md`，照裡面的規則與已知陷阱做。細部 skill 在 skill 清單裡只列名稱（專案 `.claude/settings.json` 的 `skillOverrides`，ADR-0021 決定 6），所以要從這裡進去。

範圍：晶片層級與下線：
- pad（含電源進入點）、block 位置、pin 的規劃與核准；
- 放進外殼（本 repo 是 ChipFoundry Caravel）；
- 下線平台的收件檢查（precheck）。

對應流程文件 `arvinsa-rtl-gds-flow.md` 4.1 的平台試算表與 pad／block／pin 規劃、4.6 的外殼相關檢查（li1、fill）、4.7 的下線預檢。

**順序**：pad（含電源 pad 與電源進入點）→ block 位置 → pin 指定 → RTL → harden（`CLAUDE.md` 規則 14）。

## 情況 → 細部 skill

| 情況、錯誤訊息 | 細部 skill |
|---|---|
| 開新的頂層或外殼設計、選 pad／GPIO、搬動 macro 或 block、改 `FP_DEF_TEMPLATE`／`MACROS` 位置；hook `require_pin_plan.py` 或 `make pin-plan` 擋下（`no approval`、`plan_sha256 differs`、`no pnr/<design>/pin_plan.toml`、ADR `has no line with the quote`）；floorplan 圖 | `.claude/skills/chip-floorplan-pin-planning/SKILL.md` |
| 放進 Caravel user_project_wrapper：`PDN-0239 Ring shape falls outside the die bounds`、`GRT-0036 Pin ... is outside die area`、`li1.pd.1d`（`decap_3` 填滿）、`gpio_defines` 全是 `GPIO_MODE_INVALID`、GPIO 位置、`wb_clk_i`、vccd1／vssd1 只有一顆右側 pad、fill 與 `check_density.py` 下限、邊界 SDC 試算、平台試算表 | `.claude/skills/caravel-user-project-integration/SKILL.md` |
| 跑與判定 ChipFoundry precheck：`MR_mcon.CON.10`、`MR_licon.SP.6`、`klayout_beol failed (stat=-9)`、`extraction did not complete successfully`、`OEB FAILED (stat=5)`、`possible errors SOFT ... CVC`、`the results directory checked this GDS`、flow DRC 0 而 precheck FAIL、Apple Silicon 用 lima VM、`EXTRACT_ABSTRACT` | `.claude/skills/tapeout-precheck-caravel/SKILL.md` |

## 跨段共用（照舊列在清單上）

- 新寫或修改 checker、golden 與誤差、植入錯誤：`signoff-checker-qualification`。
- 一鍵 regression（`make regress-caravel` 含 precheck）、機器資源與逾時：`flow-regression-reproducibility`。
- Phase 收尾：`phase-exit-review`。

## 交界

- die 內的擺放細節、壅塞、PDN／IR、DRC／LVS：`backend-flow`。
- 外殼頂層的 latch-up 標記（81/14）：`backend-flow` → `drc-signoff` 規則 7（ADR-0021 決定 2：記錄並問平台）。

## 維護

- 新增或改名 Package 的 skill 時，同一個 commit 更新這張表、`.claude/settings.json` 的 `skillOverrides`（新 skill 設 `name-only`）、README 的 skill 一節。
- `make skill-check` 會檢查三件事：每個細部 skill 剛好在一個入口的表裡而且設成 `name-only`、入口表列的檔案存在、description 的長度上限。
