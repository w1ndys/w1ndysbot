FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 接入国内镜像源加速依赖安装：
# - apt 使用清华大学 TUNA 的 Debian / debian-security 镜像，bookworm-slim 采用
#   DEB822 格式的 /etc/apt/sources.list.d/debian.sources，通过 sed 直接替换默认 URI。
# - uv/pip 通过 UV_DEFAULT_INDEX 和 PIP_INDEX_URL 指向清华 PyPI 镜像。
RUN sed -i \
        -e 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' \
        -e 's|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list.d/debian.sources

# 明确声明东八区（Asia/Shanghai）时区，避免基础镜像默认 UTC
# 导致容器内 datetime.now() 与日志时间与北京时间不一致。
# slim 镜像默认不含 tzdata，需要显式安装。
#
# OpenCV（opencv-python）在 import 时会 dlopen libGL.so.1 / libglib-2.0.so.0，
# 否则 GroupQRDetector 启动会报：
#   ImportError: libGL.so.1: cannot open shared object file: No such file or directory
# slim 基础镜像不含这两个库，需在此安装 libgl1 + libglib2.0-0。
#
# DeerSign 模块用 PIL 画签到日历/排行榜时需要中文字体，否则会渲染成方框/乱码。
# slim 镜像默认不含 CJK 字体，安装 fonts-wqy-microhei（约 10MB，代码首选字体）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata \
        libgl1 \
        libglib2.0-0 \
        fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# UV_DEFAULT_INDEX / PIP_INDEX_URL 让 uv sync 直接走清华 PyPI 镜像。
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    TZ=Asia/Shanghai

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

CMD ["uv", "run", "python", "app/main.py"]
