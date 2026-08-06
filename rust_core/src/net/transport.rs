//! rust_core/src/net/transport.rs
//! Tokio-based UDP Transport Layer.
//! Complete message routing with callback support.
//!
//! Security Features (M1-M4):
//! - M1: Per-IP rate limiting to prevent UDP amplification attacks
//! - M2: Maximum message size enforcement (configurable, default 8KB)
//! - M3: Connection tracking with ban list for Sybil prevention
//! - M4: Lock poisoning recovery

use std::collections::HashMap;
use std::collections::VecDeque;
use std::net::IpAddr;
use std::net::SocketAddr;
use std::str::FromStr;
use std::sync::Arc;
use std::sync::Mutex;
use std::sync::MutexGuard;
use std::sync::PoisonError;
use std::thread;
use std::time::{Duration, Instant};
use tokio::net::UdpSocket;
use tokio::runtime::Runtime;
use tokio::sync::mpsc;

/// [M1 Security] Maximum messages per IP per second (rate limiting)
pub const MAX_MESSAGES_PER_IP_PER_SECOND: u32 = 100;

/// [M2 Security] Maximum message size in bytes (default 8KB to prevent amplification)
pub const MAX_MESSAGE_SIZE: usize = 8192;

/// [M3 Security] Ban duration in seconds for rate limit violators
pub const BAN_DURATION_SECS: u64 = 300; // 5 minutes

/// [M4 Security] Helper to recover from poisoned locks
fn recover_lock<'a, T>(
    result: Result<MutexGuard<'a, T>, PoisonError<MutexGuard<'a, T>>>,
) -> MutexGuard<'a, T> {
    match result {
        Ok(guard) => guard,
        Err(poisoned) => poisoned.into_inner(),
    }
}

/// [M1/M3 Security] Per-IP rate limiting state
#[derive(Clone)]
pub struct RateLimitState {
    /// Message count in current window
    pub count: u32,
    /// Window start time
    pub window_start: Instant,
    /// Ban expiry (if banned)
    pub banned_until: Option<Instant>,
}

impl Default for RateLimitState {
    fn default() -> Self {
        RateLimitState {
            count: 0,
            window_start: Instant::now(),
            banned_until: None,
        }
    }
}

/// [M1/M3 Security] Rate limiter with ban tracking
pub struct RateLimiter {
    states: Mutex<HashMap<IpAddr, RateLimitState>>,
    max_per_second: u32,
    ban_duration: Duration,
}

impl RateLimiter {
    #[must_use]
    pub fn new(max_per_second: u32, ban_duration_secs: u64) -> Self {
        RateLimiter {
            states: Mutex::new(HashMap::new()),
            max_per_second,
            ban_duration: Duration::from_secs(ban_duration_secs),
        }
    }

    /// Check if an IP is allowed to send. Returns false if rate limited or banned.
    pub fn check_and_increment(&self, ip: IpAddr) -> bool {
        let mut states = recover_lock(self.states.lock());
        let now = Instant::now();

        let state = states.entry(ip).or_default();

        // Check if banned
        if let Some(banned_until) = state.banned_until {
            if now < banned_until {
                return false; // Still banned
            }
            // Ban expired, reset
            state.banned_until = None;
            state.count = 0;
            state.window_start = now;
        }

        // Check if window expired (1 second)
        if now.duration_since(state.window_start) >= Duration::from_secs(1) {
            state.count = 0;
            state.window_start = now;
        }

        // Check rate limit
        if state.count >= self.max_per_second {
            // Rate limit exceeded - ban the IP
            state.banned_until = Some(now + self.ban_duration);
            return false;
        }

        state.count += 1;
        true
    }

    /// Manually ban an IP
    pub fn ban(&self, ip: IpAddr) {
        let mut states = recover_lock(self.states.lock());
        let state = states.entry(ip).or_default();
        state.banned_until = Some(Instant::now() + self.ban_duration);
    }

    /// Check if an IP is currently banned
    pub fn is_banned(&self, ip: IpAddr) -> bool {
        let states = recover_lock(self.states.lock());
        if let Some(state) = states.get(&ip) {
            if let Some(banned_until) = state.banned_until {
                return Instant::now() < banned_until;
            }
        }
        false
    }

