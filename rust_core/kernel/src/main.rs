#![no_std]
#![no_main]

extern crate alloc;

pub mod allocator;
pub mod task;
pub mod mind;
pub mod memory;
pub mod smp;

use core::panic::PanicInfo;
use task::{Task, executor::Executor};
use alloc::vec::Vec;
use bootloader_api::{entry_point, BootInfo};
use mind::KernelBrain;

// Use the entry_point macro to define the kernel entry point.
entry_point!(kernel_main);

const HEAP_SIZE: usize = 128 * 1024; // 128 KiB for first breath
static mut HEAP_MEM: [u8; HEAP_SIZE] = [0; HEAP_SIZE];

fn kernel_main(boot_info: &'static mut BootInfo) -> ! {
    // 1. Initialize Serial
    let port = 0x3f8u16;
    println(port, "\r\n****************************************\r\n");
    println(port, "*       WARM LOGIC KERNEL v2.0         *\r\n");
    println(port, "*    ERA 70000: PHYSICAL TRANSCENDENCE *\r\n");
    println(port, "****************************************\r\n");

    // 2. Initialize Memory Management (Physical & Virtual)
    let phys_mem_offset = x86_64::VirtAddr::new(boot_info.physical_memory_offset.into_option().unwrap());
    let (_mapper, _frame_allocator) = memory::init(&boot_info.memory_regions, phys_mem_offset);
    println(port, "[INFO] Memory Matrix (Paging & Allocator): ENGAGED.\r\n");

    // 3. Initialize SMP (CPU Discovery)
    let rsdp_addr = boot_info.rsdp_addr.into_option().expect("RSDP not found");
    smp::init(rsdp_addr, phys_mem_offset);
    println(port, "[INFO] SMP Matrix (CPU Discovery): ACTIVE.\r\n");

    // 3. Initialize Basal Metabolism: Memory (Static for now, soon Dynamic)
    unsafe {
        allocator::init_heap(HEAP_MEM.as_ptr() as usize, HEAP_SIZE);
    }
    println(port, "[INFO] Basal Metabolism (Heap): ACTIVE.\r\n");

    // 3. Initialize Basal Metabolism: Scheduler
    let mut executor = Executor::new();
    
    // 4. Cognitive Boot: Initialize Sovereign Mind
    let brain = KernelBrain::new_tiny_test();
    println(port, "[INFO] Sovereign Mind: ENGAGED.\r\n");

    // Spawn AI Analysis Task
    executor.spawn(Task::new(ai_cognitive_loop(port, brain)));
    
    // Spawn Background System Task
    executor.spawn(Task::new(background_maintenance(port)));
    
    println(port, "[INFO] Multi-tasking Cog-Loop: STARTED.\r\n");
    executor.run();
}

use core::sync::atomic::{AtomicUsize, Ordering};

static TICKS: AtomicUsize = AtomicUsize::new(0);

use mind::SovereignDecision;

async fn ai_cognitive_loop(port: u16, brain: KernelBrain) {
    loop {
        let heap_used = allocator::heap_used();
        let heap_size = allocator::heap_size();
        let task_count = task::executor::TASK_COUNT.load(Ordering::Relaxed);
        let ticks = TICKS.fetch_add(1, Ordering::Relaxed);

        // Grounded state
        let mut state = [0.1f32; 34];
        state[0] = (heap_used as f32) / (heap_size as f32);
        state[1] = (task_count as f32) / 10.0;
        state[2] = (ticks as f32) / 1000.0;
        
        // AI Inference with decision
        let (decision, verdict) = brain.think_decide(&state);
        
        // 1. Send Binary Telemetry Packet
        use borsh::BorshSerialize;
        use mind::KernelPacket;

        let packet = KernelPacket::Telemetry {
            heap_used: heap_used as u64,
            heap_total: heap_size as u64,
            task_count: task_count as u32,
            ticks: ticks as u64,
        };
        send_packet(port, &packet);

        // 2. Process Decision with Economic Veto
        let mut final_decision = decision;
        if let SovereignDecision::ScaleUp(_) = final_decision {
            if !mind::LEDGER.can_afford(10.0) {
                println(port, "\r\n[ECON] VETO: ScaleUp blocked (Insufficient Funds).\r\n");
                final_decision = SovereignDecision::Optimal; // Downgrade to no-op
            }
        }

        let action_code = match final_decision {
            SovereignDecision::Optimal => 0,
            SovereignDecision::AnomalyDetected => 1,
            SovereignDecision::ScaleUp(_) => 2,
            SovereignDecision::ScaleDown(_) => 3,
        };
        let packet = KernelPacket::Decision {
            verdict: alloc::string::String::from(verdict),
            action: action_code,
            amount: 1, // Default scaling amt
        };
        send_packet(port, &packet);

        for _ in 0..50 {
            core::hint::spin_loop();
        }
    }
}

