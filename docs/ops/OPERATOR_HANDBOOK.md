# WarmLogic Operator's Handbook

> **Version**: 
> **Classification**: SOVEREIGN ONLY  
> **Purpose**: Disaster Recovery, Key Rotation, Backup, and Integrity Verification.  
> **Last Updated**: 2026-02-05
 
 ## 1. Key Rotation (Kinetic Identity)
 If your Hardware Identity is compromised or you are migrating to new silicon.
 
 ### Procedure
 1. **Export Old State**:
    ```bash
    python3 scripts/ops/export_ledger_state.py --out backup.bin
    ```
 2. **Nuke & Pave**:
    ```bash
    rm -rf warm_logic_store/
    ```
 3. **Re-Bind**:
    Start the kernel on the *new* hardware.
    ```bash
    # The system will detect new CPU UUID and generate a new Kinetic ID.
    python3 scripts/ops/ignite_kernel.py
    ```
 4. **Import Legacy State**:
    ```bash
    python3 scripts/ops/import_ledger_state.py --in backup.bin --sign-with-new-key
    ```
    *Note: This creates a "Handover Transaction" linking the old Identity to the new one.*
 
 ---
 
 ## 2. Data Corruption Recovery
 If `warm_logic_store` (Sled/SQLite) becomes corrupted due to power failure.
 
 ### Procedure
 1. **Verify Checksums**:
    ```bash
    python3 scripts/ops/verify_integrity.py
    ```
 2. **Force Replay**:
    If the Head State is corrupt, replay from the Genesis Block.
    ```bash
    python3 scripts/ops/replay_from_genesis.py --verify-all-signatures
    ```
 
 ---
 
 ## 3. Binary Verification
 Ensure your `warm_logic_rs` binary matches the source code.
 
 ### Procedure
 1. **Calculate Source Hash**:
    ```bash
    find warm_logic_rs/src -type f -exec sha256sum {} + | sort | sha256sum
    ```
 2. **Rebuild Deterministically**:
    ```bash
    export SOURCE_DATE_EPOCH=1735689600  # 2025-01-01
    maturin build --release --strip
    ```
 3. **Compare**:
    The hash of the new `.so` must match the running `.so`.
 
 ---
 *Keep this manual offline.*
