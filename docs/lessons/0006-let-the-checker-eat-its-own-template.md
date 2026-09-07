---
id: L0006
date: 2026-09-07
outcome: useful
tags: [模板, 驗收腳本, bootstrap, 一致性]
anchors:
  - templates/_meta/bootstrap_check.sh
  - templates/CONTEXT.md
  - .claude/skills/se-bootstrap/SKILL.md
supersedes:
hits: 0
generalizes_to: 任何「模板 ＋ 驗收腳本」成對出現的地方
validated:
---

# 讓驗收腳本吃一次自己的模板——不然兩邊會漂，而且兩邊看起來都正常

## 觸發情境

一個模板（要人照著填）配一支驗收腳本（檢查填完的結果）。
本 repo 裡是 `templates/CONTEXT.md` ＋ `templates/_meta/bootstrap_check.sh`；
同樣的形狀還有 PR 模板配 CI 檢查、issue 模板配 label 規則、schema 配 validator。

## 領悟

**照著模板填出來的檔案，過不了模板自己的驗收腳本。**

`bootstrap_check.sh` 判 `CONTEXT.md` 是否夠充實的方式是數以 `|` 開頭的行
（`grep -c '^|'`），要求 ≥ 5——也就是**要一張表格**。

而 `templates/CONTEXT.md` 的 Language 段落用的是散文格式：

```markdown
**<詞>**：
<一句話定義>
_避免_：<舊叫法>
```

照著填，`grep -c '^|'` 回傳 **0**【已確認：2026-09-07 對模板實測，八項檢查失敗一項，exit 1】。

第一次把這套配置帶進真實專案（ThermoForge）時之所以沒撞到，
是因為那個專案自己改用了表格——**不是因為模板對**。

## 為什麼會撞到

錯誤假設是：**模板與驗收腳本是同一份規格的兩種表達，所以會一致。**

它們是分別寫的，而且沒有任何機制要求一致。腳本的檔頭註解寫得很清楚
「核取方塊靠人記得，腳本不會忘」——完全正確，但**腳本自己也需要一個東西
來確認它量的是模板真的會產出的形狀**。

這與 [L0003](0003-eval-harness-pitfalls.md)（量尺自己要先被量）是同一族，
但更具體：那則講的是量測工具的第一個數字通常在量工具本身；
這則講的是**成對的兩份文件會各自漂移，而且看起來都是對的**。
與 [L0005](0005-your-checker-is-the-first-suspect.md) 也相鄰——
系統說壞了的時候第一個嫌疑犯是判定條件；這裡是**系統說好了的時候，
第一個嫌疑犯是判定條件從來沒被餵過真正的輸入**。

## 下次怎麼做

**任何「模板 ＋ 驗收腳本」成對出現的地方，加一個把模板本身餵給腳本的測試。**

本 repo 的落地：

```bash
bash templates/_meta/bootstrap_check.sh --selftest
```

它做三件事，缺一不可：

1. 拿 `templates/CONTEXT.md` **原樣**建一份 fixture，跑一般模式，**必須通過**。
2. 拿一份詞條不足的 CONTEXT.md，**必須被擋**（沒看過紅燈的檢查不算裝好，L0002）。
3. 拿一份表格式的，**也必須通過**（判準放寬成兩種形狀都算，不是強迫大家改用表格）。

修的時候有兩個選項，選了「腳本放寬」而不是「模板改表格」：
改模板會讓已經照舊格式寫過 `CONTEXT.md` 的專案在下次跑檢查時突然變紅，
而它們沒有做錯任何事。**判準的缺陷不該由使用者付代價。**

順帶一提：ThermoForge 用表格之後發現「避免的舊叫法」那一欄比預期有用——
它逼你寫下**被取代掉的那個名字**，而那正是歧義的來源。所以模板現在兩種形狀都示範。

## 失效條件

- `bootstrap_check.sh` 改成不檢查 `CONTEXT.md` 的充實度——這一則的具體案例失效，
  但「讓腳本吃自己的模板」那一句仍然成立。
- 若之後改用 schema 驗證（JSON Schema、frontmatter 驗證器）取代 grep，
  第 1、3 點要重寫；第 2 點（要看過紅燈）永遠成立。
