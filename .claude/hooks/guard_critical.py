import datetime, os, sys
try:
    from hooklib import command, git, is_git_cmd, mode_result, run_gate
except Exception as error:  # 判定規則缺席：往安全的方向失敗
    print(f"[guard-critical] 無法載入 hooklib（{error}），判定不了是不是破壞性操作，先擋下。", file=sys.stderr)
    raise SystemExit(2)

MODE_ENV = "SE_GUARD_CRITICAL_MODE"
DEFAULT_MODE = "block"
DESTRUCTIVE = r"reset\s+.*--hard|push\s+.*(?:--force|-f(?:\s|$))|branch\s+.*-D(?:\s|$)|rebase(?:\s|$)"

def gate(payload, root):
    if not is_git_cmd(command(payload), DESTRUCTIVE): return 0
    if git(root, "rev-parse", "--is-inside-work-tree").returncode: return 0
    rev = git(root, "rev-parse", "HEAD")
    if rev.returncode: return 0
    head = rev.stdout.strip()
    tags = git(root, "tag", "--points-at", head, "--list", "backup/*")
    if tags.stdout.strip(): return 0
    branch = git(root, "branch", "--show-current").stdout.strip() or "detached"
    short = head[:7]
    suggested = f"backup/{branch}-{datetime.date.today().isoformat()}"
    mode = os.environ.get(MODE_ENV, DEFAULT_MODE)
    print(f"[guard-critical] 破壞性 git 操作前必須先打 backup tag。\n\n目前 HEAD ({short}) 沒有指向它的 backup/* tag。先執行：\n  git tag -a \"{suggested}\" -m \"安全快照, tip {short}\"\n\n恢復路徑：\n  git reset --hard \"{suggested}\"\n\n（目前模式 {mode}）", file=sys.stderr)
    return mode_result(mode)

if __name__ == "__main__": raise SystemExit(run_gate("guard-critical", gate))
