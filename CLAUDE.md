# Serendipity — Epiphany

Claude Code 工程 harness：常駐規則、按需 skills、執行模板、確定性 gate 與領悟帳本。

## 入口

| 要找什麼 | 文件 |
|---|---|
| canonical skills 與路由 | [`skills/INDEX.md`](skills/INDEX.md) |
| 常駐規則 | [`.claude/rules/`](.claude/rules/) |
| 一輪工作怎麼跑 | [`.claude/RUNBOOK.md`](.claude/RUNBOOK.md) |
| 元件與責任 | [`.claude/WORKFLOW.md`](.claude/WORKFLOW.md) |
| 規則的失敗證據與消融 | [`.claude/ABLATION.md`](.claude/ABLATION.md) |
| 設計理由 | [`docs/DESIGN_RATIONALE.md`](docs/DESIGN_RATIONALE.md) |

## 常駐節奏

1. 先確認分支與工作樹；main、未提交變更或分支未指定時先停下確認。
2. 每個結論標示證據等級：已確認／推論／候選／未知／未驗證。
3. 有適用 skill 時先讀 canonical 方法，再執行與驗證。
4. 修改必須以碰到交付物本身的新證據驗證；沒有驗證不得宣稱完成。
5. 破壞性 Git 操作前建立指向目前 HEAD 的 `backup/*` tag。
6. 只有產生下一輪會再用到的領悟時，才寫入 `docs/lessons/`。

`.claude/skills/` 是由 `skills/` 同步出的安裝產物；不要直接修改。同步與驗證方式見 README。
