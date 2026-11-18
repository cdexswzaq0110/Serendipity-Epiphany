# Serendipity 2.1.0：把 2.0.0（feat/skills-bundle）與 main 的 PR #6–#15 整合

## 背景

- `feat/skills-bundle`（2.0.0，3 個 commit：`2a39a33`、`91f76d6`、`49163ca`）是從 `9db0475`（PR #5）開的，因為本機 clone 落後。
- `origin/main`（`d13bacf`）在那之後多了 26 個 commit（PR #6–#15，2026-09-05～09-24），大多有端到端基準或消融證據：
  - 記憶層准入（`check-memory`）
  - 通用能力：`capabilities.py`、`se-acquire`、`skill-candidates/`、`promote_skill.py`、`mine.py`
  - commit 閘自己判定指令（`_command.sh`，lesson 0009）
  - 斷點續跑：`checkpoint.py`、`checkpoint.sh`、`se-resume`
  - 學習訊號：`guard-done`、`recall-lessons`
  - 端到端基準（`docs/eval/bench`）
  - context 瘦身：維護契約改到 `rules/harness-maintenance.md`，用 `paths:` 按路徑載入
  - 丟棄保護（`guard-discard`，lesson 0014）
  - 拿掉有害規則（`473d4cc`：在 main 上自己開分支，不停下來問）
- 試合併：17 個衝突檔。另外 main 對舊 skill 的修改，被 rename detection 套到 `.claude/skills/extended/<name>`；但 2.0.0 的 canonical 來源是 `skills/extended/<name>`，那裡沒收到。
- 審查材料：兩個樹的完整副本 `up/`（`origin/main`）與 `base/`（`9db0475`），以及 `feat/skills-bundle` 的工作樹。

## 原則

1. **main 有證據的行為一律保留**：每一道 hook、每一個模式與環境變數、每一則 lesson、每個工具、每一行有消融證據的常駐規則。2.0.0 只帶入「結構」：canonical `skills/`、同步工具、Python hooks、9 個核心 skill。
2. **常駐面以 main 為準**（維護契約 #6：新增常駐內容要有失敗證據）。2.0.0 新增、但沒有證據的常駐句子退回 skill；2.0.0 改回的有害規則（main、有未提交變更、沒指定分支時「先停下確認」）撤銷。
3. **用 merge，不 rebase**：分支已推送，PR #16 已開。合併 commit 必須是可運作的狀態，之後的 commit 逐步轉換。
4. 2.0.0 的核心 skill 取代了 v1 的哪些 skill，main 在這段期間對那些 v1 skill 的改進都要移植進核心版本，不能隨 v1 一起被藏起來。

## 發現的 2.0.0 缺陷（這次一起修）

- **D1：延伸 skill 在 Claude Code 裡可能看不到。**
  - 2.0.0 把它們裝在 `.claude/skills/extended/<name>/SKILL.md`。
  - 官方文件只寫了 `.claude/skills/<skill-name>/SKILL.md` 一層，沒有說會遞迴。【候選：文件推論，未實測】
  - 受影響的是 `se-epiphany`、`se-branch-lifecycle`、`se-scheduling` 等；main 的 hooks 會點名叫用 `se-epiphany`、`se-acquire`、`se-resume`。
- **D2：常駐面改回了有害規則。** 根目錄 `CLAUDE.md` 第 1 條要求「在 main、有未提交變更或沒指定分支時先停下確認」，正好是 `473d4cc` 用基準證明有害、已經拿掉的規則。
- **D3：Python hook 的指令判定比 main 弱。**
  - `\bgit\s+commit\b` 會被 `echo git commit`、heredoc 內文誤判；認不得 `git -C dir commit`。
  - 破壞性判定要求 git 前面是行首或 `;&|`，所以漏掉 `( git …`、換行、`do git …`、`git -C x reset --hard`。
  - main 的 `_command.sh` 與 selftest 已經處理過這些情況（lesson 0009）。
