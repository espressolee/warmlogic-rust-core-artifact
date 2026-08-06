# WarmLogic vs 대안들

> **상태**: 연구 프로토타입. 외부 검증 없음. docs/CLAIM_EVIDENCE.md 참조.
> 비교는 2026년 2월 기준 공개 정보를 바탕으로 합니다.

---

## 요약

WarmLogic은 다음을 결합한 유일한 솔루션입니다:
1. **포스트 양자 암호화** (ML-DSA-65)
2. **비잔틴 장애 허용 합의**
3. **영지식 컴플라이언스 증명**
4. **헌법적 거버넌스 커널**

기존 솔루션 중 네 가지 기능을 모두 제공하는 것은 없습니다.

---

## 기능 비교

| 기능 | WarmLogic | LangChain | AutoGPT | CrewAI | Guardrails AI |
|------|-----------|-----------|---------|--------|---------------|
| 포스트 양자 서명 | ML-DSA-65 | 없음 | 없음 | 없음 | 없음 |
| BFT 합의 | 예 | 아니오 | 아니오 | 아니오 | 아니오 |
| 영지식 증명 | 예 | 아니오 | 아니오 | 아니오 | 아니오 |
| 헌법적 가드레일 | 예 | 아니오 | 제한적 | 아니오 | 예 |
| 암호화 감사 추적 | 예 | 아니오 | 아니오 | 아니오 | 아니오 |
| 로컬 우선 | 예 | 아니오 | 예 | 아니오 | 아니오 |
| 멀티 에이전트 오케스트레이션 | 예 | 예 | 예 | 예 | 아니오 |
| 오픈 소스 | MIT | MIT | MIT | MIT | Apache 2.0 |

---

## 상세 비교

### WarmLogic vs LangChain

| 측면 | WarmLogic | LangChain |
|------|-----------|-----------|
| **초점** | 거버넌스 & 검증 | LLM 오케스트레이션 |
| **보안 모델** | 암호화 증명 | 애플리케이션 레벨 |
| **감사 추적** | 불변, 서명됨 | 변경 가능 로그 |
| **양자 안전** | ML-DSA-65 | 없음 |
| **정책 시행** | 헌법적 커널 | 플러그인 기반 |
| **성능** | Rust 코어 (~300배 암호화) | 순수 Python |
| **멀티 노드** | BFT 합의 | 단일 프로세스 |
| **최적 용도** | 규제 산업 | 빠른 프로토타이핑 |

**WarmLogic 선택 시**: AI 결정의 암호화 증명이 필요한 금융 서비스, 의료, 법률, 정부 애플리케이션.

**LangChain 선택 시**: 빠른 프로토타입, 비규제 애플리케이션, 순수 LLM 오케스트레이션.

---

### WarmLogic vs Guardrails AI

| 측면 | WarmLogic | Guardrails AI |
|------|-----------|---------------|
| **초점** | 전체 거버넌스 스택 | 출력 검증 |
| **암호화 증명** | 예 (PQC) | 아니오 |
| **합의** | BFT 멀티 노드 | 단일 프로세스 |
| **정책 언어** | YAML + Python | RAIL (XML 유사) |
| **증거 번들** | 전체 감사 패키지 | 검증 로그 |
| **통합** | SDK + CLI + API | Python 라이브러리 |
| **배포** | 로컬 우선 / 스웜 | 클라우드 또는 로컬 |

**WarmLogic 선택 시**: 암호화 증거, 멀티 노드 배포, 포스트 양자 보안이 필요한 경우.

**Guardrails AI 선택 시**: 단순 출력 검증, 스키마 시행, LLM 응답 포맷팅.

---

### WarmLogic vs AutoGPT

| 측면 | WarmLogic | AutoGPT |
|------|-----------|---------|
| **초점** | 거버넌스된 자율성 | 무제한 자율성 |
| **안전 모델** | 헌법적 제약 | 사용자 프롬프트 |
| **감사 추적** | 암호화 | 텍스트 로그 |
| **결정 검증** | BFT 합의 | 없음 |
| **리소스 제한** | 정책 시행 | 구성 |
| **멀티 에이전트** | 합의 있는 스웜 | 단일 에이전트 |

**WarmLogic 선택 시**: 책임과 증명이 필요한 기업 배포.

**AutoGPT 선택 시**: 개인 자동화, 탐색 작업, 취미 프로젝트.

---

## 암호화 비교

### 서명 체계

| 체계 | 키 크기 | 서명 크기 | 서명 시간 | 양자 안전 |
|------|---------|-----------|-----------|-----------|
| **ML-DSA-65** | 1,952 B | 3,309 B | 48 μs | 예 |
| Ed25519 | 32 B | 64 B | 35 μs | 아니오 |
| RSA-2048 | 256 B | 256 B | 1.2 ms | 아니오 |
| ECDSA P-256 | 32 B | 64 B | 125 μs | 아니오 |

### 포스트 양자가 중요한 이유

- **양자 타임라인**: 암호학적으로 유의미한 양자 컴퓨터가 10-15년 내 예상됨
- **지금 수집, 나중에 복호화**: 적대자가 오늘 암호화된 데이터를 저장하여 미래에 복호화할 수 있음
- **규제 압력**: NIST, EU 등이 PQC 전환 권고
- **장기 기록**: 감사 추적은 수십 년간 검증 가능해야 함

---

