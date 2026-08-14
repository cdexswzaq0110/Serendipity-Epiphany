<div align="center">

<img src="assets/banner.png" alt="Serendipity — Epiphany" width="880">

# Serendipity — Epiphany

**機遇下，突然領悟學到的智慧。**

我的 Claude Code 開發配置。

</div>

---

## 這套配置在解什麼問題

大部分的開發配置管「怎麼把事情做完」。這一套多管一件事：**怎麼把每次撞出來的領悟留下來，並且讓它有機會變成制度。**

```
機遇（撞到）  →  領悟（寫成 Lesson）  →  智慧（升級成常駐規則）
   一次意外         docs/lessons/           .claude/rules/
                                         ＋ ABLATION 的失敗證據
```

沒有升級路徑的帳本只是日記；沒有帳本的常駐規則沒有證據。這套配置把兩端接起來。

---

## 快速開始

```bash
# 1. 複製到新專案
cp -r "Serendipity — Epiphany/.claude" your-project/.claude
cp -r "Serendipity — Epiphany/templates" your-project/templates

# 2. 在新專案裡走一次 bootstrap
#    templates/_meta/new_project_bootstrap.md
```

Windows：

```powershell
Copy-Item ".\Serendipity — Epiphany\.claude" -Destination "your-project\.claude" -Recurse
Copy-Item ".\Serendipity — Epiphany\templates" -Destination "your-project\templates" -Recurse
```

完整的安裝、四條路線實際走法、每個能力何時觸發：**[docs/USAGE.md](docs/USAGE.md)**

---

## 結構

```
CLAUDE.md                  # 常駐入口：這是什麼、怎麼開始、預設節奏
.claude/
├── CLAUDE.md              # 元件責任與 8 條維護契約
├── EXECUTION_MODEL.md     # 任務分解、執行派發與平行協調的完整定義
├── WORKFLOW.md            # 三層＋三角色怎麼一起運作、context 邊界、驗證紀律
├── RUNBOOK.md             # 四條路線走查（A 直接做／B 規劃／C 撥霧／D 蒐證）
├── ABLATION.md            # 常駐面消融紀錄：每條規則的失敗證據
├── rules/           (6)   # 常駐規則
├── skills/         (16)   # Coroutine 庫，按需載入
├── agents/          (9)   # Thread / Process 模板
└── settings.json          # 最小權限基線 ＋ 敏感路徑 deny
templates/                 # CONTEXT / ADR / PROCESS_SPEC / HANDOFF ＋ bootstrap
docs/
├── USAGE.md               # 詳細使用說明
├── DESIGN_RATIONALE.md    # 每條規則為什麼存在、刻意不做什麼
└── lessons/               # 領悟帳本
```

---

## 執行模型：任務分解、執行派發、平行協調

三件事全部用**作業系統併發模型**命名。借用既有語彙，是因為我已經知道兩個 thread 同時寫同一塊記憶體會出事——那份直覺不用重新教。

### 分解只有三層

```
Workload（一輪工作）
│
├─ Process ──────── 可獨立派發、獨立驗證的執行單元（完整 context 隔離）
│   ├─ Thread ───── Process 內可平行的更小單元（唯讀或無寫入衝突）
│   └─ Coroutine ── 同 context 內載入的方法（無隔離、無平行）
│
└─ Process ──────── （與上一個互不相依，或只共用寫入鎖）
```

| 單位 | 隔離 | 何時用 |
|---|---|---|
| **Coroutine** | 無（同 context） | 需要一套方法，不需要隔離。**預設就是這個** |
| **Thread** | 獨立 context 視窗，共享工作樹 | 唯讀 fan-out：搜尋、審查、第二意見 |
| **Process** | 完整 | 一個垂直切片、規劃→實作的邊界 |
| **Connection** | 外部資源 | CLI、MCP、瀏覽器、DB、API 配額、GPU |

一個 Process 要同時滿足四條：**完整**（端到端可觀察）· **可獨立驗證** · **裝得進一個新 Process** · **接縫已定**。裝不進就往下拆，無法獨立驗證就往上合併。

Pool 三種：**Thread Pool**（唯讀 fan-out）· **Process Pool**（獨立切片）· **Connection Pool**（有上限、可回收、不洩漏）。

同步原語：`Ready Queue` · `Mutex（寫入鎖）` · `Semaphore` · `Critical Section` · `Barrier` · `Fork/Join` · `Race Condition` · `Deadlock` · `Starvation` · **`GIL`（＝我本人，一次只能問一個決策）**

配置元件也對應上去：`rules/` = Kernel · `skills/` = Coroutine 庫 · `agents/` = Thread/Process 模板 · 交接文字 = IPC 訊息 · `CONTEXT.md` = 共享記憶體 · context window = 記憶體 · compact = swap。

**最重要的一個區分：寫入衝突是 Mutex，不是依賴。** 標成 `Depends on` 會憑空製造一條假的關鍵路徑。

完整定義：[.claude/EXECUTION_MODEL.md](.claude/EXECUTION_MODEL.md)

---

## 三個角色

| 角色 | 誰 | 做什麼 | 不做什麼 |
|---|---|---|---|
| **Scheduler** | 主 Process | 規劃、派發、驗證、收斂 | 不做 worker 級的工作 |
| **Supervisor** | 最強模型的唯讀 Thread | 只在**承諾邊界**被諮詢 | **從不執行** |
| **Worker** | Thread／Process Pool | 通過驗證的最便宜配置 | 不自我核准、不接下一個 Process |

