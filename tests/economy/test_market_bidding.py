import time

from warm_logic.economy.market import Bid, ComputeMarket, JobSpec
from warm_logic.economy.token import TokenLedger


def test_market_flow():
    ledger = TokenLedger()
    market = ComputeMarket(ledger)

    # Setup: Requester has 100 ST
    ledger.mint("CLIENT_A", 100.0)

    # 1. Post Job
    job = JobSpec(
        job_id="JOB-123",
        requester_id="CLIENT_A",
        compute_type="LLM",
        complexity=100,
        max_price=50.0,
        deadline=time.time() + 3600,
    )
    assert market.post_job(job) is True

    # 2. Bidding War
    bid1 = Bid(
        "BID-1", "WORKER_X", "JOB-123", price=40.0, eta=10, reputation_score=0.9
    )  # Cheap
    bid2 = Bid(
        "BID-2", "WORKER_Y", "JOB-123", price=45.0, eta=5, reputation_score=0.95
    )  # Fast but exp

    market.submit_bid(bid1)
    market.submit_bid(bid2)

    # 3. Match (Should pick Lowest Price -> Worker X)
    winner = market.match_job("JOB-123")
    assert winner.worker_id == "WORKER_X"
    assert winner.price == 40.0

    # Verify State: Job Closed, Escrow Locked
    assert "JOB-123" not in market.open_jobs
    assert market.escrow["JOB-123"] == 40.0

    # Verify Ledger: Client balance decreased
    assert ledger.get_balance("CLIENT_A") == 60.0  # 100 - 40
    assert ledger.get_balance("ESCROW_POOL") == 40.0

    # 4. Completion & Payout
    assert market.complete_job("JOB-123", "WORKER_X", "PROOF_SHA256") is True

    # Verify Final Ledger
    assert ledger.get_balance("WORKER_X") == 40.0
    assert ledger.get_balance("ESCROW_POOL") == 0.0


def test_insufficient_funds_post():
    ledger = TokenLedger()
    market = ComputeMarket(ledger)
    # Client has 0

    job = JobSpec("J1", "POOR_CLIENT", "AI", 10, 50.0, 0)
    assert market.post_job(job) is False
