#!/usr/bin/env python3
"""把仓库当前状态推成一个 commit（走 GitHub REST API，不碰 git 协议）。

为什么不用 git push：本机到 github.com 的 git 传输被代理挡死（CONNECT 502），
但 api.github.com 直连可用。

三个差分点（相比一次性搬运脚本）：
  1. 增量：本地按 git blob 规则算 sha1，与远端 tree 逐文件比，内容没变的不上传。
     日常改一两个文件 → 只传一两个 blob，几秒结束。
  2. 凭证：GH_TOKEN 环境变量 → macOS 钥匙串 → 报错并给出存放命令，不写任何文件。
  3. 模式：以 git index 的缓存模式为准（core.fileMode=false 时 index 不会被文件系统污染）。
     exFAT 上所有文件都是 755，靠 os.access 判断会把整站标成可执行。

用法：
    python3 tools/publish.py -m "改了什么"
    python3 tools/publish.py -m "..." --dry-run
"""
import base64
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.github.com"
BRANCH = "main"
KEYCHAIN_SERVICE = "pocket-llmcost-gh-token"

SKIP_DIRS = {".git", "__pycache__", ".cache", ".idea"}
SKIP_PATHS = {"build/dist", "build/work"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SCRIPT_SUFFIX = {".sh", ".command", ".bat", ".ps1"}


def remote_parts():
    """从 git remote 读 OWNER/REPO；读不到再用常量。"""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        out = ""
    if "github.com" in out:
        slug = out.split("github.com")[-1].lstrip(":/").removesuffix(".git").strip("/")
        if slug.count("/") == 1:
            owner, repo = slug.split("/")
            return owner, repo
    return "blackinkvc", "pocket-llmcost"


def guard_remote_ahead(head, dry, force):
    """远端 HEAD 不在本地历史里 → 本地落后，整棵树覆盖会删掉别人的提交。

    这个脚本不走 git 协议，而是拿本地文件拼一棵新树盖上去；
    远端有、本地没有的文件会在同一次提交里被标成删除。
    真出过事：另一个会话刚推了「算力中心」板块，这边推一次就把它 7 个文件删了。
    """
    if dry or force or not (ROOT / ".git").exists():
        return
    r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", head + "^{commit}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        return
    sys.exit(
        "远端 HEAD %s 不在本地历史里 —— 本地落后于远端。\n"
        "  这个脚本是整棵树覆盖：现在推，远端新增的文件会被删掉。\n"
        "  先把远端内容合进来（git fetch / 手工取回），或确认以本地为准加 --force-remote。"
        % head[:8])


def token(soft=False):
    t = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if t:
        return t
    try:
        t = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        t = ""
    if t:
        return t
    if soft:
        return None
    sys.exit(
        "没有凭证。二选一：\n"
        "  A) 存进钥匙串（只做一次，之后永久免输）：\n"
        "     security add-generic-password -s %s -a \"$USER\" -w ghp_你的token -U\n"
        "  B) 临时给：GH_TOKEN=ghp_xxx python3 tools/publish.py -m \"说明\"\n"
        "token 权限：classic 勾 repo + workflow；fine-grained 给 Contents 读写 + Workflows 读写。"
        % KEYCHAIN_SERVICE)


class Client:
    def __init__(self, tok):
        self.tok = tok
        self.n = 0

    def call(self, method, path, body=None):
        url = path if path.startswith("https://") else API + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.tok)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data:
            req.add_header("Content-Type", "application/json")
        self.n += 1
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            raise SystemExit("%s %s -> HTTP %s\n%s" % (method, path, e.code, detail))


def blob_sha(raw):
    """git 的 blob 对象哈希，可直接和 tree API 返回的 sha 对比。"""
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def index_modes():
    """git index 里的 path -> (100644|100755)。外置盘上不能信文件系统权限位。"""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-s"],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return {}
    modes = {}
    for line in out.splitlines():
        try:
            meta, path = line.split("\t", 1)
            modes[path] = meta.split()[0]
        except ValueError:
            continue
    return modes


