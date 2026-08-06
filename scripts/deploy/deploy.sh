#!/usr/bin/env bash
# WarmLogic Deployment Script
# Usage: ./scripts/deploy/deploy.sh [target] [options]
#
# Targets:
#   local       - Install in development mode (default)
#   docker      - Build Docker image
#   staging     - Deploy to staging (requires credentials)
#   production  - Production deployment guide
#
# Options:
#   --dry-run   - Preview without executing
#   --skip-tests - Skip test validation (not recommended)
#   --release   - Build in release mode
#   --verbose   - Show detailed output

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
TARGET="${1:-local}"
DRY_RUN=false
SKIP_TESTS=false
RELEASE=false
VERBOSE=false

# Parse options
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true ;;
        --skip-tests) SKIP_TESTS=true ;;
        --release) RELEASE=true ;;
        --verbose) VERBOSE=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Find project root
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}WarmLogic Deployment${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "Target:     $TARGET"
echo "Mode:       $([ "$DRY_RUN" = true ] && echo 'dry-run' || echo 'execute')"
echo "Release:    $([ "$RELEASE" = true ] && echo 'yes' || echo 'no')"
echo "Skip Tests: $([ "$SKIP_TESTS" = true ] && echo 'yes' || echo 'no')"
echo ""

# Pre-deployment checks
pre_deploy_checks() {
    echo -e "${YELLOW}=== Pre-Deployment Checks ===${NC}"

    # 1. P-Series compliance
    echo -n "  P-Series compliance... "
    VIOLATIONS=$(git log --oneline -5 | grep -cvE 'P[0-4][0-9]{2}' || echo "0")
    if [[ "$VIOLATIONS" -eq 0 ]]; then
        echo -e "${GREEN}PASS${NC}"
    else
        echo -e "${YELLOW}WARN ($VIOLATIONS non-compliant)${NC}"
    fi

    # 2. Reality enforcement
    echo -n "  Reality enforcement... "
    STUBS=$(grep -r "STUB_\|MOCK_\|FAKE_" src/warm_logic --include="*.py" 2>/dev/null | grep -cv test || echo "0")
    if [[ "$STUBS" -eq 0 ]]; then
        echo -e "${GREEN}PASS${NC}"
    else
        echo -e "${RED}FAIL ($STUBS stubs found)${NC}"
        if [[ "$DRY_RUN" = false ]]; then
            exit 1
        fi
    fi

    # 3. Tests (unless skipped)
    if [[ "$SKIP_TESTS" = false ]]; then
        echo -n "  Test validation... "
        if [[ "$DRY_RUN" = true ]]; then
            echo -e "${YELLOW}SKIP (dry-run)${NC}"
        else
            if pytest -m "not slow" -q --tb=no 2>/dev/null | tail -1 | grep -q "passed\|no tests"; then
                echo -e "${GREEN}PASS${NC}"
            else
                echo -e "${RED}FAIL${NC}"
                exit 1
            fi
        fi
    else
        echo -e "  Test validation... ${YELLOW}SKIPPED${NC}"
    fi

    echo ""
}

# Build Rust core
build_rust() {
    echo -e "${YELLOW}=== Building Rust Core ===${NC}"

    if [[ "$DRY_RUN" = true ]]; then
        echo "  Would run: cd warm_logic_rs && maturin develop"
        return
    fi

    cd warm_logic_rs

    if [[ "$RELEASE" = true ]]; then
        maturin develop --release
    else
        maturin develop
    fi

    cd "$PROJECT_ROOT"

    # Verify
    python3 -c "import warm_logic_rs; print(f'  Rust Core: v{warm_logic_rs.__version__}')"
    echo ""
}

# Install Python package
install_python() {
    echo -e "${YELLOW}=== Installing Python SDK ===${NC}"

    if [[ "$DRY_RUN" = true ]]; then
        echo "  Would run: pip install -e ."
        return
    fi

    pip install -e . --quiet

    # Verify
    python3 -c "from warm_logic.kernel import api; print('  Python SDK: OK')"
    echo ""
}

# Deploy local
deploy_local() {
    echo -e "${YELLOW}=== Local Deployment ===${NC}"

    build_rust
    install_python

    echo -e "${GREEN}Local deployment complete${NC}"
}

# Deploy Docker
deploy_docker() {
    echo -e "${YELLOW}=== Docker Deployment ===${NC}"

    # Get version from manifest
    VERSION=$(python3 -c "import yaml; print(yaml.safe_load(open('ROOT_MANIFEST.yaml')).get('version', '0.0.0'))" 2>/dev/null || echo "latest")

    if [[ "$DRY_RUN" = true ]]; then
        echo "  Would run: docker build -t warmlogic:$VERSION ."
        echo "  Would run: docker tag warmlogic:$VERSION warmlogic:latest"
        return
    fi

    # Check Dockerfile exists
    if [[ ! -f "Dockerfile" ]]; then
        echo -e "${RED}Dockerfile not found${NC}"
        exit 1
    fi

    echo "  Building image..."
    docker build -t warmlogic:$VERSION .
    docker tag warmlogic:$VERSION warmlogic:latest

    echo "  Image: warmlogic:$VERSION"
    echo ""

    # Verify
    echo "  Verifying image..."
    docker run --rm warmlogic:latest python3 -c "import warm_logic_rs; print('OK')" 2>/dev/null && \
        echo -e "${GREEN}Docker deployment complete${NC}" || \
        echo -e "${RED}Docker verification failed${NC}"
}

# Deploy staging
deploy_staging() {
    echo -e "${YELLOW}=== Staging Deployment ===${NC}"

    echo "  Staging deployment requires:"
    echo "    1. kubectl configured for staging cluster"
    echo "    2. KUBECONFIG environment variable set"
    echo "    3. Appropriate permissions"
    echo ""

    if [[ "$DRY_RUN" = true ]]; then
        echo "  Would run: kubectl apply -f k8s/staging/"
        return
    fi

    if [[ ! -d "k8s/staging" ]]; then
        echo -e "${YELLOW}k8s/staging/ not found${NC}"
        echo "  Create Kubernetes manifests first"
        exit 1
    fi

    echo "  Applying staging manifests..."
    kubectl apply -f k8s/staging/

    echo -e "${GREEN}Staging deployment initiated${NC}"
}

# Deploy production
deploy_production() {
    echo -e "${YELLOW}=== Production Deployment ===${NC}"
    echo ""
    echo -e "${RED}CRITICAL: Production deployment is controlled via CI/CD${NC}"
    echo ""
    echo "To deploy to production:"
    echo ""
    echo "  1. Ensure all checks pass:"
    echo "     - P-Series compliance: 100%"
    echo "     - Reality enforcement: PASS"
    echo "     - Tests: PASS"
    echo "     - Coverage: >= 70%"
    echo ""
    echo "  2. Create release tag:"
    echo "     git tag -a v1.x.x -m 'Release v1.x.x'"
    echo "     git push origin v1.x.x"
    echo ""
    echo "  3. CI/CD will automatically:"
    echo "     - Run full test suite"
    echo "     - Build Docker image"
    echo "     - Deploy to production"
    echo ""
    echo "  4. Monitor deployment:"
    echo "     gh run watch"
    echo ""
}

# Main execution
main() {
    pre_deploy_checks

    case "$TARGET" in
        local)
            deploy_local
            ;;
        docker)
            deploy_docker
            ;;
        staging)
            deploy_staging
            ;;
        production)
            deploy_production
            ;;
        *)
            echo -e "${RED}Unknown target: $TARGET${NC}"
            echo "Valid targets: local, docker, staging, production"
            exit 1
            ;;
    esac

    echo ""
    echo -e "${BLUE}======================================${NC}"
    echo "Deployment Summary"
    echo -e "${BLUE}======================================${NC}"
    echo "Target:    $TARGET"
    echo "Status:    $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'COMPLETE')"
    echo "Era:       4000 (Kinetic Fusion)"
    echo "Band:      P4xx (DevOps)"
    echo ""
}

main
