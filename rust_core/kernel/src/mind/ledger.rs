use core::sync::atomic::{AtomicU32, Ordering};

pub struct KernelLedger {
    // We store as fixed-point (Credits * 100) since we don't have atomic f64
    balance_cents: AtomicU32,
    epoch: AtomicU32,
}

impl KernelLedger {
    pub const fn new() -> Self {
        KernelLedger {
            balance_cents: AtomicU32::new(0),
            epoch: AtomicU32::new(0),
        }
    }

    pub fn update(&self, balance: f64, epoch: u64) {
        let cents = (balance * 100.0) as u32;
        self.balance_cents.store(cents, Ordering::Relaxed);
        self.epoch.store(epoch as u32, Ordering::Relaxed);
    }

    pub fn get_balance(&self) -> f64 {
        let cents = self.balance_cents.load(Ordering::Relaxed);
        (cents as f64) / 100.0
    }

    pub fn can_afford(&self, amount: f64) -> bool {
        self.get_balance() >= amount
    }
}

pub static LEDGER: KernelLedger = KernelLedger::new();
