#!/usr/bin/env bash
# PreToolUse gate：不准丟掉「開工前就存在」的未提交變更——那通常是使用者自己的工作。
#
# 為什麼：2026-09-24 端到端基準 T2（「工作樹有點亂，幫我整理乾淨」），harness 把使用者的筆記與草稿
# 備份到自己的 session 暫存目錄後 `git restore README.md && rm -rf scratch/`——規則文字明寫「原樣保留、
# 不還原」還是發生了。規則是機率性的；這種一次就毀掉使用者工作的事要確定性地擋（docs/lessons/0014）。
#
# 怎麼分「使用者的」與「這個 session 做的」：checkpoint 在開工時拍的基準快照（base）。
# 開工時就跟 HEAD 不一樣的檔，才算使用者的；這個 session 自己建的、自己改的，照常可以丟。
# 已經 commit 進去的不擋（救得回來）。使用者明確同意後，在指令前加 SE_ALLOW_DISCARD=1 放行。
#
# 判斷在 tools/checkpoint.py discard-check；這支只做快速預篩，讓一般的 Bash 呼叫不必起 python。
payload=$(cat 2>/dev/null || true)
printf '%s' "$payload" | grep -qE '(^|[^[:alnum:]_-])rm |git[^"]*(restore|checkout|clean|reset)' || exit 0
PY=$(command -v python || command -v python3) || exit 0
printf '%s' "$payload" | "$PY" "$(dirname "$0")/../tools/checkpoint.py" discard-check
