//! TPU (Tensor Processing Unit) Abstraction Layer
//!
//! Provides hardware acceleration for neural network inference on
//! Milk-V Duo S / SG2000 / CV1800B NPU (1 TOPS INT8).
//!
//! Silicon-bound AI acceleration.

use alloc::string::String;
use alloc::vec::Vec;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "std")]
use std::sync::Mutex;

#[cfg(not(feature = "std"))]
use spin::Mutex;

/// TPU Device State
#[cfg_attr(feature = "python", pyclass(eq, eq_int))]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
#[repr(u8)]
pub enum TPUState {
    /// TPU not initialized
    Uninitialized = 0,
    /// TPU ready for inference
    Ready = 1,
    /// TPU currently executing inference
    Running = 2,
    /// TPU in error state
    Error = 3,
    /// TPU in power-save mode
    PowerSave = 4,
}

/// TPU Device Type
#[cfg_attr(feature = "python", pyclass(eq, eq_int))]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum TPUType {
    /// Software fallback (CPU)
    Software,
    /// Milk-V Duo S / CV1800B NPU (1 TOPS)
    CV1800B,
    /// SG2000 NPU (enhanced)
    SG2000,
    /// Apple Neural Engine (Metal)
    AppleANE,
    /// Generic CUDA GPU
    CUDA,
}

impl TPUType {
    /// Get theoretical TOPS (Tera Operations Per Second)
    #[must_use]
    pub fn tops(&self) -> f32 {
        match self {
            TPUType::Software => 0.0,
            TPUType::CV1800B => 1.0,
            TPUType::SG2000 => 1.0,
            TPUType::AppleANE => 15.8, // M1/M2/M3
            TPUType::CUDA => 100.0,    // Varies by GPU
        }
    }

    /// Check if TPU supports INT8 quantization
    #[must_use]
    pub fn supports_int8(&self) -> bool {
        !matches!(self, TPUType::Software)
    }
}

/// TPU Tensor Format
#[derive(Debug, Clone)]
pub struct TPUTensor {
    /// Tensor data (INT8 quantized or FP32)
    pub data: Vec<u8>,
    /// Tensor shape (e.g., [batch, channels, height, width])
    pub shape: Vec<usize>,
    /// Data type (0=INT8, 1=FP16, 2=FP32)
    pub dtype: u8,
    /// Quantization scale (for INT8)
    pub scale: f32,
    /// Quantization zero-point (for INT8)
    pub zero_point: i8,
}

impl TPUTensor {
    /// Create a new INT8 tensor
    #[must_use]
    pub fn new_int8(data: Vec<u8>, shape: Vec<usize>, scale: f32, zero_point: i8) -> Self {
        Self {
            data,
            shape,
            dtype: 0,
            scale,
            zero_point,
        }
    }

    /// Create a new FP32 tensor
    #[must_use]
    pub fn new_fp32(data: Vec<f32>, shape: Vec<usize>) -> Self {
        let bytes: Vec<u8> = data.iter().flat_map(|f| f.to_le_bytes()).collect();
        Self {
            data: bytes,
            shape,
            dtype: 2,
            scale: 1.0,
            zero_point: 0,
        }
    }

    /// Get tensor size in bytes
    #[must_use]
    pub fn size_bytes(&self) -> usize {
        self.data.len()
    }

    /// Get tensor element count
    #[must_use]
    pub fn numel(&self) -> usize {
        self.shape.iter().product()
    }

