use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use pyo3::types::PyDict;

#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BridgeMetrics {
    pub bridge_latency_ms: f64,
    pub anchor_drift_seconds: i64,
    pub last_sync_timestamp: u64,
    pub eth_block_number: u64,
}

#[cfg(feature = "python")]
#[pymethods]
impl BridgeMetrics {
    #[new]
    pub fn new(latency: f64, drift: i64, ts: u64, block: u64) -> Self {
        Self {
            bridge_latency_ms: latency,
            anchor_drift_seconds: drift,
            last_sync_timestamp: ts,
            eth_block_number: block,
        }
    }

    pub fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let dict = PyDict::new(py);
        dict.set_item("bridge_latency_ms", self.bridge_latency_ms)?;
        dict.set_item("anchor_drift_seconds", self.anchor_drift_seconds)?;
        dict.set_item("last_sync_timestamp", self.last_sync_timestamp)?;
        dict.set_item("eth_block_number", self.eth_block_number)?;
        Ok(dict.unbind().into_any())
    }
}

#[cfg_attr(feature = "python", pyclass)]
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RustPatchEfficiencyReport {
    pub success_rate_by_source: HashMap<String, f64>,
    pub human_minutes_per_success: f64,
    pub rollback_rate: f64,
    pub average_minutes_to_fix_ci: Option<f64>,
    pub per_pattern_minutes: HashMap<String, f64>,
    pub sample_size: usize,
}

#[cfg(feature = "python")]
#[pymethods]
impl RustPatchEfficiencyReport {
    pub fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let dict = PyDict::new(py);

        let rates = PyDict::new(py);
        for (k, v) in &self.success_rate_by_source {
            rates.set_item(k, v)?;
        }
        dict.set_item("success_rate_by_source", rates)?;

        dict.set_item(
            "human_minutes_per_success",
            (self.human_minutes_per_success * 1000.0).round() / 1000.0,
        )?;
        dict.set_item(
            "rollback_rate",
            (self.rollback_rate * 1000.0).round() / 1000.0,
        )?;

        let ci_stats = PyDict::new(py);
        ci_stats.set_item("average_minutes", self.average_minutes_to_fix_ci)?;

        let pattern_mins = PyDict::new(py);
        for (k, v) in &self.per_pattern_minutes {
            pattern_mins.set_item(k, (v * 1000.0).round() / 1000.0)?;
        }
        ci_stats.set_item("per_pattern_minutes", pattern_mins)?;
        ci_stats.set_item("sample_size", self.per_pattern_minutes.len())?; // Approximate sample size for CI stats

        dict.set_item("time_to_fix_ci_error", ci_stats)?;
        dict.set_item("sample_size", self.sample_size)?;

        Ok(dict.unbind().into_any())
    }
}

#[must_use]
pub fn parse_ts(v: &Value) -> Option<DateTime<Utc>> {
    if let Some(s) = v.as_str() {
        return s.parse::<DateTime<Utc>>().ok();
    }
    if let Some(f) = v.as_f64() {
        return DateTime::from_timestamp(f as i64, 0);
    }
    None
}

#[must_use]
pub fn estimate_human_minutes(obj: &Value) -> f64 {
    let mut minutes = 0.0;
    let review_minutes = 5.0; // Default mirroring Python
    let manual_minutes = 6.0;

    let origin = obj
        .get("meta")
        .and_then(|m| m.get("origin").or_else(|| m.get("source")))
        .and_then(|o| o.as_str())
        .or_else(|| obj.get("origin").and_then(|o| o.as_str()))
        .unwrap_or("unknown");

    if origin == "manual" {
        minutes += manual_minutes;
    }

    let human_in_loop = obj
        .get("human_in_loop")
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
        || obj
            .get("requires_human")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

    if human_in_loop {
        minutes += review_minutes;
    }

    if let Some(meta) = obj.get("meta") {
        if meta
            .get("human_in_loop")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
            || meta
                .get("requires_human")
                .and_then(|v| v.as_bool())
                .unwrap_or(false)
        {
            minutes += review_minutes;
        }
    }

    if let Some(reason) = obj.get("reason").and_then(|r| r.as_str()) {
        let r_lower = reason.to_lowercase();
        if r_lower.contains("review") || r_lower.contains("human") || r_lower.contains("protected")
        {
            minutes += review_minutes;
        }
    }

    if let Some(detail) = obj.get("detail") {
        if detail
            .get("manual_review")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
        {
            minutes += review_minutes;
        } else if let Some(hm) = detail.get("human_minutes").and_then(|v| v.as_f64()) {
            minutes += hm;
        }
    }

    minutes
}

