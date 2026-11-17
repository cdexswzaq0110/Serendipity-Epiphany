# Skills 索引

`skills/` 是唯一 canonical source；`.claude/skills/` 由 `scripts/sync_skills.py` 產生，不直接手改。

| Tier | Skill | 何時使用 |
|---|---|---|
| core | `se-problem-definition` | 收斂問題、使用者、範圍、成功指標與假設 |
| core | `se-feasibility` | 投入前評估技術、資料、AI、成本、風險與安全 |
| core | `se-product-contract` | 建立使用者故事、UX 流程、可檢查 AC 與非功能需求 |
| core | `se-technical-design` | 設計架構、元件、API、資料模型、取捨與回滾 |
| core | `se-work-order` | 產生含穩定 AC ID、驗證、範圍與相依的工作單 |
| core | `se-minimal-implementation` | 依工作單做最小可運作實作並取得新驗證證據 |
| core | `se-spec-review` | 對 AC 逐條做 pass／fail／cannot_verify 規格審查 |
| core | `se-quality-review` | 規格通過後做有嚴重度、位置與理由的品質審查 |
| core | `se-debug` | 用重現、假設、單一變因與回歸驗證定位問題 |
| extended | `se-bootstrap` | 把 harness 帶入新專案 |
| extended | `se-branch-lifecycle` | 管理分支、worktree、commit、push 與 PR |
| extended | `se-clarify` | 深入訪談、假設施壓或建立問卷 |
| extended | `se-context-language` | 建立與維護專案共享語言 |
| extended | `se-debug` | 保留 v1 完整除錯流程，核心版本為預設 |
| extended | `se-design` | 從探索、接縫到垂直切片的完整設計流程 |
| extended | `se-discovery` | 為巨大且未知的問題建立決策地圖 |
| extended | `se-epiphany` | 召回或記錄可跨輪重用的領悟 |
| extended | `se-feasibility` | 保留 v1 完整可行性報告流程，核心版本為預設 |
| extended | `se-focus` | 壓縮輸出並維持多步驟工作的方向 |
| extended | `se-minimal-change` | 保留 v1 最小實作階梯，核心版本為預設 |
| extended | `se-ml-lifecycle` | 機器學習端到端生命週期 |
| extended | `se-preflight` | 探測外部 CLI、MCP、API 與環境能力 |
| extended | `se-scheduling` | 任務分解、派發、鎖與平行協調 |
| extended | `se-sdlc` | 十角色完整 SDLC 流程 |
| extended | `se-skill-authoring` | 新增或修改 Agent skill 與提示文件 |
| extended | `se-system-design` | 保留 v1 九階段系統設計，核心版本為預設 |
| extended | `se-two-axis-review` | 保留 v1 雙軸審查，核心拆成兩個獨立 skill |
