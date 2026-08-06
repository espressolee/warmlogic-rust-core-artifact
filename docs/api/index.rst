WarmLogic API Reference
=======================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   overview
   sdk
   governance
   crypto
   consensus
   storage

Overview
--------

WarmLogic provides a comprehensive API for building sovereign AI governance applications.

.. warning::

   **research prototype Notice**: WarmLogic is at research prototype status.
   APIs may change before 1.0 stable release.

Quick Links
-----------

* :doc:`sdk` - SovereignClient and high-level SDK
* :doc:`governance` - Governance engine and policy evaluation
* :doc:`crypto` - Cryptographic operations (ML-DSA-65, ZK proofs)
* :doc:`consensus` - BFT consensus protocol
* :doc:`storage` - Ledger and database operations

Installation
------------

.. code-block:: bash

   pip install warm-logic

   # Or from source
   git clone https://github.com/espressolee/warmlogic-rust-core-artifact
   cd warmlogic
   make setup

Basic Usage
-----------

.. code-block:: python

   from warm_logic.sdk import SovereignClient

   client = SovereignClient()

   decision = client.propose_action(
       intent="log_event",
       context={"event": "hello", "severity": "info"}
   )

   if decision.approved:
       print(f"Approved: {decision.proof_hash}")
   else:
       print(f"Rejected: {decision.rejection_reason}")

Indices and Tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
