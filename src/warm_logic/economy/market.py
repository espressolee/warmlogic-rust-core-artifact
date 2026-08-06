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
from dataclasses import dataclass
from typing import Dict, List, Optional

from warm_logic.economy.token import TokenLedger


@dataclass
class JobSpec:
    """Description of work required."""

    job_id: str
    requester_id: str
    compute_type: str  # e.g., "LLM_INFERENCE", "ZK_PROOF"
    complexity: float  # Estimated operations
    max_price: float  # Max tokens willing to pay
    deadline: float


@dataclass
class Bid:
    """Offer from a worker node."""

    bid_id: str
    worker_id: str
    job_id: str
    price: float
    eta: float
    reputation_score: float


class ComputeMarket:
    """
    Matches Job Requests (RFQs) with Worker Bids.
    Manages Escrow during execution.
    """

    def __init__(self, ledger: TokenLedger):
        self.ledger = ledger
        self.open_jobs: Dict[str, JobSpec] = {}
        self.bids: Dict[str, List[Bid]] = {}  # job_id -> list[Bid]
        self.escrow: Dict[str, float] = {}  # job_id -> locked_amount

    def post_job(self, job: JobSpec) -> bool:
        """
        Requester posts a job. Check if they have enough funds for max_price.
        """
        if self.ledger.get_balance(job.requester_id) < job.max_price:
            return False

        self.open_jobs[job.job_id] = job
        self.bids[job.job_id] = []
        return True

    def submit_bid(self, bid: Bid) -> bool:
        """
        Worker submits a bid.
        """
        if bid.job_id not in self.open_jobs:
            return False

        job = self.open_jobs[bid.job_id]
        if bid.price > job.max_price:
            return False

        self.bids[bid.job_id].append(bid)
        return True

    def match_job(self, job_id: str) -> Optional[Bid]:
        """
        Select the best bid for a job (Simple logic: Lowest Price).
        Locks funds in Escrow.
        """
        if job_id not in self.open_jobs or not self.bids.get(job_id):
            return None

        # Strategy: Lowest Price, tie-break by ETA
        candidates = sorted(self.bids[job_id], key=lambda x: (x.price, x.eta))
        best_bid = candidates[0]
        job = self.open_jobs[job_id]

        # Lock Funds (Atomic)
        # 1. Transfer from Requester to ESCROW_POOL
        if self.ledger.transfer(job.requester_id, "ESCROW_POOL", best_bid.price):
            self.escrow[job_id] = best_bid.price
            del self.open_jobs[job_id]  # Close market for this job
            return best_bid

        return None

    def complete_job(self, job_id: str, worker_id: str, proof: str) -> bool:
        """
        Worker finishes job. Release funds from Escrow.
        """
        if job_id not in self.escrow:
            return False

        amount = self.escrow[job_id]

        # Currently, we would verify the Proof here.

        # Transfer from ESCROW_POOL to Worker
        if self.ledger.transfer("ESCROW_POOL", worker_id, amount):
            del self.escrow[job_id]
            return True

        return False
