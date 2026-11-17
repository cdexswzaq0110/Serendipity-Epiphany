# Serendipity — Epiphany

## 在解什麼問題

SE 是 Claude Code 的工程 harness，把可重用方法、常駐約束、確定性 gate、角色模板與驗證紀律放在同一套可追溯配置中。它降低需求誤解、未驗證完成宣稱、危險 Git 操作與經驗反覆遺失。

## 快速開始

Python 需求：3.11 以上，只使用標準庫。

```text
python scripts/sync_skills.py build --out <bundle-dir>
python scripts/sync_skills.py install --bundle <bundle-dir> --dest .claude/skills
python scripts/sync_skills.py check --dest .claude/skills
python -m unittest discover -s tests -v
```

`skills/` 是 canonical source；`.claude/skills/` 是含 manifest 的安裝產物，請勿直接手改。`install` 會先在相鄰暫存目錄完整驗證，再替換整個目錄，因此 manifest 以外的舊檔會被移除。

Hooks 由 Python 執行。Windows 若只有 `py` launcher，請建立可呼叫的 `python` 命令或把 `.claude/settings.json` 與 `.claude/hooks/hooks.json` 的 `python` 改成 `py -3`。高風險錯誤被擋時，可建立 `.claude/hooks/BREAK_GLASS` 放行一次；檔案會在使用後刪除。

## 結構

```text
skills/                 canonical Agent Skills（核心 9 個＋extended）
scripts/sync_skills.py  bundle build／install／check
.claude/skills/         由同步工具產生的 Claude Code 副本
.claude/rules/          常駐規則
.claude/hooks/          Python PreToolUse gates
.claude/agents/         執行模板
docs/lessons/           可跨輪重用的領悟
tests/                  同步工具與 hooks 自我測試
```

詳細流程見 [RUNBOOK](.claude/RUNBOOK.md)，規則存在理由與消融方式見 [ABLATION](.claude/ABLATION.md)，skill 路由見 [skills/INDEX.md](skills/INDEX.md)。
