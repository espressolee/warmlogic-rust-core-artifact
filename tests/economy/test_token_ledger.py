import pytest

from warm_logic.economy.token import TokenLedger


def test_ledger_initialization():
    ledger = TokenLedger()
    assert ledger.get_balance("KERNEL_ROOT") == 1_000_000_000.0
    assert ledger.get_balance("USER_X") == 0.0


def test_minting():
    ledger = TokenLedger()

    # Mint 100 tokens
    success = ledger.mint("NODE_A", 100.0, proof="UPTIME_REWARD")
    assert success is True
    assert ledger.get_balance("NODE_A") == 100.0

    # Verify Transaction Log
    assert len(ledger._history) == 1
    assert ledger._history[0].receiver_id == "NODE_A"
    assert ledger._history[0].memo == "Proof: UPTIME_REWARD"


def test_transfer_success():
    ledger = TokenLedger()
    ledger.mint("NODE_A", 50.0)

    # Valid Transfer
    result = ledger.transfer("NODE_A", "NODE_B", 20.0)
    assert result is True
    assert ledger.get_balance("NODE_A") == 30.0
    assert ledger.get_balance("NODE_B") == 20.0


def test_transfer_insufficient_funds():
    ledger = TokenLedger()
    ledger.mint("NODE_A", 10.0)

    # Overdraft
    result = ledger.transfer("NODE_A", "NODE_B", 50.0)
    assert result is False
    assert ledger.get_balance("NODE_A") == 10.0
    assert ledger.get_balance("NODE_B") == 0.0


def test_negative_mint_transfer():
    ledger = TokenLedger()

    assert ledger.mint("NODE_A", -10.0) is False
    ledger.mint("NODE_A", 100.0)
    assert ledger.transfer("NODE_A", "NODE_B", -50.0) is False
