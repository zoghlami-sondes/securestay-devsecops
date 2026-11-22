FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SECURESTAY_DATABASE=/app/data/lab.db

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 securestay \
    && useradd --uid 10001 --gid 10001 --no-create-home --no-log-init --shell /usr/sbin/nologin securestay \
    && install -d -m 0750 -o securestay -g securestay /app/data /app/logs

COPY app/ .

USER 10001:10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "from http.client import HTTPConnection; connection = HTTPConnection('127.0.0.1', 8080, timeout=3); connection.request('GET', '/'); raise SystemExit(connection.getresponse().status != 200)"]

CMD ["python", "app.py"]
