# WarmLogic: 검증 가능한 AI 거버넌스를 위한 양자내성 암호 런타임

> ## ⚠️ NON-AUTHORITATIVE — HISTORICAL DESIGN DOCUMENT
>
> This file describes **design intent**, not the measured state of this
> artifact. It predates the publication audit and its claims were **not**
> re-verified. Several are known to be contradicted by measurement — see
> `KNOWN_LIMITATIONS.md` and `docs/CLAIM_EVIDENCE.md`, which are authoritative.
>
> Known contradictions include: multi-node/BFT deployment (never executed),
> zero-knowledge proofs (the `zk` feature does not compile), formal
> verification (Kani harnesses exist but no CI runs them; TLA+ specs are design
> documents, not checked models), and performance figures (no raw data is bound
> to this artifact).
>
> **Do not cite this file for current status.** Authoritative files:
> `README.md`, `STATUS.md`, `KNOWN_LIMITATIONS.md`, `docs/CLAIM_EVIDENCE.md`,
> `SECURITY.md`, `PUBLIC_PROVENANCE.json`, `SBOM.json`, `AUDIT_PROFILE.json`,
> `LICENSE`, `NOTICE`.

> **Authors**: espressolee
> **버전**: 1.0 (2026년 2월)
> **상태**: 릴리스 후보 (experimental)
> **License**: Apache-2.0 (entire repository; the MIT/Elastic split in older
> drafts was never applied to this artifact)

---

## 초록

인공지능 시스템은 금융, 의료, 채용, 형사사법 등에서 점점 더 중대한 결정을 내리고 있으나, *왜* 그러한 결정이 내려졌는지에 대한 변조 불가능한 암호학적 증거를 생성하는 인프라는 아직 널리 채택되지 않고 있다. 기존의 거버넌스 접근법 — 모델 카드, 데이터시트, 규제 프레임워크 — 은 문서화 요구사항을 규정하지만, 이를 강제할 암호학적 기반을 제공하지 못한다. 한편, 양자 컴퓨팅의 임박한 위협은 오늘날의 전자서명을 10-15년 내에 무력화시켜, 기존 서명 체계로 구축된 모든 감사 추적의 장기적 유효성을 훼손한다.

본 논문에서는 네 가지 통합 메커니즘을 통해 AI 결정에 암호학적 증거를 부착하는 오픈소스 런타임 **WarmLogic**을 제시한다: (1) ML-DSA-65(NIST FIPS 204)를 사용한 **양자내성 전자서명**, (2) 정족수 임계값 floor(2N/3)+1의 **비잔틴 장애 허용 합의**, (3) Ristretto255 곡선 위의 시그마 프로토콜을 통한 **영지식 증명**, (4) 형식 검증된 안전성 불변식을 갖춘 **반성적 거버넌스 커널**. 시스템은 이중 언어 런타임으로 구현되었으며 — `no_std` 지원의 Rust 코어가 암호학적 안전성을 담당하고, PyO3 제로카피 FFI를 통해 Python과 연결되어 기존 바인딩 대비 300배의 처리량 개선을 달성했다.

두 가지 핵심 안전성 속성을 TLA+로 형식화했다: **MethodologicalIntegrity**(신뢰된 출처 없이는 실행 불가)와 **LedgerImmutable**(증거 원장은 추가 전용). 두 속성 모두 TLC 모델 체커로 기계 검증되었다.

**WarmLogic은 기술 성숙도 7단계(experimental)의 연구 프로토타입이다.** EU AI Act(2026년 8월 발효)와 NIST PQC 이행 일정(2024-2030)이 요구할 증거 인프라를 제공하도록 설계되었다. 시스템은 프로덕션 준비가 되지 않았다. 불완전한 P2P 블록 전파, 시뮬레이션된 하드웨어 보안 모듈, 미완료 제3자 보안 감사 등 상당한 엔지니어링 격차가 남아 있다. 시스템은 오픈소스이며, 암호학적 커널은 MIT 라이선스 하에 공개된다.

**키워드**: 양자내성 암호, AI 거버넌스, 비잔틴 장애 허용, 영지식 증명, 형식 검증, FIPS 204, EU AI Act, 증거 기반 AI

---

## 1. 서론

### 1.1 동기

AI 시스템은 실제 사람들에게 실질적 결과를 초래하는 결정을 내리고 있다. 신용 평가 모델이 대출을 거절한다. 의료 영상 시스템이 종양을 탐지한다. 채용 알고리즘이 후보자를 탈락시킨다. 각 경우에서 영향을 받는 개인 — 그리고 해당 기관을 감독하는 규제기관 — 은 근본적인 질문을 갖는다: *AI가 왜 이 결정을 내렸으며, 정책 범위 내에서 작동했음을 증명할 수 있는가?*

현재의 거버넌스 접근법은 이 질문에 암호학적 엄밀성으로 답하기에 불충분하다:

