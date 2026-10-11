# Build from the repository root; the SDK is installed from this checkout.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY clients/python/pyproject.toml clients/python/README.md clients/python/LICENSE /app/sdk/
COPY clients/python/src /app/sdk/src
COPY docker/mcp/pyproject.toml docker/mcp/thinkpixel_mcp.py /app/mcp/
RUN pip install /app/sdk /app/mcp && useradd --uid 10001 --create-home mcp
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["thinkpixel-sr-mcp"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
