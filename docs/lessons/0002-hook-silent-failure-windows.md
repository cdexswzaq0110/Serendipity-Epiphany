---
id: L0002
date: 2026-08-31
outcome: useful
tags: [hooks, windows, 確定性, gate]
anchors:
  - .claude/hooks/
  - .claude/settings.json
  - .claude/ABLATION.md
supersedes:
hits: 0
---

# Gate 的預設失敗模式是「靜默放行」，所以要先證明它會擋

## 觸發情境

把一條自然語言規則機械化成 hook（或任何形式的 gate），尤其是在 Windows 上。

## 領悟

**gate 寫錯的時候不會報錯，它會放行。**

Claude Code 的 hook：路徑錯、腳本 spawn 失敗、退出碼用錯——全部都只產生 non-blocking error，動作照樣執行。【已確認：官方 hooks 文件，只有 exit 2 會 block，其他非零碼「the action proceeds」】

這跟一般程式相反。一般程式壞掉會停，gate 壞掉會**假裝在保護你**。所以 gate 的驗收條件不是「裝好了」，是**「它在該擋的時候真的擋了」**——必須有一次紅燈，才能相信它的綠燈。

Windows 上有兩個具體的坑，兩個都會讓 gate 靜默失效：

1. **exec form（帶 `args`）要求 `command` 是真正的 `.exe`。** 直接指向 `.sh` 會 spawn 失敗。【已確認：官方文件】
2. **`bash` 在 Windows PATH 上解析到 `C:\Windows\system32\bash.exe`，那是 WSL launcher，不是 Git Bash。**【已確認：2026-08-31 本機 `Get-Command bash`】WSL 沒裝就直接失敗；裝了的話腳本會在另一個檔案系統語意下跑，git 狀態未必對得上。

正確寫法是 shell form：`"shell": "bash"` ＋ `"command": "bash \"${CLAUDE_PROJECT_DIR}/.claude/hooks/x.sh\""`。此時 `bash` 由 Claude Code 選定的 Git Bash 解析（`/usr/bin/bash`），Windows 路徑當成參數傳入，正反斜線都可用。【已確認：兩種路徑形式實測 exit 0】

## 為什麼會撞到

外部提供的規劃文件把 hook 設定寫成 exec form，並在風險表把「路徑錯導致 gate 靜默失效」列為最高風險——**然後它自己的設定就是那個 bug**，因為那份規劃預設環境是 Linux/WSL。

錯的不是它不懂 hook，是**沒有人在目標平台上跑過**。一份沒跑過的設定，讀起來跟跑得起來的設定長得一模一樣。

## 下次怎麼做

1. **先寫關掉的測試**：gate 裝好後，第一件事是製造一次違規，確認 exit code 是 2。沒看過紅燈就不算裝好。
2. **腳本自己判定，不完全依賴 settings.json 的 `if`**：`guard-critical.sh` 自己 grep 指令內容，`if` 只是省一次 spawn。設定層失效時腳本仍守得住。
3. **判定要錨在指令位置**：`echo git reset --hard is dangerous` 不該被擋。用 `("command":"|&&|;|\|)git[[:space:]]+…` 錨定，比裸關鍵字少一整類誤判。【已確認：13/13 判定案例】
4. **第一版跑 warn（exit 1）**：看它擋了什麼、擋得對不對，再改 block。攔截次數本身就是那條規則的失敗證據——正好補 `ABLATION.md` 的「未登記」。

## 失效條件

- Claude Code 改變 hook 的退出碼語意，或 exec form 在 Windows 上支援 `.sh`——本則的技術細節要重驗。
- 專案改在 Linux/macOS 為主的環境開發——第 1、4 點仍成立，Windows 兩個坑不再適用。
- 若未來 hook 設定支援 schema 驗證或安裝時自測，第 1 點該被那個機制取代。
