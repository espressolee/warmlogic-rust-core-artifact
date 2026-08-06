//! rust_core/src/rate_limit.rs
//! API Rate Limiting for DoS Prevention.
//!
//! Implements token bucket rate limiting for API endpoints.
//! Prevents resource exhaustion from excessive requests.

use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{Duration, Instant};

// ============================================================================
// CONFIGURATION
// ============================================================================

/// Default rate limit: 100 requests per second
pub const DEFAULT_REQUESTS_PER_SECOND: u32 = 100;

/// Default burst capacity: 200 requests
pub const DEFAULT_BURST_CAPACITY: u32 = 200;

/// Minimum interval between refills (milliseconds)
pub const MIN_REFILL_INTERVAL_MS: u64 = 10;

/// Maximum number of tracked clients (to prevent memory exhaustion)
pub const MAX_TRACKED_CLIENTS: usize = 100_000;

/// Time to keep inactive clients before cleanup (seconds)
pub const CLIENT_EXPIRY_SECONDS: u64 = 3600;

// ============================================================================
// RATE LIMIT RESULT
// ============================================================================

/// Result of a rate limit check
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RateLimitResult {
    /// Request allowed
    Allowed {
        /// Remaining tokens
        remaining: u32,
        /// Time until bucket refills (milliseconds)
        reset_ms: u64,
    },
    /// Request denied - rate limit exceeded
    Denied {
        /// Time until next token available (milliseconds)
        retry_after_ms: u64,
        /// Maximum requests per second
        limit: u32,
    },
}

impl RateLimitResult {
    /// Check if the request is allowed
    #[must_use]
    pub fn is_allowed(&self) -> bool {
        matches!(self, RateLimitResult::Allowed { .. })
    }
}

// ============================================================================
// TOKEN BUCKET
// ============================================================================

/// Token bucket for rate limiting
#[derive(Debug, Clone)]
pub struct TokenBucket {
    /// Current number of tokens
    tokens: f64,
    /// Maximum tokens (burst capacity)
    capacity: u32,
    /// Tokens added per second
    rate: u32,
    /// Last time tokens were refilled
    last_refill: Instant,
}

impl TokenBucket {
    /// Create a new token bucket
    #[must_use]
    pub fn new(rate: u32, capacity: u32) -> Self {
        Self {
            tokens: capacity as f64,
            capacity,
            rate,
            last_refill: Instant::now(),
        }
    }

    /// Try to consume a token, returning the result
    pub fn try_consume(&mut self) -> RateLimitResult {
        self.refill();

        if self.tokens >= 1.0 {
            self.tokens -= 1.0;
            RateLimitResult::Allowed {
                remaining: self.tokens as u32,
                reset_ms: self.time_to_full_ms(),
            }
        } else {
            RateLimitResult::Denied {
                retry_after_ms: self.time_to_next_token_ms(),
                limit: self.rate,
            }
        }
    }

    /// Try to consume N tokens at once
    pub fn try_consume_n(&mut self, n: u32) -> RateLimitResult {
        self.refill();

        let n_f64 = n as f64;
        if self.tokens >= n_f64 {
            self.tokens -= n_f64;
            RateLimitResult::Allowed {
                remaining: self.tokens as u32,
                reset_ms: self.time_to_full_ms(),
            }
        } else {
            RateLimitResult::Denied {
                retry_after_ms: self.time_to_tokens_ms(n),
                limit: self.rate,
            }
        }
    }

    /// Refill tokens based on elapsed time
    fn refill(&mut self) {
        let now = Instant::now();
        let elapsed = now.duration_since(self.last_refill);

        // Calculate tokens to add
        let tokens_to_add = elapsed.as_secs_f64() * self.rate as f64;

        if tokens_to_add >= 0.01 {
            // Only update if meaningful amount
            self.tokens = (self.tokens + tokens_to_add).min(self.capacity as f64);
            self.last_refill = now;
        }
    }

