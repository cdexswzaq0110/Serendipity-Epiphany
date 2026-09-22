---
id: L0009
date: 2026-09-22
outcome: useful
tags: [hooks, gate, 預篩, 判定]
anchors:
  - .claude/hooks/check-router.sh
  - .claude/hooks/guard-critical.sh
  - .claude/settings.json
supersedes:
source: self-observed
hits: 0
generalizes_to: 任何「上游過濾器決定要不要執行、下游腳本負責判定」的閘——hook 的 if、CI 的 path filter、webhook 的事件篩選
validated:
---

# 預篩不是判定

## 觸發情境

寫一道 Gate，而平台提供了一個「什麼時候才執行它」的過濾欄位——Claude Code hook 的 `if`、
CI 的 `paths:`、webhook 的事件類型。很自然會把判定條件寫在過濾欄位裡，腳本本身只管檢查。

## 領悟

**三支 commit 閘（`check-router`、`check-memory`、`guard-branch`）完全不讀指令內容**，
是否執行全交給 `if: "Bash(git commit*)"`。結果一條不含 `git` 的 Bash 指令被擋下。

實機探測，在 router 故意不一致的狀態下送出 8 種確定跟 commit 無關的指令：【已確認：2026-09-22 本 session】

| 形狀 | 被擋？ |
|---|---|
| `for` 迴圈、`while` 迴圈 | **被擋** |
| 單純指令、`;`／`&&` 串接、heredoc、`$(...)`、`if`、`git status` | 放行 |

`if` 對它拆不開的形狀會照樣觸發。**確切原因在 harness 內部，看不到**【未知：查過 hook 設定、
探測了 8 種形狀；下一步是讀 Claude Code 對 `if` 的解析文件或原始碼】——但修法不依賴原因。

**反方向的洞更嚴重。** `guard-critical` 早就自己讀指令（它的註解就寫著「不完全依賴 if」），
可是它認得的「指令位置」只有開頭與 `&&`／`;`／`|` 之後。所以：

- `for b in x; do git branch -D $b; done`
- `git -C repo reset --hard HEAD`
- 換行之後的 `git rebase main`

在沒有 backup tag 時**全部放行**【已確認：同一份新自測對舊版 51／13】。它是一道 Critical Section 閘。

**補洞時又開了一個反方向的洞。** 把 `do`、換行加進「指令位置」之後，第一個被新版擋下的，
是我自己描述這次修正的 commit——heredoc 裡的 commit message 寫著 `; do git branch -D`，
被當成了一條破壞性指令【已確認：本 session，修正前的版本不會擋它】。
heredoc 內文是資料不是指令，比對前要先去掉；規則因此抽成 `hooks/_command.sh`，四支閘共用一份。

## 為什麼會撞到

過濾欄位用的是跟權限規則一樣的語法，看起來像判定。但它的工作是**省成本**——不用每次 Bash 都
spawn 一個 shell。省成本的元件被設計成寧可多跑、不可漏跑，所以它的誤差方向是**多觸發**。

把判定寫在它身上，就繼承了它的誤差方向。而自己寫的判定，漏掉的是**自己沒想到的形狀**——
迴圈裡、帶全域選項、換行後。兩個洞的根是同一個：沒有把「指令會長什麼樣」當成需要測試的輸入空間。

## 下次怎麼做

1. **過濾欄位只當預篩。** 判定一律在腳本裡再做一次，讀 `tool_input` 自己決定。
2. **指令位置要涵蓋控制結構。** 開頭、`&&`、`;`、`|`、換行、`(`、`do`／`then`／`else` 之後。
   `git` 後面還可能夾全域選項（`-C <dir>`、`-c k=v`）。
3. **自測要有「同一個壞狀態、不同形狀的指令」**：狀態不一致時，不是 commit 的指令必須放行，
   迴圈裡的 commit 必須照擋。只測 `git commit -m x` 一種形狀，兩個方向的洞都看不到。
4. **新自測要先對舊版跑一次，看到紅燈。** 這次舊版 51／13——沒有這一步，無法證明案例抓得到問題。
5. **放寬比對之後，拿最常見的真實輸入重跑一次。** 這個 repo 最常見的 Bash 呼叫就是「用 heredoc 寫
   commit message」，而 commit message 常常在描述 git 操作。自測只放人工短句，這個退步抓不到；
   是真實 commit 撞到的。

## 失效條件

- 若 Claude Code 的 `if` 改成對複合指令逐段精確比對、且文件明示誤差方向，第 1 點仍成立（預篩就是預篩），
  但「迴圈會誤觸發」這個具體事實失效。
- 若 hook 改成讀結構化的 shell AST（而不是對 JSON 字串做 regex），第 2 點被取代。

## 已知殘餘

`-m "...; git reset --hard ..."` 這種**引號內**的敘述仍會被 `guard-critical` 誤擋（修正前也會）。
沒有處理：誤擋的代價是多打一個 backup tag，漏擋的代價是無法復原——這道閘的誤差方向刻意偏擋。
