//! rust_core/src/compliance/report.rs
//! Generic Compliance Report Generator.
//!
//! Generates standardized compliance reports for various frameworks.

use serde::{Deserialize, Serialize};

#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString};
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

// ============================================================================
// AUDIT TRAIL
// ============================================================================

/// Governance decision audit entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    /// Entry ID
    pub id: String,
    /// Timestamp (ISO 8601)
    pub timestamp: String,
    /// Event type
    pub event_type: EventType,
    /// Actor (system or user ID)
    pub actor: String,
    /// Action taken
    pub action: String,
    /// Outcome
    pub outcome: Outcome,
    /// Context/reason
    pub context: Option<String>,
    /// Related evidence hash
    pub evidence_hash: Option<String>,
}

/// Event types for audit trail
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventType {
    /// Governance decision made
    GovernanceDecision,
    /// Safety check performed
    SafetyCheck,
    /// Access control event
    AccessControl,
    /// Configuration change
    ConfigChange,
    /// Model inference
    Inference,
    /// Human oversight action
    HumanOversight,
    /// System alert
    Alert,
    /// Incident response
    IncidentResponse,
}

/// Outcome of an action
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Outcome {
    Success,
    Failure,
    Blocked,
    Pending,
    Escalated,
}

// ============================================================================
// SAFETY METRICS
// ============================================================================

/// Safety metrics snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyMetrics {
    /// Measurement timestamp
    pub timestamp: String,
    /// Total decisions made
    pub total_decisions: u64,
    /// Decisions blocked by safety checks
    pub blocked_decisions: u64,
    /// False positive rate (estimated)
    pub false_positive_rate: Option<f64>,
    /// Average response time (ms)
    pub avg_response_time_ms: Option<f64>,
    /// Current risk score (0.0 - 1.0)
    pub risk_score: f64,
    /// Safety threshold
    pub safety_threshold: f64,
    /// Threshold breaches in period
    pub threshold_breaches: u64,
}

impl SafetyMetrics {
    /// Calculate block rate
    #[must_use]
    pub fn block_rate(&self) -> f64 {
        if self.total_decisions == 0 {
            return 0.0;
        }
        self.blocked_decisions as f64 / self.total_decisions as f64
    }

    /// Check if system is within safety bounds
    #[must_use]
    pub fn is_safe(&self) -> bool {
        self.risk_score <= self.safety_threshold
    }
}

// ============================================================================
// INCIDENT RECORD
// ============================================================================

/// Incident record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IncidentRecord {
    /// Incident ID
    pub id: String,
    /// Detection timestamp
    pub detected_at: String,
    /// Resolution timestamp (if resolved)
    pub resolved_at: Option<String>,
    /// Severity level
    pub severity: Severity,
    /// Incident type
    pub incident_type: IncidentType,
    /// Description
    pub description: String,
    /// Impact assessment
    pub impact: String,
    /// Root cause (if determined)
    pub root_cause: Option<String>,
    /// Remediation actions taken
    pub remediation: Vec<String>,
    /// Prevention measures implemented
    pub prevention: Vec<String>,
    /// Status
    pub status: IncidentStatus,
}

/// Incident severity
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Severity {
    Low,
    Medium,
    High,
    Critical,
}

/// Incident type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IncidentType {
    /// Safety violation
    SafetyViolation,
    /// Security breach
    SecurityBreach,
    /// Data integrity issue
    DataIntegrity,
    /// Performance degradation
    Performance,
    /// Availability issue
    Availability,
    /// Compliance violation
    ComplianceViolation,
    /// Other
    Other,
}

/// Incident status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IncidentStatus {
    Open,
    Investigating,
    Mitigating,
    Resolved,
    Closed,
}

// ============================================================================
// COMPLIANCE REPORT BUILDER
// ============================================================================

/// Generic compliance report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceReport {
    /// Report ID
    pub report_id: String,
    /// Report title
    pub title: String,
    /// Generation timestamp
    pub generated_at: String,
    /// Reporting period start
    pub period_start: String,
    /// Reporting period end
    pub period_end: String,
    /// Framework (e.g., "EU AI Act", "SOC 2", "ISO 27001")
    pub framework: String,
    /// Report version
    pub version: String,
    /// Executive summary
    pub executive_summary: String,
    /// Audit entries for the period
    pub audit_trail: Vec<AuditEntry>,
    /// Safety metrics
    pub safety_metrics: Option<SafetyMetrics>,
    /// Incident records
    pub incidents: Vec<IncidentRecord>,
    /// Compliance score (0-100)
    pub compliance_score: u32,
    /// Key findings
    pub findings: Vec<Finding>,
    /// Recommendations
    pub recommendations: Vec<String>,
}

/// Compliance finding
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    /// Finding ID
    pub id: String,
    /// Finding type
    pub finding_type: FindingType,
    /// Severity
    pub severity: Severity,
    /// Description
    pub description: String,
    /// Evidence references
    pub evidence: Vec<String>,
    /// Remediation status
    pub remediation_status: RemediationStatus,
}

