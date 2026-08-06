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
import unittest

from warm_logic.kernel.mesh.transport import AbstractTransport


class TestTransportAbstract(unittest.IsolatedAsyncioTestCase):
    async def test_abstract_methods(self):
        # Line 30, 35, 40, 45
        class MockTransport(AbstractTransport):
            async def start_server(self, h, p, handler):
                return await super().start_server(h, p, handler)

            def sendto(self, d, a):
                super().sendto(d, a)

            def close(self):
                super().close()

            def get_port(self):
                return super().get_port()

        mt = MockTransport()
        await mt.start_server("127.0.0.1", 0, lambda d, a: None)
        mt.sendto(b"", ("1.2.3.4", 80))
        mt.close()
        mt.get_port()


if __name__ == "__main__":
    unittest.main()
