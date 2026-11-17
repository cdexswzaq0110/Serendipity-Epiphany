---
id: L0006
date: 2026-11-17
outcome: useful
tags: [hooks, windows, 編碼]
anchors:
  - .claude/hooks/hooklib.py
  - scripts/sync_skills.py
supersedes:
hits: 0
---

# 繁中 Windows 上，Python hook 的輸出預設是 cp950

## 發生了什麼

v2.0.0 把 hooks 從 Bash 改成 Python。GPT 在自己的環境跑 `python -m unittest discover -s tests`：13/13 通過。Claude 在使用者的繁中 Windows（主控台 cp950）重跑：**2 個錯誤**，`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa4`。

原因：hook 是子程序，Python 寫 stdout 時用的是主控台編碼 cp950；呼叫端（測試，以及 Claude Code 本身）用 UTF-8 解讀 hook 的 JSON 輸出。訊息裡只要有中文，就變成亂碼或解碼失敗。設了 `PYTHONIOENCODING=utf-8` 時 13/13 通過——錯誤只在預設環境出現。

## 證據

- 修正前：預設環境 `FAILED (errors=2)`；`PYTHONIOENCODING=utf-8` 時 `OK`。
- 修正後（`hooklib.py` 與 `sync_skills.py` 啟動時把 stdout／stderr 重設為 UTF-8）：預設環境 `Ran 13 tests … OK`。

## 規則

- 會被其他程式讀取輸出的 Python 腳本（hooks、同步工具），啟動時一律 `sys.stdout.reconfigure(encoding="utf-8")`（stderr 也是）。
- 跨平台的驗收要在**使用者的預設主控台編碼**下跑一次，不能只在設了 UTF-8 環境變數的機器上跑——和 L0002「先證明它會擋」同一個道理：先證明它在真實環境會動。

**失效條件**：Python 預設改為 UTF-8 模式（PEP 686）且使用者的 Python 版本都已支援時，可以刪除這則。
