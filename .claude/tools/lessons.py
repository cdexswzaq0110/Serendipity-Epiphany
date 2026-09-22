#!/usr/bin/env python3
"""跨專案領悟帳本：一個專案學到的，另一個專案用得到。

**這是遷移，是通用性的核心。** 沒有它，每開一個新專案都從零開始學——
2026-09 的實際狀況：Serendipity 7 則、churn-guard 2 則，互相引用 0 次。

帳本位置：`$SERENDIPITY_HOME/lessons/`（預設 `~/.claude/serendipity/lessons/`）。
它本身是一個 git repo：全域記憶沒有版控，就沒有溯源也沒有回滾。

**上架門檻比升級成常駐規則還嚴**，因為擴散半徑不同——專案裡的一則髒 lesson
只污染一個專案，全域的一則髒 lesson 污染**每一個**專案。三關：

  1. source 不得是 external        外部說法沒有本地失敗證據
  2. seen_in 至少兩個不同專案       這是天然的跨專案 VALIDATE，比單一 repo 的 hits 強得多
  3. generalizes_to 必須有值        上架的是類別，不是某個專案的實例

用法：
    python .claude/tools/lessons.py init
    python .claude/tools/lessons.py list [--tag 關鍵字]
    python .claude/tools/lessons.py promote docs/lessons/0005-x.md \\
        --seen-in "專案A" --seen-in "專案B" --evidence "兩邊各自發生的具體描述"
    python .claude/tools/lessons.py check
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HOME = Path(os.environ.get("SERENDIPITY_HOME", Path.home() / ".claude" / "serendipity"))
STORE = HOME / "lessons"
INDEX = STORE / "INDEX.md"
ALLOWED = {"self-observed", "user-stated"}

INDEX_HEAD = """# 全域領悟帳本

**跨專案的長期記憶。一則一行，內容在各自的檔案裡。**

上架門檻：source 不是 external、seen_in 至少兩個不同專案、generalizes_to 有值。
由 `.claude/tools/lessons.py` 維護；本目錄是獨立 git repo，溯源與回滾用 `git log`。

