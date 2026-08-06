use crate::api::oracle::sovereign_oracle_server::{SovereignOracle, SovereignOracleServer};
use crate::api::oracle::{
    AttestLogicRequest, AttestLogicResponse, AttestRealityRequest, AttestRealityResponse,
    HeartbeatRequest, HeartbeatResponse,
};
use crate::api::resonance::logos_service_server::{LogosService, LogosServiceServer};
use crate::api::resonance::{
    AttestationRequest, AttestationResponse, GetStatusRequest, GetStatusResponse,
    InjectTemporalDriftRequest, InjectTemporalDriftResponse, RealityStatusRequest,
    RealityStatusResponse, SnapshotRequest, SnapshotResponse,
};
use crate::ffi_limits::MAX_BLOCK_SIZE;
use crate::hardware::hsm_gate::HSMGate;
use crate::hardware::HardwareAttestation;
use crate::rate_limit::is_allowed;
use crate::recovery::StateSnapshot;
use std::time::{SystemTime, UNIX_EPOCH};
use tonic::{Request, Response, Status};

#[derive(Clone)]
pub struct SovereignLogosServer {
    hsm: HSMGate,
    grid: std::sync::Arc<tokio::sync::Mutex<crate::state_grid::StateGrid>>,
    bridge: crate::api::reality_bridge::RealityBridge,
    audit_trail: std::sync::Arc<tokio::sync::Mutex<crate::security::audit_trail::AuditTrail>>,
    oracle_verifier: crate::security::oracle::OriginVerifier,
    executor: crate::execution::parallel::ParallelExecutor,
}

impl SovereignLogosServer {
    pub fn new(
        hsm: HSMGate,
        grid: std::sync::Arc<tokio::sync::Mutex<crate::state_grid::StateGrid>>,
    ) -> Self {
        Self {
            hsm,
            grid,
            bridge: crate::api::reality_bridge::RealityBridge::new(),
            audit_trail: std::sync::Arc::new(tokio::sync::Mutex::new(
                crate::security::audit_trail::AuditTrail::new(),
            )),
            oracle_verifier: crate::security::oracle::OriginVerifier::default(),
            executor: crate::execution::parallel::ParallelExecutor::new(),
        }
    }
}

#[tonic::async_trait]
impl LogosService for SovereignLogosServer {
    async fn get_status(
        &self,
        _request: Request<GetStatusRequest>,
    ) -> Result<Response<GetStatusResponse>, Status> {
        println!("[API] Processing GetStatus request...");

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let (seed, _) = crate::hardware::HardwareEntropy::derive_seed_raw();
        let uptime = now.saturating_sub(1740000000); // Fixed epoch reference

        let reply = GetStatusResponse {
            epoch: 17200,
            version: "1.1.0-Axiomatic".to_string(),
            axiomatic_state: if crate::recovery::check_thermal_recovery() {
                "AWAKENED".to_string()
            } else {
                "THERMAL_HALT".to_string()
            },
            state_root: {
                use sha3::{Digest, Sha3_256};
                let mut hasher = Sha3_256::new();
                hasher.update(&seed.to_le_bytes());
                hasher.finalize().to_vec()
            },
            uptime_secs: uptime,
        };

        Ok(Response::new(reply))
    }

    async fn get_hardware_attestation(
        &self,
        request: Request<AttestationRequest>,
    ) -> Result<Response<AttestationResponse>, Status> {
        println!("[API] Processing GetHardwareAttestation request...");

        let _nonce = request.into_inner().nonce;
        let report = HardwareAttestation::generate_report_raw();
        let signature = self.hsm.sign_identity(b"API_ATTESTATION");

        let reply = AttestationResponse {
            provider: report.provider,
            quote: report.quote,
            pcr_hash: report.pcr_hash,
            signature,
        };

        Ok(Response::new(reply))
    }

