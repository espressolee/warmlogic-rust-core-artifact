SDK Reference
=============

The SDK module provides the primary interface for applications to interact with WarmLogic.

.. module:: warm_logic.sdk
   :synopsis: High-level SDK for WarmLogic

SovereignClient
---------------

The main client class for interacting with WarmLogic.

.. class:: SovereignClient(host="127.0.0.1", port=8000, timeout=30.0)

   Create a new WarmLogic client.

   :param host: Kernel host address
   :type host: str
   :param port: Kernel port number
   :type port: int
   :param timeout: Default timeout for operations (seconds)
   :type timeout: float

   **Example:**

   .. code-block:: python

      from warm_logic.sdk import SovereignClient

      client = SovereignClient(
          host="127.0.0.1",
          port=8000,
          timeout=60.0
      )

   .. method:: propose_action(intent, context, timeout=None)

      Propose an action for governance evaluation.

      :param intent: Action intent (e.g., "log_event", "delete_user")
      :type intent: str
      :param context: Additional context for the action
      :type context: dict
      :param timeout: Override default timeout
      :type timeout: float, optional
      :returns: Decision object with approval status and proof
      :rtype: Decision
      :raises PolicyViolationError: If policy rejects the action
      :raises ConsensusError: If consensus fails (multi-node mode)
      :raises TimeoutError: If operation times out

      **Example:**

      .. code-block:: python

         decision = client.propose_action(
             intent="log_event",
             context={
                 "event": "user_login",
                 "user_id": "12345",
                 "severity": "info"
             }
         )

         if decision.approved:
             print(f"Action approved: {decision.proof_hash}")
         else:
             print(f"Action rejected: {decision.rejection_reason}")

   .. method:: get_evidence(proof_hash)

      Retrieve evidence bundle for a decision.

      :param proof_hash: Hash of the decision proof
      :type proof_hash: str
      :returns: Complete evidence bundle
      :rtype: EvidenceBundle
      :raises NotFoundError: If evidence not found

      **Example:**

      .. code-block:: python

         evidence = client.get_evidence(decision.proof_hash)

         print(f"Signature: {evidence.signature}")
         print(f"Timestamp: {evidence.timestamp}")
         print(f"Policy: {evidence.evaluated_policy}")

   .. method:: verify_evidence(evidence)

      Verify an evidence bundle cryptographically.

      :param evidence: Evidence bundle to verify
      :type evidence: EvidenceBundle
      :returns: Verification result
      :rtype: VerificationResult

      **Example:**

      .. code-block:: python

         result = client.verify_evidence(evidence)

         if result.valid:
             print("Evidence verified successfully")
         else:
             print(f"Verification failed: {result.reason}")

   .. method:: get_status()

      Get current kernel status.

      :returns: Kernel status information
      :rtype: KernelStatus

   .. method:: close()

      Close the client connection.

Decision
--------

Represents a governance decision.

.. class:: Decision

   .. attribute:: approved
      :type: bool

      Whether the action was approved.

   .. attribute:: proof_hash
      :type: str

      Unique hash identifying this decision's proof.

   .. attribute:: rejection_reason
      :type: str or None

      Reason for rejection (if not approved).

   .. attribute:: violated_policy
      :type: str or None

      Name of violated policy (if rejected).

   .. attribute:: timestamp
      :type: datetime

      When the decision was made.

   .. attribute:: consensus_round
      :type: int or None

      Consensus round number (multi-node mode only).

EvidenceBundle
--------------

Complete cryptographic evidence package.

.. class:: EvidenceBundle

   .. attribute:: proof_hash
      :type: str

      Unique identifier for this evidence.

   .. attribute:: signature
      :type: bytes

      ML-DSA-65 signature of the decision.

   .. attribute:: public_key
      :type: bytes

      Public key used for signing.

   .. attribute:: timestamp
      :type: datetime

      When evidence was created.

   .. attribute:: intent
      :type: str

      Original action intent.

   .. attribute:: context
      :type: dict

      Original action context.

   .. attribute:: evaluated_policy
      :type: str

      Policy that was evaluated.

   .. attribute:: policy_version
      :type: str

      Version of the policy at evaluation time.

   .. attribute:: zk_proof
      :type: bytes or None

      Zero-knowledge proof (if applicable).

   .. method:: to_json()

      Serialize to JSON format.

      :returns: JSON string
      :rtype: str

   .. method:: to_bytes()

      Serialize to binary format.

      :returns: Binary representation
      :rtype: bytes

   .. classmethod:: from_json(data)

      Deserialize from JSON.

      :param data: JSON string
      :type data: str
      :returns: Evidence bundle
      :rtype: EvidenceBundle

KernelStatus
------------

Kernel status information.

.. class:: KernelStatus

   .. attribute:: state
      :type: str

      Current kernel state (IDLE, RUNNING, VETO_LOCK, etc.).

   .. attribute:: uptime
      :type: float

      Seconds since kernel started.

   .. attribute:: decisions_count
      :type: int

      Total decisions made.

   .. attribute:: peer_count
      :type: int

      Number of connected peers (multi-node mode).

   .. attribute:: ledger_height
      :type: int

      Current ledger block height.

   .. attribute:: version
      :type: str

      WarmLogic version.

Exceptions
----------

.. exception:: WarmLogicError

   Base exception for all WarmLogic errors.

.. exception:: PolicyViolationError

   Raised when an action violates policy.

   .. attribute:: policy_name
      :type: str

      Name of the violated policy.

   .. attribute:: reason
      :type: str

      Reason for violation.

.. exception:: ConsensusError

   Raised when consensus fails.

.. exception:: TimeoutError

   Raised when an operation times out.

.. exception:: NotFoundError

   Raised when a resource is not found.

Context Manager
---------------

SovereignClient can be used as a context manager:

.. code-block:: python

   with SovereignClient() as client:
       decision = client.propose_action(
           intent="log_event",
           context={"event": "test"}
       )
   # Connection automatically closed

Async Support
-------------

For async applications, use AsyncSovereignClient:

.. code-block:: python

   from warm_logic.sdk import AsyncSovereignClient

   async def main():
       async with AsyncSovereignClient() as client:
           decision = await client.propose_action(
               intent="log_event",
               context={"event": "test"}
           )

See Also
--------

* :doc:`governance` - Policy evaluation details
* :doc:`crypto` - Cryptographic operations
* :doc:`consensus` - Multi-node consensus
