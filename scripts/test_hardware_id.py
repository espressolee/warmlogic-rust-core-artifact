import warm_logic_rs

try:
    hid = warm_logic_rs.get_hardware_id()
    print(f"Hardware ID: {hid}")
except Exception as e:
    print(f"Error: {e}")

try:
    report = warm_logic_rs.HardwareAttestation.generate_report()
    print(f"Report Provider: {report.provider}")
    print(f"Report Quote: {report.quote}")

    is_valid, msg = warm_logic_rs.HardwareAttestation.verify_report(report)
    print(f"Verification: {is_valid} ({msg})")

    # Check: Direct Attestation verification
    is_attested, attest_msg = warm_logic_rs.HardwareEntropy.verify_attestation()
    print(f"Direct Attestation: {is_attested} ({attest_msg})")

except Exception as e:
    print(f"Report Error: {e}")