- **모델 카드** [Mitchell et al. 2019]와 **데이터셋용 데이터시트** [Gebru et al. 2021]는 의도된 용도와 제한사항을 문서화하지만, 문서화된 제약이 추론 시 실제로 적용되었다는 런타임 증거를 생성하지 못한다.
- **AI 팩트시트** [Arnold et al. 2019]는 AI 시스템에 대한 메타데이터를 수집하지만, 이 메타데이터는 자가 보고식이며 변경 가능하다 — 소급 수정을 방지하는 메커니즘이 없다.
- **규제 프레임워크**, 예를 들어 EU AI Act(Regulation 2024/1689)는 고위험 AI 시스템에 대한 결정 추적성, 인간 감독 문서화, 리스크 관리를 의무화하지만(제6, 9, 14, 17조), 암호학적 수준에서는 아직 존재하지 않는 기술 인프라의 존재를 전제한다.

격차는 *무엇을* 문서화해야 하는지가 아니라, *어떻게* 해당 문서를 변조 불가능하고, 검증 가능하며, 기존 및 양자 적대자에 대해 복원력 있게 만드느냐에 있다.

이 격차는 양자 컴퓨팅 일정에 의해 심화된다. NIST는 2024년에 양자내성 암호 표준을 확정했다 — FIPS 203(ML-KEM), FIPS 204(ML-DSA), FIPS 205(SLH-DSA) — 핵심 인프라에 대한 이행 지침으로 2030년까지 완료를 권고한다. EU PQC 로드맵도 동일한 2030년 기한을 설정한다. 오늘날 기존 서명(ECDSA, Ed25519)으로 구축된 모든 감사 추적은 금융 및 의료 규제가 요구하는 보존 기간 내에 "지금 수확하고, 나중에 복호화(harvest now, decrypt later)" 공격에 취약해진다.

### 1.2 기여

본 논문은 양자내성 암호, 비잔틴 장애 허용, 영지식 증명, 반성적 거버넌스 커널을 AI 결정 증거를 위한 단일 런타임으로 통합한 최초의 시스템인 WarmLogic을 제시한다. 구체적 기여는 다음과 같다:

1. **PQC + BFT + ZK + 거버넌스의 아키텍처 통합**. ML-DSA-65 서명이 BFT 합의 프로토콜에 네이티브로 내장되어 모든 투표가 개별적으로 서명 및 검증되고, 커밋된 블록에 영지식 증명이 첨부되며 — 이 모든 것이 윤리적 제약 위반 시 시스템을 중단할 수 있는 거버넌스 커널에 의해 조율됨을 보인다.

2. **핵심 안전성 속성의 형식 검증**. TLA+와 TLC 모델 체커를 사용하여 두 가지 안전성 불변식을 명세하고 기계 검증한다: *MethodologicalIntegrity*(시스템은 신뢰되지 않은 산출물에 대해 실행할 수 없다)와 *LedgerImmutable*(증거 원장은 추가 전용이다). 추가로 노드 간 비잔틴 안전 로그 접두사 합의를 보장하는 위트니스 체인 프로토콜을 형식화한다.

3. **반성적 거버넌스 커널**. 안정성 방정식 `e_stab = alpha * epsilon_c + beta * (1 - tau_ethics)`로 네 가지 운영 모드(NORMAL, SUSPICIOUS, CRITICAL_HALT, VETO_LOCK)를 정의하며, 윤리적 제약 위반이 시스템을 자율적으로 중단할 수 있는 — "fail-closed" 설계 철학을 구현한다.

4. **제로카피 FFI 브릿지**. Python(지배적 ML/AI 생태계)과 Rust(암호학적 코어) 간 10MB 페이로드에 대해 기존 시퀀스 복사 방식 대비 300배의 처리량 개선을 달성하여, 기존 AI 파이프라인과의 실용적 통합을 가능하게 한다.

5. **research prototype의 오픈소스 구현**. 34개 도메인에 걸친 187개 JSON 스키마로 스키마 우선 개발 규율(SSOT: Schema > Spec > Code > Test)을 강제하며, 26개 TLA+ 형식 명세, 90개 이상의 CI 워크플로를 포함한다.

### 1.3 논문 구성

2장에서 AI 거버넌스, 양자내성 암호, BFT 합의, 영지식 증명 분야의 관련 연구를 개관한다. 3장에서 암호학적 기반, 합의 계층, 복제 원장, 거버넌스 커널을 포함한 시스템 설계를 제시한다. 4장에서 형식 검증 접근법과 결과를 상세히 기술한다. 5장에서 구현 결정사항을 설명한다. 6장에서 평가 결과를 제시한다. 7장에서 한계, 규제 정합성, 향후 과제를 논의한다. 8장에서 결론을 맺는다.

---

## 2. 배경 및 관련 연구

### 2.1 AI 거버넌스와 책임성

AI 거버넌스 환경은 자발적 프레임워크에서 구속력 있는 규제로 진화했다. 모델 카드 [Mitchell et al. 2019]는 모델 성능 특성을 문서화하는 관행을 확립했다. 데이터셋용 데이터시트 [Gebru et al. 2021]는 이를 훈련 데이터 출처 추적으로 확장했다. AI 팩트시트 [Arnold et al. 2019]는 공정성 지표, 강건성 테스트, 계보 추적을 포함하는 포괄적 문서화를 제안했다.

