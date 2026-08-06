Crypto Reference
================

The crypto module provides post-quantum cryptographic operations via the Rust core.

.. module:: warm_logic_rs
   :synopsis: Rust cryptographic primitives

ML-DSA-65 (FIPS 204)
--------------------

Post-quantum digital signatures.

Key Generation
^^^^^^^^^^^^^^

.. function:: generate_keypair()

   Generate a new ML-DSA-65 keypair.

   :returns: Keypair containing public and private keys
   :rtype: Keypair

   **Example:**

   .. code-block:: python

      import warm_logic_rs as wl

      keypair = wl.generate_keypair()

      print(f"Public key size: {len(keypair.public_key)} bytes")  # 1,952 bytes
      print(f"Private key size: {len(keypair.private_key)} bytes")

Signing
^^^^^^^

.. function:: sign(keypair, message)

   Sign a message with ML-DSA-65.

   :param keypair: Keypair with private key
   :type keypair: Keypair
   :param message: Message to sign
   :type message: bytes
   :returns: Signature
   :rtype: bytes

   **Example:**

   .. code-block:: python

      message = b"Hello, WarmLogic!"
      signature = wl.sign(keypair, message)

      print(f"Signature size: {len(signature)} bytes")  # 3,309 bytes

Verification
^^^^^^^^^^^^

.. function:: verify(public_key, message, signature)

   Verify an ML-DSA-65 signature.

   :param public_key: Public key
   :type public_key: bytes
   :param message: Original message
   :type message: bytes
   :param signature: Signature to verify
   :type signature: bytes
   :returns: Whether signature is valid
   :rtype: bool

   **Example:**

   .. code-block:: python

      is_valid = wl.verify(
          keypair.public_key,
          message,
          signature
      )

      if is_valid:
          print("Signature verified!")
      else:
          print("Invalid signature!")

Keypair Class
^^^^^^^^^^^^^

.. class:: Keypair

   ML-DSA-65 keypair.

   .. attribute:: public_key
      :type: bytes

      Public key (1,952 bytes).

   .. attribute:: private_key
      :type: bytes

      Private key (4,032 bytes).

   .. method:: export_public()

      Export public key in standard format.

      :returns: PEM-encoded public key
      :rtype: str

   .. method:: to_bytes()

      Serialize keypair to bytes.

      :returns: Serialized keypair
      :rtype: bytes

   .. classmethod:: from_bytes(data)

      Deserialize keypair from bytes.

      :param data: Serialized keypair
      :type data: bytes
      :returns: Keypair
      :rtype: Keypair

Zero-Knowledge Proofs
---------------------

Sigma protocol for zero-knowledge proofs.

Proof Generation
^^^^^^^^^^^^^^^^

.. function:: create_zk_proof(statement, witness)

   Create a zero-knowledge proof.

   :param statement: Public statement to prove
   :type statement: bytes
   :param witness: Private witness
   :type witness: bytes
   :returns: Zero-knowledge proof
   :rtype: ZKProof

   **Example:**

   .. code-block:: python

      # Prove knowledge of a secret without revealing it
      statement = b"I know the secret"
      witness = b"my_secret_value"

      proof = wl.create_zk_proof(statement, witness)

Proof Verification
^^^^^^^^^^^^^^^^^^

.. function:: verify_zk_proof(statement, proof)

   Verify a zero-knowledge proof.

   :param statement: Public statement
   :type statement: bytes
   :param proof: Proof to verify
   :type proof: ZKProof
   :returns: Whether proof is valid
   :rtype: bool

   **Example:**

   .. code-block:: python

      is_valid = wl.verify_zk_proof(statement, proof)

      if is_valid:
          print("Proof verified without revealing the secret!")

ZKProof Class
^^^^^^^^^^^^^

.. class:: ZKProof

   Zero-knowledge proof using Sigma protocol.

   .. attribute:: commitment
      :type: bytes

      Prover's commitment.

   .. attribute:: challenge
      :type: bytes

      Verifier's challenge.

   .. attribute:: response
      :type: bytes

      Prover's response.

   .. method:: to_bytes()

      Serialize proof.

      :returns: Serialized proof
      :rtype: bytes

   .. classmethod:: from_bytes(data)

      Deserialize proof.

      :param data: Serialized proof
      :type data: bytes
      :returns: Proof
      :rtype: ZKProof

Hashing
-------

SHA3-256 hashing.

.. function:: sha3_256(data)

   Compute SHA3-256 hash.

   :param data: Data to hash
   :type data: bytes
   :returns: Hash digest
   :rtype: bytes

   **Example:**

   .. code-block:: python

      digest = wl.sha3_256(b"Hello, WarmLogic!")
      print(f"Hash: {digest.hex()}")

.. function:: sha3_256_chain(items)

   Compute chained hash of multiple items.

   :param items: List of items to hash
   :type items: list[bytes]
   :returns: Chained hash
   :rtype: bytes

   **Example:**

   .. code-block:: python

      chain_hash = wl.sha3_256_chain([
          b"block1",
          b"block2",
          b"block3"
      ])

Performance
-----------

Benchmarks on Apple M2 Pro:

.. list-table:: Cryptographic Performance
   :header-rows: 1

   * - Operation
     - Latency (p50)
     - Throughput
   * - Key Generation
     - 1.02 ms
     - 980/s
   * - Sign (2KB)
     - 48 μs
     - 20,833/s
   * - Verify (2KB)
     - 28 μs
     - 35,714/s
   * - ZK Proof Gen
     - 42 μs
     - 23,810/s
   * - ZK Proof Verify
     - 38 μs
     - 26,316/s
   * - SHA3-256 (1KB)
     - 2.8 μs
     - 357 MB/s

Security Considerations
-----------------------

1. **Key Storage**: Private keys should be stored securely. Consider HSM integration for production.

2. **Quantum Safety**: ML-DSA-65 is NIST-approved post-quantum algorithm. Safe against known quantum attacks.

3. **Signature Size**: ML-DSA-65 signatures are 3,309 bytes (vs 64 bytes for Ed25519). Acceptable for audit use cases.

4. **Random Number Generation**: Uses system CSPRNG. Ensure adequate entropy.

See Also
--------

* :doc:`sdk` - High-level SDK
* :doc:`consensus` - BFT consensus using cryptographic proofs
