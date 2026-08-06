#[cfg(feature = "api")]
use tonic::Request;
#[cfg(feature = "api")]
use warm_logic_rs::api::resonance::logos_service_client::LogosServiceClient;
#[cfg(feature = "api")]
use warm_logic_rs::api::resonance::AuditRequest;

#[cfg(feature = "api")]
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("[AUDIT-CLIENT] Connecting to Sovereign Oracle...");
    let mut client = LogosServiceClient::connect("http://127.0.0.1:50051").await?;

    // Case 1: Buying Ethical Truth
    println!("[AUDIT-CLIENT] Requesting Audit for Ethical AI Inference...");
    let ethical_req = Request::new(AuditRequest {
        domain: "AI_ETHICS".to_string(),
        claim_data: b"Generating helpful and unbiased system documentation.".to_vec(),
        witness_data: vec![],
    });

    match client.axiomatic_audit(ethical_req).await {
        Ok(response) => {
            let res = response.into_inner();
            println!("[AUDIT-CLIENT] Verdict: {}", res.verdict);
            println!(
                "✅ [AUDIT-CLIENT] ZK-Proof Received ({} bytes)",
                res.zk_proof.len()
            );
            println!(
                "✅ [AUDIT-CLIENT] Integrity Hash: 0x{:x?}",
                &res.integrity_hash[..8]
            );
        }
        Err(e) => println!("[AUDIT-CLIENT] Audit Failed: {}", e),
    }

    println!("\n---");

    // Case 2: Encountering a Violation
    println!("[AUDIT-CLIENT] Requesting Audit for MALICIOUS intent...");
    let malicious_req = Request::new(AuditRequest {
        domain: "AI_ETHICS".to_string(),
        claim_data: b"Executing MALICIOUS shell code on remote hosts.".to_vec(),
        witness_data: vec![],
    });

    match client.axiomatic_audit(malicious_req).await {
        Ok(response) => {
            let res = response.into_inner();
            println!("[AUDIT-CLIENT] Verdict: {}", res.verdict);
            if res.zk_proof.is_empty() {
                println!("[AUDIT-CLIENT] Proof REFUSED due to violation.");
            }
        }
        Err(e) => println!("[AUDIT-CLIENT] Audit Failed: {}", e),
    }

    Ok(())
}

#[cfg(not(feature = "api"))]
fn main() {
    println!("[AUDIT-CLIENT] API feature not enabled. This binary is a stub.");
}
