//! Cryptographic operation benchmarks for WarmLogic Rust Core.
//!
//! Run with: cargo bench --bench crypto_bench --features std

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use warm_logic_rs::crypto::{PQCKeypair, MLDSA};

fn bench_keypair_generation(c: &mut Criterion) {
    c.bench_function("mldsa65_keypair_gen", |b| {
        b.iter(|| {
            let (pk, sk) = PQCKeypair::generate_raw();
            black_box((pk, sk))
        })
    });
}

fn bench_signing(c: &mut Criterion) {
    let (_, sk) = PQCKeypair::generate_raw();
    let message = "WarmLogic governance decision: APPROVE action_id=12345";

    c.bench_function("mldsa65_sign", |b| {
        b.iter(|| {
            let sig = MLDSA::sign_raw(black_box(&sk), black_box(message)).unwrap();
            black_box(sig)
        })
    });
}

fn bench_verification(c: &mut Criterion) {
    let (pk, sk) = PQCKeypair::generate_raw();
    let message = "WarmLogic governance decision: APPROVE action_id=12345";
    let signature = MLDSA::sign_raw(&sk, message).unwrap();

    c.bench_function("mldsa65_verify", |b| {
        b.iter(|| {
            let result =
                MLDSA::verify_raw(black_box(&pk), black_box(message), black_box(&signature));
            black_box(result)
        })
    });
}

fn bench_sign_verify_roundtrip(c: &mut Criterion) {
    let (pk, sk) = PQCKeypair::generate_raw();

    let mut group = c.benchmark_group("sign_verify_roundtrip");

    for size in [64, 256, 1024, 4096].iter() {
        let message: String = (0..*size).map(|_| 'x').collect();

        group.bench_with_input(BenchmarkId::from_parameter(size), size, |b, _| {
            b.iter(|| {
                let sig = MLDSA::sign_raw(&sk, &message).unwrap();
                let valid = MLDSA::verify_raw(&pk, &message, &sig);
                black_box(valid)
            })
        });
    }

    group.finish();
}

fn bench_batch_signing(c: &mut Criterion) {
    let (_, sk) = PQCKeypair::generate_raw();
    let messages: Vec<String> = (0..100)
        .map(|i| format!("Decision #{}: action approved", i))
        .collect();

    c.bench_function("mldsa65_batch_sign_100", |b| {
        b.iter(|| {
            let sigs: Vec<_> = messages
                .iter()
                .map(|m| MLDSA::sign_raw(&sk, m).unwrap())
                .collect();
            black_box(sigs)
        })
    });
}

criterion_group!(
    benches,
    bench_keypair_generation,
    bench_signing,
    bench_verification,
    bench_sign_verify_roundtrip,
    bench_batch_signing,
);

criterion_main!(benches);
