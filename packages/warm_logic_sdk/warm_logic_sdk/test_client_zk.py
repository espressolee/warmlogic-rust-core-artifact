import unittest

from warm_logic.sdk.client import SovereignClient


class TestSovereignClientZK(unittest.TestCase):
    def setUp(self):
        self.client = SovereignClient()

    def test_zk_proof_lifecycle(self):
        """
        Verify that the client can generate a proof via store()
        and verify it via get_truth().
        """
        key = "test_wealth"
        value = 1000

        # 1. Store (Generate Proof)
        payload = self.client.store(key, value)

        self.assertIn("zk_proof", payload)
        self.assertIn("commitment", payload)
        self.assertTrue(len(payload["zk_proof"]) > 0)
        self.assertTrue(len(payload["commitment"]) > 0)

        print(f"\nGenerated Proof: {payload['zk_proof']}")
        print(f"Generated Commitment: {payload['commitment']}")

        # 2. Verify (Get Truth)
        # We simulate the data fetch by passing the payload back
        is_valid = self.client.get_truth(key, proof_data=payload)

        self.assertTrue(is_valid, "Client failed to verify its own ZK proof")

    def test_zk_proof_tamper(self):
        """Verify that tampered proofs are rejected."""
        key = "test_tamper"
        value = 500
        payload = self.client.store(key, value)

        # Tamper with the proof string
        original_proof = payload["zk_proof"]
        # Bit flip or just random garbage modification if hex
        # format is e:z1:z2. Let's modify z1.
        parts = original_proof.split(":")
        # Modifying the first char of z1
        z1 = list(parts[1])
        z1[0] = "a" if z1[0] != "a" else "b"
        parts[1] = "".join(z1)
        tampered_proof = ":".join(parts)

        payload["zk_proof"] = tampered_proof

        is_valid = self.client.get_truth(key, proof_data=payload)
        self.assertFalse(is_valid, "Client accepted tampered proof")


if __name__ == "__main__":
    unittest.main()
