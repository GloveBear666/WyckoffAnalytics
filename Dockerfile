# WyckoffAnalytics 后端镜像 (Web 终端)
# 构建: docker build -t wyckoff-web .
# 运行: docker compose up -d --build  (推荐, 含持久卷)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    HOST=0.0.0.0

WORKDIR /app

# 依赖缓存层 (代码变更不触发重新安装)
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# 应用代码
COPY . .

EXPOSE 8088

# 健康检查: /api/status
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/api/status', timeout=4)" || exit 1

CMD ["python", "-X", "utf8", "web/app.py", "8088"]
