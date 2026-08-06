#![cfg_attr(not(feature = "std"), no_std)]

use nalgebra::{SMatrix, SVector, Vector3};

#[derive(Clone, Debug)]
pub struct ExtendedKalmanFilter {
    dt: f64,
    // [q0, q1, q2, q3, bx, by, bz] (w, x, y, z)
    state: SVector<f64, 7>,
    p: SMatrix<f64, 7, 7>,
    q: SMatrix<f64, 7, 7>,
    r_accel: SMatrix<f64, 3, 3>,
    // r_mag: SMatrix<f64, 3, 3>, // Not used yet
}

impl ExtendedKalmanFilter {
    #[must_use]
    pub fn new(dt: f64) -> Self {
        let mut state = SVector::<f64, 7>::zeros();
        state[0] = 1.0; // q0 (w) = 1.0

        let p = SMatrix::<f64, 7, 7>::identity() * 0.1;

        let mut q = SMatrix::<f64, 7, 7>::identity() * 1e-4;
        // Tune Q (match Python)
        for i in 0..4 {
            q[(i, i)] *= 1e-5;
        }
        for i in 4..7 {
            q[(i, i)] *= 1e-7;
        }

        let r_accel = SMatrix::<f64, 3, 3>::identity() * 0.01;

        ExtendedKalmanFilter {
            dt,
            state,
            p,
            q,
            r_accel,
        }
    }

    pub fn predict(&mut self, gyro: Vector3<f64>) {
        let gx = gyro.x;
        let gy = gyro.y;
        let gz = gyro.z;

        let q0 = self.state[0];
        let q1 = self.state[1];
        let q2 = self.state[2];
        let q3 = self.state[3];
        let bx = self.state[4];
        let by = self.state[5];
        let bz = self.state[6];

        let wx = gx - bx;
        let wy = gy - by;
        let wz = gz - bz;

        let dt = self.dt;

        // Quaternion integration
        let dq0 = 0.5 * (-q1 * wx - q2 * wy - q3 * wz);
        let dq1 = 0.5 * (q0 * wx - q3 * wy + q2 * wz);
        let dq2 = 0.5 * (q3 * wx + q0 * wy - q1 * wz);
        let dq3 = 0.5 * (-q2 * wx + q1 * wy + q0 * wz);

        self.state[0] += dq0 * dt;
        self.state[1] += dq1 * dt;
        self.state[2] += dq2 * dt;
        self.state[3] += dq3 * dt;

        // Normalize
        let norm = (self.state[0].powi(2)
            + self.state[1].powi(2)
            + self.state[2].powi(2)
            + self.state[3].powi(2))
        .sqrt();
        if norm > 0.0 {
            self.state[0] /= norm;
            self.state[1] /= norm;
            self.state[2] /= norm;
            self.state[3] /= norm;
        }

        // Covariance Prediction (Simplified diagonal propagation)
        self.p += self.q;
    }