**模型是旋鈕，層級才是不變的部分。**

---

## 常駐規則（6 條）

| 規則 | 核心 |
|---|---|
| **core-rules** | 來源優先、可追溯、保護使用者工作、以證據宣告完成、最小變更、**留下領悟** |
| **evidence-grades** | 每個結論帶等級：`已確認`／`推論`／`候選`／`未知`／`未驗證`。不可升級也不可降級 |
| **dispatch** | 預設 Coroutine、切片換 Process、平行前確認鎖、GIL 一次一問 |
| **git-workflow** | 先開分支、Critical Section 先 backup tag、commit→push→PR 連貫 |
| **thinking-boundary** | 速通／深思、雛型期不前置治理、**預算超支不得靜默** |
| **register** | 文件 L1／L2／L3；對話何時翻到決策層 |

新增常駐規則前先讀 [ABLATION.md](.claude/ABLATION.md)——**填不出「因為什麼失敗才存在」的規則，不該常駐。**

---

## Skills（16 個 Coroutine）

### 通用

| 你在做什麼 | 載入 |
|---|---|
| 需求還模糊，要探索並定接縫 | `se-design` |
| 想法太大，連要問什麼都不確定 | `se-discovery` |
| 要被逼問／想法要被戳破／答案在別人身上 | `se-clarify` |
| 不確定值不值得做 | `se-feasibility` |
| 專案詞彙混亂 | `se-context-language` |
| 要寫程式 | `se-minimal-change` |
| 卡在 bug | `se-debug` |
| 變更完成要審查 | `se-two-axis-review` |
| 要任務分解、派發、管平行 | `se-scheduling` |
| 外部工具不確定能不能用 | `se-preflight` |
| 開分支、收尾開 PR | `se-branch-lifecycle` |
| 回答太長太散 | `se-focus` |
| **這一輪學到東西了** | **`se-epiphany`** |
| 要新增或修改 skill | `se-skill-authoring` |

### 特例領域（遇到相關問題才觸發）

| 你在做什麼 | 載入 |
|---|---|
| 設計一個系統、拿到 PRD 要寫架構文件、評估既有架構瓶頸 | **`se-system-design`** |
| 做 ML 專案、訓練模型、處理 split 與 leakage、要上線 | **`se-ml-lifecycle`** |

完整路由與「別選錯」欄：[.claude/skills/INDEX.md](.claude/skills/INDEX.md)

---

## Agents（9 個派發模板）

名字就說出隔離等級與成本。

| Agent | 型別 | 什麼時候派 |
|---|---|---|
| `thread-scout` | Thread | 廣度搜尋，只要結論不要檔案內容 |
| `thread-supervisor` | Thread（最強模型） | 承諾邊界：結果矛盾、驗證失敗兩次、計畫要結構性改變 |
| `thread-reviewer-spec` | Thread | Spec 軸審查：有沒有做對東西 |
| `thread-reviewer-standards` | Thread | Standards 軸審查：有沒有做好 |
| `thread-security` | Thread | 碰到 auth、輸入、秘密、對外介面、部署設定 |
| `process-worker` | Process | 一個 Process 的完整實作 |
| **`thread-system-architect`** | **Thread（最強模型）** | **系統設計九階段：估算 → 瓶頸 → 深挖 → 取捨總表** |
| **`process-ml-engineer`** | **Process** | **ML 六階段五道 Gate：定義 → 切分 → Pipeline → 評估 → 上線** |
| **`thread-ml-auditor`** | **Thread（最強模型）** | **既有 ML 專案稽核：這個分數可不可信** |

---

## 十條核心信念

1. **證據等級是第一公民。** 最貴的失敗是把推論寫得像事實。
2. **確定性工程 × Agent。** 不能出錯的用程式或清單保證，動態決策才交給模型。
3. **常駐面要有失敗證據。** 填不出「因為什麼錯誤才存在」就不該常駐。
4. **先爬最小實作階梯再寫程式。** 但絕不省略理解、信任邊界、資料遺失處理、安全、無障礙。
5. **Finding 是待驗證的主張，不是命令。** 提出者擁有它，被指出者可以反證。
6. **兩軸不合併。** 「規範全過但做錯東西」是最貴的失敗。
7. **共享語言先於程式碼。** `CONTEXT.md` 省的不只是 token。
8. **借用既有語彙，不自創詞。** 併發模型的直覺不用重新教。
9. **人的決策是全域鎖。** 一次只問一個。
10. **每一輪留下可檢索的領悟，而且要有升級路徑。**

每條信念背後的推導、以及**刻意不做的九件事**：[docs/DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md)

---

## 第一輪之後要做的事

**跑一次消融。** 常駐面 339 行，其中有四條標著「未登記」——連我自己都填不出它為什麼存在。那些是第一批刪除候選。

流程在 [.claude/ABLATION.md](.claude/ABLATION.md)，理由在 [docs/lessons/0001](docs/lessons/0001-ablation-first-run.md)。

> RUNBOOK 與 ABLATION 本來就該被實戰改寫。改完記得寫 Lesson。

---

## License

MIT
