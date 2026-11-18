import json, os, subprocess, sys
from pathlib import Path

for _s in (sys.stdin, sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass


def mode_result(mode):
    return 2 if mode == 'block' else 1


def read_payload():
    try:
        value = json.loads(sys.stdin.read())
    except Exception:
        value = {}
    return None, value if isinstance(value, dict) else {}


def root():
    return Path(os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd())

MODE_ENV='SE_GUARD_DONE_MODE';DEFAULT_MODE='block'
def main():
    _,p=read_payload(); project=root()
    if p.get('stop_hook_active') is True or not (project/'.claude/skills/INDEX.md').is_file():return 0
    fake='{"tool_name":"Bash","tool_input":{"command":"git commit"}}'; problems=[]
    for name in ('check_router.py','check_memory.py'):
        path=Path(__file__).with_name(name)
        if path.is_file():
            r=subprocess.run([sys.executable,str(path)],input=fake,text=True,capture_output=True,encoding='utf-8',env={**os.environ,'CLAUDE_PROJECT_DIR':str(project)})
            if r.returncode:problems.append(f'--- {name} ---\n{r.stderr}')
    if not problems and not os.environ.get('SE_EVAL') and os.environ.get('SE_LEARN_NUDGE','on')!='off' and (project/'docs/lessons').is_dir():
        r=subprocess.run([sys.executable,str(project/'.claude/tools/checkpoint.py'),'learned'],cwd=project,capture_output=True,text=True,encoding='utf-8')
        if r.returncode==3:
            print('[guard-done] 這一回合有「撞到才改對」的情形：\n'+r.stdout,file=sys.stderr)
            return mode_result(os.environ.get(MODE_ENV,DEFAULT_MODE))
    if not problems:return 0
    print('[guard-done] 結束前自檢未通過——配置目前不一致。\n'+'\n'.join(problems),file=sys.stderr)
    return mode_result(os.environ.get(MODE_ENV,DEFAULT_MODE))
if __name__=='__main__':raise SystemExit(main())
