#!/usr/bin/env python3
"""建立、安裝並驗證 Serendipity Agent Skills bundle。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"


class BundleError(Exception):
    pass


def normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    had_final_newline = text.endswith("\n")
    normalized = "\n".join(line.rstrip(" \t") for line in text.split("\n"))
    if had_final_newline and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized.encode("utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(normalized_bytes(path)).hexdigest()


def run_git(root: Path, *args: str) -> str:
    command = ["git", "-c", f"safe.directory={root.as_posix()}", *args]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise BundleError(f"git {' '.join(args)} 失敗：{result.stderr.strip()}")
    return result.stdout.strip()


def source_manifest(source: Path, repo_root: Path) -> dict[str, Any]:
    version = (source / "VERSION").read_text(encoding="utf-8").strip()
    files = []
    for path in sorted(p for p in source.rglob("*") if p.is_file() and p.name != MANIFEST_NAME):
        files.append({"path": path.relative_to(source).as_posix(), "sha256": file_hash(path)})
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "bundle_version": version,
        "source_repo": run_git(repo_root, "remote", "get-url", "origin"),
        "source_commit": run_git(repo_root, "rev-parse", "HEAD"),
        "files": files,
    }
    if run_git(repo_root, "status", "--porcelain"):
        manifest["source_dirty"] = True
    return manifest


def write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def build(source: Path, out: Path, repo_root: Path) -> None:
    if out.exists():
        raise BundleError(f"輸出目錄已存在：{out}")
    out.mkdir(parents=True)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = out / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.name != MANIFEST_NAME:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    write_json(out / MANIFEST_NAME, source_manifest(source, repo_root))
    problems = validate(out)
    if problems:
        raise BundleError("建置後驗證失敗：\n" + "\n".join(problems))


def load_manifest(root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = root / MANIFEST_NAME
    if not path.is_file():
        return None, [f"缺少 {MANIFEST_NAME}"]
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, [f"manifest 格式錯誤：{error}"]
    problems = []
    if not isinstance(value, dict):
        return None, ["manifest 必須是 JSON object"]
    required = {"schema_version", "bundle_version", "source_repo", "source_commit", "files"}
    for key in sorted(required - value.keys()):
        problems.append(f"manifest 缺少欄位：{key}")
    if value.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"不支援的 schema_version：{value.get('schema_version')!r}")
    if not isinstance(value.get("files"), list):
        problems.append("manifest files 必須是 array")
    return value, problems


def validate(root: Path) -> list[str]:
    manifest, problems = load_manifest(root)
    if manifest is None or problems:
        return problems
    expected: dict[str, str] = {}
    for index, item in enumerate(manifest["files"]):
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            problems.append(f"files[{index}] 格式錯誤")
            continue
        relative, digest = item.get("path"), item.get("sha256")
        if not isinstance(relative, str) or not relative or "\\" in relative:
            problems.append(f"files[{index}] 路徑錯誤：{relative!r}")
            continue
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            problems.append(f"files[{index}] 路徑逃逸：{relative}")
            continue
        if relative in expected:
            problems.append(f"manifest 重複路徑：{relative}")
        elif not isinstance(digest, str) or len(digest) != 64:
            problems.append(f"files[{index}] sha256 格式錯誤：{relative}")
        else:
            expected[relative] = digest
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.name != MANIFEST_NAME
    }
    for relative in sorted(expected.keys() - actual):
        problems.append(f"缺檔：{relative}")
    for relative in sorted(actual - expected.keys()):
        problems.append(f"多檔：{relative}")
    for relative in sorted(actual & expected.keys()):
        actual_hash = file_hash(root / relative)
        if actual_hash != expected[relative]:
            problems.append(f"hash 不符：{relative}（預期 {expected[relative]}，實際 {actual_hash}）")
    return problems


def compare_manifests(bundle: Path, dest: Path) -> list[str]:
    bundle_manifest, bundle_errors = load_manifest(bundle)
    dest_manifest, dest_errors = load_manifest(dest)
    problems = [*(f"bundle：{p}" for p in bundle_errors), *(f"dest：{p}" for p in dest_errors)]
    if not problems and bundle_manifest != dest_manifest:
        problems.append("bundle 與 dest 的 manifest 不一致")
    return problems


def install(bundle: Path, dest: Path) -> None:
    problems = validate(bundle)
    if problems:
        raise BundleError("來源 bundle 無效：\n" + "\n".join(problems))
    dest_parent = dest.parent.resolve()
    dest_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{dest.name}.stage-", dir=dest_parent))
    backup = dest_parent / f".{dest.name}.backup-{os.getpid()}"
    try:
        shutil.rmtree(stage)
        shutil.copytree(bundle, stage)
        stage_problems = validate(stage)
        if stage_problems:
            raise BundleError("暫存副本驗證失敗：\n" + "\n".join(stage_problems))
        if backup.exists():
            shutil.rmtree(backup)
        if dest.exists():
            os.replace(dest, backup)
        try:
            os.replace(stage, dest)
        except OSError as error:
            if backup.exists() and not dest.exists():
                os.replace(backup, dest)
            raise BundleError(
                f"無法替換 {dest}，可能有檔案被占用：{error}。關閉占用程式後重試。"
            ) from error
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if backup.exists() and dest.exists():
            shutil.rmtree(backup, ignore_errors=True)


def command_check(bundle: Path | None, dest: Path) -> None:
    problems = validate(dest)
    if bundle is not None:
        problems = [*(f"dest：{p}" for p in problems), *(f"bundle：{p}" for p in validate(bundle))]
        problems.extend(compare_manifests(bundle, dest))
    if problems:
        raise BundleError("驗證失敗：\n" + "\n".join(dict.fromkeys(problems)))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--out", type=Path, required=True)
    install_parser = sub.add_parser("install")
    install_parser.add_argument("--bundle", type=Path, required=True)
    install_parser.add_argument("--dest", type=Path, required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--bundle", type=Path)
    check_parser.add_argument("--dest", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "build":
            build(repo_root / "skills", args.out.resolve(), repo_root)
        elif args.command == "install":
            install(args.bundle.resolve(), args.dest.resolve())
        else:
            command_check(args.bundle.resolve() if args.bundle else None, args.dest.resolve())
    except BundleError as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return 1
    print("通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
