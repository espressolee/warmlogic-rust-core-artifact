//! rust_core/src/compliance/eu_ai_act.rs
//! EU AI Act Compliance Framework.
//!
//! Implements requirements from EU Regulation 2024/1689 (AI Act).
//! Reference: <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>

use serde::{Deserialize, Serialize};

#[cfg(not(feature = "std"))]
use alloc::string::{String, ToString};
#[cfg(not(feature = "std"))]
use alloc::vec::Vec;

// ============================================================================
// RISK CLASSIFICATION (Article 6)
// ============================================================================

/// EU AI Act Risk Classification
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskLevel {
    /// Minimal/No risk - general purpose AI, spam filters, etc.
    Minimal,
    /// Limited risk - chatbots, emotion recognition systems
    Limited,
    /// High risk - safety components, critical infrastructure, law enforcement
    High,
    /// Unacceptable risk - prohibited practices (social scoring, etc.)
    Unacceptable,
}

impl RiskLevel {
    /// Check if this risk level requires conformity assessment
    #[must_use]
    pub fn requires_conformity_assessment(&self) -> bool {
        matches!(self, RiskLevel::High)
    }

    /// Check if this risk level is prohibited
    #[must_use]
    pub fn is_prohibited(&self) -> bool {
        matches!(self, RiskLevel::Unacceptable)
    }

    /// Get human-readable description
    #[must_use]
    pub fn description(&self) -> &'static str {
        match self {
            RiskLevel::Minimal => "Minimal risk - no specific regulatory requirements",
            RiskLevel::Limited => "Limited risk - transparency obligations apply",
            RiskLevel::High => "High risk - full compliance requirements apply",
            RiskLevel::Unacceptable => "Unacceptable risk - prohibited under EU AI Act",
        }
    }
}

// ============================================================================
// HIGH-RISK AI CATEGORIES (Annex III)
// ============================================================================

/// High-Risk AI System Categories per Annex III
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HighRiskCategory {
    /// Biometric identification and categorization
    BiometricIdentification,
    /// Management of critical infrastructure
    CriticalInfrastructure,
    /// Education and vocational training
    Education,
    /// Employment and worker management
    Employment,
    /// Access to essential services
    EssentialServices,
    /// Law enforcement
    LawEnforcement,
    /// Migration, asylum and border control
    Migration,
    /// Administration of justice
    Justice,
    /// Democratic processes
    DemocraticProcesses,
}

impl HighRiskCategory {
    /// Get Annex III reference
    #[must_use]
    pub fn annex_reference(&self) -> &'static str {
        match self {
            HighRiskCategory::BiometricIdentification => "Annex III, 1",
            HighRiskCategory::CriticalInfrastructure => "Annex III, 2",
            HighRiskCategory::Education => "Annex III, 3",
            HighRiskCategory::Employment => "Annex III, 4",
            HighRiskCategory::EssentialServices => "Annex III, 5",
            HighRiskCategory::LawEnforcement => "Annex III, 6",
            HighRiskCategory::Migration => "Annex III, 7",
            HighRiskCategory::Justice => "Annex III, 8",
            HighRiskCategory::DemocraticProcesses => "Annex III, 9",
        }
    }
}

// ============================================================================
// CONFORMITY ASSESSMENT (Article 43)
// ============================================================================

/// Conformity assessment procedure
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConformityProcedure {
    /// Internal control (Annex VI)
    InternalControl,
    /// Conformity assessment with notified body (Annex VII)
    NotifiedBody,
}

/// Conformity assessment status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConformityStatus {
    /// Assessment procedure used
    pub procedure: ConformityProcedure,
    /// Assessment completion date (ISO 8601)
    pub assessment_date: Option<String>,
    /// Notified body ID (if applicable)
    pub notified_body_id: Option<String>,
    /// Certificate/Declaration reference
    pub certificate_ref: Option<String>,
    /// Expiry date (ISO 8601)
    pub expiry_date: Option<String>,
    /// Status of assessment
    pub status: AssessmentStatus,
}

