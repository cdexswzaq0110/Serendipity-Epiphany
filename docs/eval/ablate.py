#!/usr/bin/env python3
"""常駐規則消融執行器（leave-one-out）。

**刻意不是通用平台。** 它只做 `ABLATION.md` 定義的那一件事：
拿掉一條規則、其餘完全不動、replay 一個已知失敗、看行為變不變。

設計約束（來自 ABLATION.md 的三個不准）：
- 不用 bundle 對照。一次只拿掉一條規則。
- 判準是「能不能重現那個已知失敗」，不是泛化 effect size。
- 「沒測到差異」不寫成「無效」——輸出用 `no_measured_difference`，不用 `ineffective`。

用法：
    python docs/eval/ablate.py --list
    python docs/eval/ablate.py --rule dispatch-1 --runs 3
    python docs/eval/ablate.py --rule dispatch-1 --dry-run   # 只驗變體，不花 API
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "docs" / "eval" / "runs"

# 每個受測規則：從哪個檔案切掉哪一段、replay 什麼任務、怎麼判定。
RULES = {
    "dispatch-1": {
        "file": ".claude/rules/dispatch.md",
        "section": "## 1. 預設是 Coroutine",
        "next": "## 2. ",
        "claim": "沒買到隔離就不要派 subagent，預設留在同一個 context 做",
        # replay：2026-09-02 的 P2 探測。廣度搜尋任務——規則要的行為是自己做完，
        # 不派 thread-scout。當時觀察到模型確實沒派，但那是在有規則的情況下。
        "prompt": "這個 repo 裡跟 hook 有關的設定散在哪些檔案？幫我掃一遍列出來。",
        "known_failure": "為了「分工看起來比較專業」而派 subagent，付了隔離成本卻沒買到隔離",
        "tools": ["Skill", "Task", "Read", "Grep", "Glob", "Bash"],
        "max_turns": 12,
    },
}


def make_variant(rule: dict, drop: bool, dest: Path) -> Path:
    """複製整份配置；drop=True 時切掉那一段。其餘完全相同。"""
    dest.mkdir(parents=True, exist_ok=True)
    for item in ("CLAUDE.md", ".claude"):
        src = ROOT / item
        dst = dest / item
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    if drop:
        f = dest / rule["file"]
        text = f.read_text(encoding="utf-8")
        start = text.index(rule["section"])
        end = text.index(rule["next"], start)
        f.write_text(text[:start] + text[end:], encoding="utf-8", newline="\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(dest),
                   capture_output=True)
    return dest


def dispatched(stream: str) -> tuple[bool, list[str]]:
    """這次執行有沒有派出 subagent。確定性判定，不用 LLM judge。"""
    names = []
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
        for b in d.get("message", {}).get("content", []):
            if b.get("type") == "tool_use" and b.get("name") in ("Task", "Agent"):
                names.append((b.get("input") or {}).get("subagent_type") or "?")
    return bool(names), names


def run_once(rule: dict, workdir: Path, timeout: int) -> dict:
    proc = subprocess.run(
        ["claude", "-p", rule["prompt"], "--output-format", "stream-json",
         "--verbose", "--max-turns", str(rule["max_turns"]),
         "--allowedTools", *rule["tools"]],
        cwd=str(workdir), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, shell=(sys.platform == "win32"),
    )
    raw = proc.stdout or ""
    hit, names = dispatched(raw)
    n_tools = sum(1 for l in raw.splitlines() if '"type":"tool_use"' in l.replace(" ", ""))
    return {"dispatched": hit, "agents": names, "raw_len": len(raw)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule", choices=sorted(RULES))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="只產生兩個變體並驗證差異，不呼叫模型")
    args = ap.parse_args()

    if args.list or not args.rule:
        for k, v in RULES.items():
            print(f"{k:14s} {v['file']} → {v['section']}")
            print(f"{'':14s} 宣稱：{v['claim']}")
            print(f"{'':14s} replay：{v['prompt']}")
        return 0

    rule = RULES[args.rule]
    tmp = Path(tempfile.mkdtemp(prefix="ablate-"))
    full = make_variant(rule, False, tmp / "full_rule")
    absent = make_variant(rule, True, tmp / "absent")

    a = (full / rule["file"]).read_text(encoding="utf-8")
    b = (absent / rule["file"]).read_text(encoding="utf-8")
    delta = len(a.splitlines()) - len(b.splitlines())
    print(f"變體已建立：full_rule {len(a.splitlines())} 行 / absent "
          f"{len(b.splitlines())} 行（差 {delta} 行）")
    if rule["section"] in b or delta <= 0:
        print("✗ 變體無效：absent 版本仍含該段，或行數沒有減少", file=sys.stderr)
        return 2
    print(f"✓ 只有那一段被切掉，其餘完全相同\n")
    if args.dry_run:
        print(f"dry-run 結束。變體留在 {tmp}")
        return 0

    results = {"full_rule": [], "absent": []}
    for cond, wd in (("full_rule", full), ("absent", absent)):
        for i in range(args.runs):
            r = run_once(rule, wd, args.timeout)
            results[cond].append(r)
            print(f"  {cond:10s} run{i+1}: 派發={'YES' if r['dispatched'] else 'no'} "
                  f"{r['agents'] or ''}")

    n_full = sum(r["dispatched"] for r in results["full_rule"])
    n_abs = sum(r["dispatched"] for r in results["absent"])
    print(f"\nfull_rule 派發 {n_full}/{args.runs}　absent 派發 {n_abs}/{args.runs}")

    if n_abs > n_full:
        verdict = ("rule_has_effect：拿掉之後更常派發，規則有在擋。"
                   "保留，並把這次數字寫進 ABLATION 的失敗證據欄")
    elif n_full > n_abs:
        verdict = ("unexpected_direction：有規則反而更常派發。"
                   "先查是不是任務或判定設計有問題，不要直接下結論")
    else:
        verdict = (f"no_measured_difference：兩邊都是 {n_full}/{args.runs}。"
                   "**這不等於無效**——它只說明在這個任務、這個模型版本、"
                   f"這 {args.runs} 次裡沒測到差異。依 ABLATION 的單向門檻，"
                   "這是**縮短或刪除**的候選，不是保留的證據")
    print(f"\n判定：{verdict}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                         capture_output=True, text=True).stdout.strip()
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    out = RUNS_DIR / f"{stamp}-{sha}-ablate-{args.rule}.json"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"rule": args.rule, "commit": sha, "runs": args.runs,
                   "prompt": rule["prompt"], "known_failure": rule["known_failure"],
                   "dispatch_count": {"full_rule": n_full, "absent": n_abs},
                   "verdict": verdict, "detail": results}, fh,
                  ensure_ascii=False, indent=2)
    print(f"結果寫入 {out.relative_to(ROOT)}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
