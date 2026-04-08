# Use Python 3.12 slim as the base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/mcp_venv \
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

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Create the virtual environment
RUN uv venv /opt/mcp_venv

# Copy the dependency file to leverage Docker layer caching
COPY pyproject.toml /tmp/pyproject.toml

# Install dependencies from the toml file into the global venv
RUN uv pip install --python /opt/mcp_venv/bin/python -r /tmp/pyproject.toml

WORKDIR /app

# Run the server using the absolute path to the baked-in venv.
CMD ["/opt/mcp_venv/bin/python", "server.py"]
