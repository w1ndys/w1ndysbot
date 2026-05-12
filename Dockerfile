FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 明确声明东八区（Asia/Shanghai）时区，避免基础镜像默认 UTC
# 导致容器内 datetime.now() 与日志时间与北京时间不一致。
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TZ=Asia/Shanghai

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app

CMD ["uv", "run", "python", "app/main.py"]