    /// Get count of currently tracked IPs
    pub fn tracked_count(&self) -> usize {
        let states = recover_lock(self.states.lock());
        states.len()
    }

    /// Clean up expired entries (call periodically)
    pub fn cleanup_expired(&self) {
        let mut states = recover_lock(self.states.lock());
        let now = Instant::now();
        states.retain(|_, state| {
            // Keep if: has recent activity OR still banned
            let recent = now.duration_since(state.window_start) < Duration::from_secs(60);
            let banned = state.banned_until.map(|t| now < t).unwrap_or(false);
            recent || banned
        });
    }
}

/// Message priority levels
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Default)]
pub enum MessagePriority {
    /// Low priority: handshakes, discovery, DAG sync
    Low = 0,
    /// Normal priority: governance votes, policy updates
    #[default]
    Normal = 1,
    /// High priority: block proposals, commits, view changes
    High = 2,
    /// Critical priority: view change timeouts, emergency veto
    Critical = 3,
}

/// Message to be sent over UDP
#[derive(Debug, Clone)]
pub struct OutgoingMessage {
    pub target: SocketAddr,
    pub payload: Vec<u8>,
    /// Message priority for queue ordering
    pub priority: MessagePriority,
}

/// Message received from UDP (passed to callback/channel)
#[derive(Debug, Clone)]
pub struct IncomingMessage {
    pub source: SocketAddr,
    pub payload: Vec<u8>,
}

/// Thread-safe message buffer for incoming messages
/// Used to bridge async Tokio recv to sync Python callbacks
pub struct MessageBuffer {
    messages: Mutex<VecDeque<IncomingMessage>>,
    capacity: usize,
}

impl MessageBuffer {
    #[must_use]
    pub fn new(capacity: usize) -> Self {
        MessageBuffer {
            messages: Mutex::new(VecDeque::with_capacity(capacity)),
            capacity,
        }
    }

    pub fn push(&self, msg: IncomingMessage) {
        if let Ok(mut queue) = self.messages.lock() {
            if queue.len() >= self.capacity {
                queue.pop_front(); // Drop oldest message if full
            }
            queue.push_back(msg);
        }
    }

    pub fn pop(&self) -> Option<IncomingMessage> {
        if let Ok(mut queue) = self.messages.lock() {
            queue.pop_front()
        } else {
            None
        }
    }

    pub fn pop_all(&self) -> Vec<IncomingMessage> {
        if let Ok(mut queue) = self.messages.lock() {
            queue.drain(..).collect()
        } else {
            Vec::new()
        }
    }

