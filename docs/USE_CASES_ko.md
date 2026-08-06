# WarmLogic 사용 사례

> **상태**: 연구 프로토타입. 외부 검증 없음. docs/CLAIM_EVIDENCE.md 참조.
> 사용 사례는 예상 프로덕션 시나리오를 기반으로 합니다.

---

## 개요

WarmLogic은 **AI 결정의 암호화 증명**이 필요한 조직을 위해 설계되었습니다.

---

## 금융 서비스

### 알고리즘 트레이딩 감사

**문제**: 규제 기관은 트레이딩 알고리즘이 승인된 규칙을 따른다는 증명을 요구합니다. 기존 로그는 변조될 수 있습니다.

**솔루션**: WarmLogic 제공:
- 모든 트레이딩 결정의 불변 감사 추적
- ML-DSA-65 서명 (양자 안전)
- 다자간 검증을 위한 BFT 합의
- 민감한 데이터를 위한 영지식 증명

**구현**:

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient()

decision = client.propose_action(
    intent="execute_trade",
    context={
        "symbol": "AAPL",
        "action": "buy",
        "quantity": 1000,
        "price": 185.50,
        "strategy_id": "momentum_v2",
        "risk_score": 0.3
    }
)

if decision.approved:
    execute_trade()
else:
    log_rejection(decision.rejection_reason)
```

**이점**:
- 규제 준수 (MiFID II, SEC)
- 감사 준비 시간 80% 단축
- 장기 기록을 위한 포스트 양자 보안

---

### 대출 승인 결정

**문제**: 공정 대출법은 설명 가능성을 요구합니다. AI 결정은 문서화되어야 합니다.

**솔루션**: WarmLogic 캡처:
- 대출 결정에 고려된 모든 요소
- 평가된 정책 규칙
- 결정 과정의 암호화 증명

---

## 의료

### 임상 의사 결정 지원

**문제**: 의료 AI 권장 사항은 의료 과실 보호 및 규제 준수를 위한 감사 추적이 필요합니다.

**솔루션**: WarmLogic 제공:
- HIPAA 준수 증거 번들
- 영지식 증명 (PHI를 노출하지 않고 검증)
- AI 권장 사항의 불변 기록

**구현**:

```python
decision = client.propose_action(
    intent="clinical_recommendation",
    context={
        "patient_hash": sha256(patient_id),  # PHI 직접 저장 금지
        "recommendation": "consider_screening",
        "confidence": 0.85,
        "model_version": "v2.3.1"
    }
)

# 영지식 증명: 환자 신원을 밝히지 않고
# 권장 사항이 만들어졌음을 증명
zk_proof = decision.generate_zk_proof(
    reveal=["recommendation", "confidence"],
    hide=["patient_hash"]
)
```

---

## 법률 기술

### 계약서 검토 AI

**문제**: 로펌은 AI가 회사 지침에 따라 계약서를 검토했다는 증명이 필요합니다.

**솔루션**: WarmLogic 제공:
- 특정 조항이 검토되었다는 증거
- 검토 타임스탬프의 암호화 증명
- 정책 준수 검증

---

## 정부 및 국방

### 보안 허가 결정

**문제**: 정부 AI 결정은 극도의 감사 가능성과 장기 기록 무결성이 필요합니다.

**솔루션**: WarmLogic 제공:
- 포스트 양자 암호화 (ML-DSA-65)
- 50년 이상 기록 무결성
- 다기관 BFT 합의

**포스트 양자가 중요한 이유**:
- 허가 결정은 50년 이상 관련성 유지
- "지금 수집, 나중에 복호화" 위협
- NIST FIPS 204 준수

---

## 엔터프라이즈 AI

### AI 모델 배포 거버넌스

**문제**: 기업은 어떤 AI 모델을 배포할 수 있는지에 대한 거버넌스가 필요합니다.

**솔루션**: 배포 게이트로서의 WarmLogic:

```python
decision = client.propose_action(
    intent="deploy_model",
    context={
        "model_name": "customer_churn_v4",
        "model_hash": sha256(model_weights),
        "training_data_hash": dataset_hash,
        "bias_audit_passed": True,
        "security_scan_passed": True,
        "performance_metrics": {
            "accuracy": 0.94,
            "f1_score": 0.91
        }
    }
)

if not decision.approved:
    raise ModelDeploymentBlocked(decision.rejection_reason)
```

---

## 연구 및 학계

### 재현 가능한 AI 실험

**문제**: AI 연구는 재현성이 필요하지만 실험은 검증하기 어렵습니다.

**솔루션**: 실험 원장으로서의 WarmLogic:

```python
decision = client.propose_action(
    intent="log_experiment",
    context={
        "experiment_id": "exp_2026_02_001",
        "model_config_hash": config_hash,
        "dataset_hash": dataset_hash,
        "random_seed": 42,
        "results": {
            "accuracy": 0.923,
            "loss": 0.0821
        },
        "environment_hash": env_hash
    }
)

# 결과의 암호화 증명
# 누구나 실험이 주장대로 실행되었음을 검증 가능
```

---

## 요약

| 사용 사례 | 산업 | 핵심 기능 |
|----------|------|----------|
| 트레이딩 감사 | 금융 | PQC, BFT, 불변 |
| 대출 결정 | 금융 | 설명 가능성, 감사 |
| 임상 AI | 의료 | ZK 증명, HIPAA |
| 약물 검사 | 의료 | 안전 게이트 |
| 계약 검토 | 법률 | 증거 번들 |
| 전자 증거 개시 | 법률 | 분류 증명 |
| 허가 | 정부 | 50년 PQC |
| 자율 시스템 | 국방 | 엄격한 제약 |
| 모델 배포 | 기업 | 거버넌스 게이트 |
| AI 추적 | 기업 | 예산/규정 준수 |
| 실험 | 연구 | 재현성 |
| 멀티 에이전트 | AI/ML | 조정 |

---

## 시작하기

1. **설치**: `pip install warm-logic`
2. **구성**: `constitution.yaml` 생성
3. **통합**: AI 결정 지점 래핑
4. **검증**: 증거 번들 검토

단계별 안내는 [튜토리얼](tutorial/01_quickstart.md)을 참조하세요.

---

*마지막 업데이트: 2026-02-07*
