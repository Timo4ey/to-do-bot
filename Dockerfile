FROM python:3.12.10-slim

# Install ffmpeg in a single layer and clean up in the same step to reduce image size
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app

# Copy only requirements files first to leverage Docker cache
COPY pyproject.toml uv.lock /app/

# Install dependencies in a single layer
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir uv && \
    uv pip install --no-cache-dir -r pyproject.toml --system

# Copy application code after installing dependencies
COPY ./simple_bot .

# Use a non-root user for better security
RUN useradd -m appuser && \
    chown -R appuser:appuser /app
USER appuser

# Set environment variable to indicate Python is running in a container
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
