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

# --selftest：拿**這個腳本自己的模板**建一份 fixture，再用一般模式檢查它。
#
# 存在的理由是一個真的踩過的坑：templates/CONTEXT.md 照著填會過不了這支腳本
# （模板寫散文，腳本數表格的 `|`）。兩份檔案分別寫、沒有機制要求一致，於是漂掉，
# 而且**兩邊看起來都很正常**——只有把模板餵給腳本才看得出來。
#
# 順便驗一次紅燈：詞條不足的 CONTEXT.md 必須被擋。只驗綠燈的自測，
# 對一個永遠回傳 0 的假實作也會全過。
if [ "${1:-}" = "--selftest" ]; then
  self=$(cd "$(dirname "$0")" && pwd)
  tpl="$self/../CONTEXT.md"
  [ -f "$tpl" ] || { echo "找不到 $tpl"; exit 1; }

  fixture() { # context-file -> 一個最小但合格的專案目錄
    local ctx="$1" d
    d=$(mktemp -d)
    ( cd "$d"       && git init -q -b main .       && git config user.email selftest@local && git config user.name selftest       && printf '.claude/settings.local.json
' > .gitignore       && printf '# fixture
' > CLAUDE.md       && mkdir -p .claude/rules docs/lessons       && for n in core-rules dispatch evidence-grades git-workflow register thinking-boundary; do
           printf '# %s
' "$n" > ".claude/rules/$n.md"
         done       && cp "$ctx" CONTEXT.md       && git add -A && git commit -qm 'chore: bootstrap' ) >/dev/null 2>&1
    echo "$d"
  }

  fails=0

  # 綠燈：模板原樣（它的 Language 段落有三個詞條）必須通過。
  good=$(fixture "$tpl")
  if bash "$0" "$good" >/dev/null 2>&1; then
    echo "  ok    模板原樣通過自己的檢查"
  else
    echo "  FAIL  templates/CONTEXT.md 過不了 bootstrap_check.sh —— 兩者又漂開了"
    bash "$0" "$good" | sed 's/^/        /'
    fails=$((fails + 1))
  fi

  # 紅燈：只有一個詞條必須被擋。沒看過紅燈的檢查不算裝好。
  thin=$(mktemp)
  printf '# 共享語言

## Language

**只有一個詞**：
定義
' > "$thin"
  poor=$(fixture "$thin")
  if bash "$0" "$poor" >/dev/null 2>&1; then
    echo "  FAIL  詞條不足的 CONTEXT.md 沒有被擋下來"
    fails=$((fails + 1))
  else
    echo "  ok    詞條不足時擋下來（看過紅燈）"
  fi

  # 紅燈：表格式寫法也要認得。
  tbl=$(mktemp)
  printf '# 共享語言

## Language

| 詞 | 定義 | 避免 |
|---|---|---|
| A | a | x |
| B | b | y |
| C | c | z |
' > "$tbl"
  tblp=$(fixture "$tbl")
  if bash "$0" "$tblp" >/dev/null 2>&1; then
    echo "  ok    表格式寫法也算數"
  else
    echo "  FAIL  表格式的 CONTEXT.md 被誤判為太空"
    fails=$((fails + 1))
  fi

  rm -rf "$good" "$poor" "$tblp" "$thin" "$tbl"
  [ "$fails" -eq 0 ] && { echo; echo "自測通過"; exit 0; }
  echo; echo "自測失敗 $fails 項"; exit 1
fi

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
# CONTEXT.md 的充實度。**兩種寫法都算**——散文式（模板的預設）與表格式。
#
# 舊版只數以 `|` 開頭的行，於是照 templates/CONTEXT.md 填出來的檔案一律不及格：
# 那個模板的 Language 段落是散文，`grep -c '^|'` 回傳 0。模板與它的驗收腳本
# 分別寫、沒有任何機制要求一致，於是漂掉了。`--selftest` 現在會擋住這件事重演。
count_terms() { # file -> 詞條數
  local f="$1" bold rows
  bold=$(grep -cE '^\*\*[^*]+\*\*' "$f" 2>/dev/null || true)
  # 表格：扣掉分隔列，再扣一列表頭。
  rows=$(grep -E '^\|' "$f" 2>/dev/null | grep -cvE '^\|[[:space:]:|-]+$' || true)
  [ "${rows:-0}" -gt 0 ] && rows=$((rows - 1))
  echo $(( ${bold:-0} + ${rows:-0} ))
}

if [ -f "$ROOT/CONTEXT.md" ]; then
  terms=$(count_terms "$ROOT/CONTEXT.md")
  if [ "$terms" -ge 3 ]; then ok "CONTEXT.md 有內容（$terms 個詞條）"
  else bad "CONTEXT.md 太空（$terms 個詞條）" "至少填三到五個真的會用到的詞"; fi
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
