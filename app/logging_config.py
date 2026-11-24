import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from flask import g, request


LOG_DIRECTORY = os.path.join(os.path.dirname(__file__), "logs")
METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"}
security_counts = Counter()
counter_lock = Lock()


def setup_loggers():
    os.makedirs(LOG_DIRECTORY, exist_ok=True)

    # Werkzeug's access log includes the original request target and query string.
    logging.getLogger("werkzeug").disabled = True
    loggers = []
    for name in ("access", "auth", "app"):
        logger = logging.getLogger(f"securestay.{name}")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if not logger.handlers:
            handler = logging.FileHandler(os.path.join(LOG_DIRECTORY, f"{name}.log"), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
        loggers.append(logger)
    return tuple(loggers)


def start_request():
    g.correlation_id = uuid4().hex


def correlation_id():
    if "correlation_id" not in g:
        start_request()
    return g.correlation_id


def log_event(logger, event, *, status=None, count=False):
    """Emit only route metadata and application-defined event codes."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id(),
        "event": event,
        "method": request.method if request.method in METHODS else "OTHER",
        "route": request.url_rule.rule if request.url_rule is not None else "unmatched",
    }
    if status is not None:
        record["status"] = status

    if count:
        with counter_lock:
            security_counts[event] += 1
            record["event_count"] = security_counts[event]
            logger.info(json.dumps(record))
    else:
        logger.info(json.dumps(record))
