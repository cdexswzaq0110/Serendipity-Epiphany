# 領悟帳本索引

**一則一行。內容留在各自的檔案裡。**

這份索引每次召回都會被讀，長度就是成本。維護方式見 [`.claude/skills/se-epiphany`](../../.claude/skills/se-epiphany/SKILL.md)。

## 現行

| ID | 一句話 | tags | outcome | hits |
|---|---|---|---|---|
| [L0001](0001-ablation-first-run.md) | 常駐規則只會單向長大，要有機制才刪得掉 | ablation, rules, prompt | useful | 0 |
| [L0002](0002-hook-silent-failure-windows.md) | Gate 的預設失敗模式是靜默放行，要先證明它會擋 | hooks, windows, gate | useful | 0 |
| [L0003](0003-eval-harness-pitfalls.md) | 量尺自己要先被量：第一個數字通常在量工具 | eval, 量測, 方法論 | useful | 0 |
| [L0004](0004-powershell-destroys-utf8-source.md) | 不要用 PowerShell 讀寫原始碼——會不可逆毀掉非 ASCII | windows, 編碼, 工具選擇 | useful | 0 |
| [L0005](0005-your-checker-is-the-first-suspect.md) | 系統說壞了的時候，第一個嫌疑犯是你的判定條件 | 量測, 判定, 除錯 | useful | 0 |

## 已升級（`outcome: promoted`）

| ID | 升級到哪 | 日期 |
|---|---|---|
| — | — | — |

## 已封存

移到 `archive/`，被 `supersedes` 取代或已失效的。

| ID | 原因 | 取代者 |
|---|---|---|
| — | — | — |

---

## 統計

- 現行：5 則
- 距離下次回顧：15 則（滿 20 則觸發）
- `no-trigger`（沒填失效條件）：0 則
