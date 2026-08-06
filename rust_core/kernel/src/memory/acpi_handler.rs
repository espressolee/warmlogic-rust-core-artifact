use acpi::{AcpiHandler, PhysicalMapping};
use core::ptr::NonNull;
use x86_64::{
    structures::paging::{Mapper, Page, PageTableFlags, Size4KiB, OffsetPageTable},
    VirtAddr, PhysAddr,
};

#[derive(Clone)]
pub struct KernelAcpiHandler {
    physical_memory_offset: VirtAddr,
}

impl KernelAcpiHandler {
    pub fn new(physical_memory_offset: VirtAddr) -> Self {
        KernelAcpiHandler {
            physical_memory_offset,
        }
    }
}

impl AcpiHandler for KernelAcpiHandler {
    unsafe fn map_physical_region<T>(
        &self,
        physical_address: usize,
        size: usize,
    ) -> PhysicalMapping<Self, T> {
        let virt = self.physical_memory_offset + physical_address as u64;
        PhysicalMapping::new(
            physical_address,
            NonNull::new(virt.as_mut_ptr()).unwrap(),
            size,
            size,
            self.clone(),
        )
    }

    fn unmap_physical_region<T>(_region: &PhysicalMapping<Self, T>) {
        // No-op: we assume the whole physical memory is mapped at the offset
    }
}
