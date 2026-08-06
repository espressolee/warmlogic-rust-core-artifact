#!/bin/bash
# WarmLogic K8s Local Deployment Script
# Supports: minikube, kind, docker-desktop

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
NAMESPACE="warmlogic"
RELEASE_NAME="warmlogic"

echo "🚀 WarmLogic K8s Deployment"
echo "=========================="

# Detect K8s environment
detect_k8s() {
    if kubectl config current-context 2>/dev/null | grep -q "minikube"; then
        echo "minikube"
    elif kubectl config current-context 2>/dev/null | grep -q "kind"; then
        echo "kind"
    elif kubectl config current-context 2>/dev/null | grep -q "docker-desktop"; then
        echo "docker-desktop"
    else
        echo "unknown"
    fi
}

# Build Docker image
build_image() {
    echo "📦 Building Docker image..."
    docker build -t warmlogic/core:latest "$PROJECT_ROOT"

    K8S_ENV=$(detect_k8s)
    if [ "$K8S_ENV" = "minikube" ]; then
        echo "Loading image to minikube..."
        minikube image load warmlogic/core:latest
    elif [ "$K8S_ENV" = "kind" ]; then
        echo "Loading image to kind..."
        kind load docker-image warmlogic/core:latest
    fi
}

# Create namespace
create_namespace() {
    echo "📁 Creating namespace: $NAMESPACE"
    kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
}

# Deploy with Helm
deploy_helm() {
    echo "⎈ Deploying with Helm..."

    HELM_DIR="$PROJECT_ROOT/deploy/helm/warmlogic"

    helm upgrade --install $RELEASE_NAME "$HELM_DIR" \
        --namespace $NAMESPACE \
        --set image.repository=warmlogic/core \
        --set image.tag=latest \
        --set image.pullPolicy=Never \
        --set warmlogic.env=development \
        --set warmlogic.security.fipsMode=false \
        --wait \
        --timeout 5m
}

# Port forward
port_forward() {
    echo "🔗 Setting up port forwarding..."
    kubectl port-forward -n $NAMESPACE svc/$RELEASE_NAME 8080:8080 &
    echo "API available at: http://localhost:8080"
}

# Check status
check_status() {
    echo ""
    echo "📊 Deployment Status:"
    kubectl get pods -n $NAMESPACE
    echo ""
    kubectl get svc -n $NAMESPACE
    echo ""
    kubectl get hpa -n $NAMESPACE 2>/dev/null || echo "HPA not enabled"
}

# Cleanup
cleanup() {
    echo "🧹 Cleaning up..."
    helm uninstall $RELEASE_NAME -n $NAMESPACE 2>/dev/null || true
    kubectl delete namespace $NAMESPACE 2>/dev/null || true
}

# Main
main() {
    case "${1:-deploy}" in
        deploy)
            K8S_ENV=$(detect_k8s)
            echo "Detected K8s: $K8S_ENV"

            build_image
            create_namespace
            deploy_helm
            check_status

            echo ""
            echo "✅ Deployment complete!"
            echo "Run: kubectl port-forward -n $NAMESPACE svc/$RELEASE_NAME 8080:8080"
            ;;
        status)
            check_status
            ;;
        cleanup)
            cleanup
            echo "✅ Cleanup complete!"
            ;;
        *)
            echo "Usage: $0 {deploy|status|cleanup}"
            exit 1
            ;;
    esac
}

main "$@"
