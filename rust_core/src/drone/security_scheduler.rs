//! security_scheduler.rs
//! Hybrid Security Scheduling for RISC-V Reality Gap.
//! Strategy 1: "Amortized Signing" — SHA3 MAC per-tick, PQC signature per-epoch.
//! Strategy 2: "Async Signer" — Channel-based non-blocking PQC on separate core.

use sha3::{Digest, Sha3_256};

#[cfg(not(feature = "std"))]
use alloc::{string::String, vec::Vec};

/// Security level determines the signing strategy.
/// FullPQC: Every tick gets a PQC signature (M4 Pro class hardware).
/// AmortizedPQC: SHA3 hash chain per-tick, PQC signature every N ticks (RISC-V).
/// HashOnly: Only SHA3 MAC, no PQC at all (extreme resource constraint).
#[derive(Debug, Clone, Copy, PartialEq)]
#[non_exhaustive]
pub enum SecurityLevel {
    FullPQC,
    AmortizedPQC,
    HashOnly,
}

/// A single tick's integrity record in the hash chain.
#[derive(Debug, Clone)]
pub struct TickRecord {
    pub tick_id: u64,
    pub hash: [u8; 32],
}

/// SecurityScheduler: Amortized PQC signing with SHA3 hash chain.
///
/// Every tick: hash(tick_id || sensor_data || prev_hash) → O(1)µs on RISC-V.
/// Every pqc_interval ticks: sign(merkle_root(hash_chain)) → ~9ms on RISC-V (amortized to 22µs/tick).
#[derive(Debug, Clone)]
pub struct SecurityScheduler {
    pub tick_count: u64,
    pub pqc_interval: u64,
    pub hash_chain: Vec<TickRecord>,
    pub prev_hash: [u8; 32],
    pub last_pqc_signature: Option<String>,
    pub last_merkle_root: Option<[u8; 32]>,
    pub level: SecurityLevel,
}

impl SecurityScheduler {
    #[must_use]
    pub fn new(level: SecurityLevel, pqc_interval: u64) -> Self {
        SecurityScheduler {
            tick_count: 0,
            pqc_interval,
            hash_chain: Vec::with_capacity(pqc_interval as usize),
            prev_hash: [0u8; 32],
            last_pqc_signature: None,
            last_merkle_root: None,
            level,
        }
    }

    /// Called every control tick (400Hz). Returns true if PQC epoch boundary was reached.
    pub fn tick(&mut self, sensor_data: &[u8]) -> bool {
        self.tick_count += 1;

        match self.level {
            SecurityLevel::HashOnly | SecurityLevel::AmortizedPQC => {
                // SHA3-256 hash chain: H(tick_id || sensor_data || prev_hash)
                let mut hasher = Sha3_256::new();
                hasher.update(self.tick_count.to_le_bytes());
                hasher.update(sensor_data);
                hasher.update(self.prev_hash);
                let result = hasher.finalize();

                let mut hash = [0u8; 32];
                hash.copy_from_slice(&result);

                self.hash_chain.push(TickRecord {
                    tick_id: self.tick_count,
                    hash,
                });
                self.prev_hash = hash;

                // Check if we've reached a PQC epoch boundary
                if self.level == SecurityLevel::AmortizedPQC
                    && self.tick_count % self.pqc_interval == 0
                {
                    let root = self.compute_merkle_root();
                    self.last_merkle_root = Some(root);
                    self.hash_chain.clear();
                    return true; // Signal: caller should invoke PQC sign on `root`
                }
                false
            }
            SecurityLevel::FullPQC => {
                // In FullPQC mode, every tick triggers PQC. Hash chain is optional.
                let mut hasher = Sha3_256::new();
                hasher.update(self.tick_count.to_le_bytes());
                hasher.update(sensor_data);
                let result = hasher.finalize();
                let mut hash = [0u8; 32];
                hash.copy_from_slice(&result);
                self.prev_hash = hash;
                true
            }
        }
    }

    /// Computes the Merkle Root of the accumulated hash chain.
    /// For N hashes, this is O(N) with O(log N) tree depth.
    #[must_use]
    pub fn compute_merkle_root(&self) -> [u8; 32] {
        if self.hash_chain.is_empty() {
            return [0u8; 32];
        }
        if self.hash_chain.len() == 1 {
            return self.hash_chain[0].hash;
        }

        let mut layer: Vec<[u8; 32]> = self.hash_chain.iter().map(|r| r.hash).collect();

        while layer.len() > 1 {
            let mut next_layer = Vec::with_capacity(layer.len().div_ceil(2));
            for chunk in layer.chunks(2) {
                let mut hasher = Sha3_256::new();
                hasher.update(chunk[0]);
                if chunk.len() > 1 {
                    hasher.update(chunk[1]);
                } else {
                    hasher.update(chunk[0]); // Duplicate odd leaf
                }
                let result = hasher.finalize();
                let mut hash = [0u8; 32];
                hash.copy_from_slice(&result);
                next_layer.push(hash);
            }
            layer = next_layer;
        }

        layer[0]
    }

