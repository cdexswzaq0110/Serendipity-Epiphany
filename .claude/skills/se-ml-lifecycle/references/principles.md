# 判斷原則、Metric 選擇與常見錯誤

卡住、要做選擇、或想確認自己有沒有走偏時讀這一份。

---

### Metric 選擇

| 任務 | 常用 | 提醒 |
|---|---|---|
| Regression | MAE、RMSE、RMSLE、MAPE、R² | RMSE 重罰大誤差；MAPE 對 0 不穩；RMSLE 重視相對誤差 |
| Binary | ROC-AUC、PR-AUC、log loss、F1 | 極度不平衡優先 PR-AUC；**閾值另依成本選** |
| 機率 | Log loss、Brier、ECE | ranking 好不代表機率校準好 |
| 營運 | latency、throughput、coverage、人工複核率 | 離線分數只是產品指標的一部分 |


---

## 十二條判斷

1. 驗證設計錯了，任何漂亮分數都沒有意義。
2. 資料語意通常比換模型更值錢；先問 NaN 為什麼存在。
3. OOF 是模型比較、誤差分析與 ensemble 的共同語言。
4. Baseline 不是初學者模型，而是每次改動的品質底線。
5. 調參只能微調正確方向，不能修復錯誤 target 或 leakage。
6. 特徵工程要從可解釋假設開始，以 ablation 結束。
7. Public leaderboard、單一 holdout、單一 seed 都不能作唯一證據。
8. Stacking 沒通過 outer/meta cross-fit 就不要採用。
9. 重要性不是因果；Model Card 必須說清楚失敗模式與不適用範圍。
10. 保存完整 pipeline、data/code/env lineage，才叫可重現。
11. Production 指標包含 latency、cost、coverage、drift、fairness 與 rollback，不只有 AUC/RMSE。
12. 當改善小於噪音或維護成本時，停止就是最佳優化。

> 成熟的 ML 工程不是找到最花俏的模型，而是讓每個資料與模型決策都有**可信驗證、可重現紀錄與可回復邊界**。

## 常見錯誤與修正

| 錯誤 | 後果 | 修正 |
|---|---|---|
| 全資料先 impute/scale/encode | validation 樂觀 | 全部 fit 型處理放 Pipeline，每 fold 重 fit |
| 時間資料 random split | 未來資訊進 train | rolling / expanding time split |
| 同客戶跨 train/valid | 模型記住 entity | GroupKFold |
| 看 test / leaderboard 調規則 | 選模洩漏、不可泛化 | frozen holdout / nested CV |
| 所有 NaN `fillna(0)` | 破壞業務語意 | semantic missing + fold imputation |
| 只報最佳 fold / trial | 忽略 variance 與 selection bias | OOF、mean/std、所有 trials |
| 同時改五件事 | 不知道提升來源 | 單一主要假設 + ablation ledger |
| 重要性當因果 | 錯誤業務決策 | 只說模型依賴；因果需實驗設計 |
| 只存 `model.pkl` | train/serve skew | 完整 pipeline + schema + env |
| 沒有 rollback | 服務故障難恢復 | versioned artifacts + 演練 |

