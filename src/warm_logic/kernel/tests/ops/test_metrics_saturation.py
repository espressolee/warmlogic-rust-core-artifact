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
import os
import platform
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from warm_logic.kernel.ops.metrics import (
    PatchEfficiencyReport,
    SystemMetrics,
    _compute_ci_fix_stats,
    _compute_rollback_rate,
    _estimate_human_minutes,
    _is_ci_related,
    _load_lines,
    _parse_ts,
    _status_bucket,
    load_patch_efficiency,
)


class TestMetricsSaturation(unittest.TestCase):
    def test_parse_ts_saturated(self):
        # Line 49: already datetime
        dt = datetime.now()
        self.assertEqual(_parse_ts(dt).tzinfo, timezone.utc)
        self.assertIsNone(_parse_ts("garbage"))

    def test_load_lines_saturated(self):
        # Success load hits 68-82
        p = Path("sat_test.jsonl")
        p.write_text('{"a": 1}\n{"b": 2}', encoding="utf-8")
        try:
            self.assertEqual(len(_load_lines(p, 10)), 2)
        finally:
            if p.exists():
                p.unlink()
        self.assertEqual(_load_lines(Path("none"), 10), [])

    def test_status_bucket_saturated(self):
        self.assertEqual(_status_bucket("rollback"), "rollback")
        self.assertEqual(_status_bucket("applied"), "success")

    def test_is_ci_related_saturated(self):
        self.assertTrue(_is_ci_related({"tests_failing": True}))
        self.assertTrue(_is_ci_related({"detail": {"ci_failure": True}}))

    def test_estimate_human_saturated(self):
        # Line 147
        entry = {"detail": {"manual_review": True, "human_minutes": 15}}
        self.assertEqual(_estimate_human_minutes(entry), 15.0)
        # Line 152
        entry2 = {"detail": {"reason": "manual review marker"}}
        self.assertEqual(
            _estimate_human_minutes(entry2),
            float(os.environ.get("PATCH_REVIEW_MINUTES", 5)),
        )

    def test_ci_fix_stats_saturated(self):
        base = datetime.now(timezone.utc)
        records = [
            {
                "pattern": "P1",
                "ts": base.timestamp(),
                "status": "failed",
                "reason": "ci",
            },
            {"ts": "bad"},  # Line 206
            {
                "pattern": "P1",
                "ts": (base + timedelta(minutes=1)).timestamp(),
                "status": "other",
                "reason": "non-ci",
            },  # Line 209
            {
                "pattern": "P1",
                "ts": (base + timedelta(minutes=10)).timestamp(),
                "status": "applied",
            },
        ]
        stats = _compute_ci_fix_stats(records)
        self.assertEqual(stats["sample_size"], 1)

    def test_rollback_rate_saturated(self):
        self.assertEqual(_compute_rollback_rate([]), 0.0)
        # Line 234
        self.assertEqual(
            _compute_rollback_rate([{"status": "applied"}, {"status": "rollback"}]), 0.5
        )

    def test_system_metrics_saturated(self):
        sm = SystemMetrics()
        # Line 316
        sm._trend_buffer = [
            {"drift_score": 0.5, "timestamp": 1.0},
            {"drift_score": 0.6, "timestamp": 1.0},
        ]
        self.assertEqual(sm.get_derivative("drift_score"), 0.0)

        # Line 322/342
        self.assertGreater(sm.uptime, 0.0)
        self.assertIn("uptime", sm.get_snapshot())

        # Line 351
        sm.drift_score = 0.9
        self.assertTrue(sm.is_critical())

        # Hardware ID
        with mock.patch(
            "warm_logic.kernel.identity.kinetic_id.KineticIdentity.get_node_id",
            create=True,
            side_effect=Exception("f"),
        ):
            self.assertIn(platform.system().upper(), sm.hardware_id)

    def test_report_saturated(self):
        # Line 165/171
        rep = PatchEfficiencyReport({}, 0.0, 0.0, {}, 0)
        self.assertEqual(rep.to_dict()["sample_size"], 0)

    def test_load_wrapper_saturated(self):
        # Line 265-267
        p = Path("sat_test2.jsonl")
        p.write_text('{"status": "applied"}')
        try:
            res = load_patch_efficiency(p)
            self.assertEqual(res["sample_size"], 1)
        finally:
            if p.exists():
                p.unlink()


if __name__ == "__main__":
    unittest.main()
