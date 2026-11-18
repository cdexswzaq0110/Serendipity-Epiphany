"""Serendipity hooks 共用函式（Python 3.11 標準庫）。"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

for _stream in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

COMMAND_PREFIX = re.compile(r"(?:^|&&|;|\||\n|\(|\b(?:do|then|else)\b)\s*$", re.I)
GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path"}
TOKEN = re.compile(r'''(?:"(?:\\.|[^"\\])*"|'[^']*'|[^\s;&|()]+)''')
PROTECTED_PATH = re.compile(r"(?:^|[\\/])(?:\.env(?:\.|$)|secrets?|credentials?|\.ssh)(?:[\\/]|$)", re.I)
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit"}


class HookFailure(Exception):
    pass


def root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()


def read_payload(require_tool: bool = True) -> tuple[str, dict[str, Any]]:
    raw = sys.stdin.read()
    value = json.loads(raw)
    if not isinstance(value, dict) or (require_tool and not isinstance(value.get("tool_name"), str)):
        raise HookFailure("payload 格式不正確")
    return raw, value


def command(payload: dict[str, Any]) -> str:
    value = payload.get("tool_input")
    return str(value.get("command", "")) if isinstance(value, dict) else ""


def strip_heredocs(text: str) -> str:
    """移除 heredoc 內文；保留宣告行，未結束時丟棄其後內容。"""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    active: tuple[str, bool] | None = None
    marker = re.compile(r"(?<!<)<<(-)?\s*([\"']?)([A-Za-z_][A-Za-z0-9_]*)\2")
    for line in lines:
        if active:
            delimiter, tabs = active
            candidate = line.rstrip("\r\n")
            if tabs:
                candidate = candidate.lstrip("\t")
            if candidate == delimiter:
                active = None
                out.append("\n")
            continue
        out.append(line)
        match = marker.search(line)
        if match:
            active = (match.group(3), bool(match.group(1)))
    return "".join(out)


SEGMENT_END = re.compile(r"&&|\|\||[;|\n)]")


def is_git_cmd(command_text: str, subcommand_regex: str) -> bool:
    """判定 git 是否出現在 shell 指令位置，且子指令符合 regex（main 的 _command.sh，docs/lessons/0009）。

    每一個出現在指令位置的 git 都要看：`git add . && git commit` 的第二個才是 commit。
    只看這一段指令（到 && || ; | 換行 ) 為止），跳過全域選項（-C <dir>、-c k=v、--no-pager）。
    區分大小寫：`branch -d` 是安全的刪除，`branch -D` 才是強制刪除。
    """
    text = strip_heredocs(command_text)
    for match in re.finditer(r"\bgit\b", text):
        if not COMMAND_PREFIX.search(text[:match.start()]):
            continue
        rest = text[match.end():]
        cut = SEGMENT_END.search(rest)
        tokens = TOKEN.findall(rest[:cut.start()] if cut else rest)
        i = 0
        while i < len(tokens) and tokens[i].startswith("-"):
            i += 2 if tokens[i] in GLOBAL_WITH_VALUE else 1
        if i < len(tokens) and re.match(rf"(?:{subcommand_regex})", " ".join(tokens[i:])):
            return True
    return False


def git(project: Path, *args: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-c", f"safe.directory={project.as_posix()}", *args], cwd=project,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def changed_paths(project: Path) -> list[str] | None:
    probe = git(project, "rev-parse", "--is-inside-work-tree")
    if probe.returncode:
        return None
    result = git(project, "status", "--porcelain", "--untracked-files=all")
    if result.returncode:
        raise HookFailure("無法讀取 git status")
    paths = []
    for line in result.stdout.splitlines():
        p = line[3:].strip('"')
        paths.append(p.split(" -> ")[-1])
    return paths


def break_glass(project: Path) -> bool:
    marker = project / ".claude/hooks/BREAK_GLASS"
    if not marker.is_file():
        return False
    marker.unlink()
    print("[SE-HOOK-BREAK-GLASS] 已使用並刪除一次性 BREAK_GLASS；本次放行。", file=sys.stderr)
    return True


def high_risk(raw: str, project: Path) -> bool:
    if PROTECTED_PATH.search(raw) or re.search(r"git(?:\\?\"|\s)+(?:.*\s)?(?:reset.*--hard|push.*(?:--force|-f\b)|branch.*-D\b|rebase\b)", raw, re.I):
        return True
    if any(x in raw for x in ('"Edit"', '"Write"', '"NotebookEdit"', "git commit")):
        try:
            return git(project, "branch", "--show-current").stdout.strip() in {"main", "master"}
        except Exception:
            return True
    return False


def mode_result(mode: str) -> int:
    return 2 if mode == "block" else 1


def run_gate(name: str, callback: Callable[[dict[str, Any], Path], int]) -> int:
    project = root()
    raw = sys.stdin.read()
    try:
        if break_glass(project):
            return 0
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("tool_name"), str):
            raise HookFailure("payload 格式不正確")
        if os.environ.get("SE_HOOK_FORCE_ERROR") == "1":
            raise RuntimeError("測試用內部例外")
        return callback(payload, project)
    except Exception as error:
        if high_risk(raw, project):
            print(f"[{name}-INTERNAL] hook 內部錯誤且操作屬高風險，先擋下：{error}", file=sys.stderr)
            print("修復：python -m unittest discover -s tests", file=sys.stderr)
            return 2
        print(f"[{name}-INTERNAL] hook 內部錯誤；本次低風險操作放行：{error}", file=sys.stderr)
        print("修復：python -m unittest discover -s tests", file=sys.stderr)
        return 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_sync(project: Path):
    path = project / "scripts/sync_skills.py"
    spec = importlib.util.spec_from_file_location("se_sync_skills", path)
    if not spec or not spec.loader:
        raise HookFailure("無法載入 scripts/sync_skills.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
