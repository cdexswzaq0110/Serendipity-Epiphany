# Changelog

## 2.1.0 — 2026-11-18

把 2.0.0 與 main 的 PR #6–#15 整合。2.0.0 是從 PR #5 開出來的（本機 clone 落後），沒有包含之後 26 個 commit；這一版保留 main 的全部行為，2.0.0 只帶入結構。設計、GPT 紅隊與最終方案在 [`docs/design/2026-11-18-v2.1-integration/`](docs/design/2026-11-18-v2.1-integration/)。

- **main 的行為全部保留**：記憶層准入、通用能力（`capabilities.py`、`se-acquire`、候選 skill 升級閘、`mine.py`）、斷點續跑（`checkpoint.py`、`se-resume`）、學習訊號、端到端基準、按路徑載入的維護契約、丟棄保護，以及 8 道 hook 的模式與環境變數。
- **撤銷 2.0.0 改回的有害規則**：常駐面不再要求「在 main 上先停下來問」。`473d4cc` 已用端到端基準證明這條規則有害，現在改回 main 的「自己開分支、不必問」。
- **Claude Code 用 flat 版面**：`install --layout flat` 讓每個 skill 都在 `.claude/skills/<name>/`。2.0.0 把延伸 skill 裝在 `.claude/skills/extended/` 底下，Claude Code 可能找不到。預設的 `bundle` 版面不變，Agora 照樣使用。
- **被核心取代的 v1 併進核心**：`se-minimal-change`、`se-two-axis-review`，以及 v1 的 `se-debug`、`se-feasibility`，完整內文原樣搬進對應核心 skill 的 `references/`，agents 的預載與所有引用改為核心名稱；退役名稱列在 `skills/extended/superseded.json`。
- **main 對 v1 skill 的改進移植進核心**：
  - `se-debug` 加入補外部訊號；
  - `se-minimal-implementation` 加入「先問需不需要模型」與「在 main 上自己開分支」；
  - `se-work-order` 加入「不熟程式庫先唯讀查慣例」，以及「驗證要碰到交付物」。
- **hooks 改寫成 Python**：每道 gate 保留獨立入口，模式、環境變數、退出碼與 main 相同。main 的 `selftest.sh` 原樣搬到 `tests/hooks_selftest.sh`，改成呼叫 Python 版，再加 4 條 canonical router 案例，共 139/139；它在改寫過程中抓到 3 個真 bug。一般 Bash 呼叫的 hook 延遲：Python 75 ms，main 的 Bash 版 89 ms。被帶進其他專案時，router 與 promote 照舊檢查、寫入 `.claude/skills`。GPT 交出的版本與審查發現見設計文件 04、05。
- 延伸 skill 新增 `se-acquire`、`se-resume`；`se-epiphany` 採用 main 那份經過觸發量測的 description。
- Lesson：2.0.0 的 L0006（cp950）改號為 **L0015**；新增 **L0016**（開分支要從遠端的預設分支開——2.0.0 就是從落後的本機 clone 開的）。
- 未驗證：核心 skill 的 description 在 Claude Code 的觸發率（維護契約 #8，`docs/eval/trigger-cases.md` B1–B3 已改用新名稱，但還沒重跑）。

## 2.0.0 — 2026-11-17

- 建立 `skills/` canonical Agent Skills bundle：9 個核心 skill 與選用 extended tier。
- 新增可重現的 `build`／`install`／`check` 同步工具與正規化 SHA-256 manifest。
- `.claude/skills/` 改為安裝產物，不再手工維護。
- hooks 由 Bash 改為跨平台 Python；正常拒絕 fail-closed，內部錯誤只阻擋高風險操作，並提供一次性 break-glass。
- 精簡 `CLAUDE.md`、`AGENTS.md` 與 README；Lesson 改為有跨輪重用價值才寫。

### Skill 遷移

| 舊名稱 | 2.0 核心名稱 |
|---|---|
| `se-discovery`、`se-clarify`、`se-design`（問題定義） | `se-problem-definition` |
| `se-feasibility` | `se-feasibility` |
| `se-sdlc`（需求） | `se-product-contract` |
| `se-system-design` | `se-technical-design` |
| 無 | `se-work-order` |
| `se-minimal-change` | `se-minimal-implementation` |
| `se-two-axis-review`（規格軸） | `se-spec-review` |
| `se-two-axis-review`（工程軸） | `se-quality-review` |
| `se-debug` | `se-debug` |

舊版完整內容保留在 `skills/extended/`，供需要完整流程時選用。
