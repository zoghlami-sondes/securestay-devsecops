"""Verify the price rejection telemetry on a local SecureStay test instance."""

import argparse
from http.client import HTTPConnection
import json
from pathlib import Path
import re


def find_event(path, correlation_id, event):
    with path.open(encoding="utf-8") as records:
        for line in records:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if (isinstance(record, dict) and record.get("correlation_id") == correlation_id
                    and record.get("event") == event and record.get("route") == "/search"
                    and record.get("status") == 400):
                return record
    raise SystemExit(f"Expected {event} was not found for this request")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()

    connection = HTTPConnection("127.0.0.1", args.port, timeout=5)
    try:
        connection.request("GET", "/search?min_price=NaN")
        response = connection.getresponse()
        status = response.status
        correlation_id = response.getheader("X-Correlation-ID") or ""
    finally:
        connection.close()
    if status != 400 or not re.fullmatch(r"[0-9a-f]{32}", correlation_id):
        raise SystemExit("Expected HTTP 400 and a server-generated correlation ID")

    access = find_event(args.log_dir / "access.log", correlation_id, "HTTP_REQUEST")
    event = find_event(args.log_dir / "app.log", correlation_id, "PRICE_NAN_REJECTED")
    count = event.get("event_count")
    if type(count) is not int or count < 1:
        raise SystemExit("Expected a positive security event counter")
    print(json.dumps({
        "correlation_id": correlation_id,
        "http_status": status,
        "route": event["route"],
        "timestamp": event["timestamp"],
        "access_event": access["event"],
        "security_event": event["event"],
        "event_count": count,
    }))


if __name__ == "__main__":
    main()
