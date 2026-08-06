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
import json
from unittest.mock import MagicMock, patch

import pytest

from warm_logic.kernel.substrate.attestation import CrossNodeAttestation


@pytest.fixture
def mock_tower_response():
    return {
        "ok": True,
        "result": {
            "silicon_id": "EXAMPLE0-0000-0000-0000-000000000000:EXAMPLE001",
            "signature": "MOCKED_PQC_SIG_valid",
            "nonce": "MOCKED_NONCE",
        },
    }


@patch("urllib.request.urlopen")
@patch("warm_logic.kernel.substrate.attestation.warm_logic_rs.MLDSA.verify")
@patch("warm_logic.kernel.substrate.attestation.RUST_CORE_AVAILABLE", True)
def test_attestation_success(mock_verify, mock_urlopen, mock_tower_response):
    # Setup
    mock_verify.return_value = True
    context = MagicMock()
    context.__enter__.return_value.read.return_value = json.dumps(
        mock_tower_response
    ).encode()
    mock_urlopen.return_value = context

    attestor = CrossNodeAttestation(target_ip="100.116.80.23")
    attestor.known_tower_id = "EXAMPLE0-0000-0000-0000-000000000000:EXAMPLE001"
    attestor.known_tower_pubkey = "MOCKED_PUBKEY"

    # Execute
    res = attestor.challenge_tower()

    # Assert
    assert res is True
    # Verify that warm_logic_rs.MLDSA.verify was called (indicating PQC check)
    assert mock_verify.called


@patch("urllib.request.urlopen")
def test_attestation_id_mismatch(mock_urlopen, mock_tower_response):
    # Setup
    mock_tower_response["result"]["silicon_id"] = "ATTACKER_SILICON_ID"
    context = MagicMock()
    context.__enter__.return_value.read.return_value = json.dumps(
        mock_tower_response
    ).encode()
    mock_urlopen.return_value = context

    attestor = CrossNodeAttestation(target_ip="100.116.80.23")
    attestor.known_tower_id = "EXAMPLE0-0000-0000-0000-000000000000:EXAMPLE001"

    # Execute
    res = attestor.challenge_tower()

    # Assert
    assert res is False


@patch("urllib.request.urlopen")
@patch("warm_logic.kernel.substrate.attestation.warm_logic_rs.MLDSA.verify")
@patch("warm_logic.kernel.substrate.attestation.RUST_CORE_AVAILABLE", True)
def test_attestation_signature_failure(mock_verify, mock_urlopen, mock_tower_response):
    # Setup
    mock_verify.return_value = False  # Signature invalid
    context = MagicMock()
    context.__enter__.return_value.read.return_value = json.dumps(
        mock_tower_response
    ).encode()
    mock_urlopen.return_value = context

    attestor = CrossNodeAttestation(target_ip="100.116.80.23")
    attestor.known_tower_id = "EXAMPLE0-0000-0000-0000-000000000000:EXAMPLE001"
    attestor.known_tower_pubkey = "MOCKED_PUBKEY"

    # Execute
    res = attestor.challenge_tower()

    # Assert
    assert res is False
