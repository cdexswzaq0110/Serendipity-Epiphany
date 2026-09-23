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
check 0 "$(SE_EVAL=1 recall "$RL/proj" "$RL/home")" "觸發評測的 session（SE_EVAL）不注入——提示點名了被測的 skill"

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
check 1 "$(SERENDIPITY_HOME="$LH/home" python "$ROOT/.claude/tools/capabilities.py" --json 2>/dev/null \
  | python -c 'import json,sys; print(json.load(sys.stdin)["verified"]["lessons"]["global"])' 2>/dev/null)" \
  "自我模型數得到剛上架的那則（與 recall-lessons 一致）"
check "$(grep -o 'hooks/[a-z-]*\.sh' "$ROOT/.claude/settings.json" | sort -u | wc -l | tr -d ' ')" \
  "$(python "$ROOT/.claude/tools/capabilities.py" --json 2>/dev/null \
     | python -c 'import json,sys; print(len(json.load(sys.stdin)["can_do"]["hooks"]))' 2>/dev/null)" \
  "自我模型的 hook 數＝設定檔實際註冊的腳本數（一支掛多個事件只算一道）"

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
cand se-dup "2026-09-24 用過" user-prompt user-prompt user-prompt
sed -i 's/| c[0-9] |/| 同一句話 |/' "$PS/.claude/skill-candidates/se-dup/evals/trigger-cases.md"
check 2 "$(pskill se-dup --dry-run)" "同一句話貼三行只算一條 → 不得升級（採礦會挖出大量逐字重複）"

# ---------- mine.py（經驗採礦：學習迴圈的第一步）----------
echo "mine.py"
MN="$TMP/mn"; mkdir -p "$MN/tx" "$MN/proj/.claude/tools" "$MN/proj/.claude/skill-candidates" "$MN/proj/.claude/skills"
cp "$ROOT/.claude/tools/mine.py" "$ROOT/.claude/tools/promote_skill.py" "$MN/proj/.claude/tools/"
printf '# INDEX\n' > "$MN/proj/.claude/skills/INDEX.md"
python - "$MN/tx" <<'PY'
import json, sys, os
d = sys.argv[1]
def u(text, human=True, meta=False):
    o = {"type": "user", "message": {"role": "user", "content": text}}
    if human: o["origin"] = {"kind": "human"}
    if meta: o["isMeta"] = True
    return o
