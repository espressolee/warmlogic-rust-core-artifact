# WarmLogic Load Testing

P4xx: Production Load Testing Suite using k6.

## Prerequisites

```bash
# Install k6
brew install k6

# Or via Docker
docker pull grafana/k6
```

## Running Tests

### Quick Smoke Test
```bash
k6 run --vus 1 --duration 30s tests/load/k6-warmlogic.js
```

### Load Test
```bash
k6 run tests/load/k6-warmlogic.js
```

### Custom Configuration
```bash
# Set target URL
k6 run -e BASE_URL=https://warmlogic.example.com tests/load/k6-warmlogic.js

# Adjust VUs and duration
k6 run --vus 50 --duration 10m tests/load/k6-warmlogic.js
```

### Docker Execution
```bash
docker run --rm -i grafana/k6 run - < tests/load/k6-warmlogic.js
```

## Test Scenarios

| Scenario | VUs | Duration | Purpose |
|----------|-----|----------|---------|
| Smoke | 1 | 30s | Quick validation |
| Load | 10-20 | 9m | Normal expected load |
| Stress | 50-100 | 16m | Beyond normal capacity |
| Spike | 100 | ~1m | Sudden traffic surge |

## Thresholds

- **p95 Response Time**: < 500ms
- **p99 Response Time**: < 1s
- **Error Rate**: < 1%
- **Health Check p95**: < 100ms
- **Policy Evaluation p95**: < 200ms

## Output

### Console Summary
Default k6 output shows real-time metrics.

### JSON Output
```bash
k6 run --out json=results.json tests/load/k6-warmlogic.js
```

### InfluxDB + Grafana
```bash
k6 run --out influxdb=http://localhost:8086/k6 tests/load/k6-warmlogic.js
```

## CI/CD Integration

See `.github/workflows/ci-load-test.yml` for automated load testing in CI pipelines.
