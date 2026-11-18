"""斷點記錄器（預寫日誌）：工具呼叫後記下工作樹指紋、記下回合有沒有正常結束，有斷點時印出續跑簡報。
邏輯在 tools/checkpoint.py，程序在 se-resume。這支是記錄器不是閘：任何失敗都 exit 0；
失敗寫進 .git/serendipity/error.log，由續跑簡報提示（docs/lessons/0002）。
"""
import os, subprocess, sys
from pathlib import Path

DEFAULT_MODE = "always"


def main() -> int:
    tool = Path(__file__).resolve().parents[1] / "tools" / "checkpoint.py"
    try:
        result = subprocess.run([sys.executable, str(tool), "record"], input=sys.stdin.buffer.read(),
                                cwd=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd(), timeout=25,
                                stdout=subprocess.PIPE)
        sys.stdout.buffer.write(result.stdout)
        sys.stdout.flush()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