EU AI Act(Regulation 2024/1689)는 자발적 문서화를 넘어선다. 제9조는 고위험 AI 제공자에게 "적절하고 표적화된 조치"를 갖춘 리스크 관리 시스템 구현을 요구한다. 제14조는 AI 결정을 "중단, 수정 또는 되돌릴" 수 있는 인간 감독을 의무화한다. 제17조는 "데이터 관리, 훈련, 테스트 및 검증"에 대한 문서화된 절차를 갖춘 품질 관리 시스템을 요구한다.

이러한 요구사항은 암묵적으로 조직이 컴플라이언스의 *검증 가능한 증거*를 생성할 수 있다고 전제한다 — 특정 모델 버전이, 특정 정책 하에서, 특정 시점에 결정을 내렸다는 것을. 현재의 AI 관측 플랫폼(Weights & Biases, LangSmith, Arize)은 지표 로깅과 실험 추적을 제공하지만, 이 데이터는 플랫폼 운영자가 통제하는 변경 가능한 데이터베이스에 저장된다. 소급 수정에 대한 암호학적 보장이 없다.

WarmLogic은 암호학적 증거 인프라를 제공함으로써 이 격차를 해결한다: 모든 AI 결정은 제3자가 독립적으로 검증할 수 있는 불변의, 서명된, 합의 검증된 증거 영수증을 생성한다.

### 2.2 양자내성 암호

NIST 양자내성 암호 표준화 프로젝트 [NIST 2024]는 세 가지 표준을 산출했다:

- **FIPS 203**: ML-KEM(모듈 격자 키 캡슐화 메커니즘) — 키 교환용
- **FIPS 204**: ML-DSA(모듈 격자 전자서명 알고리즘) — 전자서명용
- **FIPS 205**: SLH-DSA(무상태 해시 기반 전자서명 알고리즘) — 대안

FIPS 204의 보안 레벨 3 매개변수 집합인 ML-DSA-65는 다음과 같은 특성으로 128비트 양자내성 보안을 제공한다:

| 매개변수 | 값 |
|-----------|-------|
| 공개키 크기 | 1,952 바이트 |
| 비밀키 크기 | 4,032 바이트 |
| 서명 크기 | 3,309 바이트 |
| 보안 레벨 | NIST Level 3 (128비트 PQ) |
| 보안 가정 | Module-LWE 난제 |

WarmLogic은 ML-DSA-65를 유일한 서명 알고리즘으로 사용하며, 키 생성, 결정 서명, 투표 인증, 블록 확정 등 모든 연산에 균일하게 적용한다. 이는 의도적 설계 선택이다: 단일 PQC 알고리즘으로 표준화함으로써 알고리즘 협상의 복잡성을 제거하면서 시스템 전체에 양자 내성을 보장한다.

### 2.3 비잔틴 장애 허용

Lamport, Shostak, Pease [1982]가 형식화한 비잔틴 장애 허용은 n개 노드 중 최대 f개가 임의로(악의적으로 포함) 동작하더라도 n >= 3f + 1 조건 하에서 시스템의 정확성을 보장한다. PBFT [Castro and Liskov 1999]는 BFT를 실제 시스템에 실용적으로 만들었다. HotStuff [Yin et al. 2019]는 통신 복잡도를 O(n)으로 개선했다. Tendermint [Buchman 2016]는 BFT를 블록체인 합의에 적용했다.

WarmLogic의 BFT 엔진은 정족수 임계값 = floor(2N/3) + 1의 단순화된 단일 라운드 투표 프로토콜을 사용한다. 블록체인 BFT와 달리, WarmLogic의 합의는 다른 목적을 수행한다: 금융 거래를 순서화하는 것이 아니라, AI 결정 증거 기록이 유효하다는 *다자 증명*을 생성하는 것이다. 핵심 혁신은 모든 투표가 ML-DSA-65 서명을 수반하며 카운팅 전에 검증된다는 점이다 — 양자 적대자조차 합의 투표를 위조할 수 없다는 의미이다.

### 2.4 프라이버시 보존 거버넌스를 위한 영지식 증명

영지식 증명은 증명자가 값 자체를 공개하지 않고 해당 값에 대한 지식을 증명할 수 있게 한다. 시그마 프로토콜 [Cramer 1996]은 지식 증명을 위한 효율적 프레임워크를 제공하며, Fiat-Shamir 휴리스틱 [Fiat and Shamir 1986]을 통해 비대화식으로 전환될 수 있다.

WarmLogic은 Ristretto255 소수위수군 [de Valence et al. 2020]에서 시그마 프로토콜을 구현하며, Fiat-Shamir 변환에 Merlin 트랜스크립트 [Henry 2019]를 사용한다. 증명은 Pedersen 커밋먼트 C = v*G + r*H가 성립하는 값 (v, r)에 대한 지식을 증명하며, 여기서 G는 Ristretto 기저점이고 H는 도메인 분리된 생성자 문자열의 SHA3-512를 통해 유도된다.

이를 통해 프라이버시 보존 컴플라이언스 검증이 가능해진다: 조직은 독점 모델 내부나 특정 결정 입력값을 공개하지 않고 AI 시스템이 특정 매개변수(예: 편향 임계값, 신뢰도 범위) 내에서 운영되었음을 증명할 수 있다.

### 2.5 분산 시스템의 형식 검증

