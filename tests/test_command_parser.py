from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hooklib',ROOT/'.claude/hooks/hooklib.py')
hooklib=importlib.util.module_from_spec(spec);spec.loader.exec_module(hooklib)

class CommandParserTest(unittest.TestCase):
    def test_required_command_positions_and_global_options(self):
        yes=['git commit','x && git commit','x; git commit','x | git commit','x\ngit commit','( git reset --hard','for x in a; do git branch -D x; done','if x; then git commit; else git commit; fi','git -C dir commit','git -c a=b --no-pager commit','git -C x reset --hard']
        for command in yes:
            with self.subTest(command=command):
                self.assertTrue(hooklib.is_git_cmd(command,r'commit|reset\s+.*--hard|branch\s+.*-D'))

    def test_non_commands_and_heredoc(self):
        no=['echo git commit','printf "git reset --hard"',"python - <<'PY'\ngit commit\nPY\n", "cat <<EOF\ngit reset --hard\n"]
        for command in no:
            with self.subTest(command=command): self.assertFalse(hooklib.is_git_cmd(command,r'commit|reset\s+.*--hard'))

    def test_here_string_is_not_heredoc(self):
        self.assertTrue(hooklib.is_git_cmd('cat <<< x; git commit',r'commit'))
