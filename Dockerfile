FROM python:3.12-slim AS builder

COPY app/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SECURESTAY_DATABASE=/app/data/lab.db \
    PATH=/opt/venv/bin:${PATH}

WORKDIR /app

# Mettre à jour zlib1g et créer un utilisateur non-root
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 securestay \
    && useradd --uid 10001 --gid 10001 --no-create-home --no-log-init --shell /usr/sbin/nologin securestay \
    && install -d -m 0750 -o securestay -g securestay /app/data /app/logs

COPY --from=builder /opt/venv /opt/venv

# Copier le code de SecureStay
COPY app/ .

# Appliquer le principe du moindre privilège
USER 10001:10001

EXPOSE 8080

# Vérifier automatiquement que Flask répond
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "from http.client import HTTPConnection; connection = HTTPConnection('127.0.0.1', 8080, timeout=3); connection.request('GET', '/'); raise SystemExit(connection.getresponse().status != 200)"]

CMD ["python", "app.py"]
