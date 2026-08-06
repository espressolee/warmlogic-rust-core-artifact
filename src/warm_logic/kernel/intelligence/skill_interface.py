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
from abc import ABC, abstractmethod
from typing import Any, Dict


class SovereignSkill(ABC):
    """
    Abstract Base Class for all Sovereign Skills (Plugins).
    Provides a standardized interface for LLM interaction and execution.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the skill (e.g., 'calculator', 'db_query')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the skill does."""
        pass

    @abstractmethod
    def get_specification(self) -> Dict[str, Any]:
        """
        Returns the JSON schema specification for the tool.
        This is used to inform the LLM about the tool's parameters.
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> str:
        """
        Executes the skill's logic with the provided parameters.
        Returns a string result to be sent back to the LLM.
        """
        pass

    def validate_security(self, context: Dict[str, Any]) -> bool:
        """
        Optional: Validates if the execution is safe within the given context.
        Default implementation returns True.
        """
        return True