- **D4：`guard_branch` 在 2.0.0 是 block；main 是 warn（`SE_GUARD_BRANCH_MODE`）。** main 刻意先跑 warn 累積證據。
- **D5：2.0.0 的 router gate 只掃 INDEX。** 沒有檢查常駐檔裡的 `/se-xxx` 斷鏈，也沒有「這次沒動到路由檔就跳過」的省時判斷（main 量過，Windows 上每次省 1 秒以上）。

## 決策

### A. Skill 結構

- **A1：canonical 來源維持 `skills/`。**
  - `skills/<core>` 是 9 個核心 skill。
  - `skills/extended/<name>` 是其他所有 skill，包含 main 新增的 `se-acquire`、`se-resume`。
  - main 對 v1 skill 的修改，從合併後的 `.claude/skills/extended/<name>` 搬回 `skills/extended/<name>`：
    - `se-epiphany`（加上 `references/promotion-gates.md`、`purge.md`）
    - `se-scheduling`（加上 `references/verification-surfaces.md`）
    - `se-branch-lifecycle`、`se-minimal-change`、`se-debug`
  - 搬之前先比對：2.0.0 對這些檔只改過路徑（R095–R099）。
- **A2：「被取代」的 v1 skill 不再安裝到 Claude Code。**
  - 名單：`se-feasibility`（v1）、`se-debug`（v1）、`se-minimal-change`、`se-two-axis-review`。
  - 它們留在 `skills/extended/`，在 INDEX 標示被誰取代。
  - 其餘延伸 skill 照常安裝，因為它們有核心 skill 沒涵蓋的用途：`se-design`、`se-discovery`、`se-clarify`、`se-sdlc`、`se-system-design`（特例領域）等。
- **A3：`sync_skills.py install` 增加 `--layout flat`。**
  - 規則和 SE-Codex 相同：核心優先，延伸只加不同名、而且沒被標為被取代的 skill。
  - 給 Claude Code 用的 `.claude/skills/` 改用 flat：每個 skill 都在第一層。
  - 預設的 `bundle` 版面不變（Agora 的 `harness/se/` 讀巢狀版面）。
  - 被取代的標記放在 `skills/extended/<name>/SKILL.md` 的 frontmatter（`superseded-by: se-xxx`）。
    - 待確認：Claude Code 遇到未知的 frontmatter 鍵會不會出錯。若有疑慮，改放在 bundle manifest 或 INDEX 的機器可讀區塊。
- **A4：把 main 的改進移植進核心 skill。**
  - `se-debug`（核心）：加入「補訊號：只讀不改的一段」，含三行產出格式、與 `thread-scout` 的分工。
  - `se-minimal-implementation`：加入「第 0 階：這件事需要模型嗎」。核心版已經有階梯。
  - `se-work-order`：加入「不熟這個 codebase 就先派唯讀 scout 回報慣例，再寫驗收條件」，以及「意圖不清時不在這裡解決」的界線。
  - 核心 skill 裡任何「先停下來問分支」的句子，改成 main 的版本。
- **A5：INDEX 合併。**
  - 以 main 的「情境路由」表為骨架（含「別選錯」欄），並把指向被取代 skill 的列改成核心名稱。
  - 新增「核心 9 個（Agora／Codex 共用、Agora 確定性注入）」區塊，與「被取代的 v1（不安裝；需要完整舊流程時看 `skills/extended/<name>`）」區塊。
  - 新增「別選錯」的區辨：
    - `se-problem-definition` vs `se-design`／`se-discovery`／`se-clarify`
    - `se-technical-design` vs `se-system-design`
    - `se-product-contract` vs `se-sdlc`
- **A6：版本號 `bundle_version` 改為 2.1.0**，CHANGELOG 補遷移說明。

### B. Hooks（全部改為 Python；行為與 main 等價）

