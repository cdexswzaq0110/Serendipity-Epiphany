#!/usr/bin/env python3
"""Skill 觸發評測執行器。

案例的單一真相源是 trigger-cases.md 的表格，這支只負責跑與比對。

用法：
    python docs/eval/run_eval.py --list          # 只列出解析到的案例，不呼叫模型
    python docs/eval/run_eval.py                 # 跑 A/B 組，每條 2 次
    python docs/eval/run_eval.py --runs 1        # 快速版
    python docs/eval/run_eval.py --only A        # 只跑 A 組
    python docs/eval/run_eval.py --parse-only <file.jsonl>   # 驗證解析邏輯

前置：claude CLI 已安裝且已登入（`claude login`）。未登入時每條都會回
「Not logged in」，本程式會偵測到並中止，不會把它算成 FAIL。
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
CASES_MD = ROOT / "docs" / "eval" / "trigger-cases.md"
RUNS_DIR = ROOT / "docs" / "eval" / "runs"

ROW = re.compile(r"^\|\s*([AB]\d+)\s*\|(.+?)\|(.+?)\|(.+?)\|\s*$")
SKILL = re.compile(r"`([a-z0-9-]+)`")


def load_cases(only=None):
    cases = []
    for line in CASES_MD.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        cid, text, expect, forbid = m.groups()
        if only and not cid.startswith(only):
            continue
        cases.append({
            "id": cid,
            "text": text.strip(),
            "expect": SKILL.findall(expect),
            "forbid": SKILL.findall(forbid),
        })
    return cases


def skills_used(stream):
    """從 stream-json transcript 抽出實際載入的 skill 名稱。"""
    used, refused = [], False
    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "assistant":
            for b in d.get("message", {}).get("content", []):
                if b.get("type") == "tool_use" and b.get("name") == "Skill":
                    name = (b.get("input") or {}).get("skill")
                    if name:
                        used.append(name)
                elif b.get("type") == "text" and "Not logged in" in (b.get("text") or ""):
                    refused = True
    return used, refused


def run_case(case, timeout):
    proc = subprocess.run(
        ["claude", "-p", case["text"], "--output-format", "stream-json",
         "--verbose", "--max-turns", "2", "--allowedTools", "Skill"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, shell=(sys.platform == "win32"),
    )
    return skills_used(proc.stdout or "")


def judge(case, used):
    hit = any(s in used for s in case["expect"])
    bad = [s for s in case["forbid"] if s in used]
    return hit and not bad, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--only", choices=["A", "B"])
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--parse-only")
    args = ap.parse_args()

    if args.parse_only:
        used, refused = skills_used(Path(args.parse_only).read_text(encoding="utf-8"))
        print("skills:", used, "| not-logged-in:", refused)
        return 0

    cases = load_cases(args.only)
    if not cases:
        print("沒有解析到任何案例——檢查 trigger-cases.md 的表格格式", file=sys.stderr)
        return 2

    if args.list:
        for c in cases:
            print(f"{c['id']}  {c['text']}\n     該載入 {c['expect']}  不該 {c['forbid']}")
        print(f"\n共 {len(cases)} 條")
        return 0

    results, passes = [], 0
    for c in cases:
        runs = []
        for i in range(args.runs):
            used, refused = run_case(c, args.timeout)
            if refused:
                print("claude CLI 未登入。先跑 `claude login`，再重跑本程式。", file=sys.stderr)
                return 3
            ok, bad = judge(c, used)
            runs.append({"used": used, "ok": ok, "forbidden_hit": bad})
            print(f"  {c['id']} run{i+1}: {'PASS' if ok else 'FAIL'}  載入={used or '（無）'}")
        allok = all(r["ok"] for r in runs)
        passes += allok
        results.append({**c, "runs": runs, "pass": allok})
        print(f"{c['id']}: {'PASS' if allok else 'FAIL'}（{args.runs} 次都對才算 PASS）\n")

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                         capture_output=True, text=True).stdout.strip()
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out = RUNS_DIR / f"{stamp}-{sha or 'nogit'}.json"
    out.write_text(json.dumps(
        {"date": stamp, "commit": sha, "runs_per_case": args.runs,
         "passed": passes, "total": len(cases), "cases": results},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"命中 {passes}/{len(cases)}（每條跑 {args.runs} 次）")
    print(f"結果寫入 {out.relative_to(ROOT)}")
    print("把這個數字填進 trigger-cases.md 的執行紀錄。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
