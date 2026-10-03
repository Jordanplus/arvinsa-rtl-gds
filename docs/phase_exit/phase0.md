# Phase 0 exit review：環境

日期：2026-10-03　結論：**PASS**（三項 exit criteria 全部達成）

Exit criteria 出處：`project-plan.md` §8 Phase 0。

| Exit criterion | 結果 | 證據 |
|---|---|---|
| smoke test PASS | PASS | `make flow-setup`：`librelane --smoke-test` → `Smoke test passed.`（`runs/flow_setup/smoke_test.log`） |
| `test_sram_macro` 以 25 ns 全 PASS | PASS | `make ci-sram-ref`：16 個 signoff 項目為 0、9 個 corner setup／hold slack 全為正、307 個 metrics 與本機 golden 完全相同；與官方 CI 的 slack 差距 ≤ 0.01 ns（`signoff/golden/ci_sram_ref/README.md`） |
| 版本與 hash 全部記錄 | PASS | `env/versions.mk`（釘版唯一來源）、`toolchain.md` §2／§3（LibreLane 內建工具實際版本、PDK）、`env/sky130_pdk_assets.sha256`；`make env-check` 比對 `toolchain.md` 與本機實際版本 |

計畫中 Phase 0 的其他工作項目：

| 項目 | 狀態 |
|---|---|
| 安裝 Nix + FOSSi binary cache | 完成。改用 NixOS/nix-installer 2.35.2 的固定版本執行檔（計畫寫 Determinate installer）：官方啟動 script 在本機網速下會因低於 250 KB/s 中止，見 `env/setup.md` §2 |
| LibreLane clone + nix-shell + smoke test | 完成（3.0.14，commit `f24e0ea5`） |
| ciel 下載 sky130A | 完成，但改由 `make pdk-fetch` 下載（平行、可續傳、sha256 驗證）再交給 ciel 安裝，原因見 `env/setup.md` §3 |
| 確認 PDK 內 SRAM LEF 含 `FOREIGN` | 完成，並納入 `make env-check`；另確認 PDK 內的 SRAM Verilog 模型與 `ip/sram/` 釘版副本 sha256 相同 |
| 記錄 PDK hash | 完成：`8afc8346a57fe1ab7934ba5a6056ea8b43078e71`（LibreLane 3.0.14 的 `pdk_hashes.yaml`）；`make env-check` 檢查 `~/.ciel/sky130A` 指向這一版 |
| 確認 toolchain 能編 picorv32 firmware | 完成：`make core-stock` 用 `riscv64-elf-gcc` 16.1 編上游 firmware，`test`／`test_ez`／`test_wb`／`test_synth` PASS（Phase 1） |
| repo 骨架與 `versions.mk` | 完成 |

## 過程中發現、已處理的問題

1. **網路慢**：本機到 GitHub 單一連線 45–175 KB/s。Nix 安裝程式與 PDK 都改成可續傳、驗 sha256 的下載方式。
2. **`make clean` 刪掉 flow 產出**：Phase 1 的 fix agent 執行 `make clean` 時刪除整個 `runs/`，連帶刪掉進行中的 `runs/flow_setup/`。已把 `make clean` 限縮為 Phase 1 的模擬與 firmware 產出。
3. **CI 參考設計的版本**：原本釘的 librelane-ci-designs commit 不是 LibreLane 3.0.14 自己測試用的那一版，已改為 3.0.14 的 `test/designs` submodule commit `9b3bebe8`（`test_sram_macro` 內容相同）。
4. **跨平台差異**：本機 max slew violation 74，官方 CI 70。查證為擺放／繞線的平台差異（本機連跑三次結果完全相同），checker 改為「signoff 項目跨平台比對＋全部 metrics 與本機 golden 完全比對」，過程記錄在 `signoff/golden/ci_sram_ref/README.md`。

## 留給後續階段

- flow 內建的 Yosys 0.62、Verilator 5.044 比本機的 0.69、5.050 舊；正式流程（Phase 2 起）一律用 nix-shell 內的版本。
- `test_sram_macro` 的 Magic DRC 為 532（官方相同），來自 SRAM macro 本身；Phase 3 依 `project-plan.md` §6.3 處理（abstract DRC = 0、full-GDS DRC 只在 SRAM 內且不超過 baseline）。
