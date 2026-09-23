#!/usr/bin/env python3
"""候選 skill 升級成正式 skill 的閘門——學習新技能的 SOLIDIFY 關。

**候選 skill 放在 `.claude/skill-candidates/`，Claude Code 不會自動載入它。**
這是刻意的：一個還沒被驗證的做法，不該在沒人察覺的情況下開始影響路由。
直接生成就直接載入，是影片判成「半成品」的那條路（外掛知識庫、無驗證閉環）。

四道閘，對應 se-epiphany 的 GEP 四關：

  SCAN      SKILL.md 存在，name 與目錄一致，description 有觸發條件
  VALIDATE  frontmatter 的 validated 有值：這套做法**實際用過且成功**，寫得出在哪
  MUTATE    evals/trigger-cases.md 至少 3 條**獨立來源**正例（session-trace／user-prompt）
            ——不是照 description 寫的，那種案例不可能失敗
  SOLIDIFY  名稱不與既有 skill 衝突；通過後才搬進 skills/ 並寫進 INDEX

用法：
    python .claude/tools/promote_skill.py <候選名稱> --dry-run   # 只檢查
    python .claude/tools/promote_skill.py <候選名稱>             # 檢查並升級
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
CAND = ROOT / ".claude" / "skill-candidates"
SKILLS = ROOT / ".claude" / "skills"
INDEX = SKILLS / "INDEX.md"
INDEPENDENT = {"session-trace", "user-prompt"}
FLOOR = 3


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out = {}
    for line in (m.group(1).splitlines() if m else []):
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.split("#")[0].strip()
    return out


def independent_positives(cases_md: Path) -> tuple[int, int]:
    """回傳 (獨立來源正例數, 總案例數)。表格第二欄是原話、最後一欄是來源。

    同一句話出現三次仍是一條案例——只數**不同說法**。mine.py 會挖出大量逐字重複的原話，
    不去重的話，一句話貼三行就過得了這一關。"""
    if not cases_md.exists():
        return 0, 0
    total, seen = 0, set()
    for line in cases_md.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.match(r"^[A-Z]?\d+$", cells[0]):
            continue
        total += 1
        if re.sub(r"[`\s]", "", cells[-1]) in INDEPENDENT:
            seen.add(" ".join(cells[1].lower().split()))
    return len(seen), total


def gates(name: str) -> list[str]:
    d = CAND / name
    why = []
    sk = d / "SKILL.md"
    if not sk.exists():
        return [f"SCAN：{sk} 不存在"]
    fm = _frontmatter(sk.read_text(encoding="utf-8"))
    if fm.get("name") != name:
        why.append(f"SCAN：frontmatter name='{fm.get('name')}' 與目錄名 '{name}' 不一致")
    if len(fm.get("description", "")) < 20:
        why.append("SCAN：description 太短，寫不出觸發條件的 skill 不會被正確路由")
    if not fm.get("validated"):
        why.append("VALIDATE：validated 是空的——這套做法實際用過並成功了嗎？寫出在哪一次")
    indep, total = independent_positives(d / "evals" / "trigger-cases.md")
    if indep < FLOOR:
        why.append(f"MUTATE：獨立來源正例 {indep}/{FLOOR}（共 {total} 條）——"
                   "照 description 寫的案例不算，要從真實 session 或使用者原話取")
    if (SKILLS / name).exists():
        why.append(f"SOLIDIFY：skills/{name} 已經存在，名稱衝突")
    return why


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list or not a.name:
        found = sorted(p.parent.name for p in CAND.glob("*/SKILL.md")) if CAND.is_dir() else []
        if not found:
            print("（目前沒有候選 skill）")
        for n in found:
            w = gates(n)
            print(f"{n:28s} {'✓ 可升級' if not w else f'✗ {len(w)} 道閘未過'}")
        return 0

    why = gates(a.name)
    if why:
        print(f"✗ {a.name} 不得升級成正式 skill：", file=sys.stderr)
        for w in why:
            print(f"  - {w}", file=sys.stderr)
        return 2
    if a.dry_run:
        print(f"✓ {a.name} 四道閘全過（dry-run，未搬移）")
        return 0

    shutil.move(str(CAND / a.name), str(SKILLS / a.name))
    fm = _frontmatter((SKILLS / a.name / "SKILL.md").read_text(encoding="utf-8"))
    summary = re.split(r"[——。]", fm["description"])[0][:40]
    with open(INDEX, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"\n| {summary} | `{a.name}` | 由 se-acquire 習得，升級於 promote_skill.py |\n")
    print(f"✓ {a.name} 已升級：.claude/skills/{a.name}/，並寫入 INDEX.md")
    print("  下一步：git commit——check-router.sh 會再驗一次 INDEX 與目錄一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
