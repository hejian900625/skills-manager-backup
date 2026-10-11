---
name: github-repo-fetch-windows
description: This skill should be used when a GitHub repository needs to be fetched, cloned, or downloaded onto this Windows machine — for example "pull repo X to D:\\source_code", "clone this GitHub project", or "download the source of owner/repo". It covers the blocked git endpoints in this environment, the codeload archive route that actually works, and the Windows symlink failure during tar extraction. It also covers the GitHub REST API calls used to inspect a repo (metadata, README, languages, releases) before deciding to download it.
version: 1.0.0
agent_created: true
---

# Fetching GitHub repos on this Windows machine

## Environment facts (verified 2026-10-05)

- `github.com`'s **git protocol entry is blocked**: `git clone https://github.com/...` hangs for many minutes with zero bytes downloaded (`info/refs?service=git-upload-pack` times out).
- `api.github.com` and `codeload.github.com` **work fine**; codeload sustains roughly 15 MB/s.
- `raw.githubusercontent.com` returned empty in this environment — prefer the API when file content is needed.
- The `gh-proxy.com` mirror prefix works for small repos but **also stalls on large ones** (a `--depth 1` clone of a 490 MB repo ran 9 minutes at 0 bytes). Skip straight to the archive route when the repo is big.
- Windows `tar -xzf` **fails on repos containing symlinks** with `Cannot unlink: Permission denied` and aborts mid-extraction. Extract with Python `tarfile` and skip link members instead.

Do not spend time attempting `git clone` on a repo larger than a few tens of MB. Go straight to Step 2.

## Step 0 — Inspect before downloading (cheap, no bytes)

Use `curl` against the REST API. Unauthenticated calls are rate-limited but fine for a handful of lookups.

```bash
# Metadata: stars, size, license, language, last push, default branch
curl -s --max-time 30 "https://api.github.com/repos/<owner>/<repo>" \
  | python -c "import sys,json;d=json.load(sys.stdin);print({k:d.get(k) for k in ['full_name','description','stargazers_count','forks_count','language','license','created_at','pushed_at','homepage','size','default_branch']})"

# README (base64 in JSON)
curl -s --max-time 40 "https://api.github.com/repos/<owner>/<repo>/readme" -H "Accept: application/vnd.github+json" \
  | python -c "import sys,json,base64;print(base64.b64decode(json.load(sys.stdin)['content']).decode('utf-8','replace')[:4000])"

# Language breakdown, latest release, search
curl -s --max-time 30 "https://api.github.com/repos/<owner>/<repo>/languages"
curl -s --max-time 30 "https://api.github.com/repos/<owner>/<repo>/releases/latest"
curl -s --max-time 30 "https://api.github.com/search/repositories?q=<term>&sort=stars&order=desc&per_page=15"
```

Defensive checks:
- A `message` key in the JSON means an error (usually 404 "Not Found"), not a real repo.
- The API `size` field is in **KB and wildly unreliable** as a download estimate — a repo reporting 505 MB produced a 23 MB tarball. Treat it as "big vs small" only.

## Step 1 — Confirm the codeload channel

```bash
curl -sIL --max-time 30 "https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main" | grep -iE "^(HTTP|content-disposition)"
```

A `200 OK` with `content-disposition: attachment; filename=<repo>-main.tar.gz` means the channel is healthy.

## Step 2 — Download the archive

```bash
cd /d/source_code
curl -sL --max-time 1200 -o <repo>-main.tar.gz \
  "https://codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main" && ls -lh <repo>-main.tar.gz
```

Run this in the background — a 120 MB archive takes about 3.5 minutes, a 23 MB one about 70 seconds. `--max-time 1200` gives headroom. A stalled download is diagnosed by `du -sh <target-dir>` staying at 0.

Tags and other refs work too: use `refs/tags/<tag>` instead of `refs/heads/main`.

## Step 3 — Extract with Python, not tar

`scripts/fetch_repo.py` does download plus extract in one shot:

```bash
"C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe" \
  "C:/Users/Lenovo/.workbuddy/skills/github-repo-fetch-windows/scripts/fetch_repo.py" \
  <owner>/<repo> --dest D:/source_code
```

Optional flags: `--ref`, `--tag`, `--name` (target dir name), `--keep-archive`.

The extraction loop strips the tarball's top-level `<repo>-<ref>/` component, rejects path traversal, and **skips symlink/hardlink members** (the Windows failure point). Expect one or two skipped links on repos such as hyperframes; they are cosmetic.

To extract an already-downloaded archive instead, the core loop is:

```python
import os, tarfile
with tarfile.open(archive, "r:gz") as tf:
    for m in tf:
        name = m.name.split("/", 1)[1] if "/" in m.name else m.name
        target = os.path.normpath(os.path.join(dst, name))
        if not target.startswith(dst) or m.issym() or m.islnk():
            continue
        if m.isfile():
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with tf.extractfile(m) as f, open(target, "wb") as o:
                o.write(f.read())
```

## Step 4 — Wrap up

- The result is a **snapshot, not a git repo** — no `.git`, no history. Say so when reporting.
- Delete the `.tar.gz` when done, or tell the user it is still there and how big it is.
- Clean up any throwaway helper scripts written into the destination directory.

## Updating an already-fetched snapshot

Do not re-clone. Either re-run Steps 2 and 3 into a fresh directory, or — if the copy is a real git checkout with a `mirror` remote — fetch through the proxy:

```bash
git -C <repo> fetch https://gh-proxy.com/https://github.com/<owner>/<repo>.git main:refs/remotes/origin/main
git -C <repo> rev-list --left-right --count HEAD...origin/main
```

`git fetch origin` against the real remote always fails here (CONNECT tunnel 502).

## Measuring a repo after extraction

```bash
du -sh <dir>                                      # on-disk size
find <dir> -type f | wc -l                        # file count
find <dir> -name "SKILL.md" | wc -l               # skill count
for d in <dir>/packages/*/; do echo "$d $(find "$d" -name '*.ts' | wc -l)"; done
```
