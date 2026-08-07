"""Verification test for Aeon Engine."""

import json
import os
import sys

# Ensure warm_logic is in path
sys.path.append(os.getcwd())

from warm_logic.intelligence.graph.engine import AeonEngine


def test_aeon_engine_reality():
    print("Testing Aeon Intelligence (Graph-RAG) Engine...")

    graph_path = "out/test_aeon_graph.json"
    if os.path.exists(graph_path):
        os.remove(graph_path)

    engine = AeonEngine(graph_path=graph_path)

    # 1. Ingest Text
    sample_text = """
    WarmLogic Protocol v2 (WLPv2) requires a Secure Enclave (SEP) for hardware-bound identity.
    The GVM implements the moral finality check. SEP supports the GVM by providing signed attestation.
    P105 is the milestone for ZKP hardening.
    """
    print("Ingesting sample sovereign context...")
    engine.ingest_text(sample_text)

    # 2. Verify Graph Store
    assert os.path.exists(graph_path), "Graph file should be created."
    with open(graph_path, "r") as f:
        graph_data = json.load(f)
        print(f"   Nodes found: {len(graph_data['nodes'])}")
        print(f"   Edges found: {len(graph_data['edges'])}")
        assert len(graph_data["nodes"]) >= 5, "Should have extracted several entities."
        assert len(graph_data["edges"]) >= 2, "Should have extracted some relations."

    # 3. Test Semantic Retrieval
    query = "What does WLPv2 require?"
    print(f"Querying semantic context for: '{query}'")
    context = engine.get_semantic_context(query)

    print("\n--- RETRIEVED CONTEXT ---")
    print(context)
    print("-------------------------\n")

    assert "WLPv2" in context
    assert "SEP" in context
    assert "requires" in context.lower() or "Relationships" in context

    print("AEON ENGINE SCENARIO OK (not verification): Semantic Lattice Operational.")


if __name__ == "__main__":
    test_aeon_engine_reality()
