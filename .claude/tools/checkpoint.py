#!/usr/bin/env python3
"""斷點續跑：長任務跑到一半掛了，從現實對照出「上次停在哪」。

面試題的標準答案是「每完成一步就存狀態，重啟時從最後完成的那步接著跑」。
對 LLM agent，這個答案有三個洞，這支工具補的就是這三個：

1. 掛掉的那一刻 agent 來不及寫任何東西
   → 斷點由 hook 自動寫，不靠 agent 記得（預寫日誌，WAL）
2. 「我做到第 3 步」是一句宣稱，宣稱會說謊（docs/lessons/0010）
   → 斷點存可以對照現實的指紋；續跑時重新檢查，不照單全收（fsck）
3. 斷點本身也會寫到一半被打斷
   → append-only JSONL，讀的時候跳過殘缺的行

日誌在 $(git rev-parse --absolute-git-dir)/serendipity/journal.jsonl：
不進版控、每個 worktree 各一份、跟著 clone 一起消失。

hook 自動寫（checkpoint.py record，讀 stdin 的 payload）：
  PostToolUse／PostToolUseFailure → snap        工作樹指紋、HEAD、分支
  Stop                            → turn_end    回合正常結束
  StopFailure                     → turn_failed 回合因 API 錯誤結束
  UserPromptSubmit                → prompt      同一個 session 剛被打斷 → 先印簡報
  SessionStart                    →             有斷點 → 印簡報

agent 手動寫：
  step add <id> <標題> --done-when "<bash 指令>"   完成條件要能用指令檢查
  step done <id>                                   宣稱完成（續跑時會重新檢查）
  verify -- <指令...>                              跑指令；證據綁定當下的工作樹指紋
  decide <問題> <答案>                              人拍板過的決定，續跑後不重問
  close                                            這段工作結束，之後不再提示

讀：
  resume   完整簡報，會跑每一步的 done-when
  status   同上，不跑 done-when
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROTATE_BYTES = 1_000_000
KEEP_SNAPS = 20
PROBE_TIMEOUT = 60
GIT_OPS = [("rebase-merge", "rebase"), ("rebase-apply", "rebase／am"), ("MERGE_HEAD", "merge"),
           ("CHERRY_PICK_HEAD", "cherry-pick"), ("REVERT_HEAD", "revert"), ("BISECT_LOG", "bisect")]


# ---------- git 與現實 ----------

def git(args, cwd, env=None):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=cwd, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout.strip(), r.stderr
    except OSError:
        return 1, "", "git not found"


def locate(cwd):
    """(工作樹根目錄, 斷點目錄)；不在 git repo 裡就回 None。"""
    rc, top, _ = git(["rev-parse", "--show-toplevel"], cwd)
    if rc or not top:
        return None
    _, gd, _ = git(["rev-parse", "--absolute-git-dir"], cwd)
    return top, Path(gd) / "serendipity"


def fingerprint(top, sd):
    """整個工作樹（含未追蹤、遵守 .gitignore）的 tree hash。

    用斷點目錄裡的獨立 index，不碰使用者的 index；它會保留 stat 快取，第二次起只重算變過的檔。
    blob 會寫進物件庫，所以斷點當下的內容在 gc 之前都還能取回。"""
    sd.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_INDEX_FILE=str(sd / "index"))
    for _ in range(20):  # 背景 hook 可能同時跑，撞到 index.lock 就等一下
        rc, _, err = git(["add", "-A"], top, env)
        if rc == 0:
            rc, tree, _ = git(["write-tree"], top, env)
            return tree if rc == 0 else None
        if "index.lock" not in err:
            return None
        time.sleep(0.1)
    return None


def head(top):
    rc, out, _ = git(["rev-parse", "HEAD", "HEAD^{tree}", "--abbrev-ref", "HEAD"], top)
    if rc:
        _, br, _ = git(["symbolic-ref", "--short", "-q", "HEAD"], top)
        return None, None, br or "(unborn)"
    sha, tree, br = (out.splitlines() + ["", "", ""])[:3]
    return sha, tree, ("(detached)" if br == "HEAD" else br)


def git_ops(sd):
    gd = sd.parent
    ops = [label for name, label in GIT_OPS if (gd / name).exists()]
    if (gd / "index.lock").exists():
        ops.append("index.lock 殘留（有 git 指令做到一半）")
    return ops


def changed(top, a, b):
    """兩個 tree 之間變了哪些檔。物件已被 gc 回 None。"""
    if not a or not b:
        return None
    if a == b:
        return []
    rc, out, _ = git(["diff-tree", "-r", "--name-only", a, b], top)
    return out.splitlines() if rc == 0 else None


# ---------- 日誌 ----------

def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def append(sd, ev):
    sd.mkdir(parents=True, exist_ok=True)
    ev.setdefault("at", now())
    p = sd / "journal.jsonl"
    lead = ""
    if p.exists() and p.stat().st_size:  # 上一次寫到一半被打斷 → 先補換行，不然這一行會跟殘缺行黏在一起一起壞掉
        with open(p, "rb") as f:
            f.seek(-1, os.SEEK_END)
            lead = "" if f.read(1) == b"\n" else "\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(lead + json.dumps(ev, ensure_ascii=False) + "\n")
    if p.stat().st_size > ROTATE_BYTES:
        rotate(sd)


def load(sd):
    """讀日誌。殘缺的行（寫到一半被打斷）跳過並計數，不讓整份失效。"""
    p = sd / "journal.jsonl"
    evs, bad = [], 0
    if not p.exists():
        return evs, bad
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(e, dict) and "kind" in e:
            evs.append(e)
        else:
            bad += 1
    evs.sort(key=lambda e: e.get("at", ""))  # 背景 hook 的寫入順序不保證，以時間為準
    return evs, bad


def rotate(sd):
    """日誌太大時只留：非 snap 事件、每段工作的第一個 snap（改了什麼的基準）、最後幾個 snap。"""
    evs, _ = load(sd)
    keep, snaps, first = [], [], True
    for e in evs:
        if e["kind"] == "close":
            first = True
        if e["kind"] != "snap":
            keep.append(e)
        elif first:
            keep.append(e)
            first = False
        else:
            snaps.append(e)
    keep = sorted(keep + snaps[-KEEP_SNAPS:], key=lambda e: e.get("at", ""))
    p = sd / "journal.jsonl"
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in keep), encoding="utf-8")
    os.replace(tmp, p)  # 原子替換：輪替本身被打斷也不會留下半份日誌


def alive(pid):
    """那個 Claude Code 程序還在不在。查不到就回 None（退回用結束標記推論）。

    Windows 上絕對不能用 os.kill(pid, 0)——那會呼叫 TerminateProcess 把它殺掉。"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def fold(evs, me=None):
    """把事件折成現在的狀態。me 是呼叫者自己的程序（CLAUDE_PID）。

    身分用程序不用 session：同一個 session 被 --resume 起來是新程序，舊程序的事件就是「上一段」。

    有沒有中斷看**最後一個動過工作樹的別的程序**：
      - 回合正常結束 → 沒中斷；因 API 錯誤結束 → 中斷
      - 沒有結束標記 → 程序還活著就是**還在跑**，死了才是中斷（docs/lessons/0011）
    呼叫者自己：沒有結束標記一律當作還在跑，只信 turn_failed 這種正面的失敗訊號。
    只聊天、不改檔的 session（例如觸發評測）沒有 snap，不算，也不能替別人的中斷「結案」。"""
    cut = max((i for i, e in enumerate(evs) if e["kind"] == "close"), default=-1)
    seg = evs[cut + 1:]
    st = {"seg": seg, "steps": {}, "decisions": [], "verifies": {},
          "snaps": [e for e in seg if e["kind"] == "snap"],
          "interrupted": None, "session": None, "last_snap": None, "prompt": None,
          "briefed": set(), "live": None, "base": None, "failed": False}
    for e in seg:
        k = e["kind"]
        if k == "step_add":
            st["steps"][e["id"]] = {"title": e.get("title", ""), "done_when": e.get("done_when"), "claimed": False}
        elif k == "step_done" and e["id"] in st["steps"]:
            st["steps"][e["id"]]["claimed"] = True
        elif k == "decide":
            st["decisions"].append(e)
        elif k == "verify":
            st["verifies"][e["cmd"]] = e  # 同一條指令只看最後一次
    me = str(me) if me else None
    same = lambda e, ref: e.get("pid") == ref.get("pid") and e.get("session") == ref.get("session")  # noqa: E731
    ref = None
    if me:  # 呼叫者自己的上一回合因 API 錯誤中止（例如用量上限）——同一個程序裡唯一可信的中斷訊號
        mine = [e for e in seg if str(e.get("pid")) == me and e["kind"] in ("turn_end", "turn_failed")]
        if mine and mine[-1]["kind"] == "turn_failed":
            before = [s for s in st["snaps"] if str(s.get("pid")) == me and s["at"] <= mine[-1]["at"]]
            if before:
                ref = before[-1]
                st["interrupted"] = f"回合因 API 錯誤中止（{mine[-1].get('error') or 'unknown'}）"
                st["failed"] = True
        bases = [e for e in seg if e["kind"] == "base" and str(e.get("pid")) == me]
        st["base"] = bases[-1] if bases else None
    if ref is None:
        pool = [s for s in st["snaps"] if not me or str(s.get("pid")) != me]
        if not pool:
            return st
        ref = pool[-1]
        ends = [e for e in seg if same(e, ref) and e["kind"] in ("turn_end", "turn_failed") and e["at"] >= ref["at"]]
        if not ends:
            if alive(ref.get("pid")):
                st["live"] = ref  # 還在跑的另一個程序，不是中斷
            else:
                st["interrupted"] = "回合沒有正常結束（連線中斷、程式關閉、當機或手動中斷）"
        elif ends[-1]["kind"] == "turn_failed":
            st["interrupted"] = f"回合因 API 錯誤中止（{ends[-1].get('error') or 'unknown'}）"
            st["failed"] = not me  # 身分不明（沒有 CLAUDE_PID）時退回：正面的失敗訊號本身就算數
    st["session"], st["last_snap"] = ref.get("session"), ref
    prompts = [e for e in seg if e["kind"] == "prompt" and same(e, ref) and e["at"] <= ref["at"]
               and not str(e.get("text", "")).startswith("<")]  # <task-notification> 之類是系統插的，不是使用者的要求
    st["prompt"] = prompts[-1]["text"] if prompts else None
    st["briefed"] = {str(e.get("pid")) for e in seg if e["kind"] == "brief" and e.get("for") == ref["at"]}
    return st


