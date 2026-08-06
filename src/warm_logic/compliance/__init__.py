# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
[Q3 2026] Compliance Infrastructure

Provides regulatory compliance support for:
- GDPR (General Data Protection Regulation)
- SOC 2 Type I/II
- HIPAA
- EU AI Act
"""

from warm_logic.compliance.gdpr import (
    ConsentManager,
    ConsentPurpose,
    ConsentRecord,
    DataRetentionPolicy,
    DataSubjectRequest,
    DataSubjectRights,
    GDPRCompliance,
    ProcessingRecord,
    RequestStatus,
    RequestType,
)
from warm_logic.compliance.soc2 import (
    AccessAuditLog,
    AccessLog,
    ChangeManagement,
    ChangeRecord,
    ControlRegistry,
    IncidentManagement,
    RiskAssessment,
    RiskRegistry,
    SecurityControl,
    SecurityIncident,
    SOC2Compliance,
    TrustServiceCategory,
)
from warm_logic.compliance.hipaa import (
    BreachNotificationManager,
    BreachSeverity,
    BusinessAssociate,
    BusinessAssociateManager,
    DisclosureType,
    HIPAACompliance,
    PHIAccessLog,
    PHICategory,
    PHIDataHandler,
    PHIRecord,
    RiskAnalysis,
    RiskAnalysisManager,
    SafeguardsRegistry,
    SafeguardType,
    SecuritySafeguard,
)
from warm_logic.compliance.eu_ai_act import (
    AISystemRecord,
    AISystemRegistry,
    ConformityAssessment,
    ConformityAssessmentManager,
    ConformityStatus,
    EUAIActCompliance,
    HighRiskArea,
    HumanOversightManager,
    HumanOversightMeasure,
    IncidentManager as EUAIIncidentManager,
    IncidentRecord as EUAIIncidentRecord,
    RiskAssessmentManager as EUAIRiskAssessmentManager,
    RiskAssessmentRecord,
    RiskCategory,
    TechnicalDocumentation,
    TechnicalDocumentationManager,
    TransparencyManager,
    TransparencyRecord,
)
from warm_logic.compliance.documentation import (
    AuditStatus,
    AuditTrailEntry,
    AuditTrailManager,
    ComplianceDocument,
    ComplianceDocumentationManager,
    ComplianceFramework,
    CompliancePackageExporter,
    ComplianceReport,
    DocumentRegistry,
    DocumentType,
    EvidenceCollector,
    EvidenceItem,
    ReportGenerator,
)

__all__ = [
    # GDPR
    "GDPRCompliance",
    "DataSubjectRights",
    "DataSubjectRequest",
    "RequestType",
    "RequestStatus",
    "ConsentManager",
    "ConsentRecord",
    "ConsentPurpose",
    "DataRetentionPolicy",
    "ProcessingRecord",
    # SOC 2
    "SOC2Compliance",
    "TrustServiceCategory",
    "SecurityControl",
    "ControlRegistry",
    "AccessLog",
    "AccessAuditLog",
    "ChangeRecord",
    "ChangeManagement",
    "SecurityIncident",
    "IncidentManagement",
    "RiskAssessment",
    "RiskRegistry",
    # HIPAA
    "HIPAACompliance",
    "PHICategory",
    "DisclosureType",
    "SafeguardType",
    "BreachSeverity",
    "PHIRecord",
    "PHIAccessLog",
    "PHIDataHandler",
    "SafeguardsRegistry",
    "SecuritySafeguard",
    "BusinessAssociate",
    "BusinessAssociateManager",
    "BreachNotificationManager",
    "RiskAnalysis",
    "RiskAnalysisManager",
    # EU AI Act
    "EUAIActCompliance",
    "RiskCategory",
    "HighRiskArea",
    "ConformityStatus",
    "AISystemRecord",
    "AISystemRegistry",
    "RiskAssessmentRecord",
    "EUAIRiskAssessmentManager",
    "TechnicalDocumentation",
    "TechnicalDocumentationManager",
    "HumanOversightMeasure",
    "HumanOversightManager",
    "TransparencyRecord",
    "TransparencyManager",
    "ConformityAssessment",
    "ConformityAssessmentManager",
    "EUAIIncidentRecord",
    "EUAIIncidentManager",
    # Documentation Package
    "ComplianceDocumentationManager",
    "ComplianceFramework",
    "DocumentType",
    "AuditStatus",
    "ComplianceDocument",
    "DocumentRegistry",
    "EvidenceItem",
    "EvidenceCollector",
    "AuditTrailEntry",
    "AuditTrailManager",
    "ComplianceReport",
    "ReportGenerator",
    "CompliancePackageExporter",
]
