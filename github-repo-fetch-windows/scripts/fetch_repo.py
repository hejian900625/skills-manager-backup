#!/usr/bin/env python3
"""Fetch a GitHub repo snapshot on Windows without git.

Why: github.com's git-upload-pack entry is blocked in this environment, and
gh-proxy.com also stalls on large repos (9 min, 0 bytes observed). codeload
tarballs work. Windows `tar -xzf` then dies on symlinks with
"Cannot unlink: Permission denied", so extraction goes through Python tarfile
with symlink/hardlink members skipped.

Usage:
  python fetch_repo.py <owner/repo> [--ref main] [--dest DIR] [--keep-archive]

Examples:
  python fetch_repo.py pbakaus/impeccable --dest D:/source_code
  python fetch_repo.py heygen-com/hyperframes --ref v0.8.127 --dest D:/source_code
"""

import argparse
import os
import sys
import tarfile
import urllib.request

CODELOAD = "https://codeload.github.com/{repo}/tar.gz/refs/heads/{ref}"
CODELOAD_TAG = "https://codeload.github.com/{repo}/tar.gz/refs/tags/{ref}"


def download(url: str, dest: str) -> str:
    os.makedirs(dest, exist_ok=True)
    name = url.rsplit("/", 1)[-1]
    # e.g. tar.gz/refs/heads/main -> <repo>-main.tar.gz
    parts = url.split("/")
    repo = parts[4]
    name = f"{repo}-{url.rsplit('/', 1)[-1]}.tar.gz"
    path = os.path.join(dest, name)
    print(f"downloading {url}", flush=True)
    with urllib.request.urlopen(url, timeout=1800) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    print(f"saved {path} ({os.path.getsize(path) / 1e6:.1f} MB)", flush=True)
    return path


def extract(archive: str, dest_dir: str) -> tuple[int, list]:
    os.makedirs(dest_dir, exist_ok=True)
    skipped, count = [], 0
    with tarfile.open(archive, "r:gz") as tf:
        for m in tf:
            name = m.name.split("/", 1)[1] if "/" in m.name else m.name
            if not name:
                continue
            target = os.path.normpath(os.path.join(dest_dir, name))
            if not target.startswith(dest_dir):
                skipped.append(("TRAVERSAL", name))
                continue
            if m.issym() or m.islnk():
                skipped.append(("LINK", name))
                continue
            try:
                if m.isdir():
                    os.makedirs(target, exist_ok=True)
                elif m.isfile():
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with tf.extractfile(m) as src, open(target, "wb") as out:
                        out.write(src.read())
                    count += 1
            except OSError as e:
                skipped.append((f"ERR:{e}", name))
    return count, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", help="owner/repo")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--tag", action="store_true", help="treat --ref as a tag")
    ap.add_argument("--dest", default=".", help="parent directory")
    ap.add_argument("--name", default=None, help="target dir name (default: repo name)")
    ap.add_argument("--keep-archive", action="store_true")
    args = ap.parse_args()

    tmpl = CODELOAD_TAG if args.tag else CODELOAD
    url = tmpl.format(repo=args.repo, ref=args.ref)
    archive = download(url, args.dest)

    target = os.path.join(args.dest, args.name or args.repo.split("/")[-1])
    count, skipped = extract(archive, target)
    print(f"extracted {count} files -> {target}")
    if skipped:
        print(f"skipped {len(skipped)}:")
        for kind, name in skipped[:20]:
            print(f"  {kind}  {name}")
    if not args.keep_archive:
        os.remove(archive)
        print(f"removed {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
