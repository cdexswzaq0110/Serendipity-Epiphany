from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sync_skills", ROOT / "scripts" / "sync_skills.py")
sync = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(sync)


class SyncSkillsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.dest = self.root / "dest"
        sync.build(ROOT / "skills", self.bundle, ROOT)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_install_check_round_trip(self) -> None:
        sync.install(self.bundle, self.dest)
        self.assertEqual([], sync.validate(self.dest))
        self.assertEqual([], sync.compare_manifests(self.bundle, self.dest))

    def test_check_detects_modified_deleted_and_extra_files(self) -> None:
        cases = ("modified", "deleted", "extra")
        for case in cases:
            with self.subTest(case=case):
                if self.dest.exists():
                    shutil.rmtree(self.dest)
                sync.install(self.bundle, self.dest)
                target = next(p for p in self.dest.rglob("SKILL.md"))
                if case == "modified":
                    target.write_text(target.read_text(encoding="utf-8") + "改", encoding="utf-8", newline="")
                elif case == "deleted":
                    target.unlink()
                else:
                    (self.dest / "extra.txt").write_text("extra", encoding="utf-8", newline="")
                self.assertTrue(sync.validate(self.dest))

    def test_crlf_and_lf_hash_are_equal(self) -> None:
        lf = self.root / "lf.txt"
        crlf = self.root / "crlf.txt"
        lf.write_bytes("甲  \n乙\n".encode())
        crlf.write_bytes("甲  \r\n乙\r\n".encode())
        self.assertEqual(sync.file_hash(lf), sync.file_hash(crlf))

    def test_failed_replace_restores_complete_old_dest(self) -> None:
        self.dest.mkdir()
        marker = self.dest / "old.txt"
        marker.write_text("old", encoding="utf-8", newline="")
        real_replace = sync.os.replace

        def fail_stage(source: Path, target: Path) -> None:
            if Path(target) == self.dest and ".stage-" in Path(source).name:
                raise OSError("occupied")
            real_replace(source, target)

        with mock.patch.object(sync.os, "replace", side_effect=fail_stage):
            with self.assertRaises(sync.BundleError):
                sync.install(self.bundle, self.dest)
        self.assertEqual("old", marker.read_text(encoding="utf-8"))
        self.assertEqual(["old.txt"], [p.name for p in self.dest.iterdir()])

    def test_flat_layout_puts_every_skill_one_level_deep(self) -> None:
        # Claude Code only discovers .claude/skills/<name>/SKILL.md.
        sync.install(self.bundle, self.dest, "flat")
        self.assertEqual([], sync.validate(self.dest))
        self.assertEqual([], sync.compare_manifests(self.bundle, self.dest))
        self.assertFalse((self.dest / "extended").exists())
        skill_files = list(self.dest.rglob("SKILL.md"))
        self.assertTrue(skill_files)
        for path in skill_files:
            self.assertEqual(self.dest, path.parent.parent, path)
        core = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir() and p.name != "extended"}
        retired = json.loads((ROOT / "skills" / "extended" / "superseded.json").read_text(encoding="utf-8"))
        extended = {p.name for p in (ROOT / "skills" / "extended").iterdir() if p.is_dir()}
        installed = {p.parent.name for p in skill_files}
        self.assertEqual(core | (extended - core - set(retired)), installed)
        manifest = json.loads((self.dest / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("flat", manifest["layout"])
        self.assertEqual(sorted((extended & core) | set(retired)), sorted(manifest["skipped"]))
        # The core skill wins over its extended namesake.
        for name in extended & core:
            self.assertEqual(
                (ROOT / "skills" / name / "SKILL.md").read_bytes(), (self.dest / name / "SKILL.md").read_bytes()
            )

    def test_flat_check_detects_tampering_and_layout_mismatch(self) -> None:
        sync.install(self.bundle, self.dest, "flat")
        target = next(p for p in self.dest.rglob("SKILL.md"))
        target.write_text(target.read_text(encoding="utf-8") + "改", encoding="utf-8", newline="")
        self.assertTrue(sync.validate(self.dest))
        shutil.rmtree(self.dest)
        sync.install(self.bundle, self.dest, "flat")
        manifest = json.loads((self.dest / "manifest.json").read_text(encoding="utf-8"))
        manifest["layout"] = "bundle"
        sync.write_json(self.dest / "manifest.json", manifest)
        self.assertTrue(sync.compare_manifests(self.bundle, self.dest))

    def test_superseded_must_name_a_core_skill(self) -> None:
        (self.bundle / "extended" / "superseded.json").write_text('{"se-focus": ["se-nope"]}', encoding="utf-8")
        with self.assertRaises(sync.BundleError):
            sync.flat_plan(self.bundle)

    def test_manifest_has_required_provenance(self) -> None:
        manifest = json.loads((self.bundle / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(1, manifest["schema_version"])
        self.assertEqual("2.0.0", manifest["bundle_version"])
        self.assertTrue(manifest["source_repo"])
        self.assertTrue(manifest["source_commit"])


class SkillFormatTest(unittest.TestCase):
    def test_frontmatter_and_core_line_limits(self) -> None:
        core = [p for p in (ROOT / "skills").iterdir() if p.is_dir() and p.name != "extended"]
        self.assertEqual(9, len(core))
        for directory in core + [p for p in (ROOT / "skills" / "extended").iterdir() if p.is_dir()]:
            with self.subTest(skill=directory.name):
                path = directory / "SKILL.md"
                lines = path.read_text(encoding="utf-8").splitlines()
                self.assertEqual("---", lines[0])
                end = lines.index("---", 1)
                fields = {}
                for line in lines[1:end]:
                    if not line.startswith("  ") and ":" in line:
                        key, value = line.split(":", 1)
                        fields[key] = value.strip()
                self.assertEqual(directory.name, fields.get("name"))
                self.assertLessEqual(len(fields.get("description", "")), 1024)
                self.assertTrue(fields.get("description"))
                self.assertTrue(set(fields) <= {"name", "description", "metadata"})
                if directory.parent.name == "skills":
                    self.assertLessEqual(len(lines), 200)


if __name__ == "__main__":
    unittest.main()
