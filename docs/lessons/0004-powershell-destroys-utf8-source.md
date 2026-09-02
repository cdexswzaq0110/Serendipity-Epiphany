---
id: L0004
date: 2026-09-03
outcome: useful
tags: [windows, powershell, 編碼, 工具選擇]
anchors:
  - .claude/rules/git-workflow.md
supersedes:
hits: 0
---

# 不要用 PowerShell 讀寫原始碼檔案——它會不可逆地毀掉非 ASCII 內容

## 觸發情境

在 Windows 上要對一個含中文（或任何非 ASCII）的原始碼檔做一行小修改，
手邊剛好在用 PowerShell。

## 領悟

**這一行會毀檔：**

```powershell
(Get-Content file.py -Raw) -replace 'old', 'new' | Set-Content -Encoding utf8 file.py
```

實際發生的三件事：

1. `Get-Content` 用系統 ANSI 代碼頁（本機是 cp950）解讀 UTF-8 位元組 → 中文變 mojibake
2. `Set-Content -Encoding utf8` 把 mojibake 再編碼一次 → **雙重編碼**
3. 順便加上 BOM，並在某一處吃掉一個換行 → Python 直接 `IndentationError`

**而且不可逆。** 我試過 cp950／big5／mbcs／cp437／cp1252／latin1 六種反向解碼，
全部失敗——字元已經被替換成私用區碼位（U+F387 之類），原始位元組沒有留下來。
那個檔案只能重寫。

## 為什麼會撞到

因為 PowerShell 在這個 harness 裡是 primary shell，改一行字的時候順手就用了。
而它「看起來成功了」——沒有錯誤、沒有警告，檔案還在，大小也正常。
下一次執行才炸，而且錯誤訊息（`IndentationError`）完全指不到真正的原因。

**這跟 L0002 是同一種失敗模式**：預設失敗行為是靜默，錯誤要等到很後面才浮出來，
而且浮出來的形狀跟成因無關。

## 下次怎麼做

**改原始碼檔一律用 Edit／Write 工具，或 Bash（`sed -i`、heredoc ＋ python）。**
PowerShell 只用於它真正擅長的事：`Get-Command`、服務查詢、Windows 專有的 API。

三條具體判準：

1. 檔案含非 ASCII → **絕不**用 PowerShell 讀寫它的內容。
2. 需要在 PowerShell 裡處理文字 → 明確指定 `-Encoding utf8` **在讀的那一端**
   （`Get-Content -Encoding utf8`），不是只在寫的那端。光指定寫入端是最常見的錯法。
3. **動任何檔案之前先確認它在版控裡。** 這次之所以要重寫，是因為那個新專案還沒
   `git init`。`git checkout -- file` 只要三秒。

## 失效條件

- PowerShell 7+ 預設 UTF-8（`$PSDefaultParameterValues` 或 `-Encoding` 預設值改變）之後，
  第 1、2 點的具體機制要重驗；第 3 點永遠成立。
- 若本機系統代碼頁改為 UTF-8（Windows 的 Beta: Use Unicode UTF-8 選項），
  第 1 點的 mojibake 不再發生——但那是機器設定，不是可攜的假設。