/// Assessment status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AssessmentStatus {
    /// Not started
    NotStarted,
    /// In progress
    InProgress,
    /// Passed
    Passed,
    /// Failed
    Failed,
    /// Expired
    Expired,
}

// ============================================================================
// TRANSPARENCY REQUIREMENTS (Article 52)
// ============================================================================

/// Transparency requirement checklist
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct TransparencyChecklist {
    /// Users informed of AI interaction
    pub ai_interaction_disclosed: bool,
    /// Emotion recognition disclosed (if applicable)
    pub emotion_recognition_disclosed: Option<bool>,
    /// Biometric categorization disclosed (if applicable)
    pub biometric_categorization_disclosed: Option<bool>,
    /// Deep fake labeled (if applicable)
    pub deep_fake_labeled: Option<bool>,
    /// AI-generated content marked
    pub ai_content_marked: bool,
}

impl TransparencyChecklist {
    /// Check if all applicable requirements are met
    #[must_use]
    pub fn is_compliant(&self) -> bool {
        if !self.ai_interaction_disclosed {
            return false;
        }
        if let Some(disclosed) = self.emotion_recognition_disclosed {
            if !disclosed {
                return false;
            }
        }
        if let Some(disclosed) = self.biometric_categorization_disclosed {
            if !disclosed {
                return false;
            }
        }
        if let Some(labeled) = self.deep_fake_labeled {
            if !labeled {
                return false;
            }
        }
        self.ai_content_marked
    }
}

// ============================================================================
// TECHNICAL DOCUMENTATION (Article 11)
// ============================================================================

/// Technical documentation requirements for high-risk AI
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TechnicalDocumentation {
    /// General description of the AI system
    pub system_description: String,
    /// Elements of the AI system and development process
    pub development_process: DevelopmentDocumentation,
    /// Detailed information about monitoring, functioning and control
    pub monitoring_info: MonitoringDocumentation,
    /// Description of the risk management system
    pub risk_management: RiskManagementDocumentation,
    /// Changes made to the system through its lifecycle
    pub change_log: Vec<ChangeRecord>,
}

/// Development process documentation
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DevelopmentDocumentation {
    /// Design specifications
    pub design_specs: Option<String>,
    /// Development methodology
    pub methodology: Option<String>,
    /// Training data description
    pub training_data_description: Option<String>,
    /// Validation and testing procedures
    pub validation_procedures: Option<String>,
    /// Hardware/software requirements
    pub system_requirements: Option<String>,
}

/// Monitoring documentation
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MonitoringDocumentation {
    /// Capabilities and limitations
    pub capabilities: Option<String>,
    /// Accuracy metrics
    pub accuracy_metrics: Option<String>,
    /// Cybersecurity measures
    pub cybersecurity_measures: Option<String>,
    /// Human oversight mechanisms
    pub human_oversight: Option<String>,
}

/// Risk management documentation
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RiskManagementDocumentation {
    /// Risk identification methodology
    pub risk_identification: Option<String>,
    /// Risk analysis results
    pub risk_analysis: Option<String>,
    /// Risk mitigation measures
    pub mitigation_measures: Option<String>,
    /// Residual risks
    pub residual_risks: Option<String>,
}

/// Change record for lifecycle tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeRecord {
    /// Change timestamp (ISO 8601)
    pub timestamp: String,
    /// Change description
    pub description: String,
    /// Change author
    pub author: String,
    /// Impact assessment
    pub impact: String,
    /// Approval status
    pub approved: bool,
}

// ============================================================================
// RECORD KEEPING (Article 12)
// ============================================================================

/// Automatic logging requirements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LoggingRequirements {
    /// Period of use recording
    pub usage_period_logged: bool,
    /// Input data characteristics logged
    pub input_data_logged: bool,
    /// Reference database used
    pub reference_database_logged: bool,
    /// Verification results logged
    pub verification_logged: bool,
    /// Natural persons involved logged
    pub persons_involved_logged: bool,
}

impl LoggingRequirements {
    /// Check if all logging requirements are met
    #[must_use]
    pub fn is_compliant(&self) -> bool {
        self.usage_period_logged
            && self.input_data_logged
            && self.reference_database_logged
            && self.verification_logged
            && self.persons_involved_logged
    }
}

