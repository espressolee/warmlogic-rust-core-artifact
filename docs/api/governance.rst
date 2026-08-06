Governance Reference
====================

The governance module provides policy evaluation and constitutional enforcement.

.. module:: warm_logic.governance
   :synopsis: Governance engine and policy evaluation

GovernanceEngine
----------------

Core policy evaluation engine.

.. class:: GovernanceEngine(config=None)

   Create a governance engine.

   :param config: Optional configuration dictionary
   :type config: dict, optional

   **Example:**

   .. code-block:: python

      from warm_logic.governance import GovernanceEngine

      engine = GovernanceEngine()
      engine.load_policy("constitution.yaml")

   .. method:: load_policy(path)

      Load a policy from a YAML file.

      :param path: Path to policy file
      :type path: str
      :raises PolicyLoadError: If policy is invalid

   .. method:: evaluate(intent, context)

      Evaluate an action against loaded policies.

      :param intent: Action intent
      :type intent: str
      :param context: Action context
      :type context: dict
      :returns: Evaluation result
      :rtype: PolicyResult

      **Example:**

      .. code-block:: python

         result = engine.evaluate(
             intent="delete_user",
             context={"user_id": "123", "reason": "requested"}
         )

         if result.allowed:
             print("Action permitted")
         else:
             print(f"Denied: {result.reason}")

   .. method:: add_rule(rule)

      Add a rule dynamically.

      :param rule: Rule to add
      :type rule: Rule

   .. method:: get_policy_version()

      Get current policy version.

      :returns: Policy version string
      :rtype: str

Policy
------

Policy definition and loading.

.. class:: Policy

   .. classmethod:: from_yaml(path)

      Load policy from YAML file.

      :param path: Path to YAML file
      :type path: str
      :returns: Policy object
      :rtype: Policy

   .. classmethod:: from_dict(data)

      Create policy from dictionary.

      :param data: Policy data
      :type data: dict
      :returns: Policy object
      :rtype: Policy

   .. attribute:: name
      :type: str

      Policy name.

   .. attribute:: version
      :type: str

      Policy version.

   .. attribute:: rules
      :type: list[Rule]

      List of rules in the policy.

Policy YAML Format
------------------

Example constitution.yaml:

.. code-block:: yaml

   name: WarmLogic Constitution
   version: "1.0.0"

   # Core principles
   principles:
     - name: safety_first
       description: "Safety takes precedence over capability"
     - name: transparency
       description: "All decisions must be explainable"

   # Access control
   roles:
     admin:
       permissions:
         - "*"
     operator:
       permissions:
         - "read:*"
         - "write:logs"
     viewer:
       permissions:
         - "read:*"

   # Policy rules
   policies:
     no_dangerous_actions:
       description: "Prevent dangerous operations"
       rules:
         - intent: "delete_*"
           action: deny
           reason: "Deletion requires admin approval"
           unless:
             - role: admin
             - has_approval: true

         - intent: "modify_constitution"
           action: deny
           reason: "Constitution is immutable"

     rate_limiting:
       description: "Rate limit high-frequency operations"
       rules:
         - intent: "*"
           rate_limit:
             max_requests: 100
             window_seconds: 60

     audit_logging:
       description: "Log all sensitive operations"
       rules:
         - intent: "read:sensitive_*"
           action: allow
           audit: true
           audit_level: detailed

Rule
----

Individual policy rule.

.. class:: Rule

   .. attribute:: intent
      :type: str

      Intent pattern to match (supports wildcards).

   .. attribute:: action
      :type: str

      Action to take (allow, deny, require_approval).

   .. attribute:: reason
      :type: str

      Reason for the rule.

   .. attribute:: conditions
      :type: list[Condition]

      Conditions for rule to apply.

PolicyResult
------------

Result of policy evaluation.

.. class:: PolicyResult

   .. attribute:: allowed
      :type: bool

      Whether the action is allowed.

   .. attribute:: reason
      :type: str or None

      Reason (if denied).

   .. attribute:: matched_rule
      :type: Rule or None

      The rule that matched.

   .. attribute:: evaluated_policies
      :type: list[str]

      Policies that were evaluated.

   .. attribute:: audit_required
      :type: bool

      Whether action requires audit logging.

   .. attribute:: approval_required
      :type: bool

      Whether action requires additional approval.

Meta-Governance
---------------

Meta-governance for policy evolution.

.. class:: MetaGovernanceEngine

   Engine for managing policy changes.

   .. method:: propose_policy_change(change)

      Propose a change to the policy.

      :param change: Proposed change
      :type change: PolicyChange
      :returns: Proposal ID
      :rtype: str

   .. method:: vote(proposal_id, vote)

      Vote on a policy proposal.

      :param proposal_id: Proposal ID
      :type proposal_id: str
      :param vote: Vote (approve/reject)
      :type vote: str

   .. method:: get_proposal_status(proposal_id)

      Get status of a proposal.

      :param proposal_id: Proposal ID
      :type proposal_id: str
      :returns: Proposal status
      :rtype: ProposalStatus

Policy Hot-Reload
-----------------

Policies can be reloaded without restart:

.. code-block:: python

   from warm_logic.governance import PolicyHotReloader

   reloader = PolicyHotReloader(engine)
   reloader.watch("constitution.yaml")

   # Policy will be reloaded when file changes

See Also
--------

* :doc:`sdk` - High-level SDK
* :doc:`consensus` - Multi-node consensus for policy changes
