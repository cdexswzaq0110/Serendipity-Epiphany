# AGENTS.md

本專案的指令入口是 [`CLAUDE.md`](CLAUDE.md)。**先讀它。**

這份 `AGENTS.md` 存在的唯一理由：讓非 Claude Code 的 agent（Codex、Gemini CLI、
opencode 等）也找得到入口。內容不在這裡重複——重複兩份就會漂掉。

## 給非 Claude Code agent 的三件事

這套配置的機制有一部分綁定 Claude Code（skill 自動載入、subagent 派發、
PreToolUse hook）。在其他 agent 上，那些會退化成「要你自己去讀」的文件。

**即使沒有自動載入，下面三條仍然成立，而且是這套配置的核心：**

1. **每個結論帶證據等級**——已確認／推論／候選／未知／未驗證，五選一，不留裸主張。
   細節見 [`.claude/rules/evidence-grades.md`](.claude/rules/evidence-grades.md)。
2. **先確認分支再動 code。** 在 main 上、有未提交變更、或使用者沒指定分支就要改 → 停下來問。
3. **破壞性 git 操作前先打 backup tag。** `reset --hard`／`push --force`／`branch -D`／`rebase`。

## 目錄對照

| 你要找 | 在哪 |
|---|---|
| 常駐規則（六條） | `.claude/rules/` |
| 按需載入的能力（17 個） | `.claude/skills/`，路由見 `.claude/skills/INDEX.md` |
| Subagent 模板（14 個） | `.claude/agents/` |
| 確定性 Gate（3 個 hook ＋ 自測） | `.claude/hooks/` |
| 領悟帳本 | `docs/lessons/` |
| 為什麼每條規則存在 | `.claude/ABLATION.md`、`docs/DESIGN_RATIONALE.md` |

## 在其他 agent 上跑得起來的部分

`.claude/hooks/*.sh` 只依賴 bash ＋ git，不依賴 Claude Code。任何能在工具呼叫前
執行外部命令的 agent 都掛得上去——它們讀 stdin 的 JSON payload，用退出碼表達判定
（2 = 擋下，1 = 提示，0 = 放行）。

`templates/_meta/bootstrap_check.sh` 與 `docs/eval/run_eval.py` 同樣是獨立腳本。
