use criterion::{criterion_group, criterion_main, Criterion};
use warm_logic_rs::drone::controller::{ControllerConfig, RustController};
use warm_logic_rs::drone::mavlink::MavlinkNode;
use warm_logic_rs::mavlink::common::{HilSensorUpdatedFlags, HIL_SENSOR_DATA};
use warm_logic_rs::nalgebra::Vector3;

fn bench_controller_update(c: &mut Criterion) {
    let mut controller = RustController::new(None, "00".repeat(1952), [0u8; 32]);
    controller.armed = true;
    let gyro = Vector3::new(0.01, 0.02, 0.03);
    let accel = Vector3::new(0.0, 0.0, -10.0);

    c.bench_function("controller_update_1khz", |b| {
        b.iter(|| {
            controller.update_imu(gyro, accel);
            let _ = controller.get_control_output(-10.0);
        })
    });
}

fn bench_mavlink_encoding(c: &mut Criterion) {
    let mut node = MavlinkNode::new(1, 1);
    let v = Vector3::zeros();

    c.bench_function("mavlink_encode_hil_sensor", |b| {
        b.iter(|| {
            let _ = node
                .encode_hil_sensor(1000, v, v, v, 1013.25, 0.0, 0.0, 25.0)
                .unwrap();
        })
    });
}

fn bench_full_bridge_tick(c: &mut Criterion) {
    let mut controller = RustController::new(None, "00".repeat(1952), [0u8; 32]);
    controller.armed = true;
    let mut node = MavlinkNode::new(1, 1);

    let msg = warm_logic_rs::mavlink::common::MavMessage::HIL_SENSOR(HIL_SENSOR_DATA {
        time_usec: 1000,
        xacc: 0.0,
        yacc: 0.0,
        zacc: -9.81,
        xgyro: 0.01,
        ygyro: 0.02,
        zgyro: 0.03,
        xmag: 0.1,
        ymag: 0.0,
        zmag: 0.0,
        abs_pressure: 1013.25,
        diff_pressure: 0.0,
        pressure_alt: 0.0,
        temperature: 25.0,
        fields_updated: HilSensorUpdatedFlags::empty(),
    });

    c.bench_function("full_bridge_tick_latency", |b| {
        b.iter(|| {
            let _ = controller.handle_mavlink_msg(&mut node, &msg);
        })
    });
}

criterion_group!(
    benches,
    bench_controller_update,
    bench_mavlink_encoding,
    bench_full_bridge_tick
);
criterion_main!(benches);
