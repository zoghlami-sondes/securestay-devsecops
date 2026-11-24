
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
            description: 'Activer apres validation du worker BuildKit SecureStay'
        )

        choice(
            name: 'IMAGE_CRITICAL_POLICY',
            choices: ['all', 'fixable', 'off'],
            description: 'Blocage CRITICAL image lorsque le Security Gate est actif'
        )

        booleanParam(
            name: 'DEPLOY_DAST',
            defaultValue: false,
            description: 'Importer et verifier uniquement dans securestay-dast apres le gate'
        )

        string(
            name: 'ZAP_IMAGE',
            defaultValue: '',
            description: 'Image ZAP approuvee, referencee par digest'
        )

        booleanParam(
            name: 'ENFORCE_SECURITY_GATE',
            defaultValue: false,
            description: 'Activer apres validation des resultats initiaux'
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
                script {
                    if (params.DEPLOY_DAST && (!params.BUILD_IMAGE || !params.ENFORCE_SECURITY_GATE ||
                                               params.IMAGE_CRITICAL_POLICY != 'all')) {
                        error('DEPLOY_DAST requires BUILD_IMAGE, ENFORCE_SECURITY_GATE and IMAGE_CRITICAL_POLICY=all.')
                    }
                    if (params.DEPLOY_DAST &&
                        !(params.ZAP_IMAGE ==~ /docker[.]io\/zaproxy\/zap-stable@sha256:[0-9a-f]{64}/)) {
                        error('DEPLOY_DAST requires an approved ZAP image digest.')
                    }
                }
                sh '''
                    set -e
                    test -f Dockerfile
                    test -f app/requirements.txt
                    mkdir -p reports
                    rm -f reports/trivy-image.json reports/trivy-image-fixable.json reports/zap-passive.json reports/zap-passive.html
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
                    set -eu
                    set -- ./ci/k8s-dast/rejected-pod.yaml ./k8s/tests/rejected-pod.yaml
                    python3 ci/check_psa_fixtures.py "$@"

                    trivy config . \
                      --skip-files "$1" \
                      --skip-files "$2" \
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

        stage('Docker Build + Trivy Image') {
            when {
                expression { return params.BUILD_IMAGE }
            }

            steps {
                script {
                    if (params.DEPLOY_DAST) {
                        env.SECURESTAY_OCI = pwd(tmp: true) + "/securestay-${env.BUILD_NUMBER}.oci.tar"
                    }
                }
                sh '''
                    set -eu
                    builder=/home/jenkins/agent/.securestay-buildkit
                    address="unix://$builder/buildkitd.sock"
                    "$builder/buildctl" --addr "$address" debug workers

                    work=$(mktemp -d)
                    trap 'rm -rf "$work"' EXIT
                    mkdir -p "$work/context" reports
                    git archive --format=tar --output="$work/source.tar" HEAD
                    tar -xf "$work/source.tar" -C "$work/context"

                    if [ -n "${SECURESTAY_OCI:-}" ]; then
                        mkdir -p "$(dirname "$SECURESTAY_OCI")" "$work/oci"
                        rm -f -- "$SECURESTAY_OCI"
                        set -- --opt platform=linux/amd64 --output "type=oci,name=docker.io/library/securestay:ci-$BUILD_NUMBER,dest=$SECURESTAY_OCI"
                        scan_input="$work/oci"
                    else
                        set -- --output "type=docker,name=securestay:$BUILD_NUMBER,dest=$work/image.tar"
                        scan_input="$work/image.tar"
                    fi

                    "$builder/buildctl" --addr "$address" build \
                      --frontend dockerfile.v0 \
                      --local context="$work/context" \
                      --local dockerfile="$work/context" \
                      "$@"

                    if [ -n "${SECURESTAY_OCI:-}" ]; then
                        archive_sha=$(sha256sum "$SECURESTAY_OCI")
                        tar -xf "$SECURESTAY_OCI" -C "$scan_input"
                    fi
                    trivy image \
                      --input "$scan_input" \
                      --scanners vuln \
                      --severity HIGH,CRITICAL \
                      --ignorefile /dev/null \
                      --format json \
                      --exit-code 0 \
                      --output reports/trivy-image.json

                    python3 ci/trivy_image_policy.py fixable \
                      reports/trivy-image.json reports/trivy-image-fixable.json

                    if [ -n "${SECURESTAY_OCI:-}" ]; then
                        python3 ci/k8s-dast/release.py "$scan_input" "$SECURESTAY_OCI" \
                          "${archive_sha%% *}" reports/trivy-image.json "$(git rev-parse HEAD)" \
                          "$SECURESTAY_OCI.json"
                    fi
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
import os
import subprocess
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

image_failed = False
if os.environ.get("BUILD_IMAGE") == "true":
    image_gate = subprocess.run([
        "python3", "ci/trivy_image_policy.py", "gate",
        "reports/trivy-image.json", "--critical", os.environ["IMAGE_CRITICAL_POLICY"]
    ])
    image_failed = image_gate.returncode != 0

if errors or critical or secrets or image_failed:
    raise SystemExit("SECURITY GATE FAILED")

print("SECURITY GATE PASSED")
PY
                '''
                script {
                    env.SECURESTAY_GATE_PASSED = 'true'
                }
            }
        }

        stage('Authorize local OCI delivery') {
            when { expression { return params.DEPLOY_DAST } }
            steps {
                timeout(time: 45, unit: 'MINUTES') {
                    script {
                        if (env.SECURESTAY_GATE_PASSED != 'true' ||
                            !env.SECURESTAY_IMPORT_APPROVERS?.trim()) {
                            error('A successful gate and a configured import approver are required.')
                        }
                        input message: 'Autoriser la mise a disposition de l’archive OCI controlee ?',
                              ok: 'Autoriser la livraison',
                              submitter: env.SECURESTAY_IMPORT_APPROVERS
                        env.SECURESTAY_DELIVERY_APPROVED = 'true'
                    }
                }
            }
        }

        stage('Archive gated OCI image') {
            when { expression { return params.DEPLOY_DAST } }
            steps {
                script {
                    if (env.SECURESTAY_GATE_PASSED != 'true' || env.SECURESTAY_DELIVERY_APPROVED != 'true' ||
                        !env.SECURESTAY_IMPORT_APPROVERS?.trim()) {
                        error('A successful gate and a configured import approver are required.')
                    }
                }
                sh '''
                    set -eu
                    mkdir -p release
                    cp -- "$SECURESTAY_OCI" release/securestay.oci.tar
                    cp -- "$SECURESTAY_OCI.json" release/release.json
                    python3 -c 'import json; import sys; print(json.load(sys.stdin)["archive_sha256"] + "  release/securestay.oci.tar")' \
                      < release/release.json | sha256sum --check
                '''
                archiveArtifacts artifacts: 'release/securestay.oci.tar,release/release.json',
                                 fingerprint: true
            }
        }

        stage('Approve local kind import') {
            when { expression { return params.DEPLOY_DAST } }
            steps {
                timeout(time: 45, unit: 'MINUTES') {
                    script {
                        if (env.SECURESTAY_GATE_PASSED != 'true' || env.SECURESTAY_DELIVERY_APPROVED != 'true' ||
                            !env.SECURESTAY_IMPORT_APPROVERS?.trim()) {
                            error('This build has no gated archive or import approver.')
                        }
                        def imported = input(
                            message: "Importer l'archive de CE build depuis ${env.BUILD_URL}artifact/release/ et confirmer le digest vérifié.",
                            ok: 'Confirmer l’import',
                            submitter: env.SECURESTAY_IMPORT_APPROVERS,
                            submitterParameter: 'IMPORT_OPERATOR',
                            parameters: [string(name: 'IMPORTED_DIGEST', defaultValue: '',
                                                description: 'Digest du manifeste vérifié par le script Windows')]
                        )
                        withEnv(["APPROVED_DIGEST=${imported.IMPORTED_DIGEST}"]) {
                            sh '''
                                set +x
                                set -eu
                                python3 -c 'import json, os, sys; sys.exit(json.load(sys.stdin)["manifest_digest"] != os.environ["APPROVED_DIGEST"])' < release/release.json
                            '''
                        }
                        env.SECURESTAY_IMPORT_CONFIRMED = 'true'
                        env.SECURESTAY_IMPORT_OPERATOR = imported.IMPORT_OPERATOR
                    }
                }
            }
        }

        stage('Deploy and verify isolated SecureStay') {
            when { expression { return params.DEPLOY_DAST } }
            steps {
                timeout(time: 25, unit: 'MINUTES') {
                    script {
                        if (env.SECURESTAY_GATE_PASSED != 'true' || env.SECURESTAY_DELIVERY_APPROVED != 'true' ||
                            env.SECURESTAY_IMPORT_CONFIRMED != 'true') {
                            error('This build has no verified local import.')
                        }
                    }
                    withEnv(['PATH+SECURESTAY=/home/jenkins/agent/.securestay-tools']) {
                        withCredentials([file(credentialsId: 'securestay-dast-kubeconfig',
                                              variable: 'KUBECONFIG')]) {
                            sh '''
                                set +x
                                set -eu
                                command -v kubectl >/dev/null
                                python3 ci/k8s-dast/run.py release/release.json
                            '''
                        }
                    }
                }
            }
        }
    }

    post {
        cleanup {
            sh 'if [ -n "${SECURESTAY_OCI:-}" ]; then rm -f -- "$SECURESTAY_OCI" "$SECURESTAY_OCI.json" release/securestay.oci.tar release/release.json; fi'
        }
        always {
            archiveArtifacts(
                artifacts: 'reports/*.json,reports/*.html',
                allowEmptyArchive: true
            )
        }
    }
}
