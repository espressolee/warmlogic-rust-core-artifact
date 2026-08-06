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
# Kernel tests conftest.py
# NOTE: Mock configuration is now handled by the root conftest.py.
# This file is kept for any kernel-specific test fixtures.

# Do not force mock here - let root conftest.py decide based on
# WARMLOGIC_USE_MOCK env var and Rust module availability.
