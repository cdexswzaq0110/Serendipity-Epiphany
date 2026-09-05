---
id: L0006
date: 2026-09-05
outcome: useful
tags: [外部來源, 覆蓋度, 常駐面, 方法論]
anchors:
  - .claude/skills/se-debug/SKILL.md
  - .claude/skills/se-minimal-change/SKILL.md
  - .claude/skills/se-scheduling/SKILL.md
  - .claude/ABLATION.md
supersedes:
hits: 0
generalizes_to: 把任何外部最佳實踐清單併進一套已經成形的配置
validated:
---

# 外部最佳實踐清單，先做覆蓋度對照再決定加什麼

## 觸發情境

看到一份寫得很好的外部清單，每一條都對，而且每一條都讓人想「這個應該加進配置裡」。

**本次來源**：〈2026 年 Coding Agent 實戰技巧：10 個我每天都在用的 Pro Tips〉，garyhsieh.com。以下對照針對那 10 條。

## 領悟

**先對照，再決定。實際做完對照，10 條裡有 6 條已經被覆蓋，而且多半比原文更嚴格。**

一份好清單讀起來每條都成立，於是「加進去」感覺是零成本的。但這套配置的成本從來不在「有沒有寫下來」，在**常駐面每輪都要花的 token 與注意力**，以及**入口重疊造成的誤觸發**。沒有對照就整份併入，會同時付這兩筆。

### 對照結果

| 外部條目 | 這裡的狀態 | 落在哪 |
|---|---|---|
| 先 Research 再寫 Code | **缺口** → 已補 | `se-debug` 三次規則新增「補訊號」一階 |
| Model Routing | 已覆蓋 | `se-scheduling` 難度選模 ＋ Supervisor／Worker／Reviewer 三層；且已規定 Reviewer 不依難度換模型 |
| Handoff 不靠長 Session | 已覆蓋 | `templates/HANDOFF.md`（欄位比原文多：持有中的鎖、已宣告的假設、證據等級） |
| 平行 Session | 已覆蓋，且**機制層已實測拒絕** | `rules/dispatch.md` 3、`se-scheduling` Phase 2；見 `.out-of-scope/parallel-dispatch-rule.md` |
| 重複流程就 Skill 化 | 已覆蓋 | `se-skill-authoring` ＋ `se-epiphany` 升級表（`hits` 達 3 才升級，比「重複 2–3 次」多一道門檻） |
| 能用 Script 就不用 LLM | **缺口** → 已補 | `se-minimal-change` 新增「第 0 階」；同一條原則在常駐面的版本是 `ABLATION.md` 機械化優先 |
| 驗證對準真實 Surface | 原則已覆蓋、**對照表是缺口** → 已補 | `se-scheduling/references/verification-surfaces.md` |
| Never Self-Verify | 已覆蓋 | `se-two-axis-review` 兩軸隔離；原文只要求換人審，這裡另外禁止「叫第三個模型投票」 |
| 用 Agent 寫 Prompt | **部分缺口** → 已補（收窄） | `se-scheduling` Phase 1；只補 codebase 知識，意圖不清仍走 `se-discovery`／`se-clarify` |
| Cognitive Load 留給判斷 | 已覆蓋 | `se-focus` ＋ `rules/register.md` ＋ `dispatch.md` 4（GIL） |

**四個缺口全部落在 Skill，沒有一條進常駐面。** 依 `ABLATION.md`：填不出「模型反覆犯什麼錯」就不准常駐——這四條都是可重用做法，不是模型的錯誤行為補丁。

### 兩個具體收穫

1. **`.out-of-scope/` 真的省下一輪論證。** 「平行 Session」看起來完全該加，但 `parallel-dispatch-rule.md` 已經記著：那條規則實測過、行為沒變、而且不加也會發生。沒有那份紀錄，這一輪會重新提一次同樣的提案。
2. **覆蓋不等於一樣好，有時候是這裡更嚴格。** Never Self-Verify、Handoff、Skill 化三條，本地版本都多一道原文沒有的約束。對照時要分辨「已覆蓋」與「原文更完整」——後者才該改。

## 下次怎麼做

拿到外部清單時，逐條走 `skills/INDEX.md` 的**責任檢查表**，先問「這裡已經有嗎」，再問「該放哪一層」：

```
已覆蓋            → 不動，記在對照表裡（就是這則 Lesson）
原文更完整        → 改既有那一份，不新增
真缺口 ＋ 可重用做法 → 進**擁有該關注點的既有 Skill**，不開新 skill
真缺口 ＋ 每輪都成立  → 才考慮常駐，而且要先填得出失敗證據
```

**不要為一份清單開一個新 skill。** 這份清單橫跨 debug、派發、實作、審查四個關注點，包成一個 skill 會同時和四個既有入口搶觸發，違反維護契約第 1 與第 8 條要保護的東西。
