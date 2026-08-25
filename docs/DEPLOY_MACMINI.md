# Mac mini 24×7 后端部署指南

把 WyckoffAnalytics 后端跑在家里 Mac mini（或其他 Linux 服务器）的 Docker 里，电脑可以关机，服务 24 小时在线。

## 架构回顾

```
[任意设备浏览器] → https://wyckoff-analytics.vercel.app (前端, GitHub 自动部署)
                        │ 顶部"后端地址"填:
                        ▼
[Mac mini Docker] → http://<Mac mini IP>:8088  (后端: 回测/AI训练/答题批改)
   └─ 持久卷: ./data (行情缓存) · ./research (答题记录/训练历史/学习笔记)
```

## 一、首次部署（约 15 分钟）

### 1. 安装前置软件（仅一次）

- **Docker Desktop for Mac**（Apple Silicon 版）：https://www.docker.com/products/docker-desktop/
  安装后打开一次，等右下角鲸鱼图标变绿（引擎启动）。
  ⚙️ 设置 → General → 勾选 **"Start Docker Desktop when you sign in"**（登录自启，配合 `restart: unless-stopped` 实现开机自动服务）。
- **git**：macOS 自带（`git --version` 可验证）。

### 2. 克隆代码（首次）

```bash
cd ~/workspace                       # 任意目录
git clone https://github.com/GloveBear666/WyckoffAnalytics.git
cd WyckoffAnalytics
```

### 3. 一键部署

```bash
bash scripts/macmini_deploy.sh
```

脚本自动完成：`git pull` → `docker compose up -d --build` → 健康检查 → 打印访问地址。
首次构建需下载基础镜像并安装依赖（约 3-8 分钟），之后增量构建很快。

### 4. 验证

- 本机浏览器打开 `http://127.0.0.1:8088` —— 看到完整终端即成功
- 手机连同一 WiFi 打开 `http://<Mac mini IP>:8088`（Mac mini 的 IP 可用 `ipconfig getifaddr en0` 查看）

### 5.（可选）预抓行情数据

```bash
docker compose run --rm wyckoff-web python core/data.py --profile crypto --symbol BTC/USDT --tf 1h 4h 1d
docker compose run --rm wyckoff-web python core/data.py --profile equity --symbol SPY AAPL
```

数据写入 `./data` 持久卷，之后回测/答题无需再等待抓取。

## 二、公网访问（可选，让任意网络环境可用）

前端页面（https://wyckoff-analytics.vercel.app）打开后，在顶部"后端地址"填入下面任一隧道地址：

```bash
# 方式A: cloudflared 临时隧道 (免费, 无需注册, URL 每次运行会变)
cloudflared tunnel --url http://127.0.0.1:8088

# 方式B: Tailscale (免费, 稳定 HTTPS 域名, 推荐)
# 在 Mac mini 和你的手机/电脑上都装 Tailscale 并登录同一账号:
tailscale serve --bg 8088
# → 得到 https://<机器名>.<tailnet>.ts.net 永久地址
```

> ⚠️ 网页是 https 时后端也必须 https（用上述隧道即可）；局域网直连 `http://IP:8088` 不受影响。
> ⚠️ macOS 防火墙一般默认放行 Docker 端口；若局域网访问不通，检查 系统设置 → 网络 → 防火墙。

## 三、日常更新（每次改完代码后）

代码在任何设备 push 到 GitHub 后，在 Mac mini 上执行：

```bash
cd ~/workspace/WyckoffAnalytics
bash scripts/macmini_deploy.sh     # 自动 pull + 重建容器, 数据卷不丢失
```

前端无需任何操作（GitHub Actions 自动部署 Vercel）。

## 四、常见维护命令

| 命令 | 作用 |
|---|---|
| `docker compose logs -f` | 实时查看后端日志 |
| `docker compose restart` | 重启容器 |
| `docker compose down && docker compose up -d` | 完全重建（保留数据卷） |
| `docker system prune -a` | 清理旧镜像（谨慎，会触发下次完整构建） |
| `docker compose exec wyckoff-web python scripts/run_pipeline.py --symbol BTC/USDT --profile crypto --tf 4h --htf-tf 1d --trials 40` | 在容器内跑完整流水线（训练/验证/学习笔记） |

## 五、数据与备份

- **答题记录/标注集/训练历史/学习笔记**：全部在仓库的 `research/` 目录（宿主机磁盘，非容器内），随 git 同步/备份。
- **行情缓存**：`data/` 目录，可随时重新抓取，也可手动备份。
- 建议每周 `git add research && git commit -m "sync research" && git push`，让答题标注集在任何设备可见（详见 `docs/GITHUB_MULTIDEVICE.md`）。
