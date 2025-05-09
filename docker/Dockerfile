FROM python:3.12-slim

# Build argument to use Tsinghua mirror for apt
ARG USE_TSINGHUA_MIRROR=false

ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app

# Install system dependencies
RUN if [ "$USE_TSINGHUA_MIRROR" = "true" ]; then \
        # 处理 sources.list 文件（如果存在）
        if [ -f /etc/apt/sources.list ]; then \
            sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
            sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
        fi && \
        # 处理 sources.list.d 目录中的文件
        if [ -d /etc/apt/sources.list.d ]; then \
            rm -f /etc/apt/sources.list.d/* && \
            echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list.d/debian.list && \
            echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.list && \
            echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.list && \
            echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list.d/debian.list; \
        fi; \
    fi && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    build-essential \
    binutils \
    pkg-config \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "docker/entrypoint.py"]
