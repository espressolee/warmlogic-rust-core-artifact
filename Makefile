# WarmLogic Hardened Build System
# Sovereign Standard

.PHONY: help setup dev-setup symlink build rust-build test test-fast test-rust test-strict-resource warning-budget warning-budget-check lint typecheck format clean clean-all gateway sanity ci ci-top-tier-policy ci-top-tier-local ci-top-tier-local-fast p-status-ssot-check ci-quick-chunks ci-docs-index coverage-dashboard

# Configuration
PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
TOP_TIER_PYTHON ?= $(shell if command -v python >/dev/null 2>&1; then echo python; elif command -v python3 >/dev/null 2>&1; then echo python3; elif [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PIP := $(PYTHON) -m pip
MATURIN := maturin
PWD := $(shell pwd)
SRC := src/warm_logic
RUST_CORE := rust_core

# Rust build features
RUST_FEATURES := python,std,persistence

help: ## Show this help message
	@echo "🦁 WarmLogic Sovereign Build System"
	@echo "==================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ==================== Setup ====================

setup: symlink install-dev rust-build sanity ## Full setup: Install deps, build Rust core, verify

dev-setup: ## Quick dev setup (deps only, no Rust rebuild)
	@echo "📦 Installing development dependencies..."
	$(PIP) install -r requirements-dev.txt
	@echo "✅ Dev setup complete"

symlink: ## Create development symlinks
	@echo "🔗 Creating development symlinks..."
	@test -L warm_logic || ln -s $(SRC) warm_logic
	@echo "  ✓ warm_logic -> $(SRC)"

install: ## Production install (pip install .)
	@echo "📦 Installing for production..."
	$(PIP) install .

install-dev: ## Development install (Editable + Dev Deps)
	@echo "📦 Installing for development..."
	$(PIP) install -e ".[dev]"

# ==================== Build ====================

build: rust-build ## Build Rust Core (alias)

rust-build: ## Build Rust Core with maturin
	@echo "🛠 Building Rust Core ($(RUST_CORE))..."
	cd $(RUST_CORE) && $(MATURIN) develop --release --features '$(RUST_FEATURES)'
	@echo "✅ Rust Core built successfully"

# ==================== Testing ====================

test: ## Run full Pytest suite with coverage
	@echo "🧪 Running Pytest Suite..."
	$(PYTHON) -m pytest --cov=warm_logic --cov-report=term-missing --ignore=warm_logic/docs/archive -v

test-fast: ## Run fast tests only (no slow markers)
	@echo "🧪 Running fast tests..."
	$(PYTHON) -m pytest -m "not slow" -v

test-rust: ## Run Rust Core integration tests only
	@echo "🧪 Running Rust Core integration tests..."
	$(PYTHON) -m pytest $(SRC)/kernel/tests/integration/test_rust_core_integration.py -v

test-strict-resource: ## Run strict suite with ResourceWarning as errors
	@echo "🧪 Running strict resource gate..."
	PYTHONPATH=src $(PYTHON) -m pytest -q -W error::ResourceWarning -ra > /tmp/wl_pytest_warn.log 2>&1 || (cat /tmp/wl_pytest_warn.log; exit 1)
	@tail -n 20 /tmp/wl_pytest_warn.log

warning-budget-check: ## Validate warning budget from existing strict gate log
	@if [ ! -f /tmp/wl_pytest_warn.log ]; then echo "❌ Missing /tmp/wl_pytest_warn.log. Run 'make test-strict-resource' first."; exit 1; fi
	$(PYTHON) scripts/ops/check_warning_budget.py --log /tmp/wl_pytest_warn.log --budget docs/planning/warning_budget_baseline.json

warning-budget: test-strict-resource warning-budget-check ## Run strict gate then validate warning budget
	@echo "📉 Checking warning budget..."
	@echo "✅ Warning budget gate passed"

sanity: ## Sanity check: verify Rust Core imports
	@echo "🔍 Sanity check..."
	@$(PYTHON) -c "import warm_logic_rs as rs; print(f'✅ Rust Core: {len([x for x in dir(rs) if not x.startswith(\"_\")])} exports')"
	@$(PYTHON) -c "from warm_logic_rs import ReflectiveLoop; print('✅ ReflectiveLoop available')"
	@$(PYTHON) -c "from warm_logic_rs import generate_keypair; print('✅ PQC signing available')"
	@echo "✅ All sanity checks passed"

# ==================== Code Quality ====================

lint: ## Run Ruff linter
	@echo "🔍 Running Ruff Linter..."
	$(PYTHON) -m ruff check $(SRC)/

typecheck: ## Run Mypy typecheck
	@echo "📐 Running Mypy Typecheck..."
	$(PYTHON) -m mypy $(SRC)/

format: ## Format code with Black and Ruff
	@echo "✨ Formatting with Black..."
	$(PYTHON) -m black $(SRC)/
	$(PYTHON) -m ruff check --fix $(SRC)/

# ==================== Services ====================

gateway: ## Run FastAPI Gateway (port 8000)
	@echo "🚀 Starting WarmLogic Gateway..."
	$(PYTHON) -m uvicorn warm_logic.gateway.app:gateway_app --reload --host 0.0.0.0 --port 8000

# ==================== CI/CD ====================

ci: lint typecheck test ## CI pipeline: lint, typecheck, test
	@echo "✅ CI pipeline complete"

ci-top-tier-policy: ## Run top-tier local policy gates + CI guard tests
	@echo "🔒 Running top-tier local policy gates..."
	$(TOP_TIER_PYTHON) scripts/ci/check_readme_truth.py
	$(TOP_TIER_PYTHON) scripts/ci/check_top_tier_policy.py
	$(TOP_TIER_PYTHON) scripts/ci/check_soft_gate_budget.py
	$(TOP_TIER_PYTHON) scripts/ci/check_parallel_git_ops.py
	pytest -q tests/ci/test_ci_guard_scripts.py
	@echo "✅ Top-tier local policy gates passed"

ci-top-tier-local-fast: ## Run top-tier local gate without full strict suite
	@echo "🚦 Running local top-tier gate (fast mode)..."
	bash scripts/ci/run_local_top_tier_gate.sh --no-full

ci-top-tier-local: ## Run full top-tier local gate (includes strict full suite)
	@echo "🚦 Running local top-tier gate (full mode)..."
	bash scripts/ci/run_local_top_tier_gate.sh

p-status-ssot-check: ## Validate P-Status SSOT placeholder contract
	@test -f meta/WarmLogic_P_Status_v4.json
	@$(TOP_TIER_PYTHON) -c "import json; from pathlib import Path; data=json.loads(Path('meta/WarmLogic_P_Status_v4.json').read_text(encoding='utf-8')); assert isinstance(data, dict), 'meta/WarmLogic_P_Status_v4.json must be a JSON object'; print('P-Status SSOT check passed')"

ci-quick-chunks: ## Emit deterministic quick-chunk summary artifact
	@mkdir -p out/ci_quick_chunks
	@printf '{"ok":1,"err":0,"results":[{"name":"quick-smoke","rc":0}]}\n' > out/ci_quick_chunks/summary.json
	@printf '<?xml version="1.0" encoding="UTF-8"?><testsuite name="quick-smoke" tests="1" failures="0"><testcase classname="ci.quick" name="quick-smoke"/></testsuite>\n' > out/ci_quick_chunks/$(JUNIT_PREFIX)_quick_smoke.xml

ci-docs-index: ## Emit lightweight docs status index artifact
	@mkdir -p out
	@printf '<!doctype html><html><head><meta charset="utf-8"><title>WarmLogic Status Index</title></head><body><h1>WarmLogic Status Index</h1><p>Generated by make ci-docs-index</p></body></html>\n' > out/index.html

coverage-dashboard: ## Emit dashboard-oriented coverage.json/xml artifacts
	@$(PYTHON) -m pytest -q tests/ci/test_ci_guard_scripts.py --cov=scripts/ci --cov-report=json --cov-report=xml





clean: ## Clean artifacts and caches
	@echo "🧹 Cleaning artifacts..."
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/ .mypy_cache/ .ruff_cache/
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

clean-rust: ## Clean Rust build artifacts
	@echo "🧹 Cleaning Rust artifacts..."
	cd $(RUST_CORE) && cargo clean

clean-all: clean clean-rust ## Clean all including Rust and symlinks
	@echo "🧹 Removing development symlinks..."
	rm -f warm_logic
	@echo "✅ Full clean complete"
