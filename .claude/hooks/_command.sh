# 被 hook source 的共用判定：這條 Bash 指令，有沒有在「指令位置」呼叫某個 git 子指令。
# 不是 hook 本身，不註冊在 settings.json。
#
# 為什麼不交給 settings.json 的 if：if 只是預篩，遇到 for／while 迴圈會照樣觸發
# （docs/lessons/0009）。
# 為什麼要先去掉 heredoc：heredoc 內文是資料（commit message、python 腳本）——
# 一段描述 `do git branch -D` 的 commit message 不是 git 操作。

# git 出現在這些位置之後才算指令：command 開頭、&& ; | 換行 ( 之後、do then else 之後。
CMD_POS='("command"[[:space:]]*:[[:space:]]*"|&&|;|[|]|\\n|[(]|^|(^|[[:space:]])(do|then|else))[[:space:]]*'
# git 與子指令之間可以夾全域選項：-C <dir>、-c k=v、--no-pager
GIT_OPTS='([[:space:]]+-[^[:space:]"]+([[:space:]]+[^-[:space:]"][^[:space:]"]*)?)*'

# payload 是單行 JSON，換行是字面的 \n。未結束的 heredoc，其後全部視為內文（bash 也這樣解讀）。
strip_heredocs() {
  awk '{
    s = $0; out = ""
    while (match(s, /<<-?[[:space:]]*\\?["\047]?[A-Za-z_][A-Za-z0-9_]*\\?["\047]?/)) {
      if (RSTART > 1 && substr(s, RSTART - 1, 1) == "<") {   # <<< 是 here-string，不是 heredoc
        out = out substr(s, 1, RSTART + 1); s = substr(s, RSTART + 2); continue
      }
      tok = substr(s, RSTART, RLENGTH)
      out = out substr(s, 1, RSTART + RLENGTH - 1)
      s = substr(s, RSTART + RLENGTH)
      d = tok; sub(/^<<-?[[:space:]]*/, "", d); gsub(/[\\"\047]/, "", d)
      e = index(s, "\\n" d "\\n")
      if (e == 0) e = index(s, "\\n" d "\"")
      if (e == 0) { s = ""; break }
      s = substr(s, e + 2 + length(d))
    }
    print out s
  }'
}

is_git_cmd() {  # is_git_cmd <payload> <子指令 ERE>
  printf '%s' "$1" | strip_heredocs | grep -Eq "${CMD_POS}git${GIT_OPTS}[[:space:]]+($2)"
}