TLA+ [Lamport 2002]는 동시성 및 분산 시스템을 위한 명세 언어이다. TLC 모델 체커는 유한 상태 모델에서 시간 논리 속성을 완전히 검증한다. Amazon Web Services는 DynamoDB와 S3에서 설계 오류를 발견하는 등 핵심 분산 인프라 검증에 TLA+를 사용한 사례를 문서화했다 [Newcombe et al. 2015].

WarmLogic은 TLA+를 사용하여 핵심 프로토콜의 안전성 및 활성 속성을 명세한다. 이 접근법은 형식적 암호 보안 증명(7장에서 향후 과제로 언급)의 필요성을 보완하지만 대체하지는 않는다.

### 2.6 기존 시스템과의 비교

| 기능 | WarmLogic | Ethereum 2.0 | Hyperledger Fabric | AI Factsheets | W&B / LangSmith |
|---------|-----------|-------------|-------------------|---------------|-----------------|
| PQC 서명 | ML-DSA-65 (FIPS 204) | ECDSA (BLS 계획) | ECDSA | 없음 | 없음 |
| BFT 합의 | 있음 (floor(2N/3)+1) | 있음 (Casper) | Raft/PBFT | 없음 | 없음 |
| ZK 증명 | Sigma/Ristretto255 | zk-SNARKs (L2) | 없음 | 없음 | 없음 |
| AI 거버넌스 초점 | 1차 목적 | 없음 | 없음 | 1차 목적 | 부분적 |
| 형식 검증 | 26개 TLA+ 명세 | 부분적 | 없음 | 없음 | 없음 |
| 하드웨어 바인딩 | vHSM (시뮬레이션) | 없음 | HSM 선택사항 | 없음 | 없음 |
| 반성적 커널 | VETO_LOCK 메커니즘 | 없음 | 없음 | 없음 | 없음 |
| 로컬 우선 | 있음 | 없음 (퍼블릭 체인) | 허가형 | 해당 없음 | 없음 (클라우드) |
| 프로덕션 준비 | **아니오 (experimental)** | 예 | 예 | 해당 없음 | 예 |

**PQC + BFT + ZK + 반성적 AI 거버넌스를 단일 런타임으로 결합한 기존 시스템은 없다.** 그러나 WarmLogic은 Ethereum 2.0이나 Hyperledger Fabric과 같은 프로덕션 시스템보다 상당히 초기 성숙 단계에 있다.

---

## 3. 시스템 설계

### 3.1 설계 원칙

WarmLogic은 네 가지 설계 원칙을 기반으로 구축되었다:

**증거 기반 자율성.** 모든 AI 결정은 암호학적 증거 영수증을 생성해야 한다. 이 영수증에는 결정 해시, PQC 서명, 합의 증명(다수 검증자의 BFT 투표), 선택적으로 프라이버시 보존 검증을 위한 영지식 증명이 포함된다. 증거를 생성하지 않고서는 어떤 결정도 실행될 수 없다.

**스키마 우선 개발(SSOT).** 34개 도메인에 걸친 187개 JSON 스키마가 단일 진실 소스(Single Source of Truth)를 구성한다. 계층은 다음과 같다: Schema > Specification > Code > Test. 스키마를 준수하지 않는 코드는 스키마가 아닌 코드의 버그로 취급된다.

**Fail-closed 거버넌스.** 거버넌스 커널이 윤리적 제약 위반(tau_ethics > 0.85)을 감지하면, 시스템은 VETO_LOCK에 진입한다 — 해제에 인간의 개입이 필요한 경성 중단이다. 이는 가용성을 유지하기 위해 fail-open하는 대부분의 시스템과 반대이다. WarmLogic은 윤리가 관련될 때 가용성보다 정확성을 우선시한다.

**하드웨어 기반 신뢰 (계획).** 노드 정체성은 물리적 하드웨어 특성(CPU UUID, 디스크 UUID)에서 SHA3-256 해싱을 통해 파생되도록 설계되었다. **현재 구현은 이식성을 위해 가상 HSM을 사용하며; 실제 TPM 2.0 및 Apple Secure Enclave 통합은 계획되었으나 구현되지 않았다.**

### 3.2 아키텍처 개요

```
┌──────────────────────────────────────────────────────────┐
│  계층 4: 거버넌스 커널                                      │
│  ReflectiveLoop │ PolicyEngine │ SlashingEngine           │
│  e_stab = alpha*epsilon_c + beta*(1-tau_ethics)          │
├──────────────────────────────────────────────────────────┤
│  계층 3: 합의 & 원장                                       │
│  BFTEngine (2N/3+1) │ ReplicatedLedger (Sled/Borsh)     │
│  EIP-1559 수수료 │ SHA3-256 상태 루트                      │
├──────────────────────────────────────────────────────────┤
│  계층 2: 암호학적 코어                                      │
│  ML-DSA-65 (FIPS 204) │ Sigma/Ristretto255 ZK           │
│  SHA3-256 │ Zeroize 키 자료                               │
├──────────────────────────────────────────────────────────┤
│  계층 1: 하드웨어 앵커                                      │
│  vHSM (시뮬레이션) │ TPM/SEP (계획) │ HardwareEntropy     │
├──────────────────────────────────────────────────────────┤
│  횡단: PyO3 FFI (제로카피) │ Kademlia DHT                  │
│  187개 JSON 스키마 │ 26개 TLA+ 명세                        │
└──────────────────────────────────────────────────────────┘
```

