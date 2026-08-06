// Copyright 2026 espressolee
#[cfg(feature = "bare-metal")]
use linked_list_allocator::LockedHeap;

#[cfg(feature = "bare-metal")]
#[global_allocator]
static ALLOCATOR: LockedHeap = LockedHeap::empty();

#[cfg(feature = "bare-metal")]
pub fn init_heap() {
    // 0x80200000 is typical for QEMU Virt but check memory map.
    // For 64-bit, we need usize.
    let heap_start = 0x8020_0000usize;
    let heap_size = 1024 * 1024 * 4; // 4MB
    unsafe {
        ALLOCATOR.lock().init(heap_start as *mut u8, heap_size);
    }
}

#[cfg(not(feature = "bare-metal"))]
pub fn init_heap() {}
