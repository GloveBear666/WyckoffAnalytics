#!/usr/bin/env bash
# ============================================================
# WyckoffAnalytics - Mac mini 24x7 后端部署/更新脚本
# 用法:
#   首次部署:  bash scripts/macmini_deploy.sh
#   日常更新:  在任何设备 push 代码后, 在 Mac mini 上再次运行本脚本
# 前提: 已安装 Docker Desktop (或 colima+docker CLI) 与 git
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> [1/4] 拉取最新代码 (git pull)"
git pull --ff-only

echo "==> [2/4] 构建并启动 Docker 容器 (首次构建约 3-8 分钟)"
docker compose up -d --build

echo "==> [3/4] 等待服务就绪..."
for i in $(seq 1 45); do
  if curl -sf http://127.0.0.1:8088/api/status >/dev/null 2>&1; then
    IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "<本机IP>")
    echo ""
    echo "==> [4/4] ✅ 后端已就绪"
    echo "    本机:      http://127.0.0.1:8088"
    echo "    局域网:    http://${IP}:8088   (手机/平板/其他电脑同一WiFi直接访问)"
    echo "    公网:      打开 https://wyckoff-analytics.vercel.app, 顶部\"后端地址\"填云端隧道 (见 README 部署段)"
    echo ""
    echo "    日常维护:"
    echo "      docker compose logs -f      查看日志"
    echo "      docker compose restart      重启服务"
    echo "      bash scripts/macmini_deploy.sh   再次更新 (自动 pull + 重建)"
    exit 0
  fi
  sleep 2
done

echo "==> ❌ 服务未就绪, 查看日志: docker compose logs -f" >&2
exit 1