// ============================================================================
// HUMAN OVERSIGHT (Article 14)
// ============================================================================

/// Human oversight implementation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanOversight {
    /// Oversight mechanism in place
    pub mechanism: OversightMechanism,
    /// User interface for oversight
    pub user_interface: bool,
    /// Intervention capability
    pub intervention_capability: bool,
    /// Override capability
    pub override_capability: bool,
    /// Stop/disable capability
    pub stop_capability: bool,
}

/// Oversight mechanism types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OversightMechanism {
    /// Human-in-the-loop (decision approval required)
    HumanInTheLoop,
    /// Human-on-the-loop (monitoring with intervention)
    HumanOnTheLoop,
    /// Human-in-command (full control)
    HumanInCommand,
}

impl HumanOversight {
    /// Check if oversight requirements are met
    #[must_use]
    pub fn is_compliant(&self) -> bool {
        self.user_interface && self.intervention_capability && self.stop_capability
    }
}

// ============================================================================
// EU AI ACT COMPLIANCE REPORT
// ============================================================================

/// Complete EU AI Act compliance report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EuAiActComplianceReport {
    /// Report ID
    pub report_id: String,
    /// Generation timestamp (ISO 8601)
    pub timestamp: String,
    /// AI system identifier
    pub system_id: String,
    /// AI system name
    pub system_name: String,
    /// Provider/Operator information
    pub provider: ProviderInfo,
    /// Risk classification
    pub risk_level: RiskLevel,
    /// High-risk category (if applicable)
    pub high_risk_category: Option<HighRiskCategory>,
    /// Conformity assessment status
    pub conformity_status: Option<ConformityStatus>,
    /// Transparency checklist
    pub transparency: TransparencyChecklist,
    /// Technical documentation summary
    pub technical_docs: Option<TechnicalDocumentation>,
    /// Logging requirements status
    pub logging: LoggingRequirements,
    /// Human oversight implementation
    pub human_oversight: HumanOversight,
    /// Overall compliance status
    pub overall_compliance: ComplianceStatus,
    /// Recommendations
    pub recommendations: Vec<String>,
}

/// Provider/Operator information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderInfo {
    /// Legal name
    pub name: String,
    /// Registration number
    pub registration_number: Option<String>,
    /// Address
    pub address: Option<String>,
    /// Contact email
    pub contact_email: String,
    /// EU representative (if non-EU provider)
    pub eu_representative: Option<String>,
}

/// Overall compliance status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ComplianceStatus {
    /// Fully compliant
    Compliant,
    /// Partially compliant - action required
    PartiallyCompliant,
    /// Non-compliant - immediate action required
    NonCompliant,
    /// Assessment pending
    Pending,
}

impl EuAiActComplianceReport {
    /// Create a new compliance report
    #[must_use]
    pub fn new(
        system_id: String,
        system_name: String,
        provider: ProviderInfo,
        risk_level: RiskLevel,
    ) -> Self {
        Self {
            report_id: generate_report_id(),
            timestamp: current_iso_timestamp(),
            system_id,
            system_name,
            provider,
            risk_level,
            high_risk_category: None,
            conformity_status: None,
            transparency: TransparencyChecklist::default(),
            technical_docs: None,
            logging: LoggingRequirements {
                usage_period_logged: false,
                input_data_logged: false,
                reference_database_logged: false,
                verification_logged: false,
                persons_involved_logged: false,
            },
            human_oversight: HumanOversight {
                mechanism: OversightMechanism::HumanOnTheLoop,
                user_interface: false,
                intervention_capability: false,
                override_capability: false,
                stop_capability: false,
            },
            overall_compliance: ComplianceStatus::Pending,
            recommendations: Vec::new(),
        }
    }