| ID | 一句話 | 類別 | seen_in |
|---|---|---|---|
"""


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(STORE), capture_output=True, text=True)


def _split(text: str) -> tuple[dict, str, str]:
    """回傳 (欄位, 原始 frontmatter, 內文)。"""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, "", text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.split("#")[0].strip()
    return fm, m.group(1), m.group(2)


def _title(body: str) -> str:
    m = re.search(r"^# (.+)$", body, re.M)
    return m.group(1).strip() if m else "（無標題）"


def cmd_init(_a) -> int:
    STORE.mkdir(parents=True, exist_ok=True)
    if not INDEX.exists():
        INDEX.write_text(INDEX_HEAD, encoding="utf-8", newline="\n")
    if not (STORE / ".git").exists():
        _git("init", "-q", "-b", "main")
        _git("add", "-A")
        _git("-c", "user.name=serendipity", "-c", "user.email=serendipity@local",
             "commit", "-q", "-m", "init: 全域領悟帳本")
    print(f"帳本位置：{STORE}")
    return 0


def cmd_list(a) -> int:
    if not INDEX.exists():
        print("全域帳本還不存在。先跑 `lessons.py init`。")
        return 0
    rows = [l for l in INDEX.read_text(encoding="utf-8").splitlines() if l.startswith("| [G")]
    if a.tag:
        rows = [r for r in rows if a.tag.lower() in r.lower()]
    print("\n".join(rows) if rows else "（沒有符合的全域 lesson）")
    return 0


def gate(fm: dict, seen_in: list[str]) -> list[str]:
    """上架三關。回傳沒過的理由；空清單 = 通過。"""
    why = []
    src = fm.get("source", "")
    if src not in ALLOWED:
        why.append(f"source='{src or '（空）'}'：只接受 {sorted(ALLOWED)}——外部說法沒有本地失敗證據")
    distinct = sorted({s.strip() for s in seen_in if s.strip()})
    if len(distinct) < 2:
        why.append(f"seen_in 只有 {len(distinct)} 個專案 {distinct}：至少要在兩個不同專案各自撞到過")
    if not fm.get("generalizes_to"):
        why.append("generalizes_to 是空的：上架的是類別，不是某個專案的實例")
    return why


def cmd_promote(a) -> int:
    src = Path(a.lesson)
    if not src.exists():
        print(f"找不到 {src}", file=sys.stderr)
        return 2
    fm, raw, body = _split(src.read_text(encoding="utf-8"))
    why = gate(fm, a.seen_in)
    if why:
        print("✗ 不得上架全域帳本：", file=sys.stderr)
        for w in why:
            print(f"  - {w}", file=sys.stderr)
        return 2
    if not STORE.exists():
        cmd_init(a)

    slug = re.sub(r"^\d+-", "", src.stem)
    if any(slug in p.name for p in STORE.glob("G[0-9]*.md")):
        print(f"✗ 已經上架過（{slug}）", file=sys.stderr)
        return 2

    n = len(list(STORE.glob("G[0-9]*.md"))) + 1
    gid = f"G{n:04d}"
    seen = sorted({s.strip() for s in a.seen_in if s.strip()})
    extra = (f"global_id: {gid}\norigin: {src.as_posix()}\npromoted_at: {date.today()}\n"
             "seen_in:\n" + "".join(f"  - {s}\n" for s in seen))
    evidence = f"\n## 跨專案證據（上架依據）\n\n{a.evidence}\n" if a.evidence else ""
    out = STORE / f"{gid}-{slug}.md"
    out.write_text(f"---\n{raw}\n{extra}---\n{body.rstrip()}\n{evidence}",
                   encoding="utf-8", newline="\n")

    with open(INDEX, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"| [{gid}]({out.name}) | {_title(body)} | {fm['generalizes_to'][:40]} "
                 f"| {'、'.join(seen)} |\n")

    _git("add", "-A")
    _git("-c", "user.name=serendipity", "-c", "user.email=serendipity@local",
         "commit", "-q", "-m", f"promote {gid}: {slug}（seen_in: {', '.join(seen)}）")
    print(f"✓ 已上架 {gid}：{out}")
    return 0


def cmd_check(_a) -> int:
    if not STORE.exists():
        print("全域帳本不存在（尚未 init）——沒有東西可檢查")
        return 0
    problems = []
    index_text = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    for p in sorted(STORE.glob("G[0-9]*.md")):
        fm, raw, _ = _split(p.read_text(encoding="utf-8"))
        seen = re.findall(r"^\s+- (.+)$", raw.split("seen_in:", 1)[1], re.M) if "seen_in:" in raw else []
        for w in gate(fm, seen):
            problems.append(f"{p.name}：{w}")
        if p.name not in index_text:
            problems.append(f"{p.name}：檔案存在但 INDEX 未列出")
    for name in re.findall(r"\((G[0-9][\w-]*\.md)\)", index_text):
        if not (STORE / name).exists():
            problems.append(f"INDEX 指向不存在的 {name}")
    if problems:
        print("✗ 全域帳本檢查未通過：", file=sys.stderr)
        for w in problems:
            print(f"  - {w}", file=sys.stderr)
        return 2
    print(f"✓ 全域帳本一致：{len(list(STORE.glob('G[0-9]*.md')))} 則")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    pl = sub.add_parser("list")
    pl.add_argument("--tag")
    pp = sub.add_parser("promote")
    pp.add_argument("lesson")
    pp.add_argument("--seen-in", action="append", default=[])
    pp.add_argument("--evidence", default="")
    sub.add_parser("check")
    a = ap.parse_args()
    return {"init": cmd_init, "list": cmd_list, "promote": cmd_promote,
            "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
