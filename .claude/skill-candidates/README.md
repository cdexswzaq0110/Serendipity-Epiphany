# 候選 Skill

**這裡的東西 Claude Code 不會自動載入。** 刻意放在 `skills/` 之外。

## 為什麼要有這一層

`se-acquire` 在處理一個**沒有任何 skill 覆蓋**的任務時，會把做法記下來成為候選 skill。
那是學習新技能的第一步——但只是第一步。

一個剛從單次經驗寫出來的做法，還沒被驗證過。它如果直接放進 `skills/`，就會在沒人察覺的
情況下開始影響路由：description 寫得夠像，模型就會在不相關的任務裡載入它。

那正是「自動生成 skill 但沒有驗證閉環」——一份外部的自進化專案分級把這條路判成**半成品**。

## 怎麼升級成正式 skill

```bash
python .claude/tools/promote_skill.py --list              # 看所有候選的狀態
python .claude/tools/promote_skill.py <名稱> --dry-run    # 只檢查
python .claude/tools/promote_skill.py <名稱>              # 檢查並升級
```

四道閘，對應 `se-epiphany` 的 GEP 四關：

| 閘 | 要求 |
|---|---|
| SCAN | `SKILL.md` 存在，`name` 與目錄一致，`description` 寫得出觸發條件 |
| VALIDATE | frontmatter 的 `validated` 有值——這套做法**實際用過且成功**，寫得出在哪一次 |
| MUTATE | `evals/trigger-cases.md` 至少 **3 條獨立來源**正例。照 description 寫的案例不算 |
| SOLIDIFY | 名稱不與既有 skill 衝突 |

四道全過才搬進 `skills/` 並寫入 `INDEX.md`。之後 `git commit` 時 `check-router.sh` 會再驗一次。

## 候選的格式

```text
skill-candidates/<名稱>/
├── SKILL.md                 # 跟正式 skill 同格式，frontmatter 多一個 validated
└── evals/trigger-cases.md   # | # | 使用者說的話 | 來源 |
```

`validated` 的寫法：`2026-09-22 在 <專案> 用這套做法完成了 <什麼>，結果 <可驗證的產出>`。
寫不出來就代表還沒真的用過。
