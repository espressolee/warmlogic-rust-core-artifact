# WarmLogic 문제 해결 가이드

> **상태**: 연구 프로토타입. 외부 검증 없음. docs/CLAIM_EVIDENCE.md 참조.
> 일부 문제는 소프트웨어의 프로토타입 특성으로 인한 것일 수 있습니다.

---

## 목차

1. [설치 문제](#설치-문제)
2. [런타임 오류](#런타임-오류)
3. [성능 문제](#성능-문제)
4. [네트워크 문제](#네트워크-문제)
5. [데이터베이스 문제](#데이터베이스-문제)
6. [SDK/API 오류](#sdkapi-오류)
7. [일반 오류 메시지](#일반-오류-메시지)
8. [진단 명령어](#진단-명령어)
9. [도움 받기](#도움-받기)

---

## 설치 문제

### `maturin: command not found`

**증상**: `make setup`이 maturin을 찾지 못해 실패합니다.

**해결책**:
```bash
# 먼저 가상 환경 활성화
source .venv/bin/activate

# maturin 설치
pip install maturin

# 설정 재시도
make setup
```

---

### `Cargo not found` 또는 `rustc not found`

**증상**: Rust 툴체인이 설치되지 않았습니다.

**해결책**:
```bash
# Rust 설치
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 셸 다시 로드
source ~/.cargo/env

# 확인
rustc --version  # 1.75+ 이어야 함
```

---

### `Python.h not found`

**증상**: 컴파일이 Python 헤더를 찾지 못해 실패합니다.

**해결책**:
```bash
# Ubuntu/Debian
sudo apt install python3.12-dev

# macOS (Homebrew)
brew reinstall python@3.12

# Fedora
sudo dnf install python3.12-devel
```

---

### `OpenSSL not found`

**증상**: Rust 컴파일이 OpenSSL 오류로 실패합니다.

**해결책**:
```bash
# Ubuntu/Debian
sudo apt install libssl-dev pkg-config

# macOS
brew install openssl
export OPENSSL_DIR=$(brew --prefix openssl)

# Fedora
sudo dnf install openssl-devel
```

---

### Apple Silicon에서 Rust 컴파일 실패

**증상**: M1/M2/M3 Mac에서 빌드 오류 발생.

**해결책**:
```bash
# 올바른 타겟 확인
rustup target add aarch64-apple-darwin

# 정리 후 재빌드
cd rust_core
cargo clean
maturin develop --release
```

---

### pip install 중 `Permission denied`

**증상**: 패키지를 설치할 수 없습니다.

**해결책**:
```bash
# 절대 sudo pip 사용 금지. 가상 환경 사용.
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 런타임 오류

### `ModuleNotFoundError: No module named 'warm_logic_rs'`

**증상**: Rust 코어가 로드되지 않았습니다.

**해결책**:
```bash
# Rust 코어 재빌드
cd rust_core
maturin develop --release
cd ..

# 확인
python -c "import warm_logic_rs; print('OK')"
```

---

### `ImportError: cannot import name 'SovereignClient'`

**증상**: SDK 임포트가 실패합니다.

**해결책**:
```bash
# 편집 가능 모드로 재설치
pip install -e .

# 확인
python -c "from warm_logic.sdk import SovereignClient; print('OK')"
```

---

### 커널이 시작되지 않음

**증상**: `wlctl start`가 멈추거나 실패합니다.

**진단**:
```bash
# 포트가 사용 중인지 확인
lsof -i :8000

# 로그 확인
cat ~/.warm_logic/logs/kernel.log

# 다른 포트 시도
wlctl start --port 8001
```

---

### `VETO_LOCK` 상태에서 멈춤

**증상**: 커널이 VETO_LOCK에 진입하고 복구되지 않습니다.

**해결책**:
```bash
# 현재 상태 확인
wlctl status

# 강제 복구 (안전한 경우)
wlctl recover --force

# 또는 깨끗한 상태로 재시작
wlctl stop
rm -rf ~/.warm_logic/state/
wlctl start
```

---

## 성능 문제

### 첫 번째 작업이 느림

**증상**: 첫 API 호출이 수 초 걸립니다.

**원인**: JIT 컴파일 및 캐시 워밍.

**해결책**: 예상된 동작입니다. 이후 호출은 더 빠릅니다.

---

### 높은 메모리 사용량

**증상**: 프로세스가 2GB 이상 RAM 사용.

**진단**:
```bash
# 메모리 확인
ps aux | grep warm_logic

# 배치 크기 줄이기
export WARM_LOGIC_BATCH_SIZE=100
```

---

### 느린 합의

**증상**: BFT 합의가 500ms 이상 걸림.

**진단**:
```bash
# 네트워크 지연 확인
ping <peer_ip>

# 노드 수 확인
wlctl peers

# 테스트용 클러스터 크기 줄이기
```

---

### 데이터베이스 느림

**증상**: 저장소 작업이 느립니다.

**해결책**:
```bash
# SSD 저장소 확인
df -h ~/.warm_logic

# 데이터베이스 압축
wlctl db compact

# 디스크 I/O 확인
iostat -x 1
```

---

## 네트워크 문제

### 피어에 연결할 수 없음

**증상**: `wlctl peers`가 0개 피어를 표시합니다.

**진단**:
```bash
# DHT가 실행 중인지 확인
wlctl status

# 방화벽 확인
sudo ufw status

# DHT 포트 허용
sudo ufw allow 4001/udp
```

---

### 부트스트랩 실패

**증상**: 기존 네트워크에 참가할 수 없습니다.

**해결책**:
```bash
# 부트스트랩 노드가 도달 가능한지 확인
nc -zv <bootstrap_ip> 4001

# 수동 부트스트랩 시도
wlctl bootstrap --peer <ip>:4001
```

---

### 메시지가 전파되지 않음

**증상**: 결정이 모든 노드에 도달하지 않습니다.

**진단**:
```bash
# 피어 연결 확인
wlctl peers --verbose

# 메시지 큐 확인
wlctl queue status
```

---

## 데이터베이스 문제

### `sled` 손상

**증상**: 시작 시 데이터베이스 오류 발생.

**해결책**:
```bash
# 현재 상태 백업
cp -r ~/.warm_logic/sled ~/.warm_logic/sled.bak

# 복구 시도
wlctl db recover

# 또는 새로 시작 (데이터 손실)
rm -rf ~/.warm_logic/sled
wlctl init
```

---

### 디스크 공간 부족

**증상**: 쓰기 오류 발생.

**해결책**:
```bash
# 공간 확인
df -h ~/.warm_logic

# 오래된 데이터 정리
wlctl db prune --before 30d

# 데이터 디렉토리 이동
export WARM_LOGIC_ROOT=/new/location
```

---

### 상태 불일치

**증상**: 해시 체인 검증 실패.

**해결책**:
```bash
# 체인 검증
wlctl verify --chain

# 백업에서 복원
wlctl restore --from /backup/location
```

---

## SDK/API 오류

### `ConnectionRefusedError`

**증상**: 커널에 연결할 수 없습니다.

**해결책**:
```python
# 커널이 실행 중인지 확인
# wlctl status

# 호스트/포트 확인
client = SovereignClient(host="127.0.0.1", port=8000)
```

---

### `PolicyViolationError`

**증상**: 정책에 의해 작업이 거부됨.

**해결책**:
```python
# 거부 이유 확인
print(decision.rejection_reason)
print(decision.violated_policy)

# constitution.yaml 검토
# 정책 또는 작업 조정
```

---

### `SignatureVerificationError`

**증상**: 서명 검증 실패.

**진단**:
```bash
# 키 유효성 확인
wlctl identity --verify

# 손상된 경우 재생성
wlctl identity --regenerate
```

---

### 타임아웃 오류

**증상**: 작업이 타임아웃됨.

**해결책**:
```python
# 타임아웃 증가
client = SovereignClient(timeout=60)

# 또는 작업별로
decision = client.propose_action(..., timeout=30)
```

---

## 일반 오류 메시지

| 오류 | 원인 | 해결책 |
|------|------|--------|
| `WARM-KEY-SIM-*` | 시뮬레이션 키 사용 | 개발 중 예상됨; 프로덕션에서는 실제 키 사용 |
| `Quorum not reached` | 노드 부족 | 노드 추가 또는 쿼럼 줄이기 |
| `Evidence bundle expired` | 오래된 증명 | 새 증거 요청 |
| `Policy not found` | 헌법 누락 | `wlctl init` 실행 |
| `Ledger hash mismatch` | 손상 | `wlctl verify --repair` 실행 |

---

## 진단 명령어

### 시스템 상태

```bash
# 전체 상태
wlctl status

# 상세 상태 점검
wlctl health --verbose

# 버전 정보
wlctl version
```

### 로그

```bash
# 최근 로그 보기
wlctl logs --tail 100

# 로그 따라가기
wlctl logs -f

# 디버그 레벨
WARM_LOGIC_LOG_LEVEL=DEBUG wlctl start
```

### 데이터베이스

```bash
# 데이터베이스 통계
wlctl db stats

# 무결성 확인
wlctl db verify

# 분석용 내보내기
wlctl db export --format json > dump.json
```

### 네트워크

```bash
# 피어 목록
wlctl peers

# 네트워크 통계
wlctl network stats

# 연결 테스트
wlctl ping <node_id>
```

### Python 진단

```python
import warm_logic_rs as wl
import warm_logic

# Rust 코어 확인
print(f"Rust 버전: {wl.__version__}")

# Python 버전 확인
print(f"Python 버전: {warm_logic.__version__}")

# 자체 테스트 실행
wl.self_test()
```

---

## 도움 받기

### 질문하기 전에

1. 이 가이드 확인
2. [FAQ_ko.md](FAQ_ko.md) 확인
3. [GitHub Issues](https://github.com/espressolee/WarmLogic/issues) 검색
4. 진단 실행: `wlctl diagnose > report.txt`

### 이슈 보고

포함할 내용:
- WarmLogic 버전: `wlctl version`
- Python 버전: `python --version`
- Rust 버전: `rustc --version`
- OS 및 버전
- 전체 오류 메시지
- 재현 단계
- 진단 출력: `wlctl diagnose`

### 리소스

- [GitHub Issues](https://github.com/espressolee/WarmLogic/issues)
- [GitHub Discussions](https://github.com/espressolee/WarmLogic/discussions)
- [FAQ_ko](FAQ_ko.md)
- [설치 가이드](INSTALLATION.md)

---

*마지막 업데이트: 2026-02-07*
