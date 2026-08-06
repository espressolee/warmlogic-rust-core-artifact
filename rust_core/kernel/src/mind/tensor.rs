use alloc::vec::Vec;

pub struct Layer {
    pub weights: Vec<f32>,
    pub bias: Vec<f32>,
    pub input_dim: usize,
    pub output_dim: usize,
}

impl Layer {
    pub fn new(input_dim: usize, output_dim: usize) -> Self {
        Layer {
            weights: Vec::with_capacity(input_dim * output_dim),
            bias: Vec::with_capacity(output_dim),
            input_dim,
            output_dim,
        }
    }

    /// performs dense layer: output = activate(W * input + b)
    pub fn forward(&self, input: &[f32]) -> Vec<f32> {
        let mut output = Vec::with_capacity(self.output_dim);
        
        for j in 0..self.output_dim {
            let mut sum = self.bias.get(j).cloned().unwrap_or(0.0);
            for i in 0..self.input_dim {
                sum += input[i] * self.weights[j * self.input_dim + i];
            }
            // ReLU Activation
            output.push(if sum > 0.0 { sum } else { sum * 0.01 }); // Leaky ReLU
        }
        
        output
    }
}
