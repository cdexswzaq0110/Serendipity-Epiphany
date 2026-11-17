# Changelog

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
