# Use Python 3.12 slim as the base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    # Point Python to the global venv instead of the local .venv
    PATH="/opt/mcp_venv/bin:/root/.local/bin:${PATH}"

# Install system dependencies and Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy project files to a temporary location to install dependencies
COPY pyproject.toml . 

# Install dependencies into a global location /opt/mcp_venv 
# instead of the local /app/.venv
RUN uv venv /opt/mcp_venv && \
    uv pip install --python /opt/mcp_venv/bin/python -r pyproject.toml

# Expose the port used by the aggregator server
EXPOSE 7000

# Use the global venv to run the server
CMD ["/opt/mcp_venv/bin/python", "server.py"]
