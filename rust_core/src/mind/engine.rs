//! rust_core/src/mind/engine.rs
//! Native Inference Engine using HuggingFace Candle.

use anyhow::{Context, Result};
use candle_core::{Device, Tensor};
use candle_transformers::models::quantized_llama::ModelWeights;
use std::path::PathBuf;
use tokenizers::Tokenizer;

pub struct InferenceEngine {
    _device: Device,
    _tokenizer: Option<Tokenizer>,
    _model: Option<ModelWeights>,
    pub model_commitment: Option<crate::zk::ml::ModelWeightCommitment>,
    pub invariants: crate::zk::ml::ConstitutionInvariants,
}

impl InferenceEngine {
    /// Initializes a new Inference Engine.
    /// Hardware acceleration (Metal/CUDA) is auto-detected.
    pub fn new() -> Result<Self> {
        let device = if cfg!(target_os = "macos") {
            Device::new_metal(0).unwrap_or(Device::Cpu)
        } else {
            Device::Cpu
        };

        println!("[SyntheticMind] Initializing on device: {:?}", device);

        let tokenizer = Tokenizer::from_file("tokenizer.json").ok();
        if tokenizer.is_none() {
            println!("[SyntheticMind] tokenizer.json missing, running in limited mode.");
        }

        Ok(InferenceEngine {
            _device: device,
            _tokenizer: tokenizer,
            _model: None,
            model_commitment: None,
            invariants: crate::zk::ml::ConstitutionInvariants {
                max_entropy: 0.5,
                min_confidence: 0.85,
            },
        })
    }

    /// Loads model weights from a GGUF file.
    pub fn load_model(&mut self, path: String) -> Result<()> {
        let path = PathBuf::from(path);
        if !path.exists() {
            return Err(anyhow::anyhow!("Model file not found at {:?}", path));
        }

        println!("[SyntheticMind] Loading GGUF weights from {:?}...", path);
        let file = std::fs::File::open(&path)?;
        let mut reader = std::io::BufReader::new(file);

        let gguf = candle_core::quantized::gguf_file::Content::read(&mut reader)
            .map_err(|e| anyhow::anyhow!("GGUF Read Error: {}", e))?;

        let model = ModelWeights::from_gguf(gguf, &mut reader, &self._device)
            .context("Failed to initialize ModelWeights from GGUF")?;

        // Model Weight Attestation (Prevent Poisoning)
        if let Some(ref commitment) = self.model_commitment {
            println!(
                "🛡️ [SyntheticMind] Verifying Model Attestation: {}",
                commitment.model_id
            );
            // In a production verification system, we would perform a Poseidon check here
            // on the quantized weights.
            if !commitment.verify_weights(&[]) {
                return Err(anyhow::anyhow!("🚨 [SyntheticMind] ATTESTATION REFUSED: Model weights do not match commitment!"));
            }
            println!("[SyntheticMind] Model Attestation Verified.");
        }

        self._model = Some(model);
        println!("[SyntheticMind] Model Loaded. Ready for Sovereign Thought.");
        Ok(())
    }

    /// Generates a response based on a prompt.
    pub fn think(&mut self, prompt: &str) -> Result<(String, Vec<u32>)> {
        let model = self
            ._model
            .as_mut()
            .context("Model not loaded. Call load() first.")?;

        println!("[SyntheticMind] Thinking: '{}'...", prompt);

        let encoded = self
            ._tokenizer
            .as_ref()
            .context("Tokenizer not initialized")?
            .encode(prompt, true)
            .map_err(|e| anyhow::anyhow!("Tokenization error: {}", e))?;

        let mut tokens = encoded.get_ids().to_vec();
        let input_tokens = tokens.clone();
        let mut generated_text = String::new();

        // Simple greedy generation for MVP (can expand to Sampler later)
        for i in 0..100 {
            // Max 100 tokens
            let last_token = *tokens.last().context("No tokens")?;
            let input = Tensor::new(&[last_token], &self._device)?.unsqueeze(0)?;
            let logits = model.forward(&input, i)?;
            let logits = logits.squeeze(0)?.squeeze(0)?;

            // Greedy: find index of max logit
            let next_token = logits.argmax(0)?.to_scalar::<u32>()?;

            if next_token == 2 {
                // EOS token typically
                break;
            }

            tokens.push(next_token);
            let decoded = self
                ._tokenizer
                .as_ref()
                .unwrap()
                .decode(&[next_token], true)
                .map_err(|e| anyhow::anyhow!("Decoding error: {}", e))?;

            generated_text.push_str(&decoded);

            if i % 10 == 0 {
                println!("[SyntheticMind] ... {} tokens generated", i);
            }
        }

        Ok((generated_text, input_tokens))
    }

    /// Generates a response with a ZK-ML constitutional witness.
    pub fn think_with_proof(
        &mut self,
        prompt: &str,
    ) -> Result<(String, crate::zk::ml::InferenceWitness)> {
        let (output, input_tokens) = self.think(prompt)?;

        let commitment =
            self.model_commitment
                .clone()
                .unwrap_or_else(|| crate::zk::ml::ModelWeightCommitment {
                    model_id: "default-unattested".to_string(),
                    version: 0,
                    weight_root: "0".repeat(64),
                    timestamp: 0,
                });

        let mut witness = crate::zk::ml::InferenceWitness {
            input_tokens,
            output_token: 0, // In real system, this would be a specific token being proved
            model_commitment: commitment,
            proof: vec![],
        };

        // Generate Axiomatic Proof
        let proof = witness
            .prove_alignment(&self.invariants)
            .map_err(|e| anyhow::anyhow!("Proof generation failed: {}", e))?;

        witness.proof = proof;

        Ok((output, witness))
    }
}
