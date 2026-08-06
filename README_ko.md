# WarmLogic

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

> **모든 AI 결정에 암호학적 증거를.**
> 포스트 양자. 비잔틴 장애 허용. 로컬 퍼스트.

[![Version](https://img.shields.io/badge/version-1.0.0--rc1-blue)](src/warm_logic/VERSION)
[![License: MIT](https://img.shields.io/badge/kernel-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://python.org)
[![Rust](https://img.shields.io/badge/rust-1.75+-orange)](https://rust-lang.org)

---

## 왜 WarmLogic인가?

AI 에이전트는 "블랙박스"입니다. **왜** 그런 결정을 했는지, 규칙을 **따랐는지** 증명할 수 없습니다.

WarmLogic은 AI 추론을 **암호학적 커널**로 감싸 모든 결정에 대해 위조 불가능한 증거를 생성합니다.

| 문제점 | WarmLogic 해결책 |
|--------|-----------------|
| AI 결정은 검증 불가 | 모든 결정에 ML-DSA-65(포스트 양자) 서명 |
| 단일 장애점 | 노드 스웜 전체에 걸친 BFT 합의 |
| 프라이버시 vs 규정 준수 트레이드오프 | 데이터 노출 없이 규정 준수를 검증하는 영지식 증명 |
| 규제 불확실성 | 정형 검증된 헌법적 가드레일 |
| 중앙화된 AI에 대한 신뢰 | 로컬 퍼스트, 주권적 데이터 소유 |

---

## 아키텍처

```
+----------------------------------------------------------+
|                    WarmLogic 스택                         |
+----------------------------------------------------------+
|  애플리케이션 계층  |  CLI / 콕핏 UI / REST API            |
+---------------------+------------------------------------+
|  거버넌스 커널      |  헌법 / RBAC / 정책 VM              |
+---------------------+------------------------------------+
|  암호 기반 계층     |  ML-DSA-65 / ZK 증명 / BFT          |
+---------------------+------------------------------------+
|  저장소 계층        |  원장 / Sled DB / DHT 메시           |
+----------------------------------------------------------+
```

**핵심 컴포넌트:**

- **Rust 코어** (`rust_core/`): 고성능 암호화, 합의, 원장
- **Python 커널** (`src/warm_logic/`): 거버넌스 로직, SDK, 애플리케이션 계층
- **PyO3 브릿지**: 암호화 연산에서 순수 Python 대비 ~300배 빠름

---

## 핵심 기능

| 기능 | 설명 |
|------|------|
| **포스트 양자 암호화** | ML-DSA-65 (FIPS 204) 서명으로 양자 공격 방어 |
| **BFT 합의** | 노드 간 비잔틴 장애 허용 합의 |
| **영지식 증명** | 데이터 노출 없이 규정 준수 검증 |
| **헌법적 거버넌스** | 우회할 수 없는 정형 규칙 |
| **증거 번들** | 모든 결정에 대한 불변 감사 추적 |
| **로컬 퍼스트** | 데이터는 당신의 하드웨어에 |
| **스웜 메시** | Kademlia DHT 기반 P2P 네트워크 |

---

## 빠른 시작

### 사전 요구사항
- Python 3.12+
- Rust 1.75+
- macOS, Linux 또는 Docker

### 설치 (3줄)

```bash
git clone https://github.com/espressolee/warmlogic-rust-core-artifact
cd warmlogic
make setup
```

이 명령은 의존성 설치, Rust 코어 컴파일, 시스템 무결성 검증을 수행합니다.

### 소버린 커널 실행

```bash
# CLI 인터페이스 시작
warmlogic

# 또는 웹 대시보드로 시작
python -m warm_logic.ui.server
```

### Docker (대안)

```bash
docker-compose up -d
# 대시보드: http://localhost:8000
```

---

## 첫 번째 소버린 결정

```python
from warm_logic.sdk import SovereignClient

# 로컬 커널에 연결
client = SovereignClient()

# 액션 제안
decision = client.propose_action(
    intent="send_email",
    context={"to": "user@example.com", "subject": "안녕하세요"}
)

# 모든 결정은 암호학적 증거를 가짐
print(f"결정: {decision.verdict}")
print(f"증거 해시: {decision.proof_hash}")
print(f"PQC 서명: {decision.signature[:32]}...")
```

---

## 벤치마크

| 지표 | 값 | 비고 |
|------|-----|------|
| ML-DSA-65 서명 | ~50 us | 포스트 양자 서명 |
| ML-DSA-65 검증 | ~30 us | 검증 |
| BFT 합의 (4노드) | <100 ms | 합의 지연시간 |
| 증거 번들 | <10 ms | 전체 감사 패키지 |
| PyO3 FFI 오버헤드 | <1 us | Rust-Python 브릿지 |

*Apple M2 기준. 자세한 내용은 [docs/BENCHMARKS.md](docs/BENCHMARKS.md) 참조.*

---

## 문서

| 문서 | 설명 |
|------|------|
| [설치 가이드](docs/INSTALLATION_ko.md) | 상세 플랫폼별 설치 지침 |
| [아키텍처](docs/ARCHITECTURE_ko.md) | 시스템 설계 상세 |
| [백서](docs/WHITEPAPER_ko.md) | 학술적 기반 |
| [기술 명세](docs/TECHNICAL_SPEC_ko.md) | 프로토콜 세부사항 |
| [API/SDK 레퍼런스](docs/API_SDK_ko.md) | 개발자 API 문서 |
| [튜토리얼](docs/tutorial/) | 단계별 가이드 |
| [용어집](docs/GLOSSARY_ko.md) | 용어 참조 |

---

## 프로젝트 상태

> **research prototype**: 시스템 프로토타입 실증
> 1.0 안정 릴리스 전 API가 변경될 수 있습니다.

| 컴포넌트 | 상태 |
|----------|------|
| Rust 암호 코어 | 안정 |
| Python 커널 | 안정 |
| BFT 합의 | 베타 |
| 영지식 증명 | 알파 |
| 하드웨어 어테스테이션 | 계획됨 |

---

## 기여하기

기여를 환영합니다! 가이드라인은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

```bash
# 테스트 실행
pytest

# 커버리지 포함 실행
pytest --cov=warm_logic

# 코드 포맷
make format
```

---

## 보안

취약점을 발견하셨나요? 책임 있는 공개를 위해 [SECURITY.md](SECURITY.md)를 참조하세요.

---

## 커뮤니티

- [GitHub Discussions](https://github.com/espressolee/warmlogic-rust-core-artifact/discussions)
- [Issue Tracker](https://github.com/espressolee/warmlogic-rust-core-artifact/issues)

---

## 라이선스

MIT 라이선스. 누구나 자유롭게 사용 가능.

---

## 감사의 글

WarmLogic은 다음을 기반으로 합니다:
- [ML-DSA (FIPS 204)](https://csrc.nist.gov/pubs/fips/204/final) - NIST 포스트 양자 표준
- [PyO3](https://pyo3.rs/) - Rust-Python 바인딩
- [Sled](https://sled.rs/) - 임베디드 데이터베이스
- 오픈소스 암호화 커뮤니티

---

*Resonance 팀이 신념을 담아 만들었습니다.*