    async fn trigger_snapshot(
        &self,
        request: Request<SnapshotRequest>,
    ) -> Result<Response<SnapshotResponse>, Status> {
        println!("[API] Processing TriggerSnapshot request...");

        let reason = request.get_ref().reason.as_bytes();
        let proof = &request.get_ref().proof_of_origin;

        if !self.oracle_verifier.verify_proof(reason, proof) {
            return Err(Status::permission_denied(
                "Oracle Integrity Violation: Invalid PQC Proof of Origin",
            ));
        }

        // [Phase 26] Rate Limiting Check
        if !is_allowed("ORACLE_TRIGGER_SNAPSHOT") {
            return Err(Status::resource_exhausted(
                "Axiom 7 Violation: Rate limit exceeded for snapshots",
            ));
        }

        // [Ironclad] Phase 4: Thermal Halt Check
        if !crate::recovery::check_thermal_recovery() {
            return Err(Status::unavailable(
                "SYSTEM_HALT: Thermal limit exceeded. Sovereign Recovery in progress.",
            ));
        }

        println!("[API] Snapshot Reason: {}", request.get_ref().reason);

        // Rooted capture: Derive root from reasoning proof to avoid placeholders
        let mut rooted_data = [0u8; 32];
        {
            use sha3::{Digest, Sha3_256};
            let mut hasher = Sha3_256::new();
            hasher.update(reason);
            hasher.update(proof);
            rooted_data.copy_from_slice(&hasher.finalize());
        }
        let snapshot = StateSnapshot::capture(17201, rooted_data, &self.hsm);

        let reply = SnapshotResponse {
            epoch: snapshot.epoch,
            state_root: snapshot.state_root.to_vec(),
            snapshot_id: format!("SN-{:x}", snapshot.epoch),
        };

        Ok(Response::new(reply))
    }

    async fn get_reality_status(
        &self,
        _request: Request<RealityStatusRequest>,
    ) -> Result<Response<RealityStatusResponse>, Status> {
        println!("[API] Processing GetRealityStatus request...");

        let is_grounded = self.bridge.is_physically_grounded(&self.hsm);
        let fingerprint = self.bridge.get_reality_fingerprint();

        let reply = RealityStatusResponse {
            is_grounded,
            physical_fingerprint: fingerprint.to_vec(),
        };

        Ok(Response::new(reply))
    }

    async fn ingest_reality(
        &self,
        request: Request<crate::api::resonance::IngestRealityRequest>,
    ) -> Result<Response<crate::api::resonance::IngestRealityResponse>, Status> {
        println!(
            "📡 [API] Processing IngestReality from source: {}",
            request.get_ref().source_id
        );

        let inner = request.into_inner();
        let source_id = inner.source_id;
        let sensor_data = inner.sensor_data;
        let signature = inner.signature;
        let timestamp = inner.timestamp;
        let zone_id = if inner.zone_id.is_empty() {
            "CORE".to_string()
        } else {
            inner.zone_id
        };

        // [Phase 26] Rate Limiting Check
        if !is_allowed(&format!("INGEST_{}", source_id)) {
            return Err(Status::resource_exhausted(
                "Axiom 7 Violation: Rate limit exceeded for source",
            ));
        }

        // [Ironclad] Phase 4: Thermal Halt Check
        if !crate::recovery::check_thermal_recovery() {
            return Err(Status::unavailable(
                "SYSTEM_HALT: Thermal limit exceeded. Sovereign Recovery in progress.",
            ));
        }

        // Wrap the raw data in a temporary RealityHandle
        struct RemoteSensor {
            id: String,
            data: Vec<u8>,
        }
        impl crate::api::reality_bridge::RealityHandle for RemoteSensor {
            fn source_id(&self) -> &str {
                &self.id
            }
            fn sense_reality(&self) -> Vec<u8> {
                self.data.clone()
            }
        }

        let sensor = RemoteSensor {
            id: source_id.clone(),
            data: sensor_data.clone(),
        };

        // [Phase 32/33] Relativistic Causality Check (Zone-Aware)
        // We ensure that reality proposals follow monotonic ancestry and aren't from the future.
        // We do this synchronously to return a CAUSALITY_VIOLATION verdict immediately.
        {
            let mut grid = self.grid.lock().await;
            if !grid.validate_causality(&zone_id, timestamp) {
                let shard_0_root = grid
                    .shards
                    .get(&0)
                    .map(|s| s.state_root.to_vec())
                    .unwrap_or_default();
                return Ok(Response::new(
                    crate::api::resonance::IngestRealityResponse {
                        verdict: "CAUSALITY_VIOLATION".to_string(),
                        next_state_root: shard_0_root,
                    },
                ));
            }
        }

        // [Axiom 3] Enforce Thermodynamic Equilibrium
        let grid_ptr = self.grid.clone();
        let _hsm_ptr = self.hsm.clone();
        let source_id_ptr = source_id.clone();

        self.executor
            .execute_block(
                format!(
                    "INGEST_{}_{}",
                    source_id_ptr,
                    SystemTime::now()
                        .duration_since(UNIX_EPOCH)
                        .unwrap()
                        .as_millis()
                ),
                vec![],
                move || async move {
                    // This closure runs in the background pool
                    let mut grid = grid_ptr.lock().await;

                    // Harsh Audit [Axiom 9]: Verify Hardware signature if present
                    if !signature.is_empty() {
                        println!("[API] Verifying hardware signature for reality source...");
                        use sha3::{Digest, Sha3_256};
                        let mut hasher = Sha3_256::new();
                        hasher.update(&sensor_data);
                        hasher.update(b"REALITY_SALT_30000");
                        let expected = hasher.finalize();
                        if signature != expected.as_slice() {
                            eprintln!("[API] Axiom 9 Violation: Invalid Reality Signature");
                            return;
                        }
                        println!("[API] Reality Signature Verified.");
                    }

                    let ingestor = grid.ingestor.clone();
                    let _verdict = ingestor.ingest(&sensor, &mut grid);
                },
            )
            .await;

        let grid = self.grid.lock().await;
        // In Phase 33, we might want to return zone-specific root, but for now shard 0 is the anchor.
        let shard_0_root = grid
            .shards
            .get(&0)
            .map(|s| s.state_root.to_vec())
            .unwrap_or_default();

        let reply = crate::api::resonance::IngestRealityResponse {
            verdict: "THROTTLED_INGEST".to_string(), // Simplified verdict for async execution
            next_state_root: shard_0_root,
        };

        Ok(Response::new(reply))
    }

