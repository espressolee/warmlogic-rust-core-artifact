//! Pure Rust P2P Networking (QUIC)
//! Operation Ironclad: Replacing Python/GRPC with high-performance async Rust.

use crate::consensus::raft_pure::RaftEvent;
use crate::consensus::types::RaftRPC;
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::mpsc;

#[cfg(feature = "api")]
use quinn::{ClientConfig, Endpoint, ServerConfig};

pub struct P2PNetwork {
    #[cfg(feature = "api")]
    endpoint: Endpoint,
    peers: HashMap<String, SocketAddr>, // Map NodeID -> Address
    rpc_tx: mpsc::Sender<RaftEvent>,
}

#[cfg(feature = "api")]
impl P2PNetwork {
    pub async fn new(
        node_id: String,
        bind_addr: SocketAddr,
        peers: HashMap<String, SocketAddr>,
        rpc_tx: mpsc::Sender<RaftEvent>,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        // Configure Server (Placeholder: Requires Certs)
        // For now, we panic or fail if not configured, but we need code to compile.
        // We will implement `make_server_config` later or use a insecure stub if possible.

        let (endpoint, _) = make_server_endpoint(bind_addr)?;

        let p2p = Self {
            endpoint,
            peers,
            rpc_tx,
        };

        let endpoint_clone = p2p.endpoint.clone();
        let rpc_tx_clone = p2p.rpc_tx.clone();

        // Listen Loop
        tokio::spawn(async move {
            listen_loop(endpoint_clone, rpc_tx_clone).await;
        });

        Ok(p2p)
    }

    /// Run the networking loop to send outbound RPCs
    pub async fn run_sender(&self, mut outbound_rx: mpsc::Receiver<RaftRPC>) {
        while let Some(rpc) = outbound_rx.recv().await {
            if let Some(ref target) = rpc.target_id {
                self.unicast(target, rpc).await;
            } else {
                self.broadcast(rpc).await;
            }
        }
    }

    pub async fn unicast(&self, target_id: &str, rpc: RaftRPC) {
        if let Some(addr) = self.peers.get(target_id) {
            self.send_rpc(*addr, rpc).await;
        } else {
            println!("[P2P] Unknown peer: {}", target_id);
        }
    }

    pub async fn broadcast(&self, rpc: RaftRPC) {
        for addr in self.peers.values() {
            self.send_rpc(*addr, rpc.clone()).await;
        }
    }

    async fn send_rpc(&self, addr: SocketAddr, rpc: RaftRPC) {
        // Open connection, open stream, send serialized RPC
        // serialized via serde_json or borsh
        let payload = match serde_json::to_vec(&rpc) {
            Ok(v) => v,
            Err(e) => {
                println!("[P2P] Failed to serialize RPC: {}", e);
                return;
            }
        };

        match self.endpoint.connect(addr, "localhost") {
            Ok(connecting) => match connecting.await {
                Ok(connection) => match connection.open_uni().await {
                    Ok(mut stream) => {
                        if let Err(e) = stream.write_all(&payload).await {
                            println!("[P2P] Failed to send RPC: {}", e);
                        }
                        let _ = stream.finish().await;
                    }
                    Err(e) => println!("[P2P] Connection open failed: {}", e),
                },
                Err(e) => println!("[P2P] Connection failed: {}", e),
            },
            Err(e) => println!("[P2P] Connect error: {}", e),
        }
    }
}

// Stub for non-api features to allow compilation
#[cfg(not(feature = "api"))]
impl P2PNetwork {
    pub async fn new(
        _node_id: String,
        _bind: SocketAddr,
        _peers: HashMap<String, SocketAddr>,
        _tx: mpsc::Sender<RaftEvent>,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        panic!("P2P requires api feature");
    }
}

#[cfg(feature = "api")]
fn make_server_endpoint(
    bind_addr: SocketAddr,
) -> Result<(Endpoint, Vec<u8>), Box<dyn std::error::Error>> {
    // Generate self-signed cert on the fly
    let cert = rcgen::generate_simple_self_signed(vec!["localhost".into()])?;
    let cert_der = cert.serialize_der()?;
    let priv_key = cert.serialize_private_key_der();

    let server_config = ServerConfig::with_single_cert(
        vec![rustls::Certificate(cert_der.clone())],
        rustls::PrivateKey(priv_key),
    )?;

    let mut endpoint = Endpoint::server(server_config, bind_addr)?;

    // Client config (skip verification for now/internal)
    // In real Ironclad, we verify CA.
    // ...

    Ok((endpoint, cert_der))
}

#[cfg(feature = "api")]
async fn listen_loop(endpoint: Endpoint, tx: mpsc::Sender<RaftEvent>) {
    while let Some(conn) = endpoint.accept().await {
        let tx = tx.clone();
        tokio::spawn(async move {
            let connection = match conn.await {
                Ok(c) => c,
                Err(e) => {
                    println!("[P2P] Accept handshake failed: {}", e);
                    return;
                }
            };

            while let Ok(mut stream) = connection.accept_uni().await {
                let tx_inner = tx.clone();
                tokio::spawn(async move {
                    let mut buf = Vec::new();
                    if let Ok(_) = stream.read_to_end(&mut buf).await {
                        if let Ok(rpc) = serde_json::from_slice::<RaftRPC>(&buf) {
                            let _ = tx_inner.send(RaftEvent::RPC(rpc)).await;
                        }
                    }
                });
            }
        });
    }
}
