# 설치 가이드

WarmLogic은 **3줄**로 설치할 수 있도록 설계되었습니다.

> 원문: [INSTALLATION.md](INSTALLATION.md)

## 지원 플랫폼

- macOS (Apple Silicon & Intel)
- Linux (x86_64, ARM64)
- Docker (Universal)

## 옵션 1: 빠른 시작 (개발자용)

사전 요구사항: `python3.12+`, `rust 1.75+`, `make`

```bash
git clone https://github.com/espressolee/WarmLogic
cd warmlogic
make setup
```

이 명령은 다음을 수행합니다:
1. 가상 환경 생성 (수동 관리 시)
2. Python 의존성 설치
3. **Rust 코어 자동 컴파일** (`warm_logic_rs`, 하드웨어에 최적화)
4. 무결성 검증을 위한 테스트 스위트 실행

## 옵션 2: Docker (엔터프라이즈)

강화된 컨테이너에서 주권 커널을 실행합니다.

```bash
docker compose up -d
```

콕핏 접속: http://localhost:8033

## 문제 해결

### `maturin: command not found`

`make setup`이 실패하면 가상 환경이 활성화되어 있는지 확인하거나 `maturin`을 수동 설치하세요:

```bash
pip install maturin
```

### `Cargo not found`

Rust가 설치되어 있어야 합니다.

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

---

*마지막 업데이트: 2026-02-07*
