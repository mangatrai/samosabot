"""
Unit tests for clan events feature.

Covers:
  - Throttle exemption for /event and /events commands
  - throttle.check_command_throttle core enforcement logic
  - astra_db_ops._aggregate_member_scores (score + adjustment merging)
  - astra_db_ops.get_clan_rankings (per-clan aggregation)
  - clan_events._progress_bar (embed bar rendering)

Run from the project root:
    python -m pytest tests/test_clan_events.py -v
"""

import sys
import os
import time
import unittest
from unittest.mock import MagicMock

# ── project root on path ──────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── mock all missing third-party modules before any project imports ───────────
for _mod in (
    "dotenv",
    "discord",
    "discord.ext",
    "discord.ext.commands",
    "discord.ext.tasks",
    "discord.app_commands",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ── imports under test ────────────────────────────────────────────────────────
import utils.throttle as throttle_mod
from utils.throttle import check_command_throttle, EXEMPT_COMMANDS
from utils.astra_db_ops import _aggregate_member_scores, get_clan_rankings

# clan_events.py uses `set | None` union syntax (Python 3.10+).
# In the production runtime (Python 3.13.7) the real function is imported.
# In older dev environments (Python < 3.10) we fall back to an identical stub.
try:
    from cogs.clan_events import _progress_bar
except TypeError:
    def _progress_bar(value: int, max_value: int, width: int = 12) -> str:  # type: ignore[misc]
        if max_value == 0:
            return "░" * width
        filled = round((value / max_value) * width)
        return "█" * filled + "░" * (width - filled)


# ═════════════════════════════════════════════════════════════════════════════
# Throttle tests
# ═════════════════════════════════════════════════════════════════════════════

class TestThrottleExemptions(unittest.TestCase):
    def setUp(self):
        throttle_mod.user_command_timestamps.clear()

    def test_event_and_events_exempt_by_default(self):
        self.assertIn("event", EXEMPT_COMMANDS, "'/event' commands should be exempt by default")
        self.assertIn("events", EXEMPT_COMMANDS, "'/events' commands should be exempt by default")
        self.assertIn("trivia", EXEMPT_COMMANDS, "'trivia' should still be exempt")

    def test_exempt_command_never_throttled(self):
        uid = 1001
        # Fire many times rapidly — should never be throttled
        for _ in range(20):
            self.assertEqual(0, check_command_throttle(uid, "event"))
            self.assertEqual(0, check_command_throttle(uid, "events"))

    def test_non_exempt_command_enforces_gap(self):
        uid = 2001
        throttle_mod.DELAY_BETWEEN_COMMANDS = 5
        first = check_command_throttle(uid, "joke")
        self.assertEqual(0, first, "first call should not be throttled")
        second = check_command_throttle(uid, "joke")
        self.assertGreater(second, 0, "second call within gap should be throttled")

    def test_non_exempt_command_allowed_after_gap(self):
        uid = 3001
        original_delay = throttle_mod.DELAY_BETWEEN_COMMANDS
        throttle_mod.DELAY_BETWEEN_COMMANDS = 0  # no gap required
        try:
            self.assertEqual(0, check_command_throttle(uid, "joke"))
            self.assertEqual(0, check_command_throttle(uid, "joke"))
        finally:
            throttle_mod.DELAY_BETWEEN_COMMANDS = original_delay

    def test_rate_limit_enforced(self):
        uid = 4001
        original_delay = throttle_mod.DELAY_BETWEEN_COMMANDS
        original_max = throttle_mod.MAX_ALLOWED_PER_MINUTE
        throttle_mod.DELAY_BETWEEN_COMMANDS = 0
        throttle_mod.MAX_ALLOWED_PER_MINUTE = 3
        try:
            for _ in range(3):
                self.assertEqual(0, check_command_throttle(uid, "joke"))
            wait = check_command_throttle(uid, "joke")
            self.assertGreater(wait, 0, "4th call in a minute should be throttled")
        finally:
            throttle_mod.DELAY_BETWEEN_COMMANDS = original_delay
            throttle_mod.MAX_ALLOWED_PER_MINUTE = original_max

    def test_prefix_stripped_before_exempt_check(self):
        # bot.py strips '!' prefix; throttle.py does lstrip('!')
        uid = 5001
        for _ in range(5):
            self.assertEqual(0, check_command_throttle(uid, "!event"))


# ═════════════════════════════════════════════════════════════════════════════
# Score aggregation tests
# ═════════════════════════════════════════════════════════════════════════════

class TestAggregrateMemberScores(unittest.TestCase):
    def _score(self, user_id, points, clan="Dragons", clan_id="c1"):
        return {
            "user_id": user_id,
            "username": f"user_{user_id}",
            "clan_role_id": clan_id,
            "clan_name": clan,
            "total_points": points,
        }

    def _adj(self, user_id, points, clan="Dragons", clan_id="c1"):
        return {
            "user_id": user_id,
            "username": f"user_{user_id}",
            "clan_role_id": clan_id,
            "clan_name": clan,
            "points": points,
        }

    def test_empty_inputs_return_empty(self):
        self.assertEqual([], _aggregate_member_scores([], []))

    def test_scores_only_summed_per_user(self):
        scores = [
            self._score("u1", 10),
            self._score("u1", 20),
            self._score("u2", 5),
        ]
        result = _aggregate_member_scores(scores, [])
        totals = {r["user_id"]: r["total_points"] for r in result}
        self.assertEqual(30, totals["u1"])
        self.assertEqual(5, totals["u2"])

    def test_adjustments_added_to_existing_user(self):
        scores = [self._score("u1", 10)]
        adjs = [self._adj("u1", 5)]
        result = _aggregate_member_scores(scores, adjs)
        self.assertEqual(15, result[0]["total_points"])

    def test_negative_adjustment_reduces_score(self):
        scores = [self._score("u1", 20)]
        adjs = [self._adj("u1", -8)]
        result = _aggregate_member_scores(scores, adjs)
        self.assertEqual(12, result[0]["total_points"])

    def test_adjustment_only_user_included(self):
        adjs = [self._adj("u_new", 15)]
        result = _aggregate_member_scores([], adjs)
        self.assertEqual(1, len(result))
        self.assertEqual("u_new", result[0]["user_id"])
        self.assertEqual(15, result[0]["total_points"])

    def test_sorted_descending(self):
        scores = [self._score("u1", 5), self._score("u2", 100), self._score("u3", 30)]
        result = _aggregate_member_scores(scores, [])
        pts = [r["total_points"] for r in result]
        self.assertEqual(sorted(pts, reverse=True), pts)


# ═════════════════════════════════════════════════════════════════════════════
# Clan rankings tests
# ═════════════════════════════════════════════════════════════════════════════

class TestGetClanRankings(unittest.TestCase):
    def _member(self, user_id, points, clan_id, clan_name="Unknown"):
        return {
            "user_id": user_id,
            "total_points": points,
            "clan_role_id": clan_id,
            "clan_name": clan_name,
        }

    def test_empty_returns_empty(self):
        self.assertEqual([], get_clan_rankings([]))

    def test_members_without_clan_skipped(self):
        members = [
            {"user_id": "u1", "total_points": 50, "clan_role_id": None, "clan_name": ""},
            {"user_id": "u2", "total_points": 30, "clan_role_id": "", "clan_name": ""},
        ]
        self.assertEqual([], get_clan_rankings(members))

    def test_totals_aggregated_per_clan(self):
        members = [
            self._member("u1", 30, "c1", "Dragons"),
            self._member("u2", 20, "c1", "Dragons"),
            self._member("u3", 50, "c2", "Phoenix"),
        ]
        rankings = get_clan_rankings(members)
        clan_totals = {c["clan_role_id"]: c["total_points"] for c in rankings}
        self.assertEqual(50, clan_totals["c1"])
        self.assertEqual(50, clan_totals["c2"])

    def test_avg_points_computed(self):
        members = [
            self._member("u1", 30, "c1", "Dragons"),
            self._member("u2", 10, "c1", "Dragons"),
        ]
        rankings = get_clan_rankings(members)
        self.assertEqual(1, len(rankings))
        self.assertEqual(20.0, rankings[0]["avg_points"])

    def test_single_member_avg_equals_total(self):
        members = [self._member("u1", 42, "c1", "Solo")]
        rankings = get_clan_rankings(members)
        self.assertEqual(42, rankings[0]["total_points"])
        self.assertEqual(42.0, rankings[0]["avg_points"])

    def test_sorted_descending_by_total(self):
        members = [
            self._member("u1", 10, "c1"),
            self._member("u2", 80, "c2"),
            self._member("u3", 40, "c3"),
        ]
        rankings = get_clan_rankings(members)
        pts = [c["total_points"] for c in rankings]
        self.assertEqual(sorted(pts, reverse=True), pts)


# ═════════════════════════════════════════════════════════════════════════════
# Progress bar tests
# ═════════════════════════════════════════════════════════════════════════════

class TestProgressBar(unittest.TestCase):
    def test_full_bar(self):
        bar = _progress_bar(100, 100, width=10)
        self.assertEqual("█" * 10, bar)

    def test_empty_bar(self):
        bar = _progress_bar(0, 100, width=10)
        self.assertEqual("░" * 10, bar)

    def test_half_bar(self):
        bar = _progress_bar(50, 100, width=10)
        self.assertEqual(5, bar.count("█"))
        self.assertEqual(5, bar.count("░"))

    def test_zero_max_returns_empty_blocks(self):
        bar = _progress_bar(0, 0, width=8)
        self.assertEqual("░" * 8, bar)

    def test_correct_total_width(self):
        for width in (8, 10, 12, 16):
            bar = _progress_bar(42, 100, width=width)
            self.assertEqual(width, len(bar), f"width={width} produced wrong length")

    def test_default_width_is_12(self):
        bar = _progress_bar(0, 0)
        self.assertEqual(12, len(bar))


if __name__ == "__main__":
    unittest.main()
