//! rust_core/src/debug/metrics.rs
//! Prometheus-style metrics for AI governance

use lazy_static::lazy_static;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;

lazy_static! {
    /// Global registry for atomic counters
    static ref COUNTERS: Mutex<HashMap<String, AtomicU64>> = Mutex::new(HashMap::new());
}

/// Increment a global counter
pub fn increment_counter(name: &str) {
    let mut counters = COUNTERS.lock().unwrap();
    let counter = counters
        .entry(name.to_string())
        .or_insert_with(|| AtomicU64::new(0));
    counter.fetch_add(1, Ordering::SeqCst);
}

/// Get the current value of a counter
#[must_use]
pub fn get_counter(name: &str) -> u64 {
    let counters = COUNTERS.lock().unwrap();
    counters
        .get(name)
        .map(|c| c.load(Ordering::SeqCst))
        .unwrap_or(0)
}

/// Export all metrics as Prometheus-formatted string
#[must_use]
pub fn export_prometheus() -> String {
    let counters = COUNTERS.lock().unwrap();
    let mut output = String::new();

    for (name, value) in counters.iter() {
        let val = value.load(Ordering::SeqCst);
        output.push_str(&format!(
            "# HELP {}_total AI governance Counter for {}\n",
            name, name
        ));
        output.push_str(&format!("# TYPE {}_total counter\n", name));
        output.push_str(&format!("{}_total {}\n", name, val));
    }

    output
}

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
#[pyfunction]
pub fn get_metrics_snapshot() -> std::collections::HashMap<String, u64> {
    let counters = COUNTERS.lock().unwrap();
    let mut map = std::collections::HashMap::new();
    for (name, value) in counters.iter() {
        map.insert(name.clone(), value.load(Ordering::SeqCst));
    }
    map
}
