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

import time
import threading
from typing import Dict, Tuple

class TokenBucketRateLimiter:
    """
    Thread-safe Token Bucket Rate Limiter.
    Ensures 'Structural Excellence' by preventing DoS attacks.
    """
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_refill_time)
        self.lock = threading.Lock()

    def consume(self, key: str, tokens: int = 1) -> bool:
        with self.lock:
            now = time.time()
            if key not in self.buckets:
                self.buckets[key] = (self.capacity, now)

            current_tokens, last_refill = self.buckets[key]

            # Refill
            elapsed = now - last_refill
            new_tokens = min(self.capacity, current_tokens + (elapsed * self.refill_rate))

            if new_tokens >= tokens:
                self.buckets[key] = (new_tokens - tokens, now)
                return True

            self.buckets[key] = (new_tokens, now)
            return False

# Global instance for API protection
# 100 requests capacity, refills at 10 requests per second.
api_limiter = TokenBucketRateLimiter(capacity=100.0, refill_rate=10.0)
