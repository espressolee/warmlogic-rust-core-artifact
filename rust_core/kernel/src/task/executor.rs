use super::Task;
use alloc::collections::VecDeque;
use core::task::{Context, Poll, RawWaker, RawWakerVTable, Waker};
use core::sync::atomic::{AtomicUsize, Ordering};

pub static TASK_COUNT: AtomicUsize = AtomicUsize::new(0);

pub struct Executor {
    task_queue: VecDeque<Task>,
}

impl Executor {
    pub fn new() -> Self {
        Executor {
            task_queue: VecDeque::new(),
        }
    }

    pub fn task_count(&self) -> usize {
        self.task_queue.len()
    }

    pub fn spawn(&mut self, task: Task) {
        self.task_queue.push_back(task);
        TASK_COUNT.fetch_add(1, Ordering::Relaxed);
    }

    pub fn run(&mut self) -> ! {
        loop {
            self.run_ready_tasks();
        }
    }

    fn run_ready_tasks(&mut self) {
        let mut n = self.task_queue.len();
        while n > 0 {
            let mut task = self.task_queue.pop_front().unwrap();
            let waker = dummy_waker();
            let mut context = Context::from_waker(&waker);
            match task.poll(&mut context) {
                Poll::Ready(()) => {
                    TASK_COUNT.fetch_sub(1, Ordering::Relaxed);
                } // Task finished
                Poll::Pending => {
                    self.task_queue.push_back(task);
                }
            }
            n -= 1;
        }
    }
}

fn dummy_raw_waker() -> RawWaker {
    fn no_op(_: *const ()) {}
    fn clone(_: *const ()) -> RawWaker {
        dummy_raw_waker()
    }

    let vtable = &RawWakerVTable::new(clone, no_op, no_op, no_op);
    RawWaker::new(core::ptr::null(), vtable)
}

fn dummy_waker() -> Waker {
    unsafe { Waker::from_raw(dummy_raw_waker()) }
}
