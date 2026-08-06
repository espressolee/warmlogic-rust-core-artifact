import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

nx = pytest.importorskip("networkx")

import warm_logic.kernel.memory.semantic as semantic_module
from warm_logic.kernel.memory.episodic import EpisodicStore
from warm_logic.kernel.memory.graph_vault import GraphVault
from warm_logic.kernel.memory.semantic import SemanticMemory
from warm_logic.kernel.memory.vector_vault import VectorVault


class TestMemorySaturation:
    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return tmp_path

    # --- EpisodicStore Tests ---
    def test_episodic_store_flow(self, tmp_dir):
        db_path = str(tmp_dir / "episodic.db")
        es = EpisodicStore(db_path)
        es.add_memory("user", "Hello agents")
        es.add_memory("assistant", "Hello human", {"source": "test"})

        history = es.get_session_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"

        summary = es.get_last_conversation_summary()
        assert (
            "No previous memories found." in summary
        )  # Because session_id matches current

        # Test summary with a different session
        es2 = EpisodicStore(db_path)
        es2.session_id = "new_session"
        summary2 = es2.get_last_conversation_summary()
        assert "Last Active" in summary2
        assert "user: Hello agents" in summary2

    # --- VectorVault Tests ---
    def test_vector_vault_init(self, tmp_dir):
        persist_path = str(tmp_dir / "vector")
        with patch("chromadb.PersistentClient") as mock_client:
            vv = VectorVault(persist_path)
            assert vv.persist_path == persist_path
            mock_client.assert_called_once()

    def test_vector_vault_store_thought(self, tmp_dir):
        with patch("chromadb.PersistentClient"):
            vv = VectorVault(str(tmp_dir / "v2"))
            vv.thoughts = MagicMock()
            vv.store_thought("Mind over matter", {"meta": 1})
            vv.thoughts.add.assert_called_once()

            # Exception path
            vv.thoughts.add.side_effect = Exception("Chroma Fail")
            vv.store_thought("Fail", {})  # Should not raise

    def test_vector_vault_query(self, tmp_dir):
        with patch("chromadb.PersistentClient"):
            vv = VectorVault(str(tmp_dir / "v3"))
            vv.thoughts = MagicMock()
            vv.thoughts.query.return_value = {"documents": [["Result A"]]}
            assert vv.query_thoughts("query") == ["Result A"]

            # Empty results
            vv.thoughts.query.return_value = {"documents": []}
            assert vv.query_thoughts("query") == []

            # Exception path
            vv.thoughts.query.side_effect = Exception("Query Error")
            assert vv.query_thoughts("query") == []

    def test_vector_vault_store_plan(self, tmp_dir):
        with patch("chromadb.PersistentClient"):
            vv = VectorVault(str(tmp_dir / "v4"))
            vv.plans = MagicMock()
            vv.store_plan("Goal", ["Step 1"], "Success")
            vv.plans.add.assert_called_once()

            # Exception path
            vv.plans.add.side_effect = Exception("Plan Store Fail")
            vv.store_plan("Goal", [], "Fail")

    def test_vector_vault_wipe(self, tmp_dir):
        with patch("chromadb.PersistentClient") as mock_client_class:
            mock_client = mock_client_class.return_value
            vv = VectorVault(str(tmp_dir / "v5"))
            vv.wipe_memory()
            mock_client.delete_collection.assert_called()

            # Exception path
            mock_client.delete_collection.side_effect = Exception("Wipe Fail")
            vv.wipe_memory()

    # --- GraphVault Tests ---
    def test_graph_vault_load_success(self, tmp_dir):
        graph_path = str(tmp_dir / "graph.json")
        # Use NetworkX to generate valid schema
        temp_g = nx.DiGraph()
        temp_g.add_node("NodeA")
        data = nx.node_link_data(temp_g)
        with open(graph_path, "w") as f:
            json.dump(data, f)

        gv = GraphVault(graph_path)
        assert "NodeA" in gv.graph.nodes

    def test_graph_vault_load_fail(self, tmp_dir):
        graph_path = tmp_dir / "bad_graph.json"
        graph_path.write_text("{ corrupt }")

        gv = GraphVault(str(graph_path))
        assert gv.graph.number_of_nodes() == 0

    def test_graph_vault_save_fail(self, tmp_dir):
        gv = GraphVault(str(tmp_dir / "graph_save.json"))
        with patch("builtins.open", side_effect=PermissionError("Locked")):
            gv.save()  # Should log error

    def test_graph_vault_concepts(self, tmp_dir):
        gv = GraphVault(str(tmp_dir / "graph_ops.json"))
        gv.add_concept("NodeA", type="Type1")
        gv.link_concepts("NodeA", "NodeB", "LeadsTo")
        assert "NodeB" in gv.graph.nodes
        assert gv.get_related("NodeA") == ["NodeB"]
        assert gv.get_related("Missing") == []

    def test_graph_vault_pathfinding(self, tmp_dir):
        gv = GraphVault(str(tmp_dir / "graph_path.json"))
        gv.link_concepts("A", "B", "connect")
        gv.link_concepts("B", "C", "connect")
        gv.add_concept("Z")  # Isolated node
        assert gv.find_path("A", "C") == ["A", "B", "C"]

        # Test NoPath coverage
        assert gv.find_path("A", "Z") == []

        # Test NodeNotFound coverage (Z is not in graph)
        with patch(
            "warm_logic.kernel.memory.graph_vault.nx.shortest_path",
            side_effect=nx.NodeNotFound("Missing"),
        ):
            assert gv.find_path("Missing", "A") == []

    def test_graph_vault_wipe(self, tmp_dir):
        gv = GraphVault(str(tmp_dir / "graph_wipe.json"))
        gv.add_concept("A")
        gv.wipe()
        assert gv.graph.number_of_nodes() == 0

    # --- SemanticMemory Tests ---
    def test_semantic_memory_lazy_loading(self):
        # Patch the shared globals to avoid side effects
        semantic_module._CHROMADB = None
        semantic_module._SENTENCE_TRANSFORMERS = None

        with patch.dict(sys.modules, {"chromadb": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                assert semantic_module._ensure_chromadb() is None
                assert semantic_module._ensure_sentence_transformers() is None

    def test_semantic_memory_init_no_chroma(self):
        with patch(
            "warm_logic.kernel.memory.semantic._ensure_chromadb", return_value=None
        ):
            sm = SemanticMemory()
            assert sm.is_available() is False
            assert sm.count() == 0

    @patch("warm_logic.kernel.memory.semantic._ensure_chromadb")
    @patch("warm_logic.kernel.memory.semantic._ensure_sentence_transformers")
    def test_semantic_memory_init_success(self, mock_trans, mock_chroma):
        mock_chroma_lib = mock_chroma.return_value
        mock_trans_lib = mock_trans.return_value

        sm = SemanticMemory()
        assert sm.is_available() is True
        mock_chroma_lib.PersistentClient.assert_called_once()

        # Verify count call coverage
        sm._collection = MagicMock()
        sm._collection.count.return_value = 100
        assert sm.count() == 100

        # Verify CustomEmbeddingFn call
        if sm._embedding_fn:
            mock_model = MagicMock()
            mock_model.encode.return_value = MagicMock(tolist=lambda: [[0.1, 0.2]])
            fn = sm._embedding_fn
            fn._model = mock_model
            res = fn(["hello"])
            assert res == [[0.1, 0.2]]

    def test_semantic_memory_add_search(self):
        with patch("warm_logic.kernel.memory.semantic._ensure_chromadb"):
            sm = SemanticMemory()
            sm._collection = MagicMock()

            # Unavailable path
            sm._collection = None
            assert sm.add("test") is False
            assert sm.search("query") == []

            # Success path
            sm._collection = MagicMock()
            assert sm.add("Hello", role="assistant", metadata={"key": "val"}) is True
            sm._collection.add.assert_called_once()

            # Search with filter
            sm.search("find", filter_role="user")
            sm._collection.query.assert_called_with(
                query_texts=["find"], n_results=5, where={"role": "user"}
            )

            # Search parsing
            sm._collection.query.return_value = {
                "documents": [["Mem1"]],
                "distances": [[0.5]],
                "metadatas": [[{"role": "user"}]],
            }
            res = sm.search("find")
            assert len(res) == 1
            assert res[0]["content"] == "Mem1"

            # Exception paths
            sm._collection.add.side_effect = Exception("Add Fail")
            assert sm.add("fail") is False
            sm._collection.query.side_effect = Exception("Query Fail")
            assert sm.search("fail") == []

    def test_semantic_memory_sync_episodic(self, tmp_dir):
        db_path = tmp_dir / "episodic.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE episodes (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, timestamp REAL)"
        )
        conn.execute(
            "INSERT INTO episodes (session_id, role, content, timestamp) VALUES ('s1', 'user', 'sync me', 123.456)"
        )
        conn.execute(
            "INSERT INTO episodes (session_id, role, content, timestamp) VALUES ('s1', 'user', 'already in', 789.012)"
        )
        conn.commit()
        conn.close()

        with patch("warm_logic.kernel.memory.semantic._ensure_chromadb"):
            with patch(
                "warm_logic.kernel.memory.semantic.Path.exists",
                side_effect=[False, True, True],
            ):
                sm = SemanticMemory(episodic_db_path=str(db_path))
                sm._collection = MagicMock()

                # Path missing path
                assert sm.sync_from_episodic() == 0

                # is_available False path
                sm._collection = None
                assert sm.sync_from_episodic() == 0
                sm._collection = MagicMock()

                # Already indexed check logic for line 248
                # Return list with ID for 'already in' and empty list for 'sync me'
                sm._collection.get.side_effect = [{"ids": ["some_id"]}, {"ids": []}]

                count = sm.sync_from_episodic()
                assert count == 1  # Only one should be synced
                assert sm._collection.add.call_count == 1

    def test_semantic_memory_get_context(self):
        with patch("warm_logic.kernel.memory.semantic._ensure_chromadb"):
            sm = SemanticMemory()
            with patch.object(sm, "search") as mock_search:
                # No results
                mock_search.return_value = []
                assert sm.get_context_for_query("hello") == ""

                # Results with truncation
                mock_search.return_value = [
                    {"content": "A" * 50, "metadata": {"role": "assistant"}},
                    {"content": "B" * 60, "metadata": {"role": "user"}},
                ]
                context = sm.get_context_for_query("query", max_tokens=100)
                assert "assistant" in context
                assert "user" not in context  # Truncated

    def test_semantic_memory_init_no_sentence_transformers(self):
        with patch("warm_logic.kernel.memory.semantic._ensure_chromadb"):
            with patch(
                "warm_logic.kernel.memory.semantic._ensure_sentence_transformers",
                return_value=None,
            ):
                sm = SemanticMemory()
                assert sm.is_available() is True
                assert sm._model is None
                assert sm._embedding_fn is None
