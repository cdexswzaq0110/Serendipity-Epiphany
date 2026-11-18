"""核心 skill 會被裝進 Agora（harness/se）與 Codex（.agents/skills），相對連結不能跳出自己的目錄。

延伸 skill 的連結照 SE 自己的 .claude/skills/<name>/ 位置寫（main 既有的設計），不在此限。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"


class CorePortabilityTest(unittest.TestCase):
    def test_core_skill_links_stay_inside_the_skill(self) -> None:
        core = [p for p in SKILLS.iterdir() if p.is_dir() and p.name != "extended"]
        self.assertEqual(9, len(core))
        escaping = []
        for skill in core:
            for md in skill.rglob("*.md"):
                for link in re.findall(r"\]\(([^)#\s]+)", md.read_text(encoding="utf-8")):
                    if "://" in link:
                        continue
                    target = (md.parent / link).resolve()
                    if skill.resolve() not in target.parents:
                        escaping.append(f"{md.relative_to(SKILLS).as_posix()} -> {link}")
                    elif not target.is_file():
                        escaping.append(f"{md.relative_to(SKILLS).as_posix()} -> {link}（檔案不存在）")
        self.assertEqual([], escaping)

    def test_core_skill_body_fits_agora_injection_budget(self) -> None:
        # Agora 把核心 SKILL.md 本體注入提示詞，每個最多 4,000 字（references 不注入）。
        for skill in (p for p in SKILLS.iterdir() if p.is_dir() and p.name != "extended"):
            with self.subTest(skill=skill.name):
                self.assertLessEqual(len((skill / "SKILL.md").read_text(encoding="utf-8")), 4000)


if __name__ == "__main__":
    unittest.main()
