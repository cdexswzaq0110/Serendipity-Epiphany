"""跑 tests/hooks_selftest.sh：main 的 hook 自測（139 條，含 canonical router 案例）原樣檢驗 Python hooks。

需要 bash 與 git（Claude Code 在 Windows 上本來就需要 Git Bash）。找不到 bash 時明確略過，而不是假裝通過。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HooksSelftest(unittest.TestCase):
    def test_every_main_selftest_case_passes_against_the_python_hooks(self) -> None:
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("找不到 bash：hooks 自測沒有執行")
        result = subprocess.run([bash, str(ROOT / "tests" / "hooks_selftest.sh")], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=600)
        out = result.stdout + result.stderr
        failed = [line for line in out.splitlines() if line.lstrip().startswith("FAIL")]
        self.assertEqual([], failed, out[-4000:])
        match = re.search(r"通過 (\d+)／失敗 (\d+)", out)
        self.assertIsNotNone(match, out[-2000:])
        self.assertEqual("0", match.group(2))
        self.assertGreaterEqual(int(match.group(1)), 139)
        self.assertEqual(0, result.returncode, out[-2000:])


if __name__ == "__main__":
    unittest.main()
