#![cfg(not(feature = "std"))]

// The "Spark of Life".
// This is the entry point when the Logic is burnt directly onto Silicon.

use core::panic::PanicInfo;

// Bare-metal Panic Handler
// If the Logic panics on hardware, we halt the CPU to preserve forensic state (Registers/RAM).
#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    loop {}
}

// The Element Zero Entry Point
// This symbol `_start` is what the Linker looks for after the BIOS hands over control.
#[no_mangle]
pub extern "C" fn _start() -> ! {
    // 1. Initialize Memory (Stack/Heap) - Assumed done by ASM preamble
    // 2. Initialize Clocks - Abstracted in HardwareClock

    // 3. Enter the Kernel Loop (Hardware Ignition)
    crate::kernel::kernel_main();
}
