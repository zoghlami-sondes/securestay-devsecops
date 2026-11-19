
pipeline {
    agent { label 'securestay-agent' }

    options {
        timestamps()
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
    }

    parameters {
        booleanParam(
            name: 'BUILD_IMAGE',
            defaultValue: false,
            description: 'Activer après configuration du securestay-builder'
        )
        booleanParam(
            name: 'ENFORCE_SECURITY_GATE',
            defaultValue: false,
            description: 'Activer après validation des résultats initiaux'
        )
    }

    stages {
        stage('Checkout GitHub') {
            steps {
                checkout scm
            }
        }

        stage('Verify Source') {
            steps {
                sh '''
                    test -f Dockerfile
                    test -f app/requirements.txt
                    mkdir -p reports
                    echo "SecureStay source verified"
                '''
            }
        }

        stage('SAST - Semgrep') {
            steps {
                sh '''
                    semgrep scan \
                      --config auto \
                      --json \
                      --output reports/semgrep.json \
                      .
                '''
            }
        }

        stage('Secrets - Gitleaks') {
            steps {
                sh '''
                    gitleaks git . \
                      --redact=100 \
                      --exit-code 0 \
                      --report-format json \
                      --report-path reports/gitleaks-git.json \
                      --no-banner

                    gitleaks dir . \
                      --redact=100 \
                      --exit-code 0 \
                      --report-format json \
                      --report-path reports/gitleaks-files.json \
                      --no-banner

                    test -s reports/gitleaks-git.json || \
                      printf '[]\\n' > reports/gitleaks-git.json

                    test -s reports/gitleaks-files.json || \
                      printf '[]\\n' > reports/gitleaks-files.json
                '''
            }
        }

        stage('SCA - Trivy Dependencies') {
            steps {
                sh '''
                    trivy fs . \
                      --scanners vuln \
                      --format json \
                      --output reports/trivy-sca.json \
                      --exit-code 0
                '''
            }
        }

        stage('IaC - Trivy Configuration') {
            steps {
                sh '''
                    trivy config . \
                      --format json \
                      --output reports/trivy-iac.json \
                      --exit-code 0
                '''
            }
        }

        stage('Security Report') {
            steps {
                sh '''
                    python3 - <<'PY'
import json
import html
from pathlib import Path

root = Path("reports")

def load(name, fallback):
    path = root / name
    if not path.exists() or not path.stat().st_size:
        return fallback
    return json.loads(path.read_text())

semgrep = load("semgrep.json", {})
git_history = load("gitleaks-git.json", [])
git_files = load("gitleaks-files.json", [])
sca = load("trivy-sca.json", {})
iac = load("trivy-iac.json", {})

def findings(report):
    return [
        v
        for result in report.get("Results", [])
        for v in result.get("Vulnerabilities", [])
    ]

def misconfigs(report):
    return [
        m
        for result in report.get("Results", [])
        for m in result.get("Misconfigurations", [])
    ]

rows = [
    ("SAST - Semgrep",
     len(semgrep.get("results", []))),
    ("Secrets - Git History",
     len(git_history)),
    ("Secrets - Working Files",
     len(git_files)),
    ("SCA - Trivy",
     len(findings(sca))),
    ("IaC - Trivy",
     len(misconfigs(iac))),
]

parts = [
    "<!doctype html><html><head><meta charset='utf-8'>",
    "<title>SecureStay Security Report</title>",
    "<style>",
    "body{font-family:Arial,sans-serif;max-width:950px;",
    "margin:40px auto;color:#172334}",
    "h1{color:#16345c}",
    "table{border-collapse:collapse;width:100%}",
    "th,td{padding:14px;border:1px solid #d6dce5}",
    "th{background:#edf2f8;text-align:left}",
    "tr:nth-child(even){background:#f8fafc}",
    "</style></head><body>",
    "<h1>SecureStay - DevSecOps Security Report</h1>",
    "<p>Initial automated security assessment</p>",
    "<table><tr><th>Security Control</th>",
    "<th>Findings</th></tr>"
]

for name, count in rows:
    parts.append(
        "<tr><td>" + html.escape(name) +
        "</td><td>" + str(count) + "</td></tr>"
    )

parts.append("</table>")
parts.append(
    "<p>Findings require validation. Zero findings "
    "does not prove the application is secure.</p>"
)
parts.append("</body></html>")

(root / "security-report.html").write_text(
    "\\n".join(parts), encoding="utf-8"
)

print("=== SECURITY SUMMARY ===")
for name, count in rows:
    print(f"{name}: {count}")
PY
                '''
            }
        }

        stage('Security Gate') {
            when {
                expression {
                    return params.ENFORCE_SECURITY_GATE
                }
            }
            steps {
                sh '''
                    python3 - <<'PY'
import json
from pathlib import Path

root = Path("reports")

def load(name):
    return json.loads((root / name).read_text())

semgrep = load("semgrep.json")
gitleaks_git = load("gitleaks-git.json")
gitleaks_files = load("gitleaks-files.json")
sca = load("trivy-sca.json")
iac = load("trivy-iac.json")

critical = sum(
    v.get("Severity") in ("HIGH", "CRITICAL")
    for result in sca.get("Results", [])
    for v in result.get("Vulnerabilities", [])
)

critical += sum(
    m.get("Severity") in ("HIGH", "CRITICAL")
    for result in iac.get("Results", [])
    for m in result.get("Misconfigurations", [])
)

errors = sum(
    r.get("extra", {}).get("severity") == "ERROR"
    for r in semgrep.get("results", [])
)

secrets = len(gitleaks_git) + len(gitleaks_files)

print(f"Semgrep ERROR: {errors}")
print(f"Trivy HIGH/CRITICAL: {critical}")
print(f"Gitleaks findings: {secrets}")

if errors or critical or secrets:
    raise SystemExit("SECURITY GATE FAILED")

print("SECURITY GATE PASSED")
PY
                '''
            }
        }

        stage('Docker Build + Trivy Image') {
            when {
                expression {
                    return params.BUILD_IMAGE
                }
            }
            agent {
                label 'securestay-builder'
            }
            steps {
                checkout scm
                sh '''
                    set -eu

                    docker build \
                      -t securestay:${BUILD_NUMBER} .

                    mkdir -p reports

                    trivy image \
                      --scanners vuln \
                      --format json \
                      --output reports/trivy-image.json \
                      securestay:${BUILD_NUMBER}
                '''
                archiveArtifacts(
                    artifacts: 'reports/trivy-image.json',
                    allowEmptyArchive: false
                )
            }
        }
    }

    post {
        always {
            archiveArtifacts(
                artifacts: 'reports/*.json,reports/*.html',
                allowEmptyArchive: true
            )
        }
    }
}