    /// Evaluate overall compliance status
    pub fn evaluate_compliance(&mut self) {
        self.recommendations.clear();

        // Check if risk level requires special handling
        if self.risk_level.is_prohibited() {
            self.overall_compliance = ComplianceStatus::NonCompliant;
            self.recommendations
                .push("CRITICAL: System falls under prohibited AI practices".to_string());
            return;
        }

        let mut issues = 0;
        let mut critical = 0;

        // High-risk specific checks
        if self.risk_level == RiskLevel::High {
            if self.conformity_status.is_none() {
                critical += 1;
                self.recommendations
                    .push("Conformity assessment required for high-risk AI".to_string());
            } else if let Some(ref status) = self.conformity_status {
                if status.status != AssessmentStatus::Passed {
                    critical += 1;
                    self.recommendations
                        .push("Conformity assessment not passed".to_string());
                }
            }

            if self.technical_docs.is_none() {
                critical += 1;
                self.recommendations.push(
                    "Technical documentation required for high-risk AI (Article 11)".to_string(),
                );
            }
        }

        // Transparency checks
        if !self.transparency.is_compliant() {
            issues += 1;
            self.recommendations
                .push("Transparency requirements not fully met (Article 52)".to_string());
        }

        // Logging checks (high-risk)
        if self.risk_level == RiskLevel::High && !self.logging.is_compliant() {
            issues += 1;
            self.recommendations
                .push("Automatic logging requirements not fully met (Article 12)".to_string());
        }

        // Human oversight checks (high-risk)
        if self.risk_level == RiskLevel::High && !self.human_oversight.is_compliant() {
            issues += 1;
            self.recommendations
                .push("Human oversight requirements not fully met (Article 14)".to_string());
        }

        // Determine overall status
        self.overall_compliance = if critical > 0 {
            ComplianceStatus::NonCompliant
        } else if issues > 0 {
            ComplianceStatus::PartiallyCompliant
        } else {
            ComplianceStatus::Compliant
        };
    }

    /// Export report as JSON
    pub fn to_json(&self) -> Result<String, String> {
        serde_json::to_string_pretty(self).map_err(|e| e.to_string())
    }
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/// Generate unique report ID
fn generate_report_id() -> String {
    use sha3::{Digest, Sha3_256};
    let mut hasher = Sha3_256::new();

    // Use current time + random for uniqueness
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    hasher.update(timestamp.to_le_bytes());

    let hash = hasher.finalize();
    format!("EU-AI-{}", hex::encode(&hash[..8]))
}

/// Get current ISO 8601 timestamp
fn current_iso_timestamp() -> String {
    use std::time::SystemTime;
    let now = SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs();

    // Simple ISO 8601 format (without timezone library)
    let days = secs / 86400;
    let remaining = secs % 86400;
    let hours = remaining / 3600;
    let minutes = (remaining % 3600) / 60;
    let seconds = remaining % 60;

    // Calculate date (simplified, not accounting for leap years perfectly)
    let years = 1970 + (days / 365);
    let day_of_year = days % 365;
    let month = (day_of_year / 30) + 1;
    let day = (day_of_year % 30) + 1;

    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        years, month, day, hours, minutes, seconds
    )
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_risk_level_properties() {
        assert!(!RiskLevel::Minimal.requires_conformity_assessment());
        assert!(!RiskLevel::Limited.requires_conformity_assessment());
        assert!(RiskLevel::High.requires_conformity_assessment());
        assert!(!RiskLevel::Unacceptable.requires_conformity_assessment());

        assert!(!RiskLevel::Minimal.is_prohibited());
        assert!(RiskLevel::Unacceptable.is_prohibited());
    }

    #[test]
    fn test_transparency_checklist() {
        let mut checklist = TransparencyChecklist::default();
        assert!(!checklist.is_compliant());

        checklist.ai_interaction_disclosed = true;
        checklist.ai_content_marked = true;
        assert!(checklist.is_compliant());

        checklist.emotion_recognition_disclosed = Some(false);
        assert!(!checklist.is_compliant());

        checklist.emotion_recognition_disclosed = Some(true);
        assert!(checklist.is_compliant());
    }

    #[test]
    fn test_logging_requirements() {
        let logging = LoggingRequirements {
            usage_period_logged: true,
            input_data_logged: true,
            reference_database_logged: true,
            verification_logged: true,
            persons_involved_logged: true,
        };
        assert!(logging.is_compliant());

        let incomplete = LoggingRequirements {
            usage_period_logged: true,
            input_data_logged: false,
            reference_database_logged: true,
            verification_logged: true,
            persons_involved_logged: true,
        };
        assert!(!incomplete.is_compliant());
    }

