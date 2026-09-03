# 觸發案例集

怎麼跑、怎麼判、限制在哪 → [README.md](README.md)。

**每條跑 2 次，兩次都對才算 PASS。**

**案例必須自足。** 第一版的句子照「真實說過的話」寫（「這東西做得出來嗎」「改完了幫我檢查」），但真實對話有前文，評測的每個 session 沒有——模型會回「這東西指的是什麼」而不是載入 skill。16 次裡 12 次什麼都沒載入，全是這個原因。**量尺自己先要能量。**

## A 組：碰撞區（4 條）

`se-feasibility` / `se-discovery` / `se-design` / `se-clarify` 四個入口的 description 落在同一個語意區間，「當需求還模糊」這五個字在 `se-design` 與 `se-clarify` 裡逐字重複。這組就是為了量它們的互斥程度。

**互斥判準**（description 改寫時的目標狀態）：

```text
se-feasibility  → 還沒決定要不要做
se-discovery    → 決定要做，但講不出「做完長什麼樣」
se-design       → 講得出終點，要切成可派發的片
se-clarify      → 答案不在任何文件裡，在某個人身上
```

| # | 使用者說的話 | 該載入 | 明確不該載入 | 來源 |
|---|---|---|---|---|
| A1 | 我想做一個把 Notion 筆記自動同步到 Obsidian 的小工具，這做得出來嗎？大概要多久 | `se-feasibility` | `se-design`、`se-discovery` | `authored` |
| A2 | 我想做一個內部工具，但還講不出做完長什麼樣 | `se-discovery` | `se-design`、`se-clarify` | `authored` |
| A3 | 訂單匯出要加上多幣別支援，這個功能幫我切成幾塊，我要分批做 | `se-design` | `se-discovery` | `authored` |
| A4 | 退款要不要開放給非會員，這個決定要問 PM，幫我整理成一份給他填的東西 | `se-clarify` | `se-design`、`se-feasibility` | `authored` |

## B 組：對照（4 條）

這組測的是**本輪不會改動**的 skill。A 組改完之後 B 組若跟著變差，代表改動的副作用溢出到沒碰的地方——這是只看 A 組看不到的。

| # | 使用者說的話 | 該載入 | 明確不該載入 | 來源 |
|---|---|---|---|---|
| B1 | 匯入 CSV 的時候一直報 encoding 錯誤，幫我找原因 | `se-debug` | `se-minimal-change` | `authored` |
| B2 | 幫我在使用者註冊表單加一個手機號碼欄位 | `se-minimal-change` | `se-design`、`se-two-axis-review` | `authored` |
| B3 | 我剛改完付款流程的重試邏輯，幫我 review 一下 | `se-two-axis-review` | `se-debug`、`code-review` | `authored` |
| B4 | 我要開分支做付款重試這個功能，做完開 PR | `se-branch-lifecycle` | `se-scheduling` | `authored` |

**⚠ B 組目前不可測。** 執行器只給 `Skill` 工具（理由見下），但 B 組全是**動作型**請求——修 bug、加欄位、review、開分支。模型沒有 Read/Grep 就看不到程式碼，於是回「把檔案給我」或「這個 repo 沒有付款程式碼」，從頭到尾不需要載入 skill。8 次全部「無」。

**這不是路由失敗，是案例在這個 repo 裡無法執行。** 要測 B 組必須把 `.claude/` 複製到一個有真實程式碼、且不含本檔的暫存專案再跑。未做。


### ⚠ 來源（provenance）決定這些數字算不算數

| 值 | 意義 | 計入覆蓋率？ |
|---|---|---|
| `session-trace` | 從真實 session 的逐字紀錄取出 | ✅ |
| `user-prompt` | 使用者真的打過的句子 | ✅ |
| `authored` | 照 skill 的 description 寫出來的 | ❌ |

**`authored` 不計入覆蓋率。** 理由：用 description 寫出來的案例，交給讀同一份
description 的判官去判，**不可能失敗**——它測的是自我一致性，不是路由能力。

**目前 8 條全部是 `authored`。** 所以下面那個「A 組 4/4」是一個**自我一致性**的
觀測，不是路由能力的證據。要讓它算數，必須從真實 session 逐字紀錄回填案例。

覆蓋率下限：每個受測 skill 至少 **3 條獨立來源正例 ＋ 2 條碰撞案例**。
不足就回 `unmeasured`，不編分數。跑 `python docs/eval/run_eval.py --coverage` 查。

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

| 日期 | 版本 | A 組 | B 組 | 備註 |
|---|---|---|---|---|
| 2026-09-02 | `81fb341` v0 | 1/4 | 0/4 | **作廢**：案例不自足（「這東西」無指涉），16 次有 12 次什麼都沒載入 |
| 2026-09-02 | `81fb341` v1 | 3/4 | 1/4 | **作廢**：開放 Read/Grep 後模型 grep 到本檔的答案欄【已確認：B1 transcript】 |
| 2026-09-02 | `81fb341` **v2** | **4/4** | 不可測 | **有效 baseline**。案例自足＋只給 Skill 工具；A 組 8 次全對、零誤觸發 |

### ⚠ 這個結論已被降級（2026-09-03）

下面這段是加上 provenance 與覆蓋率下限**之前**寫的。8 條案例全部是 `authored`
（照 skill 自己的 description 寫出來的），所以 `--coverage` 現在對 10 個 skill
全部回 **unmeasured**。

**「A 組 4/4」仍然是一個真實觀測，但它量到的是自我一致性，不是路由能力。**
要讓它算數，必須從真實 session 逐字紀錄回填至少 3 條獨立來源正例 ＋ 2 條碰撞。

保留原文不刪，因為它是這個降級決定的證據來源。

### v2 的結論（已降級）：A 組沒有碰撞

`se-feasibility` / `se-discovery` / `se-design` / `se-clarify` 四個入口，在 4 條明確案例上 **8/8 正確路由，且一次都沒有載入「明確不該載入」的那些**【已確認：`runs/2026-09-02T133932-81fb341.json`】。

原本的診斷是「description 語意重疊 → 誤觸發機率高」。**語意重疊是事實（「當需求還模糊」逐字重複），但它沒有造成誤觸發。**

所以**不改這四份 description**。baseline 已經滿分，改動只有一個方向可去。要重開這個議題，得先拿出一條真的被路由錯的案例。

**限制**：這只證明「意圖明確的輸入不會走錯」。**真正模糊的輸入沒有測**——那種案例很難寫得客觀，因為連人都未必同意正確答案是什麼。

### C 組觀察紀錄

| 日期 | 案例 | 實際行為 | 備註 |
|---|---|---|---|
| — | — | — | 尚未執行 |
