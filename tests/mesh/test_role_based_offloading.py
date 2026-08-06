import unittest
from unittest.mock import MagicMock, patch

from src.warm_logic.kernel.intelligence.swarm_orchestrator import (
    SubTask,
    SwarmOrchestrator,
)
from warm_logic.kernel.mesh.dht import Contact


class TestRoleBasedOffloading(unittest.TestCase):
    def test_capability_aware_assignment(self):
        """Verify that tasks are assigned to nodes with matching capabilities."""
        # 1. Setup Mock Mesh
        mock_mesh = MagicMock()
        mock_mesh.node_id.hex.return_value = "local_node"
        mock_mesh.capabilities = {"LLM_REASONING": 5}  # Local is weak

        # 2. Setup Neighbors
        # Peer 1: root authority (LLM Specialist)
        c1 = Contact(b"peer_1_id", "1.1.1.1", 5000, capabilities={"LLM_REASONING": 100})
        # Peer 2: Edge (Sensor Specialist)
        c2 = Contact(b"peer_2_id", "2.2.2.2", 5000, capabilities={"SENSOR_STREAM": 100})

        mock_mesh.routing.get_all_contacts.return_value = [c1, c2]

        orchestrator = SwarmOrchestrator(mock_mesh, MagicMock())

        # 3. Test LLM Task
        llm_task = SubTask(task_id="t1", description="Reason about ethics")
        assigned = orchestrator.assign_tasks([llm_task])
        self.assertEqual(assigned[0].assigned_node, b"peer_1_id".hex())

        # 4. Test Sensor Task
        sensor_task = SubTask(task_id="t2", description="Collect sensor data")
        assigned = orchestrator.assign_tasks([sensor_task])
        self.assertEqual(assigned[0].assigned_node, b"peer_2_id".hex())

    def test_fallback_to_local(self):
        """Verify that it falls back to local if no specialist is found."""
        mock_mesh = MagicMock()
        mock_mesh.node_id.hex.return_value = "local_node"
        mock_mesh.capabilities = {"LLM_REASONING": 10}
        mock_mesh.routing.get_all_contacts.return_value = []

        orchestrator = SwarmOrchestrator(mock_mesh, MagicMock())
        task = SubTask(task_id="t1", description="Any task")
        assigned = orchestrator.assign_tasks([task])
        self.assertEqual(assigned[0].assigned_node, "local_node")


if __name__ == "__main__":
    unittest.main()