- **B1：移植 `_command.sh` 的判定到 `hooklib`。**
  - 用法：`is_git_cmd(command, subcommand_regex)`。
  - 規則：
    - 指令位置：開頭、`&&`、`;`、`|`、換行、`(`、`do`／`then`／`else` 之後；
    - git 的全域選項：`-C <dir>`、`-c k=v`、`--no-pager`；
    - heredoc 內文去除；`<<<` 不算 heredoc；沒結束的 heredoc 後面全部視為內文。
  - Python 拿到的是 JSON 解開後的真實換行，所以不需要處理字面的 `\n`。
- **B2：每一道 hook 一對一移植，模式、環境變數、訊息語意都不變。**

| main | Python | 模式（環境變數） |
|---|---|---|
| guard-branch | branch gate | warn（`SE_GUARD_BRANCH_MODE`，block 改為選用）；Bash 只在真的 git commit 時判定 |
| guard-critical | critical gate | block（`SE_GUARD_CRITICAL_MODE`）；判定不了就擋；backup tag 必須指向 HEAD；給建議的 tag 名稱 |
| check-router | router gate | block（`SE_CHECK_ROUTER_MODE`）；三向檢查改在 canonical `skills/`（核心＋延伸）上做；常駐檔的 `/se-xxx` 斷鏈；沒動到路由檔就跳過；另外檢查 `.claude/skills` 與 manifest 一致（等同 `sync_skills.py check`） |
| check-memory | memory gate | block（`SE_CHECK_MEMORY_MODE`）；source、promoted、validated、INDEX 雙向；沒動到 `docs/lessons/` 就跳過 |
| guard-discard | discard gate | 先用 Python 預篩，命中才呼叫 `checkpoint.py discard-check`（可 import 或子程序）；`SE_ALLOW_DISCARD=1` 放行 |
| guard-done | Stop | 只擋一次（`stop_hook_active`）；跑 router 與 memory；學習訊號只認 `checkpoint.py learned` 的 exit 3；`SE_EVAL` 與 `SE_LEARN_NUDGE=off` 時不問 |
| checkpoint | 記錄器 | 任何失敗都 exit 0；錯誤寫進 `.git/serendipity/error.log` |
| recall-lessons | SessionStart | 只印指標；`SE_EVAL` 時不注入；最多 10 則 |

- **B3：保留 2.0.0 的錯誤政策**：一次性 `BREAK_GLASS`；hook 內部錯誤時只擋高風險操作（`raw_high_risk`），其他放行並印出修法。強制 UTF-8 輸出。
- **B4：減少直譯器啟動次數。**
  - 每個事件只啟動一個 Python 行程，例如 `pretool.py` 依 tool_name 跑該跑的 gate；每個 gate 各自 try，一個出錯不影響其他。
  - checkpoint 的非同步事件照 main 的註冊方式。
  - `if` 預篩可以保留，但只能當作省時的手段，不能拿來決定擋不擋。
  - 量測：在這台 Windows 上比較 Bash 一次呼叫的 hook 額外延遲，main 與移植版各量一次，結果寫進 ABLATION。
- **B5：測試。**
  - 把 `selftest.sh` 的每一個案例改寫成 `tests/test_hooks.py`（unittest，暫存 git repo），案例數不減。
  - 另外加上 D3 列出的 2.0.0 漏判案例。
  - `selftest.sh` 刪除；文件裡的用法改為 `python -m unittest`。
- **B6：設定檔。**
  - `.claude/settings.json`（`CLAUDE_PROJECT_DIR`）與 `.claude/hooks/hooks.json`（plugin，`CLAUDE_PLUGIN_ROOT`）都要註冊 main 的全部事件：PreToolUse、Stop、SessionStart、PostToolUse、PostToolUseFailure、StopFailure、UserPromptSubmit，指向 Python。
  - `python` 不存在時的說明沿用 2.0.0 README。

### C. 工具

- `capabilities.py`：hook 偵測同時認得 `.py`；skill 偵測讀 flat 的 `.claude/skills/*/SKILL.md`。flat 之後原本的 glob 就正確，另外標示核心或延伸。
- `promote_skill.py`：升級時寫入 canonical `skills/extended/<name>` 與 `skills/INDEX.md`，然後執行 `sync_skills.py build` 與 `install --layout flat`。不再直接寫 `.claude/skills/`。
- `checkpoint.py`、`lessons.py`、`mine.py`：不動。
- `docs/eval/bench/bench.py`、`run_eval.py`：只修路徑與 hook 名稱。

