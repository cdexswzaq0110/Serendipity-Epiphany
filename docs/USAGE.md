# 使用說明

從安裝到日常使用的完整流程。**照順序讀一次，之後只查需要的那一節。**

---

## 目錄

1. [安裝](#1-安裝)
2. [第一次在新專案啟動](#2-第一次在新專案啟動)
3. [每天怎麼開一輪工作](#3-每天怎麼開一輪工作)
4. [四條路線的實際走法](#4-四條路線的實際走法)
5. [什麼時候會自動觸發哪個能力](#5-什麼時候會自動觸發哪個能力)
6. [怎麼派 Agent](#6-怎麼派-agent)
7. [兩個特例領域怎麼用](#7-兩個特例領域怎麼用)
8. [領悟帳本怎麼經營](#8-領悟帳本怎麼經營)
9. [常見情況速查](#9-常見情況速查)
10. [怎麼維護這套配置本身](#10-怎麼維護這套配置本身)

---

## 1. 安裝

### 單一專案

```bash
cp -r "Serendipity — Epiphany/.claude" your-project/.claude
cp -r "Serendipity — Epiphany/templates" your-project/templates
```

```powershell
Copy-Item ".\Serendipity — Epiphany\.claude" -Destination "your-project\.claude" -Recurse
Copy-Item ".\Serendipity — Epiphany\templates" -Destination "your-project\templates" -Recurse
```

**不要複製根目錄的 `CLAUDE.md`**——那份描述的是配置本身，新專案要產生自己的。

### 讓某些能力在所有專案都可用

把 skill 目錄 symlink 到全域，**檔案實體留在專案內**（版控追得到），全域只放捷徑：

```bash
ln -s "$(pwd)/.claude/skills/se-epiphany" ~/.claude/skills/se-epiphany
ln -s "$(pwd)/.claude/skills/se-focus"    ~/.claude/skills/se-focus
```

```powershell
# 需要管理員或開發者模式
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\se-epiphany" -Target "$PWD\.claude\skills\se-epiphany"
```

**建議全域共用的**：`se-epiphany`（領悟帳本要跨專案累積）、`se-focus`（輸出密度）、`se-minimal-change`。
**建議留在專案內的**：其餘的——它們會被專案的實際情況改寫，改一處全域同步反而危險。

### 驗證裝好了

在專案裡開一個 Claude Code session，打：

```
/se-epiphany
```

有反應就是裝好了。沒反應 → 檢查 `.claude/skills/se-epiphany/SKILL.md` 存在，且 frontmatter 的 `name` 與目錄名一致。

---

## 2. 第一次在新專案啟動

跑一次 `templates/_meta/new_project_bootstrap.md` 的四個 Phase。實際做法：

**貼這段給 Claude Code：**

```
請照 templates/_meta/new_project_bootstrap.md 幫我啟動這個專案。
先問我 Phase 1 的四題，我答完再往下。
```

四個 Phase 做的事：

| Phase | 做什麼 | 產出 |
|---|---|---|
| 1 | 基礎資訊四題 | 專案定位、階段（雛型 or production） |
| 2 | 七問澄清 | 核心問題、功能、約束、規模、成功標準 |
| 3 | 前置檢查 | 這台機器有什麼 CLI、MCP、API key、並行數 |
| 4 | 產出三份檔案 | 專案的 `CLAUDE.md`、`CONTEXT.md`、`docs/lessons/INDEX.md` |

**Phase 1 第 4 題最重要**：雛型還是 production。它決定後面所有的深度。**不確定就填雛型**——用 production 的標準卡住雛型是最常見的浪費。

**Phase 3 在寫第一行程式碼之前做完。** 跑到一半才發現缺工具，等於整輪重來。

### 專案的 `CLAUDE.md` 只放環境查不到的東西

`package.json` 已經有的 script 不要抄一份進來——**環境是真相源，抄一份只會漂掉**。

該寫的是：沒寫下來的慣例、選擇背後的理由、沒有設定檔會招認的坑。

---

## 3. 每天怎麼開一輪工作

### 開工前只問一句

> **「做完長什麼樣」，你現在講得出來嗎？**

| 答案 | 走 |
|---|---|
| 講得出來，而且很小 | A：直接做 |
| 講得出來，是一個功能 | B：規劃一輪 |
| **講不出來** | C：先撥霧 |
| 講得出來，但不確定**值不值得做** | D：先蒐證 |

這一句是整套配置的入口。答錯了走錯路線，後面全部白做。

### 開工前值得做的一件事

如果這件事**似曾相識**，先讓它召回舊教訓：

```
這件事我好像做過類似的，先查一下 lessons
```

`se-epiphany` 會讀 `docs/lessons/INDEX.md`（只有指標，很便宜），挑最多 3 則展開。命中一則的話，你省下的是重踩一次的時間。

---

## 4. 四條路線的實際走法

### A：直接做

```
開分支 → 爬最小實作階梯 → 做最小可動的東西 → 跑起來看 → 打掉或往下
```

**不能省的只有三件**：先開分支、回不了頭的決策寫 ADR、收尾判斷有沒有 Lesson。

其他全部不用：規劃、切片、覆蓋率、文件。

**離開這條路的訊號**：你開始記不住做過哪些決定，或東西要交給別人。

貼這段：

```
我要在這個專案加 <一句話描述>。
走 A 路線，先開分支再動 code。
```

---

### B：規劃一輪

`▸` = 一個 Process 邊界（換一個新 session）。

#### ▸ 1 — 探索到切片（**不能中斷**）

```
載入 se-design。我要做 <一句話>。
先跟我確認接縫，再切片。這一輪不要開始實作。
```

兩個最常被跳過、但決定後面順不順的：

| 步驟 | 規則 |
|---|---|
| **定接縫** | 沿用既有 > 新開；用**能觀測到行為的最高**接縫；越少越好。**先確認再寫第一個測試** |
| **切片** | 縱切穿過所有層。四判準：完整、可獨立驗證、**塞得進一個新 Process**、接縫已定 |

任務分解完成後接著：

```
載入 se-scheduling，建 Ready Queue 與寫入鎖。
```

**這一輪結束時不要開始實作。** 這是 context 邊界，不是儀式——實作細節會污染後面每一片的推導。

#### ▸ 2..N — 每片一個新 session

每片開新 session，貼交接文字（`templates/HANDOFF.md` 的格式）：

```
新 context → 讀這片的計畫 → 爬最小實作階梯 → 在已確認接縫寫測試 → 跑 → commit
```

#### ▸ 收尾

```
載入 se-two-axis-review，基準點是 main。
```

兩軸跑完 → `se-branch-lifecycle` 開 PR → `se-epiphany` 留 Lesson。

**兩軸不要合併看。** Standards 與 Spec 分開報、不排名。

---

### C：先撥霧

用在「連要問什麼都不確定」的時候。

```
載入 se-discovery。我想做 <一個很大的東西>，但我講不出做完長什麼樣。
```

```
▸ 1     命名終點 → 廣度掃描 → 建決策節點 → 派 Thread Pool 蒐證 → 停
▸ 2..N  一個 Process 解一個 → 寫答案 → 更新地圖
▸ 清楚了 交棒 se-design
```

**兩個最容易搞錯的**：

1. 把霧預先切成 ticket 大小。判準是「現在能不能把問題**講精準**」，不是能不能回答。
2. 一個 session 想解好幾個。狀態活在地圖裡（`docs/maps/`），不活在 context 裡。

**想直接動手的衝動 = 已走到地圖邊界、該交棒**，不是可以加速。

---

### D：先蒐證

```
載入 se-feasibility。我想做 <一句話>，但不確定值不值得投入。
我的環境與限制是 <...>。
```

產出一份帶判定與機率區間的報告。**不給假精確的百分比，而且明確允許「無法評估」。**

報告完會問你：維持方案／縮小範圍／補驗證／停止。**它不會自動接著開始規劃。**

---

## 5. 什麼時候會自動觸發哪個能力

大部分情況你不用手動載入——描述你的處境，對應的能力會被觸發。**下面是「你講什麼」對應「會載入什麼」**：

| 你講的話 | 觸發 |
|---|---|
| 「需求還很模糊」「這個功能要怎麼做」 | `se-design` |
| 「這個太大了我不知道從哪開始」 | `se-discovery` |
| 「幫我想清楚」「戳破這個想法」「這要問誰」 | `se-clarify` |
| 「這做得出來嗎」「值不值得」「要多久」「大概多少錢」 | `se-feasibility` |
| 「這個東西我們叫什麼」「名詞好亂」 | `se-context-language` |
| 「幫我實作」「加一個功能」 | `se-minimal-change` |
| 「這裡有 bug」「測試掛了」「行為怪怪的」 | `se-debug` |
| 「review 一下」「這樣可以嗎」「要開 PR 了」 | `se-two-axis-review` |
| 「拆成幾個 Process」「可以平行嗎」「卡住了」 | `se-scheduling` |
| 「這個工具能用嗎」「環境好像有問題」 | `se-preflight` |
| 「commit」「推上去」「開 PR」 | `se-branch-lifecycle` |
| 「太長」「講重點」「所以我要幹嘛」 | `se-focus` |
| 「記下來」「上次是怎麼解的」「這個好像遇過」 | `se-epiphany` |
| 「這系統怎麼設計」「怎麼擴展」「怎麼避免超賣」 | `se-system-design` |
| 「要從零開一個專案」「這件事該誰負責」「缺什麼沒定義」 | `se-sdlc` |
| 「訓練模型」「這個 CV 分數對嗎」「要上線了」 | `se-ml-lifecycle` |
| 「模型為什麼這樣判」「哪些特徵重要」「這筆為什麼被拒」 | `se-ml-lifecycle` Stage 6 |

### 手動載入的時機

三種情況值得明確打 `/skill-name`：

1. **你知道要走哪條路，不想讓它猜**——例如明明是大工程，但描述聽起來很小。
2. **要強制走完整流程**——例如你想要完整的兩軸 review，而不是順手看一眼。
3. **它猜錯了**——載了 `se-design` 但你要的是 `se-system-design`。

### 一次只套一個流程型 Skill

`se-design`、`se-discovery`、`se-system-design`、`se-ml-lifecycle` 是**流程型**的，同一件事不要同時套兩個。

方法型的（`se-minimal-change`、`se-focus`、`se-epiphany`）可以疊加。

---

## 6. 怎麼派 Agent

### 先問一句：需要隔離嗎

```
需要隔離嗎？
├─ 不需要 ──────────────────────── Coroutine（載 skill，自己做）
└─ 需要
   ├─ 只讀，不寫工作樹 ──────────── Thread
   └─ 要寫工作樹或要換乾淨 context ─ Process
```

**預設是 Coroutine。** Thread 與 Process 都有啟動成本（重建 context、重讀檔案、結果要再收斂一次），只有隔離真的買到東西時才付。

「分工看起來比較專業」不是隔離買到的東西。

### 十四個 Agent 各自什麼時候用

| Agent | 派它的訊號 |
|---|---|
| `thread-scout` | 「這個東西在哪」而答案要掃過很多檔案 |
| `thread-supervisor` | 兩個結果矛盾／同一件事失敗兩次／計畫要結構性改變 |
| `thread-reviewer-spec` + `thread-reviewer-standards` | 變更完成要審查（**兩個一起派，首輪不互看**） |
| `thread-security` | 碰到 auth、使用者輸入、憑證、對外介面、檔案路徑、部署設定 |
| `process-worker` | 一個 Process 有明確交付成果、驗收條件與寫入鎖 |
| `thread-system-architect` | 系統設計、架構評估 |
| `process-ml-engineer` | ML 實作 |
| `thread-ml-auditor` | 既有 ML 專案要接手或分數可疑 |
| `thread-ml-interpreter` | 要說明模型靠什麼決定、某一筆為什麼、reason code、公平性檢查 |
| `thread-ux` | 要定義使用者怎麼走、畫面有哪些狀態（含失敗與空狀態） |
| `thread-sa` | 要定義系統依什麼判斷、規則的例外與衝突優先序 |
| `thread-dba` | 要設計或審查資料模型、索引、遷移安全 |
| `thread-devops` | 要規劃上線、監控告警、回滾路徑 |

### 平行的兩條紅線

**紅線一：平行前先確認鎖。** 以下同時只能有一個持有者：

同一檔案或模組寫入 · Schema · Migration · Lockfile · 同分支 git 寫操作 · 正式資料 · GPU · 全專案測試

**紅線二：寫入衝突是鎖，不是依賴。** 兩個 Process 都要改同一個檔案 → 標同一把鎖讓它們序列化，**不要串成 `Depends on`**。串成依賴會憑空製造一條假的關鍵路徑。

### 驗證派出去的結果

**驗證必須碰到交付物本身。**

grep 一下 README、測一個相鄰的東西、印出 `True` 然後 exit 0——這些都證明不了任何事。跑真正的指令，讀真正的輸出。

每個結果三選一：**PASS** ／ **FIX**（重新派發，指名具體失敗）／ **ESCALATE**。

**不要手動補丁一個實質失敗，重新派發。**

---

## 7. 兩個特例領域怎麼用

這兩個**不是每個專案都會用到**，但一旦命中就整套接手。

### 系統設計

觸發：要設計一個系統、拿到 PRD 要寫架構文件、被問怎麼擴展、評估既有架構瓶頸。

**完整走一輪：**

```
載入 se-system-design。
需求：<貼 PRD 或一句話題目>
先走 Stage 0–2，我要看到「第一個瓶頸假設」那句話再往下。
```

**只要單點答案：**

```
派 thread-system-architect：
我們現在 <現況>，遇到 <症狀>。第一個瓶頸在哪？
```

**九個階段**：需求預處理 → 範圍收斂 → 量化 → 實體與不變量 → API 契約 → High-Level → 瓶頸深挖 → 資料層 → 韌性 → Review 交付。

**三件一定會拿到的東西**：

1. 「第一個瓶頸假設」一句話
2. 每條 Invariant → 保護機制對照
3. 取捨總表（決策／選擇／放棄了什麼／何時重評）

**三個最常見的錯，這套流程各有一道閘擋著**：

| 錯 | 擋在哪 |
|---|---|
| 還沒估算就開始擺 Redis、Kafka | Stage 2 強制先量化 |
| 每個元件都講一點，沒有一個講深 | Stage 6 強制挑 2–3 個 |
| 「用 cache 就快了」不講代價 | 每個 Stage 的產出都要求寫出取捨 |

**設計定案之後**才交給 `se-design` 定接縫、`se-scheduling` 任務分解。這兩個是不同層次的工作。

---

### ML 專案

觸發：要做 ML、訓練或改進模型、處理 split 與 leakage、選 metric、要上線。

**新專案：**

```
載入 se-ml-lifecycle。
我要做 <任務描述>，資料是 <來源>。
先走 Gate 0 的七問。
```

**接手既有模型（最常見的情況）：**

```
派 thread-ml-auditor 稽核 <專案路徑>。
我要知道這個分數可不可信。
```

**這是最有價值的一個入口。** 接手別人的 ML 專案時，第一件事不是看分數多高，是看那個分數是怎麼算出來的。

**七階段六道 Gate**：

```
問題定義          → Gate 0  target / prediction time / metric / owner 明確
資料契約 + split  → Gate 1  schema、leakage、missing、drift 已確認
清洗 + 特徵 + Pipeline → Gate 2  可 fit/predict，未知類別測試通過
Baseline + CV/OOF → Gate 3  改善跨 folds / seeds / segments 穩定
調參 + ensemble   → Gate 4  通過品質、成本、公平與延遲門檻
封裝 + 上線 + 監控
```

**Gate 沒過不進下一階段。** 你說「幫我調參」但 Gate 1 沒過 → 它會回報這件事，先修驗證可信度。

**優先順序（最重要的一個表）：**

```
正確的 split ＞ 防 leakage ＞ metric 對齊 ＞ 資料語意 ＞ baseline
              ＞ 特徵 ＞ 模型選擇 ＞ 調參 ＞ ensemble
```

**模型複雜度通常不是第一個瓶頸。** 有人想直接跳到調參時，它會指出跳過了左邊哪幾項。

**三條硬規則**：

1. 所有 fit 型處理都在 training fold 內（imputer、scaler、encoder、target encoding、PCA、outlier threshold 全部）
2. 一次只改一個主要假設
3. 保存完整 pipeline，不是只存 `model.pkl`

---

## 8. 領悟帳本怎麼經營

**這是這套配置和一般開發配置唯一的結構性差別。** 用不用它，決定這套配置是不是只是又一套規則。

### 三個模式

| 模式 | 什麼時候 | 一句話 |
|---|---|---|
| **捕捉** | 一輪工作結束 | 這一輪撞出來、下一輪還會用到的東西 |
| **召回** | 開始一件似曾相識的工作 | 讀 INDEX，挑最多 3 則展開 |
| **回顧** | 帳本滿 20 則、或每個模型大版本 | 去重、標失效、**升級** |

### 捕捉：三個問題都是 yes 才寫

1. 這一輪有什麼是**開始前不知道、現在知道了**的？
2. 那件事**下次還會遇到**嗎？
3. 如果下次是全新 context 的你碰到，這一頁**夠不夠讓他直接跳過這個坑**？

任一個 no → 說一句「本輪無 Lesson，原因：⋯」然後結束。**不寫也要是判斷過的結果，不是忘記。**

**一輪最多寫 1 則。** 寫兩則通常代表其中一則不夠格，或這一輪其實是兩輪。

### outcome 三選一，`dead_end` 常被跳過但同樣值錢

| 值 | 意義 |
|---|---|
| `useful` | 這個做法有效，下次照做 |
| `dead_end` | **這條路走不通**。省下的是下次重走一遍的時間 |
| `corrected` | 我原本以為 X，實際是 Y |

「我試過 A，因為 B 所以不行」和「用 C」一樣有價值。

### 升級：帳本的意義在這裡

一則 Lesson 的 `hits` 達到 **3** → 它不是偶然，是規律。判斷該升級成什麼：

| 這則教訓的形狀 | 升級成 | 必須通過 |
|---|---|---|
| 每次工作都成立，而且與模型預設行為不同 | `rules/` 常駐規則 | ABLATION 的失敗證據欄——**這則 Lesson 本身就是證據** |
| 一套可重用的方法或清單 | 新 Skill 或既有 Skill 的一段 | `se-skill-authoring` 的觸發測試 |
| 一次不可逆的技術取捨 | ADR | 三條件閘 |
| 專案詞彙 | `CONTEXT.md` | — |
| 環境事實 | 專案的 `CLAUDE.md` | 環境是否已是真相源 |

**升級後原 Lesson 不刪除**，改標 `outcome: promoted`。它是那條規則的失敗證據來源。

### 失效檢查

每則 Lesson 有 `anchors`（它貼在哪些檔案上）。召回時：

```bash
git log --oneline -1 -- <anchor>
```

anchor 的最後改動晚於 Lesson 的 `date` → 標記「**程式已變動，需重新驗證**」，**不得直接當成已確認事實**。

一則過期的 Lesson 是「候選」，不是「已確認」。

---

## 9. 常見情況速查

| 情況 | 動作 |
|---|---|
| 這個要求可能有兩種讀法 | 只問會改變產出的缺口（上限 3 個），其餘宣告假設往下做 |
| 講不出「做完長什麼樣」 | `se-discovery`，別開工 |
| 「該長什麼樣」爭不出來 | 做丟棄式原型；決策折回真碼，原型丟掉 |
| 一片塞不進一個 Process | 切太粗，回去重切 |
| 要在計畫外的位置寫測試 | 那是新接縫，先確認 |
| 規劃逼近 ~120k | 寫下結論、開新 Process，不要硬撐 |
| 工作樹有不認得的變更 | **停**，問人（race condition） |
| 兩個 Process 互相等對方 | deadlock：拆依賴或合併成一個 |
| 某個 Process 永遠排不到 | starvation：拆小它的寫入範圍 |
| **同一個 bug 修第三次** | **停止改 code**，命名可能錯的那個假設，**寫 Lesson** |
| 想開 ADR | 三條件缺一就不寫（難以逆轉 ∧ 沒背景會困惑 ∧ 真實取捨） |
| 模型分數突然變很好 | 先懷疑 leakage，派 `thread-ml-auditor` |
| 設計文件寫不完 | Deep Dive 挑 2–3 個就好，High-Level 只要能跑 |

### 別做這些

| 反模式 | 改成 |
|---|---|
| 一個 Process 從規劃做到實作完 | 邊界斷開，切片各自新 Process |
| 為了看起來專業而派 Thread | 不需要隔離就 Coroutine |
| 跳過接縫確認直接寫測試 | 接縫是規劃階段的產出 |
| 橫切（先做完 schema 層再做 API 層） | 縱切，每片穿過所有層 |
| 依編號或「可能會衝突」建 `Depends on` | 那是鎖不是依賴 |
| 驗證時 grep 一下就說通過 | 跑真正的指令，讀真正的輸出 |
| 兩個結果矛盾就取平均 | 顯式解決，或升級 Supervisor |
| 預載整個 skill 庫求「完整」 | 只載當前步驟要的 |
| 小改動也跑完整規劃 | 走 A |
| 兩軸 review 合成一份排名 | 分開報，不排名 |
| 一次丟三個決策給人 | GIL：一次一個 |
| ML 分數不好就先調參 | 先看 Gate 哪一道沒過 |
| 做完就結束，什麼都沒留下 | `se-epiphany` |

---

## 10. 怎麼維護這套配置本身

### 八條維護契約（改動時必須重新滿足）

1. **Router 不說謊**——新增、改名、刪除 skill 要同步 `skills/INDEX.md`
2. **Frontmatter 與現實一致**——description 不得引用已退役的檔名
3. **大型 skill 分層**——SKILL.md 超過約 200 行時拆 `references/`
4. **來源可追**——新增第三方能力要記來源、授權與更新方式
5. **拒絕有紀錄**——退役一個機制時在 `.out-of-scope/` 留檔
6. **常駐面要有證據**——新增常駐內容要在 ABLATION 填「失敗證據」
7. **調用軸不得混淆**——每個 skill 只能是使用者調用或模型可調用之一
8. **改 skill 要跑觸發測試**——雙向：該載入時載入、不該載入時不載入

### 新增東西之前先判斷放哪

| 問題 | 是 → 放哪 |
|---|---|
| 每次任務都必須遵守，而且與模型預設行為不同？ | `rules/`——而且要能填出失敗證據 |
| 是知識、清單或可重用做法？ | Skill（Coroutine） |
| 需要獨立 context、工具或權限？ | Agent（Thread／Process） |
| 是確定、快速、低頻且無隱性狀態的自動化？ | 才考慮 Hook |
| 曾被拒絕過？ | 先讀 `.out-of-scope/` 對應檔 |

### 第一輪之後：跑消融

常駐面 339 行，其中四條標著「未登記」——連我自己都填不出它為什麼存在。

```
1. rules/ 暫時只留 core-rules.md
2. 跑三個最常做的任務
3. 只記反覆出現的同一種失敗（一次性失誤不算）
4. 一次加回一行，在 ABLATION.md 登記證據
5. 沒加回的不留
```

**不要憑感覺刪，要全部拿掉再逐條加回來。** 憑感覺刪會保留最順眼的，而不是最有用的。

流程在 [.claude/ABLATION.md](../.claude/ABLATION.md)，理由在 [lessons/0001](lessons/0001-ablation-first-run.md)。

### 一句話

**這套配置本來就該被實戰改寫。** RUNBOOK 的判準是估的、預算的形狀是估的、切片大小的判準是估的。跑完第一輪回來改它們——改完記得寫 Lesson。
