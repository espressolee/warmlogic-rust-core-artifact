# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
[Phase 105.1] Rule-Based World Simulation.
Implements a simple world model with state transitions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("WorldSim")


class EntityType(Enum):
    AGENT = "agent"
    OBJECT = "object"
    LOCATION = "location"
    EVENT = "event"


@dataclass
class Entity:
    """An entity in the world model."""

    id: str
    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)
    relations: Dict[str, List[str]] = field(
        default_factory=dict
    )  # relation_name -> [entity_ids]


@dataclass
class WorldState:
    """A snapshot of the world state."""

    timestamp: datetime
    entities: Dict[str, Entity]
    global_properties: Dict[str, Any]
    state_hash: str = ""


@dataclass
class TransitionRule:
    """A rule for state transitions."""

    name: str
    preconditions: Callable[[WorldState, Dict], bool]
    effects: Callable[[WorldState, Dict], WorldState]
    description: str


class RuleBasedWorldModel:
    """
    [Phase 105.1] Rule-Based World Simulation.

    Capabilities:
    1. Entity management (create, update, query)
    2. State transitions via rules
    3. Prediction of future states
    4. Counterfactual reasoning (what-if)
    """

    def __init__(self) -> None:
        self.entities: Dict[str, Entity] = {}
        self.rules: List[TransitionRule] = []
        self.history: List[WorldState] = []
        self.global_properties: Dict[str, Any] = {"time": 0}
        self._setup_default_rules()
        logger.info("[WorldModel] Rule-Based Engine Active.")

    def _setup_default_rules(self) -> None:
        """Setup default world rules."""
        # Rule: Time always advances
        self.add_rule(
            TransitionRule(
                name="time_advance",
                preconditions=lambda s, p: True,
                effects=lambda s, p: self._advance_time(s),
                description="Time advances by 1 unit",
            )
        )

        # Rule: Objects can be moved
        self.add_rule(
            TransitionRule(
                name="move_object",
                preconditions=lambda s, p: (
                    p.get("object_id") in s.entities
                    and p.get("target_location") in s.entities
                    and s.entities[p["target_location"]].entity_type
                    == EntityType.LOCATION
                ),
                effects=lambda s, p: self._move_object(s, p),
                description="Move an object to a location",
            )
        )

        # Rule: Agents can interact
        self.add_rule(
            TransitionRule(
                name="agent_interact",
                preconditions=lambda s, p: (
                    p.get("agent_id") in s.entities and p.get("target_id") in s.entities
                ),
                effects=lambda s, p: self._agent_interact(s, p),
                description="Agent interacts with target",
            )
        )

    def _advance_time(self, state: WorldState) -> WorldState:
        """Advance time in the world."""
        state.global_properties["time"] = state.global_properties.get("time", 0) + 1
        return state

    def _move_object(self, state: WorldState, params: Dict) -> WorldState:
        """Move an object to a new location."""
        obj = state.entities[params["object_id"]]
        obj.relations["at"] = [params["target_location"]]
        return state

    def _agent_interact(self, state: WorldState, params: Dict) -> WorldState:
        """Record agent interaction."""
        agent = state.entities[params["agent_id"]]
        if "interactions" not in agent.properties:
            agent.properties["interactions"] = []
        agent.properties["interactions"].append(
            {
                "target": params["target_id"],
                "time": state.global_properties.get("time", 0),
            }
        )
        return state

    def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Entity:
        """Add an entity to the world."""
        entity_id = f"E{len(self.entities):05d}"
        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            properties=properties or {},
        )
        self.entities[entity_id] = entity
        logger.debug(f"Added entity: {name} ({entity_type.value})")
        return entity

    def add_rule(self, rule: TransitionRule) -> None:
        """Add a transition rule."""
        self.rules.append(rule)

    def get_state(self) -> WorldState:
        """Get current world state."""
        import hashlib
        import json

        state_data = {
            "entities": {k: v.name for k, v in self.entities.items()},
            "global": self.global_properties,
        }
        state_hash = hashlib.sha256(
            json.dumps(state_data, sort_keys=True).encode()
        ).hexdigest()[:16]

        return WorldState(
            timestamp=datetime.now(),
            entities=dict(self.entities),
            global_properties=dict(self.global_properties),
            state_hash=state_hash,
        )

    def apply_action(
        self, action_name: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Apply an action using matching rules."""
        params = params or {}
        current_state = self.get_state()

        # Find matching rule
        for rule in self.rules:
            if rule.name == action_name:
                if rule.preconditions(current_state, params):
                    # Apply effects
                    new_state = rule.effects(current_state, params)

                    # Update world
                    self.entities = new_state.entities
                    self.global_properties = new_state.global_properties

                    # Save history
                    self.history.append(current_state)

                    logger.info(f"Applied action: {action_name}")
                    return {
                        "success": True,
                        "action": action_name,
                        "state_hash": self.get_state().state_hash,
                    }
                else:
                    return {
                        "success": False,
                        "action": action_name,
                        "reason": "Preconditions not met",
                    }

        return {"success": False, "action": action_name, "reason": "No matching rule"}

    def predict(self, actions: List[Dict]) -> List[WorldState]:
        """Predict future states given a sequence of actions."""
        # Save current state
        saved_entities = dict(self.entities)
        saved_global = dict(self.global_properties)

        predicted_states = []

        for action in actions:
            result = self.apply_action(action["name"], action.get("params", {}))
            if result["success"]:
                predicted_states.append(self.get_state())

        # Restore original state
        self.entities = saved_entities
        self.global_properties = saved_global

        return predicted_states

    def query(
        self, query_type: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Entity]:
        """Query the world model."""
        params = params or {}
        results: List[Entity] = []

        if query_type == "by_type":
            entity_type = EntityType(params.get("type", "object"))
            results = [
                e for e in self.entities.values() if e.entity_type == entity_type
            ]

        elif query_type == "by_property":
            prop_name = str(params.get("property", ""))
            prop_value = params.get("value")
            results = [
                e
                for e in self.entities.values()
                if e.properties.get(prop_name) == prop_value
            ]

        elif query_type == "by_relation":
            relation = str(params.get("relation", ""))
            target_id = params.get("target")
            results = [
                e
                for e in self.entities.values()
                if target_id in e.relations.get(relation, [])
            ]

        return results

    def counterfactual(
        self, what_if: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a counterfactual simulation (what-if analysis)."""
        params = params or {}

        # Clone current state
        original_state = self.get_state()

        # Apply hypothetical changes
        if what_if == "entity_removed":
            entity_id = params.get("entity_id")
            if entity_id in self.entities:
                del self.entities[entity_id]

        elif what_if == "property_changed":
            entity_id = params.get("entity_id")
            prop = str(params.get("property", ""))
            value = params.get("value")
            if entity_id in self.entities and prop:
                self.entities[entity_id].properties[prop] = value

        # Get counterfactual state
        cf_state = self.get_state()

        # Restore original
        self.entities = original_state.entities
        self.global_properties = original_state.global_properties

        return {
            "original_hash": original_state.state_hash,
            "counterfactual_hash": cf_state.state_hash,
            "changed": original_state.state_hash != cf_state.state_hash,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get world model statistics."""
        type_counts: Dict[str, int] = {}
        for entity in self.entities.values():
            t = entity.entity_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "entities": len(self.entities),
            "rules": len(self.rules),
            "history_length": len(self.history),
            "current_time": self.global_properties.get("time", 0),
            "entity_types": type_counts,
        }


def get_world_model() -> RuleBasedWorldModel:
    """Get a new Rule-Based World Model."""
    return RuleBasedWorldModel()
