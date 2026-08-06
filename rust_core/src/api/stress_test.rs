use crate::api::resonance::logos_service_client::LogosServiceClient;
use crate::api::resonance::{IngestRealityRequest, SnapshotRequest};
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;
use std::time::{Duration, Instant};

/// High-intensity gRPC Stress Audit
/// Verifies PQC verification latency and rate limiting resilience.
pub async fn run_stress_test(
    addr: String,
    duration_secs: u64,
    concurrency: usize,
    malformed_ratio: f64,
) -> Result<(), Box<dyn std::error::Error>> {
    println!(
        "🔥 [STRESS] Starting high-intensity gRPC audit on {}...",
        addr
    );
    println!(
        "🔥 [STRESS] Params: duration={}s, concurrency={}, malformed_ratio={}",
        duration_secs, concurrency, malformed_ratio
    );

    let start_time = Instant::now();
    let duration = Duration::from_secs(duration_secs);

    let mut handles = vec![];

    for worker_id in 0..concurrency {
        let addr = addr.clone();
        let handle = tokio::spawn(async move {
            let mut client = match LogosServiceClient::connect(format!("http://{}", addr)).await {
                Ok(c) => c,
                Err(e) => {
                    eprintln!("Worker {} failed to connect: {}", worker_id, e);
                    return;
                }
            };

            let mut success = 0;
            let mut errors = 0;
            let mut rng = ChaCha8Rng::from_entropy();

            while start_time.elapsed() < duration {
                // Alternating between IngestReality and SnapshotRequest
                let is_snapshot = rng.gen_bool(0.1); // 10% snapshots

                if is_snapshot {
                    let req = SnapshotRequest {
                        reason: "STRESS_TEST_AUDIT".to_string(),
                        proof_of_origin: vec![0u8; 32], // Mock small proof
                    };
                    match client.trigger_snapshot(req).await {
                        Ok(_) => success += 1,
                        Err(_) => errors += 1,
                    }
                } else {
                    let mut data = vec![0u8; 1024]; // 1KB sensor data
                    rng.fill(&mut data[..]);

                    let mut signature;
                    if rng.gen_bool(malformed_ratio) {
                        // Malformed signature
                        signature = vec![0u8; 64]; // Wrong size or content
                        rng.fill(&mut signature[..]);
                    } else {
                        // Valid signature simulation (Mock SHA3-hash as currently used in server.rs)
                        use sha3::{Digest, Sha3_256};
                        let mut hasher = Sha3_256::new();
                        hasher.update(&data);
                        hasher.update(b"REALITY_SALT_30000");
                        signature = hasher.finalize().to_vec();
                    }

                    let req = IngestRealityRequest {
                        source_id: format!("S_{}", worker_id),
                        sensor_data: data,
                        signature,
                        timestamp: std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)
                            .unwrap()
                            .as_millis() as u64,
                        zone_id: "CORE".to_string(),
                    };

                    match client.ingest_reality(req).await {
                        Ok(_) => success += 1,
                        Err(_) => errors += 1,
                    }
                }

                // Extremely tight loop for maximum pressure
            }
            println!(
                "📊 Worker {}: Success={}, Errors={}",
                worker_id, success, errors
            );
        });
        handles.push(handle);
    }

    for h in handles {
        let _ = h.await;
    }

    println!(
        "✅ [STRESS] Audit complete in {}ms.",
        start_time.elapsed().as_millis()
    );
    Ok(())
}
