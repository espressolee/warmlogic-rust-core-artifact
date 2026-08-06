#![no_std]
#![no_main]

#[cfg(not(feature = "std"))]
use panic_halt as _;

#[cfg(feature = "std")]
extern crate std;

#[cfg(not(feature = "std"))]
#[panic_handler]
fn panic(_info: &core::panic::PanicInfo) -> ! {
    loop {}
}

/*
UART0 for QEMU virt machine is at 0x10000000
*/
const UART0: *mut u8 = 0x10000000 as *mut u8;

#[no_mangle]
#[link_section = ".text.entry"]
pub extern "C" fn _start() -> ! {
    // Stage 1: Pre-boot Telemetry
    for &b in b"kernel-Alpha: Initializing Sovereign Bootloader...\n" {
        unsafe {
            *UART0 = b;
        }
    }

    // Axiomatic Verification
    // In a bare-metal environment, we would load the last snapshot from flash.
    // For the architectural demonstration, we define the hook.

    /*
    let hsm = HSMGate::new();
    let boot = AxiomaticBootloader::new(hsm);
    let state = boot.awaken(&latest_snapshot);
    if state != AxiomaticState::Awakened {
        loop { unsafe { *UART0 = b'!'; } }
    }
    */

    for &b in b"Ready for Kernel Jump.\n" {
        unsafe {
            *UART0 = b;
        }
    }

    loop {}
}
