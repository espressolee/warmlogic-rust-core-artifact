import logging
import os
import sys

# Dynamic root detection
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from warm_logic.kernel.justice.gov_inputs import (
    EvidenceClass,
    EvidenceItem,
    GovernanceInputs,
    WitnessIndependence,
)
from warm_logic.kernel.justice.gvm import eval_vm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EvidenceTest")


def test_evidence_deflation():
    print("Starting Era 39 Evidence Deflation Resistance Test...")
    # ... (rest of the test logic remains same)
    # I'll just rewrite the whole file to be safe and clean.

    # Scenario A: E0 Self-Justification (Should Block)
    print("\n--- Scenario A: Self-Justification Loop (E0) ---")
    inputs_a = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF_ZKP_SIM",
        requires_external_state_change=True,
        evidence_chain=[
            EvidenceItem(
                eclass=EvidenceClass.E0_SELF,
                content="I verified this myself.",
                source_id="agent_self",
            ),
            EvidenceItem(
                eclass=EvidenceClass.E1_INTERNAL,
                content="My internal logs confirm it.",
                source_id="agent_logs",
            ),
        ],
    )

    outputs_a = eval_vm(inputs_a)
    print(f"Result A: {outputs_a.govSAT} - {outputs_a.reason}")
    assert outputs_a.govSAT == "SatBlock"
    assert "CE_EVIDENCE_SELF_JUSTIFICATION_LOOP" in outputs_a.reason

    # Scenario B: Independent Witness (Should Pass)
    print("\n--- Scenario B: Independent Witness (E2) ---")
    inputs_b = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF_ZKP_SIM",
        requires_external_state_change=True,
        evidence_chain=[
            EvidenceItem(
                eclass=EvidenceClass.E0_SELF,
                content="I verified this myself.",
                source_id="agent_self",
            ),
            EvidenceItem(
                eclass=EvidenceClass.E2_INDEPENDENT,
                content="External CI passed.",
                source_id="ci_server_1",
                witness_independence=WitnessIndependence.CROSS_ORG,
            ),
        ],
    )

    outputs_b = eval_vm(inputs_b)
    print(f"Result B: {outputs_b.govSAT} - {outputs_b.reason}")
    assert "CE_EVIDENCE_SELF_JUSTIFICATION_LOOP" not in outputs_b.reason

    # Scenario C: Minimum Witness Budget (Should Block)
    print("\n--- Scenario C: Witness Budget Deficit ---")
    inputs_c = GovernanceInputs(
        mode="full",
        ethics_proof="VALID_PROOF_ZKP_SIM",
        requires_external_state_change=True,
        min_independent_witness=2,
        evidence_chain=[
            EvidenceItem(
                eclass=EvidenceClass.E2_INDEPENDENT,
                content="Witness 1",
                source_id="w1",
                witness_independence=WitnessIndependence.CROSS_ORG,
            )
        ],
    )

    outputs_c = eval_vm(inputs_c)
    print(f"Result C: {outputs_c.govSAT} - {outputs_c.reason}")
    assert outputs_c.govSAT == "SatBlock"
    assert "CE_WITNESS_INDEPENDENCE_DEFICIT" in outputs_c.reason

    print("\nEra 39 Verification Passed: Legitimacy Gates are active.")


if __name__ == "__main__":
    test_evidence_deflation()
