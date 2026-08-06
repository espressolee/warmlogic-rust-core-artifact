use super::tensor::Layer;
use alloc::vec::Vec;
use alloc::string::String;

#[derive(Debug, PartialEq)]
pub enum SovereignDecision {
    Optimal,
    AnomalyDetected,
    ScaleUp(u32),   // Requesting more resources (e.g., task slots)
    ScaleDown(u32), // Requesting resource compaction (e.g., heap cleanup)
}

pub struct KernelBrain {
    layers: Vec<Layer>,
}

impl KernelBrain {
    pub fn new_tiny_test() -> Self {
        // Initialize a 34x8x4 dummy network (34 inputs, 8 hidden, 4 output)
        // 34 inputs: mock kernel state metrics
        // 4 outputs: [0]=Optimal, [1]=Anomaly, [2]=ScaleUp, [3]=ScaleDown
        let mut layers = Vec::new();
        
        let mut l1 = Layer::new(34, 8);
        l1.weights.extend((0..34*8).map(|i| (i as f32) * 0.001));
        l1.bias.extend((0..8).map(|_| 0.1));
        
        let mut l2 = Layer::new(8, 4);
        l2.weights.extend((0..8*4).map(|i| (i as f32) * 0.01));
        l2.bias.extend((0..4).map(|_| 0.0));
        
        layers.push(l1);
        layers.push(l2);
        
        KernelBrain { layers }
    }

    pub fn think_decide(&self, state: &[f32]) -> (SovereignDecision, String) {
        let mut current = state.to_vec();
        for layer in &self.layers {
            current = layer.forward(&current);
        }
        
        // Simple classifier: pick highest index
        let mut max_idx = 0;
        let mut max_val = -1000.0;
        
        for (i, &val) in current.iter().enumerate() {
            if val > max_val {
                max_val = val;
                max_idx = i;
            }
        }

        match max_idx {
            0 => (SovereignDecision::Optimal, String::from("Healthy & Optimal")),
            1 => (SovereignDecision::AnomalyDetected, String::from("Anomaly Detected - Optimizing...")),
            2 => (SovereignDecision::ScaleUp(1), String::from("Scale Up Required")),
            3 => (SovereignDecision::ScaleDown(1), String::from("Scale Down Required")),
            _ => (SovereignDecision::Optimal, String::from("Undefined State - Defaulting to Optimal")),
        }
    }
}
