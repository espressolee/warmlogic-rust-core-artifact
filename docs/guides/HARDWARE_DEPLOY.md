# Hardware Deployment Guide

> **Objective:** Deploy Sovereign Nodes on physical hardware.

## Supported Architectures

| Device                        | Architecture  | Target Triple                 |
| ----------------------------- | ------------- | ----------------------------- |
| **Raspberry Pi 4 / Zero 2 W** | ARM64         | `aarch64-unknown-linux-gnu`   |
| **VisionFive 2 / Milk-V**     | RISC-V (64GC) | `riscv64gc-unknown-linux-gnu` |
| **Standard Server**           | x86_64        | `x86_64-unknown-linux-gnu`    |

## Prerequisite: Build Artifacts

We use Docker to cross-compile the Rust core (`warm_logic_rs`) for these targets.

```bash
# From project root
chmod +x scripts/deploy/build_iot.sh
./scripts/deploy/build_iot.sh
```

This ensures reproducible builds without installing complex toolchains on your host machine.

## Deployment Steps

1. **Flash OS**: Install minimal Linux (Debian/Ubuntu) on the device SD card.
2. **Transfer Artifacts**:
   ```bash
   scp warm_logic_rs/target/wheels/warm_logic_rs-*-linux_*.whl user@device:~
   scp -r warm_logic/ device:~/warm_logic
   ```
3. **Install**:
   ```bash
   # On device
   python3 -m venv venv
   source venv/bin/activate
   pip install warm_logic_rs-*.whl
   pip install -r warm_logic/requirements.txt
   ```
4. **Boot**:
   ```bash
   # Start as seed node
   python3 -m warm_logic.system.boot --seed
   ```

## Hardware Attestation (V-HSM)

WarmLogic binds to the device's hardware root of trust.
- **Linux**: Requires TPM 2.0 module enabled.
- **RISC-V**: Uses experimental `v_hsm` software vault if physical SE is unavailable.

Verify attestation:
```bash
wlctl identity attest
```