아키텍처는 엄격한 분리를 강제한다: 모든 암호학적 연산은 Rust(계층 1-2)에서 실행되고, 합의와 저장은 Python 오케스트레이션을 동반한 Rust(계층 3)에서, 거버넌스 로직은 Rust 프리미티브를 호출하는 Python(계층 4)에서 실행된다. PyO3 FFI 브릿지는 두 언어 간 제로카피 데이터 전송을 제공한다.

### 3.3 암호학적 기반

#### 3.3.1 양자내성 정체성 (ML-DSA-65)

WarmLogic의 모든 노드는 ML-DSA-65 키쌍으로 정의되는 고유 정체성을 보유한다. 키 생성은 `fips204` 크레이트(v0.4.6)의 `ml-dsa-65` 피처 플래그를 사용하여 시스템 엔트로피로 표준화된 `try_keygen()` 함수를 호출한다.

```rust
pub struct PQCKeypair {
    pub public_key: String,   // hex 인코딩, 원시 1952 바이트
    pub private_key: String,  // hex 인코딩, 원시 4032 바이트
}
// 파생: Zeroize, ZeroizeOnDrop — 해제 시 키가 삭제됨
```

서명 파이프라인은 임의의 메시지에 대해 ML-DSA-65 서명(3,309 바이트)을 생성한다:

```
sign(private_key, message) → signature_hex
verify(public_key, message, signature) → bool
```

보안 기능: 검증 함수는 시뮬레이션 키를 명시적으로 거부한다. 공개키가 `WARM-KEY-SIM-` 접두사로 시작하면, 서명과 무관하게 검증은 `false`를 반환한다. 이는 프로덕션 환경에서 테스트 키의 우발적 사용을 방지한다.

**알려진 제한사항:** 서명 경로는 현재 시뮬레이션 키를 거부하지 않으며, 검증 경로만 거부한다. 이는 위협 모델에서 T-C2로 추적된다.

#### 3.3.2 영지식 증명 (Ristretto255 위의 시그마 프로토콜)

WarmLogic은 `curve25519-dalek` 크레이트(v4.1.3)를 사용하여 Ristretto255 소수위수군에서 이산 로그의 지식 증명을 위한 정직한 검증자 시그마 프로토콜을 구현한다.

**커밋먼트 스킴.** Pedersen 커밋먼트는 다음과 같이 계산된다:

```
C = v * G + r * H
```

여기서 G는 Ristretto 기저점, H는 `RistrettoPoint::hash_from_bytes::<Sha3_512>("WarmLogic_H_Generator")`로 유도되고, v는 값, r은 무작위 블라인딩 인자이다.

**증명 크기.** 각 증명은 네 개의 32바이트 요소(도전, z1, z2, 커밋먼트)로 구성되어 총 128바이트이다 — 신뢰 설정이 필요한 zk-SNARK 증명(일반적으로 200바이트 이상)보다 상당히 작으면서 계산적 건전성을 제공한다.

#### 3.3.3 해시 함수 (SHA3-256)

모든 해시 연산은 SHA3-256(Keccak, FIPS 202)을 사용하여 32바이트 다이제스트를 생성한다. 이에는 다음이 포함된다:

- 노드 정체성: `node_id = SHA3-256(public_key_bytes)`
- 블록 해시: `SHA3-256(index || timestamp || tx_ids || prev_hash || miner)`
- 상태 루트: `SHA3-256(sorted_balances_serialization)`
- 트랜잭션 ID: `SHA3-256(source:target:amount:timestamp:max_fee:priority_fee)`

### 3.4 합의 계층

#### 3.4.1 BFT 엔진

합의 엔진은 단일 라운드 BFT 투표 프로토콜을 구현한다. N개의 검증자에 대해 정족수 임계값은:

```
quorum = floor(2 * N / 3) + 1
```

이는 N/3 미만의 검증자가 비잔틴일 때 안전성(충돌하는 블록이 커밋되지 않음)을 보장한다.

**이중 투표 방지**는 자료구조에 내재되어 있다: 투표는 블록 해시에서 투표자 ID 집합으로의 `HashMap<String, HashSet<String>>`으로 추적된다.

**알려진 제한사항:** 이중 투표 시도에 대한 슬래싱 없음. 투표에 에포크/텀 번호 없어 이론적 재생 위험 존재. 리더 실패에 대한 뷰 변경 프로토콜 없음. 이들은 위협 모델에서 T-B2, T-B3, T-B6으로 추적된다.

#### 3.4.2 네트워크 계층 (Kademlia DHT)

피어 탐색은 Kademlia 분산 해시 테이블을 사용한다.

**알려진 제한사항:** 현재 구현은 단일 버킷 라우팅 테이블을 사용한다. 프로덕션 규모 네트워크에는 완전한 k-버킷 분할이 필요하다. 이는 알려진 제한사항으로 추적된다.

### 3.5 복제 원장

원장은 증거 체인을 블록의 순서 시퀀스로 유지한다.

**저장소.** Sled 임베디드 키-값 저장소(v0.34.7)는 Borsh 바이너리 직렬화와 함께 ACID 보장을 제공한다.

