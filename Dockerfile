FROM registry.docker.ir/library/python:3.12.8-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_HTTP_TIMEOUT=120
ENV UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

RUN pip install --no-cache-dir --timeout 120 --retries 10 uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8501

CMD [".venv/bin/streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true"]
