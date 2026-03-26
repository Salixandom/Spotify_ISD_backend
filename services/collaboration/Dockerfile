FROM python:3.11-slim
WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Copy application code
COPY . .

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Development: uvicorn with hot-reload
CMD ["uv", "run", "uvicorn", "core.asgi:application", \
     "--host", "0.0.0.0", "--port", "8003", "--reload"]
