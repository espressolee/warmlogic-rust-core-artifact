#!/usr/bin/env python3
import sys


def analyze_gap(log_file):
    """
    Parses UART logs and calculates Reality Gap stats.
    Assumes standard RISC-V QEMU clock or sets baseline.
    Default QEMU Virt is often 10MHz or depends on host, but mapped `time` CSR usually counts at fixed freq.
    Typical RISC-V `time` frequency is 1/10th or 1MHz on some boards, but let's assume 1GHz for normalized viewing or require calibration.

    Actually, on QEMU `mtime` frequency is usually 10MHz.
    """

    # QEMU Virt default timebase frequency
    # MTIME_FREQ_HZ = 10_000_000 # 10 MHz

    # Let's parameterize or assume 10MHz
    mtime_freq_hz = 10_000_000

    control_cycles = []
    crypto_cycles = []

    try:
        with open(log_file, "r") as f:
            for line in f:
                if line.startswith("CYCLES,"):
                    parts = line.strip().split(",")
                    if len(parts) >= 3:
                        try:
                            c_ctrl = int(parts[1])
                            c_crypto = int(parts[2])
                            control_cycles.append(c_ctrl)
                            crypto_cycles.append(c_crypto)
                        except ValueError:
                            continue
    except FileNotFoundError:
        print(f"Error: Log file '{log_file}' not found.")
        sys.exit(1)

    if not control_cycles:
        print("No valid cycle logs found.")
        return

    avg_ctrl = sum(control_cycles) / len(control_cycles)
    avg_crypto = sum(crypto_cycles) / len(crypto_cycles)

    # Convert to Microseconds
    # Duration (s) = Cycles / Freq
    # Duration (us) = (Cycles / Freq) * 1_000_000
    avg_ctrl_us = (avg_ctrl / mtime_freq_hz) * 1_000_000
    avg_crypto_us = (avg_crypto / mtime_freq_hz) * 1_000_000

    print(f"=== Reality Gap Analysis (Base Freq: {mtime_freq_hz / 1_000_000} MHz) ===")
    print(f"Data Points: {len(control_cycles)}")
    print("Control Logic:")
    print(f"  Avg Cycles: {avg_ctrl:.2f}")
    print(f"  Duration  : {avg_ctrl_us:.2f} \u00b5s")
    print("Crypto Logic (ML-DSA-65 Sign):")
    print(f"  Avg Cycles: {avg_crypto:.2f}")
    print(f"  Duration  : {avg_crypto_us:.2f} \u00b5s")

    # M4 Pro Baseline (from paper/walkthrough)
    # Control: 0.7us (700ns)
    # Crypto: 443us

    m4_ctrl_us = 0.7
    m4_crypto_us = 443.0

    ctrl_gap = avg_ctrl_us / m4_ctrl_us if m4_ctrl_us > 0 else 0
    crypto_gap = avg_crypto_us / m4_crypto_us if m4_crypto_us > 0 else 0

    print("\n--- Reality Gap Factor (vs M4 Pro) ---")
    print(f"Control Slowdown: {ctrl_gap:.2f}x")
    print(f"Crypto Slowdown : {crypto_gap:.2f}x")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ./analyze_gap.py <log_file>")
        sys.exit(1)
    analyze_gap(sys.argv[1])
