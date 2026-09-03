# Serendipity — Epiphany

**機遇下，突然領悟學到的智慧。**

這是一套 Claude Code 的工程 Harness——常駐約束、按需能力、派發模板、確定性 Gate 與驗證迴圈的集合。它假設你會反覆撞上同一類問題，所以除了「怎麼把事做完」，它同時管**怎麼把每次撞出來的領悟留下來**。

## 開始一輪工作

**沒有寫死的命令序列。** 能力按任務語意載入，或由你 `/skill-name` 明確啟動。

| 要知道什麼 | 去哪 |
|---|---|
| 實際怎麼跑一輪：A 直接做／B 規劃一輪／C 先撥霧／D 先蒐證 | [.claude/RUNBOOK.md](.claude/RUNBOOK.md) |
| 任務怎麼切、派給誰、怎麼同步（Process／Thread／Coroutine／Pool） | [.claude/EXECUTION_MODEL.md](.claude/EXECUTION_MODEL.md) |
| 誰負責哪一層的正確性（PM／UX／SA／Architect／SD／DBA／Dev／QA／DevOps） | [.claude/ROLE_MODEL.md](.claude/ROLE_MODEL.md) |
| Rules／Skills／Agents 三層怎麼一起運作 | [.claude/WORKFLOW.md](.claude/WORKFLOW.md) |
| 哪個 Skill 何時載入、相似入口怎麼區辨 | [.claude/skills/INDEX.md](.claude/skills/INDEX.md) |
| 改動這套配置本身時不能破壞什麼 | [.claude/CLAUDE.md](.claude/CLAUDE.md) |
| 這套配置的每一條規則為什麼存在 | [docs/DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md) |

## 預設節奏

1. **先確認分支再動 code**——在 main 上、有未提交變更、或使用者沒指定分支就要改，停下來問。
2. **寫程式前先爬最小實作階梯**——不用寫 > 已經有 > 標準庫 > 平台原生 > 已裝依賴 > 一行 > 最小可動（`se-minimal-change`）。
3. **有適用的 Skill 先載入再行動**；同一件事不同時套多個流程型 Skill。
4. **每個結論帶證據等級**——`已確認`／`推論`／`候選`／`未知`／`未驗證`，五選一，不留裸主張（`rules/evidence-grades.md`）。
5. **派發前先選單位**——不需要隔離就 Coroutine（載 skill）；唯讀 fan-out 用 Thread；要寫工作樹或要乾淨 context 用 Process（`rules/dispatch.md`）。
6. **雛型期走 happy path**——先能動、能驗證，不前置法規、權限、邊界案的窮舉。
7. **收尾留一則 Lesson**——這一輪學到、而且下一輪會再用到的東西，寫進 `docs/lessons/`（`se-epiphany`）。

先雛形 → 打掉 → 重構迭代是正常路徑，不是缺陷。衝突時，使用者直接要求的結果與 `.claude/rules/core-rules.md` 優先。

## 帶進新專案

複製 `.claude/` 與需要的 `templates/`，然後跑 `/se-bootstrap`，產出那個專案自己的 `CLAUDE.md` 與 `CONTEXT.md`，最後用 `templates/_meta/bootstrap_check.sh` 機械化驗收。

也可以裝成 plugin（`claude --plugin-dir <這個 repo>`）——那會拿到 skills、agents 與 hooks，**但不含常駐規則**。

**這一份不要整份複製過去**——它描述的是 Serendipity 本身。
