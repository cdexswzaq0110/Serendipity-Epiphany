#!/usr/bin/env bash
# SessionStart hook：開工時把跨專案學過的東西浮上來——讓自我改進迴圈的第一步真的發生。
#
# 為什麼：2026-09-22 盤點時，兩個專案共 9 則 lesson，hits 總和 0、升級 0 則。
# 不是 lesson 沒用，是**從來沒被召回過**：se-epiphany 的召回模式要「似曾相識」才啟動，
# 而那個判斷交給了模型。迴圈的第一步不發生，後面的升級、驗證全都沒有輸入。
#
# 這裡只放**指標**（一則一行），不放內容。stdout 會進 context，長度就是成本——
# 上限 10 則全域 lesson，超過就只給數量與查法。
set -uo pipefail

# 觸發評測的 session 不注入：提示裡點名了 se-epiphany／se-acquire，會汙染它們的路由量測（docs/lessons/0011）
[ -n "${SE_EVAL:-}" ] && exit 0

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
HOME_DIR="${SERENDIPITY_HOME:-$HOME/.claude/serendipity}"
GLOBAL_INDEX="$HOME_DIR/lessons/INDEX.md"
LOCAL_INDEX="$ROOT/docs/lessons/INDEX.md"
MAX=10

g_rows=""
g_n=0
if [ -f "$GLOBAL_INDEX" ]; then
  g_rows=$(grep -E '^\| \[G[0-9]+' "$GLOBAL_INDEX" 2>/dev/null)
  g_n=$(printf '%s' "$g_rows" | grep -c '^|' 2>/dev/null || echo 0)
fi
l_n=0
[ -f "$LOCAL_INDEX" ] && l_n=$(grep -cE '^\| \[L[0-9]+' "$LOCAL_INDEX" 2>/dev/null || echo 0)

# 兩邊都沒有就安靜——不為空帳本佔 context
[ "$g_n" -eq 0 ] && [ "$l_n" -eq 0 ] && exit 0

echo "[Serendipity] 領悟帳本：本專案 ${l_n} 則、跨專案 ${g_n} 則。"
if [ "$g_n" -gt 0 ]; then
  echo "跨專案（在至少兩個專案各自撞到過的）："
  printf '%s\n' "$g_rows" | head -n "$MAX" | sed -E 's/^\| \[(G[0-9]+)\]\([^)]*\) \| ([^|]*)\|.*/  \1 \2/'
  [ "$g_n" -gt "$MAX" ] && echo "  …另有 $((g_n - MAX)) 則，用 lessons.py list --tag <關鍵字> 查"
fi
echo "任務似曾相識時用 se-epiphany 的召回模式；領域全新時用 se-acquire。"
exit 0
