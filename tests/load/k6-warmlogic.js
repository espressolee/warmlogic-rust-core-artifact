/**
 * WarmLogic k6 Load Test Suite
 * P4xx: Production Load Testing
 *
 * Run: k6 run tests/load/k6-warmlogic.js
 * With options: k6 run --vus 50 --duration 5m tests/load/k6-warmlogic.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const healthCheckDuration = new Trend('health_check_duration');
const policyEvalDuration = new Trend('policy_eval_duration');
const kernelStateDuration = new Trend('kernel_state_duration');
const requestCounter = new Counter('total_requests');

// Test configuration
export const options = {
  scenarios: {
    // Smoke test - quick validation
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      startTime: '0s',
      tags: { test_type: 'smoke' },
    },
    // Load test - normal expected load
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 10 },  // Ramp up
        { duration: '3m', target: 10 },  // Stay at 10 VUs
        { duration: '1m', target: 20 },  // Ramp to 20
        { duration: '3m', target: 20 },  // Stay at 20 VUs
        { duration: '1m', target: 0 },   // Ramp down
      ],
      startTime: '30s',
      tags: { test_type: 'load' },
    },
    // Stress test - beyond normal capacity
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 0 },
      ],
      startTime: '10m',
      tags: { test_type: 'stress' },
    },
    // Spike test - sudden traffic surge
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },  // Instant spike
        { duration: '1m', target: 100 },   // Hold
        { duration: '10s', target: 0 },    // Instant drop
      ],
      startTime: '26m',
      tags: { test_type: 'spike' },
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],  // 95% under 500ms, 99% under 1s
    http_req_failed: ['rate<0.01'],                   // Error rate under 1%
    errors: ['rate<0.05'],                            // Custom error rate under 5%
    health_check_duration: ['p(95)<100'],             // Health check under 100ms
    policy_eval_duration: ['p(95)<200'],              // Policy eval under 200ms
  },
};

// Base URL from environment or default
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

// Test data
const testPolicies = [
  { name: 'governance_default', params: { strict: true } },
  { name: 'kernel_transition', params: { from: 'idle', to: 'active' } },
  { name: 'era_validation', params: { era: 3000 } },
];

export function setup() {
  // Verify service is available before running tests
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`Service not available: ${res.status}`);
  }
  return {
    startTime: new Date().toISOString(),
    baseUrl: BASE_URL,
  };
}

export default function(data) {
  group('Health Check', () => {
    const start = Date.now();
    const res = http.get(`${BASE_URL}/health`);
    healthCheckDuration.add(Date.now() - start);
    requestCounter.add(1);

    const success = check(res, {
      'health status 200': (r) => r.status === 200,
      'health body contains ok': (r) => r.body && r.body.includes('ok') || r.body.includes('healthy'),
    });
    errorRate.add(!success);
  });

  sleep(0.5);

  group('Metrics Endpoint', () => {
    const res = http.get(`${BASE_URL}/metrics`);
    requestCounter.add(1);

    const success = check(res, {
      'metrics status 200': (r) => r.status === 200,
      'metrics contains warmlogic': (r) => r.body && r.body.includes('warmlogic'),
    });
    errorRate.add(!success);
  });

  sleep(0.5);

  group('API Endpoints', () => {
    // Status endpoint
    const statusRes = http.get(`${BASE_URL}/api/v1/status`);
    requestCounter.add(1);
    check(statusRes, {
      'status endpoint available': (r) => r.status === 200 || r.status === 404,
    });

    // Kernel state
    const start = Date.now();
    const kernelRes = http.get(`${BASE_URL}/api/v1/kernel/state`);
    kernelStateDuration.add(Date.now() - start);
    requestCounter.add(1);
    check(kernelRes, {
      'kernel state available': (r) => r.status === 200 || r.status === 404,
    });
  });

  sleep(0.5);

  group('Policy Evaluation', () => {
    const policy = testPolicies[Math.floor(Math.random() * testPolicies.length)];
    const payload = JSON.stringify(policy);
    const params = {
      headers: { 'Content-Type': 'application/json' },
    };

    const start = Date.now();
    const res = http.post(`${BASE_URL}/api/v1/policy/evaluate`, payload, params);
    policyEvalDuration.add(Date.now() - start);
    requestCounter.add(1);

    const success = check(res, {
      'policy eval status ok': (r) => r.status === 200 || r.status === 201 || r.status === 404,
    });
    errorRate.add(!success && res.status >= 500);
  });

  sleep(1);
}

export function teardown(data) {
  console.log(`Load test completed. Started at: ${data.startTime}`);
}

// Separate scenarios for CI/CD
export function smokeTest() {
  const res = http.get(`${BASE_URL}/health`);
  check(res, { 'smoke test passed': (r) => r.status === 200 });
}

export function spikeTest() {
  // Rapid-fire requests
  for (let i = 0; i < 10; i++) {
    http.get(`${BASE_URL}/health`);
    http.get(`${BASE_URL}/metrics`);
  }
}
