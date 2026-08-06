//! BFT Consensus benchmarks for WarmLogic Rust Core.
//!
//! Run with: cargo bench --bench consensus_bench --features std

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use warm_logic_rs::crypto::{PQCKeypair, MLDSA};

fn bench_vote_signing(c: &mut Criterion) {
    let mut group = c.benchmark_group("bft_vote_signing");

    for node_count in [4, 7, 10, 16].iter() {
        // Generate keypairs for nodes
        let nodes: Vec<_> = (0..*node_count)
            .map(|_| PQCKeypair::generate_raw())
            .collect();

        group.bench_with_input(
            BenchmarkId::new("sign_votes", node_count),
            node_count,
            |b, &n| {
                b.iter(|| {
                    let block_hash = "0xabc123def456";

                    // Simulate vote signing by all nodes
                    let votes: Vec<_> = nodes
                        .iter()
                        .take(n as usize)
                        .enumerate()
                        .map(|(i, (_, sk))| {
                            let vote = format!("VOTE:{}:{}", i, block_hash);
                            MLDSA::sign_raw(sk, &vote).unwrap()
                        })
                        .collect();

                    black_box(votes)
                })
            },
        );
    }

    group.finish();
}

fn bench_quorum_verification(c: &mut Criterion) {
    // Pre-generate votes for 10 nodes
    let nodes: Vec<_> = (0..10).map(|_| PQCKeypair::generate_raw()).collect();
    let block_hash = "0xdef456789abcdef";

    let votes: Vec<_> = nodes
        .iter()
        .enumerate()
        .map(|(i, (pk, sk))| {
            let vote_msg = format!("VOTE:{}:{}", i, block_hash);
            let sig = MLDSA::sign_raw(sk, &vote_msg).unwrap();
            (pk.clone(), vote_msg, sig)
        })
        .collect();

    c.bench_function("bft_verify_quorum_7_of_10", |b| {
        b.iter(|| {
            // Verify 7 votes (quorum = floor(2*10/3) + 1 = 7)
            let valid_count = votes
                .iter()
                .take(7)
                .filter(|(pk, msg, sig)| MLDSA::verify_raw(pk, msg, sig))
                .count();

            black_box(valid_count >= 7)
        })
    });
}

fn bench_vote_aggregation(c: &mut Criterion) {
    let nodes: Vec<_> = (0..16).map(|_| PQCKeypair::generate_raw()).collect();
    let block_hash = "0xdef456789abcdef";

    // Pre-generate signatures
    let signatures: Vec<_> = nodes
        .iter()
        .enumerate()
        .map(|(i, (_, sk))| {
            let vote_msg = format!("VOTE:{}:{}", i, block_hash);
            MLDSA::sign_raw(sk, &vote_msg).unwrap()
        })
        .collect();

    c.bench_function("bft_aggregate_11_sigs", |b| {
        b.iter(|| {
            // Aggregate 11 signatures (quorum for 16 nodes)
            let aggregated: String = signatures
                .iter()
                .take(11)
                .fold(String::new(), |acc, s| acc + s);
            black_box(aggregated)
        })
    });
}

criterion_group!(
    benches,
    bench_vote_signing,
    bench_quorum_verification,
    bench_vote_aggregation,
);

criterion_main!(benches);
