Storage Reference
=================

The storage module provides ledger and database operations.

.. module:: warm_logic.storage
   :synopsis: Ledger and database operations

Ledger
------

Append-only cryptographic ledger.

.. class:: Ledger(path, config=None)

   Create or open a ledger.

   :param path: Path to ledger directory
   :type path: str
   :param config: Optional configuration
   :type config: LedgerConfig, optional

   **Example:**

   .. code-block:: python

      from warm_logic.storage import Ledger

      ledger = Ledger("~/.warm_logic/ledger")

   .. method:: append(transactions, metadata=None)

      Append a new block to the ledger.

      :param transactions: Transactions to include
      :type transactions: list[Transaction]
      :param metadata: Optional block metadata
      :type metadata: dict, optional
      :returns: Created block
      :rtype: Block

      **Example:**

      .. code-block:: python

         from warm_logic.storage import Transaction

         tx1 = Transaction(
             type="decision",
             data={"intent": "log_event", "approved": True}
         )

         block = ledger.append(
             transactions=[tx1],
             metadata={"epoch": 42}
         )

         print(f"Block height: {block.height}")
         print(f"Block hash: {block.hash}")

   .. method:: get_block(hash_or_height)

      Get a block by hash or height.

      :param hash_or_height: Block hash or height
      :type hash_or_height: str or int
      :returns: Block if found
      :rtype: Block or None

   .. method:: get_latest()

      Get the latest block.

      :returns: Latest block
      :rtype: Block

   .. method:: get_height()

      Get current ledger height.

      :returns: Block height
      :rtype: int

   .. method:: verify_chain()

      Verify the entire hash chain.

      :returns: Verification result
      :rtype: ChainVerificationResult

      **Example:**

      .. code-block:: python

         result = ledger.verify_chain()

         if result.valid:
             print("Chain verified successfully")
         else:
             print(f"Corruption at block {result.failed_at}")

   .. method:: get_state_root()

      Get current state root hash.

      :returns: State root hash
      :rtype: str

   .. method:: export(path, format="json")

      Export ledger to file.

      :param path: Output path
      :type path: str
      :param format: Export format (json, cbor)
      :type format: str

   .. method:: close()

      Close the ledger.

Block
-----

Ledger block.

.. class:: Block

   .. attribute:: height
      :type: int

      Block height (0-indexed).

   .. attribute:: hash
      :type: str

      Block hash (SHA3-256).

   .. attribute:: previous_hash
      :type: str

      Previous block hash.

   .. attribute:: timestamp
      :type: datetime

      Block creation time.

   .. attribute:: transactions
      :type: list[Transaction]

      Transactions in this block.

   .. attribute:: metadata
      :type: dict

      Block metadata.

   .. attribute:: state_root
      :type: str

      State root after this block.

   .. attribute:: signature
      :type: bytes

      ML-DSA-65 signature.

Transaction
-----------

Individual transaction record.

.. class:: Transaction(type, data)

   Create a transaction.

   :param type: Transaction type
   :type type: str
   :param data: Transaction data
   :type data: dict

   .. attribute:: id
      :type: str

      Transaction ID (auto-generated).

   .. attribute:: type
      :type: str

      Transaction type.

   .. attribute:: data
      :type: dict

      Transaction data.

   .. attribute:: timestamp
      :type: datetime

      Creation time.

StateStore
----------

Key-value state store (Sled backend).

.. class:: StateStore(path)

   Create or open a state store.

   :param path: Path to database directory
   :type path: str

   **Example:**

   .. code-block:: python

      from warm_logic.storage import StateStore

      store = StateStore("~/.warm_logic/state")

   .. method:: get(key)

      Get a value by key.

      :param key: Key
      :type key: str
      :returns: Value if found
      :rtype: bytes or None

   .. method:: set(key, value)

      Set a key-value pair.

      :param key: Key
      :type key: str
      :param value: Value
      :type value: bytes

   .. method:: delete(key)

      Delete a key.

      :param key: Key
      :type key: str

   .. method:: scan(prefix)

      Scan keys with prefix.

      :param prefix: Key prefix
      :type prefix: str
      :returns: Iterator of (key, value) pairs
      :rtype: Iterator[tuple[str, bytes]]

      **Example:**

      .. code-block:: python

         for key, value in store.scan("user:"):
             print(f"{key}: {value}")

   .. method:: batch_write(operations)

      Atomic batch write.

      :param operations: List of (operation, key, value) tuples
      :type operations: list[tuple]

      **Example:**

      .. code-block:: python

         store.batch_write([
             ("set", "key1", b"value1"),
             ("set", "key2", b"value2"),
             ("delete", "old_key", None),
         ])

   .. method:: compact()

      Compact the database.

   .. method:: close()

      Close the store.

Performance
-----------

.. list-table:: Storage Performance (Sled on NVMe SSD)
   :header-rows: 1

   * - Operation
     - Latency (p50)
     - Throughput
   * - Single Write
     - 95 μs
     - 10,526/s
   * - Single Read
     - 12 μs
     - 83,333/s
   * - Batch Write (100)
     - 2.8 ms
     - 35,714 items/s
   * - Range Scan (100)
     - 450 μs
     - 222,222 items/s
   * - Block Append
     - 1.2 ms
     - 833/s

Storage Sizes
-------------

.. list-table:: Storage Sizes
   :header-rows: 1

   * - Component
     - Size
     - Notes
   * - Block Header
     - 256 bytes
     - Fixed
   * - Transaction
     - 512-2048 bytes
     - Variable
   * - Evidence Bundle
     - 1-4 KB
     - With proofs
   * - ML-DSA-65 Signature
     - 3,309 bytes
     - Per block

Backup & Recovery
-----------------

Backup
^^^^^^

.. code-block:: python

   from warm_logic.storage import backup_ledger

   backup_ledger(
       source="~/.warm_logic/ledger",
       destination="/backup/ledger-2026-02-07.tar.gz",
       compress=True
   )

Recovery
^^^^^^^^

.. code-block:: python

   from warm_logic.storage import restore_ledger

   restore_ledger(
       source="/backup/ledger-2026-02-07.tar.gz",
       destination="~/.warm_logic/ledger"
   )

Pruning
^^^^^^^

.. code-block:: python

   from warm_logic.storage import prune_ledger

   # Keep only last 30 days
   prune_ledger(
       path="~/.warm_logic/ledger",
       keep_days=30,
       keep_checkpoints=True
   )

CLI Commands
------------

.. code-block:: bash

   # Database stats
   wlctl db stats

   # Verify integrity
   wlctl db verify

   # Compact database
   wlctl db compact

   # Export ledger
   wlctl db export --format json > ledger.json

   # Prune old data
   wlctl db prune --before 30d

See Also
--------

* :doc:`sdk` - High-level SDK
* :doc:`consensus` - Consensus before ledger append
* :doc:`crypto` - Cryptographic signatures