    /// Store the PQC signature for the last epoch's Merkle root.
    pub fn set_pqc_signature(&mut self, sig: String) {
        self.last_pqc_signature = Some(sig);
    }

    /// Get the data that needs to be PQC-signed (Merkle root as hex).
    pub fn get_signing_payload(&self) -> Option<String> {
        self.last_merkle_root.map(hex::encode)
    }
}

// ============================================================
// Strategy 2: Async Signer (Dual-Core Separation) - Requires std
// ============================================================
#[cfg(feature = "std")]
mod strategy_async {
    use std::sync::{mpsc, Arc, Mutex};
    use std::thread;

    /// Request sent from the control core to the crypto core.
    #[derive(Debug)]
    pub struct SignRequest {
        pub epoch: u64,
        pub payload: String, // Merkle root hex
    }

    /// Result returned from the crypto core after PQC signing.
    #[derive(Debug)]
    pub struct SignResult {
        pub epoch: u64,
        pub signature: String,
    }

    /// AsyncPQCSigner: Non-blocking PQC signing via channel.
    /// Control core sends SignRequests, crypto core processes them in background.
    #[derive(Clone)]
    pub struct AsyncPQCSigner {
        sign_tx: mpsc::Sender<SignRequest>,
        result_rx: Arc<Mutex<mpsc::Receiver<SignResult>>>,
    }

    impl std::fmt::Debug for AsyncPQCSigner {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            f.debug_struct("AsyncPQCSigner").finish()
        }
    }

    impl AsyncPQCSigner {
        /// Spawns a dedicated signing thread (models the "Big Core" on Milk-V Duo S).
        #[must_use]
        pub fn spawn(private_key: String) -> Self {
            let (sign_tx, sign_rx) = mpsc::channel::<SignRequest>();
            let (result_tx, result_rx) = mpsc::channel::<SignResult>();

            thread::spawn(move || {
                for req in sign_rx {
                    // Perform heavy PQC signing on the crypto core
                    match crate::crypto::MLDSA::sign_raw(&private_key, &req.payload) {
                        Ok(sig) => {
                            let _ = result_tx.send(SignResult {
                                epoch: req.epoch,
                                signature: sig,
                            });
                        }
                        Err(_) => {
                            // Signing failed — log but don't crash the control loop
                            let _ = result_tx.send(SignResult {
                                epoch: req.epoch,
                                signature: String::new(),
                            });
                        }
                    }
                }
            });

            AsyncPQCSigner {
                sign_tx,
                result_rx: Arc::new(Mutex::new(result_rx)),
            }
        }

        /// Non-blocking: submit a signing request. Returns immediately.
        #[must_use]
        pub fn request_sign(&self, epoch: u64, payload: String) -> bool {
            self.sign_tx.send(SignRequest { epoch, payload }).is_ok()
        }

        /// Non-blocking: poll for a completed signature.
        #[must_use]
        pub fn poll_result(&self) -> Option<SignResult> {
            if let Ok(rx) = self.result_rx.try_lock() {
                let res: Result<SignResult, mpsc::TryRecvError> = rx.try_recv();
                res.ok()
            } else {
                None
            }
        }
    }
}

#[cfg(feature = "std")]
pub use strategy_async::*;

