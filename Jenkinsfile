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
    }

    post {
        always {
            archiveArtifacts artifacts: 'reports/*.json',
                             allowEmptyArchive: true
        }
    }
}
