# Serendipity 2.1.0 整合：最終方案（採納 GPT 紅隊後）

前一版是 [01-plan](01-plan.md)，GPT 紅隊見 [02-gpt-redteam](02-gpt-redteam.md)。下面只寫修改後的決策與每條紅隊意見的處置。

## 已完成

| commit | 內容 | 證據 |
|---|---|---|
| `3233f57` | `sync_skills.py install --layout flat`；被取代清單改放 manifest 層的 `skills/extended/superseded.json`，不用 frontmatter；核心 `se-debug`、`se-minimal-implementation`、`se-work-order` 移植 main 的改進 | unittest 16/16 |
| `6dfc5a9` | merge `origin/main`。hooks 暫用 main 的 Bash 版；常駐面用 main 的；skill 三方合併進 canonical；`.claude/skills` 改為 flat（26 個）；INDEX 合併；L0006 改號為 L0015；版本 2.1.0。`superseded.json` 暫時為空 | `selftest.sh` 135/135、check-router 與 check-memory 對本樹都是 0、unittest 16/16 |

## 紅隊意見的處置

| # | 處置 |
|---|---|
| 1、2 | 已做：`--layout flat`；同名時以核心為準並記錄在 manifest 的 `skipped`；被取代清單在 `superseded.json`，必須指向核心 skill，否則 build 失敗；有 round-trip 與竄改測試 |
| 3 | 已做：`se-acquire`、`se-resume` 與 references 放進 canonical。router、guard-done、promote_skill 改讀 canonical，見 B |
| 4、7 | B：135 條 selftest 斷言每一條都要有 Python 測試 ID 與對照表；移植期間兩套並跑，全部對齊後才刪 Bash |
| 5 | 已採用：合併 commit 先用 main 的 Bash 版本並跑 selftest，下一個 commit 才換成 Python |
| 6 | 已處理：main 對 v1 `se-debug` 的修改，用 base／up 三方合併進 `skills/extended/se-debug`（v1）；「補訊號」另外以改寫的方式放進核心 `se-debug` |
| 8 | 合併時已抓到：check-router 擋下 `core-rules.md` 指向被取代的 skill。C 的引用盤點用機械化方式全 repo 搜尋 |
| 9 | 採用：每道 gate 保留獨立的入口，共用 `hooklib`；checkpoint 照樣非同步，並與阻擋型 gate 分開 |
| 10 | 採用：B 要交出環境變數相容表 |
| 11 | 採用：`trigger-cases.md`、`run_eval.py`、`SE_EVAL` 視為一組。只跑 `--list`／`--parse-only`；要花額度的評測由使用者決定 |
| 12 | 採用：promote 在暫存區 build、validate 之後才替換，失敗就回滾，並有失敗注入測試 |
| 13、14 | 合併時已保留：`.gitignore` 的 `__pycache__/`、`*.pyc`；`dispatch.md` 用 main 的版本（自動合併，2.0.0 沒有改這個檔） |

## 修正後的決策：被取代的 v1 內容「搬進」核心，不丟掉

v1 的 `se-minimal-change`（131 行）與 `se-two-axis-review`（137 行，另有 `references/smell-baseline.md`）有核心版本沒有的方法：五件不得省略的事、`DEBT:` 標記、過度工程審查、接縫的判準、雙軸隔離審查的各個階段、finding 格式、「finding 是主張不是命令」。agents 也預載了它們：`process-worker` 預載 `se-minimal-change`，兩個 reviewer 預載 `se-two-axis-review`。

**做法（C1，Claude）**

- 把 v1 獨有的段落原文搬到對應核心 skill 的 `references/`，例如：
  - `se-minimal-implementation/references/v1-minimal-change.md`
  - `se-spec-review/references/` 與 `se-quality-review/references/`：雙軸流程、finding 格式、`smell-baseline.md`
- 核心 `SKILL.md` 本體維持在 Agora 注入上限（4,000 字）之內，只加上「需要完整做法時讀 references」的指標。
- agents 的預載與引用、`core-rules.md`、`WORKFLOW.md`、`USAGE.md`、`DESIGN_RATIONALE.md`、ABLATION 的仲裁表改成指向核心名稱。
- `superseded.json` 這時才列入 `se-minimal-change`、`se-two-axis-review`。v1 的 `se-debug`、`se-feasibility` 與核心同名，所以本來就以核心為準；它們獨有的段落一樣搬進核心的 references。
- 歷史紀錄不改寫：lessons、ABLATION 的日誌列、`docs/eval/runs` 保留當時的名稱。

## B：hooks 改寫成 Python（GPT，在獨立 worktree）

GPT 的實作報告見 [04-gpt-hooks-result](04-gpt-hooks-result.md)。驗收條件：

- 135 條斷言都有對應測試並且通過；
- 2.0.0 漏判的案例（D3）通過；
- 環境變數相容表；
- 量測每次 Bash 呼叫的 hook 額外延遲（main 的 Bash 版 vs Python 版）；
- 文件裡 hook 的名稱與指令更新完畢。

## E：下游（Claude，B 與 C 都合入之後）

在乾淨的 commit 上 `build` 2.1.0 bundle，再同步到：

- Agora `harness/se/`：cargo test，commit 到 main 並推送；
- SE-Codex `.agents/skills/`：`se.py test`，推送到 `feat/se-v2-skills`。

最後 `feat/skills-bundle` 快轉到 `integrate/2.1` 並推送，PR #16 就可以合併。

## 未驗證（會寫進 PR）

- Claude Code 是否真的看不到巢狀的 `extended/`：flat 版面不論答案都正確，所以不另外花額度實測。
- 核心 skill 的 description 在 Claude Code 的觸發率（維護契約 #8）：要跑多次 `claude -p`，由使用者決定。
