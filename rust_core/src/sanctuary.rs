//! [Phase 20] Terminal Persistence (Digital Sanctuary)
//! ===================================================
//! Ensures civilizational continuity via immutable wide-area state anchors.

use borsh::{BorshDeserialize, BorshSerialize};
use serde::{Deserialize, Serialize};

/// An immutable anchor of the system's most critical axiomatic state.
#[derive(Debug, Clone, Serialize, Deserialize, BorshSerialize, BorshDeserialize)]
pub struct SanctuaryAnchor {
    pub epoch: u64,
    pub global_root: [u8; 32],
    pub ethics_commitment: [u8; 32],
}

#[derive(Debug, Clone, BorshSerialize, BorshDeserialize)]
pub struct SanctuaryGuard {
    pub last_anchor: Option<SanctuaryAnchor>,
}

impl SanctuaryGuard {
    #[must_use]
    pub fn new() -> Self {
        Self { last_anchor: None }
    }

    /// Seals the current state as a Sanctuary Anchor.
    pub fn seal_state(&mut self, epoch: u64, root: [u8; 32], ethics: [u8; 32]) -> SanctuaryAnchor {
        println!(
            "🏛️ [SANCTUARY] Sealing Era {} as terminal civilizational anchor.",
            epoch
        );
        let anchor = SanctuaryAnchor {
            epoch,
            global_root: root,
            ethics_commitment: ethics,
        };
        self.last_anchor = Some(anchor.clone());
        anchor
    }

    /// Verifies if a remote anchor is compatible with the local sanctuary.
    #[must_use]
    pub fn verify_sanctuary_integrity(local: &SanctuaryAnchor, remote: &SanctuaryAnchor) -> bool {
        // [Axiom 11] Truth is invariant across all sanctuaries.
        local.ethics_commitment == remote.ethics_commitment
    }
}
