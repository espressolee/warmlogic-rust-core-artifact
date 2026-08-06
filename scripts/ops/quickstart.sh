#!/usr/bin/env bash
# WarmLogic Quickstart Script
# Usage: ./quickstart.sh [mode]

set -e

echo "=================================================="
echo " WarmLogic Research Edition - Quickstart"
echo "=================================================="

MODE="${1:-help}"

function show_help() {
    echo "Usage: ./quickstart.sh [command]"
    echo ""
    echo "Commands:"
    echo "  demo        Run the Client-0 End-to-End Pilot Demo (Finance Vertical)"
    echo "  obs         Run the Observability Pilot (LLM Gateway Logs)"
    echo "  test        Run the core verified test suite"
    echo "  console     Start the Governance Console (requires Node.js)"
    echo "  help        Show this message"
    echo ""
}

function run_demo() {
    echo "[*] Running Client-0 Pilot Demo (Finance)..."
    bash scripts/workflow/client0_e2e.sh
}

function run_obs() {
    echo "[*] Running Observability Pilot (LLM Logs)..."
    python scripts/product/emit_llm_ce_from_logs.py \
        --logs logs/gateway/sample_breach.jsonl \
        --ledger ledger/CE_Ledger_v1.jsonl \
        --run-id RUN_QUICKSTART_OBS \
        --sli-out out/metrics/quickstart_sli.json
}

function run_test() {
    echo "[*] Running Core Tests..."
    pytest tests/ -v
}

function run_console() {
    echo "[*] Starting Governance Console..."
    if [ -d "ui/console" ]; then
        cd ui/console
        if [ ! -d "node_modules" ]; then
            npm install
        fi
        npm run dev
    else
        echo "[Error] ui/console directory not found."
        exit 1
    fi
}

case "$MODE" in
    "demo")
        run_demo
        ;;
    "obs")
        run_obs
        ;;
    "test")
        run_test
        ;;
    "console")
        run_console
        ;;
    *)
        show_help
        ;;
esac