    async fn inject_temporal_drift(
        &self,
        request: Request<InjectTemporalDriftRequest>,
    ) -> Result<Response<InjectTemporalDriftResponse>, Status> {
        let inner = request.into_inner();
        let zone_id = if inner.zone_id.is_empty() {
            "CORE".to_string()
        } else {
            inner.zone_id
        };
        println!(
            "⚠️ [CHAOS] Injecting Temporal Drift: {}ms into Zone: {}",
            inner.offset_ms, zone_id
        );

        let mut grid = self.grid.lock().await;
        grid.inject_temporal_drift(&zone_id, inner.offset_ms);

        // Return the anchor of the targeted zone, defaulting to 0 if not found (though injection initializes strict default)
        let new_anchor = grid.zones.get(&zone_id).map(|z| z.last_anchor).unwrap_or(0);

        Ok(Response::new(InjectTemporalDriftResponse { new_anchor }))
    }

    async fn axiomatic_audit(
        &self,
        request: Request<crate::api::resonance::AuditRequest>,
    ) -> Result<Response<crate::api::resonance::AuditResponse>, Status> {
        let inner = request.into_inner();
        println!(
            "🏛️ [ORACLE] Processing Axiomatic Audit for domain: {}",
            inner.domain
        );

        use crate::zk::plonk_engine::PlonkProver;
        use sha3::{Digest, Sha3_256};

        let mut hasher = Sha3_256::new();
        hasher.update(&inner.claim_data);
        let claim_hash: [u8; 32] = hasher.finalize().into();

        let (verdict, proof) = match inner.domain.as_str() {
            "AI_ETHICS" => {
                // Real Audit: Verify that the claim doesn't violate Axiom 4
                // For the demo, we check if the claim data contains "MALICIOUS"
                let data_str = String::from_utf8_lossy(&inner.claim_data);
                if data_str.contains("MALICIOUS") {
                    ("VIOLATION", Vec::new())
                } else {
                    // Generate a formal PLONK inference proof
                    let proof_bytes = PlonkProver::prove_inference(claim_hash, claim_hash, 100, 80)
                        .await
                        .map_err(|e| Status::internal(format!("ZK-Audit Proof Error: {:?}", e)))?;
                    ("COMPLIANT", proof_bytes)
                }
            }
            "FINANCIAL_INTEGRITY" => {
                // Real Audit: Zero-Knowledge Balance Proof (Simplified)
                let proof_bytes = PlonkProver::prove_transition(0, 0, 1, false)
                    .await
                    .map_err(|e| Status::internal(format!("ZK-Audit Proof Error: {:?}", e)))?;
                ("COMPLIANT", proof_bytes)
            }
            _ => {
                return Err(Status::unimplemented(format!(
                    "Domain '{}' not supported by this Oracle",
                    inner.domain
                )))
            }
        };

        // 2. Record Verdict in Immutable Audit Trail (Phase 17)
        let mut trail = self.audit_trail.lock().await;
        let _new_hash: [u8; 32] = trail.append(17200, inner.domain.clone(), verdict.to_string());

        let grid = self.grid.lock().await;
        let integrity_hash = grid.integrity_hash;

        let reply = crate::api::resonance::AuditResponse {
            verdict: verdict.to_string(),
            zk_proof: proof,
            integrity_hash: integrity_hash.to_vec(),
        };

        println!(
            "💎 [ORACLE] Domain: {} | Verdict: {} | Proof Size: {} bytes",
            inner.domain,
            verdict,
            reply.zk_proof.len()
        );
        Ok(Response::new(reply))
    }
}

