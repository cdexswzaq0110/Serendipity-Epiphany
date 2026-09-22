#!/usr/bin/env bash
# Gate 自測：確認每支 hook 在**該擋的時候真的擋**、該放的時候真的放。
#
# 為什麼要有這支：hook 寫壞的預設失敗模式是「靜默放行」——路徑錯、spawn 失敗、
# 退出碼用錯，全部只產生 non-blocking error，動作照常執行。裝好不等於守得住，
# 必須看過一次紅燈。詳見 docs/lessons/0002。
#
# 用法：bash .claude/hooks/selftest.sh
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
H="$ROOT/.claude/hooks"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

pass=0
fail=0

check() { # expected actual label
  if [ "$1" = "$2" ]; then
    pass=$((pass + 1)); printf '  ok    %s\n' "$3"
  else
    fail=$((fail + 1)); printf '  FAIL  %s（期望 %s，實得 %s）\n' "$3" "$1" "$2"
  fi
}

run() { # script payload -> exit code
  printf '%s' "$2" | bash "$H/$1" >/dev/null 2>&1
  echo $?
}

bash_payload() { printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$1"; }
edit_payload='{"tool_name":"Edit","tool_input":{"file_path":"README.md"}}'

# ---------- guard-branch ----------
echo "guard-branch"
REPO="$TMP/repo"; mkdir -p "$REPO"
( cd "$REPO" && git init -q -b main . && git config user.email t@t && git config user.name t \
  && echo x > a.txt && git add . && git commit -qm init ) >/dev/null 2>&1
export CLAUDE_PROJECT_DIR="$REPO"

check 1 "$(run guard-branch.sh "$edit_payload")" "main（warn 模式）提示但不阻擋"
check 2 "$(printf '%s' "$edit_payload" | SE_GUARD_BRANCH_MODE=block bash "$H/guard-branch.sh" >/dev/null 2>&1; echo $?)" \
        "main（block 模式）阻擋"
check 1 "$(run guard-branch.sh "$(bash_payload "git add . && git commit -m x")")" "main 上 Bash 的 git commit 也提示"
check 0 "$(run guard-branch.sh "$(bash_payload "for i in 1; do echo \$i; done")")" "main 上不是 commit 的 Bash 迴圈放行"
( cd "$REPO" && git checkout -q -b feature/x )
check 0 "$(run guard-branch.sh "$edit_payload")" "feature 分支放行"

# ---------- guard-critical ----------
echo "guard-critical"
for c in "git reset --hard HEAD~1" \
         "git push --force origin main" \
         "git push -f origin main" \
         "git branch -D feature/x" \
         "git rebase -i main" \
         "git add . && git reset --hard HEAD" \
         "for b in x; do git branch -D \$b; done" \
         "git -C repo reset --hard HEAD" \
         "cd repo\\ngit rebase main" \
         "cat <<'EOF'\\nhi\\nEOF\\ngit reset --hard HEAD" \
         "cat <<<x; git reset --hard HEAD"; do
  check 2 "$(run guard-critical.sh "$(bash_payload "$c")")" "無 tag 時攔下：$c"
done

for c in "git status" \
         "git push origin main" \
         "git branch -d feature/x" \
         "git reset HEAD~1" \
         "git commit -m 'docs: 說明 rebase 恢復策略'" \
         "echo git reset --hard is dangerous" \
         "grep -rn 'branch -D' docs/" \
         "git commit -F - <<'EOF'\\nfix: for x; do git branch -D y; done\\ngit rebase main 前先打 tag\\nEOF" \
         "python - <<PY\\nprint(1); git reset --hard\\nPY"; do
  check 0 "$(run guard-critical.sh "$(bash_payload "$c")")" "不該攔：$c"
done

# 判定規則缺席時要往安全的方向失敗：guard-critical 擋，commit 閘退回一律檢查
NOLIB="$TMP/nolib"; mkdir -p "$NOLIB"; cp "$H/guard-critical.sh" "$H/check-router.sh" "$NOLIB/"
check 2 "$(printf '%s' "$(bash_payload "git status")" | bash "$NOLIB/guard-critical.sh" >/dev/null 2>&1; echo $?)" \
        "缺 _command.sh 時 guard-critical 擋下"

( cd "$REPO" && git tag -a "backup/selftest" -m snap )
check 0 "$(run guard-critical.sh "$(bash_payload "git reset --hard HEAD~1")")" "已有指向 HEAD 的 backup tag 時放行"

# ---------- check-router ----------
echo "check-router"
FAKE="$TMP/fake"; mkdir -p "$FAKE/.claude/skills/se-a" "$FAKE/.claude/skills/se-b"
export CLAUDE_PROJECT_DIR="$FAKE"
commit_payload=$(bash_payload "git commit -m x")

printf '# INDEX\n\n- `se-a`\n' > "$FAKE/.claude/skills/INDEX.md"
check 2 "$(run check-router.sh "$commit_payload")" "目錄存在但 INDEX 未列出"

# 同一個不一致狀態下：不是 commit 的指令一律放行（if 會對迴圈誤觸發，腳本要自己守）
for c in "for i in 1; do echo \$i; done" \
         "x=1; while [ -n \"\$x\" ]; do x=; done" \
         "git status" \
         "echo git commit is just a word"; do
  check 0 "$(run check-router.sh "$(bash_payload "$c")")" "不是 commit，放行：$c"
done
for c in "for f in a; do git commit -m x; done" \
         "git -C repo commit -m x" \
         "cd repo\\ngit commit -m x" \
         "git commit -F - <<'EOF'\\nmsg\\nEOF"; do
  check 2 "$(run check-router.sh "$(bash_payload "$c")")" "是 commit，照擋：$c"
done
check 0 "$(run check-router.sh "$(bash_payload "python - <<'PY'\\nprint(1); git commit\\nPY")")" \
        "heredoc 內文提到 git commit 不算 commit"
check 2 "$(printf '%s' "$(bash_payload "echo x")" | bash "$NOLIB/check-router.sh" >/dev/null 2>&1; echo $?)" \
        "缺 _command.sh 時 check-router 退回一律檢查"

printf '# INDEX\n\n- `se-a`\n- `se-b`\n' > "$FAKE/.claude/skills/INDEX.md"
check 0 "$(run check-router.sh "$commit_payload")" "INDEX 與目錄一致"

printf '# INDEX\n\n- `se-a`\n- `se-b`\n- `se-ghost`\n' > "$FAKE/.claude/skills/INDEX.md"
check 2 "$(run check-router.sh "$commit_payload")" "INDEX 指向已刪 skill"

printf '# INDEX\n\n- `se-a`\n- `se-b`\n' > "$FAKE/.claude/skills/INDEX.md"
printf '跑 /se-nope 開始。\n' > "$FAKE/CLAUDE.md"
check 2 "$(run check-router.sh "$commit_payload")" "常駐檔指向不存在的 skill"

export CLAUDE_PROJECT_DIR="$ROOT"
check 0 "$(run check-router.sh "$commit_payload")" "本專案目前狀態一致"

# ---------- check-memory ----------
echo "check-memory"
MEM="$TMP/mem"; mkdir -p "$MEM/docs/lessons"
export CLAUDE_PROJECT_DIR="$MEM"

lesson() {  # lesson <檔名> <source 行> <outcome> <validated 行>
  printf -- '---\nid: L0001\ndate: 2026-01-01\noutcome: %s\ntags: [t]\nanchors:\nsupersedes:\n%s\nhits: 0\ngeneralizes_to: x\n%s\n---\n\n# t\n' \
    "$3" "$2" "$4" > "$MEM/docs/lessons/$1"
}
index() { printf '# 索引\n\n| ID | 一句話 |\n|---|---|\n%s\n' "$1" > "$MEM/docs/lessons/INDEX.md"; }

lesson 0001-a.md "source: self-observed" useful "validated:"
index "| [L0001](0001-a.md) | x |"
check 0 "$(run check-memory.sh "$commit_payload")" "來源合法、INDEX 一致 → 放行"

lesson 0001-a.md "" useful "validated:"
check 2 "$(run check-memory.sh "$commit_payload")" "缺 source 欄位"
check 0 "$(run check-memory.sh "$(bash_payload "for f in a; do echo \$f; done")")" "同一狀態下不是 commit 的迴圈放行"

lesson 0001-a.md "source: 隨便寫" useful "validated:"
check 2 "$(run check-memory.sh "$commit_payload")" "source 不是合法值"

lesson 0001-a.md "source: external" promoted "validated: 有驗過"
check 2 "$(run check-memory.sh "$commit_payload")" "外部來源不得升級成常駐規則"

lesson 0001-a.md "source: self-observed" promoted "validated:"
check 2 "$(run check-memory.sh "$commit_payload")" "promoted 但 VALIDATE 關沒過"

lesson 0001-a.md "source: self-observed" useful "validated:"
index "| — | — |"
check 2 "$(run check-memory.sh "$commit_payload")" "檔案存在但 INDEX 未列出"

index "| [L0009](0009-ghost.md) | x |"
lesson 0001-a.md "source: self-observed" useful "validated:"
index "| [L0001](0001-a.md) | x |
| [L0009](0009-ghost.md) | x |"
check 2 "$(run check-memory.sh "$commit_payload")" "INDEX 指向不存在的 lesson"

export CLAUDE_PROJECT_DIR="$ROOT"
check 0 "$(run check-memory.sh "$commit_payload")" "本專案帳本目前狀態合規"

# ---------- guard-done（自主自控）----------
echo "guard-done"
GD="$TMP/gd"; mkdir -p "$GD/.claude/skills/se-a" "$GD/.claude/skills/se-orphan" "$GD/.claude/hooks" "$GD/docs/lessons"
cp "$H/check-router.sh" "$H/check-memory.sh" "$H/_command.sh" "$GD/.claude/hooks/"
printf '# INDEX\n\n- `se-a`\n' > "$GD/.claude/skills/INDEX.md"
printf '# 索引\n' > "$GD/docs/lessons/INDEX.md"
stop() { printf '{"stop_hook_active":%s}' "$1" | CLAUDE_PROJECT_DIR="$2" bash "$H/guard-done.sh" >/dev/null 2>&1; echo $?; }
check 2 "$(stop false "$GD")" "配置不一致 → 不准結束，繼續修"
check 0 "$(stop true "$GD")" "已被擋過一次 → 放行（自控邊界，防無限迴圈）"
printf '# INDEX\n\n- `se-a`\n- `se-orphan`\n' > "$GD/.claude/skills/INDEX.md"
check 0 "$(stop false "$GD")" "修好之後 → 放行"
check 0 "$(stop false "$TMP")" "非本配置的目錄 → 放行"

# ---------- recall-lessons（開工召回）----------
echo "recall-lessons"
RL="$TMP/rl"; mkdir -p "$RL/proj/docs/lessons" "$RL/home/lessons"
recall() { printf '{"source":"startup"}' | CLAUDE_PROJECT_DIR="$1" SERENDIPITY_HOME="$2" \
  bash "$H/recall-lessons.sh" 2>/dev/null | grep -c . ; }
check 0 "$(recall "$RL/proj" "$RL/nohome")" "兩邊都空 → 完全安靜，不佔 context"
printf '| [G0001](G0001-x.md) | 跨專案教訓 | 類別 | A、B |\n' > "$RL/home/lessons/INDEX.md"
n=$(recall "$RL/proj" "$RL/home")
[ "$n" -ge 2 ] && n=ok || n="只有 $n 行"
check ok "$n" "有跨專案 lesson → 另一個專案開工時看得到（遷移）"

# ---------- lessons.py（全域帳本上架閘）----------
echo "lessons.py"
LH="$TMP/lh"; mkdir -p "$LH/src"
les() { printf -- '---\nsource: %s\nhits: 0\ngeneralizes_to: %s\n---\n\n# t\n' "$2" "$3" > "$LH/src/$1"; }
promote() { SERENDIPITY_HOME="$LH/home" python "$ROOT/.claude/tools/lessons.py" promote "$@" >/dev/null 2>&1; echo $?; }
les ext.md external 類別; les ok.md self-observed 類別; les nogen.md self-observed ""
check 2 "$(promote "$LH/src/ext.md" --seen-in A --seen-in B)" "external 不得上架全域"
check 2 "$(promote "$LH/src/ok.md" --seen-in A)" "只在一個專案撞到 → 不算遷移"
check 2 "$(promote "$LH/src/nogen.md" --seen-in A --seen-in B)" "沒有泛化類別 → 不得上架"
check 0 "$(promote "$LH/src/ok.md" --seen-in A --seen-in B)" "兩個專案、有類別、非外部 → 上架"

# ---------- promote_skill.py（學習新技能的升級閘）----------
echo "promote_skill.py"
PS="$TMP/ps"; mkdir -p "$PS/.claude/tools" "$PS/.claude/skills" "$PS/.claude/skill-candidates"
cp "$ROOT/.claude/tools/promote_skill.py" "$PS/.claude/tools/"
printf '# INDEX\n' > "$PS/.claude/skills/INDEX.md"
cand() {
  d="$PS/.claude/skill-candidates/$1"; mkdir -p "$d/evals"
  printf -- '---\nname: %s\ndescription: 處理某個新領域的完整程序，當任務屬於這個新領域時使用\nvalidated: %s\n---\n\n# x\n' "$1" "$2" > "$d/SKILL.md"
  printf '| # | 使用者說的話 | 來源 |\n|---|---|---|\n' > "$d/evals/trigger-cases.md"
  shift 2; i=0
  for p in "$@"; do i=$((i+1)); printf '| %d | c%d | `%s` |\n' "$i" "$i" "$p" >> "$d/evals/trigger-cases.md"; done
}
pskill() { python "$PS/.claude/tools/promote_skill.py" "$@" >/dev/null 2>&1; echo $?; }
cand se-auth "用過" authored authored authored
cand se-noval "" user-prompt user-prompt user-prompt
cand se-good "2026-09-22 在X完成Y" user-prompt session-trace user-prompt
check 2 "$(pskill se-auth --dry-run)" "案例全照 description 寫 → 不得升級"
check 2 "$(pskill se-noval --dry-run)" "沒真的用過（validated 空）→ 不得升級"
check 0 "$(pskill se-good --dry-run)" "3 條獨立來源＋用過 → 可升級"

# ---------- 結果 ----------
echo ""
echo "通過 $pass／失敗 $fail"
[ "$fail" -eq 0 ] || exit 1
