FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git && \
    rm -rf /var/lib/apt/lists/*

# Python deps for EMATA research (no Sigil production deps)
RUN pip install --no-cache-dir \
    numpy>=1.24 \
    scipy>=1.10 \
    pytest>=7.0 \
    pytest-asyncio>=0.21 \
    pyyaml>=6.0 \
    rich>=13.0 \
    dataclasses-json>=0.6

# Copy only the research code (mounted at runtime for dev)
COPY . /app/

# No secrets, no API keys, no production data
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]
