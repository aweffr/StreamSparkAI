# Stage 1: Builder stage for compiling mysqlclient
FROM python:3.12-slim AS builder

# Build argument to use Tsinghua mirror for apt
ARG USE_TSINGHUA_MIRROR=false

ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /build

# Copy mirror setup script
COPY docker/setup-mirrors.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/setup-mirrors.sh

# Install build dependencies
RUN /usr/local/bin/setup-mirrors.sh "$USE_TSINGHUA_MIRROR" && \
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
RUN pip install --no-cache-dir mysqlclient && \
    pip wheel mysqlclient -w /build/wheels/

# Find all needed mysqlclient libraries
RUN mkdir -p /build/lib && \
    cp -L $(find /usr/lib -name "libmysqlclient*.so*") /build/lib/ && \
    cp -L /usr/lib/x86_64-linux-gnu/libssl.so* /build/lib/ 2>/dev/null || true && \
    cp -L /usr/lib/x86_64-linux-gnu/libcrypto.so* /build/lib/ 2>/dev/null || true && \
    find /usr/local/lib/python3.12/site-packages -name "*.so" -o -name "*.so.*" | grep -i mysql | xargs -I {} cp {} /build/lib/

RUN echo "print /build/lib \n" && find /build/lib/

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

# Copy mirror setup script
COPY docker/setup-mirrors.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/setup-mirrors.sh

# Install minimal runtime dependencies
RUN /usr/local/bin/setup-mirrors.sh "$USE_TSINGHUA_MIRROR" && \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev \
    ca-certificates \
    default-libmysqlclient-dev \
    tzdata \
    gettext \
    vim-tiny \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy mysql shared libraries from builder
COPY --from=builder /build/lib/ /usr/lib/
# Copy mysqlclient wheel from builder
COPY --from=builder /build/wheels/ /wheels/

RUN ldconfig

# Install mysqlclient wheel first
RUN pip install --no-cache-dir /wheels/mysqlclient*.whl && \
    echo "mysqlclient wheel installed successfully"

# Copy mysqlclient Python package
COPY --from=builder /usr/local/lib/python3.12/site-packages/MySQLdb /usr/local/lib/python3.12/site-packages/MySQLdb
COPY --from=builder /usr/local/lib/python3.12/site-packages/mysqlclient-*.dist-info /usr/local/lib/python3.12/site-packages/

# Verify MySQLdb can be imported and _mysql module exists
RUN python -c "import MySQLdb; print('MySQLdb import successful'); import MySQLdb._mysql; print('MySQLdb._mysql is available')" || { echo 'MySQLdb verification failed'; exit 1; }

# Copy requirements and install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip list | grep mysqlclient && \
    echo "all dependencies installed"

# Copy the project files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "docker/entrypoint.py"]
