# 使用官方 Python 轻量级镜像
FROM python:3.12-slim

# 设置维护者信息
LABEL maintainer="Qtrading Bot"

# 设置环境变量
# 防止 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1
# 确保日志即时输出到控制台
ENV PYTHONUNBUFFERED=1
# 设置 PYTHONPATH 以便直接运行 src 目录下的代码
ENV PYTHONPATH=/app
# 设置默认时区为上海 (CST)
ENV TZ=Asia/Shanghai

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (主要用于时区设置)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要的目录
RUN mkdir -p output temp_download

# 默认启动命令 (启动实盘机器人)
CMD ["python", "src/live_bot.py"]
