## 完成摘要

【已確認】已將 8 道 Bash hook 攍為 Python 3.11 標準庫入口：

- `guard_branch.py`
- `guard_critical.py`
- `check_router.py`
- `check_memory.py`
- `guard_discard.py`
- `guard_done.py`
- `checkpoint.py`
- `recall_lessons.py`

共用邏輯集中在 `hooklib.py`，支援：

- 指令開頭、`&&`、`;`、`|`、換行、`(`、`do/then/else`
- `git -C`、`git -c`、`--no-pager` 等全域選項
- heredoc 內文排除、未結束 heredoc、`<<<` here-string
- 一次性 `BREAK_GLASS`
- UTF-8 stdout/stderr
- 內部錯誤時，高風險操作阻擋、低風險放行
- git dubious ownership 不寫設定檔，僅以命令列 `safe.directory` 放行

【已確認】舊 hook `.sh`、`_command.sh`、`selftest.sh` 均已刪除；非 hook 的 `templates/_meta/bootstrap_check.sh` 保留。

## Router 與工具

【已確認】`check_router.py` 現在以 canonical `skills/` 為準：

- 驗證核心與 `extended/` 目錄相對 `skills/INDEX.md`
- 驗證常駐檔 `/se-*` 引用
- 使用 `sync_skills.flat_plan()` 計算 flat projection
- 比對 manifest 內容 hash 與實際安裝檔案
- 不比較 `source_commit` 等 provenance 欄位
- 保留變更範圍預篩

【已確認】工具同步完成：

- `capabilities.py` 可辨識 Python hook，並讀取 `DEFAULT_MODE`
- `promote_skill.py` 寫入 `skills/extended/<name>` 與 canonical INDEX
- promotion 先在暫存區 build/validate，再 flat install
- 失敗會回滾 canonical 變更
- 相關現行文件已更新為 Python hook 名稱
- ABLATION 歷史日誌維持原來的 Bash 名稱，僅新增 2026-11-18 量測列

## 驗收結果

【已確認】完整測試：

```text
..........................................................................................................................................................
----------------------------------------------------------------------
Ran 154 tests in 5.474s

OK
```

【已確認】`tests/SELFTEST_MAP.md`：

```text
selftest-map: 135/135 OK
```

【已確認】每個映射指向可被 unittest discovery 找到的測試名稱。

【已確認】真實 repo 假 payload：

```text
check_router exit=0
check_memory exit=0
```

【已確認】評測工具：

```text
python docs/eval/run_eval.py --list
共 14 條
```

```text
python docs/eval/run_eval.py --parse-only <測試 transcript>
skills: [] | not-logged-in: False
派發分組: （無） → 序列／無派發
單則訊息最大工具批次: 0
```

【已確認】其他檢查：

- 設定檔除 command 外，事件、matcher、`if`、timeout、async、statusMessage 與 HEAD 相同
- `capabilities.py --json`：exit 0
- `git diff --check`：exit 0
- 未 commit、未切換分支、未修改 git 設定

## 環境變數相容表

| 名稱 | 預設值 | 事件 | 作用 | 測試 |
|---|---:|---|---|---|
| `SE_GUARD_BRANCH_MODE` | `warn` | PreToolUse | 分支 gate exit 1/2 | `test_branch_rejection_really_blocks` |
| `SE_GUARD_CRITICAL_MODE` | `block` | PreToolUse | 破壞性 git gate | `test_destructive_git_requires_backup_tag` |
| `SE_CHECK_ROUTER_MODE` | `block` | PreToolUse | Router/canonical gate | `test_selftest_028`–`043` |
| `SE_CHECK_MEMORY_MODE` | `block` | PreToolUse | lessons 准入 gate | `test_selftest_044`–`054` |
| `SE_GUARD_DONE_MODE` | `block` | Stop | 結束前自檢，只擋一次 | `test_selftest_055`–`058` |
| `SE_LEARN_NUDGE` | `on` | Stop | 學習訊號提醒 | `test_selftest_119`–`125` |
| `SE_ALLOW_DISCARD` | 未設定 | PreToolUse | 經同意後允許丟棄 | `test_selftest_126`–`135` |
| `SE_EVAL` | 未設定 | SessionStart/Stop | 評測時抑制召回與提醒 | `test_selftest_061`、`121` |
| `CLAUDE_PROJECT_DIR` | cwd | 全部 | 專案根目錄 | hook integration tests |
| `CLAUDE_PID` | 未設定 | checkpoint | session 程序身分 | checkpoint 映射測試 |
| `SERENDIPITY_HOME` | `~/.claude/serendipity` | recall | 跨專案帳本位置 | recall 映射測試 |

## Windows 延遲量測

【已確認】方法：同一台 Windows 主機，依序執行一次 Bash 工具呼叫會觸發的 5 道 PreToolUse hook；相同 payload，各跑 20 次取中位數，包含程序啟動成本。

| 情境 | Bash | Python |
|---|---:|---:|
| 一般非 git 指令 | 130.70 ms | 466.84 ms |
| `git commit` | 137.35 ms | 571.64 ms |
| `rm` 開頭 | 130.19 ms | 607.41 ms |

【已確認】數字已加入 `.claude/ABLATION.md` 的 2026-11-18 日誌列。

【已確認】Python 版本在這台 Windows 上明顯較慢；這是目前剩餘的主要效能風險。

## Git 狀態

【已確認】主要修改：

- 修改：設定、ABLATION、hook 共用層、工具、相關規則與 README
- 新增：5 個原先不存在的 Python hook、command parser 測試、135 項映射與測試入口
- 刪除：9 個 hook Bash 輔助／入口及 `selftest.sh`
- 未 commit
- 未執行 push、reset、rebase 或其他破壞性 Git 操作

完整清單已由 `git status --short` 驗證，共包含上述 `.claude/hooks/`、工具、文件與 `tests/` 變更。