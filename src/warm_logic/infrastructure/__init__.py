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
[Q4 2026] Infrastructure Module

Production infrastructure for WarmLogic deployments:
- SLA Architecture (99.9% uptime)
- Multi-region Deployment
- Health Monitoring
- Traffic Routing
- Failover Management
- Performance Benchmarking (1000+ TPS)
- Release Management (v1.0.0 GA)
"""

from warm_logic.infrastructure.release import (
    ArtifactBuilder,
    Changelog,
    ChangelogEntry,
    ChangelogGenerator,
    ChangeType,
    DistributionChannel,
    DistributionManager,
    Release,
    ReleaseArtifact,
    ReleaseManager,
    ReleaseStatus,
    ReleaseType,
    ReleaseValidator,
    SemanticVersion,
    ValidationGate,
    ValidationResult,
    VersionManager,
)
from warm_logic.infrastructure.benchmark import (
    BenchmarkConfig,
    BenchmarkReportGenerator,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkStatus,
    BenchmarkSuite,
    CustomTransactionGenerator,
    LatencyMetrics,
    LoadGenerator,
    LoadPattern,
    PerformanceThreshold,
    RegressionDetector,
    SimpleTransactionGenerator,
    ThresholdValidator,
    ThroughputMetrics,
    TransactionGenerator,
    TransactionResult,
)
from warm_logic.infrastructure.sla import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    DatabaseHealthCheck,
    DependencyHealthCheck,
    GracefulDegradation,
    HealthCheck,
    HealthCheckRegistry,
    HealthCheckResult,
    HealthStatus,
    SLAConfig,
    SLAMetrics,
    SLAMonitor,
)
from warm_logic.infrastructure.multiregion import (
    DataSovereignty,
    FailoverEvent,
    FailoverManager,
    HealthMonitor,
    MultiRegionDeployment,
    Region,
    RegionHealth,
    RegionRegistry,
    RegionStatus,
    ReplicationConfig,
    ReplicationManager,
    ReplicationMode,
    ReplicationStatus,
    RoutingRule,
    RoutingStrategy,
    TrafficRouter,
)

__all__ = [
    # Release Management
    "ReleaseType",
    "ReleaseStatus",
    "ChangeType",
    "ValidationGate",
    "DistributionChannel",
    "SemanticVersion",
    "ChangelogEntry",
    "Changelog",
    "ValidationResult",
    "ReleaseArtifact",
    "Release",
    "VersionManager",
    "ChangelogGenerator",
    "ReleaseValidator",
    "ArtifactBuilder",
    "DistributionManager",
    "ReleaseManager",
    # Performance Benchmarking
    "BenchmarkStatus",
    "LoadPattern",
    "TransactionResult",
    "LatencyMetrics",
    "ThroughputMetrics",
    "BenchmarkConfig",
    "BenchmarkResult",
    "TransactionGenerator",
    "SimpleTransactionGenerator",
    "CustomTransactionGenerator",
    "LoadGenerator",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "PerformanceThreshold",
    "ThresholdValidator",
    "RegressionDetector",
    "BenchmarkReportGenerator",
    # SLA Architecture
    "HealthStatus",
    "CircuitState",
    "HealthCheckResult",
    "SLAConfig",
    "SLAMetrics",
    "HealthCheck",
    "DatabaseHealthCheck",
    "DependencyHealthCheck",
    "CircuitBreaker",
    "CircuitOpenError",
    "HealthCheckRegistry",
    "SLAMonitor",
    "GracefulDegradation",
    # Multi-region Deployment
    "RegionStatus",
    "ReplicationMode",
    "RoutingStrategy",
    "DataSovereignty",
    "Region",
    "RegionHealth",
    "ReplicationConfig",
    "ReplicationStatus",
    "FailoverEvent",
    "RoutingRule",
    "RegionRegistry",
    "HealthMonitor",
    "ReplicationManager",
    "FailoverManager",
    "TrafficRouter",
    "MultiRegionDeployment",
]