    /// Calculate time until next token is available
    fn time_to_next_token_ms(&self) -> u64 {
        if self.tokens >= 1.0 {
            return 0;
        }
        let needed = 1.0 - self.tokens;
        let seconds = needed / self.rate as f64;
        (seconds * 1000.0).ceil() as u64
    }

    /// Calculate time until N tokens are available
    fn time_to_tokens_ms(&self, n: u32) -> u64 {
        let n_f64 = n as f64;
        if self.tokens >= n_f64 {
            return 0;
        }
        let needed = n_f64 - self.tokens;
        let seconds = needed / self.rate as f64;
        (seconds * 1000.0).ceil() as u64
    }

    /// Calculate time until bucket is full
    fn time_to_full_ms(&self) -> u64 {
        let needed = self.capacity as f64 - self.tokens;
        if needed <= 0.0 {
            return 0;
        }
        let seconds = needed / self.rate as f64;
        (seconds * 1000.0).ceil() as u64
    }

    /// Get current token count
    pub fn available(&mut self) -> u32 {
        self.refill();
        self.tokens as u32
    }

    /// Check time since last activity
    #[must_use]
    pub fn time_since_last_refill(&self) -> Duration {
        self.last_refill.elapsed()
    }
}

// ============================================================================
// RATE LIMITER
// ============================================================================

/// Client entry with bucket and metadata
#[derive(Debug)]
struct ClientEntry {
    bucket: TokenBucket,
    #[allow(dead_code)]
    created_at: Instant,
}

/// Thread-safe rate limiter for multiple clients
#[derive(Debug)]
pub struct RateLimiter {
    /// Per-client token buckets
    clients: Mutex<HashMap<String, ClientEntry>>,
    /// Default rate (requests per second)
    default_rate: u32,
    /// Default burst capacity
    default_capacity: u32,
    /// Client expiry time
    expiry: Duration,
}

impl RateLimiter {
    /// Create a new rate limiter with default settings
    #[must_use]
    pub fn new() -> Self {
        Self::with_config(DEFAULT_REQUESTS_PER_SECOND, DEFAULT_BURST_CAPACITY)
    }

    /// Create a rate limiter with custom configuration
    #[must_use]
    pub fn with_config(rate: u32, capacity: u32) -> Self {
        Self {
            clients: Mutex::new(HashMap::new()),
            default_rate: rate,
            default_capacity: capacity,
            expiry: Duration::from_secs(CLIENT_EXPIRY_SECONDS),
        }
    }

    /// Check rate limit for a client
    pub fn check(&self, client_id: &str) -> RateLimitResult {
        let mut clients = self.clients.lock().unwrap();

        // Cleanup expired clients periodically
        if clients.len() > MAX_TRACKED_CLIENTS / 2 {
            self.cleanup_expired(&mut clients);
        }

        // Get or create client entry
        let entry = clients
            .entry(client_id.to_string())
            .or_insert_with(|| ClientEntry {
                bucket: TokenBucket::new(self.default_rate, self.default_capacity),
                created_at: Instant::now(),
            });

        entry.bucket.try_consume()
    }

    /// Check rate limit for a client with N tokens
    pub fn check_n(&self, client_id: &str, n: u32) -> RateLimitResult {
        let mut clients = self.clients.lock().unwrap();

        let entry = clients
            .entry(client_id.to_string())
            .or_insert_with(|| ClientEntry {
                bucket: TokenBucket::new(self.default_rate, self.default_capacity),
                created_at: Instant::now(),
            });

        entry.bucket.try_consume_n(n)
    }

    /// Get remaining tokens for a client without consuming
    pub fn remaining(&self, client_id: &str) -> u32 {
        let mut clients = self.clients.lock().unwrap();

        if let Some(entry) = clients.get_mut(client_id) {
            entry.bucket.available()
        } else {
            self.default_capacity
        }
    }

    /// Cleanup expired client entries
    fn cleanup_expired(&self, clients: &mut HashMap<String, ClientEntry>) {
        let now = Instant::now();
        clients.retain(|_, entry| {
            let elapsed = now.duration_since(entry.bucket.last_refill);
            elapsed < self.expiry
        });
    }

