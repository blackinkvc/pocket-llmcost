#!/bin/bash
# Token 价格追踪 · 安装 / 更新
#
#   首次安装   ./install.sh
#   更新       ./install.sh --update         （= git pull --ff-only + 重启）
#   只装不启动 ./install.sh --no-launch
#   改位置     ./install.sh --code ~/某处/llmcost --data ~/某处/13-算价
#
# 它做三件事，全部可重复执行（跑第二遍就是「更新」）：
#   1. 把仓库拉到 <中台数据根>/_插件/llmcost（已有就是 git pull）；
#   2. 在 <中台数据根>/_工作台/plugins.json 里登记这个插件（同 id 覆盖内置那一行）；
#   3. 拉起来（可选），并等 /api/ping 通过再报成功。
#
# 代码归仓库、数据归数据目录：git pull 永远不会碰 data/。
# 数据目录写在 <code>/.llmcost-dir 里，run.command 会读它（环境变量优先）。

set -u

REPO="https://github.com/Pamphile0117/pocket-llmcost.git"
HERE="$(cd "$(dirname "$0")" && pwd)"

ROOT="${HOME}/Documents/AI项目"
CODE=""
DATA=""
MODE="install"
LAUNCH=1
RESTART=0

while [ $# -gt 0 ]; do
  case "$1" in
    --update)   MODE="update"; RESTART=1; shift ;;
    --root)     ROOT="$2"; shift 2 ;;
    --code)     CODE="$2"; shift 2 ;;
    --data)     DATA="$2"; shift 2 ;;
    --no-launch) LAUNCH=0; shift ;;
    --restart)  RESTART=1; shift ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "不认识的参数：$1（--help 看用法）"; exit 2 ;;
  esac
done

ROOT="${ROOT/#\~/$HOME}"
[ -n "${CODE}" ] && CODE="${CODE/#\~/$HOME}"
[ -n "${DATA}" ] && DATA="${DATA/#\~/$HOME}"
# 默认值放在解析参数之后算：--root 改了根目录，代码和数据要跟着走
[ -z "${CODE}" ] && CODE="${ROOT}/_插件/llmcost"
[ -z "${DATA}" ] && DATA="${ROOT}/13-算价"

PY="$(command -v python3)" || { echo "需要 python3"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "需要 git"; exit 1; }

say() { printf '%s\n' "$*"; }

# ---------------------------------------------------------------- 1. 拉代码
if [ -d "${CODE}/.git" ]; then
  say "· 更新代码：${CODE}"
  if ! git -C "${CODE}" pull --ff-only --quiet; then
    say "  ⚠️ git pull 失败（本地有改动或被分叉了）。先看一眼：git -C \"${CODE}\" status"
    exit 1
  fi
elif [ -d "${CODE}" ] && [ -f "${CODE}/llmcost.py" ]; then
  say "· ${CODE} 已经有一份代码但不是 git 仓库，跳过拉取（当作用户自备目录）"
else
  say "· 克隆到：${CODE}"
  mkdir -p "$(dirname "${CODE}")"
  git clone --quiet "${REPO}" "${CODE}" || { say "  ⚠️ clone 失败，检查网络或仓库地址"; exit 1; }
fi

VER="$("${PY}" "${CODE}/llmcost.py" --version 2>/dev/null || echo '0.0.0')"
say "· 版本：${VER}"

# ---------------------------------------------------------------- 2. 登记到中台
mkdir -p "${DATA}"
printf '%s\n' "${DATA}" > "${CODE}/.llmcost-dir"

"${PY}" - "${ROOT}" "${CODE}" "${DATA}" <<'PY'
import json, os, sys

root, code, data = sys.argv[1:4]
p = os.path.join(root, "_工作台", "plugins.json")
os.makedirs(os.path.dirname(p), exist_ok=True)

try:
    d = json.load(open(p, encoding="utf-8"))
    if not isinstance(d, dict):
        d = {"plugins": d}
except (OSError, ValueError):
    d = {"plugins": []}

rows = [r for r in (d.get("plugins") or []) if isinstance(r, dict)]
cmd = os.path.relpath(os.path.join(code, "run.command"), root)
entry = {
    "id": "llmcost",
    "name": "Token 价格追踪",
    "url": "http://127.0.0.1:8776/",
    "port": 8776,
    "cmd": cmd,
    "glyph": "llmcost",
    "note": "模型 API / 套餐 / 本地部署成本 · 从 GitHub 装",
    "svc_name": "Token 价格追踪",
    "group": "other",
}
old = next((r for r in rows if r.get("id") == "llmcost"), None)
if old is None:
    rows.append(entry)
    action = "已登记"
else:
    old.update(entry)
    action = "已更新登记"
d["plugins"] = rows
tmp = p + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
os.replace(tmp, p)
print("· %s：%s（cmd=%s）" % (action, p, cmd))
PY

# ---------------------------------------------------------------- 3. 拉起来
PORT=8776
if /usr/sbin/lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  if [ "${RESTART}" = "1" ]; then
    say "· 停掉旧进程（${PORT}），让新代码生效"
    OLD_PIDS="$(/usr/sbin/lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN -t 2>/dev/null)"
    if [ -n "${OLD_PIDS}" ]; then
      printf '%s\n' "${OLD_PIDS}" | xargs kill 2>/dev/null
    fi
    sleep 1
  else
    say "· ${PORT} 已经有人在跑：本次不启动。想换成本仓库这版，加 --restart"
    say ""
    say "完成。打开 http://127.0.0.1:${PORT}/"
    exit 0
  fi
fi

if [ "${LAUNCH}" = "1" ]; then
  say "· 启动服务…"
  CUNTU_NO_OPEN=1 LLMCOST_DIR="${DATA}" "${CODE}/run.command" >/dev/null 2>&1 &
  i=0
  while [ "${i}" -lt 40 ]; do
    if curl -s -m 2 "http://127.0.0.1:${PORT}/api/ping" >/dev/null 2>&1; then
      say "· 起来了（${PORT}）"
      break
    fi
    i=$((i + 1))
    sleep 0.25
  done
  if [ "${i}" -ge 40 ]; then
    say "  ⚠️ 20 秒还没通，看日志：~/Library/Logs/llmcost.log"
  fi
fi

say ""
say "完成。打开 http://127.0.0.1:${PORT}/"
say "中台里的一颗药丸会自动出现（不用重启口袋，刷新页面即可）。"
