//! Raft Distributed Network Layer
//!
//! High-performance asynchronous transport using TCP + Manual Length-Delimited Framing.
//! Optimized for sub-millisecond consensus on Milk-V Duo S without external framing dependencies.

use crate::consensus::types::RaftRPC;
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::mpsc;
use tokio::sync::Mutex;

pub struct RaftNetwork {
    node_id: String,
    peers: HashMap<String, SocketAddr>,
    rpc_tx: mpsc::UnboundedSender<RaftRPC>,
    peer_connections: Arc<Mutex<HashMap<String, mpsc::UnboundedSender<RaftRPC>>>>,
}

impl RaftNetwork {
    #[must_use]
    pub fn new(
        node_id: String,
        peers: HashMap<String, SocketAddr>,
        rpc_tx: mpsc::UnboundedSender<RaftRPC>,
    ) -> Self {
        Self {
            node_id,
            peers,
            rpc_tx,
            peer_connections: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Start the network listener and peer management loop
    pub async fn start(&self, listen_addr: SocketAddr) -> tokio::io::Result<()> {
        let listener = TcpListener::bind(listen_addr).await?;
        let rpc_tx = self.rpc_tx.clone();

        // Spawn Listener Loop
        tokio::spawn(async move {
            while let Ok((mut stream, _)) = listener.accept().await {
                let rpc_tx_inner = rpc_tx.clone();
                tokio::spawn(async move {
                    loop {
                        // Read 4-byte length prefix
                        let mut len_buf = [0u8; 4];
                        if stream.read_exact(&mut len_buf).await.is_err() {
                            break;
                        }
                        let len = u32::from_be_bytes(len_buf) as usize;
                        if len > 10 * 1024 * 1024 {
                            // 10MB sanity limit
                            break;
                        }

                        // Read payload
                        let mut payload = vec![0u8; len];
                        if stream.read_exact(&mut payload).await.is_err() {
                            break;
                        }

                        if let Ok(rpc) = serde_json::from_slice::<RaftRPC>(&payload) {
                            let _ = rpc_tx_inner.send(rpc);
                        }
                    }
                });
            }
        });

        Ok(())
    }

    /// Send a Raft RPC to a specific peer
    pub async fn send_rpc(&self, target_id: &String, rpc: RaftRPC) {
        let mut conns = self.peer_connections.lock().await;

        if let Some(tx) = conns.get(target_id) {
            if tx.send(rpc.clone()).is_ok() {
                return;
            }
        }

        // Connect if not exist or failed
        if let Some(&addr) = self.peers.get(target_id) {
            let (tx, mut rx) = mpsc::unbounded_channel::<RaftRPC>();
            let _ = tx.send(rpc);
            conns.insert(target_id.clone(), tx);

            tokio::spawn(async move {
                if let Ok(mut stream) = TcpStream::connect(addr).await {
                    while let Some(rpc_to_send) = rx.recv().await {
                        if let Ok(bytes) = serde_json::to_vec(&rpc_to_send) {
                            let len = bytes.len() as u32;
                            let mut packet = Vec::with_capacity(4 + bytes.len());
                            packet.extend_from_slice(&len.to_be_bytes());
                            packet.extend_from_slice(&bytes);

                            if stream.write_all(&packet).await.is_err() {
                                break;
                            }
                        }
                    }
                }
            });
        }
    }

    /// Broadcast an RPC to all peers
    pub async fn broadcast(&self, rpc: RaftRPC) {
        for peer_id in self.peers.keys() {
            if peer_id == &self.node_id {
                continue;
            }
            self.send_rpc(peer_id, rpc.clone()).await;
        }
    }
}