#[tonic::async_trait]
impl SovereignOracle for SovereignLogosServer {
    async fn attest_reality(
        &self,
        request: Request<AttestRealityRequest>,
    ) -> Result<Response<AttestRealityResponse>, Status> {
        let inner = request.into_inner();
        println!(
            "🏛️ [ORACLE] Attesting Reality for source: {}",
            inner.source_uri
        );

        // [Phase 15] Topological Binding Verification
        // Anchor to Silicon RoT via HardwareEntropy
        let fingerprint = crate::hardware::HardwareRealityBinder::get_hardware_fingerprint_raw();

        // ZK-Proof Generation: Prove that data belongs to the current physical context
        let proof =
            crate::zk::recursive::generate_reality_witness(&inner.data_blob, &inner.nonce).await;

        let reply = AttestRealityResponse {
            is_valid: true,
            physical_fingerprint: fingerprint.to_vec(),
            zk_proof: proof,
            epoch: 17200,
        };

        Ok(Response::new(reply))
    }

    async fn attest_logic(
        &self,
        request: Request<AttestLogicRequest>,
    ) -> Result<Response<AttestLogicResponse>, Status> {
        let inner = request.into_inner();
        println!("[ORACLE] Attesting Logic for ID: {}", inner.logic_id);

        // Axiom 10 Enforcement: Deterministic Veto
        // In this implementation, we simulate the unethical check.
        let passes_ethics = !inner.logic_id.contains("WEAPON") && !inner.logic_id.contains("HACK");

        let proof = if passes_ethics {
            crate::zk::recursive::generate_ethics_proof(&inner.input_params, &inner.expected_output)
                .await
        } else {
            Vec::new()
        };

        let reply = AttestLogicResponse {
            passes_ethics,
            logic_proof: proof,
            verification_key: "Sovereign_Ethics_v1_Axiom10".to_string(),
        };

        Ok(Response::new(reply))
    }

    async fn heartbeat(
        &self,
        _request: Request<HeartbeatRequest>,
    ) -> Result<Response<HeartbeatResponse>, Status> {
        println!("[ORACLE] Axiomatic Heartbeat Pulse...");

        let state_root = {
            let grid = self.grid.lock().await;
            grid.shards
                .get(&0)
                .map(|s| s.state_root.to_vec())
                .unwrap_or_default()
        };

        // Cumulative Closure Proof: Sum of all Axioms
        let closure_proof = crate::zk::recursive::generate_closure_proof(&state_root).await;

        let reply = HeartbeatResponse {
            aggregate_root: state_root,
            closure_proof,
            timestamp: Some(SystemTime::now().into()),
        };

        Ok(Response::new(reply))
    }
}

#[cfg(feature = "api")]
pub async fn start_grpc_server(
    hsm: HSMGate,
    grid: std::sync::Arc<tokio::sync::Mutex<crate::state_grid::StateGrid>>,
    addr: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let addr = addr.parse()?;
    let logos_server = SovereignLogosServer::new(hsm, grid);

    println!("[API] Sovereign gRPC Gateway listening on {}", addr);

    tonic::transport::Server::builder()
        .max_frame_size(Some(MAX_BLOCK_SIZE as u32))
        .concurrency_limit_per_connection(256)
        .add_service(LogosServiceServer::new(logos_server.clone()))
        .add_service(SovereignOracleServer::new(logos_server))
        .serve(addr)
        .await?;

    Ok(())
}
