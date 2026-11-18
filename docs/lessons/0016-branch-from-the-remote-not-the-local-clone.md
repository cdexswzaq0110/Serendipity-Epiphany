---
id: L0016
date: 2026-11-18
outcome: useful
tags: [git, 分支, 基準, 整合]
anchors:
  - .claude/rules/git-workflow.md
  - docs/design/2026-11-18-v2.1-integration/01-plan.md
supersedes:
source: self-observed
hits: 0
generalizes_to: 任何「在別人也會推送的 repo 上開一段長工作」——本機 clone 的預設分支只代表上次 pull 的時間點，不代表現在
validated:
---

# 開分支要從遠端的預設分支開，不是從本機那份

## 觸發情境

要在一個 repo 上做一段大改動，本機已經有 clone，`git status` 乾淨、`main` 看起來正常，就直接從它開分支。

## 領悟

2.0.0（`feat/skills-bundle`）是從本機 clone 的 `main` 開的，那時本機停在 PR #5（`9db0475`）；
GitHub 上的 `main` 已經合到 PR #15，中間有 26 個 commit：記憶層准入、斷點續跑、丟棄保護、
端到端基準，以及一條用基準證明有害、已經拿掉的規則【已確認：`git log 9db0475..origin/main`】。

**2.0.0 的設計討論、GPT 的提案與紅隊全部建立在這個舊基準上**，所以：

- 有兩個 skill 在 main 已經改過，2.0.0 卻在舊版本上重寫；
- 2.0.0 的常駐面把那條有害規則加了回去；
- 推送時 PR 開不成可合併的狀態，最後要再做一輪整合（2.1.0）。

`git status` 乾淨不能證明什麼：它只比較工作樹與本機的 HEAD，不會告訴你遠端已經往前走了多少。

## 為什麼會撞到

開工檢查只看本機狀態（分支、工作樹），沒有一步去問「這個基準是不是最新的」。
本機 clone 平常不常用，落後幾週也不會有任何警訊。

## 下次怎麼做

1. 開一段長工作的第一步：`git fetch origin`，然後 `git switch -c <branch> origin/<預設分支>`，**不要從本機的預設分支開**。
2. 設計或研究某個 repo 之前，先比對 `git rev-parse origin/<預設分支>` 與本機的版本；落後就先 pull 再讀。
3. 推送前再 fetch 一次，看 `git log HEAD..origin/<預設分支>`；有新 commit 就先整合再開 PR。

## 失效條件

- 只有自己會推送、而且只在這台機器上工作的 repo，本機就是最新的，這一條可以省略。
- 若預設分支不叫 `main`（例如 Serendipity-Epiphany-Codex 的預設分支是 `feature/agent-execution`），要用 `git remote show origin` 查出實際的預設分支。
