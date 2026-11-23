#!/usr/bin/env python3
"""生成 llmcost/data/data.json —— 线上五页读的那份只读快照。

本地手跑和 GitHub Actions 里跑的是同一个脚本，口径不会分叉：
    python3 tools/make_snapshot.py

带图表（charts=True，约 440 KB，gzip 后 ~90 KB）。
剥掉 meta.root：那是本机绝对路径，线上不该出现。
"""
import datetime
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "llmcost" / "data" / "data.json"

sys.path.insert(0, str(ROOT))
os.environ.setdefault("LLMCOST_DIR", str(pathlib.Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "lc-snapshot"))

import llmcost  # noqa: E402


def version():
    try:
        meta = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        return str(meta.get("version") or "0")
    except Exception:
        return "0"


def main():
    p = llmcost.build_payload(charts=True)
    if not p.get("ok"):
        raise SystemExit("算账失败：%s" % p.get("error"))

    p.get("meta", {}).pop("root", None)

    now = datetime.datetime.now().astimezone()
    p["_snapshot"] = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "generated_ts": int(now.timestamp()),
        "version": version(),
        "released_at": now.strftime("%Y-%m-%d"),
        "sha256": "",
        "note": "线上为只读快照，装本地版可现场重新核验",
    }

    if not OUT.parent.is_dir():
        OUT.parent.mkdir(parents=True)
    OUT.write_text(json.dumps(p, ensure_ascii=False, separators=(",", ":"), default=str),
                   encoding="utf-8")
    print("写入 %s（%.0f KB）· 数据日 %s · %d 张图 · %d 条 API 价" % (
        OUT.relative_to(ROOT), OUT.stat().st_size / 1024,
        p["meta"]["date"], len(p.get("charts") or {}), len(p["api"])))


if __name__ == "__main__":
    main()
