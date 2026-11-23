#!/usr/bin/env python3
"""从 GitHub 取一份源码到指定目录 —— 给 `git clone` 不通的网络用。

为什么需要这个：国内网络里 `github.com` 的 git 协议经常被掐（`CONNECT tunnel
failed` / `HTTP2 framing layer`），但 `api.github.com` 和 `codeload.github.com`
通常还通。所以拿不到 git 仓库时，退一步用「API 查最新 commit + codeload 下
tar.gz 解开」，代码一模一样，只是没有 .git 历史。

    python3 fetch_src.py --dest ~/某处/llmcost
    python3 fetch_src.py --dest ./x --rev 96599cb          # 钉某个 commit
    python3 fetch_src.py --dest ./x --dry-run              # 只报远端版本

装完会在目标目录写 `.llmcost-rev`（JSON：sha / branch / 下载时间 / 来源），
`--check` 用它在不下载的前提下判断「有没有新版本」，给 install.sh 做增量。

只用标准库。代理坏了会自己回退直连 —— 公司网/梯子挂掉时也能过。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.request

DEFAULT_REPO = "https://github.com/blackinkvc/pocket-llmcost"
REV_FILE = ".llmcost-rev"


def _open(url: str, timeout: int = 60, token: str = ""):
    """先按环境里的代理走，失败再直连 —— 两种都可能失败，但通常有一个能过。"""
    headers = {"User-Agent": "pocket-llmcost/fetch_src", "Accept": "*/*"}
    if token:
        headers["Authorization"] = "token " + token
    last = None
    for direct in (False, True):
        handler = urllib.request.ProxyHandler({}) if direct else urllib.request.ProxyHandler()
        req = urllib.request.Request(url, headers=headers)
        try:
            return urllib.request.build_opener(handler).open(req, timeout=timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:  # noqa: PERF203
            last = e
    raise SystemExit("取不到 %s\n  %s" % (url, last))


def repo_slug(repo: str) -> str:
    s = repo.strip().rstrip("/")
    for p in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if s.startswith(p):
            s = s[len(p):]
    if s.endswith(".git"):
        s = s[:-4]
    if s.count("/") != 1:
        raise SystemExit("看不懂的仓库地址：%s（要 owner/name）" % repo)
    return s


def remote_head(slug: str, branch: str, token: str) -> dict:
    api = "https://api.github.com/repos/%s" % slug
    with _open(api, 30, token) as r:
        info = json.load(r)
    branch = branch or info.get("default_branch") or "main"
    with _open("%s/commits/%s" % (api, branch), 30, token) as r:
        c = json.load(r)
    return {
        "sha": c["sha"],
        "short": c["sha"][:7],
        "branch": branch,
        "date": ((c.get("commit") or {}).get("committer") or {}).get("date", ""),
        "message": ((c.get("commit") or {}).get("message") or "").splitlines()[0][:72],
    }


def download(slug: str, rev: str, dest: str, token: str) -> int:
    url = "https://codeload.github.com/%s/tar.gz/%s" % (slug, rev)
    with _open(url, 180, token) as r:
        blob = r.read()

    tmp = dest + ".incoming"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        # 顶层只有一个 owner-repo-<ref>/ 目录，剥掉它
        members = []
        for m in tf.getmembers():
            head = m.name.split("/", 1)
            if len(head) < 2 or not head[1]:
                continue
            m.name = head[1]
            members.append(m)
        tf.extractall(tmp, members=members)

    n = 0
    for name in os.listdir(tmp):
        src = os.path.join(tmp, name)
        dst = os.path.join(dest, name)
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        n += 1
    shutil.rmtree(tmp, ignore_errors=True)
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="从 GitHub 取源码（clone 不通时的回退）")
    ap.add_argument("--dest", help="装到哪个目录（不存在就建）")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--rev", default="", help="分支或 commit，默认仓库默认分支")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    ap.add_argument("--dry-run", action="store_true", help="只报远端版本，不下载")
    ap.add_argument("--check", action="store_true", help="对比本地 .llmcost-rev，不下载")
    a = ap.parse_args(argv)

    slug = repo_slug(a.repo)
    head = remote_head(slug, a.rev, a.token)
    if a.dry_run:
        print(json.dumps(head, ensure_ascii=False))
        return 0

    if not a.dest:
        raise SystemExit("--dest 是必填（除非 --dry-run）")
    dest = os.path.abspath(os.path.expanduser(a.dest))
    rev_path = os.path.join(dest, REV_FILE)
    local = {}
    try:
        with open(rev_path, encoding="utf-8") as f:
            local = json.load(f)
    except (OSError, ValueError):
        pass

    same = local.get("sha") == head["sha"]
    if a.check:
        print(json.dumps({"sha": head["sha"], "short": head["short"], "local": local.get("sha", ""),
                          "up_to_date": same}, ensure_ascii=False))
        return 0
    if same and os.path.isfile(os.path.join(dest, "llmcost.py")):
        print("· %s 已是最新（%s），跳过下载" % (slug, head["short"]))
        return 0

    os.makedirs(dest, exist_ok=True)
    n = download(slug, head["sha"], dest, a.token)
    with open(rev_path, "w", encoding="utf-8") as f:
        json.dump({"sha": head["sha"], "short": head["short"], "branch": head["branch"],
                   "date": head["date"], "source": "codeload", "at": time.strftime("%Y-%m-%d %H:%M:%S")},
                  f, ensure_ascii=False, indent=1)
    print("· 已下载 %s@%s（%d 项，codeload）" % (slug, head["short"], n))
    print("  %s" % head["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
