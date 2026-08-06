use std::cmp::Ordering;
use std::collections::BinaryHeap;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg_attr(feature = "python", pyclass)]
#[derive(Debug)]
pub struct RustKernelTask {
    pub priority: i32,
    pub task_id: String,
    #[cfg(feature = "python")]
    pub action: Option<Py<PyAny>>,
}

impl PartialEq for RustKernelTask {
    fn eq(&self, other: &Self) -> bool {
        self.priority == other.priority && self.task_id == other.task_id
    }
}

impl Eq for RustKernelTask {}

impl Ord for RustKernelTask {
    fn cmp(&self, other: &Self) -> Ordering {
        // BinaryHeap is a Max-Heap by default.
        // We want lower priority numbers to come first (Min-Heap style).
        // Reverse the priority comparison.
        other
            .priority
            .cmp(&self.priority)
            .then_with(|| self.task_id.cmp(&other.task_id))
    }
}

impl PartialOrd for RustKernelTask {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[cfg_attr(feature = "python", pyclass)]
pub struct RustTaskScheduler {
    #[allow(dead_code)]
    queue: BinaryHeap<RustKernelTask>,
}

impl Default for RustTaskScheduler {
    fn default() -> Self {
        Self::new()
    }
}

impl RustTaskScheduler {
    #[must_use]
    pub fn new() -> Self {
        Self {
            queue: BinaryHeap::new(),
        }
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl RustTaskScheduler {
    #[new]
    #[must_use]
    pub fn py_new() -> Self {
        Self::new()
    }

    pub fn schedule(&mut self, task_id: String, action: Py<PyAny>, priority: i32) {
        self.queue.push(RustKernelTask {
            priority,
            task_id,
            action: Some(action),
        });
    }

    pub fn next_task(&mut self) -> Option<RustKernelTask> {
        self.queue.pop()
    }

    #[must_use]
    pub fn pending_count(&self) -> usize {
        self.queue.len()
    }
}

#[cfg(feature = "python")]
#[pymethods]
impl RustKernelTask {
    #[getter]
    #[must_use]
    pub fn priority(&self) -> i32 {
        self.priority
    }

    #[getter]
    #[must_use]
    pub fn task_id(&self) -> String {
        self.task_id.clone()
    }

    #[getter]
    #[must_use]
    pub fn action<'py>(&self, py: Python<'py>) -> Option<Py<PyAny>> {
        self.action.as_ref().map(|act| act.clone_ref(py))
    }
}
