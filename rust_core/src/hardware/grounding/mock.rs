use crate::hardware::grounding::Groundable;

pub struct MockGrounding;

impl Groundable for MockGrounding {
    fn grounding_spec(&self) -> [u8; 32] {
        [0x42; 32]
    }

    fn physical_value(&self) -> [u8; 32] {
        [0x42; 32]
    }
}