    /// Convert INT8 tensor to FP32
    #[must_use]
    pub fn dequantize(&self) -> Vec<f32> {
        if self.dtype == 2 {
            // Already FP32
            self.data
                .chunks_exact(4)
                .map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]]))
                .collect()
        } else {
            // INT8 -> FP32
            // [BugFix] Use wrapping subtraction to prevent overflow
            self.data
                .iter()
                .map(|&x| ((x as i32) - (self.zero_point as i32)) as f32 * self.scale)
                .collect()
        }
    }

    /// Quantize FP32 data to INT8
    pub fn quantize_int8(data: &[f32]) -> (Vec<u8>, f32, i8) {
        let mut min_val = data.iter().cloned().fold(f32::INFINITY, f32::min);
        let mut max_val = data.iter().cloned().fold(f32::NEG_INFINITY, f32::max);

        // [BugFix] Ensure range includes 0.0 and avoid constant range
        min_val = min_val.min(0.0);
        max_val = max_val.max(0.0);
        if (max_val - min_val).abs() < 1e-5 {
            max_val = min_val + 1.0;
        }

        let scale = (max_val - min_val) / 255.0;
        let zero_point = (-min_val / scale).round() as i8;

        let quantized: Vec<u8> = data
            .iter()
            .map(|&x| ((x / scale) + zero_point as f32).clamp(0.0, 255.0) as u8)
            .collect();

        (quantized, scale, zero_point)
    }
}

/// TPU Model (compiled for hardware acceleration)
#[derive(Debug)]
pub struct TPUModel {
    /// Model identifier
    pub id: String,
    /// Input tensor shape
    pub input_shape: Vec<usize>,
    /// Output tensor shape
    pub output_shape: Vec<usize>,
    /// Compiled model weights (INT8 quantized)
    pub weights: Vec<TPUTensor>,
    /// Model FLOPS estimate
    pub flops: u64,
}

impl TPUModel {
    /// Create a new TPU model
    #[must_use]
    pub fn new(id: &str, input_shape: Vec<usize>, output_shape: Vec<usize>) -> Self {
        Self {
            id: String::from(id),
            input_shape,
            output_shape,
            weights: Vec::new(),
            flops: 0,
        }
    }

    /// Estimate inference time in microseconds
    #[must_use]
    pub fn estimate_latency_us(&self, tpu_type: TPUType) -> u64 {
        let tops = tpu_type.tops();
        if tops == 0.0 {
            // Software fallback: assume 1 GFLOPS
            (self.flops as f64 / 1e9 * 1e6) as u64
        } else {
            // Hardware TPU: FLOPS / TOPS
            (self.flops as f64 / (tops as f64 * 1e12) * 1e6) as u64
        }
    }
}

/// TPU Inference Result
#[derive(Debug, Clone)]
pub struct TPUInferenceResult {
    /// Output tensor
    pub output: TPUTensor,
    /// Inference time in microseconds
    pub latency_us: u64,
    /// Power consumption estimate in milliwatts
    pub power_mw: u32,
    /// Whether result was from cache
    pub cached: bool,
}

/// TPU Device Interface
pub struct TPUDevice {
    /// Device type
    pub device_type: TPUType,
    /// Device state
    pub state: TPUState,
    /// Loaded models
    models: Vec<TPUModel>,
    /// Performance statistics
    total_inferences: u64,
    total_latency_us: u64,
}

impl TPUDevice {
    /// Create a new TPU device with auto-detection
    #[must_use]
    pub fn new() -> Self {
        let device_type = Self::detect_hardware();

        Self {
            device_type,
            state: TPUState::Ready,
            models: Vec::new(),
            total_inferences: 0,
            total_latency_us: 0,
        }
    }

    /// Create a software-only TPU (CPU fallback)
    #[must_use]
    pub fn software() -> Self {
        Self {
            device_type: TPUType::Software,
            state: TPUState::Ready,
            models: Vec::new(),
            total_inferences: 0,
            total_latency_us: 0,
        }
    }

    /// Detect available TPU hardware
    #[cfg(feature = "std")]
    #[allow(unreachable_code)]
    fn detect_hardware() -> TPUType {
        // Check for Milk-V / CV1800B
        if std::path::Path::new("/sys/devices/platform/sophon").exists() {
            return TPUType::SG2000;
        }

        if std::path::Path::new("/dev/cvi_tpu").exists() {
            return TPUType::CV1800B;
        }

        // Check for Apple Neural Engine
        #[cfg(target_os = "macos")]
        {
            return TPUType::AppleANE;
        }

        // Check for CUDA
        #[cfg(feature = "cuda")]
        {
            return TPUType::CUDA;
        }

        TPUType::Software
    }