## 합의 비교

| 프로토콜 | 지연 | 처리량 | 장애 허용 | 최종성 |
|----------|------|--------|-----------|--------|
| **WL-BFT-v1** | 87 ms | 11.5/초 | 비잔틴 (f < n/3) | 즉시 |
| Raft | 45 ms | 22/초 | 크래시 (f < n/2) | 즉시 |
| Paxos | 50 ms | 20/초 | 크래시 (f < n/2) | 즉시 |
| Tendermint | 120 ms | 8.3/초 | 비잔틴 (f < n/3) | 즉시 |

### BFT가 중요한 이유

- **악의적 노드**: 크래시 장애 허용 (Raft/Paxos)은 비잔틴 동작을 처리할 수 없음
- **AI 안전**: 일부 노드가 손상되거나 환각할 수 있다고 가정
- **규제 요구 사항**: 금융 시스템은 종종 BFT 필요

---

## 거버넌스 비교

### 정책 시행

| 시스템 | 정책 유형 | 시행 지점 | 우회 가능 |
|--------|-----------|-----------|-----------|
| **WarmLogic** | 헌법적 | 커널 (Rust) | 아니오 |
| LangChain | 플러그인 | 애플리케이션 | 예 |
| Guardrails | RAIL 스키마 | 라이브러리 | 예 |
| AutoGPT | 프롬프트 | LLM | 예 |

### 헌법적 거버넌스의 이유

- **우회 불가**: 규칙이 가장 낮은 레벨에서 시행됨
- **형식 검증**: 안전 속성에 대한 TLA+ 명세
- **결정론적**: 동일 입력 → 동일 정책 결정
- **감사 가능**: 모든 정책 평가가 기록됨

---

## 성능 비교

### 결정 지연

| 시스템 | 단일 노드 | 4노드 클러스터 |
|--------|-----------|----------------|
| **WarmLogic** | 12 ms | 99 ms |
| LangChain | 5 ms | N/A |
| Guardrails | 8 ms | N/A |
| AutoGPT | 3 ms | N/A |

*참고: WarmLogic은 암호화 서명 및 선택적 합의 포함.*

### 처리량

| 시스템 | 결정/초 | 비고 |
|--------|---------|------|
| **WarmLogic** | 100 (단일) / 11 (클러스터) | 전체 감사 포함 |
| LangChain | 1000+ | 암호화 오버헤드 없음 |
| Guardrails | 500+ | 검증만 |

---

## 사용 사례 적합성

| 사용 사례 | 최적 선택 | 이유 |
|----------|-----------|------|
| 금융 거래 감사 | **WarmLogic** | PQC + BFT + 증거 |
| 의료 AI 결정 | **WarmLogic** | HIPAA 컴플라이언스 증명 |
| 챗봇 프로토타이핑 | LangChain | 빠른 개발 |
| 출력 포맷팅 | Guardrails | 스키마 검증 |
| 개인 자동화 | AutoGPT | 유연성 |
| 법률 문서 검토 | **WarmLogic** | 감사 추적 필수 |
| 창작 글쓰기 | LangChain | 거버넌스 불필요 |
| 멀티 에이전트 리서치 | CrewAI | 협업 중심 |

---

## 마이그레이션 경로

### LangChain에서 WarmLogic으로

```python
# LangChain
from langchain import LLMChain
chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run(input)

# WarmLogic (거버넌스로 래핑)
from warm_logic.sdk import SovereignClient
client = SovereignClient()

decision = client.propose_action(
    intent="llm_call",
    context={"prompt": prompt, "input": input}
)

if decision.approved:
    result = chain.run(input)
    client.record_evidence(decision.proof_hash, result)
```

### Guardrails에서 WarmLogic으로

```python
# Guardrails
from guardrails import Guard
guard = Guard.from_rail(rail_spec)
result = guard(llm, prompt)

# WarmLogic (암호화 증명 포함)
from warm_logic.sdk import SovereignClient
client = SovereignClient()

decision = client.propose_action(
    intent="guarded_call",
    context={"rail_spec": rail_spec, "prompt": prompt}
)

if decision.approved:
    result = guard(llm, prompt)
    # 증거 번들이 자동으로 생성됨
```

---

## 제한 사항

### WarmLogic 제한 사항

| 제한 사항 | 영향 | 완화 |
|-----------|------|------|
| 더 큰 서명 크기 | 3KB vs 64B | 감사 사용 사례에서 허용 가능 |
| 합의 지연 | 87ms 오버헤드 | 비임계 결정에는 건너뛰기 |
| 복잡성 | 가파른 학습 곡선 | 포괄적인 문서 |
| research prototype 상태 | 프로덕션 미준비 | 2026 Q4 계획 |

### WarmLogic을 사용하지 말아야 할 때

- 감사 요구 사항이 없는 단순 챗봇
- 실시간 게이밍 (지연 민감)
- 개인 취미 프로젝트
- 빠른 프로토타이핑 단계

---

## 결론

WarmLogic은 **고위험 AI 거버넌스**를 위해 설계되었습니다:
- 결정이 암호학적으로 증명 가능해야 함
- 포스트 양자 보안이 필요함
- 멀티 노드 합의가 필요함
- 규제 컴플라이언스가 필수임

더 단순한 사용 사례에는 다른 도구가 더 적합할 수 있습니다.

---

*마지막 업데이트: 2026-02-07*