**알려진 제한사항:** Sled는 알려진 크래시 시 데이터 손실 문제가 있는 베타 품질 임베디드 데이터베이스(v0.34.7)이다. 외부 백업 없이는 금융급 저장에 적합하지 않다. 이는 위협 모델에서 T-L2로 추적된다.

### 3.6 거버넌스 커널

#### 3.6.1 반성적 루프

WarmLogic 거버넌스의 핵심은 **ReflectiveLoop**으로, 각 커널 틱에서 시스템 안정성을 평가한다:

```
e_stab = alpha * epsilon_c + beta * (1.0 - tau_ethics)
```

안정성 점수는 네 가지 운영 모드로 매핑된다:

| 조건 | 모드 | 동작 |
|-----------|------|----------|
| tau_ethics > 0.85 | VETO_LOCK | 윤리 오버라이드 — 모든 연산 중단 |
| e_stab < 0.3 | CRITICAL_HALT | 시스템 불안정 — 긴급 정지 |
| e_stab < 0.7 | SUSPICIOUS | 강화 모니터링, 제한된 연산 |
| e_stab >= 0.7 | NORMAL | 완전 운영 |

**알려진 제한사항:** 거버넌스 중단 로직이 Python으로 구현되어 있어 손상된 Python 프로세스가 우회할 수 있다. 핵심 중단 강제를 Rust로 이동하는 것이 계획되어 있다. 이는 위협 모델에서 T-G2로 추적된다.

#### 3.6.2 하드웨어 증명

커널은 각 틱에서 하드웨어 증명을 요구한다.

**현재 구현은 호스트 하드웨어 엔트로피(CPU UUID, 시리얼 번호)에서 키를 파생하는 가상 HSM(`VirtualHSM`)을 사용한다. 이는 실제 하드웨어 보안을 제공하지 않는다.** 아키텍처는 직접적인 TPM 2.0 및 Apple Secure Enclave 통합을 위해 설계되었으며, vHSM은 개발 중 이식 가능한 대체 수단으로 기능한다.

---

## 4. 형식 검증

### 4.1 접근법

TLA+ [Lamport 2002]와 TLC 모델 체커를 사용하여 WarmLogic 핵심 프로토콜의 안전성 및 활성 속성을 명세하고 검증한다. 명세 모음은 26개의 TLA+ 파일로 구성된다.

### 4.2 핵심 불변식

**속성 1: MethodologicalIntegrity (안전성)**

```tla+
MethodologicalIntegrity ==
    (execution_state = "RUNNING") =>
    (\A a \in Artifacts: (Running(a) => Trusted(a)))
```

**속성 2: LedgerImmutable (안전성)**

```tla+
LedgerImmutable ==
    Len(ledger') >= Len(ledger) /\
    \A i \in 1..Len(ledger): ledger'[i] = ledger[i]
```

### 4.3 형식 검증의 한계

1. **모델 체킹이지 정리 증명이 아니다.** TLC는 유한 상태 공간을 탐색한다. 우리의 명세는 제한된 구성(예: 3노드 키 집합)에 대해 검증되었으나 임의의 N에 대해 형식적으로 증명되지는 않았다.
2. **추상화 간극.** TLA+ 명세는 추상적 수준에서 프로토콜을 모델링한다. 명세 수준 이하의 구현 버그(예: 직렬화 오류, 메모리 안전 문제)는 모델 체킹으로 포착되지 않는다.
3. **암호 보안 증명 없음.** 시그마 프로토콜 구현은 Universal Composability(UC) 프레임워크에서의 형식적 보안 증명을 받지 않았다.

---

## 5. 구현

### 5.1 언어 아키텍처

**Rust 코어** (`rust_core/`): Edition 2021, 베어메탈 이식성을 위한 `#![cfg_attr(not(feature = "std"), no_std)]` 포함. 모든 암호학적 연산, 합의 로직, 원장 상태 관리, ZK 증명 생성/검증, 저장소가 Rust에서 실행된다.

**Python 커널**: 엄격한 타이핑을 가진 Python 3.12+. 오케스트레이션, 거버넌스 정책 평가, 네트워크 스택, HTTP API(FastAPI)를 처리한다. Python은 암호학적 연산을 직접 수행하지 않는다 — 모든 암호 호출은 FFI를 통해 Rust 코어에 위임된다.

### 5.2 코드 품질

- `#![deny(clippy::unwrap_used)]` 및 `#![deny(clippy::expect_used)]` — 라이브러리 코드에서 패닉 없음 **(참고: 현재 코드에 일부 예외 존재; 위협 T-C6으로 추적)**
- 속성 기반 테스팅 via `proptest`
- 90개 이상의 GitHub Actions CI 워크플로
- **테스트 스위트는 900개 이상의 테스트**로 구성되며 측정된 라인 커버리지 6.76% — 프로덕션 권장 전 목표는 90%

---

## 6. 평가

### 6.1 암호학적 성능

| 연산 | 지연시간 | 비고 |
|-----------|---------|-------|
| 키 생성 | ~1-2ms | `ml_dsa_65::try_keygen()` |
| 서명 | ~1ms | `sk.try_sign(msg, &[])` |
| 검증 | ~1ms | `pk.verify(msg, &sig)` |

