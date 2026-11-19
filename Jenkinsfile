pipeline {
    agent { label 'securestay-agent' }

    options {
        timestamps()
        skipDefaultCheckout(true)
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
                    echo "SecureStay source verified"
                '''
            }
        }

        stage('SAST - Semgrep') {
            steps {
                sh '''
                    mkdir -p reports

                    semgrep scan \
                      --config auto \
                      --json \
                      --output reports/semgrep-initial.json \
                      .
                '''
            }
        }

        stage('Secret Scanning - Gitleaks') {
            steps {
                sh '''
                    gitleaks git . \
                      --redact=100 \
                      --exit-code 0 \
                      --report-format json \
                      --report-path reports/gitleaks-initial.json \
                      --no-banner
                '''
            }
        }

        stage('SCA - Trivy') {
            steps {
                sh '''
                    trivy fs . \
                      --scanners vuln \
                      --format json \
                      --output reports/trivy-sca-initial.json \
                      --exit-code 0
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/*.json',
                             allowEmptyArchive: true
        }
    }
}

