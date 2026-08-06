# Sovereign SDK API 참조

> **상태**: 실험적
> **경고**: 이 API는 사전 고지 없이 변경될 수 있습니다. 프로덕션에서 사용하지 마세요.
> 원문: [API_SDK.md](API_SDK.md)

`warm_logic.sdk` 패키지는 WarmLogic 거버넌스 커널과 상호작용하기 위한 고수준 추상화를 제공합니다.

---

## `SovereignClient`

애플리케이션의 주요 진입점입니다.

### 생성자

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient(endpoint: str | None = None)
```

**매개변수:**
- `endpoint`: 선택적 커널 엔드포인트 URL. `None`이면 로컬 커널 사용.

**참고:** 인스턴스 생성 시 실험적 상태를 알리는 `UserWarning`이 발생합니다.

---

### `propose_action(intent, context, *, require_proof=False) -> Decision`

거버넌스 커널에 평가를 위한 행동을 제안합니다.

```python
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com", "subject": "Hello"},
    require_proof=False
)
```

**매개변수:**
- `intent` (str): 행동 의도 (예: `"send_email"`, `"execute_trade"`)
- `context` (dict | None): 결정을 위한 추가 컨텍스트
- `require_proof` (bool): `True`면 암호학적 증명 필요 (Rust 코어 필요)

**반환값:** `Decision` 객체

**예외:** `require_proof=True`이지만 Rust 코어가 없으면 `RuntimeError`

---

### `health_check() -> dict`

커널 연결의 상태를 반환합니다.

```python
status = client.health_check()
# {'status': 'ok', 'endpoint': 'local', 'rust_core': True, ...}
```

---

## `Decision`

커널의 거버넌스 결정을 나타냅니다.

### 속성

| 속성 | 타입 | 설명 |
|------|------|------|
| `verdict` | str | `"ALLOW"`, `"DENY"`, 또는 `"PENDING"` |
| `reason` | str | 사람이 읽을 수 있는 설명 |
| `proof_hash` | str | 감사 추적용 결정론적 해시 |
| `timestamp` | datetime | UTC 결정 타임스탬프 |
| `metadata` | dict | 추가 메타데이터 |
| `allowed` | bool | verdict가 `"ALLOW"`면 `True` |
| `denied` | bool | verdict가 `"DENY"`면 `True` |

### 예제

```python
if decision.allowed:
    execute_action()
else:
    log_rejection(decision.reason)
```

---

## 전체 예제

```python
from warm_logic.sdk import SovereignClient

# 클라이언트 초기화
client = SovereignClient()

# 상태 확인
print(client.health_check())

# 행동 제안
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com", "subject": "Hello"}
)

print(f"판결: {decision.verdict}")
print(f"사유: {decision.reason}")
print(f"증명 해시: {decision.proof_hash}")

if decision.allowed:
    print("행동이 승인되었습니다!")
```

---

## 제한 사항

| 기능 | 상태 |
|------|------|
| Python 전용 정책 평가 | 활성 (폴백) |
| Rust 암호화 코어 | 선택적 |
| ZK 증명 생성 | Rust 코어 필요 |
| BFT 합의 | 불가 (단일 노드) |
| 프로덕션 강화 | 미준비 |

---

## 향후 API (계획)

v1.0.0에서 계획된 기능:

- `SovereignIdentity`: PQC 키 관리 (ML-DSA-65)
- `SovereignSession`: 세션 인식 논스 생성
- `get_truth(state_key)`: ZK 증명을 통한 검증된 원장 상태
- 다중 노드 BFT 합의

자세한 내용은 DEVELOPMENT_ROADMAP.md 참조.

---

*마지막 업데이트: 2026-02-07*
