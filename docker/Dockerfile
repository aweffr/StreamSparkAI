# Stage 1: Builder stage for compiling mysqlclient
FROM python:3.12-slim AS builder

# Build argument to use Tsinghua mirror for apt
ARG USE_TSINGHUA_MIRROR=false

ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /build

# Install build dependencies
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

# Copy requirements and install mysqlclient only
COPY requirements.txt .
RUN pip install --no-cache-dir mysqlclient

# Find all needed mysqlclient libraries
RUN mkdir -p /build/lib && \
    cp -L $(find /usr/lib -name "libmysqlclient*.so*") /build/lib/ && \
    cp -L /usr/lib/x86_64-linux-gnu/libssl.so* /build/lib/ 2>/dev/null || true && \
    cp -L /usr/lib/x86_64-linux-gnu/libcrypto.so* /build/lib/ 2>/dev/null || true && \
    find /usr/local/lib/python3.12/site-packages -name "*.so" -o -name "*.so.*" | grep -i mysql | xargs -I {} cp {} /build/lib/

# Stage 2: Final image
FROM python:3.12-slim

ARG USE_TSINGHUA_MIRROR=false
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple PIP_TRUSTED_HOST=mirrors.aliyun.com

# Set timezone and locale
ENV TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    LANGUAGE=C.UTF-8

WORKDIR /app

# Install minimal runtime dependencies
RUN if [ "$USE_TSINGHUA_MIRROR" = "true" ]; then \
        # 处理 sources.list 文件（如果存在）
        if [ -f /etc/apt/sources.list ]; then \
            sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
            sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
        fi; \
    fi && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy mysql shared libraries from builder
COPY --from=builder /build/lib/ /usr/lib/
RUN ldconfig && echo "\ncheck /usr/lib... \n" && find /usr/lib

# Copy mysqlclient Python package
COPY --from=builder /usr/local/lib/python3.12/site-packages/MySQLdb /usr/local/lib/python3.12/site-packages/MySQLdb
COPY --from=builder /usr/local/lib/python3.12/site-packages/mysqlclient-*.dist-info /usr/local/lib/python3.12/site-packages/

# Verify MySQLdb can be imported and _mysql module exists
RUN python -c "import MySQLdb; print('MySQLdb import successful'); import MySQLdb._mysql; print('MySQLdb._mysql is available')" || { echo 'MySQLdb verification failed'; exit 1; }

# Copy requirements and install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip list | grep mysqlclient && \
    echo "mysqlclient is available"

# Copy the project files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "docker/entrypoint.py"]