    #[cfg(not(feature = "std"))]
    #[allow(unreachable_code)]
    fn detect_hardware() -> TPUType {
        // In bare-metal, assume CV1800B if on RISC-V
        #[cfg(target_arch = "riscv64")]
        {
            return TPUType::CV1800B;
        }

        TPUType::Software
    }

    /// Load a model for inference
    pub fn load_model(&mut self, model: TPUModel) -> Result<usize, String> {
        let model_id = self.models.len();
        self.models.push(model);
        Ok(model_id)
    }

    /// Run inference on the TPU
    pub fn infer(
        &mut self,
        model_id: usize,
        input: TPUTensor,
    ) -> Result<TPUInferenceResult, String> {
        if model_id >= self.models.len() {
            return Err("Invalid model ID".into());
        }

        if self.state != TPUState::Ready {
            return Err(format!("TPU not ready: {:?}", self.state));
        }

        self.state = TPUState::Running;

        // Simulate inference timing
        let model = &self.models[model_id];
        let start = Self::get_timestamp_us();

        // Actually run inference (software fallback for now)
        let output = self.run_software_inference(model, &input)?;

        let latency = Self::get_timestamp_us() - start;

        self.state = TPUState::Ready;
        self.total_inferences += 1;
        self.total_latency_us += latency;

        Ok(TPUInferenceResult {
            output,
            latency_us: latency,
            power_mw: self.estimate_power_mw(),
            cached: false,
        })
    }

    /// Software inference fallback
    fn run_software_inference(
        &self,
        model: &TPUModel,
        input: &TPUTensor,
    ) -> Result<TPUTensor, String> {
        // Simple forward pass through model weights
        let mut current = input.dequantize();

        for weight_tensor in &model.weights {
            let weights = weight_tensor.dequantize();
            let out_dim = weight_tensor.shape.first().copied().unwrap_or(1);
            let in_dim = current.len();

            // [SEC-010] Division by zero defense
            if out_dim == 0 || in_dim == 0 {
                return Err("Invalid model shape: out_dim and in_dim must be > 0".into());
            }

            // [SEC-010] Safe bound calculation with overflow protection
            let safe_bound = weights
                .len()
                .checked_div(out_dim)
                .ok_or("Weight tensor size overflow")?
                .min(in_dim);

            let mut output = vec![0.0f32; out_dim];
            for j in 0..out_dim {
                let mut sum = 0.0;
                for i in 0..safe_bound {
                    // [SEC-010] Checked index calculation to prevent overflow
                    let weight_idx = j
                        .checked_mul(in_dim)
                        .and_then(|x| x.checked_add(i))
                        .ok_or("Index calculation overflow")?;

                    if weight_idx < weights.len() {
                        sum += current[i] * weights[weight_idx];
                    }
                }
                // ReLU activation
                output[j] = sum.max(0.0);
            }
            current = output;
        }

        Ok(TPUTensor::new_fp32(current, model.output_shape.clone()))
    }

    /// Estimate power consumption in milliwatts
    fn estimate_power_mw(&self) -> u32 {
        match self.device_type {
            TPUType::Software => 0,
            TPUType::CV1800B => 300,   // ~300mW for NPU
            TPUType::SG2000 => 350,    // ~350mW
            TPUType::AppleANE => 1500, // ~1.5W for ANE
            TPUType::CUDA => 75000,    // ~75W typical
        }
    }

    #[cfg(feature = "std")]
    fn get_timestamp_us() -> u64 {
        use std::time::{SystemTime, UNIX_EPOCH};
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_micros() as u64
    }

    #[cfg(not(feature = "std"))]
    fn get_timestamp_us() -> u64 {
        // Bare-metal: use cycle counter if available
        0
    }

