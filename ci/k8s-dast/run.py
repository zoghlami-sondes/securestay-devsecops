"""Run isolated SecureStay test Jobs and retain only sanitized DAST results."""

import html
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time


NAMESPACE = "securestay-dast"
TARGET_IMAGE = r"docker\.io/library/securestay@sha256:[0-9a-f]{64}"
ZAP_IMAGE = r"docker\.io/zaproxy/zap-stable@sha256:[0-9a-f]{64}"
CHECKS = {"session_profile", "session_bookings", "idor_denied", "non_finite_price_rejected"}

PROBE = """
import http.client
import os
import sys

connection = http.client.HTTPConnection(os.environ["TARGET_IP"], 8080, timeout=5)
expect_timeout = os.environ["EXPECT_TIMEOUT"] == "true"
try:
    connection.request("GET", "/")
    status = connection.getresponse().status
except TimeoutError:
    sys.exit(0 if expect_timeout else 1)
finally:
    connection.close()
sys.exit(0 if not expect_timeout and status == 200 else 1)
"""


def kubectl(*args, stdin=None):
    result = subprocess.run(
        ["kubectl", "-n", NAMESPACE, "--request-timeout=15s", *args],
        input=stdin, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise RuntimeError(f"Kubernetes {args[0]} failed")
    return result.stdout


def get(kind, name):
    return json.loads(kubectl("get", kind, name, "-o", "json"))


def patch(value):
    return json.loads(kubectl("patch", "deployment", "securestay", "--type", "strategic",
                              "-p", json.dumps(value), "-o", "json"))


def wait_for_deployment(generation):
    for _ in range(90):
        status = get("deployment", "securestay").get("status", {})
        if (status.get("observedGeneration", 0) >= generation
                and status.get("updatedReplicas") == status.get("availableReplicas") == 1):
            return
        time.sleep(2)
    raise TimeoutError("Isolated Deployment did not become ready")


def verify_runtime(image, config_digest, token):
    pods = json.loads(kubectl("get", "pods", "-l", "app.kubernetes.io/name=securestay-dast",
                              "-o", "json"))["items"]
    candidates = [
        pod for pod in pods
        if pod["metadata"].get("annotations", {}).get("securestay.io/test-run") == token
        and not pod["metadata"].get("deletionTimestamp")
    ]
    if len(candidates) != 1:
        raise RuntimeError("Expected one Pod for the approved test rollout")
    pod = candidates[0]
    if pod["spec"]["nodeName"] != "desktop-control-plane":
        raise RuntimeError("Unexpected node for locally imported image")

    runtime_ids = {}
    allowed = {image.split("@", 1)[1], config_digest}
    for section, status_section, container in (
        ("initContainers", "initContainerStatuses", "fixture"),
        ("containers", "containerStatuses", "flask"),
    ):
        spec = next(item for item in pod["spec"][section] if item["name"] == container)
        actual = next(item for item in pod["status"][status_section] if item["name"] == container)
        identifier = re.search(r"(sha256:[0-9a-f]{64})$", actual["imageID"])
        if (spec["image"] != image or spec["imagePullPolicy"] != "Never"
                or not identifier or identifier.group(1) not in allowed):
            raise RuntimeError("The Pod did not execute the approved image")
        runtime_ids[container] = identifier.group(1)
    return runtime_ids


def run_job(name, image, code, ip, *, denied=False, zap=False):
    labels = {"securestay.io/test-egress": "true"}
    if not denied:
        labels["securestay.io/test-ingress"] = "true"
    env = [{"name": "TARGET_IP", "value": ip}]
    if zap:
        env.append({"name": "DAST_PASSWORD", "valueFrom": {"secretKeyRef": {
            "name": "securestay-dast-fixture", "key": "password",
        }}})
    else:
        env.append({"name": "EXPECT_TIMEOUT", "value": str(denied).lower()})
    uid = 1000 if zap else 10001
    job = {
        "apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": name},
        "spec": {
            "backoffLimit": 0, "ttlSecondsAfterFinished": 600, "activeDeadlineSeconds": 330,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "serviceAccountName": "securestay-dast",
                    "automountServiceAccountToken": False, "restartPolicy": "Never",
                    "securityContext": {"runAsNonRoot": True, "runAsUser": uid,
                                        "runAsGroup": uid, "fsGroup": uid,
                                        "seccompProfile": {"type": "RuntimeDefault"}},
                    "volumes": [{"name": "tmp", "emptyDir": {"sizeLimit": "256Mi"}}],
                    "containers": [{
                        "name": "runner", "image": image, "command": ["python3", "-c", code],
                        "imagePullPolicy": "IfNotPresent" if zap else "Never",
                        "env": env, "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                        "securityContext": {"allowPrivilegeEscalation": False,
                                            "readOnlyRootFilesystem": True,
                                            "capabilities": {"drop": ["ALL"]}},
                        "resources": {"requests": {"cpu": "50m", "memory": "128Mi"},
                                      "limits": {"cpu": "1", "memory": "768Mi"}},
                    }],
                },
            },
        },
    }
    kubectl("create", "-f", "-", stdin=json.dumps(job))
    try:
        for _ in range(170):
            conditions = get("job", name).get("status", {}).get("conditions", [])
            if any(c["type"] == "Failed" and c["status"] == "True" for c in conditions):
                raise RuntimeError(f"Test Job {name} failed")
            if any(c["type"] == "Complete" and c["status"] == "True" for c in conditions):
                return kubectl("logs", "job/" + name) if zap else ""
            time.sleep(2)
        raise TimeoutError(f"Test Job {name} did not finish")
    finally:
        kubectl("delete", "job", name, "--ignore-not-found", "--wait=false")


