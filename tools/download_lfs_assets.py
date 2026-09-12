#!/usr/bin/env python3
"""Download Git LFS files from GitHub when git-lfs is unavailable.

GitHub's normal archive/raw URLs contain the small LFS pointer. The media
endpoint serves the object itself for public repositories.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"
OID_RE = re.compile(rb"^oid sha256:([0-9a-f]{64})$", re.MULTILINE)
REMOTE_RE = re.compile(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$")


def run_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def github_repo() -> str:
    remote = run_git("config", "--get", "remote.origin.url")
    match = REMOTE_RE.search(remote.rstrip("/"))
    if not match:
        raise RuntimeError(f"Cannot parse a GitHub repository from origin: {remote}")
    return f"{match.group(1)}/{match.group(2)}"


def parse_pointer(data: bytes, label: Path | str) -> tuple[str, int] | None:
    if not data.startswith(POINTER_PREFIX):
        return None
    match = OID_RE.search(data)
    size_match = re.search(rb"^size ([0-9]+)$", data, re.MULTILINE)
    if not match or not size_match:
        raise RuntimeError(f"Malformed Git LFS pointer: {label}")
    return match.group(1).decode("ascii"), int(size_match.group(1))


def pointer_metadata(path: Path, root: Path) -> tuple[str, int] | None:
    try:
        with path.open("rb") as stream:
            result = parse_pointer(stream.read(4096), path)
            if result:
                return result
    except OSError:
        pass
    # After a successful fallback download the working tree no longer has
    # pointer text, so read the expected object metadata from Git itself.
    relative = path.relative_to(root).as_posix()
    pointer = subprocess.check_output(["git", "show", f"HEAD:{relative}"])
    return parse_pointer(pointer, relative)


def tracked_paths(root: Path) -> list[Path]:
    names = subprocess.check_output(
        ["git", "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", "HEAD"],
        text=True,
    ).splitlines()
    return [root / name for name in names]


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, expected_oid: str, expected_size: int, retries: int) -> None:
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(1, retries + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "badminton-trajectory-analysis-asset-fetcher/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with urlopen(Request(url, headers=headers), timeout=60) as response:
                if offset and response.status != 206:
                    partial.unlink()
                    offset = 0
                mode = "ab" if offset else "wb"
                with partial.open(mode) as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
            if partial.stat().st_size != expected_size:
                raise RuntimeError(
                    f"size mismatch: got {partial.stat().st_size}, expected {expected_size}"
                )
            actual_oid = sha256(partial)
            if actual_oid != expected_oid:
                raise RuntimeError(f"SHA-256 mismatch: got {actual_oid}, expected {expected_oid}")
            os.replace(partial, destination)
            return
        except (HTTPError, URLError, OSError, RuntimeError) as error:
            if attempt == retries:
                raise RuntimeError(f"download failed after {retries} attempts: {error}") from error
            wait = min(2 ** (attempt - 1), 8)
            print(f"  attempt {attempt} failed ({error}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="GitHub owner/repository; defaults to origin")
    parser.add_argument("--ref", default=None, help="Git ref; defaults to the current branch")
    parser.add_argument("--only", action="append", help="Only fetch this tracked path (repeatable)")
    parser.add_argument("--check", action="store_true", help="Only report missing or invalid assets")
    parser.add_argument("--dry-run", action="store_true", help="Print downloads without changing files")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    repo = args.repo or github_repo()
    ref = args.ref or run_git("branch", "--show-current") or "HEAD"
    paths = tracked_paths(root)
    if args.only:
        selected = {Path(item) for item in args.only}
        paths = [path for path in paths if path.relative_to(root) in selected]

    assets = []
    for path in paths:
        pointer = pointer_metadata(path, root)
        if pointer:
            assets.append((path, *pointer))
    if not assets:
        print("No Git LFS pointer files found.")
        return 0

    failures = 0
    for path, expected_oid, expected_size in assets:
        relative = path.relative_to(root).as_posix()
        valid = path.exists() and path.stat().st_size == expected_size and sha256(path) == expected_oid
        if valid:
            print(f"OK       {relative} ({expected_size} bytes)")
            continue
        url = f"https://media.githubusercontent.com/media/{repo}/{quote(ref, safe='')}/{quote(relative, safe='/')}"
        if args.check:
            print(f"MISSING  {relative} -> {url}")
            failures += 1
            continue
        if args.dry_run:
            print(f"DOWNLOAD {relative} <- {url}")
            continue
        print(f"DOWNLOAD {relative} ({expected_size} bytes)")
        try:
            download(url, path, expected_oid, expected_size, max(1, args.retries))
            print(f"OK       {relative}")
        except RuntimeError as error:
            print(f"ERROR    {relative}: {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
