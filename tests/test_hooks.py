from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


class HookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="SE 測試 ")
        self.repo = Path(self.temp.name) / "含 空白 中文"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        (self.repo / "起始.txt").write_text("x", encoding="utf-8", newline="")
        self.git("add", ".")
        self.git("commit", "-m", "init")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> None:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def run_hook(self, name: str, payload: str | dict, force_error: bool = False) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(self.repo)
        if force_error:
            env["SE_HOOK_FORCE_ERROR"] = "1"
        raw = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return subprocess.run(
            [sys.executable, str(HOOKS / name)], input=raw, capture_output=True,
            text=True, encoding="utf-8", env=env, timeout=5,
        )

    def test_branch_rejection_really_blocks(self) -> None:
        result = self.run_hook("guard_branch.py", {"tool_name": "Edit", "tool_input": {"file_path": "中文 路徑.py"}})
        self.assertEqual(1, result.returncode)
        self.assertIn("guard-branch", result.stderr)

    def test_feature_branch_allows_write(self) -> None:
        self.git("checkout", "-b", "feat/test")
        result = self.run_hook("guard_branch.py", {"tool_name": "Write", "tool_input": {"file_path": "有 空白.txt"}})
        self.assertEqual(0, result.returncode)

    def test_destructive_git_requires_backup_tag(self) -> None:
        result = self.run_hook("guard_critical.py", {"tool_name": "Bash", "tool_input": {"command": "git reset --hard HEAD~1"}})
        self.assertEqual(2, result.returncode)
        self.git("tag", "backup/test")
        result = self.run_hook("guard_critical.py", {"tool_name": "Bash", "tool_input": {"command": "git reset --hard HEAD~1"}})
        self.assertEqual(0, result.returncode)

    def test_bad_payload_blocks_high_risk_but_allows_low_risk(self) -> None:
        high = self.run_hook("guard_branch.py", '{bad "Edit" "secrets/key"')
        low = self.run_hook("guard_branch.py", "{bad harmless status")
        self.assertEqual(2, high.returncode)
        self.assertEqual(0, low.returncode)
        self.assertIn("INTERNAL", high.stderr)

    def test_internal_exception_blocks_high_risk_only(self) -> None:
        high = self.run_hook("guard_critical.py", {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}}, True)
        low = self.run_hook("guard_critical.py", {"tool_name": "Bash", "tool_input": {"command": "git status"}}, True)
        self.assertEqual(2, high.returncode)
        self.assertEqual(0, low.returncode)

    def test_protected_unicode_path_is_high_risk_on_error(self) -> None:
        result = self.run_hook("guard_branch.py", {"tool_name": "Edit", "tool_input": {"file_path": "中文 資料/secrets/金鑰.txt"}}, True)
        self.assertEqual(2, result.returncode)

    def test_break_glass_is_consumed_once(self) -> None:
        marker = self.repo / ".claude" / "hooks" / "BREAK_GLASS"
        marker.parent.mkdir(parents=True)
        marker.write_text("once", encoding="utf-8", newline="")
        payload = {"tool_name": "Edit", "tool_input": {"file_path": "x"}}
        self.assertEqual(0, self.run_hook("guard_branch.py", payload).returncode)
        self.assertFalse(marker.exists())
        self.assertEqual(1, self.run_hook("guard_branch.py", payload).returncode)


if __name__ == "__main__":
    unittest.main()
