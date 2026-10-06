# signoff criteria knowledge database（依製程分類）

使用者 2026-10-07 的要求：`signoff-criteria` 依製程分類累積知識，每次 harden 檢查後學習。

- `../SKILL.md` 只放和製程無關的方法：怎麼推導 criteria、怎麼檢查、OpenSTA／OpenROAD／LibreLane 的行為。
- 這個目錄一個製程一個檔案，檔名是 `<PDK>_<標準元件庫>.md`。

| 製程 | 檔案 | 用過的設計 |
|---|---|---|
| SkyWater 130 nm（sky130A、sky130_fd_sc_hd） | [sky130A_sky130_fd_sc_hd.md](sky130A_sky130_fd_sc_hd.md) | arvinsa-rtl-gds soc_top（PicoRV32、Hazard3） |

## 每個製程檔案的章節

1. **適用**：PDK 版本、標準元件庫、工具版本。
2. **已驗證的製程事實**：PDK、.lib、DRC deck 的事實與預設值，每條有出處。
3. **溫度反轉**等該製程特有的 corner 行為。
4. **實測校準資料**：每次 harden 檢查（`../SKILL.md`「每次 harden 後的檢查」）的「學習」一節追加一列。每列寫量什麼、數值、校準哪一條 criterion、出處。
5. **待確認**：推測的根因，不能當規則用。

## 規則

- 新的製程開新檔案，先把 PDK 預設值與 corner 清單填好，再開始 harden。
- 校準資料只累積實測值。同一個量在兩顆以上設計或兩次以上 run 都成立，或用實驗確認過，才可以寫成「已驗證的製程事實」（CLAUDE.md 規則 3）。
- 只屬於某一顆設計的數字放該設計 repo 的文件（CLAUDE.md 規則 4），這裡只放下一顆同製程設計用得到的。
