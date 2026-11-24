#!/usr/bin/env bash
# 一条命令发布：重建子页 → 自检 → 提交 → 推 GitHub（走 REST API）
#
#   ./tools/publish.sh "改了首页导航"
#   ./tools/publish.sh "刷新价格快照" --refresh     # 顺带重算 data.json（要联网）
#   ./tools/publish.sh --dry                       # 只看到底会传什么
#
# 约定：只有 llmcost_ui.html 是源，llmcost/*.html 是生成物，别手改。
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
MSG=""
REFRESH=0
DRY=0
FORCE=""

for a in "$@"; do
  case "${a}" in
    --refresh) REFRESH=1 ;;
    --dry|--dry-run) DRY=1 ;;
    # 远端比本地新时，publish.py 默认会停下；确认以本地为准才显式打开
    --force-remote) FORCE="--force-remote" ;;
    *) MSG="${a}" ;;
  esac
done
[ -n "${MSG}" ] || MSG="chore: 更新站点内容"

echo "▸ 仓库 ${ROOT}"

# 1) 手改生成物的护栏：重建会把它们冲掉，先提醒
if git rev-parse --git-dir >/dev/null 2>&1; then
  DIRTY_GEN="$(git diff --name-only -- 'llmcost/*.html' 'llmcost/assets/*' || true)"
  SRC_DIRTY="$(git diff --name-only -- 'llmcost_ui.html' || true)"
  BUILDER_DIRTY="$(git diff --name-only -- 'tools/build_pages.py' 'tools/research.py' || true)"
  if [ -n "${DIRTY_GEN}" ] && [ -z "${SRC_DIRTY}" ] && [ -z "${BUILDER_DIRTY}" ]; then
    echo "⚠ 你改的是生成物，不是源："
    echo "${DIRTY_GEN}" | sed 's/^/    /'
    echo "  下一行就会用 llmcost_ui.html 重建，你的改动会丢。"
    echo "  要改卡片/页面结构，请改 llmcost_ui.html；只是不想丢的话，现在 Ctrl-C 出去备份。"
    read -r -t 25 -p "  继续？（25 秒无输入视为中止）(y/N) " ans || ans=""
    case "${ans}" in y|Y) ;; *) echo "已中止。"; exit 1 ;; esac
  fi
fi

# 2) 重建子页（幂等，每次从 llmcost_ui.html 重新生成）
echo "▸ 重建 llmcost 子页"
python3 tools/build_pages.py

# 2b) 打插件包。必须每次重建：包里的代码就是这个 commit 的代码，
#     忘了打会出现「站点说 1.1.0、下下来的还是 1.0.0」，更新提示点了也不生效。
echo "▸ 打插件包（.moshanplug）"
python3 tools/make_plugin_pack.py

# 3) 可选：重算价格快照（Actions 每天也会跑，本地跑要能连外网）
if [ "${REFRESH}" = "1" ]; then
  echo "▸ 重算数据快照"
  python3 tools/make_snapshot.py
fi

# 4) 断链自检
echo "▸ 自检引用"
python3 tools/check_links.py

# 5) 提交（试运行不动版本库）
if [ "${DRY}" = "1" ]; then
  echo "▸ 试运行：跳过本地提交"
elif git rev-parse --git-dir >/dev/null 2>&1; then
  git add -A
  if git diff --cached --quiet; then
    echo "▸ 没有本地改动，跳过提交"
  else
    git commit -q -m "${MSG}"
    echo "▸ 已提交 $(git log --oneline -1)"
  fi
fi

# 6) 推送
if [ "${DRY}" = "1" ]; then
  echo "▸ 试运行，不推送"
  python3 tools/publish.py -m "${MSG}" ${FORCE} --dry-run
else
  echo "▸ 推送"
  python3 tools/publish.py -m "${MSG}" ${FORCE}
fi