async fn background_maintenance(port: u16) {
    loop {
        // Poll for incoming host packets (e.g. LedgerUpdate)
        receive_packet(port);
        
        for _ in 0..20 {
            core::hint::spin_loop();
        }
    }
}

fn receive_packet(port: u16) {
    // Simple state machine for packet reception
    static mut STATE: u8 = 0; // 0: Magic, 1: Len, 2: Body
    static mut HEADER_BUF: [u8; 6] = [0; 6];
    static mut CURSOR: usize = 0;
    static mut BODY_BUF: [u8; 256] = [0; 256];
    static mut TARGET_LEN: usize = 0;

    while let Some(byte) = try_read_byte(port) {
        unsafe {
            if STATE == 0 {
                HEADER_BUF[CURSOR] = byte;
                CURSOR += 1;
                if CURSOR == 4 {
                    if &HEADER_BUF[..4] == &mind::KernelPacket::MAGIC {
                        STATE = 1;
                    } else {
                        // Magic mismatch, slide and search
                        HEADER_BUF.copy_within(1..4, 0);
                        CURSOR = 3;
                    }
                }
            } else if STATE == 1 {
                HEADER_BUF[CURSOR] = byte;
                CURSOR += 1;
                if CURSOR == 6 {
                    TARGET_LEN = u16::from_le_bytes([HEADER_BUF[4], HEADER_BUF[5]]) as usize;
                    STATE = 2;
                    CURSOR = 0;
                }
            } else if STATE == 2 {
                BODY_BUF[CURSOR] = byte;
                CURSOR += 1;
                if CURSOR == TARGET_LEN {
                    // Packet fully received
                    use borsh::BorshDeserialize;
                    if let Ok(packet) = mind::KernelPacket::deserialize(&mut &BODY_BUF[..TARGET_LEN]) {
                        handle_host_packet(packet);
                    }
                    // Reset
                    STATE = 0;
                    CURSOR = 0;
                }
            }
        }
    }
}

fn handle_host_packet(packet: mind::KernelPacket) {
    if let mind::KernelPacket::LedgerUpdate { balance, epoch } = packet {
        mind::LEDGER.update(balance, epoch);
    }
}

fn try_read_byte(port: u16) -> Option<u8> {
    unsafe {
        let mut status: u8;
        core::arch::asm!("in al, dx", out("al") status, in("dx") port + 5);
        if status & 0x01 != 0 {
            let mut byte: u8;
            core::arch::asm!("in al, dx", out("al") byte, in("dx") port);
            Some(byte)
        } else {
            None
        }
    }
}

fn send_packet<T: borsh::BorshSerialize>(port: u16, packet: &T) {
    let mut buf = [0u8; 256];
    let mut writer = &mut buf[..];
    if let Ok(_) = borsh::to_writer(&mut writer, packet) {
        let len = 256 - writer.len();
        // Send Header: MAGIC (4) + LEN (2)
        send_bytes(port, &mind::KernelPacket::MAGIC);
        send_bytes(port, &(len as u16).to_le_bytes());
        // Send Body
        send_bytes(port, &buf[..len]);
    }
}

fn send_bytes(port: u16, bytes: &[u8]) {
    for &byte in bytes {
        unsafe {
            core::arch::asm!("out dx, al", in("dx") port, in("al") byte);
        }
    }
}

fn println(port: u16, s: &str) {
    send_bytes(port, s.as_bytes());
}

#[panic_handler]
fn panic(_info: &PanicInfo) -> ! {
    let port = 0x3f8u16;
    println(port, "\r\n!!! KERNEL PANIC !!!\r\n");
    // In a real kernel, print the info
    loop {}
}