    /// Get device statistics
    #[must_use]
    pub fn get_stats(&self) -> TPUStats {
        TPUStats {
            device_type: self.device_type,
            state: self.state,
            total_inferences: self.total_inferences,
            avg_latency_us: if self.total_inferences > 0 {
                self.total_latency_us / self.total_inferences
            } else {
                0
            },
            tops_theoretical: self.device_type.tops(),
            loaded_models: self.models.len(),
        }
    }
}

impl Default for TPUDevice {
    fn default() -> Self {
        Self::new()
    }
}

/// TPU Statistics
#[cfg_attr(feature = "python", pyclass(get_all))]
#[derive(Debug, Clone)]
pub struct TPUStats {
    pub device_type: TPUType,
    pub state: TPUState,
    pub total_inferences: u64,
    pub avg_latency_us: u64,
    pub tops_theoretical: f32,
    pub loaded_models: usize,
}

// Global TPU device instance
#[cfg(feature = "std")]
lazy_static::lazy_static! {
    pub static ref TPU: Mutex<TPUDevice> = Mutex::new(TPUDevice::new());
}

#[cfg(not(feature = "std"))]
lazy_static::lazy_static! {
    pub static ref TPU: Mutex<TPUDevice> = Mutex::new(TPUDevice::software());
}

/// Get the global TPU device
/// [C3 Security Fix] Recovers from lock poisoning instead of panicking.
/// In security-critical code, panic = DoS vulnerability.
#[cfg(feature = "std")]
pub fn get_tpu() -> std::sync::MutexGuard<'static, TPUDevice> {
    use std::sync::PoisonError;
    TPU.lock().unwrap_or_else(|poisoned: PoisonError<_>| {
        // [C3 HIGH FIX] Recover from poisoning - the underlying data is still valid
        // Log the poisoning event if logging is available
        #[cfg(debug_assertions)]
        eprintln!("[WARN] TPU mutex was poisoned, recovering...");
        poisoned.into_inner()
    })
}

#[cfg(not(feature = "std"))]
pub fn get_tpu() -> spin::MutexGuard<'static, TPUDevice> {
    TPU.lock()
}

/// Check if hardware TPU is available
#[must_use]
pub fn tpu_available() -> bool {
    let tpu = get_tpu();
    !matches!(tpu.device_type, TPUType::Software)
}

/// Get TPU device type
#[must_use]
pub fn tpu_type() -> TPUType {
    get_tpu().device_type
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tensor_quantization() {
        let data: Vec<f32> = vec![0.0, 0.5, 1.0, -0.5, -1.0];
        let (quantized, scale, zp) = TPUTensor::quantize_int8(&data);

        assert_eq!(quantized.len(), 5);
        assert!(scale > 0.0);

        // Create tensor and dequantize
        let tensor = TPUTensor::new_int8(quantized, vec![5], scale, zp);
        let restored = tensor.dequantize();

        // Check approximate equality
        for (orig, rest) in data.iter().zip(restored.iter()) {
            assert!((orig - rest).abs() < 0.02, "Quantization error too large");
        }
    }

    #[test]
    fn test_tpu_device() {
        let tpu = TPUDevice::software();
        assert_eq!(tpu.state, TPUState::Ready);
        assert_eq!(tpu.device_type, TPUType::Software);
    }

    #[test]
    fn test_tpu_inference() {
        let mut tpu = TPUDevice::software();

        // Create simple model
        let model = TPUModel::new("test", vec![4], vec![2]);
        let model_id = tpu.load_model(model).unwrap();

        // Create input tensor
        let input = TPUTensor::new_fp32(vec![1.0, 2.0, 3.0, 4.0], vec![4]);

        // Run inference
        let result = tpu.infer(model_id, input).unwrap();
        assert_eq!(result.output.shape, vec![2]);
    }

    #[test]
    fn test_tpu_stats() {
        let tpu = TPUDevice::software();
        let stats = tpu.get_stats();

        assert_eq!(stats.total_inferences, 0);
        assert_eq!(stats.loaded_models, 0);
    }
}
