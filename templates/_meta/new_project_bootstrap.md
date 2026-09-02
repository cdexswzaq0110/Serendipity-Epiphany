# 新專案啟動（Bootstrap）

> 把這套配置 帶進**新專案**時的起步順序。本檔**不常駐**——開新專案時才讀。
>
> Serendipity 這個 repo 自己的入口是根目錄的 `CLAUDE.md`，不是這一份。

複製 `.claude/` 與需要的 `templates/` 到新專案後，在那個專案裡跑一次下面的四個 Phase。

---

## Phase 1 — 基礎資訊

```
1. 專案名稱？
2. 一句話：這個專案解決什麼問題？
3. 主要語言與框架？
4. 這是雛型驗證，還是要往 production 走？
```

第 4 題決定後面所有的深度。**不確定就填雛型**——用 production 的標準卡住雛型是最常見的浪費。

## Phase 2 — 七問澄清

```
1. 核心問題：主要解決什麼問題？
2. 核心功能：3–5 個最重要的？
3. 技術約束：偏好與限制？
4. 使用體驗：期望的操作感受？
5. 規模需求：預期用戶與效能？
6. 時程資源：時間與資源限制？
7. 成功標準：怎麼衡量成功？
```

答不出來的題目，載入 `se-clarify` 設計樹模式。不要猜著填。

## Phase 3 — 前置檢查

### 3.1 先進版控（這一條漏掉的代價不可逆）

```bash
cd <新專案>
git init -b main
printf '.claude/settings.local.json
' > .gitignore
```

**在複製任何檔案、寫任何一行之前做完。** 2026-09-02 第一次把這套配置帶進真實專案時，
因為還沒 init，一個檔案被工具毀掉之後只能整份重寫——見 [`docs/lessons/0004`](../../docs/lessons/0004-powershell-destroys-utf8-source.md)。

⚠ **注意上層目錄**：如果新專案開在一個已經是 git repo 的目錄底下（例如家目錄本身
被版控），`git status` 會有反應，但那是**上層的**版控，不是這個專案的。
`bootstrap_check.sh` 會抓這種情況。

### 3.2 工具前置檢查

跑一次 `se-preflight`：這台機器上有什麼 CLI、什麼 MCP、什麼 API key、平台並行數多少。

**在寫第一行程式碼之前做完**，不要邊做邊發現缺工具。

## Phase 4 — 產出三份檔案

### 1. 專案的 `CLAUDE.md`

```markdown
# CLAUDE.md — <專案名>

> **描述：** <一句話>
> **階段：** 雛型／production
> **語言：** <語言與框架>

## 開發流程

沒有寫死的命令序列。能力按需載入，路由見 `.claude/skills/INDEX.md`；
任務怎麼切、派給誰見 `.claude/EXECUTION_MODEL.md`。

預設節奏：確認分支 → 爬最小實作階梯 → 做出最小可動的東西 → 跑起來看 → 留 Lesson。

## 共享語言

見 `CONTEXT.md`。詞彙有衝突時以那份為準。

## 這個專案的實際指令

| 用途 | 指令 |
|---|---|
| 安裝 | |
| 開發 | |
| 測試 | |
| Lint／型別 | |
| 建置 | |

> 只寫**環境本身查不到**的東西。`package.json` 已經有的 script 不要抄一份進來——
> 環境是真相源，抄一份只會漂掉。

## 這個專案特有的約束

<只寫與模型預設行為不同的。填不出「為什麼需要這條」就不要寫。>
```

### 2. `CONTEXT.md`

用 `templates/CONTEXT.md`。**一開始只填三到五個詞**——這時候你猜的比知道的多。

### 3. `docs/lessons/INDEX.md`

空的索引，等第一則。

---

## 完成後檢查

**不要用眼睛核對，跑它：**

```bash
bash templates/_meta/bootstrap_check.sh <新專案路徑>
```

八項檢查，任何一項沒過就 exit 1：版控是否為本專案自己的、有沒有 commit、
`.claude/` 是否完整、`rules/` 是否六條、專案 `CLAUDE.md`／`CONTEXT.md`／
`docs/lessons/` 是否產出、`.gitignore` 有沒有擋 `settings.local.json`。

**核取方塊靠人記得，腳本不會忘。** 這份清單原本是七個方塊，第一次被真的執行時
就漏掉了最重要的那一條（版控）。

還有一項腳本判不了、要人自己確認：

- [ ] 專案的 `CLAUDE.md` **只放環境查不到的東西**（`package.json` 已有的別抄一份）
- [ ] 新專案裡用不到的 templates 已刪掉

---

## 第一輪之後要做的事

**跑一次消融。** 繼承來的 `rules/` 裡有一部分是在補一個已經不存在的模型缺陷——見 [`docs/lessons/0001`](../../docs/lessons/0001-ablation-first-run.md)。

流程在 `.claude/ABLATION.md`。
