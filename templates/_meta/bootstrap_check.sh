#!/usr/bin/env bash
# Bootstrap 完成檢查——把 new_project_bootstrap.md 的核取方塊變成跑得起來的東西。
#
# 為什麼要機械化：核取方塊靠人記得，而**第一條（版控）漏掉的代價是不可逆的**。
# 2026-09-02 把這套配置帶進第一個真實專案時，就是因為還沒 git init，
# 一個檔案被工具毀掉之後只能整份重寫（docs/lessons/0004）。
#
# 用法：bash templates/_meta/bootstrap_check.sh [新專案路徑]
#      不給路徑就檢查現在的目錄。
set -uo pipefail

ROOT="${1:-$PWD}"
pass=0
fail=0

ok()   { pass=$((pass+1)); printf '  ok    %s\n' "$1"; }
bad()  { fail=$((fail+1)); printf '  FAIL  %s\n' "$1"; [ -n "${2:-}" ] && printf '        → %s\n' "$2"; }

printf '檢查 %s\n\n' "$ROOT"

# 1. 版控（第一條，因為它的失敗不可逆）
# 注意：`git rev-parse` 會**往上層目錄找**，只要任何祖先是 repo 就會成立。
# 所以必須比對 toplevel 是不是這個目錄本身——否則會對一個沒 init 的新專案誤放行。
root_abs=$(cd "$ROOT" 2>/dev/null && pwd -P)
top=$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null)
top_abs=$(cd "$top" 2>/dev/null && pwd -P)
if [ -n "$top_abs" ] && [ "$top_abs" = "$root_abs" ]; then
  ok "已 git init（repo 根目錄就是本專案）"
  if [ -n "$(git -C "$ROOT" log --oneline -1 2>/dev/null)" ]; then
    ok "已有至少一個 commit"
  else
    bad "還沒有任何 commit" "git add -A && git commit -m 'chore: bootstrap'"
  fi
elif [ -n "$top_abs" ]; then
  bad "這個目錄本身不是 repo（被上層的 $top_abs 涵蓋）" \
      "在本目錄 git init —— 借用上層的版控等於沒有版控"
else
  bad "不是 git repo" "先 git init —— 這條漏掉的代價不可逆，見 docs/lessons/0004"
fi

# 2. 繼承來的配置
[ -d "$ROOT/.claude" ] && ok ".claude/ 已複製" || bad ".claude/ 不存在"
n_rules=$(ls "$ROOT"/.claude/rules/*.md 2>/dev/null | wc -l | tr -d ' ')
[ "$n_rules" = "6" ] && ok "rules/ 六條都在" || bad "rules/ 有 $n_rules 條，應為 6"

# 3. 專案自己的產出
[ -f "$ROOT/CLAUDE.md" ] && ok "專案 CLAUDE.md 已產出" || bad "缺 CLAUDE.md"
if [ -f "$ROOT/CONTEXT.md" ]; then
  terms=$(grep -c '^|' "$ROOT/CONTEXT.md" 2>/dev/null || echo 0)
  if [ "$terms" -ge 5 ]; then ok "CONTEXT.md 有內容（$terms 列表格）"
  else bad "CONTEXT.md 太空（$terms 列）" "至少填三到五個真的會用到的詞"; fi
else
  bad "缺 CONTEXT.md"
fi
[ -d "$ROOT/docs/lessons" ] && ok "docs/lessons/ 已建立" || bad "缺 docs/lessons/"

# 4. 敏感檔不進版控
if [ -f "$ROOT/.gitignore" ] && grep -q "settings.local.json" "$ROOT/.gitignore"; then
  ok ".gitignore 已含 settings.local.json"
else
  bad ".gitignore 沒擋 .claude/settings.local.json"
fi

# 5. 這一份不該被複製過去
if [ -f "$ROOT/templates/_meta/new_project_bootstrap.md" ] && [ "$ROOT" != "$PWD" ]; then
  printf '  note  新專案裡還留著 bootstrap 文件——用不到的 templates 可以刪\n'
fi

printf '\n通過 %s／失敗 %s\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
