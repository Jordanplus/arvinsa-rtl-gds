---
name: tapeout-precheck-caravel
description: 把設計放進 ChipFoundry Caravel 的 user_project_wrapper（2920 × 3520 µm，固定 DEF 範本 `FP_DEF_TEMPLATE`），或要跑 ChipFoundry 收件前的自動檢查（precheck、`cf precheck`、`cf-precheck`、`mpw_precheck`）時使用：precheck 一定用 Docker 跑只有 linux/amd64 的官方 image（Apple Silicon 要用 colima＋Rosetta 模擬），容器每次都 `pip install --upgrade cf-precheck`；precheck 自帶的 KLayout deck 比 flow 用的新，flow 的 KLayout DRC 是 0 不代表 precheck 的 `klayout_feol`／`klayout_beol` 會過；OpenRAM bitcell（包括 PDK 預建的 `sky130_sram_*`）在新 deck 報 `MR_mcon.CON.10`（mcon should covered by li）與 `MR_licon.SP.6`，因為 2026-05 拿掉了 `areaid.ce` 的豁免；LVS 是 transistor-level，SRAM 要用 `EXTRACT_ABSTRACT` 當 black box；`gpio_defines` 範本全是 `GPIO_MODE_INVALID`、`oeb` 檢查實體接線；XOR 要求 die 外那圈與官方空 wrapper 相同；`lvs_config.json` 路徑要以 `$PDK_ROOT`／`$UPRJ_ROOT` 開頭。Use for ChipFoundry Caravel user_project_wrapper integration and cf-precheck (docker amd64 image, KLayout deck newer than the flow's, OpenRAM bitcell MR_mcon.CON.10, LVS black box, GPIO/OEB checks).
---

# Caravel 整合與 ChipFoundry precheck

macro 本身的整合（view QA、LEF、`FOREIGN`）看 `hard-macro-integration`；DRC 的一般判讀看 `drc-signoff`；LVS 的一般做法看 `lvs-signoff`；floorplan 看 `floorplan-congestion`。本 repo 實例：ADR-0019、`docs/notes/caravel_precheck_phase7.md`（Phase 7 進行中）。

名詞：
- **Caravel**：ChipFoundry（2025 年接手 Efabless 的 sky130 共乘下線）的載具晶片。pad、電源與一顆管理用的 RISC-V 都做好了，使用者的設計放在 `user_project_wrapper` 裡。
- **precheck**：ChipFoundry 收件前的自動檢查。現在是 pip 套件 `cf-precheck`，由 `cf` 指令（pip 套件 `chipfoundry-cli`）用 Docker 呼叫。
- **扁平放法**：CPU 的 standard cell 與 SRAM macro 直接放在 wrapper 層繞線，不先把 SoC harden 成 macro（`project-plan.md` §5.5）。官方範例都是先 harden 成 macro。

## 規則（已驗證）

1. **precheck 的判定只認官方 image 的結果，並記下實際版本**。
   - `cf precheck` 沒有 Docker 就停止；image 是 `chipfoundry/mpw_precheck:latest`，只有 linux/amd64（cf-cli `main.py` 第 4887、4893、4916 行；Docker Hub 2026-10-12）。Apple Silicon 要用模擬（colima `--vm-type vz --vz-rosetta`）。
   - 容器每次先 `pip install --upgrade cf-precheck`，同一個 image 不同天跑，版本可能不同。每次記下 image digest 與 cf-precheck 版本。
   - image 的工具版本（Magic 8.3.471、KLayout 0.29.12、Netgen 1.5.272、PDK open_pdks `3e0e31dc`）和 flow 的不同；本機用 flow 的工具跑出來的結果只能加快修 bug，不能當判定。
2. **flow 的 KLayout DRC 是 0，不代表 precheck 的 KLayout DRC 會過**：precheck 用自帶的 `drc_scripts/sky130A_mr.drc`（2026-10 時是 release `2026.03.30_01.00`），flow 用 PDK 的 deck（`8afc834` 是 `2024.2.11_01.09`），規則名稱與內容都不同。每一顆 macro 交給 wrapper 之前，先用 precheck 的 deck 單獨跑 `feol`／`beol`／`offgrid`（參數照 `checks/klayout_drc.py`：`input`、`topcell`＝GDS 檔名、`report`、`thr`），幾十秒就有結果。
   - 先讀過 deck 再執行：它是第三方的 Ruby 腳本。
3. **OpenRAM bitcell 在新 deck 的兩條規則**（工具缺陷的防護，CLAUDE.md 規則 10）：
   - **症狀**：`klayout_beol` 報 `MR_mcon.CON.10 : mcon should covered by li`、`klayout_feol` 報 `MR_licon.SP.6 : poly_licon minimum space to psdm`，位置在 `sky130_fd_bd_sram__openram_dp_cell*` 與 `*_replica_column*`。PDK 預建的 `sky130_sram_2kbyte_1rw1r_32x512_8` 與 OpenRAM 自產的 macro 一樣，BEOL 264、FEOL 3（依 cell 計）。
   - **怎麼發現**：precheck 的 `outputs/reports/klayout_{feol,beol}_check.xml` 的 `<category>` 與 `<cell>`；或規則 2 的 macro 單獨檢查。
   - **原因**：cf-precheck commit `08f559e30a`（2026-05-07）把 `mconnotace.not(li)`（不檢查 SRAM 核心區 `areaid.ce`，81/2）改成 `mcon.not(li)`；`MR_licon.SP.6` 是新規則。`$sram_exclude` 只管 nsdm／psdm，而且只認 `sky130_sram_*` 名稱，關不掉這兩條。
   - **怎麼繞過**：沒有能讓官方結果 PASS 的設定。本 repo 的判定（ADR-0019 決定 5）：這兩項只允許這兩條規則，每一個違規都在 SRAM 外框內，而且 PDK 預建 macro 單獨檢查時同一個 cell、同一個相對位置也有；並向 ChipFoundry 反映。
   - **防復發**：比對 checker 與 negative test 在 Phase 7 實作時加（還沒有自動防護）。deck 升版時重跑規則 2 的兩顆對照。
4. **SRAM 的 LVS 用 black box**：precheck 的 LVS 是 Magic 萃取到電晶體層級加 Netgen。ChipFoundry 的 PDK `3e0e31dc` 對 bitcell 的元件命名和 `8afc834` 相同（`special_pfet_latch`、`special_nfet_01v8`），OpenRAM 的網表（2022 PDK 的命名）對不上。在 `lvs/user_project_wrapper/lvs_config.json` 的 `EXTRACT_ABSTRACT` 加入 SRAM 的 cell 名稱，ChipFoundry 自己的 `caravel_user_sram` 範例也這樣做。代價：SRAM 內部不檢查，要靠 view QA 與 `check_macro_gds.py`。

## 待確認（讀過原始碼，還沒實跑）

- `xor`：die（0–2920 × 0–3520 µm）外那一圈要和 caravel-lite 的空 wrapper 一樣，所以要用 `FP_DEF_TEMPLATE`（`openlane/user_project_wrapper/fixed_dont_change/user_project_wrapper.def`），core ring（寬 3.1 µm、offset 12.45 µm）不能改。
- `gpio_defines`：`verilog/rtl/user_defines.v` 的 GPIO 5–37 都要有值、不能是 `GPIO_MODE_INVALID`；範本全是 INVALID。
- `oeb`：CVC 在萃取網表上追 `io_out`／`io_oeb` 的實際接線，和 GPIO 模式比；user output 模式要真的接 `io_out` 與 `io_oeb`。RTL 對了不代表 PASS。
- `lvs_config.json` 裡的路徑必須以 `$PDK_ROOT` 或 `$UPRJ_ROOT` 開頭（cf-precheck `config.py` 第 206–219 行）。
- `klayout_met_min_ca_density` 只有上限（li1–met4 ≤ 60%、met5 ≤ 76%）；SRAM 內部與電源區要量。
- `magic_drc` 是選用，預設不跑；只有 PDK 的 `sky130_sram_*` 會換成 maglef，自產 SRAM 用完整規則會 FAIL。下線時 ChipFoundry 怎麼看要另外問。
- 官方範例的 flow 是 LibreLane 2.4.6（ChipFoundry fork `CI2511`）；LibreLane 3.0.14 支援 `FP_DEF_TEMPLATE`，舊的 `FP_PDN_*` 名稱會自動轉換。

## 用完後

1. 新的現象加進「經驗紀錄」，根因標明已驗證／推測。
2. 「待確認」的項目實跑確認後搬進規則；同一現象出現兩次或用實驗確認才寫成規則（CLAUDE.md 規則 3）。
3. precheck 或 deck 升版時，逐條重看規則 3 的防護是否還成立（CLAUDE.md 規則 10）。

## 經驗紀錄

| 日期 | 專案／run | 現象 | 根因（已驗證／推測） | 處理 | 證據 |
|---|---|---|---|---|---|
| 2026-10-12 | arvinsa-rtl-gds Phase 7 開始（查證） | precheck 的 deck 檢查 SRAM：自產 macro 與 PDK 預建 macro 都是 FEOL 3（`MR_licon.SP.6`）、BEOL 264（`MR_mcon.CON.10`）、offgrid 0；flow 的舊 deck 兩顆都是 0 | 已驗證：比對兩份 deck 與 cf-precheck commit `08f559e30a` 的 diff | ADR-0019 決定 5：這兩條比對預建 macro；向 ChipFoundry 反映的草稿由使用者決定是否送出 | `docs/notes/caravel_precheck_phase7.md` 第 7 節 |
