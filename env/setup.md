# Phase 0 環境建置

狀態（2026-10-03）：**Phase 0 完成**。Nix、LibreLane 3.0.14、sky130A PDK 已安裝；`make env-check-flow` PASS；`librelane --smoke-test` PASS；`make ci-sram-ref`（LibreLane CI 的 SRAM 參考設計）PASS。
工具與版本總表見 `toolchain.md`，釘版值見 `env/versions.mk`。

## 1. 已就緒（不需 Nix）

| 項目 | 版本 |
|---|---|
| Verilator | 5.050 |
| Icarus Verilog | 13.0 |
| Yosys（只做本機 sanity check，正式流程用 LibreLane 內建版本） | 0.69 |
| riscv64-elf-gcc | 16.1，rv32 multilib 可用，無 newlib |
| Python | 3.14（需 ≥ 3.11，只用標準函式庫） |
| GNU make | 3.81（macOS 內建；Makefile 已相容） |

## 2. 使用者執行：`make nix-install`

安裝程式會建立 `/nix` APFS volume 與 build 使用者，**會要求輸入管理者密碼**，所以要在自己的終端機執行：

```bash
cd ~/claude_prjs/arvinsa-rtl-gds
make nix-install DRY_RUN=1   # 可選：只下載安裝程式並印出將執行的指令，不安裝
make nix-install             # 實際安裝，約 5 分鐘
```

`make nix-install`（`env/install_nix.sh`）做的事：

1. 已安裝 Nix 時直接結束；若 FOSSi binary cache 沒設定，會印出要加進 `/etc/nix/nix.conf` 的設定並 FAIL。
2. 從 GitHub releases 直接下載釘版的 `nix-installer-aarch64-darwin`（版本與 sha256 見 `env/versions.mk`），快取在 `.tools/nix-installer/<版本>/`。下載可續傳、會自動重試，沒有速度門檻；中斷時重跑 `make nix-install` 會從斷點接續。
3. 驗證 sha256，不符就 FAIL 並刪除壞檔。
4. 執行 `install --no-confirm`，同時寫入 FOSSi binary cache 與 flakes 設定。安裝程式會自己用 sudo 提權，並要求輸入密碼；Nix 本體已內含在安裝程式裡，安裝時不會再下載。
5. 安裝後檢查 `nix` 執行檔與 cache 設定都存在，才印 PASS。

為什麼不用官方的一行指令：官方啟動 script 下載主程式時，若 15 秒內平均低於 250 KB/s 就會中止。2026-10-03 實測本機到 GitHub releases 約 135 KB/s，因此第一次安裝失敗（`curl: (28) Operation too slow`）。

指令出處：[LibreLane macOS 安裝文件](https://librelane.readthedocs.io/en/latest/installation/nix_installation/installation_macos.html)。
**裝完後關掉所有終端機視窗再開新的。**

## 3. 安裝 Nix 之後：`make flow-setup`（使用者或 Claude 都可以執行）

```bash
make flow-setup              # 第一次：nix-shell 下載約 619 MiB 工具 + PDK 約 338 MB
make env-check-flow          # 嚴格檢查：Nix、LibreLane 版本、PDK 版本、SRAM macro
make ci-sram-ref             # Phase 0 golden：重跑 LibreLane CI 的 test_sram_macro，約 3 分鐘
```

`make flow-setup`（`env/setup_flow.sh`）做的事：

1. 把 LibreLane `3.0.14` clone 到 `.tools/librelane`（gitignore），並確認 commit 與 `env/versions.mk` 一致。
2. 執行 `make pdk-fetch`（`env/fetch_pdk.sh`）安裝 PDK：
   - 從 GitHub releases 平行下載 ciel 預設的 7 個壓縮檔（約 338 MB），可續傳，快取在 `.tools/pdk-cache/`。
   - 每個檔案以 `env/sky130_pdk_assets.sha256` 驗證；不符就刪除並 FAIL。
   - 在本機開一個只聽 127.0.0.1 的暫時 HTTP server 當 mirror，用 ciel 的 `--data-source` 選項從本機安裝到 `~/.ciel`（2.1 GB）。
   - 為什麼不讓 LibreLane 自己下載：ciel 只用一條連線、不能續傳。2026-10-03 實測單一連線 45–175 KB/s，平行下載約 360 KB/s，338 MB 約 23 分鐘。
3. 進入 LibreLane 的 nix-shell，執行 `librelane --smoke-test`；log 在 `runs/flow_setup/smoke_test.log`。
4. 把 nix-shell 內各工具版本寫到 `runs/flow_setup/versions.txt`（已抄進 `toolchain.md` §2）。

`make env-check` 在 PDK 存在時會另外檢查：PDK 是 `SKY130_PDK_HASH` 那一版、SRAM macro 的 LEF 有 `FOREIGN`、PDK 內的 SRAM Verilog 模型與 `ip/sram/` 的釘版副本 sha256 相同。

## 4. Phase 0 golden：`make ci-sram-ref`

重跑 LibreLane 3.0.14 官方 CI 用的 `test_sram_macro`，與官方 CI 結果和本機 golden 比對。規則、結果與本機和官方的差異見 `signoff/golden/ci_sram_ref/README.md`。

2026-10-03 結果：PASS。LVS、DRC（繞線／KLayout）、power grid、antenna 全為 0；9 個 corner setup／hold slack 全為正，且與官方差距在 0.01 ns 以內；連跑三次 307 個 metrics 完全相同。

## 注意事項

- 這台機器的終端機若在安裝 Nix 之前就開著，PATH 裡沒有 `nix`；開新的終端機即可。所有 script 也會自己找 `/nix/var/nix/profiles/default/bin`。
- nix-shell 啟動時印的 `file 'nixpkgs' was not found in the Nix search path … uses bash from your environment` 是 nix-shell 找不到 nixpkgs 時改用系統 bash 的提示，不影響結果。
- `make clean` 只刪 Phase 1 的模擬與 firmware 產出，不會刪 `runs/flow_setup`、`runs/ci_sram_ref`。