/// Finding type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FindingType {
    NonConformity,
    Observation,
    Opportunity,
    Strength,
}

/// Remediation status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RemediationStatus {
    NotStarted,
    InProgress,
    Completed,
    Verified,
    NotApplicable,
}

/// Report builder
#[derive(Debug, Default)]
pub struct ReportBuilder {
    title: Option<String>,
    framework: Option<String>,
    period_start: Option<String>,
    period_end: Option<String>,
    audit_trail: Vec<AuditEntry>,
    safety_metrics: Option<SafetyMetrics>,
    incidents: Vec<IncidentRecord>,
    findings: Vec<Finding>,
    recommendations: Vec<String>,
}

impl ReportBuilder {
    /// Create a new report builder
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Set report title
    pub fn title(mut self, title: impl Into<String>) -> Self {
        self.title = Some(title.into());
        self
    }

    /// Set framework
    pub fn framework(mut self, framework: impl Into<String>) -> Self {
        self.framework = Some(framework.into());
        self
    }

    /// Set reporting period
    pub fn period(mut self, start: impl Into<String>, end: impl Into<String>) -> Self {
        self.period_start = Some(start.into());
        self.period_end = Some(end.into());
        self
    }

    /// Add audit entry
    #[must_use]
    pub fn add_audit_entry(mut self, entry: AuditEntry) -> Self {
        self.audit_trail.push(entry);
        self
    }

    /// Add multiple audit entries
    #[must_use]
    pub fn with_audit_trail(mut self, entries: Vec<AuditEntry>) -> Self {
        self.audit_trail = entries;
        self
    }

    /// Set safety metrics
    #[must_use]
    pub fn safety_metrics(mut self, metrics: SafetyMetrics) -> Self {
        self.safety_metrics = Some(metrics);
        self
    }

    /// Add incident
    #[must_use]
    pub fn add_incident(mut self, incident: IncidentRecord) -> Self {
        self.incidents.push(incident);
        self
    }

    /// Add finding
    #[must_use]
    pub fn add_finding(mut self, finding: Finding) -> Self {
        self.findings.push(finding);
        self
    }

    /// Add recommendation
    pub fn add_recommendation(mut self, rec: impl Into<String>) -> Self {
        self.recommendations.push(rec.into());
        self
    }

    /// Build the report
    pub fn build(self) -> Result<ComplianceReport, String> {
        let title = self.title.ok_or("Title is required")?;
        let framework = self.framework.ok_or("Framework is required")?;
        let period_start = self.period_start.ok_or("Period start is required")?;
        let period_end = self.period_end.ok_or("Period end is required")?;

        // Calculate compliance score based on findings
        let compliance_score = calculate_compliance_score(&self.findings, &self.incidents);

        // Generate executive summary
        let executive_summary = generate_executive_summary(
            &self.findings,
            &self.incidents,
            self.safety_metrics.as_ref(),
            compliance_score,
        );

        Ok(ComplianceReport {
            report_id: generate_report_id(),
            title,
            generated_at: current_timestamp(),
            period_start,
            period_end,
            framework,
            version: "1.0".to_string(),
            executive_summary,
            audit_trail: self.audit_trail,
            safety_metrics: self.safety_metrics,
            incidents: self.incidents,
            compliance_score,
            findings: self.findings,
            recommendations: self.recommendations,
        })
    }
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

fn generate_report_id() -> String {
    use sha3::{Digest, Sha3_256};
    let mut hasher = Sha3_256::new();
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    hasher.update(timestamp.to_le_bytes());
    let hash = hasher.finalize();
    format!("RPT-{}", hex::encode(&hash[..6]).to_uppercase())
}

fn current_timestamp() -> String {
    use std::time::SystemTime;
    let now = SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs();
    let days = secs / 86400;
    let remaining = secs % 86400;
    let hours = remaining / 3600;
    let minutes = (remaining % 3600) / 60;
    let seconds = remaining % 60;
    let years = 1970 + (days / 365);
    let day_of_year = days % 365;
    let month = (day_of_year / 30) + 1;
    let day = (day_of_year % 30) + 1;
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        years, month, day, hours, minutes, seconds
    )
}

fn calculate_compliance_score(findings: &[Finding], incidents: &[IncidentRecord]) -> u32 {
    let mut score: i32 = 100;

    // Deduct for findings
    for finding in findings {
        if finding.remediation_status == RemediationStatus::NotStarted
            || finding.remediation_status == RemediationStatus::InProgress
        {
            match finding.severity {
                Severity::Critical => score -= 25,
                Severity::High => score -= 15,
                Severity::Medium => score -= 10,
                Severity::Low => score -= 5,
            }
        }
    }

    // Deduct for open incidents
    for incident in incidents {
        if incident.status != IncidentStatus::Closed && incident.status != IncidentStatus::Resolved
        {
            match incident.severity {
                Severity::Critical => score -= 20,
                Severity::High => score -= 10,
                Severity::Medium => score -= 5,
                Severity::Low => score -= 2,
            }
        }
    }

    score.max(0) as u32
}