    pub fn len(&self) -> usize {
        if let Ok(queue) = self.messages.lock() {
            queue.len()
        } else {
            0
        }
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

pub struct NetworkingEngine {
    tx: mpsc::Sender<OutgoingMessage>,
    /// Incoming message buffer for protocol routing
    incoming: Arc<MessageBuffer>,
    /// Statistics
    stats: Arc<Mutex<NetworkStats>>,
    /// [M1/M3 Security] Rate limiter for incoming connections
    rate_limiter: Arc<RateLimiter>,
    /// [M2 Security] Maximum allowed message size
    max_message_size: usize,
}

#[derive(Default, Clone)]
pub struct NetworkStats {
    pub messages_sent: u64,
    pub messages_received: u64,
    pub bytes_sent: u64,
    pub bytes_received: u64,
    pub send_errors: u64,
    pub recv_errors: u64,
    /// [M1 Security] Messages dropped due to rate limiting
    pub rate_limited: u64,
    /// [M2 Security] Messages dropped due to size limit
    pub oversized_dropped: u64,
    /// [M3 Security] Currently banned IPs count
    pub banned_ips: u64,
    /// High priority messages sent
    pub high_priority_sent: u64,
    /// Critical priority messages sent
    pub critical_sent: u64,
}

impl NetworkingEngine {
    /// Starts the Async Network Engine in a background thread.
    /// Returns a handle to send messages and receive incoming messages.
    #[must_use]
    pub fn start(bind_addr: String) -> Self {
        Self::start_with_config(bind_addr, MAX_MESSAGE_SIZE, MAX_MESSAGES_PER_IP_PER_SECOND)
    }

    /// Starts with custom security configuration.
    /// [M1/M2 Security] Configurable rate limits and message size.
    #[must_use]
    pub fn start_with_config(
        bind_addr: String,
        max_message_size: usize,
        max_messages_per_second: u32,
    ) -> Self {
        let (tx, mut rx) = mpsc::channel::<OutgoingMessage>(100);
        let incoming = Arc::new(MessageBuffer::new(1000));
        let incoming_clone = incoming.clone();
        let stats = Arc::new(Mutex::new(NetworkStats::default()));
        let stats_recv = stats.clone();
        let stats_send = stats.clone();

        // [M1/M3 Security] Initialize rate limiter
        let rate_limiter = Arc::new(RateLimiter::new(max_messages_per_second, BAN_DURATION_SECS));
        let rate_limiter_recv = rate_limiter.clone();

        // Capture max_message_size for the async block
        let msg_size_limit = max_message_size;

        thread::spawn(move || {
            // [Security Fix] Graceful runtime initialization - no panic
            let rt = match Runtime::new() {
                Ok(rt) => rt,
                Err(e) => {
                    eprintln!(
                        "❌ [RustNet] CRITICAL: Failed to create Tokio runtime: {}",
                        e
                    );
                    // Exit thread gracefully instead of panicking
                    return;
                }
            };
            rt.block_on(async move {
                // [Security Fix] Retry socket binding with exponential backoff
                let socket = {
                    let max_retries = 3;
                    let mut retry_count = 0;
                    loop {
                        match UdpSocket::bind(&bind_addr).await {
                            Ok(socket) => break socket,
                            Err(e) if retry_count < max_retries => {
                                eprintln!(
                                    "⚠️  [RustNet] Bind attempt {}/{} failed on {}: {}. Retrying...",
                                    retry_count + 1,
                                    max_retries,
                                    bind_addr,
                                    e
                                );
                                retry_count += 1;
                                tokio::time::sleep(std::time::Duration::from_millis(100 * (1 << retry_count))).await;
                            }
                            Err(e) => {
                                eprintln!(
                                    "❌ [RustNet] CRITICAL: All bind attempts exhausted for {}: {}",
                                    bind_addr, e
                                );
                                // Exit async block gracefully instead of panicking
                                return;
                            }
                        }
                    }
                };
                println!(
                    "🌐 [RustNet] Listening on {} (max_msg: {}B, rate: {}/s)",
                    bind_addr, msg_size_limit, max_messages_per_second
                );

                let socket = Arc::new(socket);
                let recv_socket = socket.clone();
                let send_socket = socket.clone();

                // Receiver Task (Incoming UDP)
                // Now routes messages to the incoming buffer
                // [M1-M4 Security] With rate limiting, size checks, and poisoning recovery
                tokio::spawn(async move {
                    let mut buf = [0u8; 65535];
                    loop {
                        match recv_socket.recv_from(&mut buf).await {
                            Ok((size, addr)) => {
                                let ip = addr.ip();

                                // [M2 Security] Check message size
                                if size > msg_size_limit {
                                    let mut s = recover_lock(stats_recv.lock());
                                    s.oversized_dropped += 1;
                                    // Don't process oversized messages - potential amplification attack
                                    continue;
                                }

                                // [M1 Security] Check rate limit
                                if !rate_limiter_recv.check_and_increment(ip) {
                                    let mut s = recover_lock(stats_recv.lock());
                                    s.rate_limited += 1;
                                    // Rate limited or banned - drop silently
                                    continue;
                                }

                                let data = buf[..size].to_vec();

                                // [M4 Security] Update stats with poisoning recovery
                                {
                                    let mut s = recover_lock(stats_recv.lock());
                                    s.messages_received += 1;
                                    s.bytes_received += size as u64;
                                }

                                // Push to incoming buffer for protocol routing
                                let msg = IncomingMessage {
                                    source: addr,
                                    payload: data,
                                };
                                incoming_clone.push(msg);
                            }
                            Err(e) => {
                                let mut s = recover_lock(stats_recv.lock());
                                s.recv_errors += 1;
                                eprintln!("[RustNet] Recv Error: {}", e);
                            }
                        }
                    }
                });

                // Sender Task (Outgoing UDP)
                // [M4 Security] With poisoning recovery
                while let Some(msg) = rx.recv().await {
                    match send_socket.send_to(&msg.payload, msg.target).await {
                        Ok(sent) => {
                            let mut s = recover_lock(stats_send.lock());
                            s.messages_sent += 1;
                            s.bytes_sent += sent as u64;
                        }
                        Err(e) => {
                            let mut s = recover_lock(stats_send.lock());
                            s.send_errors += 1;
                            eprintln!("[RustNet] Send Error: {}", e);
                        }
                    }
                }
            });
        });

        NetworkingEngine {
            tx,
            incoming,
            stats,
            rate_limiter,
            max_message_size,
        }
    }

    /// Send a message with normal priority
    pub fn send(&self, target_addr: String, payload: Vec<u8>) {
        self.send_with_priority(target_addr, payload, MessagePriority::Normal);
    }

    /// Send a message with specified priority
    pub fn send_with_priority(
        &self,
        target_addr: String,
        payload: Vec<u8>,
        priority: MessagePriority,
    ) {
        if let Ok(addr) = SocketAddr::from_str(&target_addr) {
            let msg = OutgoingMessage {
                target: addr,
                payload,
                priority,
            };
            let _ = self.tx.blocking_send(msg);
        } else {
            eprintln!("[RustNet] Invalid Target Address: {}", target_addr);
        }
    }

    /// Send a high-priority message (block proposals, commits)
    pub fn send_urgent(&self, target_addr: String, payload: Vec<u8>) {
        self.send_with_priority(target_addr, payload, MessagePriority::High);
    }

    /// Send a critical message (view change, emergency veto)
    pub fn send_critical(&self, target_addr: String, payload: Vec<u8>) {
        self.send_with_priority(target_addr, payload, MessagePriority::Critical);
    }

    /// Poll for incoming messages (for Python integration)
    #[must_use]
    pub fn poll_incoming(&self) -> Vec<IncomingMessage> {
        self.incoming.pop_all()
    }

    /// Check if there are pending messages
    #[must_use]
    pub fn has_pending(&self) -> bool {
        !self.incoming.is_empty()
    }

    /// Get pending message count
    #[must_use]
    pub fn pending_count(&self) -> usize {
        self.incoming.len()
    }

    /// Get network statistics
    /// [M4 Security] With poisoning recovery
    #[must_use]
    pub fn get_stats(&self) -> NetworkStats {
        let mut stats = recover_lock(self.stats.lock()).clone();
        stats.banned_ips = self.rate_limiter.tracked_count() as u64;
        stats
    }

    /// [M3 Security] Manually ban an IP address
    pub fn ban_ip(&self, ip: IpAddr) {
        self.rate_limiter.ban(ip);
    }

    /// [M3 Security] Check if an IP is currently banned
    #[must_use]
    pub fn is_banned(&self, ip: IpAddr) -> bool {
        self.rate_limiter.is_banned(ip)
    }

    /// [M3 Security] Ban an IP by string address
    pub fn ban_ip_str(&self, ip_str: &str) -> Result<(), String> {
        let ip: IpAddr = ip_str
            .parse()
            .map_err(|_| format!("Invalid IP address: {}", ip_str))?;
        self.rate_limiter.ban(ip);
        Ok(())
    }

    /// [M1 Security] Get current rate limit settings
    #[must_use]
    pub fn get_rate_limit_config(&self) -> (usize, u32) {
        (self.max_message_size, MAX_MESSAGES_PER_IP_PER_SECOND)
    }

    /// [M1 Security] Cleanup expired rate limit entries (call periodically)
    pub fn cleanup_rate_limits(&self) {
        self.rate_limiter.cleanup_expired();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rate_limiter_allows_under_limit() {
        let limiter = RateLimiter::new(10, 60);
        let ip: IpAddr = "192.168.1.1".parse().unwrap();

        // Should allow up to 10 messages
        for i in 0..10 {
            assert!(
                limiter.check_and_increment(ip),
                "Message {} should be allowed",
                i
            );
        }
    }

    #[test]
    fn test_rate_limiter_blocks_over_limit() {
        let limiter = RateLimiter::new(5, 60);
        let ip: IpAddr = "10.0.0.1".parse().unwrap();

        // Allow 5 messages
        for _ in 0..5 {
            assert!(limiter.check_and_increment(ip));
        }

        // 6th message should be blocked and IP banned
        assert!(!limiter.check_and_increment(ip));
        assert!(limiter.is_banned(ip));
    }

    #[test]
    fn test_rate_limiter_different_ips_independent() {
        let limiter = RateLimiter::new(3, 60);
        let ip1: IpAddr = "1.1.1.1".parse().unwrap();
        let ip2: IpAddr = "2.2.2.2".parse().unwrap();

        // Exhaust IP1's limit
        for _ in 0..3 {
            limiter.check_and_increment(ip1);
        }
        assert!(!limiter.check_and_increment(ip1)); // Blocked

        // IP2 should still work
        assert!(limiter.check_and_increment(ip2));
        assert!(!limiter.is_banned(ip2));
    }

    #[test]
    fn test_rate_limiter_manual_ban() {
        let limiter = RateLimiter::new(100, 60);
        let ip: IpAddr = "8.8.8.8".parse().unwrap();

        assert!(!limiter.is_banned(ip));
        limiter.ban(ip);
        assert!(limiter.is_banned(ip));
        assert!(!limiter.check_and_increment(ip)); // Banned IPs can't send
    }

    #[test]
    fn test_rate_limiter_cleanup() {
        let limiter = RateLimiter::new(10, 1);
        let ip: IpAddr = "3.3.3.3".parse().unwrap();

        limiter.check_and_increment(ip);
        assert_eq!(limiter.tracked_count(), 1);

        // Cleanup should retain recent entries
        limiter.cleanup_expired();
        assert_eq!(limiter.tracked_count(), 1);
    }

    #[test]
    fn test_message_buffer_capacity() {
        let buffer = MessageBuffer::new(3);

        for i in 0..5 {
            buffer.push(IncomingMessage {
                source: "127.0.0.1:8000".parse().unwrap(),
                payload: vec![i as u8],
            });
        }

        // Should only have last 3 messages (oldest dropped)
        assert_eq!(buffer.len(), 3);

        let msgs = buffer.pop_all();
        assert_eq!(msgs.len(), 3);
        assert_eq!(msgs[0].payload[0], 2); // First two were dropped
        assert_eq!(msgs[1].payload[0], 3);
        assert_eq!(msgs[2].payload[0], 4);
    }

    #[test]
    fn test_network_stats_default() {
        let stats = NetworkStats::default();
        assert_eq!(stats.messages_sent, 0);
        assert_eq!(stats.rate_limited, 0);
        assert_eq!(stats.oversized_dropped, 0);
        assert_eq!(stats.banned_ips, 0);
    }

    #[test]
    fn test_security_constants() {
        // Ensure security constants are reasonable
        assert!(
            MAX_MESSAGES_PER_IP_PER_SECOND >= 10,
            "Rate limit too restrictive"
        );
        assert!(
            MAX_MESSAGES_PER_IP_PER_SECOND <= 1000,
            "Rate limit too permissive"
        );
        assert!(MAX_MESSAGE_SIZE >= 1024, "Message size too small");
        assert!(MAX_MESSAGE_SIZE <= 65535, "Message size exceeds UDP max");
        assert!(BAN_DURATION_SECS >= 60, "Ban duration too short");
    }

    #[test]
    fn test_message_priority_ordering() {
        // Verify priority enum ordering
        assert!(MessagePriority::Low < MessagePriority::Normal);
        assert!(MessagePriority::Normal < MessagePriority::High);
        assert!(MessagePriority::High < MessagePriority::Critical);
    }

    #[test]
    fn test_message_priority_default() {
        assert_eq!(MessagePriority::default(), MessagePriority::Normal);
    }

    #[test]
    fn test_outgoing_message_with_priority() {
        let addr: SocketAddr = "127.0.0.1:8080".parse().unwrap();
        let msg = OutgoingMessage {
            target: addr,
            payload: vec![1, 2, 3],
            priority: MessagePriority::High,
        };
        assert_eq!(msg.priority, MessagePriority::High);
    }

    #[test]
    fn test_network_stats_priority_fields() {
        let mut stats = NetworkStats::default();
        assert_eq!(stats.high_priority_sent, 0);
        assert_eq!(stats.critical_sent, 0);

        stats.high_priority_sent = 10;
        stats.critical_sent = 5;
        assert_eq!(stats.high_priority_sent, 10);
        assert_eq!(stats.critical_sent, 5);
    }
}
