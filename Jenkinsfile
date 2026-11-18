pipeline {
    agent { label 'securestay-agent' }

    stages {
        stage('Checkout GitHub') {
            steps {
                checkout scm
            }
        }

        stage('Verify Source') {
            steps {
                sh '''
                    echo "=== SecureStay ==="
                    test -f Dockerfile
                    test -f app/requirements.txt
                    echo "Source code OK"
                '''
            }
        }
    }
}

