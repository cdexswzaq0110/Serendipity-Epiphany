"""PreToolUse gate（git commit 時）：維護契約 #1「Router 不說謊」。

兩種模式，依專案自動選：
- **canonical 模式**（Serendipity 本身：有 `skills/` 與 `scripts/sync_skills.py`）：
  1. `skills/` 的核心與延伸目錄 vs `skills/INDEX.md`：目錄沒被提到 → 漏列；反引號裡的 `se-*` 找不到目錄 → 失效
  2. 常駐檔的 `/se-xxx` 必須存在於安裝後的 `.claude/skills/`
  3. `.claude/skills/` 必須等於 canonical 的 flat 投影（只比內容 hash，不比 source_commit 等來源欄位）
- **安裝模式**（用 /se-bootstrap 帶進其他專案、只有 `.claude/`）：與 main 的 check-router.sh 相同，
  檢查 `.claude/skills/` 的目錄 vs `.claude/skills/INDEX.md`，以及常駐檔的 `/se-xxx`。

這次的改動沒碰到路由相關的檔案就跳過（完整掃描在 Windows 上要 1 秒多，2026-09-24 基準量到）。
"""
import os
import re
import sys
from pathlib import Path

MODE_ENV = "SE_CHECK_ROUTER_MODE"
DEFAULT_MODE = "block"
WATCH = re.compile(r"^(?:skills/|\.claude/(?:skills/|rules/|CLAUDE\.md$)|CLAUDE\.md$|scripts/sync_skills\.py$)")

try:
    from hooklib import changed_paths, command, is_git_cmd, load_sync, mode_result, run_gate
except Exception as error:  # 判定規則缺席：往安全的方向失敗（main 的 selftest「退回一律檢查」）
    print(f"[check-router] 無法載入 hooklib（{error}），判定不了，先擋下。修好 .claude/hooks/hooklib.py 再 commit。", file=sys.stderr)
    raise SystemExit(2)


def skill_dirs(base: Path) -> set[str]:
    return {p.name for p in base.iterdir() if p.is_dir() and p.name != "extended"} if base.is_dir() else set()


def index_problems(dirs: set[str], index: Path) -> tuple[list[str], list[str]]:
    text = index.read_text(encoding="utf-8")
    listed = set(re.findall(r"`(se-[a-z0-9-]+)`", text))
    missing = sorted(d for d in dirs if d not in text)
    stale = sorted(listed - dirs)
    return missing, stale


def drift(root: Path, canonical: Path, installed: Path) -> list[str]:
    sync = load_sync(root)
    pairs, _skipped = sync.flat_plan(canonical)
    expected = {dst: sync.file_hash(canonical / src) for src, dst in pairs}
    manifest, problems = sync.load_manifest(installed)
    if manifest is None or problems:
        return [f"manifest：{p}" for p in problems] or ["manifest 無法讀取"]
    recorded = {f["path"]: f["sha256"] for f in manifest["files"] if isinstance(f, dict)}
    out = [f"缺：{p}" for p in sorted(expected.keys() - recorded.keys())]
    out += [f"多：{p}" for p in sorted(recorded.keys() - expected.keys())]
    out += [f"manifest 與 canonical 不同：{p}" for p in sorted(expected.keys() & recorded.keys()) if expected[p] != recorded[p]]
    out += [f"安裝檔被改過：{p}" for p in sorted(expected) if (installed / p).is_file() and sync.file_hash(installed / p) != expected[p]]
    return out


def gate(payload, root: Path) -> int:
    if not is_git_cmd(command(payload), r"commit"):
        return 0
    changed = changed_paths(root)
    if changed is not None and not any(WATCH.search(p.replace("\\", "/")) for p in changed):
        return 0
    canonical, installed = root / "skills", root / ".claude" / "skills"
    canonical_mode = (canonical / "INDEX.md").is_file() and (root / "scripts" / "sync_skills.py").is_file()
    if canonical_mode:
        dirs = skill_dirs(canonical) | skill_dirs(canonical / "extended")
        missing, stale = index_problems(dirs, canonical / "INDEX.md")
        moved = drift(root, canonical, installed) if installed.is_dir() else ["尚未安裝 .claude/skills"]
    elif (installed / "INDEX.md").is_file():
        missing, stale = index_problems(skill_dirs(installed), installed / "INDEX.md")
        moved = []
    else:
        return 0  # 不是這套配置的專案
    dangling = []
    for f in [root / "CLAUDE.md", root / ".claude" / "CLAUDE.md", *sorted((root / ".claude" / "rules").glob("*.md"))]:
        if f.is_file():
            for name in sorted(set(re.findall(r"/(se-[a-z0-9-]+)", f.read_text(encoding="utf-8")))):
                if not (installed / name).is_dir():
                    dangling.append(f"{f.name}:{name}")
    if not (missing or stale or dangling or moved):
        return 0
    mode = os.environ.get(MODE_ENV, DEFAULT_MODE)
    where = "skills/INDEX.md" if canonical_mode else ".claude/skills/INDEX.md"
    print("[check-router] 維護契約 #1 違反：Router 與實際目錄不一致。", file=sys.stderr)
    if missing:
        print(f"  目錄存在但 {where} 未列出: {' '.join(missing)}", file=sys.stderr)
    if stale:
        print(f"  {where} 提到但目錄不存在: {' '.join(stale)}", file=sys.stderr)
    if dangling:
        print(f"  常駐檔指向不存在的 skill: {' '.join(dangling)}", file=sys.stderr)
    if moved:
        print("  .claude/skills 與 canonical 的 flat 投影不一致:", *moved[:10], sep="\n    ", file=sys.stderr)
        print("  重新同步：python scripts/sync_skills.py build --out <暫存資料夾>，再 install --bundle <暫存資料夾> --dest .claude/skills --layout flat", file=sys.stderr)
    print(f"（由 .claude/hooks/check_router.py 強制；目前模式 {mode}）", file=sys.stderr)
    return mode_result(mode)


if __name__ == "__main__":
    raise SystemExit(run_gate("check-router", gate))
