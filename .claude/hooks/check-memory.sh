#!/usr/bin/env bash
# PreToolUse gate（git commit 時觸發）：記憶層的准入控制。
#
# 為什麼需要：`docs/lessons/` 是這套配置的長期記憶，而長期記憶在 Agent 系統裡
# 實質上是**動態的配置層**——一則錯的 lesson 被召回之後，會靜默地改變後續每一次
# 決策，而且模型不自知。這跟「快取壞掉會拋 Error」是兩種東西：壞快取會停，
# 髒記憶會繼續跑。
#
# 所以外部來源寫進記憶層，要像對待 SQL injection 一樣防。四條檢查：
#   1. 每則 lesson 必須標 source（內容依據來自哪裡）
#   2. source: external 的**不得**升級成常駐規則——外部說法沒有本地失敗證據
#   3. outcome: promoted 的必須有 validated（呼應 se-epiphany 的 VALIDATE 關）
#   4. INDEX.md 與實際檔案雙向一致（記憶層版本的「Router 不說謊」）
set -uo pipefail

MODE="${SE_CHECK_MEMORY_MODE:-block}"
ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
DIR="$ROOT/docs/lessons"
INDEX="$DIR/INDEX.md"

# 不是這個 repo（或還沒有帳本）就放行
[ -d "$DIR" ] || exit 0
[ -f "$INDEX" ] || exit 0

VALID_SOURCE="self-observed user-stated external"
problems=""
add() { problems="$problems
  $1"; }

field() {  # field <file> <name> —— 只讀 frontmatter 區段
  sed -n '2,/^---$/p' "$1" | sed -n "s/^$2: *//p" | sed 's/ *#.*//' | head -1 \
    | sed 's/[[:space:]]*$//'
}

for f in "$DIR"/[0-9]*.md; do
  [ -f "$f" ] || continue
  base=$(basename "$f")

  src=$(field "$f" source)
  outcome=$(field "$f" outcome)
  validated=$(field "$f" validated)

  if [ -z "$src" ]; then
    add "$base：缺 source 欄位（self-observed／user-stated／external）"
  else
    ok=0
    for v in $VALID_SOURCE; do [ "$src" = "$v" ] && ok=1; done
    [ "$ok" = "1" ] || add "$base：source='$src' 不是合法值（$VALID_SOURCE）"
  fi

  if [ "$outcome" = "promoted" ]; then
    [ "$src" = "external" ] && \
      add "$base：source=external 不得升級成常駐規則——外部說法沒有本地失敗證據"
    [ -z "$validated" ] && \
      add "$base：outcome=promoted 但 validated 是空的（VALIDATE 關沒過）"
  fi

  grep -q -- "$base" "$INDEX" || add "$base：檔案存在但 INDEX.md 未列出"
done

# 反向：INDEX 提到但檔案不存在
for name in $(grep -o '([0-9][0-9a-z-]*\.md)' "$INDEX" 2>/dev/null | tr -d '()' | sort -u); do
  [ -f "$DIR/$name" ] || add "INDEX.md 指向不存在的 $name"
done

if [ -n "$problems" ]; then
  {
    echo "[check-memory] 記憶層准入檢查未通過：$problems"
    echo ""
    echo "記憶層是配置層——一則錯的 lesson 會靜默改變後續每一次決策。"
    echo "修正 docs/lessons/ 的 frontmatter 或 INDEX.md 再 commit。"
    echo "（由 .claude/hooks/check-memory.sh 強制；目前模式 $MODE）"
  } >&2
  [ "$MODE" = "block" ] && exit 2
  exit 1
fi

exit 0