    #[test]
    fn test_human_oversight() {
        let oversight = HumanOversight {
            mechanism: OversightMechanism::HumanInTheLoop,
            user_interface: true,
            intervention_capability: true,
            override_capability: false,
            stop_capability: true,
        };
        assert!(oversight.is_compliant());

        let incomplete = HumanOversight {
            mechanism: OversightMechanism::HumanOnTheLoop,
            user_interface: false,
            intervention_capability: true,
            override_capability: true,
            stop_capability: true,
        };
        assert!(!incomplete.is_compliant());
    }

    #[test]
    fn test_compliance_report_creation() {
        let provider = ProviderInfo {
            name: "Test Corp".to_string(),
            registration_number: Some("DE123456".to_string()),
            address: Some("Berlin, Germany".to_string()),
            contact_email: "compliance@test.corp".to_string(),
            eu_representative: None,
        };

        let report = EuAiActComplianceReport::new(
            "AI-001".to_string(),
            "Test AI System".to_string(),
            provider,
            RiskLevel::High,
        );

        assert!(!report.report_id.is_empty());
        assert_eq!(report.risk_level, RiskLevel::High);
        assert_eq!(report.overall_compliance, ComplianceStatus::Pending);
    }

    #[test]
    fn test_compliance_evaluation_high_risk() {
        let provider = ProviderInfo {
            name: "Test Corp".to_string(),
            registration_number: None,
            address: None,
            contact_email: "test@test.com".to_string(),
            eu_representative: None,
        };

        let mut report = EuAiActComplianceReport::new(
            "AI-002".to_string(),
            "High Risk AI".to_string(),
            provider,
            RiskLevel::High,
        );

        report.evaluate_compliance();

        // Should be non-compliant (missing conformity assessment, tech docs)
        assert_eq!(report.overall_compliance, ComplianceStatus::NonCompliant);
        assert!(!report.recommendations.is_empty());
    }

    #[test]
    fn test_compliance_evaluation_minimal_risk() {
        let provider = ProviderInfo {
            name: "Test Corp".to_string(),
            registration_number: None,
            address: None,
            contact_email: "test@test.com".to_string(),
            eu_representative: None,
        };

        let mut report = EuAiActComplianceReport::new(
            "AI-003".to_string(),
            "Low Risk AI".to_string(),
            provider,
            RiskLevel::Minimal,
        );

        // Set transparency requirements
        report.transparency.ai_interaction_disclosed = true;
        report.transparency.ai_content_marked = true;

        report.evaluate_compliance();

        // Should be compliant (minimal risk has fewer requirements)
        assert_eq!(report.overall_compliance, ComplianceStatus::Compliant);
    }

    #[test]
    fn test_prohibited_ai() {
        let provider = ProviderInfo {
            name: "Bad Corp".to_string(),
            registration_number: None,
            address: None,
            contact_email: "bad@corp.com".to_string(),
            eu_representative: None,
        };

        let mut report = EuAiActComplianceReport::new(
            "AI-BAD".to_string(),
            "Social Scoring System".to_string(),
            provider,
            RiskLevel::Unacceptable,
        );

        report.evaluate_compliance();

        assert_eq!(report.overall_compliance, ComplianceStatus::NonCompliant);
        assert!(report.recommendations[0].contains("prohibited"));
    }

    #[test]
    fn test_report_json_export() {
        let provider = ProviderInfo {
            name: "Test Corp".to_string(),
            registration_number: None,
            address: None,
            contact_email: "test@test.com".to_string(),
            eu_representative: None,
        };

        let report = EuAiActComplianceReport::new(
            "AI-004".to_string(),
            "Test AI".to_string(),
            provider,
            RiskLevel::Limited,
        );

        let json = report.to_json();
        assert!(json.is_ok());
        let json_str = json.unwrap();
        assert!(json_str.contains("AI-004"));
        assert!(json_str.contains("Limited"));
    }
}
