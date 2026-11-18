import os, re, sys
try:
    from hooklib import changed_paths, command, is_git_cmd, mode_result, run_gate
except Exception as error:  # 判定規則缺席：往安全的方向失敗
    print(f"[check-memory] 無法載入 hooklib（{error}），判定不了，先擋下。", file=sys.stderr)
    raise SystemExit(2)
MODE_ENV="SE_CHECK_MEMORY_MODE"; DEFAULT_MODE="block"
def field(text, name):
    m=re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:return ""
    x=re.search(rf"^{re.escape(name)}:\s*(.*?)(?:\s+#.*)?$",m.group(1),re.M)
    return x.group(1).strip() if x else ""
def gate(payload, root):
    if not is_git_cmd(command(payload),r"commit"):return 0
    changed=changed_paths(root)
    if changed is not None and not any(p.replace('\\','/').startswith('docs/lessons/') for p in changed):return 0
    d=root/'docs/lessons'; index=d/'INDEX.md'
    if not d.is_dir() or not index.is_file():return 0
    problems=[]; it=index.read_text(encoding='utf-8')
    for f in sorted(d.glob('[0-9]*.md')):
        t=f.read_text(encoding='utf-8'); src=field(t,'source'); outcome=field(t,'outcome'); valid=field(t,'validated')
        if src not in {'self-observed','user-stated','external'}:problems.append(f"{f.name}：source 缺少或不合法")
        if outcome=='promoted' and src=='external':problems.append(f"{f.name}：external 不得升級")
        if outcome=='promoted' and not valid:problems.append(f"{f.name}：promoted 但 validated 空白")
        if f.name not in it:problems.append(f"{f.name}：INDEX 未列出")
    for name in set(re.findall(r"\(([0-9][0-9a-z-]*\.md)\)",it)):
        if not (d/name).is_file():problems.append(f"INDEX 指向不存在的 {name}")
    if not problems:return 0
    print('[check-memory] 記憶層准入檢查未通過：\n  '+'\n  '.join(problems),file=sys.stderr)
    return mode_result(os.environ.get(MODE_ENV,DEFAULT_MODE))
if __name__=='__main__':raise SystemExit(run_gate('check-memory',gate))