#[cfg(feature = "std")]
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hash_chain_integrity() {
        let mut sched = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 4);

        // Tick 4 times — should trigger PQC epoch on tick 4
        assert!(!sched.tick(b"sensor_data_1"));
        assert!(!sched.tick(b"sensor_data_2"));
        assert!(!sched.tick(b"sensor_data_3"));
        assert!(sched.tick(b"sensor_data_4")); // Epoch boundary!

        // Merkle root should be set
        assert!(sched.last_merkle_root.is_some());
        let root = sched.last_merkle_root.unwrap();
        assert_ne!(root, [0u8; 32]);

        // Hash chain should be cleared after epoch
        assert!(sched.hash_chain.is_empty());
    }

    #[test]
    fn test_hash_chain_determinism() {
        let mut s1 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 4);
        let mut s2 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 4);

        for i in 0..4 {
            let data = format!("data_{}", i);
            s1.tick(data.as_bytes());
            s2.tick(data.as_bytes());
        }

        assert_eq!(s1.last_merkle_root, s2.last_merkle_root);
    }

    #[test]
    fn test_hash_chain_tamper_detection() {
        let mut legit = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 4);
        let mut tampered = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 4);

        legit.tick(b"sensor_1");
        tampered.tick(b"sensor_1");
        legit.tick(b"sensor_2");
        tampered.tick(b"TAMPERED!"); // Injected malicious data
        legit.tick(b"sensor_3");
        tampered.tick(b"sensor_3");
        legit.tick(b"sensor_4");
        tampered.tick(b"sensor_4");

        // Merkle roots MUST differ — tamper detected
        assert_ne!(legit.last_merkle_root, tampered.last_merkle_root);
    }

    #[test]
    fn test_hash_only_mode_never_triggers_pqc() {
        let mut sched = SecurityScheduler::new(SecurityLevel::HashOnly, 4);
        for _ in 0..100 {
            assert!(!sched.tick(b"data"));
        }
        assert!(sched.last_merkle_root.is_none());
    }

    #[test]
    fn test_full_pqc_mode_always_triggers() {
        let mut sched = SecurityScheduler::new(SecurityLevel::FullPQC, 400);
        for _ in 0..10 {
            assert!(sched.tick(b"data"));
        }
    }

    #[test]
    fn test_async_signer_roundtrip() {
        // Generate a real keypair for the async signer
        let (pk, sk) = crate::crypto::PQCKeypair::generate_raw();
        let signer = AsyncPQCSigner::spawn(sk);

        let payload = "deadbeef".to_string();
        assert!(signer.request_sign(1, payload.clone()));

        // Wait for the crypto core to process (give it time)
        std::thread::sleep(std::time::Duration::from_millis(500));

        let result = signer.poll_result();
        assert!(result.is_some());
        let r = result.unwrap();
        assert_eq!(r.epoch, 1);
        assert!(!r.signature.is_empty());

        // Verify the signature
        assert!(crate::crypto::MLDSA::verify_raw(
            &pk,
            "deadbeef",
            &r.signature
        ));
    }

    proptest::proptest! {
        #[test]
        fn test_merkle_root_consistency_prop(hashes in proptest::collection::vec(proptest::array::uniform32(0u8..), 1..100)) {
            let mut sched = SecurityScheduler::new(SecurityLevel::AmortizedPQC, hashes.len() as u64);
            for h in &hashes {
                sched.hash_chain.push(TickRecord { tick_id: 0, hash: *h });
            }
            let root1 = sched.compute_merkle_root();
            let root2 = sched.compute_merkle_root();
            assert_eq!(root1, root2);
        }

        #[test]
        fn test_hash_chain_immutability_prop(
            data in proptest::collection::vec(proptest::collection::vec(0u8.., 1..64), 1..20),
            tamper_idx in 0..20usize,
            tamper_byte_idx in 0..64usize,
            tamper_val in 0u8..
        ) {
            let num_ticks = data.len();
            let mut s1 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, num_ticks as u64);
            let mut s2 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, num_ticks as u64);

            for (i, d) in data.iter().enumerate() {
                s1.tick(d);

                if i == tamper_idx % num_ticks {
                    let mut d2 = d.clone();
                    let byte_idx = tamper_byte_idx % d2.len();
                    // Ensure we actually change the value
                    if d2[byte_idx] == tamper_val {
                        d2[byte_idx] = tamper_val.wrapping_add(1);
                    } else {
                        d2[byte_idx] = tamper_val;
                    }
                    s2.tick(&d2);
                } else {
                    s2.tick(d);
                }
            }

            // Roots must differ if any input changed
            assert_ne!(s1.last_merkle_root, s2.last_merkle_root);
        }

        #[test]
        fn test_merkle_order_dependency_prop(hashes in proptest::collection::vec(proptest::array::uniform32(0u8..), 2..20)) {
            let mut s1 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, hashes.len() as u64);
            let mut s2 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, hashes.len() as u64);

            for h in &hashes {
                s1.hash_chain.push(TickRecord { tick_id: 0, hash: *h });
            }

            // Reverse the order
            let mut hashes_rev = hashes.clone();
            hashes_rev.reverse();
            for h in &hashes_rev {
                s2.hash_chain.push(TickRecord { tick_id: 0, hash: *h });
            }

            let root1 = s1.compute_merkle_root();
            let root2 = s2.compute_merkle_root();

            // Roots should differ unless all hashes are identical
            if hashes.iter().all(|h| *h == hashes[0]) {
                 assert_eq!(root1, root2);
            } else {
                 assert_ne!(root1, root2);
            }
        }

        #[test]
        fn test_tick_id_inclusion_prop(data in proptest::collection::vec(0u8.., 1..32)) {
            let mut s1 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 10);
            let mut s2 = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 10);

            s1.tick(&data);
            s2.tick(&data);
            assert_eq!(s1.prev_hash, s2.prev_hash);

            // Manually desync tick count and verify hashes diverge
            s2.tick_count = 999;
            s1.tick(&data);
            s2.tick(&data);
            assert_ne!(s1.prev_hash, s2.prev_hash);
        }

        #[test]
        fn test_hash_chain_linkage_prop(
            ticks in proptest::collection::vec(proptest::collection::vec(0u8.., 1..32), 2..10)
        ) {
            let mut sched = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 100);
            let mut hashes = Vec::new();

            for d in &ticks {
                sched.tick(d);
                hashes.push(sched.prev_hash);
            }

            // Verify each hash depends on the previous one
            for i in 1..hashes.len() {
                // If we changed any previous data, all subsequent hashes must change
                let mut attacker_sched = SecurityScheduler::new(SecurityLevel::AmortizedPQC, 100);
                for (j, d) in ticks.iter().enumerate() {
                    if j == 0 {
                        let mut bad_data = d.clone();
                        bad_data.push(0); // Change first tick
                        attacker_sched.tick(&bad_data);
                    } else {
                        attacker_sched.tick(d);
                    }
                    if j >= i {
                        assert_ne!(attacker_sched.prev_hash, hashes[j]);
                    }
                }
            }
        }
    }
}