def tool(name, inp): return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}
def err(t): return {"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True, "content": t}]}}
sed = tool("Bash", {"command": 'for f in a b; do sed -i \'s/\\r$//\' "$f"; done'})
look = tool("Bash", {"command": "tail -3 x.txt"})
here = tool("Bash", {"command": "python - <<'PY'\nprint(1)\nPY"})
e = err("Error: widget exploded while reading C:/tmp/abc123.txt at line 12")
h1 = [u("幫我跑測試"), tool("Skill", {"skill": "se-debug"}), u("幫我跑測試"), u("測試跑一下"), u("測試跑一下"),
      u("run the tests"), u("run the tests"), u("<task-notification>x</task-notification>"),
      u("[Image: original 10x10]", meta=True), e, e] + [sed] * 6 + [look] * 12 + [here] * 12
h2 = [u("幫我跑測試"), u("測試跑一下"), u("run the tests"), e] + [sed] * 6 + [here] * 3
x = [u("幫我跑測試", human=False)] * 10 + [sed] * 20
for name, evs in (("aaaaaaaa-h1", h1), ("bbbbbbbb-h2", h2), ("cccccccc-x", x)):
    with open(os.path.join(d, name + ".jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(o, ensure_ascii=False) + "\n" for o in evs)
PY
mjson=$(cd "$MN/proj" && python .claude/tools/mine.py --transcripts "$MN/tx" --json 2>/dev/null)
mq() { printf '%s' "$mjson" | PYTHONUTF8=1 python -c "import json,sys; m=json.load(sys.stdin); print($1)" 2>/dev/null; }  # 不設 UTF-8 模式，Windows 的 stdin 會用 cp950 把中文解壞
check "2/1" "$(mq 'str(m["human_sessions"]) + "/" + str(m["skipped_sessions"])')" "只讀人類 session，headless 評測略過"
check 3 "$(mq 'next((r["n"] for r in m["needs"] if r["key"]=="幫我跑測試"), 0)')" "headless 裡重複 10 次的話不算需求（只數人類的 3 次）"
check no "$(mq '"yes" if any(r["key"].startswith(("<","[image")) for r in m["needs"]) else "no"')" "系統通知與圖片說明不算使用者的話"
check yes "$(mq '"yes" if any(r["key"]=="幫我跑測試" and "se-debug" in r["skills"] for r in m["needs"]) else "no"')" "記下那句話之後實際載入了哪個 skill"
check 12 "$(mq 'next((r["n"] for r in m["actions"] if r["key"].startswith("sed -i")), 0)')" "迴圈 do 後面的動作也抓得到（CRLF 儀式就藏在那裡）"
check no "$(mq '"yes" if any(r["key"].startswith(("tail","print")) for r in m["actions"]) else "no"')" "純查看的指令與 heredoc 內文不算動作"
check 3 "$(mq 'next((r["n"] for r in m["failures"] if "widget exploded" in r["key"]), 0)')" "反覆撞到的錯誤依簽名歸在一起（路徑、數字遮掉）"
check 2 "$(cd "$MN/proj" && python .claude/tools/mine.py --transcripts "$MN/tx" seed se-runtests --from 1 >/dev/null 2>&1; echo $?)" "從零播種但說法不滿 3 種 → 拒絕"
check 0 "$(cd "$MN/proj" && python .claude/tools/mine.py --transcripts "$MN/tx" seed se-runtests --from 1 --from 2 --from 3 >/dev/null 2>&1; echo $?)" "3 種不同說法 → 播種成候選"
check 3 "$(grep -c '`session-trace`' "$MN/proj/.claude/skill-candidates/se-runtests/evals/trigger-cases.md" 2>/dev/null)" "案例逐字取自逐字紀錄，來源標 session-trace"
check 2 "$(cd "$MN/proj" && python .claude/tools/promote_skill.py se-runtests --dry-run >/dev/null 2>&1; echo $?)" "播種出來的候選在寫好 SKILL.md、真的用過之前升不上去"

# ---------- checkpoint（斷點續跑）----------
echo "checkpoint"
CK="$TMP/ck"; mkdir -p "$CK"
( cd "$CK" && git init -q -b main . && git config user.email t@t && git config user.name t \
  && echo a > a.txt && git add . && git commit -qm init && git checkout -q -b feature/x ) >/dev/null 2>&1
CKPY="$ROOT/.claude/tools/checkpoint.py"
# 真實 payload 的 cwd 是原生路徑（Windows 上是 C:\...），不是 Git Bash 的 /tmp/...
CKN=$(cygpath -m "$CK" 2>/dev/null || printf '%s' "$CK")
# 身分用程序（CLAUDE_PID）。自測本身常在 Claude Code 裡跑、會繼承它，所以一律明確指定：
# CKPID 空 → 清掉（退回用結束標記推論）；有值 → 當成那個程序
ckenv() { if [ -n "${CKPID:-}" ]; then CLAUDE_PID="$CKPID" "$@"; else env -u CLAUDE_PID "$@"; fi; }
ck() {  # ck <事件> <session> [額外欄位] → 記錄器的 stdout
  printf '{"hook_event_name":"%s","session_id":"%s","cwd":"%s"%s}' "$1" "$2" "$CKN" "${3:-}" \
    | ckenv bash "$H/checkpoint.sh" 2>/dev/null
}
ckcli() { ( cd "$CK" && ckenv python "$CKPY" "$@" 2>&1 ); }
CKPID=""
has() { printf '%s' "$1" | grep -q -- "$2" && echo yes || echo no; }

check 0 "$(printf 'not json' | bash "$H/checkpoint.sh" >/dev/null 2>&1; echo $?)" "壞掉的 payload → 記錄器不擋工作（exit 0）"
check 0 "$(printf '{"hook_event_name":"Stop","cwd":"%s"}' "$TMP" | bash "$H/checkpoint.sh" >/dev/null 2>&1; echo $?)" "不在 git repo → 放行"

ck UserPromptSubmit AAAAAAAA ',"prompt":"把付款重試做完並開 PR"' >/dev/null
( cd "$CK" && echo b > b.txt && echo a2 > a.txt )
ck PostToolUse AAAAAAAA ',"tool_name":"Edit"' >/dev/null
check yes "$( [ -s "$CK/.git/serendipity/journal.jsonl" ] && echo yes || echo no)" "工具呼叫後寫下斷點（在 .git 裡，不進版控）"
check 0 "$( cd "$CK" && git diff --cached --name-only | wc -l | tr -d ' ')" "算指紋不動使用者的 index"

out=$(ck SessionStart BBBBBBBB ',"source":"startup"')
check yes "$(has "$out" '沒有正常結束')" "回合沒結束就掛掉 → 新 session 開工時看到斷點"
check yes "$(has "$out" '把付款重試做完')" "簡報帶出中斷前最後的要求"
check yes "$(has "$out" 'a.txt、b.txt')" "簡報列出這段工作改過的檔案"
check yes "$(has "$out" '沒有被別人動過')" "工作樹沒被別人動過 → 明說可以接手"
check 0 "$(ck UserPromptSubmit BBBBBBBB ',"prompt":"繼續"' | grep -c .)" "同一個 session 已看過簡報 → 下一則訊息不重複"

( cd "$CK" && echo user > c.txt )
check yes "$(has "$(ckcli status)" 'c.txt——先確認')" "斷點之後別人改的檔案被指認出來"

ckcli verify -- bash -c "exit 0" >/dev/null
check yes "$(has "$(ckcli status)" '仍有效')" "驗證綁定工作樹：沒變 → 仍有效"
( cd "$CK" && echo more >> c.txt )
check yes "$(has "$(ckcli status)" '視為未驗證')" "工作樹變了 → 驗證自動失效"

ckcli decide "非會員能不能退款" "不能" >/dev/null
check yes "$(has "$(ckcli status)" '不要再問')" "人拍板過的決定帶進續跑"

ckcli step add S1 "寫完 done.txt" --done-when "test -f done.txt" >/dev/null
ckcli step done S1 >/dev/null
check yes "$(has "$(ckcli resume)" '宣稱完成，但現實不成立')" "宣稱完成但完成條件不成立 → 抓出來"
ckcli step add S2 "推上遠端" --done-when "test -f pushed.txt" >/dev/null
( cd "$CK" && touch done.txt pushed.txt )
check yes "$(has "$(ckcli resume)" '可能做完就斷了')" "做完了但沒記到（副作用發生在記錄之前）→ 從現實認出來"

printf '{"kind":"snap","at":"2099-' >> "$CK/.git/serendipity/journal.jsonl"
check yes "$(has "$(ckcli status)" '殘缺')" "日誌最後一行寫到一半 → 跳過，不讓整份失效"
ckcli decide "殘缺行之後的下一筆" "要活下來" >/dev/null
check yes "$(has "$(ckcli status)" '要活下來')" "殘缺行之後寫入的下一筆不被連帶吃掉"

mkdir -p "$CK/.git/rebase-merge"
check yes "$(has "$(ckcli status)" '進行中的 git 操作：rebase')" "中斷在 rebase 中途 → 先處理它"
rmdir "$CK/.git/rebase-merge"

ck PostToolUse CCCCCCCC ',"tool_name":"Bash"' >/dev/null
check 0 "$(ck UserPromptSubmit CCCCCCCC ',"prompt":"背景工作完成的通知"' | grep -c .)" "回合進行中插進訊息（還沒 Stop）→ 不是中斷，不提醒"
ck StopFailure CCCCCCCC ',"error":"rate_limit"' >/dev/null
check yes "$(has "$(ck UserPromptSubmit CCCCCCCC ',"prompt":"額度恢復了，繼續"')" 'rate_limit')" "同一個 session 因用量上限中止 → 下一則訊息提醒原因"

ck PostToolUse CCCCCCCC ',"tool_name":"Edit"' >/dev/null
ck Stop CCCCCCCC >/dev/null
ck UserPromptSubmit DDDDDDDD ',"prompt":"只是聊天"' >/dev/null
ck StopFailure DDDDDDDD ',"error":"overloaded"' >/dev/null
check no "$(has "$(ckcli status)" '沒有正常結束\|API 錯誤')" "沒動工作樹的 session 失敗 → 不算中斷，也不蓋掉別人的狀態"

ckcli close >/dev/null
check 0 "$(ck SessionStart EEEEEEEE ',"source":"startup"' | grep -c .)" "工作結束（close）→ 開工不再提示"

# 程序身分：沒有結束標記時，程序還活著＝還在跑，死了＝中斷（docs/lessons/0011）
LIVEPID=$(cat /proc/$$/winpid 2>/dev/null || echo $$)   # Git Bash 的 $$ 不是 Windows pid
DEADPID=999999
CKPID=$LIVEPID; ck PostToolUse LLLLLLLL ',"tool_name":"Edit"' >/dev/null
CKPID=77777777; out=$(ck SessionStart NNNNNNNN ',"source":"startup"')
check 0 "$(printf '%s' "$out" | grep -c '斷點')" "另一個程序還活著、回合沒結束 → 是並行不是中斷，開工不提示"
check yes "$(has "$(ckcli status)" '正在這個工作樹上工作')" "status 仍指出有另一個程序在同一個工作樹上"
CKPID=$LIVEPID; check no "$(has "$(ckcli status)" '沒有正常結束')" "呼叫者自己的程序回合還沒結束 → 不把自己當成中斷"
ckcli close >/dev/null

CKPID=$DEADPID; ck UserPromptSubmit XXXXXXXX ',"prompt":"改完 z 並推上去"' >/dev/null
ck UserPromptSubmit XXXXXXXX ',"prompt":"<task-notification>背景工作完成</task-notification>"' >/dev/null
ck PostToolUse XXXXXXXX ',"tool_name":"Edit"' >/dev/null
( cd "$CK" && echo foreign > foreign.txt )
CKPID=$LIVEPID; ck SessionStart YYYYYYYY ',"source":"startup"' >/dev/null
( cd "$CK" && echo mine > mine.txt ); ck PostToolUse YYYYYYYY ',"tool_name":"Write"' >/dev/null
out=$(ckcli resume)
check yes "$(has "$out" '沒有正常結束')" "程序已經死了、回合沒結束 → 中斷；新 session 先做了別的事再查也一樣認得出來"
check yes "$(has "$out" '改完 z 並推上去')" "中斷前的要求取使用者的話，不取系統插進來的通知"
check yes "$(has "$out" '開工之前被改過的檔案（不是上一段 agent 留下的）：foreign.txt')" "開工前別人改的指認出來"
check no "$(has "$out" 'mine.txt——')" "開工後自己改的不算成別人的"
CKPID=88888888
nb=$(grep -c '"kind": "base"' "$CK/.git/serendipity/journal.jsonl")
check 0 "$(SE_EVAL=1 ck SessionStart ZZZZZZZZ ',"source":"startup"' | grep -c .)" "觸發評測的 session（SE_EVAL）有斷點也不印簡報——簡報點名 se-resume"
check $((nb + 1)) "$(grep -c '"kind": "base"' "$CK/.git/serendipity/journal.jsonl")" "SE_EVAL 下照常記錄（開工基準仍寫入）"
CKPID=""
check no "$( [ -s "$CK/.git/serendipity/error.log" ] && echo yes || echo no)" "整個過程記錄器沒有出錯"

# ---------- 結果 ----------
echo ""
echo "通過 $pass／失敗 $fail"
[ "$fail" -eq 0 ] || exit 1
