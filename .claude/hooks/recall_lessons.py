import os, re, sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

MAX = 10


def root():
    return Path(os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd())

DEFAULT_MODE='always'
def main():
    if os.environ.get('SE_EVAL'):return 0
    project=root(); home=__import__('pathlib').Path(os.environ.get('SERENDIPITY_HOME',__import__('pathlib').Path.home()/'.claude/serendipity'))
    gi=home/'lessons/INDEX.md'; li=project/'docs/lessons/INDEX.md'
    rows=[x for x in gi.read_text(encoding='utf-8').splitlines() if re.match(r'^\| \[G\d+',x)] if gi.is_file() else []
    local=sum(bool(re.match(r'^\| \[L\d+',x)) for x in li.read_text(encoding='utf-8').splitlines()) if li.is_file() else 0
    if not rows and not local:return 0
    print(f'[Serendipity] 領悟帳本：本專案 {local} 則、跨專案 {len(rows)} 則。')
    if rows:
        print('跨專案（在至少兩個專案各自撞到過的）：')
        for row in rows[:MAX]:
            m=re.match(r'^\| \[(G\d+)\]\([^)]*\) \| ([^|]*)\|',row)
            if m:print(f'  {m.group(1)} {m.group(2)}')
        if len(rows) > MAX:print(f'  …另有 {len(rows) - MAX} 則，用 lessons.py list --tag <關鍵字> 查')
    print('任務似曾相識時用 se-epiphany 的召回模式；領域全新時用 se-acquire。')
    return 0
if __name__=='__main__':raise SystemExit(main())
