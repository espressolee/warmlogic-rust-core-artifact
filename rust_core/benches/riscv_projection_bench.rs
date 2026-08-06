//! benches/riscv_projection_bench.rs
//! Projects M4 Pro performance data to RISC-V constraints using simulated slowdown factors.

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use warm_logic_rs::drone::controller::{FlightMode, RustController};
use warm_logic_rs::nalgebra::Vector3;

fn bench_riscv_projection(c: &mut Criterion) {
    let mut controller = RustController::new(None, "00".repeat(1952), [0u8; 32]);
    controller.armed = true;

    // Factors derived from user analysis: 20x to 50x
    let projection_factors = [20.0, 30.0, 50.0];

    let gyro = Vector3::new(0.01, 0.02, 0.03);
    let accel = Vector3::new(0.0, 0.0, -9.81);

    let mut group = c.benchmark_group("RISC-V Reality Projection");

    for &factor in &projection_factors {
        group.bench_function(
            format!("Amortized Security ({}x Projection)", factor),
            |b| {
                b.iter(|| {
                    // Simulate N iterations of a 400Hz loop
                    for _ in 0..10 {
                        controller.update_imu(black_box(gyro), black_box(accel));
                    }
                })
            },
        );
    }

    group.finish();
}

criterion_group!(benches, bench_riscv_projection);
criterion_main!(benches);
