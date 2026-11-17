"""Claude Code PreToolUse gates 共用核心（只用標準庫）。"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DESTRUCTIVE = re.compile(r"(?:^|[;&|]\s*)git\s+(?:reset\b[^\r\n]*--hard|push\b[^\r\n]*(?:--force(?:-with-lease)?|-f\b)|branch\b[^\r\n]*-D\b|rebase\b)", re.I)
RAW_DESTRUCTIVE = re.compile(r"git(?:\\?\"|\s)+(?:(?:reset\b[^\r\n]*--hard)|(?:push\b[^\r\n]*(?:--force(?:-with-lease)?|-f\b))|(?:branch\b[^\r\n]*-D\b)|rebase\b)", re.I)
PROTECTED_PATH = re.compile(r"(?:^|[\\/])(?:\.env(?:\.|$)|secrets?|credentials?|\.ssh)(?:[\\/]|$)", re.I)
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit"}


class HookFailure(Exception):
    pass


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()


def break_glass(root: Path) -> bool:
    marker = root / ".claude" / "hooks" / "BREAK_GLASS"
    if not marker.is_file():
        return False
    marker.unlink()
    print("[SE-HOOK-BREAK-GLASS] 已使用並刪除一次性 BREAK_GLASS；本次放行。", file=sys.stderr)
    return True


def command(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    return tool_input.get("command", "") if isinstance(tool_input, dict) else ""


def file_path(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    return str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=4,
    )


def current_branch(root: Path) -> str:
    result = git(root, "branch", "--show-current")
    if result.returncode:
        return ""
    return result.stdout.strip()


def is_write(payload: dict[str, Any]) -> bool:
    tool = payload.get("tool_name")
    return tool in WRITE_TOOLS or (tool == "Bash" and bool(re.search(r"\bgit\s+commit\b", command(payload))))


def raw_high_risk(raw: str, root: Path) -> bool:
    if RAW_DESTRUCTIVE.search(raw) or PROTECTED_PATH.search(raw):
        return True
    looks_write = any(token in raw for token in ('"Edit"', '"Write"', '"NotebookEdit"', "git commit"))
    try:
        return looks_write and current_branch(root) in {"main", "master"}
    except Exception:
        return looks_write


def deny(code: str, message: str, root: Path) -> int:
    print(f"[{code}] {message}", file=sys.stderr)
    print("修復後重試；緊急時建立一次性檔案：", file=sys.stderr)
    print(f"  {root / '.claude' / 'hooks' / 'BREAK_GLASS'}", file=sys.stderr)
    print("暫時停用：從 .claude/settings.json 移除對應 hook，修復後立即還原。", file=sys.stderr)
    return 2


def parse(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("tool_name"), str):
        raise HookFailure("payload 必須包含字串 tool_name")
    return value


def branch_gate(payload: dict[str, Any], root: Path) -> tuple[bool, str]:
    if not is_write(payload):
        return False, ""
    branch = current_branch(root)
    if branch in {"main", "master"}:
        return True, f"目前在受保護分支 {branch}，請先建立 feature branch。"
    return False, ""


def critical_gate(payload: dict[str, Any], root: Path) -> tuple[bool, str]:
    cmd = command(payload)
    if not DESTRUCTIVE.search(cmd):
        return False, ""
    head = git(root, "rev-parse", "HEAD")
    if head.returncode:
        raise HookFailure("無法讀取目前 HEAD")
    tags = git(root, "tag", "--points-at", head.stdout.strip(), "--list", "backup/*")
    if tags.returncode:
        raise HookFailure("無法讀取 backup tags")
    if tags.stdout.strip():
        return False, ""
    return True, "破壞性 Git 操作前，必須先建立指向目前 HEAD 的 backup/* tag。"


def router_gate(payload: dict[str, Any], root: Path) -> tuple[bool, str]:
    if not re.search(r"\bgit\s+commit\b", command(payload)):
        return False, ""
    skill_root = root / ".claude" / "skills"
    index = skill_root / "INDEX.md"
    if not skill_root.is_dir() or not index.is_file():
        return False, ""
    text = index.read_text(encoding="utf-8")
    directories = {p.name for p in skill_root.iterdir() if p.is_dir() and p.name != "extended"}
    directories |= {p.name for p in (skill_root / "extended").iterdir()} if (skill_root / "extended").is_dir() else set()
    listed = set(re.findall(r"`(se-[a-z0-9-]+)`", text))
    missing = sorted(directories - listed)
    stale = sorted(listed - directories)
    if missing or stale:
        return True, f"skills/INDEX.md 不一致；漏列={missing}，失效={stale}。"
    return False, ""


GATES = {"branch": branch_gate, "critical": critical_gate, "router": router_gate}


def run(kind: str) -> int:
    root = project_root()
    raw = sys.stdin.read()
    if break_glass(root):
        return 0
    try:
        if os.environ.get("SE_HOOK_FORCE_ERROR") == "1":
            raise RuntimeError("測試用內部例外")
        payload = parse(raw)
        blocked, message = GATES[kind](payload, root)
        if blocked:
            return deny(f"SE-HOOK-{kind.upper()}-DENY", message, root)
        return 0
    except Exception as error:
        if raw_high_risk(raw, root):
            return deny("SE-HOOK-INTERNAL-HIGH-RISK", f"hook 內部錯誤且操作屬高風險：{error}", root)
        print(f"[SE-HOOK-INTERNAL-LOW-RISK] hook 內部錯誤，本次低風險操作放行：{error}", file=sys.stderr)
        print("修復：python -m unittest tests.test_hooks -v", file=sys.stderr)
        return 0
