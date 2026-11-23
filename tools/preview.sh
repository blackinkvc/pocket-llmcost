#!/usr/bin/env bash
# 本地预览：起静态服务并打开浏览器
#
#   ./tools/preview.sh          # 起在 8099 并打开首页
#   ./tools/preview.sh llmcost  # 直接开价格页
#   ./tools/preview.sh --stop   # 停掉
#
# 顺带探一下本机 pocket 服务（8776）：开着的话价格页会自动打 LIVE 角标、读实时数据。
set -euo pipefail

cd "$(dirname "$0")/.."
PORT=8099
PIDFILE="/tmp/pocket-preview-${PORT}.pid"
PATH_ARG="${1:-index.html}"

stop_server() {
  if [ -f "${PIDFILE}" ]; then
    OLD="$(cat "${PIDFILE}")"
    if kill -0 "${OLD}" 2>/dev/null; then
      kill "${OLD}" 2>/dev/null || true
      echo "已停掉预览服务（pid ${OLD}）"
    fi
    rm -f "${PIDFILE}"
  else
    P="$(lsof -ti tcp:${PORT} 2>/dev/null || true)"
    [ -n "${P}" ] && kill "${P}" 2>/dev/null && echo "已停掉占用 ${PORT} 的进程 ${P}" || echo "没有在跑"
  fi
}

if [ "${PATH_ARG}" = "--stop" ]; then
  stop_server
  exit 0
fi

# 端口被旧实例占着就重开，免得看到的是上一次的缓存页面
if lsof -ti tcp:${PORT} >/dev/null 2>&1; then
  stop_server
fi

nohup python3 -m http.server "${PORT}" --bind 127.0.0.1 >/tmp/pocket-preview.log 2>&1 &
echo $! > "${PIDFILE}"

for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 0.4
  curl -fs -o /dev/null "http://127.0.0.1:${PORT}/index.html" && break
done

URL="http://127.0.0.1:${PORT}/${PATH_ARG}"
if curl -fs -o /dev/null --max-time 1 "http://127.0.0.1:8776/api/ping" 2>/dev/null; then
  echo "本机 pocket 服务在线（8776）—— 价格页会显示 LIVE 实时数据"
else
  echo "本机 pocket 服务未启动 —— 价格页读仓库里的快照（正常，线上也是这个行为）"
fi
echo "▸ ${URL}"
echo "  停服务：./tools/preview.sh --stop"
command -v open >/dev/null && open "${URL}" || true
