"""Exercise ordinary test-user traffic through an in-Pod passive ZAP proxy."""

import http.client
import ipaddress
import json
import os
import secrets
import subprocess
import sys
import time
from http.cookies import SimpleCookie
from urllib.parse import urlencode


PORT = 8090
CHECKS = ("session_profile", "session_bookings", "idor_denied", "non_finite_price_rejected")


def request(path, method="GET", body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", PORT, timeout=5)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        return response.status, response.getheaders(), response.read()
    finally:
        connection.close()


def api(path, key, **query):
    status, _, data = request(path + "?" + urlencode(query), headers={"X-ZAP-API-Key": key})
    if status != 200:
        raise RuntimeError("Passive scanner API is unavailable")
    return json.loads(data)


def wait_for_zap(key):
    for _ in range(45):
        try:
            if api("/JSON/core/view/version/", key).get("version"):
                return
        except (OSError, RuntimeError, ValueError):
            pass
        time.sleep(2)
    raise TimeoutError("ZAP startup")


def checks(target):
    if request(target + "/")[0] != 200:
        raise RuntimeError("Test target is unavailable")
    status, headers, _ = request(
        target + "/login", "POST",
        urlencode({"username": "alice", "password": os.environ["DAST_PASSWORD"]}),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    cookies = SimpleCookie()
    for header, value in headers:
        if header.lower() == "set-cookie":
            cookies.load(value)
    if status != 302 or "session" not in cookies:
        return dict.fromkeys(CHECKS, False)
    headers = {"Cookie": "session=" + cookies["session"].coded_value}
    profile = request(target + "/profile", headers=headers)
    return {
        "session_profile": profile[0] == 200 and b"alice" in profile[2],
        "session_bookings": request(target + "/bookings", headers=headers)[0] == 200,
        "idor_denied": request(target + "/profile/2", headers=headers)[0] == 403,
        "non_finite_price_rejected": request(target + "/search?min_price=NaN", headers=headers)[0] == 400,
    }


def collect_alerts(key, target):
    for _ in range(60):
        if int(api("/JSON/pscan/view/recordsToScan/", key)["recordsToScan"]) == 0:
            break
        time.sleep(2)
    else:
        raise TimeoutError("Passive scan completion")

    alerts = []
    for offset in range(0, 10000, 100):
        page = api("/JSON/alert/view/alerts/", key, baseurl=target, start=offset, count=100)["alerts"]
        for item in page:
            rule = int(item["pluginId"])
            risk = {"Informational": 0, "Low": 1, "Medium": 2, "High": 3}[item["risk"]]
            if rule <= 0 or risk not in (0, 1, 2, 3):
                raise ValueError("Invalid ZAP metadata")
            alerts.append({"rule": rule, "risk": risk})
        if len(page) < 100:
            return alerts
    raise RuntimeError("Passive alert pagination limit exceeded")


def main():
    ip = ipaddress.IPv4Address(os.environ["TARGET_IP"])
    target = f"http://{ip}:8080"
    key = secrets.token_urlsafe(32)
    os.mkdir("/tmp/zap-session", 0o700)
    process = subprocess.Popen(
        ["/zap/zap.sh", "-daemon", "-host", "127.0.0.1", "-port", str(PORT),
         "-dir", "/tmp/zap-session", "-config", f"api.key={key}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_zap(key)
        results = checks(target)
        alerts = collect_alerts(key, target)
        print(json.dumps({"checks": results, "alerts": alerts}), flush=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Passive DAST failed before report generation.", file=sys.stderr)
        raise SystemExit(1)
