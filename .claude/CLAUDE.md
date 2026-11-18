# 配置元件責任與維護契約

入口敘述在根目錄 [`CLAUDE.md`](../CLAUDE.md)。**改動這套配置本身時**的元件責任與 8 條維護契約在
[`rules/harness-maintenance.md`](rules/harness-maintenance.md)——讀到 `.claude/`、`docs/lessons/`、`docs/eval/`
底下的檔案時自動載入，平常寫程式不佔 context。

設計原則：**Skills 厚，Runtime 薄**——常駐面只放每次工作都成立、而且與模型預設行為不同的約束。

## Runtime Context

不把每次對話或 Subagent 摘要寫成專案內的影子文件。Claude Code 的 session／task 機制處理暫態狀態；值得長期保存的內容進入 `docs/lessons/`、ADR、模板文件或測試證據。

純過渡的交接筆記寫到 OS 暫存目錄，**不進 repo**。
