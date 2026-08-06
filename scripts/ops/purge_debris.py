import os
import shutil

ROOT = os.getcwd()
ARCHIVE_DIR = os.path.join(ROOT, "archives", "legacy_cleanup")

# Explicit list from hygiene failure
DEBRIS = [
    "AGENTS.md",
    "CLAUDE.md",
    "CORE_METRICS_v1.md",
    "FINAL_MISSION_LOG.md",
    "HARSH_DOC_MATURITY_REPORT_v1.md",
    "METRICS_UTILIZATION_v1.md",
    "PROJECT_HISTORY_MASTER_LOG.md",
    "REPRODUCTION_RECEIPT.txt",
    "ROOT_MANIFEST.yaml",
    "SIMULATION_RESULT_PHASE_100.md",
    "SOVEREIGN_BASELINE.json",
    "SOVEREIGN_GOLDEN_SEAL.json",
    "SOVEREIGN_MASTER_INDEX.md",
    "WARMLOGIC_CLOSURE_SCENARIO_v1.md",
    "WARM_LOGIC_FINAL_SUBMISSION",
    "WARM_LOGIC_FINAL_SUBMISSION_2026-01-26.zip",
    "_warm_logic_rust.py",
    "aggregate_coverage.txt",
    "all_py_files.txt",
    "arch_debug.txt",
    "arch_failure.txt",
    "arxiv_submission",
    "audit",
    "benchmarks",
    "collection_errors.txt",
    "collection_errors_v5.txt",
    "collection_errors_v6.txt",
    "collection_report.txt",
    "collection_status_v2.txt",
    "collection_status_v3.txt",
    "collection_status_v4.txt",
    "console",
    "core_failures.txt",
    "debug_import.py",
    "debug_p300",
    "dev",
    "error_log.txt",
    "error_log_2.txt",
    "evidence",
    "examples",
    "explorer_dashboard.html",
    "fail_log.txt",
    "fixtures",
    "full_run.txt",
    "gateway",
    "hardening_config.html",
    "infrastructure",
    "kernel_fail_2.txt",
    "ledger",
    "llama.cpp",
    "logs",
]


def purge():
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

    print(f"Purging debris to {ARCHIVE_DIR}...")

    for item in DEBRIS:
        src = os.path.join(ROOT, item)
        dst = os.path.join(ARCHIVE_DIR, item)

        if os.path.exists(src):
            try:
                shutil.move(src, dst)
                print(f"Moved: {item}")
            except Exception as e:
                print(f"Failed to move {item}: {e}")
        else:
            print(f"Skipped (Not found): {item}")


if __name__ == "__main__":
    purge()
