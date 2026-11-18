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

# Claude Code reads hook output as UTF-8; a zh-TW Windows console defaults to cp950, which
# garbles every non-ASCII message (lesson L0004's sibling). Force UTF-8 on our own streams.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
# Extended skills whose job a core skill took over. Not installed by `--layout flat`.
SUPERSEDED_NAME = "superseded.json"
LAYOUTS = ("bundle", "flat")


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
    if problems or dest_manifest is None:
        return problems
    layout = dest_manifest.get("layout", "bundle")
    if layout not in LAYOUTS:
        return [f"dest：不支援的 layout：{layout!r}"]
    try:
        expected = expected_manifest(bundle, layout)
    except BundleError as error:
        return [f"bundle：{error}"]
    if expected != dest_manifest:
        problems.append(f"bundle 與 dest 的 manifest 不一致（layout={layout}）")
    return problems


def superseded(bundle: Path) -> dict[str, list[str]]:
    path = bundle / "extended" / SUPERSEDED_NAME
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BundleError(f"{SUPERSEDED_NAME} 格式錯誤：{error}") from error
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v) for k, v in value.items()
    ):
        raise BundleError(f"{SUPERSEDED_NAME} 必須是 {{\"舊名稱\": [\"取代它的核心 skill\", ...]}}")
    return value


def flat_plan(bundle: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """Map bundle-relative paths to flat paths: core skills and top-level files as they are,
    extended skills lifted one level up. Core wins over an extended namesake; superseded
    extended skills are left out. Returns (pairs, skipped skill names)."""
    retired = superseded(bundle)
    core = {p.name for p in bundle.iterdir() if p.is_dir() and p.name != "extended"}
    pairs: list[tuple[str, str]] = []
    skipped: list[str] = []
    for path in sorted(p for p in bundle.rglob("*") if p.is_file() and p.name != MANIFEST_NAME):
        relative = path.relative_to(bundle).as_posix()
        parts = relative.split("/")
        if parts[0] != "extended":
            pairs.append((relative, relative))
            continue
        if len(parts) < 3:  # extended/superseded.json and other bookkeeping files
            continue
        name = parts[1]
        if name in core or name in retired:
            if name not in skipped:
                skipped.append(name)
            continue
        pairs.append((relative, "/".join(parts[1:])))
    for name in retired:
        for replacement in retired[name]:
            if replacement not in core:
                raise BundleError(f"{SUPERSEDED_NAME}：{name} 的取代者 {replacement} 不是核心 skill")
    return pairs, skipped


def flat_manifest(bundle: Path) -> dict[str, Any]:
    manifest, problems = load_manifest(bundle)
    if manifest is None or problems:
        raise BundleError("來源 manifest 無效：\n" + "\n".join(problems))
    hashes = {item["path"]: item["sha256"] for item in manifest["files"]}
    pairs, skipped = flat_plan(bundle)
    result = {key: value for key, value in manifest.items() if key != "files"}
    result["layout"] = "flat"
    result["skipped"] = skipped
    result["files"] = sorted(({"path": dst, "sha256": hashes[src]} for src, dst in pairs), key=lambda f: f["path"])
    return result


def expected_manifest(bundle: Path, layout: str) -> dict[str, Any]:
    if layout == "flat":
        return flat_manifest(bundle)
    manifest, problems = load_manifest(bundle)
    if manifest is None or problems:
        raise BundleError("來源 manifest 無效：\n" + "\n".join(problems))
    return manifest


def stage_copy(bundle: Path, stage: Path, layout: str) -> None:
    if layout == "bundle":
        shutil.copytree(bundle, stage)
        return
    stage.mkdir()
    pairs, _ = flat_plan(bundle)
    for src, dst in pairs:
        target = stage / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle / src, target)
    write_json(stage / MANIFEST_NAME, flat_manifest(bundle))


def install(bundle: Path, dest: Path, layout: str = "bundle") -> None:
    problems = validate(bundle)
    if problems:
        raise BundleError("來源 bundle 無效：\n" + "\n".join(problems))
    dest_parent = dest.parent.resolve()
    dest_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{dest.name}.stage-", dir=dest_parent))
    backup = dest_parent / f".{dest.name}.backup-{os.getpid()}"
    try:
        shutil.rmtree(stage)
        stage_copy(bundle, stage, layout)
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
    install_parser.add_argument(
        "--layout", choices=LAYOUTS, default="bundle",
        help="bundle：照 bundle 原樣（Agora 的 harness/se）；flat：每個 skill 一層（Claude Code 的 .claude/skills）",
    )
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
            install(args.bundle.resolve(), args.dest.resolve(), args.layout)
        else:
            command_check(args.bundle.resolve() if args.bundle else None, args.dest.resolve())
    except BundleError as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return 1
    print("通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