#[must_use]
pub fn is_ci_related(obj: &Value) -> bool {
    let reason = obj
        .get("reason")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_lowercase();
    let status = obj
        .get("status")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_lowercase();

    if reason.contains("ci")
        || reason.contains("test")
        || reason.contains("lint")
        || reason.contains("build")
        || reason.contains("flake8")
    {
        return true;
    }
    if status.contains("ci") || status.contains("test") {
        return true;
    }

    if let Some(detail) = obj.get("detail") {
        if detail
            .get("tests_failing")
            .and_then(|v| v.as_bool())
            .unwrap_or(false)
            || detail
                .get("ci_failure")
                .and_then(|v| v.as_bool())
                .unwrap_or(false)
        {
            return true;
        }
    }

    false
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn analyze_history(py: Python<'_>, lines: Vec<String>) -> PyResult<RustPatchEfficiencyReport> {
    py.detach(|| {
        let mut records: Vec<Value> = Vec::new();
        for line in lines {
            if let Ok(val) = serde_json::from_str::<Value>(&line) {
                if val.is_object() {
                    records.push(val);
                }
            }
        }

        let mut success_counts: HashMap<String, (usize, usize)> = HashMap::new();
        let mut human_minutes_total = 0.0;
        let mut total_success = 0;
        let mut total_rollback = 0;

        // CI Fix logic
        let mut records_with_ts: Vec<(Value, DateTime<Utc>)> = records
            .iter()
            .filter_map(|r| parse_ts(r.get("ts").unwrap_or(&Value::Null)).map(|ts| (r.clone(), ts)))
            .collect();
        records_with_ts.sort_by_key(|r| r.1);

        let mut first_failure: HashMap<String, DateTime<Utc>> = HashMap::new();
        let mut ci_durations: HashMap<String, Vec<f64>> = HashMap::new();

        for (obj, ts) in &records_with_ts {
            let status = obj
                .get("status")
                .and_then(|s| s.as_str())
                .unwrap_or("")
                .to_lowercase();
            let origin = obj
                .get("meta")
                .and_then(|m| m.get("origin").or_else(|| m.get("source")))
                .and_then(|o| o.as_str())
                .or_else(|| obj.get("origin").and_then(|o| o.as_str()))
                .unwrap_or("unknown")
                .to_string();

            let is_success = status == "applied"
                || status == "ok"
                || status == "manual_applied"
                || status == "llm_applied";
            let is_rollback = status == "rollback" || status == "rolled_back";

            let entry = success_counts.entry(origin).or_insert((0, 0));
            entry.1 += 1;
            if is_success {
                entry.0 += 1;
                total_success += 1;
            } else if is_rollback {
                total_rollback += 1;
            }

            human_minutes_total += estimate_human_minutes(obj);

            // CI logic
            if let Some(pattern) = obj
                .get("pattern")
                .and_then(|v| v.as_str())
                .or_else(|| obj.get("id").and_then(|v| v.as_str()))
            {
                let ci_related = is_ci_related(obj);
                if !is_success && ci_related {
                    if !first_failure.contains_key(pattern) {
                        first_failure.insert(pattern.to_string(), *ts);
                    }
                } else if is_success {
                    if let Some(start_ts) = first_failure.remove(pattern) {
                        let delta = (*ts - start_ts).num_seconds() as f64 / 60.0;
                        ci_durations
                            .entry(pattern.to_string())
                            .or_default()
                            .push(delta.max(0.0));
                    }
                }
            }
        }

        let mut success_rates = HashMap::new();
        for (origin, (success, total)) in success_counts {
            let rate = success as f64 / total as f64;
            success_rates.insert(origin, (rate * 1000.0).round() / 1000.0);
        }

        let mut per_pattern_minutes = HashMap::new();
        let mut all_deltas = Vec::new();
        for (pattern, deltas) in ci_durations {
            let sum: f64 = deltas.iter().sum();
            let count = deltas.len();
            per_pattern_minutes.insert(pattern, sum / count as f64);
            all_deltas.extend(deltas);
        }

        let avg_ci_fix = if !all_deltas.is_empty() {
            Some(all_deltas.iter().sum::<f64>() / all_deltas.len() as f64)
        } else {
            None
        };

        let rollback_rate = if total_success + total_rollback > 0 {
            total_rollback as f64 / (total_success + total_rollback) as f64
        } else {
            0.0
        };

        Ok(RustPatchEfficiencyReport {
            success_rate_by_source: success_rates,
            human_minutes_per_success: if total_success > 0 {
                human_minutes_total / total_success as f64
            } else {
                0.0
            },
            rollback_rate,
            average_minutes_to_fix_ci: avg_ci_fix,
            per_pattern_minutes,
            sample_size: records.len(),
        })
    })
}
