# Configuration Guide

> **Note**: WarmLogic follows the **12-Factor App** methodology. Configuration is stored in **Environment Variables**.

## 🛑 Critical Settings (Must Set)

| Variable                | Description                                                            | Example          |
| ----------------------- | ---------------------------------------------------------------------- | ---------------- |
| `WARM_SOVEREIGN_SEAL`   | Hardware-derived proof string. Required for kernel boot in production. | `hsm:v1:7f8a...` |
| `SOVEREIGN_COCKPIT_KEY` | API Key for the Cockpit Dashboard.                                     | `sk_live_...`    |

## ⚙️ Core Options

| Variable            | Description                                           | Default              |
| ------------------- | ----------------------------------------------------- | -------------------- |
| `WARM_HTTP_PORT`    | Port for the main UI server.                          | `8000`               |
| `COCKPIT_HTTP_PORT` | Port for the Cockpit operational dashboard.           | `5001`               |
| `WARM_DB_PATH`      | Path to the persistent Sled database.                 | `.warm_data/sled_db` |
| `WARM_REGION`       | Network topology region.                              | `ap-northeast-2`     |
| `WARM_LOG_LEVEL`    | Logging verbosity (`DEBUG`, `INFO`, `WARN`, `ERROR`). | `INFO`               |

## 🧪 Development & Chaos

**WARNING**: These settings are for testing only. Do not use in production.

| Variable               | Description                                   | Default |
| ---------------------- | --------------------------------------------- | ------- |
| `WARMLOGIC_DEV_MODE`   | Bypasses hardware attestation checks.         | `false` |
| `WARM_CHAOS_ENABLED`   | Set to `1` to enable network fault injection. | `0`     |
| `WARM_CHAOS_DROP_RATE` | Probability of packet loss (0.0 - 1.0).       | `0.0`   |
| `WARM_CHAOS_LATENCY`   | Introduced network latency in milliseconds.   | `0`     |
| `PATCH_REVIEW_MINUTES` | Simulated time for patch review metrics.      | `5`     |