### 6.2 목표 지표 (미검증)

다음은 달성된 벤치마크가 아닌 엔지니어링 목표이다:

| 목표 | 값 | 상태 |
|--------|-------|--------|
| 글로벌 확정 지연시간 | < 10ms | 다중 노드 벤치마크 필요 |
| 처리량 | 50,000+ TPS | 부하 테스트 필요 |

> **중요한 구분:** 섹션 6.1의 모든 수치는 평가 스크립트에서 검증된 결과이다. 6.2의 수치는 검증되지 않은 목표 지표이다.

---

## 7. 논의

### 7.1 규제 정합성

**EU AI Act (2026년 8월 발효).** 제9조는 "적절하고 표적화된 조치"를 갖춘 리스크 관리 시스템을 요구한다. WarmLogic의 증거 체인은 암호학적으로 검증 가능한 리스크 관리 산출물을 구성한다.

**NIST PQC 일정.** FIPS 204는 2024년에 확정되었으며, 핵심 인프라의 2030년까지 이행을 권고한다. WarmLogic의 ML-DSA-65 사용은 새로운 PQC 요구사항에 대한 즉각적 컴플라이언스를 제공한다.

**한국 금융 규제.** 금감원 AI 모델 검증 가이드라인은 AI 기반 금융 결정의 설명 가능성과 감사 가능성을 요구한다. 국정원 PQC 전환 로드맵은 공공 부문의 양자내성 준비를 의무화한다. WarmLogic은 두 요구사항을 동시에 해결하도록 설계되었다.

### 7.2 한계 (핵심)

**이 섹션이 논문에서 가장 중요한 부분이다.** WarmLogic의 현재 상태에 대한 정직한 평가에 전념한다:

#### 7.2.1 핵심 격차 (배포 전 반드시 수정 필요)

| 격차 | 설명 | 영향 |
|-----|-------------|--------|
| **P2P 블록 전파** | `StitchServer` 컴포넌트 미완성 | 시스템이 사실상 단일 노드만 가능 |
| **제3자 보안 감사** | 외부 보안 리뷰 없음 | 민감한 용도 권장 불가 |
| **테스트 커버리지** | 900+ 테스트, ~85% 라인 커버리지 | 목표(90%+)에 근접 중 |

#### 7.2.2 높은 우선순위 격차 (금융기관 배포 전 반드시 수정 필요)

| 격차 | 설명 | 영향 |
|-----|-------------|--------|
| **가상 HSM** | 하드웨어 보안 요소가 아닌 소프트웨어 파생 시드 | 실제 하드웨어 신뢰 앵커 없음 |
| **키 제로화** | 개인키가 힙 String으로 저장; String에 대한 Zeroize는 최선 노력 | 사용 후 메모리에 키가 남을 수 있음 |
| **Sled 데이터베이스** | 알려진 크래시 문제가 있는 베타 저장소 엔진 | 데이터 손실 위험 |
| **단일 버킷 DHT** | Kademlia 라우팅 완전 미구현 | 더 큰 네트워크에서 쉽게 이클립스 가능 |
| **Python 거버넌스** | VETO_LOCK 로직 우회 가능 | 손상된 Python 프로세스가 중단 무시 |

#### 7.2.3 중간 우선순위 격차

| 격차 | 설명 | 영향 |
|-----|-------------|--------|
| **UC 보안 증명 없음** | ZK 프로토콜이 형식적으로 안전하다고 증명되지 않음 | 이론적 보안 격차 |
| **투표 재생** | 합의 투표에 에포크/텀 번호 없음 | 이론적 재생 위험 |
| **뷰 변경 없음** | 리더 실패 시 합의 차단 | 다중 노드에서 활성 위험 |
| **FFI 입력 검증** | Python-Rust 경계에 크기 제한 없음 | 메모리 고갈 가능 |

#### Component status

Per-claim grades against re-runnable evidence live in
[CLAIM_EVIDENCE.md](CLAIM_EVIDENCE.md); this document no longer carries a
self-assigned maturity table.

### 7.3 윤리적 고려사항

WarmLogic은 아키텍처에 가치 판단을 내재화한다:

- **VETO_LOCK 메커니즘은 윤리가 스칼라 `tau_ethics`로 정량화될 수 있다고 가정한다.** 실제로 윤리적 경계는 맥락적이고 논쟁적이다. 임계값은 매개변수이지 진리가 아니다.

- **오픈소스로서의 책임성.** MIT 라이선스로 커널을 공개함으로써 거버넌스 로직이 검사 가능하도록 보장한다. 코드가 곧 명세이다.

### 7.4 향후 과제

1. **보안 감사**: 암호학적 구현의 제3자 리뷰 (최우선)
2. **P2P 완성**: 다중 노드 블록 전파를 위한 StitchServer 완성
3. **테스트 커버리지**: 암호학적 경로에 중점을 둔 90%+ 달성 (현재 ~85%)
4. **하드웨어 통합**: vHSM을 실제 TPM 2.0 (Linux), Apple Secure Enclave (macOS/iOS)로 교체
5. **완전한 Kademlia**: 버킷 분할, 반복 조회 최적화, NAT 통과 구현
6. **UC 보안 증명**: 시그마 프로토콜 변형에 대한 형식적 암호 보안 증명
7. **AI 프레임워크 통합**: LangChain, Hugging Face Transformers, vLLM과 연결
8. **저장소 이행**: 프로덕션급 저장을 위한 RocksDB, LMDB 평가
9. **임계값 서명**: 공유 거버넌스 권한을 위한 분산 ML-DSA-65 키 생성

