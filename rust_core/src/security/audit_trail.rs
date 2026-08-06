use serde::{Deserialize, Serialize};
use sha3::{Digest, Sha3_256};

/// Represents a single link in the Immutable Audit Chain.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub epoch: u64,
    pub domain: String,
    pub verdict: String,
    pub prev_hash: [u8; 32],
}

impl AuditEntry {
    #[must_use]
    pub fn calculate_hash(&self) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(&self.epoch.to_le_bytes());
        hasher.update(self.domain.as_bytes());
        hasher.update(self.verdict.as_bytes());
        hasher.update(&self.prev_hash);
        hasher.finalize().into()
    }
}

/// The Audit Trail Manager: Enforces Axiom 7 (Immutable Replication).
pub struct AuditTrail {
    pub last_hash: [u8; 32],
}

impl AuditTrail {
    #[must_use]
    pub fn new() -> Self {
        Self {
            last_hash: [0u8; 32],
        } // Genesis hash
    }

    /// Records a new verdict and returns the new chain hash.
    pub fn append(&mut self, epoch: u64, domain: String, verdict: String) -> [u8; 32] {
        let entry = AuditEntry {
            epoch,
            domain,
            verdict,
            prev_hash: self.last_hash,
        };

        let new_hash = entry.calculate_hash();
        println!(
            "📜 [AUDIT] Appending Entry: Domain={}, Verdict={}, NewHash=0x{:x}...",
            entry.domain, entry.verdict, new_hash[0]
        );

        self.last_hash = new_hash;
        new_hash
    }

    #[must_use]
    pub fn verify_chain(&self, entries: &[AuditEntry]) -> bool {
        let mut current_hash = [0u8; 32];
        for entry in entries {
            if entry.prev_hash != current_hash {
                return false;
            }
            current_hash = entry.calculate_hash();
        }
        current_hash == self.last_hash
    }
}
