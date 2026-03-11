pipeline {
    agent {
        kubernetes {
            yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: gradle
    image: registry.internal.example.com/tools/gradle:8.5-jdk17
    command: ['sleep', '99d']
  - name: python
    image: registry.internal.example.com/tools/python:3.11-bdd
    command: ['sleep', '99d']
  - name: helm
    image: registry.internal.example.com/tools/helm:3.14
    command: ['sleep', '99d']
  - name: security
    image: registry.internal.example.com/tools/syft-grype:latest
    command: ['sleep', '99d']
'''
        }
    }

    environment {
        NEXUS_USER     = credentials('nexus-user')
        NEXUS_PASS     = credentials('nexus-pass')
        REGISTRY       = 'registry.internal.example.com'
        KUBECONFIG     = credentials('kubeconfig-test-cluster')
    }

    options {
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    stages {
        stage('Fetch Cameo Model') {
            steps {
                container('gradle') {
                    sh './gradlew unpackCameoZip --no-daemon'
                }
            }
        }

        stage('Traceability Check') {
            steps {
                container('python') {
                    sh '''
                        pip install -r tools/requirements.txt --quiet
                        python3 tools/traceability_checker.py \
                            --requirements build/cameo/requirements/requirements.json \
                            --features-dir bdd/features \
                            --stubs-output-dir bdd/features/automated \
                            --non-test-output-dir bdd/features/non_test \
                            --report-output build/reports/traceability/traceability_report.json \
                            --html-report-output build/reports/traceability/traceability_report.html \
                            --fail-on-uncovered \
                            --fail-on-orphaned
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build/reports/traceability/**', allowEmptyArchive: true
                }
                failure {
                    echo 'TRACEABILITY GATE FAILED: Check report for uncovered, drifted, or orphaned requirements.'
                }
            }
        }

        stage('Run Simulations') {
            steps {
                container('helm') {
                    sh '''
                        TOPOLOGY=$(grep deploy.topology versions.properties | cut -d= -f2)
                        bash scripts/run_simulations.sh test build/logs "${TOPOLOGY:-pod}" 300
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build/logs/**', allowEmptyArchive: true
                }
            }
        }

        stage('BDD Log Analysis') {
            environment {
                LOG_DIR = 'build/logs'
            }
            steps {
                container('python') {
                    sh '''
                        pip install -r bdd/requirements.txt --quiet
                        cd bdd
                        python3 -m behave \
                            --format json \
                            --outfile ../build/reports/bdd/behave-results.json \
                            --format pretty \
                            --no-capture \
                            features/
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build/reports/bdd/**', allowEmptyArchive: true
                }
            }
        }

        stage('Traceability Report') {
            steps {
                container('python') {
                    sh '''
                        python3 tools/report_generator.py \
                            --requirements build/cameo/requirements/requirements.json \
                            --behave-results build/reports/bdd/behave-results.json \
                            --traceability-input build/reports/traceability/traceability_report.json \
                            --output-json build/reports/traceability/traceability_report.json \
                            --output-html build/reports/traceability/traceability_report.html
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build/reports/traceability/**'
                    publishHTML(target: [
                        reportName: 'Traceability Matrix',
                        reportDir: 'build/reports/traceability',
                        reportFiles: 'traceability_report.html',
                        keepAll: true
                    ])
                }
            }
        }

        stage('Security Scan') {
            steps {
                container('security') {
                    sh '''
                        TOPOLOGY=$(grep deploy.topology versions.properties | cut -d= -f2)
                        if [ "${TOPOLOGY}" = "single" ]; then
                            IMAGE="$(grep single.container.image versions.properties | cut -d= -f2):$(grep single.container.version versions.properties | cut -d= -f2)"
                            IMAGES="${IMAGE}"
                        else
                            IMAGES="$(grep container.a.image versions.properties | cut -d= -f2):$(grep container.a.version versions.properties | cut -d= -f2)"
                            IMAGES="${IMAGES},$(grep container.b.image versions.properties | cut -d= -f2):$(grep container.b.version versions.properties | cut -d= -f2)"
                            IMAGES="${IMAGES},$(grep sidecar.image versions.properties | cut -d= -f2):$(grep sidecar.version versions.properties | cut -d= -f2)"
                        fi
                        bash security/scan.sh \
                            --registry ${REGISTRY} \
                            --images "${IMAGES}" \
                            --sbom-output build/reports/security/sbom.json \
                            --grype-output build/reports/security/grype-results.json \
                            --policy security/grype-policy.yaml
                    '''
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build/reports/security/**'
                }
            }
        }

        stage('Package & Publish') {
            when { branch 'main' }
            steps {
                container('helm') {
                    sh '''
                        CHART_VERSION=$(grep helm.chart.version versions.properties | cut -d= -f2)
                        helm package helm/product-chart \
                            --version "${CHART_VERSION}" \
                            --destination build/helm
                        helm push "build/helm/product-chart-${CHART_VERSION}.tgz" \
                            "oci://${REGISTRY}/helm-charts"
                    '''
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'build/reports/**', allowEmptyArchive: true
        }
        success {
            echo 'Pipeline succeeded.'
        }
        failure {
            echo 'Pipeline failed. Review archived reports.'
        }
    }
}
