#!/usr/bin/env bash
# PreToolUse gate：破壞性 git 操作前，必須有指向目前 HEAD 的 backup tag。
# 對應 rules/git-workflow.md「Critical Section 先打 backup tag」。
#
# 涵蓋範圍與規則逐字對齊：reset --hard / push --force / branch -D / rebase。
# 腳本自己判定指令內容，不完全依賴 settings.json 的 if——if 沒生效時仍然守得住。
set -uo pipefail

MODE="${SE_GUARD_CRITICAL_MODE:-block}"

payload=$(cat 2>/dev/null || true)

# git 必須出現在「指令位置」，否則 `echo git reset --hard` 這類敘述會被誤判；
# heredoc 內文（commit message）不算指令。判定規則在 _command.sh，四支閘共用。
DESTRUCTIVE='reset[[:space:]][^"]*--hard|push[[:space:]][^"]*(--force|-f([[:space:]"]|$))|branch[[:space:]][^"]*-D|rebase'

# 判定不了就擋——這是 Critical Section，寧可多擋。
if ! . "$(dirname "$0")/_command.sh" 2>/dev/null; then
  echo "[guard-critical] 找不到 .claude/hooks/_command.sh，無法判定是否為破壞性操作，先擋下。" >&2
  [ "$MODE" = "block" ] && exit 2
  exit 1
fi
is_git_cmd "$payload" "$DESTRUCTIVE" || exit 0

cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

head=$(git rev-parse HEAD 2>/dev/null) || exit 0
short=$(git rev-parse --short HEAD 2>/dev/null)
branch=$(git branch --show-current 2>/dev/null)
[ -z "$branch" ] && branch="detached"

for t in $(git tag --list 'backup/*' 2>/dev/null); do
  if [ "$(git rev-parse "$t^{commit}" 2>/dev/null)" = "$head" ]; then
    exit 0
  fi
done

suggested="backup/${branch}-$(date +%F)"

cat >&2 <<EOF
[guard-critical] 破壞性 git 操作前必須先打 backup tag。

目前 HEAD ($short) 沒有任何指向它的 backup/* tag。先執行：
  git tag -a "$suggested" -m "安全快照, tip $short"

恢復路徑：
  git reset --hard "$suggested"

（rules/git-workflow.md Critical Section，由 .claude/hooks/guard-critical.sh 強制；目前模式 $MODE）
EOF

[ "$MODE" = "block" ] && exit 2
exit 1
