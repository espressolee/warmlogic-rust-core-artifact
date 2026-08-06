pub mod frame;
pub mod paging;
pub mod acpi_handler;

use bootloader_api::info::MemoryRegions;
use x86_64::VirtAddr;
use x86_64::structures::paging::OffsetPageTable;
use frame::BitmapFrameAllocator;

pub fn init(regions: &'static MemoryRegions, offset: VirtAddr) -> (OffsetPageTable<'static>, BitmapFrameAllocator) {
    let mapper = unsafe { paging::init(offset) };
    let allocator = BitmapFrameAllocator::new(regions);
    (mapper, allocator)
}
