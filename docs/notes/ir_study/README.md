# IR drop 研究的腳本與原始結果（2026-10-04）

結論在 `docs/notes/ir_worst_case_soc_top.md`。由一個 agent 在 session 暫存目錄執行，這裡保存可以重現研究所需的部分（呼叫用的 shell 腳本含本機路徑，沒有放進來）。

| 檔案 | 內容 |
|---|---|
| `ir_custom.tcl` | LibreLane `librelane/scripts/openroad/irdrop.tcl` 加診斷輸出；環境變數 `IR_SOURCE_TYPE`、`IR_VSRC_DIR`、`IR_DEL_BTERMS`（只在記憶體裡刪掉電源 pin，讓 `-source_type` 生效）、`IR_EM`。用法：把 `OpenROAD.IRDropReport` step 的 script 換成這個檔，以 `python3 -m librelane.steps run --id OpenROAD.IRDropReport` 單步重跑 |
| `make_vsrc.py` | 產生 4 種供電模型的 `-vsrc` 檔（strap 位置取自 `final/def/soc_top.def`） |
| `parse.py`、`combined.py`、`em_summary.py` | 從每次 run 的 log、電壓 CSV、EM CSV 整理成 `results_raw.txt` |
| `results_raw.txt` | 每次 run 一行：corner、功耗、各 net 最差與平均壓降、供電點數、每平方電阻、供電來源 |
