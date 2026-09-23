---
name: se-resume
description: 工作被中斷後的斷點續跑——上一段被用量上限、斷線、當機或手動中斷打斷時，先拿現實對照斷點再接著做：哪些未提交的變更是上一段留下的、哪些是之後別人改的、哪些驗證已經失效、哪些有副作用的步驟其實已經做完。也管長任務開工時怎麼留下可續跑的斷點。當上一段工作是被打斷的——使用者說「從上次停下的地方繼續」「剛剛斷掉了」「用量重置了」「再試一次」、開工時看到 [斷點] 提示——或要開始一段很長可能一次跑不完的工作時使用。上一回合正常結束後說的「繼續下一步」是照計畫往下做，不是續跑，不用這個。
---

# Resume — 斷點續跑

**續跑不是「照上次的筆記往下做」，是「先查現實，再決定從哪裡做」。**

上一段留下的任何宣稱——對話摘要、「測試過了」、「第 3 步做完了」——在中斷之後都降級成**推論**。
中斷的那一刻，最常見的就是「做了但沒記到」與「記了但沒做完」。

---

## 斷點從哪來

`hooks/checkpoint.sh` 自動寫，不需要你記得（`tools/checkpoint.py` 是本體）：

| 事件 | 記下什麼 |
|---|---|
| 每次 Edit／Write／Bash 之後 | 整個工作樹的指紋、HEAD、分支（背景執行，不拖慢工作） |
| 回合正常結束／因 API 錯誤結束 | `turn_end`／`turn_failed`（含原因，例如 `rate_limit`） |
| 使用者送出訊息 | 訊息原文（中斷後用來回答「剛剛在做什麼」） |

**判定中斷：最後一個動過工作樹的「別的程序」，有沒有正常結束它的回合。**
沒有結束標記時，查那個 Claude Code 程序（`CLAUDE_PID`）還在不在——還在就是**並行**，不是中斷。
呼叫者自己的程序只信正面的失敗訊號（`turn_failed`），不從「還沒結束」推論自己掛過（`docs/lessons/0011`）。

有斷點時，開新 session（含 `--resume`）會自動印出 `[斷點]` 簡報；
同一個 session 因 API 錯誤中止（例如用量上限）後的下一則訊息也會提醒一次。

日誌在 `.git/serendipity/journal.jsonl`：不進版控、每個 worktree 各一份。

## 續跑五步（順序不能換）

```bash
python .claude/tools/checkpoint.py resume
```

**先看第一行。** 說「上一段工作正常結束，沒有需要續跑的東西」——這個 skill 到此為止，
照使用者原本的要求做。上一回合正常結束後的「繼續」只是往下做，不是續跑。

### 1. 先處理進行中的 git 操作

簡報出現 `進行中的 git 操作`（rebase、merge、cherry-pick…）時，**在那之前什麼都不要做**。
在做到一半的 rebase 上開始新工作，後面每一個 commit 都建立在不確定的狀態上。
`git status` 看清楚，再決定 `--continue` 還是 `--abort`（`--abort` 屬 Critical Section，先打 backup tag）。

### 2. 認領：哪些變更是上一段留下的

| 簡報說 | 意思 | 做法 |
|---|---|---|
| 「工作樹和斷點當下完全相同」 | 未提交的變更全部在上一段工作的最後一個動作之前就存在 | 可以接手，**不必問**——這正是 `dispatch.md` 第 3 條警訊的例外證據 |
| 「斷點之後被改過的檔案」 | 中斷後有人（使用者、另一個 session）動過 | **這些照 `dispatch.md` 第 3 條處理：STOP 並確認**，不要覆蓋 |
| 「HEAD 在斷點之後移動過」 | 中斷後有人 commit、切分支或 reset | 先 `git log --oneline -5` 看是誰，再繼續 |

**「上一段留下的」不等於「agent 親手改的」**：同一段時間裡別的程序寫出來的檔案，也會算在上一段。
簡報給的是時間上的歸屬，不是作者歸屬。

### 3. 失效的驗證先重跑

簡報裡 `工作樹已變，視為未驗證` 的那幾條，**在寫任何新東西之前先重跑**。
中斷前的綠燈只對中斷前的那棵樹成立。在壞掉的狀態上繼續疊，下一次失敗會找不到是哪一層壞的。

