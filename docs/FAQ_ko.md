# WarmLogic 자주 묻는 질문 (FAQ)

> **상태**: 연구 프로토타입. 외부 검증 없음. docs/CLAIM_EVIDENCE.md 참조.
> 일부 기능은 프로토타입 상태입니다.

---

## 목차

1. [일반 질문](#일반-질문)
2. [설치](#설치)
3. [사용법](#사용법)
4. [아키텍처](#아키텍처)
5. [보안](#보안)
6. [성능](#성능)
7. [문제 해결](#문제-해결)

---

## 일반 질문

### WarmLogic이란 무엇인가요?

WarmLogic은 다음을 결합한 AI 거버넌스 런타임입니다:
- **포스트 양자 암호화** (ML-DSA-65, FIPS 204)
- **비잔틴 장애 허용 합의** (BFT)
- **영지식 증명** (Sigma 프로토콜)
- **헌법적 거버넌스 커널**

이를 통해 AI 결정이 안전하고, 검증 가능하며, 변조 방지되도록 보장합니다.

---

### WarmLogic은 누구를 위한 것인가요?

- AI 결정의 감사 증거가 필요한 **기업**
- AI 시스템에 암호화 검증이 필요한 **규제 산업** (금융, 의료, 법률)
- 포스트 양자 보안을 구현하는 **보안 연구원**
- 분산 AI 거버넌스를 탐구하는 **개발자**

---

### WarmLogic의 현재 상태는 무엇인가요?

WarmLogic은 **research prototype** (기술 준비도 레벨 7)에 있습니다:
- 시스템 프로토타입 시연 완료
- 내부 테스트 통과
- 1.0 안정 버전 전 API 변경 가능

---

### 프로덕션 사용 준비가 되었나요?

아직입니다. research prototype은 프로토타입 시연을 의미합니다. 프로덕션 배포 전:
- 외부 보안 감사와 멀티노드 운영 검증을 통과해야 함
- 제3자 보안 감사 필요
- HSM 통합 필요 (현재 시뮬레이션됨)

---

### 라이선스는 무엇인가요?

WarmLogic은 **MIT 라이선스**입니다. 상용 및 비상용 사용이 자유롭습니다.

---

## 설치

### 시스템 요구 사항은 무엇인가요?

| 구성 요소 | 최소 | 권장 |
|-----------|------|------|
| Python | 3.12+ | 3.12.1 |
| Rust | 1.75+ | 1.78+ |
| RAM | 4 GB | 8 GB+ |
| 디스크 | 2 GB | 10 GB (로그용) |
| OS | Linux, macOS | Ubuntu 22.04, macOS 14+ |

---

### Docker를 사용할 수 있나요?

네! Docker가 가장 쉬운 방법입니다:

```bash
docker pull ghcr.io/espressolee/warmlogic:latest
docker run -it warmlogic wlctl status
```

자세한 내용은 [설치 가이드](INSTALLATION.md)를 참조하세요.

---

### Rust를 설치해야 하나요?

**개발용**: 네, Rust 1.75+ 필요
**사용자용**: Docker 이미지 또는 사전 빌드된 휠 사용

---

### Windows에서 실행할 수 있나요?

WSL2를 통해 가능합니다. 네이티브 Windows는 지원되지 않습니다:

```bash
wsl --install -d Ubuntu-22.04
# WSL 내에서 Ubuntu 지침 따르기
```

---

## 사용법

### WarmLogic을 어떻게 시작하나요?

```bash
# 빠른 시작
wlctl init
wlctl start

# 상태 확인
wlctl status
```

자세한 내용은 [빠른 시작 튜토리얼](tutorial/01_quickstart.md)을 참조하세요.

---

### 첫 번째 결정은 어떻게 만드나요?

```python
from warm_logic.sdk import SovereignClient

client = SovereignClient()

decision = client.propose_action(
    intent="log_event",
    context={"event": "hello", "severity": "info"}
)

if decision.approved:
    print(f"승인됨: {decision.proof_hash}")
else:
    print(f"거부됨: {decision.rejection_reason}")
```

---

### 커스텀 정책은 어떻게 작성하나요?

`constitution.yaml`에서 정책을 정의합니다:

```yaml
policies:
  no_dangerous_actions:
    description: "위험한 작업 방지"
    rules:
      - intent: "delete_*"
        action: deny
        reason: "삭제 작업은 높은 권한 필요"
      - intent: "log_*"
        action: allow
```

---

## 아키텍처

### 아키텍처 다이어그램이 있나요?

```
+----------------------------------------------------------+
|                    WarmLogic 스택                         |
+----------------------------------------------------------+
|  애플리케이션 계층  |  CLI / 대시보드 UI / REST API        |
+---------------------+------------------------------------+
|  거버넌스 커널      |  헌법 / RBAC / 정책 VM              |
+---------------------+------------------------------------+
|  암호화 기판        |  ML-DSA-65 / ZK 증명 / BFT         |
+---------------------+------------------------------------+
|  저장소 계층        |  원장 / Sled DB / DHT 메시          |
+----------------------------------------------------------+
```

자세한 내용은 [아키텍처 문서](ARCHITECTURE_ko.md)를 참조하세요.

---

### ML-DSA-65란 무엇인가요?

ML-DSA-65 (FIPS 204)는 포스트 양자 디지털 서명 알고리즘입니다:
- **키 크기**: 1,952 바이트
- **서명 크기**: 3,309 바이트
- **서명 시간**: ~48 μs
- **양자 안전**: 예

Ed25519 (64바이트)보다 크지만 양자 컴퓨터에 안전합니다.

---

### BFT 합의는 어떻게 작동하나요?

WL-BFT-v1은 PBFT에서 영감을 받았습니다:

1. **제안**: 리더 노드가 결정을 제안
2. **투표**: 노드들이 투표
3. **쿼럼**: f < n/3 비잔틴 노드 허용
4. **확정**: 쿼럼 도달 시 최종화

지연: ~87ms (4노드), 처리량: 11.5/초

---

### 왜 Rust + Python인가요?

- **Rust**: 암호화 성능 (300배 빠름), 메모리 안전
- **Python**: 빠른 개발, ML 생태계 통합
- **PyO3**: 최소 오버헤드 (~0.3μs)로 둘을 연결

---

## 보안

### 위협 모델은 무엇인가요?

[THREAT_MODEL.md](THREAT_MODEL.md)를 참조하세요. 주요 위협:
- 양자 컴퓨터 공격 (ML-DSA-65로 완화)
- 비잔틴 노드 (BFT로 완화)
- 증거 변조 (암호화 원장으로 완화)

---

### HSM은 실제인가요 시뮬레이션인가요?

현재 **시뮬레이션**됩니다:
- 실제 HSM 통합은 로드맵에 있음
- 개발/테스트에는 시뮬레이션이 충분
- 프로덕션에서는 실제 HSM 필요

---

### 보안 문제를 어떻게 보고하나요?

70549809+espressolee@users.noreply.github.com로 이메일하세요. [SECURITY.md](../SECURITY.md)를 참조하세요.

---

## 성능

### 예상 지연 시간은 얼마인가요?

| 작업 | 지연 (p50) | 처리량 |
|------|------------|--------|
| ML-DSA-65 서명 | 48 μs | 20,833/초 |
| ML-DSA-65 검증 | 28 μs | 35,714/초 |
| BFT 합의 (4노드) | 87 ms | 11.5/초 |
| 증거 번들 | 8.2 ms | 122/초 |

자세한 벤치마크는 [BENCHMARKS_ko.md](BENCHMARKS_ko.md)를 참조하세요.

---

### 왜 합의가 87ms나 걸리나요?

BFT 합의는 여러 네트워크 라운드 트립이 필요합니다:
- 제안 전파: ~20ms
- 투표 수집: ~40ms
- 최종화: ~27ms

단일 노드 모드 (합의 없음)는 ~12ms입니다.

---

### 성능을 어떻게 향상시키나요?

1. 단일 노드 사용 (비임계 결정용)
2. 결정 배치 처리
3. 하드웨어 업그레이드 (SSD 필수)
4. 클러스터 크기 줄이기 (7 → 4 노드)

---

## 문제 해결

### "ModuleNotFoundError: warm_logic_rs"가 발생해요

Rust 코어가 빌드되지 않았습니다:

```bash
cd rust_core
maturin develop --release
cd ..
python -c "import warm_logic_rs; print('OK')"
```

---

### 커널이 시작되지 않아요

```bash
# 포트 확인
lsof -i :8000

# 로그 확인
cat ~/.warm_logic/logs/kernel.log

# 다른 포트 시도
wlctl start --port 8001
```

---

### 더 많은 문제 해결 방법은 어디서 찾나요?

- [TROUBLESHOOTING_ko.md](TROUBLESHOOTING_ko.md) - 전체 문제 해결 가이드
- [GitHub Issues](https://github.com/espressolee/warmlogic-rust-core-artifact/issues)
- [GitHub Discussions](https://github.com/espressolee/warmlogic-rust-core-artifact/discussions)

---

*마지막 업데이트: 2026-02-07*
