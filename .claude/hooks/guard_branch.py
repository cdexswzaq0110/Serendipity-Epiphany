import os, sys
try:
    from hooklib import command, git, is_git_cmd, mode_result, run_gate
except Exception as error:
    print(f"[guard-branch] 無法載入 hooklib（{error}），無法確認分支。", file=sys.stderr)
    raise SystemExit(2 if os.environ.get("SE_GUARD_BRANCH_MODE", "warn") == "block" else 1)

MODE_ENV = "SE_GUARD_BRANCH_MODE"
DEFAULT_MODE = "warn"

def gate(payload, root):
    if payload.get("tool_name") == "Bash" and not is_git_cmd(command(payload), r"commit"):
        return 0
    if payload.get("tool_name") not in {"Bash", "Edit", "Write", "NotebookEdit"}:
        return 0
    if git(root, "rev-parse", "--is-inside-work-tree").returncode:
        return 0
    branch = git(root, "branch", "--show-current").stdout.strip()
    if branch not in {"main", "master"}:
        return 0
    mode = os.environ.get(MODE_ENV, DEFAULT_MODE)
    print(f"[guard-branch] 目前在受保護分支 '{branch}'，不可直接修改工作樹。\n\n先開分支再繼續：\n  git checkout -b feature/<task-name>\n\n（rules/git-workflow.md 鐵律；目前模式 {mode}）", file=sys.stderr)
    return mode_result(mode)

if __name__ == "__main__":
    raise SystemExit(run_gate("guard-branch", gate))
