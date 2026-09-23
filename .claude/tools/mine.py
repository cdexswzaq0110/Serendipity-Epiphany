#!/usr/bin/env python3
"""經驗採礦：從 session 逐字紀錄裡找出「一直重複」的東西——學習迴圈的第一步。

學習新技能的機制（skill-candidates ＋ promote_skill.py）都在，但從建立到 2026-09-24
一個候選都沒有：迴圈的第一步「注意到重複」一直靠人。唯一一次跑通（se-resume）是人工翻
逐字紀錄，看到「Continue from where you left off.」出現 9 次。這支把那一步機械化。

三條礦脈：
  需求  使用者重複說的話      → 路由缺口／新 skill 的觸發案例（來源 session-trace）
  失敗  反覆撞到的錯誤        → lesson 候選
  動作  agent 反覆手動做的事  → 自動化候選——或者迷信

**採礦只產生候選，不產生能力。** 每個重複背後都有一個信念（「這件事需要做」），
先驗證信念，再走 promote_skill.py／se-epiphany 的閘。第一次跑就挖到一個迷信：
CRLF 正規化手動做了一百多次，起因是一個在這台機器上會誤報的檢查器（docs/lessons/0012）。

只讀**人類 session**（有 origin.kind == "human" 的訊息）：headless 評測會把同一句案例
跑很多次，算進來就是假的重複。

用法：
  python .claude/tools/mine.py                  報告（本專案的逐字紀錄）
  python .claude/tools/mine.py --json
  python .claude/tools/mine.py seed <skill 名> --from N1 --from N2 --from N3
      把需求礦脈裡編號 N 的原話逐字寫成候選 skill 的觸發案例（附 session），
      不同說法才算不同案例；SKILL.md 本體與 validated 要自己寫——那是判斷，不是採礦。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

CLAUDE = Path(__file__).resolve().parents[1]
MIN_NEED, MIN_FAIL, MIN_ACT, MIN_SESS = 3, 3, 10, 2
TRIVIAL = {"cd", "echo", "export", "printf", "true", "exit", "done", "fi", "do", "then", "else",
           "wait", "sleep", "set", "local", "return", "EOF", "PY", "---", "```"}
# 純查看的指令不是自動化候選——它們本來就該由人或 agent 看完再判斷
READONLY = re.compile(r"^(tail|head|wc|cat|ls|grep|od|xxd|file|diff|column|sort|uniq|awk|cut|tr"
                      r"|sed -n|git (status|log|diff|show|branch|rev-parse|ls-files|ls-remote|fetch))\b")


def transcripts_dir(top):
    """Claude Code 把逐字紀錄放在 ~/.claude/projects/<專案路徑把非英數字元換成 ->。"""
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(top))


def project_root():
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")  # Windows 預設 cp950，路徑裡的「—」會解壞
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except OSError:
        pass
    return os.getcwd()


# ---------- 讀逐字紀錄 ----------

def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def read_session(path):
    """回傳 (是否人類 session, 依序的事件)。事件：("prompt", 原話, meta) ／ ("error", 文字) ／ ("tool", 名稱, 輸入)。"""
    evs, human = [], False
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("isSidechain"):
            continue
        t, c = o.get("type"), (o.get("message") or {}).get("content")
        if t == "user":
            if (o.get("origin") or {}).get("kind") == "human":
                human = True
            if isinstance(c, str):
                evs.append(("prompt", c, bool(o.get("isMeta"))))
            elif isinstance(c, list):
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_result" and b.get("is_error"):
                        evs.append(("error", _text(b.get("content"))))
                    elif b.get("type") == "text":
                        evs.append(("prompt", b.get("text", ""), bool(o.get("isMeta"))))
        elif t == "assistant" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    evs.append(("tool", b.get("name"), b.get("input") or {}))
    return human, evs


# ---------- 正規化 ----------

def norm_prompt(s):
    s = " ".join(s.split()).strip()
    if (not s or s.startswith(("<", "[Image")) or len(s) > 200  # 系統標籤、圖片尺寸說明不是使用者的話
            or "This session is being continued" in s):
        return None
    return s.lower().rstrip("。.!！?？ ")


def norm_error(s):
    first = s.strip().split("\n")[0][:180]
    first = re.sub(r"[A-Za-z]:[\\/][^\s'\"]*|(?<![\w$])/[\w./-]{6,}", "<path>", first)
    first = re.sub(r"\b[0-9a-f]{7,40}\b", "<sha>", first)
    first = re.sub(r"\d+", "<n>", first)
    first = " ".join(first.split())
    return None if len(first) < 16 or re.fullmatch(r"Exit code <n>", first) else first


def strip_heredocs(cmd):
    """heredoc 內文是資料（python 腳本、commit message），不是 agent 做的動作。"""
    out, lines, i = [], cmd.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?", line)
        i += 1
        if m:
            while i < len(lines) and lines[i].strip() != m.group(1):
                i += 1
            i += 1
    return "\n".join(out)


def norm_actions(cmd):
    acts = []
    # 跨行的引號字串（python -c "…多行…"）也是資料，先收成一個佔位符，不然每一行程式都會被當成一個動作
    cmd = re.sub(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'", lambda m: "<q>" if "\n" in m.group(0) else m.group(0),
                 strip_heredocs(cmd), flags=re.S)
    for part in re.split(r"\s*(?:&&|\|\||;|\||\n)\s*", cmd):
        if re.match(r"^\s*\w+=", part):  # 變數賦值
            continue
        part = re.sub(r"^(do|then|else)\s+", "", part.strip())  # 迴圈裡的動作也是動作（CRLF 正規化就藏在 do 後面）
        if (not part or len(part) < 4 or part[0] in "\"')" or part.split()[0] in TRIVIAL
                or part.startswith(("#", "for ", "if ", "while ")) or READONLY.match(part)):
            continue
        part = re.sub(r"\"([^\"]{25,})\"|'([^']{25,})'", "<q>", part)  # 長字串是內容，短的（sed 表達式）是動作的一部分
        part = re.sub(r"\"[^\"]*[\\/][^\"]*\"|[A-Za-z]:[\\/]\S+|\S*[\\/]\S+\.\w+|\S+\.(md|py|sh|json|jsonl|txt)\b", "<f>", part)
        acts.append(" ".join(part.split()[:6]))
    return acts


def eval_cases():
    """docs/eval/trigger-cases.md 裡已收錄的原話 → (案例 ID, 該載入的 skill)。"""
    p = CLAUDE.parent / "docs" / "eval" / "trigger-cases.md"
    out = {}
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"[A-Z]\d+", cells[0]):
            k = norm_prompt(cells[1])
            if k:
                out[k] = (cells[0], ",".join(re.findall(r"`([a-z0-9-]+)`", cells[2])) or "—")
    return out


# ---------- 採礦 ----------

def mine(tdir):
    need = defaultdict(lambda: {"n": 0, "sessions": set(), "text": None, "meta": False, "skills": defaultdict(int)})
    fail = defaultdict(lambda: {"n": 0, "sessions": set(), "sample": None})
    act = defaultdict(lambda: {"n": 0, "sessions": set()})
    human_n = skipped = 0
    for path in sorted(Path(tdir).glob("*.jsonl")):
        human, evs = read_session(path)
        if not human:
            skipped += 1
            continue
        human_n += 1
        sid, cur = path.stem[:8], None
        for e in evs:
            if e[0] == "prompt":
                k = norm_prompt(e[1])
                cur = k
                if k:
                    g = need[k]
                    g["n"] += 1
                    g["sessions"].add(sid)
                    g["text"] = g["text"] or " ".join(e[1].split())
                    g["meta"] = g["meta"] or e[2]
                    g["skills"]["（無）"] += 1  # 之後看到 Skill 就改記
            elif e[0] == "tool" and e[1] == "Skill" and cur:
                g = need[cur]
                name = e[2].get("skill") or "?"
                if g["skills"].get("（無）"):
                    g["skills"]["（無）"] -= 1
                g["skills"][name] += 1
            elif e[0] == "tool" and e[1] == "Bash":
                for a in norm_actions(e[2].get("command", "")):
                    act[a]["n"] += 1
                    act[a]["sessions"].add(sid)
            elif e[0] == "error":
                k = norm_error(e[1])
                if k:
                    fail[k]["n"] += 1
                    fail[k]["sessions"].add(sid)
                    fail[k]["sample"] = fail[k]["sample"] or e[1].strip().split("\n")[0][:200]

    def keep(d, lo):
        rows = [dict(v, key=k, sessions=sorted(v["sessions"])) for k, v in d.items()
                if v["n"] >= lo and len(v["sessions"]) >= MIN_SESS]
        return sorted(rows, key=lambda r: (-len(r["sessions"]), -r["n"]))

    needs = keep(need, MIN_NEED)
    cases = eval_cases()
    for r in needs:
        r["skills"] = {k: v for k, v in sorted(r["skills"].items(), key=lambda x: -x[1]) if v}
        r["case"] = cases.get(r["key"])  # 「當時沒接住」與「現在有沒有收進評測」是兩件事，對照另一個來源
    return {"human_sessions": human_n, "skipped_sessions": skipped,
            "needs": needs, "failures": keep(fail, MIN_FAIL), "actions": keep(act, MIN_ACT)[:15]}


# ---------- 輸出 ----------

def report(m):
    out = [f"# 經驗採礦（{m['human_sessions']} 個人類 session；略過 {m['skipped_sessions']} 個 headless／自動 session）",
           f"門檻：同一件事至少 {MIN_NEED} 次（動作 {MIN_ACT} 次）、橫跨至少 {MIN_SESS} 個 session。", ""]
    out.append("## 需求：使用者重複說的話")
    for i, r in enumerate(m["needs"], 1):
        who = "（系統送出）" if r["meta"] else ""
        sk = "、".join(f"{k}×{v}" for k, v in r["skills"].items()) or "（無）"
        now = f"  ｜現在：已收進案例集 {r['case'][0]}（{r['case'][1]}）" if r.get("case") else "  ｜現在：**沒有任何案例**"
        out.append(f"  N{i}  {r['n']} 次／{len(r['sessions'])} session  「{r['text'][:80]}」{who}  當時載入：{sk}{now}")
    if not m["needs"]:
        out.append("  （沒有達到門檻的）")
    out.append("  → 大多被同一個 skill 接住的是**覆蓋**；接著什麼都沒載入的才是**缺口**。")
    out.append("    同一個需求的不同說法湊滿 3 條，才夠做一個候選：mine.py seed <名稱> --from N1 --from N2 --from N3")
    out += ["", "## 失敗：反覆撞到的錯誤"]
    for i, r in enumerate(m["failures"], 1):
        out.append(f"  F{i}  {r['n']} 次／{len(r['sessions'])} session  {r['sample'][:120]}")
    if not m["failures"]:
        out.append("  （沒有達到門檻的）")
    out.append("  → 先問是判定條件錯（G0001）還是真的錯；真的錯、下次還會撞，就寫 lesson（se-epiphany）。")
    out += ["", "## 動作：agent 反覆手動做的事"]
    for i, r in enumerate(m["actions"], 1):
        out.append(f"  A{i}  {r['n']} 次／{len(r['sessions'])} session  {r['key']}")
    if not m["actions"]:
        out.append("  （沒有達到門檻的）")
    out.append("  → **先驗證它背後的信念**（這件事真的需要做嗎？用哪個獨立來源確認？），")
    out.append("    成立才考慮做成 hook 或工具；不成立就是迷信，寫 lesson 把它停掉。")
    return "\n".join(out)


def seed(name, ids, m):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        print("[mine] skill 名稱只能用小寫英數與 -")
        return 2
    picks = []
    for i in ids:
        if not 1 <= i <= len(m["needs"]):
            print(f"[mine] 沒有 N{i}（需求礦脈共 {len(m['needs'])} 條）")
            return 2
        picks.append(m["needs"][i - 1])
    distinct = {r["key"]: r for r in picks}
    d = CLAUDE / "skill-candidates" / name
    cases = d / "evals" / "trigger-cases.md"
    have = set()
    if cases.exists():  # 候選已經在（se-acquire 先寫了 SKILL.md）→ 只補還沒收錄的說法
        for line in cases.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and re.fullmatch(r"\d+", cells[0]):
                have.add(norm_prompt(cells[1]))
    have.discard(None)
    total = have | set(distinct)
    new = [r for k, r in distinct.items() if k not in have]
    if not cases.exists() and len(total) < 3:  # 從零播種：湊不滿 3 種說法就還不值得成為能力
        print(f"[mine] 不同說法只有 {len(total)} 條——升級閘要 3 條獨立來源。再找幾種說法，或等它再出現。")
        return 2
    if not new:
        print("[mine] 這些說法都已經收錄了")
        return 0
    (d / "evals").mkdir(parents=True, exist_ok=True)
    if not (d / "SKILL.md").exists():
        (d / "SKILL.md").write_text(
            # description 刻意只寫 TODO：太短過不了升級閘的 SCAN，沒寫完就升不上去
            f"---\nname: {name}\ndescription: TODO\nvalidated:\n---\n\n# TODO\n\n"
            "由 mine.py 從真實 session 播種。description 寫給模型看：做什麼、什麼時候用、什麼時候不是這個。\n"
            "`validated` 要等這套做法實際用過並成功才填。\n",
            encoding="utf-8")
    if not cases.exists():
        cases.write_text("# 觸發案例（原話逐字取自逐字紀錄）\n\n| # | 使用者說的話 | 來源 |\n|---|---|---|\n",
                         encoding="utf-8")
    start = len(have) + 1
    with open(cases, "a", encoding="utf-8") as f:
        for i, r in enumerate(new, start):
            f.write(f"| {i} | {r['text'].replace('|', '／')} | `session-trace` |\n")
        f.write("\n" + "\n".join(f"<!-- {i}：mine.py 播種，{r['n']} 次，session {', '.join(r['sessions'])} -->"
                                 for i, r in enumerate(new, start)) + "\n")
    short = "" if len(total) >= 3 else f"——還差 {3 - len(total)} 種說法才過得了升級閘"
    print(f"[mine] {d}：新增 {len(new)} 條不同說法（共 {len(total)} 條{short}）。"
          "SKILL.md 本體要自己寫，實際用過之後填 validated，再跑 promote_skill.py。")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="經驗採礦")
    ap.add_argument("--transcripts", help="逐字紀錄目錄（預設：本專案在 ~/.claude/projects 下的那個）")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sd = sub.add_parser("seed")
    sd.add_argument("name")
    sd.add_argument("--from", dest="ids", action="append", type=lambda s: int(s.lstrip("Nn")), required=True)
    a = ap.parse_args(argv)
    tdir = Path(a.transcripts) if a.transcripts else transcripts_dir(project_root())
    if not tdir.is_dir():
        print(f"[mine] 找不到逐字紀錄：{tdir}")
        return 2
    m = mine(tdir)
    if a.cmd == "seed":
        return seed(a.name, a.ids, m)
    if a.json:
        print(json.dumps(m, ensure_ascii=False, indent=1, default=list))
    else:
        print(report(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