### D. 常駐面與文件

- **根目錄 `CLAUDE.md`**：用 main 的版本。只改兩處：
  - 路由表的 skill 索引連結改為 `skills/INDEX.md`，並加一行「`.claude/skills/` 是同步產物」；
  - 第 2 條的 skill 名稱改為 `se-minimal-implementation`。
  - 2.0.0 新增的第 4 條（驗證碰到交付物）與第 5 條（backup tag）不常駐：第 5 條已有 hook 與 `git-workflow.md`，第 4 條在核心 skill 裡。
- **`.claude/CLAUDE.md`**：用 main 的精簡版。
- **`rules/harness-maintenance.md`**：
  - 用 main 的版本，hook 名稱改為 Python；
  - 契約 1 寫明 canonical 是 `skills/`、`.claude/skills` 由同步產生；
  - 加一條「改 skill 只改 `skills/`，然後 build／install／check」。
- **`rules/git-workflow.md`**：用 main 的版本，只改 hook 名稱。
- **`ABLATION.md`**：
  - 用 main 的版本；hook 表改為 Python 名稱；
  - 日誌加一列 2026-11-18（2.1.0：哪些變了、哪些沒變、B4 的量測）；
  - 常駐行數重新計算。
- **`AGENTS.md`、`README.md`、`docs/USAGE.md`、`DESIGN_RATIONALE.md`、`RUNBOOK.md`、`EXECUTION_MODEL.md`**：
  - 逐段合併，main 的內容優先；
  - 2.0.0 帶入的段落只有：同步工具的用法、Python hooks 的說明、核心與延伸的區分。
- **Lessons**：
  - 2.0.0 的 L0006（cp950）改號為 **L0015**（檔名 `0015-…`），補上 `source: self-observed`；
  - INDEX 取兩邊聯集；
  - 所有提到「L0006（cp950）」的地方改為 L0015：hooklib 註解、CHANGELOG、Agora 的開發日誌。
- **`.out-of-scope/`**：沿用 main 的。

### E. 下游

1. SE 做 `build`，產生 2.1.0 的 bundle。
2. Agora：`install --dest harness/se`（bundle 版面）→ `cargo test` → commit 到 main → 推送。是否發 v0.6.1 另外詢問。
3. SE-Codex：`install … --dest .agents/skills` → `python se.py test` → commit 到 `feat/se-v2-skills`，PR #1 會跟著更新。

## 分工與順序

1. **Claude**：在 `feat/skills-bundle` 做 `git merge origin/main`。
   - 衝突的 hooks 先保留 main 的 Bash 版，settings 也指向 Bash，讓合併 commit 可以運作。
   - 其他衝突依 A、D 解決。
   - 跑 main 的 `bash .claude/hooks/selftest.sh` 與 2.0.0 的 unittest，然後 commit。
2. **GPT**：在新的 worktree 做 B 與 C。
   - 驗收條件：`selftest.sh` 的每一個案例都有對應的 unittest 而且通過；D3 的案例通過；B4 的量測寫好。
   - Claude 審查後合入分支。
3. **Claude**：做 A2–A6 的同步版面與 skill 移植、E 的下游，最後推送。
4. 最後驗收：
   - `python -m unittest discover -s tests`
   - `sync_skills.py check --dest .claude/skills`
   - Agora 156 個測試、SE-Codex 92 個測試
   - PR #16 可以合併（`mergeable`）

## 未驗證（會寫進 PR）

- D1 的實際行為：可以用一次 `claude -p` 確認，會花使用者的額度。
- 維護契約 #8 的觸發測試（`docs/eval/trigger-cases.md`）：核心 skill 的 description 從來沒在 Claude Code 測過觸發。要跑多次 `claude -p`，所以列給使用者決定。
