#!/usr/bin/env python3
"""把仓库打成一个墨山插件包（`llmcost.moshanplug`）。

为什么要单独一个包，而不是让人 `git clone`
    装进中台的三条路（拖包 / 选文件夹 / 给网址）里，前两条要的是一个**自足的
    压缩包**：插件程序 + plugin.json + 启动脚本，解开就能跑。git clone 那种
    装法要机器上有 git、要能连 github.com —— 国内一半人卡在这一步。

包长什么样
    llmcost.moshanplug   ← 就是个 zip，扩展名不同而已
      plugin.json        版本、端口、更新地址
      run.command        启动脚本（双击也能用）
      llmcost.py 等      程序
      llmcost_ui.html    界面
      kit/  seed/        外壳与种子价目

怎么用
    python3 tools/make_plugin_pack.py                # 出到仓库根
    python3 tools/make_plugin_pack.py --out dist/    # 出到别处
    python3 tools/make_plugin_pack.py --check        # 只校验清单里有没有漏文件

发布：把产物拷到站点根（与 plugin.json 同级），名字固定为 llmcost.moshanplug。
**不要带版本号** —— plugin.json 的 update.pack 写的是固定名，版本号由 manifest
决定；带版本号就得每次改下载地址，用户手里的旧插件会一直指着老文件。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "llmcost.moshanplug"

# 插件跑起来必需的东西。少一个就是「装上了但起不来」，所以这里列全，
# --check 会逐个核。故意**不含**：站点页面（llmcost/*.html 是网页，不是插件）、
# build/、.github/、data/（那是站点快照，用户数据在 LLMCOST_DIR）。
FILES = [
    "plugin.json",
    "run.command",
    "llmcost.py",
    "llmcost_core.py",
    "llmcost_leaderboard.py",
    "llmcost_platforms.py",
    "pgkit.py",
    "lease.py",
    "llmcost_ui.html",
]
DIRS = [
    ("kit", (".css", ".js")),
    ("seed", (".csv", ".json")),
]
SKIP = {".DS_Store", "Thumbs.db"}


def _files() -> list[tuple[Path, str]]:
    """(绝对路径, 包内相对路径) 清单。"""
    out = []
    for f in FILES:
        p = ROOT / f
        if p.is_file():
            out.append((p, f))
    for d, exts in DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.name in SKIP or p.name.startswith("._"):
                continue
            if exts and p.suffix.lower() not in exts:
                continue
            out.append((p, str(p.relative_to(ROOT))))
    return out


def check() -> int:
    miss = [f for f in FILES if not (ROOT / f).is_file()]
    if miss:
        print("缺文件：")
        for m in miss:
            print("  -", m)
        return 1
    for d, _ in DIRS:
        if not (ROOT / d).is_dir():
            print("缺目录：", d)
            return 1
    man = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    for k in ("id", "name", "version"):
        if not man.get(k):
            print(f"plugin.json 少了 {k}")
            return 1
    upd = man.get("update") or {}
    if not isinstance(upd, dict) or not (upd.get("manifest") or upd.get("repo")):
        print("plugin.json 的 update 里既没有 manifest 也没有 repo —— 装进去查不了新版")
        return 1
    print(f"清单齐全：{len(FILES)} 个文件 + {len(DIRS)} 个目录；"
          f"id={man['id']} version={man['version']}")
    return 0


def build(out: Path) -> Path:
    items = _files()
    man = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        # plugin.json 放第一个：拖进中台时先看到名字和版本，预览快
        for p, rel in sorted(items, key=lambda x: (x[1] != "plugin.json", x[1])):
            # 启动脚本要带可执行位，否则解出来双击没反应（安装时中台也会补 chmod）
            info = zipfile.ZipInfo.from_file(p, rel)
            if rel.endswith((".command", ".sh")):
                info.external_attr = (0o100755 << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, p.read_bytes())
    tmp.replace(out)

    raw = out.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    print(f"已生成 {out}  ({len(raw) / 1024:.0f} KB)")
    print(f"  版本 {man['version']} · {len(items)} 个文件")
    print(f"  sha256 {sha}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="打墨山插件包（.moshanplug）")
    ap.add_argument("--out", default=str(ROOT / NAME), help="产物路径（默认仓库根）")
    ap.add_argument("--check", action="store_true", help="只校验清单，不打包")
    args = ap.parse_args(argv)

    rc = check()
    if rc or args.check:
        return rc
    build(Path(args.out).expanduser())
    return 0


if __name__ == "__main__":
    sys.exit(main())
