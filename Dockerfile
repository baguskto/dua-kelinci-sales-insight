# syntax=docker/dockerfile:1.7
# Build stage: install hash-pinned dependencies into a virtualenv and precompile bytecode.
FROM python:3.12.13-slim-trixie AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements-prod.lock .
RUN python -m venv /venv \
 && /venv/bin/pip install --require-hashes --no-deps -r requirements-prod.lock
COPY src ./src
COPY app.py sales.csv ./
RUN /venv/bin/python -m compileall -q /venv src app.py

# Runtime stage: no compilers, no pip cache, non-root, works with a read-only root filesystem.
FROM python:3.12.13-slim-trixie AS runtime
LABEL org.opencontainers.image.title="dua-kelinci-sales-insight" \
      org.opencontainers.image.source="https://github.com/baguskto/dua-kelinci-sales-insight" \
      org.opencontainers.image.licenses="Proprietary"
# Apply Debian security updates at build time; rebuild weekly (CI) to pick up new fixes.
RUN apt-get update \
 && apt-get -y upgrade --no-install-recommends \
 && apt-get -y autoremove \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app \
 && mkdir -p /data && chown app:app /data
COPY --from=build /venv /venv
COPY --from=build --chown=root:root /build /app
WORKDIR /app
ENV PATH=/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/data \
    DATA_FILE=/app/sales.csv
USER 10001:10001
EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]
STOPSIGNAL SIGTERM
CMD ["python", "app.py"]
