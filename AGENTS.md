# AGENTS.md：給 Codex 與其他 coding agent

本 repo 的代理規則只有一份，在 [CLAUDE.md](CLAUDE.md)，對 Codex 一樣適用；這裡不另寫。

- 流程經驗（skill）：先看 [README.md](README.md)「Claude Code skills」一節的「依情況找 skill」表，再讀對應的 `.claude/skills/<name>/SKILL.md`。這些是一般的 Markdown，不需要 Claude Code 也能讀。
- 在其他專案沿用本 repo 的流程：README 同一節最後的「在其他專案使用」。
- 驗證：`make smoke`（數十秒）、`make regress`（完整，約 2–2.5 小時，需要 flow 環境，要在乾淨 checkout 執行）。