def read_report(raw):
    report = json.loads(raw)
    checks = report["checks"]
    if set(checks) != CHECKS or not all(isinstance(result, bool) for result in checks.values()):
        raise ValueError("Invalid DAST checks")
    alerts = []
    for entry in report["alerts"]:
        rule, risk = entry["rule"], entry["risk"]
        if type(rule) is not int or rule <= 0 or type(risk) is not int or risk not in (0, 1, 2, 3):
            raise ValueError("Invalid DAST risk metadata")
        alerts.append({"rule": rule, "risk": risk})
    return checks, alerts


def write_reports(result):
    root = Path("reports")
    root.mkdir(exist_ok=True)
    content = json.dumps(result, indent=2)
    (root / "zap-passive.json").write_text(content + "\n", encoding="utf-8")
    (root / "zap-passive.html").write_text(
        '<!doctype html><html lang="fr"><meta charset="utf-8"><title>SecureStay ZAP</title>'
        '<h1>SecureStay ZAP passif</h1><pre>' + html.escape(content) + '</pre></html>\n',
        encoding="utf-8",
    )


def main():
    release = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    image = release["image"]
    config_digest = release["config_digest"]
    zap_image = os.environ["ZAP_IMAGE"]
    if (not re.fullmatch(TARGET_IMAGE, image) or not re.fullmatch(ZAP_IMAGE, zap_image)
            or image.split("@", 1)[1] != release["manifest_digest"]
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", config_digest)):
        raise ValueError("Expected digest-pinned SecureStay and ZAP images")

    token = secrets.token_hex(5)
    result = {
        "image": image, "archive_sha256": release["archive_sha256"],
        "import_operator": os.environ["SECURESTAY_IMPORT_OPERATOR"],
        "runtime_images": {}, "network": {}, "checks": {}, "alerts": [], "complete": False,
    }
    try:
        identity = json.loads(kubectl("auth", "whoami", "-o", "json"))["status"]["userInfo"]["username"]
        if identity != "system:serviceaccount:securestay-dast:securestay-deploy":
            raise RuntimeError("Unexpected identity for isolated deployment")
        ip = str(ipaddress.IPv4Address(get("service", "securestay")["spec"]["clusterIP"]))
        deployed = patch({"spec": {"replicas": 1, "template": {
            "metadata": {"annotations": {"securestay.io/test-run": token}},
            "spec": {"initContainers": [{"name": "fixture", "image": image}],
                     "containers": [{"name": "flask", "image": image}]},
        }}})
        try:
            wait_for_deployment(deployed["metadata"]["generation"])
            result["runtime_images"] = verify_runtime(image, config_digest, token)
            for name, denied in (("positive", False), ("negative", True), ("recheck", False)):
                run_job(f"securestay-{name}-{token}", image, PROBE, ip, denied=denied)
                result["network"][name] = True
            raw = run_job("securestay-zap-" + token, zap_image,
                          Path(__file__).with_name("zap.py").read_text(), ip, zap=True)
            result["checks"], result["alerts"] = read_report(raw)
            result["complete"] = True
        finally:
            patch({"spec": {"replicas": 0}})
    finally:
        write_reports(result)
    return int(not all(result["checks"].values()) or any(a["risk"] == 3 for a in result["alerts"]))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("SecureStay isolated DAST did not complete.", file=sys.stderr)
        raise SystemExit(1)
