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

ROW = re.compile(r"^\|\s*([AB]\d+)\s*\|(.+)\|\s*$")
INDEPENDENT = {"session-trace", "user-prompt"}
FLOOR_POSITIVE, FLOOR_COLLISION = 3, 2
SKILL = re.compile(r"`([a-z0-9-]+)`")


def load_cases(only=None):
    cases = []
    for line in CASES_MD.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        cid, rest = m.groups()
        cells = [c.strip() for c in rest.split("|")]
        if len(cells) < 3:
            continue
        text, expect, forbid = cells[0], cells[1], cells[2]
        prov = SKILL.findall(cells[3])[0] if len(cells) > 3 and SKILL.findall(cells[3]) else "authored"
        if only and not cid.startswith(only):
            continue
        cases.append({
            "id": cid,
            "text": text,
            "expect": SKILL.findall(expect),
            "forbid": SKILL.findall(forbid),
            "provenance": prov,
        })
    return cases


def coverage(cases):
    """每個受測 skill 的獨立來源覆蓋率。不足下限就是 unmeasured，不編分數。

    `authored`（照 skill 自己的 description 寫出來的案例）**不計入**——
    用 description 寫的案例交給讀同一份 description 的判官，不可能失敗。
    它測的是自我一致性，不是路由能力。
    """
    stat = {}
    for c in cases:
        indep = c["provenance"] in INDEPENDENT
        for sk in c["expect"]:
            d = stat.setdefault(sk, {"positive": 0, "collision": 0, "authored": 0})
            d["positive" if indep else "authored"] += 1
        for sk in c["forbid"]:
            d = stat.setdefault(sk, {"positive": 0, "collision": 0, "authored": 0})
            if indep:
                d["collision"] += 1
    for sk, d in stat.items():
        d["sufficient"] = (d["positive"] >= FLOOR_POSITIVE
                           and d["collision"] >= FLOOR_COLLISION)
        d["verdict"] = "measurable" if d["sufficient"] else "unmeasured"
    return stat


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


DISPATCH_PROBE = "我剛改完 .claude/hooks 底下那三支腳本，幫我做一次完整 review"


def dispatch_groups(stream):
    """每一則 assistant 訊息裡派了哪些 subagent。

    平行 = 同一則訊息內出現 2 個以上派發呼叫。分散在不同訊息就是序列化——
    這是 rules/dispatch.md 第 3 條講的那個機制，也是這支探測唯一在看的東西。
    """
    groups = []
    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            continue
        names = [(b.get("input") or {}).get("subagent_type") or "?"
                 for b in d.get("message", {}).get("content", [])
                 if b.get("type") == "tool_use" and b.get("name") in ("Task", "Agent")]
        if names:
            groups.append(names)
    return groups


def max_batch(stream):
    """整份 transcript 裡，單一 assistant 訊息最多同時發出幾個工具呼叫。

    這是**儀器自檢**：若全程最大值是 1，代表這個執行環境根本不批次工具呼叫，
    於是「有沒有並行派發」在這裡量不到——那是儀器的極限，不是被測系統壞掉。
    """
    best = 0
    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") != "assistant":
            continue
        n = sum(1 for b in d.get("message", {}).get("content", [])
                if b.get("type") == "tool_use")
        best = max(best, n)
    return best