fn generate_executive_summary(
    findings: &[Finding],
    incidents: &[IncidentRecord],
    safety_metrics: Option<&SafetyMetrics>,
    score: u32,
) -> String {
    let critical_findings = findings
        .iter()
        .filter(|f| f.severity == Severity::Critical)
        .count();
    let open_incidents = incidents
        .iter()
        .filter(|i| i.status != IncidentStatus::Closed)
        .count();

    let status = if score >= 90 {
        "excellent"
    } else if score >= 70 {
        "good"
    } else if score >= 50 {
        "needs improvement"
    } else {
        "critical attention required"
    };

    let safety_note = if let Some(metrics) = safety_metrics {
        if metrics.is_safe() {
            " Safety metrics are within acceptable bounds."
        } else {
            " ALERT: Safety metrics exceed threshold."
        }
    } else {
        ""
    };

    format!(
        "Compliance score: {}% ({}). {} critical findings, {} open incidents.{}",
        score, status, critical_findings, open_incidents, safety_note
    )
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_safety_metrics_calculations() {
        let metrics = SafetyMetrics {
            timestamp: "2024-01-01T00:00:00Z".to_string(),
            total_decisions: 1000,
            blocked_decisions: 50,
            false_positive_rate: Some(0.01),
            avg_response_time_ms: Some(15.5),
            risk_score: 0.3,
            safety_threshold: 0.5,
            threshold_breaches: 0,
        };

        assert!((metrics.block_rate() - 0.05).abs() < 0.001);
        assert!(metrics.is_safe());
    }

    #[test]
    fn test_safety_metrics_unsafe() {
        let metrics = SafetyMetrics {
            timestamp: "2024-01-01T00:00:00Z".to_string(),
            total_decisions: 100,
            blocked_decisions: 10,
            false_positive_rate: None,
            avg_response_time_ms: None,
            risk_score: 0.8,
            safety_threshold: 0.5,
            threshold_breaches: 5,
        };

        assert!(!metrics.is_safe());
    }

    #[test]
    fn test_compliance_score_calculation() {
        let findings = vec![
            Finding {
                id: "F1".to_string(),
                finding_type: FindingType::NonConformity,
                severity: Severity::High,
                description: "Test".to_string(),
                evidence: vec![],
                remediation_status: RemediationStatus::NotStarted,
            },
            Finding {
                id: "F2".to_string(),
                finding_type: FindingType::Observation,
                severity: Severity::Low,
                description: "Test".to_string(),
                evidence: vec![],
                remediation_status: RemediationStatus::Completed,
            },
        ];

        let incidents = vec![];

        let score = calculate_compliance_score(&findings, &incidents);
        assert_eq!(score, 85); // 100 - 15 (high severity finding)
    }

    #[test]
    fn test_report_builder() {
        let report = ReportBuilder::new()
            .title("Q1 2024 Compliance Report")
            .framework("EU AI Act")
            .period("2024-01-01", "2024-03-31")
            .add_recommendation("Implement additional logging")
            .build();

        assert!(report.is_ok());
        let report = report.unwrap();
        assert_eq!(report.title, "Q1 2024 Compliance Report");
        assert_eq!(report.framework, "EU AI Act");
        assert_eq!(report.compliance_score, 100); // No findings
    }

    #[test]
    fn test_report_builder_missing_required() {
        let report = ReportBuilder::new().title("Test").build();

        assert!(report.is_err());
        assert!(report.unwrap_err().contains("Framework"));
    }

    #[test]
    fn test_audit_entry() {
        let entry = AuditEntry {
            id: "AE001".to_string(),
            timestamp: "2024-01-15T10:30:00Z".to_string(),
            event_type: EventType::GovernanceDecision,
            actor: "system".to_string(),
            action: "Block harmful content".to_string(),
            outcome: Outcome::Success,
            context: Some("Content violated policy".to_string()),
            evidence_hash: Some("abc123".to_string()),
        };

        assert_eq!(entry.event_type, EventType::GovernanceDecision);
        assert_eq!(entry.outcome, Outcome::Success);
    }

    #[test]
    fn test_incident_record() {
        let incident = IncidentRecord {
            id: "INC001".to_string(),
            detected_at: "2024-01-15T10:00:00Z".to_string(),
            resolved_at: Some("2024-01-15T12:00:00Z".to_string()),
            severity: Severity::High,
            incident_type: IncidentType::SafetyViolation,
            description: "Safety threshold exceeded".to_string(),
            impact: "Service degraded".to_string(),
            root_cause: Some("Configuration error".to_string()),
            remediation: vec!["Reverted configuration".to_string()],
            prevention: vec!["Added validation".to_string()],
            status: IncidentStatus::Resolved,
        };

        assert_eq!(incident.severity, Severity::High);
        assert_eq!(incident.status, IncidentStatus::Resolved);
    }
}