# ---------- 簡報 ----------

def clip(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def names(xs, n=8):
    head_, rest = xs[:n], len(xs) - n
    return "、".join(head_) + (f" …共 {len(xs)} 個" if rest > 0 else "")


def ago(at):
    try:
        sec = (datetime.now(timezone.utc) - datetime.fromisoformat(at)).total_seconds()
    except ValueError:
        return "時間不明"
    for unit, size in (("天", 86400), ("小時", 3600), ("分鐘", 60)):
        if sec >= size:
            return f"{int(sec // size)} {unit}前"
    return "剛剛"


def probe(top, cmd):
    try:
        r = subprocess.run(["bash", "-c", cmd], cwd=top, capture_output=True, timeout=PROBE_TIMEOUT)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return None


def worth_showing(st, sd, source=""):
    """什麼時候值得打斷開工：有中斷、有做到一半的 git 操作、有沒完成的步驟。
    另一個程序還在跑（st["live"]）不算——那是並行，不是斷點，開工時不提。"""
    open_steps = any(not s["claimed"] for s in st["steps"].values())
    if st["interrupted"] or git_ops(sd) or open_steps:
        return True
    return source == "compact" and bool(st["steps"] or st["decisions"] or st["verifies"])


def brief(top, sd, st, run_probes=False):
    tree = fingerprint(top, sd)
    sha, _, br = head(top)
    last = st["last_snap"]
    out = []
    if st["interrupted"]:
        out.append(f"[斷點] 上一段工作{st['interrupted']}，{ago(last['at'])}（session {st['session']}）。")
        if st["prompt"]:
            out.append(f"  中斷前最後的要求：「{clip(st['prompt'], 120)}」")
    elif st["live"] and not st["steps"]:
        out.append("[斷點] 沒有中斷。")
    else:
        out.append("[斷點] 這段工作還沒結束。")
    if st["live"]:
        out.append(f"  另一個 Claude Code 程序（pid {st['live'].get('pid')}）正在這個工作樹上工作——不是中斷；"
                   "兩個 session 同時寫同一個工作樹見 dispatch.md 第 3 條")
    if last:
        # 呼叫者開工時拍過基準快照 → 只比「斷點到我開工」這段，我開工之後改的是我自己的
        base = st["base"] if st["base"] and st["base"].get("at", "") > last["at"] else None
        now_tree, now_head = (base.get("tree"), base.get("head")) if base else (tree, sha)
        when = "斷點之後、這個 session 開工之前" if base else "斷點之後"
        out.append(f"  分支：{br}" + ("" if last.get("branch") == br else f"（中斷時在 {last.get('branch')}）"))
        if last.get("head") != now_head:
            out.append(f"  HEAD 在{when}移動過：{(last.get('head') or '-')[:7]} → {(now_head or '-')[:7]}")
        drift = changed(top, last.get("tree"), now_tree)
        if drift is None:
            out.append("  工作樹：無法和斷點比對（快照物件不在了）——當成未知處理")
        elif drift:
            out.append(f"  ⚠ {when}被改過的檔案（不是上一段 agent 留下的）：{names(drift)}——先確認是誰改的再動")
        else:
            out.append(f"  工作樹：{when}沒有被別人動過，未提交的變更都是上一段工作留下的")
        touched = changed(top, st["snaps"][0].get("head_tree"), last.get("tree")) or []
        if touched:
            out.append(f"  這段工作改過的檔案：{names(touched)}")
    for op in git_ops(sd):
        out.append(f"  ⚠ 進行中的 git 操作：{op}——先處理完它，再做別的")
    for v in st["verifies"].values():
        ok = "仍有效" if v.get("tree") and v.get("tree") == tree else "工作樹已變，視為未驗證"
        out.append(f"  驗證：`{clip(v['cmd'], 60)}` exit {v.get('exit')}——{ok}")
    resume_at = None
    for sid, s in st["steps"].items():
        real = probe(top, s["done_when"]) if (run_probes and s.get("done_when")) else None
        if real is True:
            mark = "✓ 現實成立" + ("" if s["claimed"] else "（沒記到完成——可能做完就斷了）")
        elif real is False:
            mark = "✗ 未成立" + ("（宣稱完成，但現實不成立）" if s["claimed"] else "")
        else:
            mark = "宣稱完成" if s["claimed"] else "未完成"
            if run_probes and s.get("done_when"):
                mark += "（完成條件無法執行）"
        if resume_at is None and real is not True and not (real is None and s["claimed"]):
            resume_at = sid
            mark += "  ← 從這裡繼續"
        out.append(f"  步驟 {sid}：{clip(s['title'], 50)} —— {mark}")
    if st["steps"] and not run_probes:
        out.append("  （步驟狀態是宣稱，跑 resume 才會對照現實）")
    for d in st["decisions"]:
        out.append(f"  已拍板：{clip(d['q'], 50)} → {clip(d['a'], 50)}（不要再問）")
    err = sd / "error.log"
    if err.exists():
        out.append(f"  ⚠ 記錄器出過錯，斷點可能不完整：{err}")
    out.append("  續跑程序見 se-resume；完整簡報：python .claude/tools/checkpoint.py resume")
    return "\n".join(out)


# ---------- 學習訊號 ----------

# 失敗了不代表學到東西：搜尋找不到、測試先紅後綠是正常節奏，不是「撞到才知道」
NOT_LEARNING = re.compile(r"^(grep|rg|find|ls|cat|head|tail|test|\[|which|type|command|echo|wc|diff|"
                          r"pytest|npm test|yarn test|go test|cargo test|make test|python -m pytest|python -m unittest|"
                          r"git (status|diff|log|show|branch|rev-parse|ls-files|fetch))\b")


def cmd_head(cmd):
    """指令的「種類」：去掉 cd 前綴與 heredoc 內文後，第一段的前兩個字（python -m 取三個）。"""
    first = cmd.split("\n")[0]
    parts = [p.strip() for p in re.split(r"&&|;|\|\|", first) if p.strip()]
    parts = [p for p in parts if not re.match(r"^(cd|export|set)\b|^\w+=", p)] or parts
    toks = parts[0].split() if parts else []
    n = 3 if toks[:2] == ["python", "-m"] else 2
    return " ".join(toks[:n])


def learned(sd, pid):
    """這個程序的**這一回合**裡，同一種會改變狀態的指令先失敗、後來又成功的情形。

    這是「撞到才知道」的形狀——核心規則第 6 條要捕捉的東西。兩輪端到端基準 14 次、
    包括一個教科書級的案例（commit 被 hook 拒、看了訊息才改對），一則 lesson 都沒留：
    捕捉完全靠模型收尾時想起來，而單次任務沒有收尾的時刻。"""
    evs = [e for e in load(sd)[0] if str(e.get("pid")) == str(pid)]
    starts = [i for i, e in enumerate(evs) if e["kind"] == "prompt"]
    turn = evs[starts[-1] + 1:] if starts else evs
    out, seen = [], set()
    for i, e in enumerate(turn):
        h = e.get("cmd") or ""
        if e["kind"] != "snap" or not e.get("failed") or not h or NOT_LEARNING.match(h) or h in seen:
            continue
        if any(x["kind"] == "snap" and x.get("cmd") == h and not x.get("failed") for x in turn[i + 1:]):
            seen.add(h)
            out.append((h, e.get("error") or ""))
    t0 = evs[starts[-1]]["at"] if starts else ""
    return out, t0


def lessons_touched_since(top, at):
    """這一回合開始之後，docs/lessons/ 底下有沒有檔案被寫過。"""
    d = Path(top) / "docs" / "lessons"
    if not d.is_dir() or not at:
        return False
    try:
        t0 = datetime.fromisoformat(at).timestamp()
    except ValueError:
        return False
    return any(p.stat().st_mtime > t0 for p in d.glob("*.md"))


# ---------- 不准丟掉開工前就存在的未提交變更 ----------

def _strip_heredocs(cmd):
    out, lines, i = [], cmd.split("\n"), 0
    while i < len(lines):
        out.append(lines[i])
        m = re.search(r"<<-?\s*['\"]?([A-Za-z_]\w*)['\"]?", lines[i])
        i += 1
        if m:
            while i < len(lines) and lines[i].strip() != m.group(1):
                i += 1
            i += 1
    return "\n".join(out)


def discard_targets(cmd, cwd):
    """指令會丟掉哪些路徑的內容：[(種類, 絕對路徑)]。種類 any／untracked／tracked。"""
    import shlex
    out = []
    for part in re.split(r"&&|\|\||;|\||\n", _strip_heredocs(cmd)):
        try:
            toks = shlex.split(part, posix=True)
        except ValueError:
            toks = part.split()
        while toks and re.match(r"^\w+=", toks[0]):  # 前綴的環境變數
            toks = toks[1:]
        if not toks:
            continue
        if toks[0] == "cd" and len(toks) > 1:  # 同一條指令裡的 cd 會改變後面相對路徑的意思
            cwd = os.path.normpath(os.path.join(cwd, toks[1]))
            continue
        paths = lambda xs: [os.path.normpath(os.path.join(cwd, x)) for x in xs if not x.startswith("-")]  # noqa: E731
        if toks[0] == "rm":
            out += [("any", p) for p in paths(toks[1:])]
        elif toks[0] == "git":
            i = 1
            while i < len(toks) and toks[i].startswith("-"):
                i += 2 if toks[i] in ("-C", "-c") else 1
            sub, rest = (toks[i] if i < len(toks) else ""), toks[i + 1:]
            if sub == "restore" and not ("--staged" in rest and "--worktree" not in rest and "-W" not in rest):
                out += [("any", p) for p in paths(rest)]
            elif sub == "checkout" and "--" in rest:
                out += [("any", p) for p in paths(rest[rest.index("--") + 1:])]
            elif sub == "checkout" and rest[:1] == ["."]:
                out.append(("any", cwd))
            elif sub == "clean" and any(r == "--force" or (re.match(r"^-[a-z]+$", r) and "f" in r) for r in rest):
                out += [("untracked", p) for p in (paths(rest) or [cwd])]
            elif sub == "reset" and "--hard" in rest:
                out.append(("tracked", cwd))
    return out


def preexisting(top, sd, pid):
    """開工前就存在的未提交變更：{路徑: 狀態, ...}，以及那棵基準快照（取回用）。"""
    evs = load(sd)[0]
    bases = [e for e in evs if e["kind"] == "base" and str(e.get("pid")) == str(pid)]
    mine = [e for e in evs if e["kind"] == "snap" and str(e.get("pid")) == str(pid)]
    if bases:
        tree, sha = bases[-1].get("tree"), bases[-1].get("head")
    elif mine:
        tree, sha = mine[0].get("tree"), mine[0].get("head")
    else:  # 這個程序還沒動過任何東西 → 現在的變更全都是開工前就在的
        tree, (sha, _, _) = fingerprint(top, sd), head(top)
    if not tree or not sha:
        return {}, None
    _, htree, _ = git(["rev-parse", f"{sha}^{{tree}}"], top)
    rc, out, _ = git(["diff-tree", "-r", "--name-status", htree, tree], top)
    if rc:
        return {}, tree
    got = {}
    for line in out.splitlines():
        st, _, path = line.partition("\t")
        if st in ("A", "M"):  # 開工時多出來的（未追蹤）或被改過的
            got[path] = st
    return got, tree


def discard_check(payload):
    cmd = ((payload.get("tool_input") or {}).get("command") or "")
    if "SE_ALLOW_DISCARD=1" in cmd:  # 使用者明確同意丟棄後，刻意加上的放行記號
        return 0
    loc = locate(payload.get("cwd") or os.getcwd())
    if not loc:
        return 0
    top, sd = loc
    targets = discard_targets(cmd, payload.get("cwd") or top)
    if not targets:
        return 0
    pre, tree = preexisting(top, sd, os.environ.get("CLAUDE_PID"))
    hit = []
    for kind, abspath in targets:
        rel = os.path.relpath(abspath, top).replace("\\", "/")
        if rel.startswith(".."):
            continue
        for path, st in pre.items():
            if not (rel == "." or path == rel or path.startswith(rel.rstrip("/") + "/")):
                continue
            if (kind == "untracked" and st != "A") or (kind == "tracked" and st != "M"):
                continue
            _, now, _ = git(["rev-parse", "-q", "--verify", f"HEAD:{path}"], top)
            _, then, _ = git(["rev-parse", "-q", "--verify", f"{tree}:{path}"], top)
            if now and now == then:  # 已經 commit 進去了，丟掉工作樹的也救得回來
                continue
            hit.append(path)
    hit = sorted(set(hit))
    if not hit:
        return 0
    shown = "、".join(hit[:8]) + (f" …共 {len(hit)} 個" if len(hit) > 8 else "")
    sys.stderr.write(
        f"[guard-discard] 這個指令會丟掉**開工前就存在**的未提交變更（不是這個 session 做的）：{shown}\n"
        "丟掉就回不來——這通常是使用者自己的工作。原樣保留，只動你這次要改的檔。\n"
        "使用者明確要你丟棄時：先把這份清單講給他、拿到同意，再在指令前加 SE_ALLOW_DISCARD=1。\n"
        f"（開工時的內容在快照裡：git show {(tree or '')[:12]}:<路徑>）\n")
    return 2


# ---------- hook 入口 ----------

def record(stdin_text):
    at = now()
    try:
        p = json.loads(stdin_text or "{}")
    except ValueError:
        return 0
    loc = locate(p.get("cwd") or os.getcwd())
    if not loc:
        return 0
    top, sd = loc
    ev, sid = p.get("hook_event_name", ""), (p.get("session_id") or "")[:8]
    pid = os.environ.get("CLAUDE_PID")  # hook 繼承 Claude Code 的環境；身分用程序（見 fold）
    # 觸發評測：照常記錄，但不印簡報——簡報點名 se-resume，會汙染量測（docs/lessons/0011）
    say = (lambda *a, **k: None) if os.environ.get("SE_EVAL") else print
    who = {"session": sid, "pid": pid}
    try:
        if ev in ("PostToolUse", "PostToolUseFailure"):
            sha, htree, br = head(top)
            e = {"kind": "snap", "at": at, **who, "tool": p.get("tool_name"),
                 "tree": fingerprint(top, sd), "head": sha, "head_tree": htree, "branch": br}
            if p.get("agent_id"):
                e["agent"] = p["agent_id"]
            if p.get("tool_name") == "Bash":  # 學習訊號用：同一種指令先失敗後成功（見 learned）
                e["cmd"] = cmd_head((p.get("tool_input") or {}).get("command", ""))
            if ev == "PostToolUseFailure":
                e["failed"] = True
                e["error"] = clip(str(p.get("error") or "").split("\n")[0], 160)
            append(sd, e)
        elif ev == "Stop":
            append(sd, {"kind": "turn_end", "at": at, **who})
        elif ev == "StopFailure":
            append(sd, {"kind": "turn_failed", "at": at, **who, "error": p.get("error")})
        elif ev == "SessionStart":
            st = fold(load(sd)[0], me=pid)  # 新程序還沒有自己的事件，別人的（含 --resume 前的自己）全算
            if worth_showing(st, sd, p.get("source", "")):
                say(brief(top, sd, st))
                append(sd, {"kind": "brief", **who, "for": st["last_snap"]["at"] if st["last_snap"] else None})
            sha, _, br = head(top)  # 開工基準：之後 CLI 用它分辨「開工前別人改的」與「開工後我自己改的」
            append(sd, {"kind": "base", "at": now(), **who, "tree": fingerprint(top, sd), "head": sha, "branch": br})
        elif ev == "UserPromptSubmit":
            # 只在「明確因 API 錯誤中止」（例如用量上限）後的下一則訊息提醒一次。
            # 沒有結束標記不算：回合進行中也會有訊息插進來（背景工作完成的通知、排隊的訊息）——
            # 2026-09-23 在自己的 session 裡實際誤報過（docs/lessons/0011）。
            st = fold(load(sd)[0], me=pid)
            if st["failed"] and str(pid) not in st["briefed"]:
                say(brief(top, sd, st))
                append(sd, {"kind": "brief", **who, "for": st["last_snap"]["at"]})
            append(sd, {"kind": "prompt", "at": at, **who, "text": clip(p.get("prompt") or "", 300)})
    except Exception:
        # 記錄器不能擋工作，但壞掉要看得到（docs/lessons/0002）：寫進 error.log，簡報會提示
        try:
            sd.mkdir(parents=True, exist_ok=True)
            with open(sd / "error.log", "a", encoding="utf-8") as f:
                f.write(f"--- {at} {ev}\n{traceback.format_exc()}")
        except OSError:
            pass
    return 0


# ---------- CLI ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description="斷點續跑")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("record")
    sub.add_parser("resume")
    sub.add_parser("status")
    sub.add_parser("close")
    sub.add_parser("learned")
    sub.add_parser("discard-check")
    st_ = sub.add_parser("step")
    st_.add_argument("action", choices=["add", "done"])
    st_.add_argument("id")
    st_.add_argument("title", nargs="?", default="")
    st_.add_argument("--done-when")
    dc = sub.add_parser("decide")
    dc.add_argument("question")
    dc.add_argument("answer")
    vf = sub.add_parser("verify")
    vf.add_argument("command", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)

    if a.cmd == "record":  # payload 是 UTF-8；Windows 的 stdin 預設是 cp950，要讀位元組自己解
        return record(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    if a.cmd == "discard-check":  # PreToolUse：exit 2 擋下，stderr 給模型看
        try:
            return discard_check(json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}"))
        except Exception:
            return 0  # 判斷不了就放行：快照仍在，內容救得回來

    loc = locate(os.getcwd())
    if not loc:
        print("[checkpoint] 不在 git repo 裡，沒有斷點可用。")
        return 2
    top, sd = loc

    if a.cmd in ("resume", "status"):
        evs, bad = load(sd)
        st = fold(evs, me=os.environ.get("CLAUDE_PID"))  # 從 agent 的 Bash 呼叫時，自己這個程序的事件算「還在跑」
        if not evs:
            print("[斷點] 沒有記錄。（沒有斷點不等於沒有中斷：hook 沒裝或沒跑時也會是這樣）")
            return 0
        if not (worth_showing(st, sd) or st["steps"] or st["decisions"] or st["verifies"] or st["live"]):
            print("[斷點] 上一段工作正常結束，沒有需要續跑的東西。")
            return 0
        print(brief(top, sd, st, run_probes=(a.cmd == "resume")))
        if bad:
            print(f"  （日誌有 {bad} 行殘缺，已跳過——通常是寫到一半被打斷）")
        return 0
    if a.cmd == "learned":  # 給 guard-done 用：這一回合「撞到才改對」而帳本沒被寫過 → 印出來、exit 3
        pid = os.environ.get("CLAUDE_PID")
        if not pid:
            return 0
        hits, t0 = learned(sd, pid)
        if not hits or lessons_touched_since(top, t0):
            return 0
        for h, err in hits:
            print(f"  - `{h}`：{err or '失敗後改對'}")
        return 3
    if a.cmd == "close":
        append(sd, {"kind": "close"})
        print("[checkpoint] 這段工作已結束，之後不再提示。")
        return 0
    if a.cmd == "step":
        if a.action == "add":
            append(sd, {"kind": "step_add", "id": a.id, "title": a.title, "done_when": a.done_when})
        else:
            append(sd, {"kind": "step_done", "id": a.id})
        print(f"[checkpoint] 步驟 {a.id} 已記錄（{a.action}）。")
        return 0
    if a.cmd == "decide":
        append(sd, {"kind": "decide", "q": a.question, "a": a.answer})
        print("[checkpoint] 決定已記錄，續跑後不會再問。")
        return 0
    if a.cmd == "verify":
        cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
        if not cmd:
            print("用法：checkpoint.py verify -- <指令...>")
            return 2
        run = ["bash", "-c", cmd[0]] if len(cmd) == 1 and " " in cmd[0] else cmd
        rc = subprocess.run(run).returncode
        tree = fingerprint(top, sd)
        shown = cmd[0] if run is not cmd else subprocess.list2cmdline(cmd)
        append(sd, {"kind": "verify", "cmd": shown, "exit": rc, "tree": tree})
        print(f"[checkpoint] 驗證已記錄：exit {rc}，綁定工作樹 {(tree or '?')[:10]}")
        return rc
    return 2


if __name__ == "__main__":
    sys.exit(main())