def run_dispatch_probe(timeout):
    proc = subprocess.run(
        ["claude", "-p", DISPATCH_PROBE, "--output-format", "stream-json",
         "--verbose", "--max-turns", "25",
         "--allowedTools", "Skill", "Task", "Read", "Grep", "Glob", "Bash"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, shell=(sys.platform == "win32"),
    )
    raw = proc.stdout or ""
    return dispatch_groups(raw), max_batch(raw)


def run_case(case, timeout):
    proc = subprocess.run(
        # 只給 Skill，刻意不給 Read/Grep：本案例集就存在被測的 repo 裡，
        # 給了搜尋工具模型會 grep 到 trigger-cases.md 的答案欄（實測發生過）。
        # 路由決策在第一輪就發生，不需要其他工具。
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
    ap.add_argument("--coverage", action="store_true",
                    help="每個 skill 的獨立來源覆蓋率；不足下限回 unmeasured")
    ap.add_argument("--parse-only")
    ap.add_argument("--dispatch", action="store_true",
                    help="並行派發探測：雙軸 review 的兩個 Thread 有沒有在同一則訊息裡一次派出")
    args = ap.parse_args()

    if args.parse_only:
        raw = Path(args.parse_only).read_text(encoding="utf-8")
        used, refused = skills_used(raw)
        print("skills:", used, "| not-logged-in:", refused)
        groups = dispatch_groups(raw)
        batch = max_batch(raw)
        print("派發分組:", groups or "（無）",
              "→", "平行" if any(len(g) >= 2 for g in groups) else "序列／無派發")
        print(f"單則訊息最大工具批次: {batch}",
              "（=1 代表這份 transcript 量不到並行）" if batch <= 1 else "")
        return 0

    if args.dispatch:
        groups, batch = run_dispatch_probe(max(args.timeout, 900))
        print(f"派發訊息數 {len(groups)}，派發總數 {sum(len(g) for g in groups)}，"
              f"全程單則訊息最大工具批次 {batch}")
        for i, g in enumerate(groups, 1):
            print(f"  訊息 {i}: {g}" + ("   ← 平行" if len(g) >= 2 else ""))

        if any(len(g) >= 2 for g in groups):
            verdict, code = "PASS：兩軸在同一則訊息內一次派出", 0
        elif batch <= 1:
            verdict, code = (
                "INCONCLUSIVE：這個環境全程沒有任何一則訊息批次過兩個工具呼叫"
                "（不只 Task，Read／Grep／Bash 也一樣）。並行派發在這裡量不到，"
                "不能據此說配置有問題。", 0)
        else:
            verdict, code = ("FAIL：環境會批次工具呼叫，但這兩個派發被拆成多則訊息"
                             "＝序列化", 1)
        print(verdict)

        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                             capture_output=True, text=True).stdout.strip()
        stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
        out = RUNS_DIR / f"{stamp}-{sha or 'nogit'}-dispatch.json"
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"date": stamp, "commit": sha, "probe": DISPATCH_PROBE,
                       "groups": groups, "max_tool_batch": batch,
                       "verdict": verdict}, fh, ensure_ascii=False, indent=2)
        print(f"結果寫入 {out.relative_to(ROOT)}")
        return code

    cases = load_cases(args.only)
    if not cases:
        print("沒有解析到任何案例——檢查 trigger-cases.md 的表格格式", file=sys.stderr)
        return 2

    if args.coverage:
        stat = coverage(cases)
        print(f"覆蓋率下限：{FLOOR_POSITIVE} 條獨立來源正例 ＋ {FLOOR_COLLISION} 條碰撞")
        print()
        print(f"{'skill':26s} {'獨立正例':>8s} {'碰撞':>6s} {'authored':>9s}  判定")
        for sk in sorted(stat):
            d = stat[sk]
            print(f"{sk:26s} {d['positive']:>8d} {d['collision']:>6d} "
                  f"{d['authored']:>9d}  {d['verdict']}")
        n_bad = sum(1 for d in stat.values() if not d["sufficient"])
        print()
        print(f"{n_bad}/{len(stat)} 個 skill 的案例覆蓋率不足，判定為 unmeasured。")
        print("unmeasured 不是失敗，是**還沒有資格宣稱數字**。回填獨立來源案例才算數。")
        return 0

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
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"date": stamp, "commit": sha, "runs_per_case": args.runs,
                   "passed": passes, "total": len(cases), "cases": results},
                  fh, ensure_ascii=False, indent=2)

    print(f"命中 {passes}/{len(cases)}（每條跑 {args.runs} 次）")
    print(f"結果寫入 {out.relative_to(ROOT)}")
    print("把這個數字填進 trigger-cases.md 的執行紀錄。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
