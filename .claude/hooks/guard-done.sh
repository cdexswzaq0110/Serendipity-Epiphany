#!/usr/bin/env bash
# Stop gate：結束之前自檢，沒過就繼續修——自主自控的「自控」那一半。
#
# 為什麼：自主的反面不是「需要人」，是「做到一半就停、留下壞掉的狀態」。
# 這個 hook 讓 agent 在宣告結束前，先確認自己沒有把配置留在不一致的狀態。
#
# 邊界（這是「自控」的定義所在）：
#   - 只強制繼續**一次**。stop_hook_active=true 代表這次停止已經是被擋過之後的第二次，
#     放行。沒有這條，一個 agent 修不好的問題會變成無限迴圈。
#   - 只檢查**確定性**的東西（router 與記憶層一致性），不判斷「做得好不好」——
#     那是語意判斷，不該由一支 shell 腳本強制。
#   - 不替人做決策。它只擋「留下壞掉的狀態就走」，不擋「停下來問人」。
#
# stop_hook_active 欄位於 2026-09-22 實測確認存在（第一次停止時為 false）。
set -uo pipefail

MODE="${SE_GUARD_DONE_MODE:-block}"
ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
HOOKS="$ROOT/.claude/hooks"

payload=$(cat 2>/dev/null || true)

# 已經被擋過一次 → 放行。這一行是整個自控邊界。
if printf '%s' "$payload" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

# 不是這套配置的 repo → 放行
[ -f "$ROOT/.claude/skills/INDEX.md" ] || exit 0

fake='{"tool_name":"Bash","tool_input":{"command":"git commit"}}'
problems=""
for check in check-router.sh check-memory.sh; do
  [ -f "$HOOKS/$check" ] || continue
  out=$(printf '%s' "$fake" | CLAUDE_PROJECT_DIR="$ROOT" bash "$HOOKS/$check" 2>&1 >/dev/null)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    problems="$problems
--- $check ---
$out"
  fi
done

if [ -z "$problems" ]; then
  # 學習訊號：這一回合有「同一種指令先失敗、後來改對」而帳本沒被寫過 → 提醒一次。
  # 兩輪端到端基準 14 次一則 lesson 都沒留（含 commit 被 hook 拒、看了訊息才改對的案例）：
  # 捕捉靠模型收尾時想起來，單次任務沒有收尾的時刻（docs/lessons/0013）。
  # 不是閘：只問一次（stop_hook_active），評測（SE_EVAL）與 SE_LEARN_NUDGE=off 時不問。
  if [ -z "${SE_EVAL:-}" ] && [ "${SE_LEARN_NUDGE:-on}" != "off" ] && [ -d "$ROOT/docs/lessons" ]; then
    PY=$(command -v python || command -v python3) || exit 0
    hits=$(cd "$ROOT" && "$PY" "$HOOKS/../tools/checkpoint.py" learned 2>/dev/null)
    if [ $? -eq 3 ]; then  # 只認 exit 3——其他輸出（例如「不在 git repo 裡」）不是學習訊號
      {
        echo "[guard-done] 這一回合有「撞到才改對」的情形："
        echo "$hits"
        echo "如果其中有下一輪還會撞到、而且在環境裡（程式碼、git log、錯誤訊息）查不到的東西，"
        echo "用 se-epiphany 的捕捉模式寫進 docs/lessons/；沒有就直接結束——這個提醒只出現一次。"
      } >&2
      [ "$MODE" = "block" ] && exit 2
      exit 1
    fi
  fi
  exit 0
fi

cat >&2 <<EOF
[guard-done] 結束前自檢未通過——配置目前處於不一致的狀態，先修好再結束。
$problems

修完後再結束即可。這個檢查只會強制繼續一次；若確實無法在這一輪修好，
下一次結束會放行——請在回覆裡明說哪裡還不一致、為什麼沒修。
（由 .claude/hooks/guard-done.sh 強制；目前模式 $MODE）
EOF
[ "$MODE" = "block" ] && exit 2
exit 1
