FROM python:3.11-slim
WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3.11

# Copy application code
COPY . .

# Development: uvicorn with hot-reload
CMD ["uv", "run", "uvicorn", "core.asgi:application", "--host", "0.0.0.0", "--port", "8003", "--reload"]

