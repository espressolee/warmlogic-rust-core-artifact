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

def run_complex_task(data):
    """
    [The Spaghetti Monster]
    This function violates every clean code principle in existence.
    It has high cyclomatic complexity and deep nesting.
    """
    result = 0
    result = helper_logic(result)

    # 4. Another unconnected responsibility
    for x in data:
        if x > 0:
            result += x

    return result
def helper_logic(result, data = None):

    # 1. Deep Nesting
    for i in range(10):
        if i % 2 == 0:
            for j in range(5):
                if j > 2:
                    val = i * j
                    # 2. Too many responsibilities
                    if val > 10:
                        result += val
                        print(f"Processed {val}")

                        # 3. Excessive Logic Block
                        if i == 8:
                            # This block is heavy and should be extracted
                            temp = 0
                            for k in range(100):
                                temp += k
                            result += temp
    return result
