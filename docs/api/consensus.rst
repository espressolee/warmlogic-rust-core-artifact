Consensus Reference
===================

The consensus module provides Byzantine Fault Tolerant (BFT) consensus for multi-node deployments.

.. module:: warm_logic.consensus
   :synopsis: BFT consensus protocol

BFTNode
-------

Byzantine Fault Tolerant node.

.. class:: BFTNode(node_id, peers, config=None)

   Create a BFT consensus node.

   :param node_id: Unique identifier for this node
   :type node_id: str
   :param peers: List of peer node addresses
   :type peers: list[str]
   :param config: Optional configuration
   :type config: BFTConfig, optional

   **Example:**

   .. code-block:: python

      from warm_logic.consensus import BFTNode

      node = BFTNode(
          node_id="node-1",
          peers=["node-2:4001", "node-3:4001", "node-4:4001"]
      )

      await node.start()

   .. method:: start()

      Start the consensus node.

      :returns: None

   .. method:: stop()

      Stop the consensus node.

      :returns: None

   .. method:: propose(proposal)

      Propose a new action for consensus.

      :param proposal: Proposal to submit
      :type proposal: Proposal
      :returns: Consensus result
      :rtype: ConsensusResult

      **Example:**

      .. code-block:: python

         proposal = Proposal(
             action="approve_decision",
             data={"decision_hash": "abc123..."}
         )

         result = await node.propose(proposal)

         if result.finalized:
             print(f"Consensus reached in round {result.round}")
             print(f"Block hash: {result.block_hash}")
         else:
             print(f"Consensus failed: {result.reason}")

   .. method:: get_peers()

      Get connected peers.

      :returns: List of connected peer IDs
      :rtype: list[str]

   .. method:: get_status()

      Get node status.

      :returns: Node status
      :rtype: NodeStatus

Proposal
--------

Consensus proposal.

.. class:: Proposal(action, data)

   Create a proposal for consensus.

   :param action: Action type
   :type action: str
   :param data: Action data
   :type data: dict

   .. attribute:: action
      :type: str

      Action type.

   .. attribute:: data
      :type: dict

      Action data.

   .. attribute:: proposer
      :type: str

      Proposer node ID.

   .. attribute:: timestamp
      :type: datetime

      When proposal was created.

ConsensusResult
---------------

Result of consensus round.

.. class:: ConsensusResult

   .. attribute:: finalized
      :type: bool

      Whether consensus was reached.

   .. attribute:: block_hash
      :type: str or None

      Hash of finalized block (if finalized).

   .. attribute:: round
      :type: int

      Consensus round number.

   .. attribute:: votes
      :type: int

      Number of votes received.

   .. attribute:: quorum
      :type: int

      Quorum requirement.

   .. attribute:: reason
      :type: str or None

      Failure reason (if not finalized).

BFTConfig
---------

Configuration for BFT consensus.

.. class:: BFTConfig

   .. attribute:: timeout_ms
      :type: int

      Round timeout in milliseconds (default: 5000).

   .. attribute:: max_rounds
      :type: int

      Maximum rounds before failure (default: 10).

   .. attribute:: batch_size
      :type: int

      Maximum proposals per block (default: 100).

   .. attribute:: checkpoint_interval
      :type: int

      Blocks between checkpoints (default: 100).

Protocol Details
----------------

WL-BFT-v1 Protocol
^^^^^^^^^^^^^^^^^^

WarmLogic uses a modified PBFT protocol:

1. **Pre-Prepare**: Leader proposes block
2. **Prepare**: Nodes validate and vote
3. **Commit**: Nodes commit after 2f+1 prepares
4. **Reply**: Result returned to client

.. code-block:: text

   Leader           Replicas (1, 2, 3)
     |                    |  |  |
     |--- Pre-Prepare --->|  |  |
     |                    |  |  |
     |<---- Prepare ------|  |  |
     |<---- Prepare ---------|  |
     |<---- Prepare ------------|
     |                    |  |  |
     |---- Commit ------->|  |  |
     |---- Commit ------->|--|  |
     |---- Commit ------->|--|--|
     |                    |  |  |
     |<---- Reply --------|  |  |

Fault Tolerance
^^^^^^^^^^^^^^^

- Tolerates f < n/3 Byzantine nodes
- 4 nodes: tolerates 1 Byzantine node
- 7 nodes: tolerates 2 Byzantine nodes
- 10 nodes: tolerates 3 Byzantine nodes

Performance
-----------

.. list-table:: Consensus Performance
   :header-rows: 1

   * - Cluster Size
     - Latency (p50)
     - Throughput
   * - 3 nodes
     - 62 ms
     - 16.1/s
   * - 4 nodes
     - 87 ms
     - 11.5/s
   * - 7 nodes
     - 145 ms
     - 6.9/s
   * - 10 nodes
     - 215 ms
     - 4.7/s

Network Impact
^^^^^^^^^^^^^^

.. list-table:: Network Latency Impact (4 nodes)
   :header-rows: 1

   * - Network Latency
     - Consensus Latency
     - Throughput
   * - <1 ms (local)
     - 87 ms
     - 11.5/s
   * - 10 ms
     - 127 ms
     - 7.9/s
   * - 50 ms
     - 287 ms
     - 3.5/s
   * - 100 ms
     - 487 ms
     - 2.1/s

Deployment
----------

Multi-Node Setup
^^^^^^^^^^^^^^^^

.. code-block:: yaml

   # node-1.yaml
   node_id: "node-1"
   listen: "0.0.0.0:4001"
   peers:
     - "node-2.example.com:4001"
     - "node-3.example.com:4001"
     - "node-4.example.com:4001"

   # Start node
   # wlctl start --config node-1.yaml

Docker Compose
^^^^^^^^^^^^^^

.. code-block:: yaml

   version: '3.8'

   services:
     node1:
       image: ghcr.io/espressolee/warmlogic
       environment:
         - NODE_ID=node-1
         - PEERS=node2:4001,node3:4001,node4:4001
       ports:
         - "8001:8000"
         - "4001:4001"

     node2:
       image: ghcr.io/espressolee/warmlogic
       environment:
         - NODE_ID=node-2
         - PEERS=node1:4001,node3:4001,node4:4001
       ports:
         - "8002:8000"
         - "4002:4001"

     # ... node3, node4

View Change
-----------

When leader fails, view change occurs:

.. code-block:: python

   # View change is automatic, but can be monitored
   node.on_view_change(lambda old, new:
       print(f"View changed: {old} -> {new}")
   )

See Also
--------

* :doc:`sdk` - High-level SDK
* :doc:`crypto` - Cryptographic signatures for votes
* :doc:`storage` - Ledger storage after consensus
