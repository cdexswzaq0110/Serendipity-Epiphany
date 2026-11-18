"""PreToolUse gate：不准丟掉「開工前就存在」的未提交變更（main 的 guard-discard.sh，docs/lessons/0014）。

判斷在 tools/checkpoint.py discard-check；這支只做快速預篩，一般的 Bash 呼叫不必再起一個 python。
使用者明確同意後，在指令前加 SE_ALLOW_DISCARD=1 放行。
"""
import json, os, re, subprocess, sys
from pathlib import Path

DEFAULT_MODE = "block"
CHECKPOINT = Path(__file__).resolve().parents[1] / "tools" / "checkpoint.py"


def needs_check(cmd: str) -> bool:
    if re.search(r"(?:^|[^\w-])rm\s", cmd):
        return True
    try:
        from hooklib import is_git_cmd
    except Exception:  # 判定規則缺席：不預篩，交給 checkpoint.py 判斷
        return True
    return is_git_cmd(cmd, r"restore|checkout|clean|reset")


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        value = json.loads(raw)
        tool_input = value.get("tool_input") if isinstance(value, dict) else None
        cmd = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    except Exception:
        return 0  # 不是 Bash 指令的 payload，這道閘不管
    if not cmd or not needs_check(cmd) or not CHECKPOINT.is_file():
        return 0
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        return subprocess.run([sys.executable, str(CHECKPOINT), "discard-check"], input=raw, text=True,
                              encoding="utf-8", cwd=project, timeout=14).returncode
    except Exception:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