def local_files():
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if set(rel.parts) & SKIP_DIRS:
            continue
        s = str(rel).replace(os.sep, "/")
        if any(s == x or s.startswith(x + "/") for x in SKIP_PATHS):
            continue
        if rel.name in SKIP_NAMES or rel.name.startswith("._"):
            continue
        out.append((s, p))
    return out


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    force = "--force-remote" in argv
    msg = "chore: 更新站点"
    for i, a in enumerate(argv):
        if a in ("-m", "--message") and i + 1 < len(argv):
            msg = argv[i + 1]
        elif a.startswith("--message="):
            msg = a.split("=", 1)[1]

    owner, repo = remote_parts()
    files = local_files()
    modes = index_modes()
    print("仓库 %s/%s，本地 %d 个文件" % (owner, repo, len(files)))

    c = Client(token(soft=dry))
    if dry and c.tok is None:
        print("（dry-run 且无凭证：无法读远端，下面按「全部新增」估算）")

    # 远端现状（dry-run 也要读，才能报「会有几个变更」；无 token 时按全新处理）
    remote_files, base_tree, head = {}, None, None
    if c.tok:
        ref = c.call("GET", "/repos/%s/%s/git/ref/heads/%s" % (owner, repo, BRANCH))
        head = ref["object"]["sha"]
        commit = c.call("GET", "/repos/%s/%s/git/commits/%s" % (owner, repo, head))
        base_tree = commit["tree"]["sha"]
        tree = c.call("GET", "/repos/%s/%s/git/trees/%s?recursive=1" % (owner, repo, base_tree))
        if tree.get("truncated"):
            sys.exit("远端文件过多，tree 被截断；这条脚本不适合这么大的仓库，改用 git 客户端。")
        remote_files = {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}
        print("远端 HEAD %s（%s）" % (head[:8], commit["message"].splitlines()[0][:50]))
        guard_remote_ahead(head, dry, force)

    entries, stat = [], {"same": 0, "add": 0, "mod": 0, "up": 0}
    for s, p in files:
        raw = p.read_bytes()
        sha = blob_sha(raw)
        old = remote_files.get(s)
        if old == sha:
            stat["same"] += 1
            entries.append({"path": s, "mode": modes.get(s, "100644"), "type": "blob", "sha": sha})
            continue
        stat["add" if old is None else "mod"] += 1
        if c.tok:
            blob = c.call("POST", "/repos/%s/%s/git/blobs" % (owner, repo), {
                "content": base64.b64encode(raw).decode(),
                "encoding": "base64",
            })
            sha = blob["sha"]
            stat["up"] += 1
        mode = modes.get(s) or ("100755" if p.suffix in SCRIPT_SUFFIX else "100644")
        entries.append({"path": s, "mode": mode, "type": "blob", "sha": sha})

    local_paths = {s for s, _p in files}
    gone = sorted(p for p in remote_files if p not in local_paths)

    print("未变 %d · 新增 %d · 修改 %d · 上传 %d · 远端多余 %d"
          % (stat["same"], stat["add"], stat["mod"], stat["up"], len(gone)))
    for p in gone[:20]:
        print("  删 ", p)

    if dry or (stat["add"] == stat["mod"] == len(gone) == 0):
        print("没有需要提交的变更。")
        return

    for p in gone:
        entries.append({"path": p, "mode": "100644", "type": "blob", "sha": None})

    new_tree = c.call("POST", "/repos/%s/%s/git/trees" % (owner, repo),
                      {"base_tree": base_tree, "tree": entries})
    new = c.call("POST", "/repos/%s/%s/git/commits" % (owner, repo), {
        "message": msg, "tree": new_tree["sha"], "parents": [head],
    })
    c.call("PATCH", "/repos/%s/%s/git/refs/heads/%s" % (owner, repo, BRANCH),
           {"sha": new["sha"], "force": False})
    print("✓ 已推送 %s（API 调用 %d 次）" % (new["sha"][:8], c.n))


if __name__ == "__main__":
    main()
