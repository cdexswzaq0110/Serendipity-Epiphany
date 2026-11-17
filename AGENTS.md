# AGENTS.md

非 Claude Code agent 先讀 [`CLAUDE.md`](CLAUDE.md)。

## 必守

1. 結論標示證據等級：已確認／推論／候選／未知／未驗證。
2. 修改前確認分支與工作樹；main 或不明分支先停下確認。
3. `reset --hard`、force push、`branch -D`、rebase 前先建立 `backup/*` tag。

## 入口

| 內容 | 位置 |
|---|---|
| canonical skills | [`skills/INDEX.md`](skills/INDEX.md) |
| 常駐規則 | [`.claude/rules/`](.claude/rules/) |
| 工作手冊 | [`.claude/RUNBOOK.md`](.claude/RUNBOOK.md) |
| 規則消融 | [`.claude/ABLATION.md`](.claude/ABLATION.md) |
| 領悟帳本 | [`docs/lessons/`](docs/lessons/) |

`.claude/skills/` 是同步產物；修改 `skills/` 後用 `scripts/sync_skills.py` 更新。
