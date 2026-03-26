FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev
COPY . .
CMD ["uv", "run", "uvicorn", "core.asgi:application", \
     "--host", "0.0.0.0", "--port", "8002", "--reload"]
