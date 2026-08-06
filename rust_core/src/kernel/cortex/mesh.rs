use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CognitiveInsight {
    pub intent: String,
    pub plan: String,
    pub origin_node: crate::net::kademlia::NodeId,
    pub timestamp: u64,
    pub confidence: f64,
}

#[derive(Debug, Clone)]
pub struct InsightCacheEntry {
    pub insight: CognitiveInsight,
    pub access_count: u64,
}

#[derive(Debug, Clone)]
pub struct NeuralMesh {
    pub local_node_id: crate::net::kademlia::NodeId,
    pub cache: std::collections::HashMap<u64, InsightCacheEntry>,
    pub outbound_queue: Vec<CognitiveInsight>,
    pub max_cache_size: usize,
}

impl NeuralMesh {
    #[must_use]
    pub fn new(local_node_id: crate::net::kademlia::NodeId, max_cache_size: usize) -> Self {
        Self {
            local_node_id,
            cache: std::collections::HashMap::new(),
            outbound_queue: Vec::new(),
            max_cache_size,
        }
    }

    #[must_use]
    pub fn hash_intent(intent: &str) -> u64 {
        let mut hash = 0xcbf29ce484222325u64;
        let prime = 0x100000001b3u64;
        for byte in intent.bytes() {
            hash ^= byte as u64;
            hash = hash.wrapping_mul(prime);
        }
        hash
    }

    pub fn publish_insight(&mut self, intent: &str, plan: &str, confidence: f64) {
        let insight = CognitiveInsight {
            intent: intent.to_string(),
            plan: plan.to_string(),
            origin_node: self.local_node_id.clone(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
            confidence,
        };

        let key = Self::hash_intent(intent);

        if self.cache.len() >= self.max_cache_size {
            self.evict_lru();
        }
        self.cache.insert(
            key,
            InsightCacheEntry {
                insight: insight.clone(),
                access_count: 0,
            },
        );

        self.outbound_queue.push(insight.clone());

        println!(
            "📡 [NeuralMesh] Published insight: '{}' -> {} (confidence: {:.2})",
            if intent.len() > 40 {
                &intent[..40]
            } else {
                intent
            },
            if plan.len() > 40 { &plan[..40] } else { plan },
            confidence
        );
    }

    pub fn lookup_insight(&mut self, intent: &str) -> Option<CognitiveInsight> {
        let key = Self::hash_intent(intent);
        if let Some(entry) = self.cache.get_mut(&key) {
            entry.access_count += 1;
            Some(entry.insight.clone())
        } else {
            None
        }
    }

    pub fn receive_insight(&mut self, insight: CognitiveInsight) {
        if insight.origin_node == self.local_node_id {
            return;
        }
        let key = Self::hash_intent(&insight.intent);
        if self.cache.len() >= self.max_cache_size && !self.cache.contains_key(&key) {
            self.evict_lru();
        }
        self.cache.insert(
            key,
            InsightCacheEntry {
                insight: insight.clone(),
                access_count: 0,
            },
        );
        println!(
            "🧠 [NeuralMesh] Received swarm insight: '{}'",
            if insight.intent.len() > 40 {
                &insight.intent[..40]
            } else {
                &insight.intent
            }
        );
    }

    fn evict_lru(&mut self) {
        if let Some(min_key) = self
            .cache
            .iter()
            .min_by_key(|(_, v)| v.access_count)
            .map(|(k, _)| *k)
        {
            self.cache.remove(&min_key);
        }
    }

    pub fn drain_outbound(&mut self) -> Vec<CognitiveInsight> {
        std::mem::take(&mut self.outbound_queue)
    }
}
