# 觸發案例集

怎麼跑、怎麼判、限制在哪 → [README.md](README.md)。

**每條跑 2 次，兩次都對才算 PASS。**

## A 組：碰撞區（4 條）

`se-feasibility` / `se-discovery` / `se-design` / `se-clarify` 四個入口的 description 落在同一個語意區間，「當需求還模糊」這五個字在 `se-design` 與 `se-clarify` 裡逐字重複。這組就是為了量它們的互斥程度。

**互斥判準**（description 改寫時的目標狀態）：

```text
se-feasibility  → 還沒決定要不要做
se-discovery    → 決定要做，但講不出「做完長什麼樣」
se-design       → 講得出終點，要切成可派發的片
se-clarify      → 答案不在任何文件裡，在某個人身上
```

| # | 使用者說的話 | 該載入 | 明確不該載入 |
|---|---|---|---|
| A1 | 這東西做得出來嗎，大概要多久 | `se-feasibility` | `se-design`、`se-discovery` |
| A2 | 我想做一個內部工具，但還講不出做完長什麼樣 | `se-discovery` | `se-design`、`se-clarify` |
| A3 | 這個功能幫我切成幾塊，我要分批做 | `se-design` | `se-discovery` |
| A4 | 這個決定要問 PM，幫我整理成一份給他填的東西 | `se-clarify` | `se-design`、`se-feasibility` |

## B 組：對照（4 條）

這組測的是**本輪不會改動**的 skill。A 組改完之後 B 組若跟著變差，代表改動的副作用溢出到沒碰的地方——這是只看 A 組看不到的。

| # | 使用者說的話 | 該載入 | 明確不該載入 |
|---|---|---|---|
| B1 | 這段一直報錯，幫我找原因 | `se-debug` | `se-minimal-change` |
| B2 | 加一個欄位到這個表單 | `se-minimal-change` | `se-design`、`se-two-axis-review` |
| B3 | 改完了，幫我檢查一下 | `se-two-axis-review` | `se-debug` |
| B4 | 我要開分支做這個然後開 PR | `se-branch-lifecycle` | `se-scheduling` |

## C 組：派發觀察（2 條，不判 PASS/FAIL）

**這組只記錄，不判定。** 因為「該不該派 agent」本身就是待驗的問題——`dispatch.md` 第 1 條說預設 Coroutine，但那條在 `ABLATION.md` 標著「base 提示可能已足夠」。

記錄的目的是累積 agent 誤選的具體案例。**有了案例才談收斂，沒有案例就是憑感覺砍。**

| # | 使用者說的話 | 記錄什麼 |
|---|---|---|
| C1 | 這個功能牽涉到哪些檔案，幫我掃一遍 | 直接自己搜（Coroutine）／派 `thread-scout`／派別的？ |
| C2 | 這個資料表設計有沒有問題 | 直接答／派 `thread-dba`／派 `thread-system-architect`？ |

判準暫缺是刻意的：先看它實際怎麼選，再決定什麼叫選對。

---

## 執行紀錄

| 日期 | 版本 | A 組 | B 組 | 命中 | 備註 |
|---|---|---|---|---|---|
| — | `4ff5c26` + hook 化 | ?/4 | ?/4 | ?/8 | **baseline 尚未執行**——需要乾淨 session，由使用者跑 |

**baseline 沒跑完之前不得改動 A 組四個 skill 的 description。** 這是 Stage 3 的前置條件：沒有基準線，改動的好壞無法判斷，只會變成另一次憑感覺。

### C 組觀察紀錄

| 日期 | 案例 | 實際行為 | 備註 |
|---|---|---|---|
| — | — | — | 尚未執行 |
