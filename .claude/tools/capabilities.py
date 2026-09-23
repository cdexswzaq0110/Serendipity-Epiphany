#!/usr/bin/env python3
"""能力自我模型：這套配置會什麼、驗證過什麼、不會什麼。

**這份模型是從原始碼生成的，不是手寫的。** 手寫的自我描述會漂——加了 skill 忘了
更新、刪了 hook 還寫著有。從 frontmatter、settings.json、ABLATION.md、eval 覆蓋率
直接讀出來，它就不可能跟現實不一致。這是「Router 不說謊」延伸到整個配置的版本。

三個問題，每個都要能被回答：
  1. 我會什麼？          → skills / agents / hooks
  2. 其中哪些驗證過？    → eval 覆蓋率、消融紀錄、hook 自測
  3. 我不會什麼？        → 已知缺口 ＋ 結構上做不到的事

用法：
    python .claude/tools/capabilities.py            # 人看的摘要
    python .claude/tools/capabilities.py --json     # 機器讀的完整模型
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
CLAUDE = ROOT / ".claude"
GLOBAL_HOME = Path(os.environ.get("SERENDIPITY_HOME",
                                  Path.home() / ".claude" / "serendipity"))

# 結構上做不到的事——不是還沒做，是這一層做不到。寫死在這裡，因為它們不會從原始碼長出來。
CANNOT_DO = [
    ("改變模型本身的能力或權重", "這是配置層，只能改模型讀到什麼，不能改模型是什麼"),
    ("無人監督的長時間自主執行", "刻意不做：與「人的決策是全域鎖」衝突，見 DESIGN_RATIONALE"),
    ("對外部世界的預測模型", "沒有模擬環境；行動前的後果推演只能靠模型自己"),
    ("保證在沒見過的領域做對", "se-acquire 給的是程序，不是保證；結果仍要驗證"),
]


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.split("#")[0].strip()
    return out


def _eval_coverage() -> dict:
    """借用 run_eval.py 的覆蓋率判定，不另寫一套。"""
    p = ROOT / "docs" / "eval" / "run_eval.py"
    if not p.exists():
        return {}
    spec = importlib.util.spec_from_file_location("run_eval", p)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod.coverage(mod.load_cases())
    except Exception:
        return {}


def skills() -> list[dict]:
    cov = _eval_coverage()
    out = []
    for d in sorted((CLAUDE / "skills").glob("*/SKILL.md")):
        fm = _frontmatter(d.read_text(encoding="utf-8"))
        name = fm.get("name", d.parent.name)
        desc = fm.get("description", "")
        out.append({
            "name": name,
            "summary": re.split(r"[——。]", desc)[0][:60],
            "lines": len(d.read_text(encoding="utf-8").splitlines()),
            "has_references": (d.parent / "references").is_dir(),
            "trigger_eval": cov.get(name, {}).get("verdict", "no_cases"),
        })
    return out


def candidates() -> list[str]:
    d = CLAUDE / "skill-candidates"
    return sorted(p.parent.name for p in d.glob("*/SKILL.md")) if d.is_dir() else []


def agents() -> list[str]:
    return sorted(p.stem for p in (CLAUDE / "agents").glob("*.md"))


def hooks() -> list[dict]:
    try:
        cfg = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    by_script = {}  # 一支腳本掛在多個事件上仍是一道 hook（checkpoint.sh 掛六個）
    for event, groups in cfg.get("hooks", {}).items():
        for g in groups:
            for h in g.get("hooks", []):
                m = re.search(r"hooks/([\w-]+\.sh)", h.get("command", ""))
                if not m:
                    continue
                entry = by_script.setdefault(m.group(1), {"script": m.group(1), "events": [], "mode": "?"})
                if event not in entry["events"]:
                    entry["events"].append(event)
    for entry in by_script.values():
        script = CLAUDE / "hooks" / entry["script"]
        if script.exists():
            mm = re.search(r'MODE="\$\{[A-Z_]+:-(\w+)\}"', script.read_text(encoding="utf-8"))
            entry["mode"] = mm.group(1) if mm else "always"
    return list(by_script.values())


def resident_lines() -> int:
    files = [ROOT / "CLAUDE.md", CLAUDE / "CLAUDE.md", *sorted((CLAUDE / "rules").glob("*.md"))]
    return sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files if f.exists())


def lessons() -> dict:
    proj = sorted((ROOT / "docs" / "lessons").glob("[0-9]*.md"))
    fms = [_frontmatter(p.read_text(encoding="utf-8")) for p in proj]
    glob_dir = GLOBAL_HOME / "lessons"
    glob_n = len(list(glob_dir.glob("G[0-9]*.md"))) if glob_dir.is_dir() else 0  # lessons.py 寫的是 G0001-*.md
    return {
        "project": len(proj),
        "promoted": sum(1 for f in fms if f.get("outcome") == "promoted"),
        "validated": sum(1 for f in fms if f.get("validated")),
        "total_hits": sum(int(f.get("hits") or 0) for f in fms),
        "global": glob_n,
        "global_home": str(glob_dir),
    }


def known_gaps() -> list[str]:
    """從 ABLATION.md 的 ⚠／未登記列、以及 eval 覆蓋率讀出已知弱點。"""
    gaps = []
    ab = CLAUDE / "ABLATION.md"
    if ab.exists():
        for line in ab.read_text(encoding="utf-8").splitlines():
            if line.startswith("| `") and ("⚠" in line or "未登記" in line):
                gaps.append("未實證的常駐規則：" + line.split("|")[1].strip())
    cov = _eval_coverage()
    unmeasured = [k for k, v in cov.items() if not v.get("sufficient")]
    if unmeasured:
        gaps.append(f"skill 觸發評測覆蓋率不足：{len(unmeasured)}/{len(cov)} 個 unmeasured")
    # 兩個學習迴圈各自回報。舊版只在 hits 總和為 0 時才報，hits 一變成 3 這個缺口就從自我模型上消失了，
    # 但升級與候選仍然是 0（2026-09-24 發現）——看的是產出，不是有沒有被碰過。
    ls = lessons()
    if ls["project"] and ls["promoted"] == 0:
        gaps.append(f"從經驗學習的迴圈還沒產出升級：{ls['project']} 則 lesson、hits {ls['total_hits']}、"
                    f"驗證 {ls['validated']}、升級 0 則")
    if not candidates():
        gaps.append("學習新技能的迴圈零吞吐：0 個候選 skill（入口是 tools/mine.py）")
    return gaps


def model() -> dict:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                         capture_output=True, text=True).stdout.strip() or "unknown"
    return {
        "commit": sha,
        "can_do": {"skills": skills(), "skill_candidates": candidates(),
                   "agents": agents(), "hooks": hooks()},
        "verified": {"resident_lines": resident_lines(), "lessons": lessons()},
        "known_gaps": known_gaps(),
        "cannot_do": [{"what": w, "why": y} for w, y in CANNOT_DO],
    }


def summary(m: dict) -> str:
    cd, vf = m["can_do"], m["verified"]
    sk = cd["skills"]
    measured = sum(1 for s in sk if s["trigger_eval"] == "measurable")
    L = [f"# 能力自我模型（commit {m['commit']}，從原始碼生成）", ""]
    L.append(f"## 我會什麼")
    L.append(f"- {len(sk)} 個 skill、{len(cd['agents'])} 個 agent、"
             f"{len(cd['hooks'])} 道 hook、{len(cd['skill_candidates'])} 個候選 skill（未驗證，不會自動載入）")
    L.append(f"- 常駐規則 {vf['resident_lines']} 行")
    L.append("")
    L.append("## 其中驗證過的")
    L.append(f"- skill 觸發路由：{measured}/{len(sk)} 個達到覆蓋率下限（其餘 unmeasured 或無案例）")
    hk = ", ".join(f"{h['script']}({h['mode']})" for h in cd["hooks"])
    L.append(f"- 確定性 gate：{hk}")
    ls = vf["lessons"]
    L.append(f"- lessons：專案 {ls['project']} 則、全域 {ls['global']} 則、"
             f"VALIDATE 過 {ls['validated']} 則、升級 {ls['promoted']} 則")
    L.append("")
    L.append("## 已知缺口（從 ABLATION 與 eval 讀出，不是自評）")
    L += [f"- {g}" for g in m["known_gaps"]] or ["- （無）"]
    L.append("")
    L.append("## 結構上做不到的")
    L += [f"- {c['what']}——{c['why']}" for c in m["cannot_do"]]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    m = model()
    print(json.dumps(m, ensure_ascii=False, indent=2) if a.json else summary(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