### 4. 從第一個「現實不成立」的步驟繼續

`resume` 會對每一步跑 `--done-when`：

| 簡報 | 意思 |
|---|---|
| `✓ 現實成立` | 做完了，跳過 |
| `✓ 現實成立（沒記到完成——可能做完就斷了）` | **最危險的窗口**：副作用發生了、紀錄沒寫。跳過，不要重做 |
| `✗ 未成立（宣稱完成，但現實不成立）` | 紀錄說做完、現實說沒有。以現實為準，重做 |
| `← 從這裡繼續` | 斷點 |

**有副作用的步驟，重做之前先查現實有沒有做過**（check-then-act）：

| 動作 | 做過了嗎 |
|---|---|
| commit | `git log --oneline -5`；`git status` 是否已乾淨 |
| push | `git fetch -q && git rev-parse HEAD origin/<branch>` 兩個一樣 |
| 開 PR | `gh pr list --head <branch> --state all` |
| merge PR | `gh pr view <n> --json state` |
| 刪遠端分支 | `git ls-remote --heads origin <branch>` 是空的 |
| tag | `git tag -l <name>`；遠端 `git ls-remote --tags origin <name>` |
| 寫進外部系統（API、資料庫、發訊息） | 用冪等鍵或先查再寫；**查不到就問人，不要重送** |

### 5. 已拍板的決定不重問

簡報裡的 `已拍板` 是使用者在中斷前給過的答案。**不要再問一次。**
被重問一個已經回答過的問題，是續跑體驗裡最讓人失去信任的一件事。

---

## 開工時就留斷點（長任務）

hook 自動記工作樹，但有三件事它看不到，要你寫：

```bash
# 步驟與完成條件——完成條件要能用指令檢查，不是「感覺做完」
python .claude/tools/checkpoint.py step add S1 "付款重試邏輯" --done-when "pytest tests/test_retry.py -q"
python .claude/tools/checkpoint.py step add S2 "推上遠端" --done-when 'test "$(git rev-parse HEAD)" = "$(git rev-parse @{u})"'
python .claude/tools/checkpoint.py step done S1

# 驗證——證據綁定當下的工作樹指紋，樹一變就自動失效
python .claude/tools/checkpoint.py verify -- bash .claude/hooks/selftest.sh

# 使用者拍板的決定——拿到答案就記
python .claude/tools/checkpoint.py decide "非會員能不能退款" "不能"

# 整段工作結束（合併之後）
python .claude/tools/checkpoint.py close
```

**什麼時候值得寫步驟**：預期跨一個以上回合、或包含有副作用的動作（push、PR、部署、發訊息）。
一回合做得完的小改動，hook 自動記的就夠了。

## 長時間腳本自己的斷點

跑很久的腳本（訓練、批次處理、評測）被打斷，跟 agent 被打斷是兩件事——腳本要自己能續跑：

1. **每完成一個單位就落地**，不要全部算完才一次寫
2. **重跑時跳過已經存在的產出**（`if out.exists(): continue`）
3. **先寫暫存檔，再原子改名**（Python `os.replace`）——寫到一半被打斷，舊的完整產出還在（`core-rules` 第 3 條）
4. **記下 seed 與設定**，續跑的那一半和前一半才是同一個實驗

## 邊界

- 斷點只在 `.git/` 裡。**不把續跑簡報寫進 repo**——它是暫態，不是文件。
- `[斷點] 沒有記錄` 不等於沒有中斷：hook 沒裝、沒跑、或這個 repo 剛 clone，都會是這樣。
- 簡報出現 `記錄器出過錯` 時，斷點可能不完整，其餘判斷一律降一級。
- 計畫中的交接（刻意換 Process）用 `templates/HANDOFF.md`；這個 skill 處理的是**沒有預期的**中斷。

## 完成條件

- 進行中的 git 操作已處理
- 斷點之後別人改過的檔案已確認，沒有被覆蓋
- 失效的驗證已重跑，結果寫進回報
- 從第一個現實不成立的步驟繼續；有副作用的步驟重做前已查過現實
- 沒有重問已拍板的決定