    /// Force cleanup of all expired entries
    pub fn force_cleanup(&self) {
        let mut clients = self.clients.lock().unwrap();
        self.cleanup_expired(&mut clients);
    }

    /// Get current number of tracked clients
    pub fn client_count(&self) -> usize {
        self.clients.lock().unwrap().len()
    }

    /// Clear all client tracking data
    pub fn clear(&self) {
        self.clients.lock().unwrap().clear();
    }
}

impl Default for RateLimiter {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// ENDPOINT-SPECIFIC RATE LIMITER
// ============================================================================

/// Rate limits by endpoint
#[derive(Debug, Clone)]
pub struct EndpointConfig {
    pub rate: u32,
    pub capacity: u32,
}

/// Rate limiter with per-endpoint configuration
#[derive(Debug)]
pub struct EndpointRateLimiter {
    /// Per-endpoint rate limiters
    endpoints: HashMap<String, RateLimiter>,
    /// Default configuration
    default_config: EndpointConfig,
}

impl EndpointRateLimiter {
    /// Create a new endpoint rate limiter
    #[must_use]
    pub fn new() -> Self {
        Self {
            endpoints: HashMap::new(),
            default_config: EndpointConfig {
                rate: DEFAULT_REQUESTS_PER_SECOND,
                capacity: DEFAULT_BURST_CAPACITY,
            },
        }
    }

    /// Configure rate limit for a specific endpoint
    pub fn configure_endpoint(&mut self, endpoint: &str, rate: u32, capacity: u32) {
        self.endpoints.insert(
            endpoint.to_string(),
            RateLimiter::with_config(rate, capacity),
        );
    }

    /// Check rate limit for client on endpoint
    #[must_use]
    pub fn check(&self, endpoint: &str, client_id: &str) -> RateLimitResult {
        if let Some(limiter) = self.endpoints.get(endpoint) {
            limiter.check(client_id)
        } else {
            // Use default rate limiter (create one if needed)
            RateLimiter::with_config(self.default_config.rate, self.default_config.capacity)
                .check(client_id)
        }
    }

    /// Get total client count across all endpoints
    #[must_use]
    pub fn total_client_count(&self) -> usize {
        self.endpoints.values().map(|l| l.client_count()).sum()
    }
}

impl Default for EndpointRateLimiter {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// GLOBAL RATE LIMITER (LAZY STATIC)
// ============================================================================

lazy_static::lazy_static! {
    /// Global rate limiter instance
    pub static ref GLOBAL_LIMITER: RateLimiter = RateLimiter::new();
}

/// Check rate limit using global limiter
#[must_use]
pub fn check_rate_limit(client_id: &str) -> RateLimitResult {
    GLOBAL_LIMITER.check(client_id)
}

/// Check if request is allowed using global limiter
#[must_use]
pub fn is_allowed(client_id: &str) -> bool {
    GLOBAL_LIMITER.check(client_id).is_allowed()
}

// ============================================================================
// TESTS
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;
    use std::time::Duration;

    #[test]
    fn test_token_bucket_initial_capacity() {
        let mut bucket = TokenBucket::new(10, 100);
        assert_eq!(bucket.available(), 100);
    }

    #[test]
    fn test_token_bucket_consume() {
        let mut bucket = TokenBucket::new(10, 100);

        let result = bucket.try_consume();
        assert!(result.is_allowed());

        if let RateLimitResult::Allowed { remaining, .. } = result {
            assert_eq!(remaining, 99);
        }
    }

    #[test]
    fn test_token_bucket_exhaust() {
        let mut bucket = TokenBucket::new(1, 3); // 1 token/sec, 3 capacity

        // Consume all tokens
        assert!(bucket.try_consume().is_allowed());
        assert!(bucket.try_consume().is_allowed());
        assert!(bucket.try_consume().is_allowed());

        // Next should be denied
        let result = bucket.try_consume();
        assert!(!result.is_allowed());

        if let RateLimitResult::Denied { limit, .. } = result {
            assert_eq!(limit, 1);
        }
    }