    pub fn update_accel(&mut self, accel: Vector3<f64>) {
        // accel is assumed to be in body frame
        // Normalizing
        let norm = accel.norm();
        if norm < 0.1 {
            return;
        } // Ignore low g

        let z = accel / norm;

        let q0 = self.state[0];
        let q1 = self.state[1];
        let q2 = self.state[2];
        let q3 = self.state[3];

        // Estimated Gravity Direction (Rotation of [0, 0, 1] by q*)
        // Actually h(x) is R_bw * [0, 0, 1].
        // In Python:
        // hx = 2.0 * (q1 * q3 - q0 * q2)
        // hy = 2.0 * (q0 * q1 + q2 * q3)
        // hz = q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3
        let hx = 2.0 * (q1 * q3 - q0 * q2);
        let hy = 2.0 * (q0 * q1 + q2 * q3);
        let hz = q0 * q0 - q1 * q1 - q2 * q2 + q3 * q3;
        let h = Vector3::new(hx, hy, hz);

        let y = z - h;

        // Jacobian H (3x7)
        let mut h_mat = SMatrix::<f64, 3, 7>::zeros();

        // Row 0
        h_mat[(0, 0)] = -2.0 * q2;
        h_mat[(0, 1)] = 2.0 * q3;
        h_mat[(0, 2)] = -2.0 * q0;
        h_mat[(0, 3)] = 2.0 * q1;

        // Row 1
        h_mat[(1, 0)] = 2.0 * q1;
        h_mat[(1, 1)] = 2.0 * q0;
        h_mat[(1, 2)] = 2.0 * q3;
        h_mat[(1, 3)] = 2.0 * q2;

        // Row 2
        h_mat[(2, 0)] = 2.0 * q0;
        h_mat[(2, 1)] = -2.0 * q1;
        h_mat[(2, 2)] = -2.0 * q2;
        h_mat[(2, 3)] = 2.0 * q3;

        // S = H P H' + R
        let s = h_mat * self.p * h_mat.transpose() + self.r_accel;

        // K = P H' S^-1
        let s_inv = match s.try_inverse() {
            Some(inv) => inv,
            None => return,
        };

        let k = self.p * h_mat.transpose() * s_inv;

        // dx = K y
        let dx = k * y;
        self.state += dx;

        // P = (I - K H) P
        let identity = SMatrix::<f64, 7, 7>::identity();
        self.p = (identity - k * h_mat) * self.p;

        // Normalize
        let norm = (self.state[0].powi(2)
            + self.state[1].powi(2)
            + self.state[2].powi(2)
            + self.state[3].powi(2))
        .sqrt();
        if norm > 0.0 {
            self.state[0] /= norm;
            self.state[1] /= norm;
            self.state[2] /= norm;
            self.state[3] /= norm;
        }
    }

    #[must_use]
    pub fn get_euler_angles(&self) -> (f64, f64, f64) {
        let q0 = self.state[0];
        let q1 = self.state[1];
        let q2 = self.state[2];
        let q3 = self.state[3];

        let sinr_cosp = 2.0 * (q0 * q1 + q2 * q3);
        let cosr_cosp = 1.0 - 2.0 * (q1 * q1 + q2 * q2);
        let roll = sinr_cosp.atan2(cosr_cosp);

        let sinp = 2.0 * (q0 * q2 - q3 * q1);
        let pitch = if sinp.abs() >= 1.0 {
            (core::f64::consts::PI / 2.0).copysign(sinp)
        } else {
            sinp.asin()
        };

        let siny_cosp = 2.0 * (q0 * q3 + q1 * q2);
        let cosy_cosp = 1.0 - 2.0 * (q2 * q2 + q3 * q3);
        let yaw = siny_cosp.atan2(cosy_cosp);

        (roll.to_degrees(), pitch.to_degrees(), yaw.to_degrees())
    }

    #[must_use]
    pub fn get_rotation_matrix(&self) -> SMatrix<f64, 3, 3> {
        let q0 = self.state[0];
        let q1 = self.state[1];
        let q2 = self.state[2];
        let q3 = self.state[3];

        let r00 = 1.0 - 2.0 * (q2 * q2 + q3 * q3);
        let r01 = 2.0 * (q1 * q2 - q0 * q3);
        let r02 = 2.0 * (q1 * q3 + q0 * q2);

        let r10 = 2.0 * (q1 * q2 + q0 * q3);
        let r11 = 1.0 - 2.0 * (q1 * q1 + q3 * q3);
        let r12 = 2.0 * (q2 * q3 - q0 * q1);

        let r20 = 2.0 * (q1 * q3 - q0 * q2);
        let r21 = 2.0 * (q2 * q3 + q0 * q1);
        let r22 = 1.0 - 2.0 * (q1 * q1 + q2 * q2);

        SMatrix::<f64, 3, 3>::new(r00, r01, r02, r10, r11, r12, r20, r21, r22)
    }
}
