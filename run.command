#!/bin/bash
# 双击 = 打开「Token 价格追踪」（大模型 API / 套餐 / 本地部署 三维度成本追踪）
#
#   窗口自己关掉，服务留在后台；浏览器会弹出来。
#   想停掉服务：pkill -f "llmcost.py --serve"
#   出问题看日志：~/Library/Logs/llmcost.log
#
# 数据目录（按顺序找）：
#   1. $LLMCOST_DIR
#   2. 同目录的 .llmcost-dir（install.sh 装的时候写进去的那行路径）
#   3. ~/Documents/AI项目/13-算价（口袋的数据根下那个目录，存在就用）
#   4. ~/.pocket-llmcost（都没有时新建）
#
# 中台点药丸进来时会带 CUNTU_NO_OPEN=1：那会儿中台自己开标签页，别再弹一个。
# 手工双击则照常弹浏览器。

set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
LOGDIR="${HOME}/Library/Logs"
mkdir -p "${LOGDIR}" 2>/dev/null || LOGDIR="/tmp"
LOG="${LOGDIR}/llmcost.log"

note() {
  /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1
}

PY="$(command -v python3)"
if [ -z "${PY}" ]; then
  echo "找不到 python3"
  note "Token 价格追踪起不来" "找不到 python3"
  exit 1
fi

if [ -z "${LLMCOST_DIR:-}" ]; then
  if [ -f "${HERE}/.llmcost-dir" ]; then
    LLMCOST_DIR="$(head -n 1 "${HERE}/.llmcost-dir")"
  elif [ -d "${HOME}/Documents/AI项目/13-算价" ]; then
    LLMCOST_DIR="${HOME}/Documents/AI项目/13-算价"
  else
    LLMCOST_DIR="${HOME}/.pocket-llmcost"
  fi
fi
export LLMCOST_DIR

PORTA="${LLMCOST_PORT:-8776}"

# 已经在跑就不再起第二个（会抢端口）：直接当「打开」用
if /usr/sbin/lsof -nP -iTCP:"${PORTA}" -sTCP:LISTEN >/dev/null 2>&1; then
  if [ "${CUNTU_NO_OPEN:-}" != "1" ]; then
    /usr/bin/open "http://127.0.0.1:${PORTA}/"
  fi
  exit 0
fi

OPEN=""
if [ "${CUNTU_NO_OPEN:-}" = "1" ]; then
  OPEN="--no-open"
fi

echo "=== $(date '+%F %T') 打开 Token 价格追踪 （数据：${LLMCOST_DIR}）===" >>"${LOG}"

# 干净环境起：编辑器/沙箱 fork 出来的进程会带 PYTHONPATH shim，子进程一结束
# 就抛 _BrokerProtocolError。这里把环境收干净，路径也显式钉死。
# 前台跑：中台是用 start_new_session 起的，脚本活着 = 服务活着；
# 双击时窗口留着（关窗即停，跟别的 .command 一个规矩）。
exec env -i HOME="${HOME}" PATH=/usr/bin:/bin:/usr/sbin:/sbin \
    LLMCOST_DIR="${LLMCOST_DIR}" \
    "${PY}" "${HERE}/llmcost.py" --serve --port "${PORTA}" ${OPEN} >>"${LOG}" 2>&1
