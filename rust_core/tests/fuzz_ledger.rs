use proptest::prelude::*;
use std::env;
use warm_logic_rs::ledger::{RustReplicatedLedger, Transaction};

#[cfg(test)]
proptest! {
    // Generate valid-looking transactions and ensure the ledger doesn't panic
    #[test]
    fn test_ledger_transaction_fuzz(
        source in "[a-zA-Z0-9]{1,32}",
        target in "[a-zA-Z0-9]{1,32}",
        amount in 1u64..1_000_000_000,
        max_fee in 0u64..1000,
        priority_fee in 0u64..1000,
        timestamp in 1700000000.0f64..2000000000.0f64
    ) {
        let tmp_dir = env::temp_dir().join(format!("fuzz_ledger_{}", uuid::Uuid::new_v4()));
        let _ = std::fs::remove_dir_all(&tmp_dir);

        let mut ledger = RustReplicatedLedger::new(tmp_dir.to_str().unwrap())
            .expect("Failed to create test ledger");

        // Ensure some initial balance so we don't always fail balance checks
        // We use a "backdoor" or just rely on the genesis mechanism if we had one exposed easily
        // For fuzzing, we just care about "NO PANIC", not "VALID TRANSACTION".

        let tx = Transaction {
            tx_id: "FUZZ-TX".to_string(),
            source,
            target,
            amount,
            signature: "FUZZ-SIG".to_string(),
            timestamp,
            max_fee,
            priority_fee
        };

        // This should NOT panic, even if it rejects the transaction
        ledger.submit_transaction(tx);

        // Cleanup
        let _ = std::fs::remove_dir_all(&tmp_dir);
    }
}
