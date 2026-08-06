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
"""Computing Limit Models."""

import struct
from dataclasses import dataclass


@dataclass
class FloatingPointPrecision:
    """IEEE 754 floating-point precision limits."""

    def quantize_float32(self, value: float) -> float:
        """Quantize to float32 precision."""
        return struct.unpack("f", struct.pack("f", value))[0]

    def get_ulp(self, value: float) -> float:
        """Unit in Last Place for float32."""
        if value == 0:
            return 1.4e-45  # Smallest denormal
        import math

        _, exp = math.frexp(abs(value))
        return 2 ** (exp - 24)  # 23-bit mantissa + 1 hidden


@dataclass
class TimerOverflow:
    """Timer wrap-around model. Reference: Real-time systems."""

    max_value: int = 0xFFFFFFFF  # uint32_t
    current_value: int = 0
    overflow_count: int = 0

    def tick(self, increment: int = 1):
        """Increment timer, checking for overflow."""
        self.current_value += increment
        if self.current_value > self.max_value:
            self.overflow_count += 1
            self.current_value = self.current_value % (self.max_value + 1)
