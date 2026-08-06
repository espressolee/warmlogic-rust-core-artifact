API Overview
============

WarmLogic's API is organized into several modules, each providing specific functionality
for building sovereign AI governance applications.

Architecture
------------

.. code-block:: text

   +----------------------------------------------------------+
   |                    WarmLogic Stack                        |
   +----------------------------------------------------------+
   |  Application Layer  |  CLI / Cockpit UI / REST API       |
   +---------------------+------------------------------------+
   |  Governance Kernel  |  Constitution / RBAC / Policy VM   |
   +---------------------+------------------------------------+
   |  Crypto Substrate   |  ML-DSA-65 / ZK Proofs / BFT      |
   +---------------------+------------------------------------+
   |  Storage Layer      |  Ledger / Sled DB / DHT Mesh      |
   +----------------------------------------------------------+

Module Summary
--------------

SDK Module
^^^^^^^^^^

The primary entry point for applications.

.. code-block:: python

   from warm_logic.sdk import SovereignClient

   client = SovereignClient(
       host="127.0.0.1",
       port=8000,
       timeout=30
   )

**Key Classes:**

* ``SovereignClient`` - Main client for interacting with WarmLogic
* ``Decision`` - Represents a governance decision with proof
* ``EvidenceBundle`` - Cryptographic evidence package

Governance Module
^^^^^^^^^^^^^^^^^

Policy evaluation and constitutional enforcement.

.. code-block:: python

   from warm_logic.governance import GovernanceEngine, Policy

   engine = GovernanceEngine()
   policy = Policy.from_yaml("constitution.yaml")

   result = engine.evaluate(
       intent="delete_user",
       context={"user_id": "123"}
   )

**Key Classes:**

* ``GovernanceEngine`` - Core policy evaluation engine
* ``Policy`` - Policy definition and loading
* ``PolicyResult`` - Evaluation result with evidence

Crypto Module
^^^^^^^^^^^^^

Post-quantum cryptographic operations.

.. code-block:: python

   import warm_logic_rs as wl

   # Generate ML-DSA-65 keypair
   keypair = wl.generate_keypair()

   # Sign a message
   signature = wl.sign(keypair, b"message")

   # Verify signature
   valid = wl.verify(keypair.public_key, b"message", signature)

**Key Functions:**

* ``generate_keypair()`` - Generate ML-DSA-65 keypair
* ``sign(keypair, message)`` - Sign message with private key
* ``verify(public_key, message, signature)`` - Verify signature
* ``create_zk_proof(statement, witness)`` - Create zero-knowledge proof

Consensus Module
^^^^^^^^^^^^^^^^

Byzantine Fault Tolerant consensus for multi-node deployments.

.. code-block:: python

   from warm_logic.consensus import BFTNode, Proposal

   node = BFTNode(node_id="node-1", peers=["node-2", "node-3"])

   proposal = Proposal(action="approve_tx", data={"tx_id": "abc"})
   result = node.propose(proposal)

   if result.finalized:
       print(f"Consensus reached: {result.block_hash}")

**Key Classes:**

* ``BFTNode`` - Byzantine Fault Tolerant node
* ``Proposal`` - Consensus proposal
* ``ConsensusResult`` - Result with finality status

Storage Module
^^^^^^^^^^^^^^

Ledger and database operations.

.. code-block:: python

   from warm_logic.storage import Ledger, Block

   ledger = Ledger(path="~/.warm_logic/ledger")

   block = ledger.append(
       transactions=[tx1, tx2],
       metadata={"epoch": 42}
   )

   print(f"Block hash: {block.hash}")

**Key Classes:**

* ``Ledger`` - Append-only cryptographic ledger
* ``Block`` - Ledger block with transactions
* ``Transaction`` - Individual transaction record

Error Handling
--------------

All modules use a consistent error hierarchy:

.. code-block:: python

   from warm_logic.exceptions import (
       WarmLogicError,
       PolicyViolationError,
       ConsensusError,
       CryptoError,
       StorageError,
   )

   try:
       decision = client.propose_action(...)
   except PolicyViolationError as e:
       print(f"Policy violated: {e.policy_name}")
       print(f"Reason: {e.reason}")
   except ConsensusError as e:
       print(f"Consensus failed: {e}")
   except WarmLogicError as e:
       print(f"General error: {e}")

Type Hints
----------

WarmLogic uses comprehensive type hints. Example:

.. code-block:: python

   from warm_logic.types import Intent, Context, ProofHash

   def propose_action(
       intent: Intent,
       context: Context,
       timeout: float = 30.0
   ) -> Decision:
       ...

See Also
--------

* :doc:`sdk` - Detailed SDK documentation
* :doc:`governance` - Governance engine details
* :doc:`crypto` - Cryptographic operations
* :doc:`consensus` - BFT consensus protocol
* :doc:`storage` - Storage layer documentation