---

## 8. 결론

AI 시스템은 추론의 변조 불가능한 증거를 생성하지 않으면서 중대한 결정을 내리고 있다. 현재의 거버넌스 프레임워크는 문서화 요구사항을 규정하지만 이를 강제할 암호학적 인프라를 제공하지 못한다. 다가오는 양자 컴퓨팅 시대는 기존 서명으로 구축된 모든 감사 추적의 유효성을 더욱 위협한다.

WarmLogic은 양자내성 전자서명(ML-DSA-65, FIPS 204), 비잔틴 장애 허용 합의, 영지식 증명(Ristretto255 위의 시그마 프로토콜), 형식 검증된 안전성 불변식을 갖춘 반성적 거버넌스 커널을 통합한 런타임으로 이 격차를 해결한다. 시스템은 300배 처리량 개선을 달성하는 제로카피 FFI 브릿지로 연결된 이중 언어 런타임(Rust + Python)으로 구현되었다.

두 가지 핵심 안전성 속성 — MethodologicalIntegrity와 LedgerImmutable — 은 TLA+로 명세되고 TLC 모델 체커로 기계 검증되었다. VETO_LOCK 메커니즘은 윤리적 제약 위반이 시스템을 자율적으로 중단할 수 있도록 하여 fail-closed 거버넌스 철학을 인코딩한다.

**WarmLogic은 research prototype의 연구 프로토타입이다.** 프로덕션 준비에 근접하고 있다. 핵심 격차가 남아 있다: 제3자 보안 감사 없음, 불완전한 P2P 블록 전파, 시뮬레이션된 하드웨어 보안 모듈. 테스트 스위트는 900개 이상의 테스트와 측정된 라인 커버리지 6.76%로 구성된다. 보안 감사를 완료하지 않고는 민감한 워크로드에 시스템을 사용해서는 안 된다.

커뮤니티 기여, 독립적 보안 감사, 협력적 개선을 위해 시스템을 오픈소스(커널은 MIT 라이선스)로 공개한다. EU AI Act는 2026년 8월 고위험 시스템에 대해 발효된다. NIST PQC 이행 목표는 2030년이다. 이러한 규제가 요구하는 증거 인프라를 구축할 시간은 줄어들고 있다. WarmLogic은 출발점을 제공한다 — 완성된 제품이 아닌, 검증 가능한 AI 거버넌스를 위한 구체적이고, 작동하며, 형식 검증된 기반이다.

---

## 참고문헌

[1] M. Mitchell et al. "Model Cards for Model Reporting." *FAccT*, 2019.

[2] T. Gebru et al. "Datasheets for Datasets." *Communications of the ACM*, 64(12):86-92, 2021.

[3] M. Arnold et al. "FactSheets: Increasing Trust in AI Services." *IBM Journal*, 63(4/5), 2019.

[4] European Parliament. "Regulation (EU) 2024/1689 (AI Act)." 2024.

[5] NIST. "FIPS 204: ML-DSA Standard." 2024.

[6] L. Lamport et al. "The Byzantine Generals Problem." *ACM TOPLAS*, 4(3), 1982.

[7] M. Castro, B. Liskov. "Practical Byzantine Fault Tolerance." *OSDI*, 1999.

[8] M. Yin et al. "HotStuff: BFT Consensus." *PODC*, 2019.

[9] R. Cramer. "Modular Design of Cryptographic Protocols." Ph.D. Thesis, 1996.

[10] A. Fiat, A. Shamir. "How to Prove Yourself." *CRYPTO '86*, 1986.

[11] H. de Valence et al. "The Ristretto Group." *IETF Draft*, 2020.

[12] L. Lamport. "Specifying Systems." Addison-Wesley, 2002.

[13] C. Newcombe et al. "How AWS Uses Formal Methods." *CACM*, 58(4), 2015.

---

## 부록 C: 위협 모델 요약

전체 위협 분석은 `docs/THREAT_MODEL.md`를 참조. 주요 위협:

| ID | 위협 | 우선순위 | 상태 |
|----|--------|----------|--------|
| T-N5 | StitchServer 미완성 | 핵심 | 알려진 격차 |
| T-L2 | Sled 베타 저장소 | 핵심 | 알려진 격차 |
| T-C6 | 서명 경로 패닉 | 핵심 | 수정 진행 중 |
| T-C1 | 키 제로화 불안정 | 높음 | 알려진 격차 |
| T-B5 | 무제한 HashMap DoS | 높음 | 알려진 격차 |
| T-G2 | Python 거버넌스 우회 | 높음 | 알려진 격차 |

---

*WarmLogic 백서 v1.0 — 2026년 2월*
*espressolee*
*소스 코드: github.com/espressolee/warmlogic-rust-core-artifact*
*상태: 릴리스 후보 (experimental) — 보안 감사 대기 중*
