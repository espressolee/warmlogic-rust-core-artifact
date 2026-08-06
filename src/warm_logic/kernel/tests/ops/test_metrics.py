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
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from warm_logic.kernel.ops.metrics import (
    PatchEfficiencyReport,
    SystemMetrics,
    _estimate_human_minutes,
    _is_ci_related,
    _origin_from_entry,
    _parse_ts,
    _status_bucket,
    build_patch_efficiency_report,
    load_patch_efficiency,
)


class TestMetricsUtils(unittest.TestCase):
    def test_parse_ts(self):
        # 1. datetime object
        dt = datetime(2023, 1, 1, 12, 0, 0)
        self.assertEqual(_parse_ts(dt), dt.astimezone(timezone.utc))

        # 2. Int/Float timestamp
        ts = 1672531200.0  # 2023-01-01
        self.assertEqual(_parse_ts(ts), datetime.fromtimestamp(ts, tz=timezone.utc))
        self.assertEqual(
            _parse_ts(int(ts)), datetime.fromtimestamp(ts, tz=timezone.utc)
        )

        # 3. String ISO
        iso = "2023-01-01T12:00:00+00:00"
        self.assertEqual(_parse_ts(iso), datetime.fromisoformat(iso))

        # 4. String with Z
        z_iso = "2023-01-01T12:00:00Z"
        self.assertEqual(
            _parse_ts(z_iso), datetime.fromisoformat("2023-01-01T12:00:00+00:00")
        )

        # 5. Invalid
        self.assertIsNone(_parse_ts("invalid"))
        self.assertIsNone(_parse_ts(None))
        self.assertIsNone(_parse_ts([]))

        # 6. Overflow (Exception coverage for lines 39-40)
        self.assertIsNone(_parse_ts(1e50))  # Too large for platform datetime

    def test_status_bucket(self):
        self.assertEqual(_status_bucket("applied"), "success")
        self.assertEqual(_status_bucket("manual_applied"), "success")
        self.assertEqual(_status_bucket("ok"), "success")

        self.assertEqual(_status_bucket("rollback"), "rollback")
        self.assertEqual(_status_bucket("rolled_back"), "rollback")

        self.assertEqual(_status_bucket("failed"), "failed")
        self.assertEqual(_status_bucket("timeout"), "failed")
        self.assertEqual(_status_bucket(None), "failed")

    def test_origin_from_entry(self):
        # 1. Direct origin
        self.assertEqual(_origin_from_entry({"origin": "human"}), "human")

        # 2. Meta origin
        self.assertEqual(_origin_from_entry({"meta": {"origin": "agent"}}), "agent")

        # 3. Meta source (fallback)
        self.assertEqual(_origin_from_entry({"meta": {"source": "system"}}), "system")

        # 4. Fallback sequence
        self.assertEqual(
            _origin_from_entry({"meta": {}, "origin": "fallback"}), "fallback"
        )

        # 5. Unknown
        self.assertEqual(_origin_from_entry({}), "unknown")
        self.assertEqual(_origin_from_entry({"meta": "not_dict"}), "unknown")

    def test_is_ci_related(self):
        # 1. Direct markers
        self.assertTrue(_is_ci_related({"reason": "ci failed"}))
        self.assertTrue(_is_ci_related({"status": "test failed"}))
        self.assertTrue(_is_ci_related({"tests_failing": True}))

        # 2. Detail dict markers
        self.assertTrue(_is_ci_related({"detail": {"error": "build error"}}))
        self.assertTrue(_is_ci_related({"detail": {"ci_failure": True}}))

        self.assertTrue(_is_ci_related({"detail": {"stderr": ["flake detected"]}}))
        # Multi-item list including non-string to cover loop skip (Branch 100->99)
        self.assertTrue(
            _is_ci_related({"detail": {"stderr": ["item1", 123, "build failure"]}})
        )

        # 4. Negative cases
        self.assertFalse(_is_ci_related({"reason": "logic error"}))
        self.assertFalse(
            _is_ci_related({"detail": "not dict"})
        )  # Covers branches 93->104 and 128->136 checking logic
        self.assertFalse(_is_ci_related({"detail": ["list"]}))

    def test_estimate_human_minutes(self):
        # 1. Manual origin
        self.assertEqual(_estimate_human_minutes({"origin": "manual"}), 6.0)

        # 2. Human in loop flag
        self.assertEqual(_estimate_human_minutes({"human_in_loop": True}), 5.0)
        self.assertEqual(
            _estimate_human_minutes({"meta": {"human_in_loop": True}}), 5.0
        )

        # 3. Review markers in reason
        self.assertEqual(
            _estimate_human_minutes({"reason": "human review needed"}), 5.0
        )

        # 4. Detail explicit minutes
        self.assertEqual(
            _estimate_human_minutes(
                {"detail": {"manual_review": True, "human_minutes": 10}}
            ),
            10.0,
        )

        # 5. Detail reason marker
        self.assertEqual(
            _estimate_human_minutes({"detail": {"reason": "protected file"}}), 5.0
        )

        # 6. Accumulation
        # Manual origin (6) + Human in loop (5) = 11
        self.assertEqual(
            _estimate_human_minutes({"origin": "manual", "human_in_loop": True}), 11.0
        )

    def test_build_patch_efficiency_report(self):
        records = [
            {
                "status": "applied",
                "origin": "agent",
                "ts": "2023-01-01T10:00:00Z",
                "id": "task1",
            },
            {
                "status": "rollback",
                "origin": "agent",
                "ts": "2023-01-01T11:00:00Z",
                "id": "task1",
            },
            {
                "status": "failed",
                "origin": "human",
                "reason": "ci failure",
                "ts": "2023-01-01T12:00:00Z",
                "id": "fix_ci",
            },
            {
                "status": "applied",
                "origin": "human",
                "ts": "2023-01-01T13:00:00Z",
                "id": "fix_ci",
                "pattern": "fix_ci",
            },
            # Previous was failure, this success -> fix time calculation
            # But failure didn't have pattern 'fix_ci' unless we add it
            # Non-CI failure (Cover line 191)
            {
                "status": "failed",
                "reason": "logic error",
                "origin": "manual",
                "ts": "2023-01-01T14:00:00Z",
                "id": "logic_fail",
            },
        ]

        # Re-structure for CI fix stats test
        records[2]["pattern"] = "fix_ci"

        report = build_patch_efficiency_report(records)

        self.assertIsInstance(report, PatchEfficiencyReport)
        self.assertEqual(report.sample_size, 5)

        # Success rates: Agent 1/2 (0.5), Human 1/2 (0.5)
        self.assertEqual(report.success_rate_by_source["agent"], 0.5)
        self.assertEqual(report.success_rate_by_source["human"], 0.5)

        # Rollback rate: 1 rollback / (2 success + 1 rollback) = 1/3 = 0.333
        self.assertAlmostEqual(report.rollback_rate, 0.333, places=3)

        # CI Fix stats
        # Failure at 12:00, Success at 13:00 -> 60 minutes
        self.assertEqual(report.ci_fix_stats["average_minutes"], 60.0)

    def test_load_patch_efficiency(self):
        json_lines = """
        {"status": "applied", "origin": "agent"}
        {"status": "failed"}
        malformed_json
        """
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=json_lines),
        ):
            data = load_patch_efficiency(Path("dummy"), limit=10)
            self.assertEqual(data["sample_size"], 2)  # Malformed line skipped

        # Non-dict JSON case (Cover branch 63->58)
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value='[1, 2]\n{"status": "ok"}'),
        ):
            data = load_patch_efficiency(Path("dummy"))
            self.assertEqual(data["sample_size"], 1)  # List line skipped

        # Missing file case
        with patch("pathlib.Path.exists", return_value=False):
            data = load_patch_efficiency(Path("missing"))
            self.assertEqual(data["sample_size"], 0)

        # Read error case
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", side_effect=Exception("Read fail")),
        ):
            data = load_patch_efficiency(Path("error"))
            self.assertEqual(data["sample_size"], 0)

    def test_system_metrics(self):
        sm = SystemMetrics()
        self.assertTrue(sm.is_critical())

        sm.drift_score = 0.9
        self.assertTrue(sm.is_critical())

        sm.drift_score = 0.0
        sm.governance_health = 0.4
        self.assertTrue(sm.is_critical())

        sm.governance_health = 1.0
        sm.network_stability = 0.4
        self.assertTrue(sm.is_critical())

    def test_ingest_batch(self):
        sm = SystemMetrics()
        records = [
            {"status": "applied", "origin": "agent", "ts": "2023-01-01T10:00:00Z"},
            {"status": "failed", "origin": "system", "ts": "2023-01-01T11:00:00Z"},
        ]
        report = sm.ingest_batch(records)
        self.assertIsInstance(report, PatchEfficiencyReport)
        self.assertEqual(report.sample_size, 2)
        self.assertEqual(report.success_rate_by_source["agent"], 1.0)

    def test_ingest_with_invalid_ts(self):
        # Case covering "if ts is None: continue" in _compute_ci_fix_stats
        sm = SystemMetrics()
        records = [
            {"status": "applied", "origin": "agent", "ts": "invalid-date"},
        ]
        report = sm.ingest_batch(records)
        self.assertEqual(report.sample_size, 1)
        # CI stats sample size should be 0 because ts is invalid
        self.assertEqual(report.ci_fix_stats["sample_size"], 0)

    def test_ingest_batch_non_ci_failure(self):
        # Case covering "if not _is_ci_related(entry): continue" (Line 192)
        sm = SystemMetrics()
        records = [
            # Failed but not CI related (e.g. logic error)
            {
                "status": "failed",
                "origin": "manual",
                "reason": "logic error",
                "ts": "2023-01-01T12:00:00Z",
            }
        ]
        report = sm.ingest_batch(records)
        self.assertEqual(report.sample_size, 1)
        # Should be skipped in CI stats
        self.assertEqual(report.ci_fix_stats["sample_size"], 0)

    def test_ingest_no_id(self):
        # Case covering "if not pattern: continue" (Line 178)
        sm = SystemMetrics()
        records = [
            # Valid TS but no ID/Pattern
            {"status": "applied", "origin": "agent", "ts": "2023-01-01T12:00:00Z"},
        ]
        report = sm.ingest_batch(records)
        self.assertEqual(report.sample_size, 1)
        # Should be skipped in CI stats (sample size 0)
        self.assertEqual(report.ci_fix_stats["sample_size"], 0)

    def test_ingest_consecutive_failures(self):
        # Case covering "if pattern not in first_failure:" (Line 195 -> False -> 173)
        # Occurs when we have multiple failures before a fix.
        sm = SystemMetrics()
        records = [
            {
                "status": "failed",
                "reason": "ci failure",
                "ts": "2023-01-01T10:00:00Z",
                "id": "task1",
            },
            {
                "status": "failed",
                "reason": "ci failure",
                "ts": "2023-01-01T10:05:00Z",
                "id": "task1",
            },
            {"status": "applied", "ts": "2023-01-01T10:10:00Z", "id": "task1"},
        ]
        report = sm.ingest_batch(records)
        # Should only record ONE fix duration (from first failure to fix)
        # 10:10 - 10:00 = 10 minutes
        self.assertEqual(report.ci_fix_stats["sample_size"], 1)
        self.assertEqual(report.ci_fix_stats["average_minutes"], 10.0)


if __name__ == "__main__":
    unittest.main()
