# GRT-0229 隨機中止的重現紀錄（2026-10-03）

`OpenROAD.RepairDesignPostGRT` 偶爾報下面的錯誤而中止。這份紀錄保存重現實驗的證據；原始輸出在 session 暫存目錄，之後會消失。

```
[ERROR GRT-0229] Vertical edge usage exceeds the maximum allowed. (79, 0) usage=65534 limit=2200
Error: repair_design_postgrt.tcl, 52 GRT-0229
```

## 第一次發生

- 第一次 `make phase3`（乾淨 worktree `../arvinsa-rtl-gds-phase3`，commit 654c303），第 41 步。log：`runs/p3_phase3_clean.log`。
- 第 39 步（global routing）以前的 DEF 與網表，和 golden 來源 run（`runs/soc_top`）逐 byte 相同（06、28、35、37、39 步，`cmp`）。所以中止前的輸入與 golden 來源 run 相同。

## 重現實驗

拿第一次 `make phase3` 第 41 步的 `config.json` 與 `state_in.json`，用 LibreLane 單步重跑同一步 4 次（4 個 process 同時跑，間隔 2 秒）：

```
cd .tools/librelane && nix-shell --run "python3 -m librelane.steps run --id OpenROAD.RepairDesignPostGRT \
  -c <run>/41-openroad-repairdesignpostgrt/config.json -i <run>/41-openroad-repairdesignpostgrt/state_in.json -o <out>/rN"
```

| 次 | 結束碼 | 結果 |
|---|---|---|
| r1 | 0 | 通過；`Resized 1273 instances`、`Inserted 779 buffers in 1411 nets` |
| r2 | 255 | 同樣的 resize／buffer 數之後，第二次 global route 報 GRT-0229（step log 第 182 行） |
| r3 | 0 | 通過；輸出的 `soc_top.def` 與 r1 逐 byte 相同 |
| r4 | 255 | 同 r2 |

結論（已驗證）：同一份輸入，結果隨機；通過時的結果是確定的。

推測（未驗證）：(79, 0) 是 clk pin 所在的 GCell（pin 在 die 下緣，clk net 用 CTS 的 non-default rule）；65534 像是 16-bit 計數的特殊值。

## 第二個位置：`OpenROAD.ResizerTimingPostGRT`（2026-10-07）

ADR-0014 開了 `RUN_POST_GRT_RESIZER_TIMING`，這一步修完也會再做一次 `global_route`。ADR-0016（`adac1a9`）的正式 harden，PicoRV32 與 Hazard3 都在這一步中止，訊息與位置相同：

```
[ERROR GRT-0229] Vertical edge usage exceeds the maximum allowed. (79, 0) usage=65534 limit=2200
Error: rsz_timing_postgrt.tcl, 68 GRT-0229
```

用 PicoRV32 那個 run 第 44 步的 `config.json` 與 `state_in.json` 單步重跑 4 次（同時跑，間隔 2 秒，`--id OpenROAD.ResizerTimingPostGRT`）：r2 中止（結束碼 255），r1、r3、r4 通過，輸出的 `soc_top.def` 三次相同。用同一份 CTS 結果（DEF 相同）的接續實驗 D，兩個 CPU 都通過這一步。

結論（已驗證）：同一個隨機問題，出現在另一個做 `global_route` 的 step。`pnr/librelane_flow.sh` 的重試加上這一步，`make test-flow-retry` 加 3 種情境（這一步中止後通過、兩步各中止一次、這一步連續中止 3 次），並檢查每次接續的 `--from`。

## 處理

- `pnr/librelane_flow.sh`：只有最後一步是 `RepairDesignPostGRT`（Phase 5 起也包括 `ResizerTimingPostGRT`）、沒有 `state_out.json`、step log 有上面這行時，從該步接續；總共最多跑 3 次（最多重試 2 次），重試記在 `runs/<tag>_signoff/retries.txt`。
- `make test-flow-retry` 用假的 nix-shell 測情境（Phase 3 7 種，Phase 5 加到 10 種）。真正的重試路徑只在第一次 `make phase3` 手動接續過一次（接續後 320 個 metrics 與 golden 相同）；第二到第四次 `make phase3` 都沒有觸發。
- skill：`librelane-run-debug` 規則 5、`signoff-checker-qualification` 漏洞類型表。
