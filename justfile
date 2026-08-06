# 🏛️ WarmLogic Sovereignty Orchestration

# Setup the environment
setup:
    @echo "🚀 Igniting Sovereignty Environment..."
    @pip install -r requirements.txt
    @mkdir -p out/audit
    @just rebuild-rust
    @just verify-docs

# Rebuild the Rust logic kernel
rebuild-rust:
    @echo "🦀 Compiling Rust Kernel..."
    cd warm_logic_rs && maturin build --release
    cp warm_logic_rs/target/release/lib_warm_logic_rust.dylib warm_logic/warm_logic_rs.so
    python3 -c "import warm_logic.warm_logic_rs; print('✅ Rust Extension Loaded')"

# Verify documentation integrity
verify-docs:
    @echo "📖 Verifying Documentation Lattice..."
    python3 scripts/verify_docs_links.py

# Run the 35-point Harsh Audit
audit-35:
    @echo "⚖️ Executing Harsh Scoring Protocol (35/35)..."
    @just verify-docs
    @python3 -m pytest warm_logic/tests/
    @echo "✅ Audit Complete. Map is Territory."

# Clean environment (PRESERVES out/bridge_eval - protected Data)
clean:
    @echo "🧹 Purging entropy (protected Data Protected)..."
    @echo "⚠️  Preserving: out/bridge_eval/, out/audit/, out/oss_staging/"
    rm -rf out/sbom/ out/wheels/ out/tmp_src*/ out/gcloud_mock/ out/gcloud_temp/
    find . -name "__pycache__" -exec rm -rf {} +

# DANGER: Full purge including benchmark data (requires confirmation)
nuke:
    @echo "☢️  NUCLEAR OPTION: This will delete ALL out/ data including benchmarks!"
    @echo "    Run 'just nuke-confirm' to proceed."

nuke-confirm:
    @echo "☢️  Deleting ALL out/ data..."
    rm -rf out/
    @echo "💀 Done. Benchmark data destroyed."
