# GitHub 多设备协作与同步指南

> 目标：在 **Windows 工作机**、**Mac mini 服务器**、**Mac 笔记本** 等多台设备上共同编辑同一项目，代码与数据通过 GitHub 保持同步。

## 0. 角色划分（先想清楚，避免踩坑）

| 设备 | 角色 | 说明 |
|---|---|---|
| Windows 工作机（当前） | 开发/主编辑 | 随意改代码、跑本地测试 |
| Mac mini（家里） | **唯一 24×7 后端** | 只运行 `docker compose` 服务，代码通过 `git pull` 更新 |
| Mac 笔记本/其他 | 开发/查看 | 改代码 push，或浏览器访问 Vercel 页面答题 |
| Vercel（云端） | 前端托管 | 每次 push 自动部署，无需人工操作 |

> ⚠️ **只让一台机器跑后端**。答题记录/训练日志写在运行后端的机器上，多台同时跑会互相覆盖。

## 1. Git 基础（每台设备只需配置一次）

```bash
# 克隆（新设备）
git clone https://github.com/GloveBear666/WyckoffAnalytics.git
cd WyckoffAnalytics

# 配置身份（提交时署名）
git config user.name "你的名字"
git config user.email "你的邮箱"
```

> 不习惯命令行的设备可用 **GitHub Desktop**（https://desktop.github.com）或 VS Code 内置源代码管理面板，功能等价。

## 2. 标准协作循环

```
[设备A] 改代码 → git add -A → git commit -m "说明" → git push
[Mac mini] 更新后端 → bash scripts/macmini_deploy.sh   (自动 git pull + 重建容器)
[任意设备] 打开 https://wyckoff-analytics.vercel.app   (前端已自动更新)
```

### 每次开工前（避免冲突）

```bash
git pull --ff-only      # 拉取别人/别的设备的改动
```

### 常用命令速查（Windows PowerShell / macOS 通用）

| 操作 | 命令 |
|---|---|
| 查看状态 | `git status` |
| 查看改动 | `git diff` |
| 提交全部改动 | `git add -A && git commit -m "说明"` |
| 推送 | `git push` |
| 拉取 | `git pull --ff-only` |
| 放弃某文件本地改动 | `git checkout -- <文件>` |
| 查看历史 | `git log --oneline -10` |

## 3. 数据同步（答题记录 / 训练历史）

后端产生的数据都在 `research/` 目录，随 git 同步：

```bash
# 在 Mac mini（运行后端的机器）上定期执行：
cd ~/workspace/WyckoffAnalytics
git add research
git commit -m "sync: 答题记录与训练数据"
git push
```

- 其他设备 `git pull` 即可看到最新答题记录/标注集/学习笔记。
- 答题期间产生的 `research/quiz/records.jsonl` 会自动更新，导出标注集在 `research/quiz/labels/`。
- `data/`（行情缓存）**不**进 git（.gitignore），各设备按需自行抓取。

## 4. 分支工作流（改动较大时）

```bash
git checkout -b feature-quiz-v2      # 新功能分支
# ... 修改代码 ...
git add -A && git commit -m "..."    # 多次提交
git push -u origin feature-quiz-v2   # 推分支
# 确认稳定后合入主分支:
git checkout main && git pull
git merge feature-quiz-v2
git push
git branch -d feature-quiz-v2        # 删除本地分支
```

> 小改动直接在主分支提交即可；大改动建议走分支，避免打断 Mac mini 正在运行的服务（合并后需在 Mac mini 重新 deploy）。

## 5. 冲突处理（最简单版）

`git pull` 报冲突时，多半是 `research/` 或 README 被两边同时改：

```bash
# 1) 先提交本地的改动, 再拉取合并
git add -A && git commit -m "本地改动"
git pull          # 自动合并, 冲突文件会标出 <<<<<<< ======= >>>>>>>
# 2) 用编辑器打开冲突文件, 保留想要的内容, 删掉标记行
# 3) 完成后:
git add -A && git commit -m "解决冲突" && git push
```

> 提示：答题记录文件 `records.jsonl` 是"服务器产物"，建议**只在 Mac mini 上提交它**，其他设备只读；若两台开发机都改了它，冲突时以 Mac mini（后端）版本为准。
> 更省心的做法：把 `research/quiz/records.jsonl` 从版本控制中排除（加入 .gitignore），只通过导出标注集的方式同步数据 —— 需要的话告诉我，我帮你改。

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| push 被拒（non-fast-forward） | 先 `git pull` 再 push |
| 忘了在 Mac mini 更新 | 运行 `bash scripts/macmini_deploy.sh` |
| 浏览器打开 Vercel 提示无法连接后端 | 检查 Mac mini 后端是否在跑 + "后端地址"是否填对（https 页面必须配 https 隧道） |
| 想在手机上答题 | 浏览器打开 Vercel 地址 → 填后端地址（局域网 IP 或隧道）→ 直接答 |
