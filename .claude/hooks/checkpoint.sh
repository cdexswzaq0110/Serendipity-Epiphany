#!/usr/bin/env bash
# 斷點記錄器（預寫日誌）：每次工具呼叫後記下工作樹指紋、記下回合有沒有正常結束，
# 有斷點時在開工或下一則訊息印出續跑簡報。邏輯在 tools/checkpoint.py，程序在 skills/se-resume。
#
# 這支是記錄器不是閘：任何失敗都 exit 0，不擋工作。
# 失敗會寫進 .git/serendipity/error.log，由續跑簡報提示——記錄器壞掉要看得到（docs/lessons/0002）。
PY=$(command -v python || command -v python3) || exit 0
"$PY" "$(dirname "$0")/../tools/checkpoint.py" record
exit 0
