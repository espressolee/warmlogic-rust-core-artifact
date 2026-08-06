# WarmLogic 기술 사양서

> **버전**: 1.0-kinetic
> **상태**: 연구 프로토타입 (experimental)
> **대상**: 개발자, 기여자, 보안 연구자
> **라이선스**: MIT (커널) + ELv2 (엔터프라이즈 컴포넌트)

---

## 목차

1. [개요](#1-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [Rust 코어](#3-rust-코어)
4. [Python 커널](#4-python-커널)
5. [네트워크 프로토콜](#5-네트워크-프로토콜)
6. [스토리지 아키텍처](#6-스토리지-아키텍처)
7. [보안 모델](#7-보안-모델)
8. [API 레퍼런스](#8-api-레퍼런스)
9. [거버넌스 워크플로우](#9-거버넌스-워크플로우)
10. [배포](#10-배포)
11. [설정 레퍼런스](#11-설정-레퍼런스)
12. [스키마 시스템](#12-스키마-시스템)
13. [성능](#13-성능)
14. [구현 현황](#14-구현-현황)
15. [기여 방법](#15-기여-방법)
16. [부록: 상수 & 임계값](#16-부록-상수--임계값)

---

## 1. 개요

### 1.1 WarmLogic의 역할

WarmLogic은 AI 의사결정에 런타임 수준에서 **암호학적 증거**를 부착합니다. 모든 판단은:

1. 포스트양자 암호 (ML-DSA-65, FIPS 204)로 **서명**됩니다
2. 비잔틴 장애 허용 합의를 통해 **검증**됩니다
3. 변조 불가능한 임베디드 원장에 **저장**됩니다
4. 민감한 데이터를 노출하지 않고 영지식 증명으로 **증명 가능**합니다

### 1.2 설계 원칙

| 원칙 | 의미 | 구현 |
|------|------|------|
| **SSOT** | 스키마 > 스펙 > 코드 > 테스트 | 187개 JSON 스키마가 단일 진실 소스 |
| **증거 기반** | 모든 주장에 증거 필요 | 모든 상태 전이에 서명 포함 |
| **실패 시 차단** | 불확실할 때 중지 | `tau_ethics > 0.85` → VETO_LOCK |
| **하드웨어 루트** | 소프트웨어만으로는 신뢰 불충분 | TPM/CPU UUID 기반 키 유도 |

### 1.3 프로젝트 구조

```
WarmLogic/
├── warm_logic_rs/          Rust 코어 — 암호화, 합의, 원장, ZK 증명
│   └── src/
│       ├── crypto.rs       ML-DSA-65 (FIPS 204) 서명/검증
│       ├── consensus.rs    BFT 투표 엔진
│       ├── ledger.rs       복제 원장 + 상태 머신
│       ├── proof_zk.rs     Sigma 프로토콜 ZK 증명 (Ristretto255)
│       ├── storage.rs      Sled/메모리 스토어 추상화
│       ├── dht.rs          Kademlia 라우팅 테이블
│       ├── policy_engine.rs 정책 검증 엔진
│       ├── slashing.rs     위반 페널티 엔진
│       ├── hardware/       vHSM + 하드웨어 엔트로피
│       └── kernel.rs       반성 루프 + 모드 결정
├── warm_logic/             Python 커널 — 오케스트레이션, 거버넌스
│   ├── kernel/
│   │   ├── sys/            암호화 FFI 래퍼, 네트워킹, 합의
│   │   ├── mesh/           Kademlia DHT, 비컨 탐색, 동기화
│   │   ├── economy/        복제 원장 (Rust 위임)
│   │   ├── identity/       KineticIdentity (PQC 키 관리)
│   │   └── ops/            커널 루프, 작업 스케줄러, 정족수 관리자
│   ├── ui/                 Glass Browser (FastAPI, 포트 8000)
│   └── app/cockpit/        Sovereign Cockpit (FastAPI, 포트 5001)
└── spec/schema/            JSON 스키마 (187개 파일, 34개 도메인)
```

### 1.4 기술 스택

| 레이어 | 기술 | 목적 |
|--------|------|------|
| 암호화 | Rust + fips204 (ML-DSA-65) | 포스트양자 서명/검증 |
| 합의 | Rust BFTEngine | 비잔틴 장애 허용 투표 |
| ZK 증명 | Rust + curve25519-dalek | Ristretto255 기반 Sigma 프로토콜 |
| 원장 | Rust + Sled | 임베디드 KV 스토어, ACID |
| 오케스트레이션 | Python + FastAPI | HTTP API, 거버넌스 로직 |
| 네트워킹 | Python asyncio + UDP | Kademlia DHT, 비컨 탐색 |
| FFI | PyO3 0.22 | 제로카피 Rust↔Python 바인딩 |

---

## 2. 시스템 아키텍처

### 2.1 레이어 다이어그램

```
┌──────────────────────────────────────────────────────────┐
│                     사용자 인터페이스                       │
│  Glass Browser (포트 8000)  │  Cockpit (포트 5001)  │ TUI │
├──────────────────────────────────────────────────────────┤
│                    Python 커널 레이어                      │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐   │
│  │  Mesh   │ │ Economy │ │ Identity │ │  Governance  │   │
│  │  (DHT)  │ │ (원장)  │ │(Kinetic) │ │   (정책)     │   │
│  └────┬────┘ └────┬────┘ └────┬─────┘ └──────┬──────┘   │
├───────┼───────────┼───────────┼───────────────┼──────────┤
│                   PyO3 FFI 경계 (제로카피)                 │
├───────┼───────────┼───────────┼───────────────┼──────────┤
│                     Rust 코어 레이어                       │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐   │
│  │  DHT    │ │  원장   │ │  암호화  │ │   합의       │   │
│  │(라우팅) │ │ (Sled)  │ │(ML-DSA)  │ │   (BFT)      │   │
│  └─────────┘ └─────────┘ └──────────┘ └─────────────┘   │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐   │
│  │ ZK 증명 │ │스토리지 │ │ 하드웨어 │ │  슬래싱      │   │
│  │(Sigma)  │ │ (Sled)  │ │  (vHSM)  │ │  (페널티)    │   │
│  └─────────┘ └─────────┘ └──────────┘ └─────────────┘   │
├──────────────────────────────────────────────────────────┤
│                    하드웨어 레이어                         │
│  TPM/SEP  │  CPU UUID  │  Disk UUID  │  네트워크 인터페이스│
└──────────────────────────────────────────────────────────┘
```

### 2.2 데이터 흐름: 주권 의사결정

```
① 사용자 입력
   │  Transaction(source, target, amount, signature)
   v
② 제출 (Python → Rust FFI)
   │  ledger.submit_tx(tx) → RustReplicatedLedger::submit_transaction()
   v
③ 검증 (Rust)
   │  슬래싱 확인 → 잔액 확인 → 멤풀 추가
   v
④ 합의 (Rust BFT)
   │  Vote { block_hash, voter_id, decision, signature }
   │  ML-DSA-65 서명 검증
   │  투표 수 ≥ 정족수 (2n/3 + 1) → 블록 커밋
   v
⑤ 블록 채굴 (Rust)
   │  mine_block(miner) → 잔액 업데이트 + 상태 루트 계산
   v
⑥ ZK 증명 생성 (Rust)
   │  Sigma 프로토콜: generate_state_proof(value, blinding)
   │  증명을 블록에 첨부
   v
⑦ 저장 (Rust Sled + Python SQLite)
   │  blocks 트리 → 블록 커밋
   │  balances 트리 → 잔액 업데이트
   │  SQLite → 감사 로그
   v
⑧ 전파 (Python P2P)
   │  메시 동기화 → 피어 검증 → 로컬 원장 커밋
   v
⑨ 검증 가능한 증거 완성
   │  PQC 서명 + BFT 합의 증명 + ZK 프라이버시 증명
   └─→ 누구나 독립적으로 검증 가능
```

---

## 3. Rust 코어

### 3.1 모듈 개요

| 모듈 | 파일 | 기능 | no_std |
|------|------|------|--------|
| `crypto` | `crypto.rs` | ML-DSA-65 서명/검증 | 예 |
| `consensus` | `consensus.rs` | BFT 합의 엔진 | 예 |
| `ledger` | `ledger.rs` | 복제 원장 + 상태 머신 | 아니오 (Sled) |
| `proof_zk` | `proof_zk.rs` | Sigma 프로토콜 ZK 증명 | 예 |
| `storage` | `storage.rs` | Sled/메모리 스토어 | 예 (메모리) |
| `dht` | `dht.rs` | Kademlia 라우팅 테이블 | 예 |
| `policy_engine` | `policy_engine.rs` | 정책 검증 | 예 |
| `slashing` | `slashing.rs` | 위반 페널티 엔진 | 예 |
| `hardware` | `hardware/` | vHSM + 하드웨어 엔트로피 | 아니오 (IOKit) |
| `kernel` | `kernel.rs` | 반성 루프 + 모드 결정 | 예 |

### 3.2 암호화 (`crypto.rs`)

#### 데이터 구조

```rust
pub struct PQCKeypair {
    pub public_key: String,   // hex 인코딩, 원시 1952 바이트
    pub private_key: String,  // hex 인코딩, 원시 4032 바이트
}

pub struct MLDSA;  // ML-DSA-65 (FIPS 204) 구현
```

#### 공개 API

```rust
impl PQCKeypair {
    /// ML-DSA-65 키쌍 생성
    /// 반환: (public_key_hex, private_key_hex)
    pub fn generate() -> (String, String);
}

impl MLDSA {
    /// ML-DSA-65로 메시지 서명
    /// private_key 형식: "pk_hex:sk_hex"
    /// 반환: signature_hex (원시 3309 바이트)
    pub fn sign_raw(private_key: &str, message: &str) -> Result<String, String>;

    /// ML-DSA-65 서명 검증
    /// 반환: 유효하면 true
    pub fn verify_raw(public_key: &str, message: &str, signature: &str) -> bool;
}
```

#### 암호학적 상수

| 상수 | 값 | 출처 |
|------|-----|------|
| 공개키 크기 | 1,952 바이트 | FIPS 204 ML-DSA-65 |
| 비밀키 크기 | 4,032 바이트 | FIPS 204 ML-DSA-65 |
| 서명 크기 | 3,309 바이트 | FIPS 204 ML-DSA-65 |
| 해시 함수 | SHA3-256 | 32바이트 출력 |
| ZK 커브 | Ristretto255 | curve25519-dalek |

### 3.3 합의 엔진 (`consensus.rs`)

#### 데이터 구조

```rust
pub struct Vote {
    pub block_hash: String,
    pub voter_id: String,
    pub decision: String,     // "APPROVE" | "REJECT"
    pub signature: String,    // ML-DSA-65 서명
    pub timestamp: f64,
}

pub struct BFTEngine {
    pub quorum_threshold: usize,              // (2n/3) + 1
    votes: HashMap<String, HashSet<String>>,  // block_hash → voter_ids
    committed_blocks: HashSet<String>,
}
```

#### 공개 API

```rust
impl BFTEngine {
    /// 합의 엔진 초기화
    /// 정족수 = (2 * total_validators / 3) + 1
    pub fn new(total_validators: usize) -> Self;

    /// 서명 검증과 함께 투표 제출
    /// 반환: 정족수 도달 시 true (블록 커밋)
    pub fn submit_vote(&mut self, vote: Vote) -> bool;

    /// 블록 커밋 상태 확인
    pub fn is_committed(&self, block_hash: &str) -> bool;
}
```

#### 합의 알고리즘

```
1. N개 검증자, 정족수 = ⌊2N/3⌋ + 1
2. 각 투표: ML-DSA-65 서명으로 인증
3. 투표 집계: block_hash당 고유 voter_id 수
4. 정족수 도달 → 블록 커밋 (committed_blocks에 추가)
5. 이중 투표 방지: block_hash당 voter_id 1표
```

### 3.4 원장 (`ledger.rs`)

#### 데이터 구조

```rust
pub struct Transaction {
    pub tx_id: String,
    pub source: String,
    pub target: String,
    pub amount: u64,
    pub signature: String,
    pub timestamp: f64,
    pub max_fee: u64,        // EIP-1559 스타일
    pub priority_fee: u64,   // 채굴자 팁
}

pub struct Block {
    pub index: u32,
    pub timestamp: f64,
    pub tx_ids: Vec<String>,
    pub prev_hash: String,
    pub hash: String,
    pub miner: String,
    pub zk_proof: Option<String>,
    pub state_root: Option<String>,
    pub base_fee_per_gas: u64,
}
```

#### 공개 API

```rust
impl RustReplicatedLedger {
    pub fn new(path: &str) -> Self;
    pub fn submit_transaction(source, target, amount, signature, timestamp, max_fee, priority_fee);
    pub fn mine_block(miner_address: &str) -> Option<String>;
    pub fn get_balance(address: &str) -> u64;
    pub fn get_state_root() -> String;
    pub fn get_last_block() -> Option<Block>;
}
```

#### Sled 스토리지 트리

| 트리 | 키 | 값 | 목적 |
|------|-----|-----|------|
| `balances` | address (String) | u64 (Borsh) | 주소별 잔액 |
| `blocks` | block_hash (String) | Block (Borsh) | 블록 체인 |
| `meta` | "last_block_hash" | String | 최신 블록 해시 |
| `locks` | address (String) | bool | 슬래싱 잠금 |

### 3.5 ZK 증명 (`proof_zk.rs`)

#### 데이터 구조

```rust
pub struct ZKProof {
    pub challenge: [u8; 32],
    pub z1: [u8; 32],
    pub z2: [u8; 32],
    pub commitment: [u8; 32],
}
```

#### 알고리즘: Sigma 프로토콜 (Ristretto255)

```
증명자 (Prover):
  1. 임의의 r1, r2 선택
  2. commitment = r1·G + r2·H  (Pedersen 커밋먼트)
  3. challenge = SHA3(commitment ∥ public_data)
  4. z1 = r1 + challenge·v,  z2 = r2 + challenge·r
  5. proof = (challenge, z1, z2, commitment)

검증자 (Verifier):
  1. 재계산: expected = z1·G + z2·H - challenge·C
  2. expected == commitment 이면 유효
```

### 3.6 슬래싱 (`slashing.rs`)

```rust
pub enum Penalty {
    StateLock,           // 심각도 > 0.95: 모든 활동 차단
    EconomicBurn(u64),   // 심각도 > 0.80: 잔액 차감 (100)
    IdentityIsolation,   // 네트워크 격리
}
```

### 3.7 커널 모드 결정 (`kernel.rs`)

#### 반성 루프

```rust
impl ReflectiveLoop {
    // alpha = 0.5 (기본값), beta = 0.5 (기본값)
    // e_stab = alpha * epsilon_c + beta * (1.0 - tau_ethics)

    pub fn compute_mode_raw(&self, epsilon_c: f64, tau_ethics: f64) -> ModeDecision {
        if tau_ethics > 0.85 { return VETO_LOCK }
        if e_stab < 0.3     { return CRITICAL_HALT }
        if e_stab < 0.7     { return SUSPICIOUS }
        return NORMAL;
    }
}
```

---

## 4. Python 커널

### 4.1 모듈 구조

```
warm_logic/kernel/
├── sys/
│   ├── cryptography.py   ML-DSA FFI 래퍼 + HardwareEnclave
│   ├── network.py        MeshNetworking (DHT 오케스트레이션)
│   └── consensus.py      BFT Python 래퍼
├── mesh/
│   ├── dht.py            Kademlia DHT (Contact, RoutingTable, SovereignDHT)
│   ├── beacon.py         UDP 비컨 탐색
│   └── sync.py           P2P 메시지 동기화
├── economy/
│   └── ledger.py         ReplicatedLedger (Rust 위임)
├── identity/
│   └── kinetic_id.py     KineticIdentity (PQC 키 관리)
├── ops/
│   ├── control.py        KernelLoop, TaskScheduler
│   ├── policy.py         PluginRecord, verify_plugin()
│   └── quorum_manager.py QuorumManager (투표 오케스트레이션)
└── api.py                compute_mode() 진입점
```

### 4.2 핵심 클래스

#### KineticIdentity

```python
class KineticIdentity:
    """PQC 키쌍 기반 주권 신원"""

    def __init__(keypair: Optional[Tuple[str, str]] = None):
        # 키쌍 미제공 시 Rust를 통해 새 ML-DSA-65 키쌍 생성
        # Rust 코어 필수 (미설치 시 RuntimeError 발생)

    def sign_intent(intent_payload: str) -> str:
        """비밀키로 메시지 서명. 반환: signature_hex"""

    @staticmethod
    def generate_keypair() -> Tuple[str, str]:
        """ML-DSA-65 키쌍 생성. 반환: (public_key_hex, private_key_hex)"""

    @staticmethod
    def verify_intent(public_key: str, payload: str, signature: str) -> bool:
        """서명 검증. 반환: 유효성"""
```

#### ReplicatedLedger

```python
class ReplicatedLedger:
    """Rust 기반 복제 원장"""

    def __init__(store: SovereignStore, consensus_callback: Callable):
        # Sled DB 초기화, Rust 코어 필수

    def submit_tx(tx: Transaction) -> bool:
        """트랜잭션 제출. 검증 후 멤풀에 추가"""

    def mine_block(miner_address: str) -> Optional[str]:
        """블록 채굴. 반환: block_hash 또는 None"""

    def receive_external_block(block_data, balance_updates, zk_proof, txs) -> bool:
        """외부 블록 수신 및 검증. ZK 증명 + 상태 루트 검증"""

    def get_balance(address: str) -> int:
        """주소 잔액 조회"""

    def get_state_root() -> str:
        """모든 잔액의 결정론적 해시"""
```

#### QuorumManager

```python
class QuorumManager:
    """BFT 합의 오케스트레이터"""

    def __init__(ledger: ReplicatedLedger, total_validators: int = 4):
        # Rust BFTEngine 초기화

    def cast_vote(block_hash: str, decision: str) -> None:
        """투표 생성 및 서명 (VAL_IDENTITY, VAL_SECRET 환경변수 필수)"""

    def on_receive_block(payload: Dict) -> None:
        """외부 블록 수신 → 검증 → APPROVE/REJECT 투표"""

    def on_receive_vote(payload: Dict) -> None:
        """투표 수신 → BFT 엔진에 제출 → 확정성 확인"""
```

#### SovereignDHT

```python
class SovereignDHT:
    """Kademlia 기반 P2P 탐색"""

    def __init__(node_id: bytes, address: str = "127.0.0.1", port: int = 4000):
        # K=20, ALPHA=3 Kademlia 파라미터

    async def start() -> None:
        """UDP 서버 시작"""

    async def bootstrap(seeds: List[Tuple[str, int]]) -> None:
        """부트스트랩 노드에 연결하고 라우팅 테이블 구축"""

    async def iterative_find_node(target_id: bytes) -> List[Contact]:
        """반복적 노드 검색 (ALPHA=3 병렬)"""

    def store(key: bytes, value: str) -> None:
        """키-값 쌍 저장"""
```

### 4.3 Python→Rust FFI 경계

**원칙**: 모든 암호화 및 합의 연산은 Rust에서 실행. Python은 오케스트레이션만 담당.

| Python 호출 | Rust 함수 | 데이터 전달 |
|-------------|-----------|------------|
| `MLDSA.sign()` | `MLDSA::sign_raw()` | String (hex) |
| `MLDSA.verify()` | `MLDSA::verify_raw()` | String → bool |
| `KineticIdentity.generate_keypair()` | `PQCKeypair::generate()` | → (String, String) |
| `ledger.submit_tx()` | `RustReplicatedLedger::submit_transaction()` | 개별 필드 |
| `ledger.mine_block()` | `RustReplicatedLedger::mine_block()` | String → Option |
| `BFTEngine.submit_vote()` | `BFTEngine::submit_vote()` | Vote 구조체 |

**FFI 성능**: Paper #9에서 측정 — PyO3 제로카피로 기본 대비 300배 성능 향상 (10MB 페이로드).

---

## 5. 네트워크 프로토콜

### 5.1 프로토콜 스택

```
┌──────────────────────────────────┐
│        애플리케이션 레이어         │
│  블록 전파, 투표, 동기화          │
├──────────────────────────────────┤
│        탐색 레이어                │
│  Kademlia DHT (포트 4000/UDP)   │
│  비컨 브로드캐스트 (포트 8999/UDP)│
├──────────────────────────────────┤
│        API 레이어                 │
│  HTTP/JSON (포트 8000, 5001)    │
├──────────────────────────────────┤
│        전송 레이어                │
│  UDP (DHT/비컨) + TCP (HTTP)    │
└──────────────────────────────────┘
```

### 5.2 비컨 탐색

| 속성 | 값 |
|------|-----|
| 프로토콜 | UDP 브로드캐스트 |
| 포트 | 8999 |
| 주기 | 2.0초 |
| 페이로드 | `{"type": "beacon", "node_id": "...", "http_port": ...}` |
| 피어 TTL | 15초 (비활성 시 제거) |

### 5.3 Kademlia DHT

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| K | 20 | 버킷 크기 |
| ALPHA | 3 | 병렬 검색 |
| 노드 ID | 32 바이트 | SHA3-256(public_key) |
| 거리 메트릭 | XOR | 표준 Kademlia |
| 메시지 | PING, FIND_NODE, FIND_VALUE, STORE | JSON 인코딩 UDP |

### 5.4 PQC 게이트키퍼

DHT 라우팅 테이블에 등록되는 모든 Contact는 PQC 검증을 통과해야 합니다:

```
검증: SHA3-256(contact.public_key) == contact.node_id
실패 시: 무시 (제로 트러스트)
```

---

## 6. 스토리지 아키텍처

### 6.1 이중 스토리지

| 레이어 | 엔진 | 목적 | 형식 |
|--------|------|------|------|
| Rust | Sled (임베디드 KV) | 합의 상태 (잔액, 블록, 메타) | Borsh 직렬화 |
| Python | SQLite (SovereignStore) | 감사 로그 (블록, 이벤트) | JSON |

**근거**: 고성능 합의 경로 KV에 Sled, 쿼리 가능한 감사 로그에 SQLite.

### 6.2 Sled 트리 구조

```
data/ledger.sled/
├── balances       address → u64 (Borsh)
├── blocks         block_hash → Block (Borsh)
├── meta           "last_block_hash" → String
└── locks          address → bool (슬래싱 잠금)
```

### 6.3 데이터 경로

| 데이터 | 기본 경로 | 환경변수 |
|--------|----------|----------|
| 원장 DB | `data/ledger.sled` | (하드코딩) |
| 소셜 DB | `data/social_db` | `WARM_DB_PATH` |
| 감사 로그 | SQLite (SovereignStore 내부) | — |

---

## 7. 보안 모델

### 7.1 위협 모델

| 위협 | 방어 | 상태 |
|------|------|------|
| 양자 컴퓨터 서명 위조 | ML-DSA-65 (FIPS 204) | 구현됨 |
| 비잔틴 노드 (1/3 이하) | BFT 합의 (2n/3+1 정족수) | 구현됨 |
| 키 메모리 노출 | `zeroize` 크레이트 (메모리 스크러빙) | 구현됨 |
| 하드웨어 변조 | TPM/CPU UUID 기반 증명 | 시뮬레이션 |
| 리플레이 공격 | 타임스탬프 + 서명 포함 | 구현됨 |
| 원장 변조 | Merkle 상태 루트 + ZK 증명 | 구현됨 |
| 정책 위반 | 슬래싱 엔진 (StateLock, EconomicBurn) | 구현됨 |
| 네트워크 공격 (패킷 드롭/변조) | 카오스 몽키 테스팅 | 테스트 인프라 준비됨 |
| 시빌 공격 | PQC 게이트키퍼 (node_id = hash(pubkey)) | 구현됨 |

### 7.2 인증

```
노드 인증:
  node_id = SHA3-256(ML-DSA-65 공개키)
  → 모든 메시지에 서명 포함
  → 서명 검증 실패 → 무시 (제로 트러스트)

API 인증:
  Glass Browser (포트 8000): 인증 없음 (로컬 전용)
  Cockpit (포트 5001): SOVEREIGN_COCKPIT_KEY 필수
```

### 7.3 키 생명주기

```
생성 → 사용 → (로테이션: 미구현) → 파기 (zeroize)
  │       │                            │
  │       │  ML-DSA-65 서명/검증        │  보안 메모리 삭제
  │       └────────────────────────────┘
  │
  └── HardwareEntropy::derive_seed_raw()
      (macOS: IOPlatformUUID + SerialNumber)
```

> **참고**: 자동 키 로테이션은 아직 미구현. 키는 세션별로 생성됩니다.

---

## 8. API 레퍼런스

### 8.1 Glass Browser API (포트 8000)

#### 상태 확인

```
GET /health/liveness
→ 200 {"status": "alive", "timestamp": 1706832000.0}

GET /health/readiness
→ 200 {"status": "ready"}
→ 503 {"detail": "Not connected to mesh"}

GET /metrics
→ 200 (Prometheus 텍스트 형식)
   warmlogic_uptime_seconds 3600.0
   warmlogic_peer_count 3
   warmlogic_drift_score 0.02
```

#### 신원

```
GET /api/identity
→ 200 {"identity": "a1b2c3d4..."}
```

#### 검증

```
POST /api/verify
Content-Type: application/json
{"message": "이 의사결정을 승인합니다"}
→ 200 {"signed_packet": {...}, "public_key": "...", "signature": "..."}
```

#### 소셜 피드

```
GET /api/social/feed
→ 200 [{"id": "...", "message": "...", "timestamp": ..., "signature": "..."}]

POST /api/social/post
Content-Type: application/json
{"message": "주권 메시지"}
→ 200 {"status": "posted", "id": "..."}
→ 429 {"detail": "Sovereign Rate Limit Exceeded"}
```

#### 메시

```
GET /api/mesh/peers
→ 200 {"peers": [...], "sync_stats": {...}}
```

### 8.2 Cockpit API (포트 5001)

| 엔드포인트 | 인증 필요 | 설명 |
|-----------|----------|------|
| `GET /api/status` | 아니오 | 시스템 상태 |
| `POST /api/verify_key` | 아니오 | API 키 검증 |
| `GET /api/mesh` | 예 | 메시 텔레메트리 |
| `GET /api/logs` | 아니오 | 최근 활동 로그 |
| `GET /api/logs/stream` | 예 | SSE 실시간 로그 스트림 |
| `GET /api/config` | 예 | 설정 조회 |
| `POST /api/config/seal` | 예 | 정책 설정 업데이트 |

**인증 헤더**: `X-Cockpit-Key: {SOVEREIGN_COCKPIT_KEY}`

**SSE 이벤트 유형**:
- `REALITY_SYNC` — 드리프트 점수 업데이트
- `TELEMETRY_UPDATE` — 시스템/메시 상태

---

## 9. 거버넌스 워크플로우

### 9.1 상태 다이어그램

```
┌──────────┐     tick ≥ 3     ┌────────────┐
│   INIT   │ ───────────────→ │ AUTHORIZED │
└──────────┘                  └─────┬──────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              tau > 0.85     e_stab < 0.3    e_stab < 0.7
                    │               │               │
                    v               v               v
             ┌───────────┐  ┌─────────────┐  ┌────────────┐
             │ VETO_LOCK │  │CRITICAL_HALT│  │ SUSPICIOUS │
             └───────────┘  └─────────────┘  └────────────┘
```

### 9.2 의사결정 체인

| 단계 | 상태 | 설명 |
|------|------|------|
| ① 제안 생성 | 미구현 | AmendmentProposal |
| ② 투표 서명 | 구현됨 | KineticIdentity.sign_intent() |
| ③ BFT 합의 | 구현됨 | BFTEngine.submit_vote() (Rust) |
| ④ 확정성 감지 | 구현됨 | 정족수 도달 시 로그 출력 |
| ⑤ 네트워크 전파 | 미구현 | StitchServer |
| ⑥ 상태 적용 | 부분적 | 원장 커밋 작동; 거버넌스 상태 전이 대기 중 |

### 9.3 플러그인 시스템

```python
PluginRecord(
    name="example_plugin",
    package="example-package",
    entry_point="example.main",
    min_version="1.0.0",
    editions_allowed={"pro", "enterprise"},
    modules_required={"warm_logic.kernel"},
    signature="ML-DSA-65 서명",
)

# 검증 프로세스:
# 1. 레지스트리 존재 확인
# 2. Rust PolicyEngine을 통한 서명 검증
# 3. 에디션 권한 확인
# 4. 모듈 의존성 확인
# 5. 패키지 버전 확인
# 6. 진입점 등록 확인
# 7. 외부 서명 파일 검증
```

---

## 10. 배포

### 10.1 노드 유형

| 유형 | 구성요소 | 합의 | 스토리지 |
|------|---------|------|---------|
| Validator | 전체 Rust + Python | 예 | 전체 원장 |
| Beacon | Python 메시만 | 아니오 | 없음 |
| Gateway | FastAPI 서버 | 아니오 | 소셜 피드 |

### 10.2 최소 네트워크 구성

```
BFT f+1 장애 허용 최소 구성:

검증자 4개 → 정족수 = 3 → 비잔틴 노드 1개 허용
검증자 7개 → 정족수 = 5 → 비잔틴 노드 2개 허용
검증자 10개 → 정족수 = 7 → 비잔틴 노드 3개 허용
```

### 10.3 포트 사용

| 포트 | 프로토콜 | 목적 |
|------|---------|------|
| 8000 | TCP (HTTP) | Glass Browser UI/API |
| 5001 | TCP (HTTP) | Sovereign Cockpit |
| 8999 | UDP | 비컨 브로드캐스트 |
| 4000 | UDP | Kademlia DHT |

---

## 11. 설정 레퍼런스

### 11.1 환경변수

| 변수 | 기본값 | 필수 | 설명 |
|------|--------|------|------|
| `WARM_HTTP_PORT` | 8000 | 아니오 | HTTP 서버 포트 |
| `WARM_DB_PATH` | `data/social_db` | 아니오 | 소셜 DB 경로 |
| `WARM_DEV_MODE` | (미설정) | 아니오 | "1" 설정 시 피어 검사 우회 |
| `WARM_REGION` | (미설정) | 아니오 | 네트워크 토폴로지 리전 |
| `WARM_LOGIC_SALT` | (미설정) | 아니오 | 추가 키 유도 엔트로피 |
| `WARM_LOGIC_SIMULATION` | (미설정) | 아니오 | "1" 설정 시 시뮬레이션 모드 |
| `WARM_IDENTITY_SEED` | (미설정) | 아니오 | ID 시드 오버라이드 |
| `SOVEREIGN_COCKPIT_KEY` | (없음) | 예* | Cockpit API 키 (*Cockpit 사용 시) |
| `COCKPIT_HTTP_PORT` | 5001 | 아니오 | Cockpit 포트 |
| `VAL_IDENTITY` | (없음) | 예* | 검증자 노드 ID (*합의 참여 시) |
| `VAL_SECRET` | (없음) | 예* | 검증자 비밀키 (*합의 참여 시) |
| `WARM_SIM_SANDBOX` | (미설정) | 아니오 | 설정 시 하드웨어 증명 비활성화 |
| `CHAOS_DROP_RATE` | 0.0 | 아니오 | 패킷 드롭률 (0.0–1.0) |
| `CHAOS_LATENCY_MS` | 0 | 아니오 | 인위적 지연 (ms) |
| `CHAOS_CORRUPTION_RATE` | 0.0 | 아니오 | 패킷 손상률 |

### 11.2 Cargo Feature 플래그

| 플래그 | 의존성 | 설명 |
|--------|--------|------|
| `std` | sha3, rand, hex, serde, chrono, fips204 std | 표준 라이브러리 |
| `python` | PyO3, persistence, std | Python 바인딩 |
| `persistence` | Sled, DashMap, std | 영구 스토리지 |
| `cockpit` | ratatui, crossterm, clap, persistence | TUI 대시보드 |

---

## 12. 스키마 시스템

### 12.1 개요

| 지표 | 값 |
|------|-----|
| 총 JSON 스키마 | 187개 |
| 도메인 | 34개 |
| SSOT 계층 | 스키마 > 스펙 > 코드 > 테스트 |

### 12.2 주요 도메인

| 도메인 | 스키마 수 | 예시 |
|--------|----------|------|
| evidence | 15 | CE 원장, 감사 팩, 외부 인시던트 |
| meta | 40+ | 실행 매니페스트, 실험 번들 |
| governance | 19 | GovDec 이벤트, tau 정책 |
| os | 20+ | OS 상태, 스케줄러, 안정성 엔벨로프 |
| ops | 10 | 감사 이벤트, 인시던트, SBOM |
| security | 4 | 변조 로그, 레드팀 실험 |
| ml | 6 | 모델 레지스트리, 파이프라인 |
| mcp | 9 | MCP 트레이스, 도구 제한 |
| research | 6 | A/B 실험, 연합 트레이스 |

### 12.3 스키마 거버넌스 규칙

- **새 스키마**: `spec/schema/` 하위에 생성, `SCHEMA_REGISTRY_v1.md`에 등록
- **변경**: 하위 호환성 유지 (새 필드는 optional). 호환 불가 시 새 버전 생성 (v1 → v2).
- **마이그레이션**: 버전 변경 시 마이그레이션 스크립트 필수.

---

## 13. 성능

### 13.1 검증된 벤치마크

| 지표 | 값 | 재현 가능 | 출처 |
|------|-----|----------|------|
| PyO3 FFI 오버헤드 (10MB) | 기본 대비 300배 개선 | 예 | Paper #9, `scripts/eval/` |
| ML-DSA-65 서명/검증 | ~ms 단위 | 예 | 코드 내 테스트 |
| SHA3-256 해싱 | ~μs 단위 | 예 | 라이브러리 벤치마크 |
| Sled 읽기/쓰기 | ~μs 지연 | 예 | Sled 공식 벤치마크 |
| BFT 투표 처리 | O(1)/투표 | 예 | HashMap + HashSet |

### 13.2 목표 지표 (미검증)

아래는 달성을 위해 노력 중인 목표입니다 — 아직 달성된 수치가 아닙니다:

| 목표 | 값 | 상태 |
|------|-----|------|
| 글로벌 확정 지연 | < 10ms | 멀티노드 벤치마크 필요 |
| 형식 검증 지연 | < 0.1ms | UDS 소켓 벤치마크 필요 |
| 탈중앙 동기화 | < 15ms | 멀티노드 테스트 필요 |
| 처리량 | 50,000+ TPS | 부하 테스트 필요 |

> 우리는 증명할 수 있는 것만 주장합니다. 목표 지표는 검증된 결과와 명확히 구분됩니다.

---

## 14. 구현 현황

### 14.1 완성도 매트릭스

| 구성요소 | 상태 | 완성도 | 비고 |
|---------|------|--------|------|
| ML-DSA-65 서명/검증 | 작동 중 | 95% | 키 로테이션 미구현 |
| BFT 합의 엔진 | 작동 중 | 85% | 네트워크 전파 대기 중 |
| 복제 원장 | 작동 중 | 80% | Tx 검증 + 블록 채굴 운영 중 |
| ZK 증명 | 작동 중 | 75% | 기본 Sigma 프로토콜 |
| Kademlia DHT | 작동 중 | 70% | 부트스트랩 시드 미설정 |
| 비컨 탐색 | 작동 중 | 90% | UDP 로컬 탐색 |
| Glass Browser API | 작동 중 | 85% | 6개 엔드포인트 |
| Cockpit API | 작동 중 | 80% | SSE 스트림 포함 |
| 하드웨어 증명 | 부분적 | 40% | macOS IOKit만, TPM 시뮬레이션 |
| P2P 블록 전파 | 미구현 | 0% | StitchServer 스텁 |
| 제안 생성 | 미구현 | 0% | AmendmentProposal 스텁 |
| 자동 키 로테이션 | 미구현 | 0% | 세션 기반 키만 |
| CLI 도구 | 미구현 | 5% | wlctl 미문서화 |
| 모니터링 (Prometheus) | 부분적 | 30% | 기본 메트릭만 |

### 14.2 알려진 스텁 (RuntimeError 발생)

| 스텁 | 위치 | 영향 |
|------|------|------|
| `StitchServer.broadcast()` | quorum_manager.py | 높음 — 합의 전파 불가 |
| `AmendmentProposal` | control.py | 높음 — 거버넌스 워크플로우 미완성 |
| `ClosureDaemon` | control.py | 중간 — 자율 커널 진화 |
| `EvolutionScheduler` | control.py | 중간 — 정책 스케줄링 |
| `ConsensusMechanism` | control.py | 중간 — 상위 합의 래퍼 |
| `SystemMetrics` (텔레메트리) | control.py | 높음 — 모니터링 없음 |

### 14.3 프로덕션을 위한 핵심 격차

| 격차 | 심각도 | 접근법 |
|------|--------|--------|
| P2P 전파 | 치명적 | StitchServer → libp2p 또는 커스텀 TCP |
| 키 영구 보관 | 치명적 | 키스토어 (파일 또는 OS 키체인) |
| 보안 감사 | 치명적 | 제3자 감사 필수 |
| 모니터링 | 높음 | Prometheus 익스포터 완성 |
| CLI 도구 | 높음 | typer 기반 `wlctl` 완성 |
| 문서화 | 높음 | API 문서, 튜토리얼 |
| 패키지 배포 | 높음 | PyPI, Docker Hub |
| 테스트 커버리지 (~60%) | 중간 | 목표 80% |
| 하드웨어 증명 | 중간 | 실제 TPM 통합 |

---

## 15. 기여 방법

### 15.1 개발 환경 설정

```bash
# 사전 요구사항
Python 3.12+
Rust 1.75+ (cargo 포함)

# 클론 및 빌드
git clone https://github.com/espressolee/WarmLogic
cd warmlogic
pip install -r requirements.txt
pip install maturin
cd warm_logic_rs && maturin develop && cd ..

# Rust 코어 확인
python -c "import warm_logic_rs; print('Rust 코어 로드 완료')"

# 테스트 실행
pytest tests/ -v

# 서버 시작
python -m warm_logic.ui.server
```

### 15.2 기여 영역

| 영역 | 난이도 | 임팩트 | 첫 기여 적합 |
|------|--------|--------|-------------|
| 문서 & 튜토리얼 | 낮음 | 높음 | 예 |
| Docker 이미지 | 낮음 | 높음 | 예 |
| 테스트 커버리지 | 중간 | 중간 | 예 |
| PyPI 패키징 | 중간 | 높음 | 아니오 |
| CLI 도구 (`wlctl`) | 중간 | 높음 | 아니오 |
| Prometheus 모니터링 | 중간 | 중간 | 아니오 |
| P2P 블록 전파 | 높음 | 치명적 | 아니오 |
| TPM 통합 (Linux/Windows) | 높음 | 중간 | 아니오 |
| libp2p 통합 | 높음 | 높음 | 아니오 |

### 15.3 규약

- **커밋 형식**: `feat|fix|docs|refactor: 간단한 설명`
- **SSOT 계층**: 스키마 변경 먼저, 그다음 코드, 그다음 테스트
- **모든 암호화 연산**: 반드시 Rust 코어를 통과, Python에서 직접 수행 금지
- **새 스키마**: `SCHEMA_REGISTRY_v1.md`에 등록
- **테스트 필수**: 의미 있는 모든 변경에 대해

### 15.4 보안 취약점 보고

보안 취약점을 발견하면, 책임감 있게 보고해 주세요:

- 공개 이슈를 열지 **마세요**
- 이메일: 70549809+espressolee@users.noreply.github.com
- 48시간 이내 확인을 목표로 합니다

---

## 16. 부록: 상수 & 임계값

### 16.1 암호학적 상수

```
ML-DSA-65 (FIPS 204):
  공개키:     1,952 바이트
  비밀키:     4,032 바이트
  서명:       3,309 바이트
  보안 수준:  NIST Level 3 (128비트 포스트양자)

SHA3-256:
  출력:       32 바이트 (256비트)

Ristretto255 (ZK):
  스칼라:     32 바이트
  포인트:     32 바이트 (압축)
```

### 16.2 네트워크 상수

```
Kademlia:
  K (버킷 크기):         20
  ALPHA (병렬):          3
  노드 ID:               32 바이트 (SHA3-256)

비컨:
  포트:                  8999 (UDP)
  브로드캐스트 주기:     2.0초
  피어 TTL:              15초

HTTP:
  Glass Browser:         8000 (기본값)
  Cockpit:               5001 (기본값)
  DHT:                   4000 (기본값)
```

### 16.3 정책 임계값

```
커널 모드:
  VETO_LOCK:     tau_ethics > 0.85
  CRITICAL_HALT: e_stab < 0.3
  SUSPICIOUS:    e_stab < 0.7
  NORMAL:        그 외

합의:
  정족수 = ⌊(2 × N) / 3⌋ + 1

슬래싱:
  StateLock:      심각도 > 0.95
  EconomicBurn:   심각도 > 0.80 (100 단위 차감)

불변 위반:
  CPU 드리프트:   > 0.05
  메모리 사용:    > 0.95

블록 수수료:
  base_fee_per_gas: 10
  max_fee (기본값): 20
  priority_fee (기본값): 1
```

---

*WarmLogic 기술 사양서 v1.0 — 오픈소스 에디션*
*이 문서는 실제 코드베이스를 반영합니다. 미구현 기능과 시뮬레이션 스텁은 명시적으로 표시되어 있습니다.*
