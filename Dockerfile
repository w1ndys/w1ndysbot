FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 明确声明东八区（Asia/Shanghai）时区，避免基础镜像默认 UTC
# 导致容器内 datetime.now() 与日志时间与北京时间不一致。
# slim 镜像默认不含 tzdata，需要显式安装。
#
# OpenCV（opencv-python）在 import 时会 dlopen libGL.so.1 / libglib-2.0.so.0，
# 否则 GroupQRDetector 启动会报：
#   ImportError: libGL.so.1: cannot open shared object file: No such file or directory
# slim 基础镜像不含这两个库，需在此安装 libgl1 + libglib2.0-0。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TZ=Asia/Shanghai

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

CMD ["uv", "run", "python", "app/main.py"]
