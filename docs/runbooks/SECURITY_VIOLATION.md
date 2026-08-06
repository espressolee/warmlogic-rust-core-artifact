# Runbook: Security Violation

## Alert: SecurityViolationDetected

**Severity**: Critical
**Component**: Security (Aegis)
**SLO Impact**: Critical - Potential system compromise

---

## Description

The Aegis security subsystem has detected a security violation. This could indicate:
- Attempted code injection (eval/exec)
- Hardcoded credential detection
- Unauthorized patch attempt
- Policy bypass attempt

## IMMEDIATE RESPONSE

**This is a security incident. Follow incident response protocol.**

### 1. Acknowledge & Contain (First 5 minutes)

```bash
# Get violation details
curl http://warmlogic:8080/api/v1/security/violations/latest | jq

# Check if ongoing attack
curl http://warmlogic:8080/api/v1/security/violations?since=5m | jq '.count'

# Enable enhanced logging
curl -X POST http://warmlogic:8080/api/v1/security/enhanced-logging
```

### 2. Identify Source

```bash
# Get violation details
VIOLATION=$(curl -s http://warmlogic:8080/api/v1/security/violations/latest)

echo "Type: $(echo $VIOLATION | jq -r '.violation_type')"
echo "Source: $(echo $VIOLATION | jq -r '.source_ip')"
echo "User: $(echo $VIOLATION | jq -r '.user_id')"
echo "File: $(echo $VIOLATION | jq -r '.file_path')"
echo "Line: $(echo $VIOLATION | jq -r '.line_number')"
```

### 3. Block if Necessary

```bash
# Block suspicious IP (if external attack)
curl -X POST http://warmlogic:8080/api/v1/security/block \
  -H "Content-Type: application/json" \
  -d '{"ip": "<SOURCE_IP>", "duration": "1h", "reason": "Security violation"}'

# Revoke user session (if internal)
curl -X POST http://warmlogic:8080/api/v1/auth/revoke \
  -H "Content-Type: application/json" \
  -d '{"user_id": "<USER_ID>"}'
```

## Violation Types

### Type: `security_vulnerability` (Code Injection)

Detection of `eval()` or `exec()` in submitted code.

**Investigation:**
```bash
# Get the offending code
curl http://warmlogic:8080/api/v1/security/violations/latest | jq '.code_snippet'

# Check submission history
curl http://warmlogic:8080/api/v1/patches?user=<USER_ID>&limit=10 | jq
```

**Response:**
1. Reject the patch
2. Review user's recent activity
3. Consider temporary suspension if malicious intent

### Type: `hardcoded_secret`

Detection of hardcoded credentials in submitted code.

**Investigation:**
```bash
# Get secret type
curl http://warmlogic:8080/api/v1/security/violations/latest | jq '.secret_type'

# Check if secret was exposed
curl http://warmlogic:8080/api/v1/audit/log?event_type=secret_exposure | jq
```

**Response:**
1. Reject the patch
2. If secret was exposed, rotate immediately
3. Notify security team

### Type: `policy_bypass`

Attempt to circumvent governance policy.

**Investigation:**
```bash
# Get attempted policy bypass details
curl http://warmlogic:8080/api/v1/security/violations/latest | jq '.policy_details'

# Check governance logs
curl http://warmlogic:8080/api/v1/governance/audit?action=bypass | jq
```

**Response:**
1. Block the action
2. Review policy configuration
3. Update policy if legitimate use case

### Type: `unauthorized_access`

Attempt to access restricted resource.

**Investigation:**
```bash
# Get access attempt details
curl http://warmlogic:8080/api/v1/security/violations/latest | jq '.resource_path'

# Check auth logs
curl http://warmlogic:8080/api/v1/auth/audit?user=<USER_ID> | jq
```

**Response:**
1. Verify user permissions
2. Check for credential compromise
3. Enable MFA if not already

## Post-Incident

### 1. Document the Incident

```bash
# Export violation details
curl http://warmlogic:8080/api/v1/security/violations/<VIOLATION_ID> > incident_$(date +%Y%m%d_%H%M%S).json

# Export related logs
docker logs warmlogic_kernel --since "1h" > kernel_logs_$(date +%Y%m%d_%H%M%S).log
```

### 2. Create Evidence Bundle

```bash
# Generate security incident bundle
curl -X POST http://warmlogic:8080/api/v1/security/evidence-bundle \
  -H "Content-Type: application/json" \
  -d '{"violation_id": "<VIOLATION_ID>", "include_logs": true}'
```

### 3. Review and Improve

- Update detection rules if false positive
- Add to threat intelligence if true positive
- Review access controls
- Update runbook if needed

## Escalation Matrix

| Violation Count (1h) | Action |
|---------------------|--------|
| 1-2 | Investigate, document |
| 3-5 | Page security on-call |
| 6+ | Incident commander escalation |

## Related Alerts

- `HighFailedAuthAttempts`
- `CryptoOperationFailure`
- `PolicyViolation`

---

*Last updated: 2026-02-13*
