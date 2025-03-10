FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 先复制 requirements.txt 以利用 Docker 缓存
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 创建下载目录
RUN mkdir -p /app/download

# 复制应用代码
COPY . .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV DOWNLOAD_DIR=/app/download

# 设置卷挂载点
VOLUME ["/app/download"]

# 运行机器人
CMD ["python", "main.py"]
