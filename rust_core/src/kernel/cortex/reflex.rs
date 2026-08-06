use regex::Regex;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FlightMode {
    Abort,
    Disarm,
    Land,
    Arm,
    Guided,
    Altitude,
}

#[derive(Debug, Clone)]
pub struct ReflexBrain {
    abort_regex: Regex,
    disarm_regex: Regex,
    land_regex: Regex,
    arm_regex: Regex,
    guided_regex: Regex,
    altitude_regex: Regex,
}

impl Default for ReflexBrain {
    fn default() -> Self {
        Self::new()
    }
}

impl ReflexBrain {
    #[must_use]
    pub fn new() -> Self {
        Self {
            abort_regex: Regex::new(r"(?i)\babort\b|\bemergency\b|\bstop\b").unwrap(),
            disarm_regex: Regex::new(r"(?i)\bdisarm\b|\bkill\b").unwrap(),
            land_regex: Regex::new(r"(?i)\bland\b|\bdescend\b").unwrap(),
            arm_regex: Regex::new(r"(?i)\barm\b|\bactivate\b").unwrap(),
            guided_regex: Regex::new(r"(?i)\bguided\b|\bmission\b").unwrap(),
            altitude_regex: Regex::new(r"(?i)\baltitude\b|\bhold\b").unwrap(),
        }
    }

    #[must_use]
    pub fn evaluate(&self, intent: &str) -> Option<FlightMode> {
        if self.abort_regex.is_match(intent) {
            return Some(FlightMode::Abort);
        }
        if self.disarm_regex.is_match(intent) {
            return Some(FlightMode::Disarm);
        }
        if self.land_regex.is_match(intent) {
            return Some(FlightMode::Land);
        }
        if self.arm_regex.is_match(intent) {
            return Some(FlightMode::Arm);
        }
        if self.guided_regex.is_match(intent) {
            return Some(FlightMode::Guided);
        }
        if self.altitude_regex.is_match(intent) {
            return Some(FlightMode::Altitude);
        }
        None
    }
}