    #[test]
    fn test_token_bucket_refill() {
        let mut bucket = TokenBucket::new(100, 10); // 100 tokens/sec, 10 capacity

        // Consume all tokens
        for _ in 0..10 {
            bucket.try_consume();
        }
        assert_eq!(bucket.available(), 0);

        // Wait for refill (at least 50ms = 5 tokens at 100/sec)
        thread::sleep(Duration::from_millis(60));

        let available = bucket.available();
        assert!(
            available >= 5,
            "Expected at least 5 tokens, got {}",
            available
        );
    }

    #[test]
    fn test_rate_limiter_multiple_clients() {
        let limiter = RateLimiter::with_config(10, 5);

        // Different clients should have separate buckets
        let result1 = limiter.check("client1");
        let result2 = limiter.check("client2");

        assert!(result1.is_allowed());
        assert!(result2.is_allowed());

        // Each should have 4 remaining
        assert_eq!(limiter.remaining("client1"), 4);
        assert_eq!(limiter.remaining("client2"), 4);
    }

    #[test]
    fn test_rate_limiter_client_tracking() {
        let limiter = RateLimiter::new();

        limiter.check("client1");
        limiter.check("client2");
        limiter.check("client3");

        assert_eq!(limiter.client_count(), 3);

        limiter.clear();
        assert_eq!(limiter.client_count(), 0);
    }

    #[test]
    fn test_rate_limit_result_is_allowed() {
        let allowed = RateLimitResult::Allowed {
            remaining: 10,
            reset_ms: 1000,
        };
        assert!(allowed.is_allowed());

        let denied = RateLimitResult::Denied {
            retry_after_ms: 100,
            limit: 10,
        };
        assert!(!denied.is_allowed());
    }

    #[test]
    fn test_consume_n_tokens() {
        let mut bucket = TokenBucket::new(10, 100);

        // Consume 50 tokens
        let result = bucket.try_consume_n(50);
        assert!(result.is_allowed());
        assert_eq!(bucket.available(), 50);

        // Try to consume 60 more (should fail)
        let result = bucket.try_consume_n(60);
        assert!(!result.is_allowed());

        // Consume exactly remaining
        let result = bucket.try_consume_n(50);
        assert!(result.is_allowed());
        assert_eq!(bucket.available(), 0);
    }

    #[test]
    fn test_endpoint_rate_limiter() {
        let mut limiter = EndpointRateLimiter::new();

        // Configure different limits for different endpoints
        limiter.configure_endpoint("/api/fast", 1000, 200);
        limiter.configure_endpoint("/api/slow", 10, 5);

        // Fast endpoint should allow more
        let fast_result = limiter.check("/api/fast", "client1");
        assert!(fast_result.is_allowed());

        // Slow endpoint has lower limit
        let slow_result = limiter.check("/api/slow", "client1");
        assert!(slow_result.is_allowed());
    }

    #[test]
    fn test_global_limiter() {
        let result = check_rate_limit("test_client");
        assert!(result.is_allowed());

        assert!(is_allowed("test_client"));
    }

    #[test]
    fn test_retry_after_calculation() {
        let mut bucket = TokenBucket::new(10, 1); // 10 tokens/sec, 1 capacity

        // Consume the only token
        bucket.try_consume();

        // Next request should give retry_after
        let result = bucket.try_consume();
        if let RateLimitResult::Denied { retry_after_ms, .. } = result {
            // Should be around 100ms (1 token at 10/sec)
            assert!(
                retry_after_ms <= 150,
                "retry_after_ms {} too high",
                retry_after_ms
            );
            assert!(
                retry_after_ms >= 50,
                "retry_after_ms {} too low",
                retry_after_ms
            );
        } else {
            panic!("Expected Denied result");
        }
    }
}
