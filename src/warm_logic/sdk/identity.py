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
from typing import Optional, Tuple

from warm_logic.kernel.identity.kinetic_id import KineticIdentity


class SovereignIdentity:
    def __init__(self, keypair: Optional[Tuple[str, str]] = None):
        self._inner = KineticIdentity(keypair=keypair)
        self.public_key = self._inner.public_key
        self.private_key = self._inner.private_key

    def sign(self, payload: str) -> str:
        return self._inner.sign_intent(payload)

    @staticmethod
    def verify(public_key: str, payload: str, signature: str) -> bool:
        return KineticIdentity.verify_intent(public_key, payload, signature)
