"""
Tests for the companion summoning EV recommendation:
  - Constants sanity (rates sum to 1, ticket cost matches user spec)
  - Recursive EV math at each tier
  - Cascading promotion handling (extras of maxed comp → tier-above value)
  - Edge cases (empty collection, all-maxed)
  - Optimizer-wrapper shape contract
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.companions import COMPANIONS, JobAdvancement, MAX_LEVELS
from game.companion_summoning import (
    DIAMONDS_PER_TICKET,
    TIER_RATES,
    PROMOTION_RATES,
    LEVEL_UP_COSTS,
    companions_in_tier,
    calculate_ev_per_pull_at_tier,
    calculate_expected_value_per_ticket,
    get_companion_ticket_recommendation_for_optimizer,
)


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------

class TestConstants:
    def test_tier_rates_sum_to_one(self):
        # User-provided odds: 75.21 + 22 + 2.5 + 0.25 + 0.04 = 100.00
        self.assert_close(sum(TIER_RATES.values()), 1.0)

    def test_ticket_cost_matches_30000_for_850(self):
        # User-confirmed: 30,000 diamonds → 850 tickets
        expected = 30_000 / 850
        self.assert_close(DIAMONDS_PER_TICKET, expected)

    def test_promotion_rates_exist_for_all_tiers_except_fourth(self):
        # Can't promote past FOURTH.
        self.assertIn(JobAdvancement.BASIC, PROMOTION_RATES)
        self.assertIn(JobAdvancement.FIRST, PROMOTION_RATES)
        self.assertIn(JobAdvancement.SECOND, PROMOTION_RATES)
        self.assertIn(JobAdvancement.THIRD, PROMOTION_RATES)
        assert JobAdvancement.FOURTH not in PROMOTION_RATES

    def test_promotion_rate_values(self):
        # User-provided: 100/50/30/20
        assert PROMOTION_RATES[JobAdvancement.BASIC] == 1.00
        assert PROMOTION_RATES[JobAdvancement.FIRST] == 0.50
        assert PROMOTION_RATES[JobAdvancement.SECOND] == 0.30
        assert PROMOTION_RATES[JobAdvancement.THIRD] == 0.20

    def test_level_up_costs_populated_for_each_tier(self):
        for tier in (JobAdvancement.BASIC, JobAdvancement.FIRST, JobAdvancement.SECOND,
                     JobAdvancement.THIRD, JobAdvancement.FOURTH):
            assert tier in LEVEL_UP_COSTS
            # Every tier should have at least cost for level 1.
            assert 1 in LEVEL_UP_COSTS[tier]
            assert LEVEL_UP_COSTS[tier][1] > 0

    def test_level_up_costs_capped_at_max_level(self):
        # cost-to-advance is 0 at the tier's max level (no further levels exist).
        for tier in (JobAdvancement.BASIC, JobAdvancement.FIRST, JobAdvancement.SECOND,
                     JobAdvancement.THIRD, JobAdvancement.FOURTH):
            max_lvl = MAX_LEVELS[tier]
            assert LEVEL_UP_COSTS[tier].get(max_lvl, 0) == 0

    # Helpers — pytest-friendly assertion shorthand
    @staticmethod
    def assert_close(a, b, tol=1e-9):
        assert abs(a - b) < tol, f"{a} != {b} (tol={tol})"

    @staticmethod
    def assertIn(item, container):
        assert item in container, f"{item!r} not in {container!r}"


# ---------------------------------------------------------------------------
# companions_in_tier sanity
# ---------------------------------------------------------------------------

class TestCompanionsInTier:
    def test_returns_only_companions_of_that_tier(self):
        # Bishop 4th must show up in the FOURTH tier list (we wired its kit
        # in the previous task) and NOT in any other tier.
        fourth = companions_in_tier(JobAdvancement.FOURTH)
        assert "bishop_4th" in fourth
        for other in (JobAdvancement.BASIC, JobAdvancement.FIRST,
                      JobAdvancement.SECOND, JobAdvancement.THIRD):
            assert "bishop_4th" not in companions_in_tier(other)

    def test_every_companion_in_exactly_one_tier(self):
        # Sanity: the union of all tier members equals all COMPANIONS,
        # and no companion is double-counted.
        all_members = set()
        for tier in (JobAdvancement.BASIC, JobAdvancement.FIRST,
                     JobAdvancement.SECOND, JobAdvancement.THIRD,
                     JobAdvancement.FOURTH):
            members = set(companions_in_tier(tier))
            assert not (members & all_members), \
                f"{tier} overlaps with previously-tiered companions"
            all_members.update(members)
        assert all_members == set(COMPANIONS.keys())


# ---------------------------------------------------------------------------
# EV solver math
# ---------------------------------------------------------------------------

def _const_gain_fn(per_companion_gain: float):
    """Returns a marginal_dps_fn that gives `per_companion_gain` for any
    override of any companion. Makes the EV math easy to verify by hand."""
    def fn(overrides):
        # Sum DPS = per_companion_gain per non-zero override level.
        return sum(per_companion_gain for v in overrides.values() if v > 0)
    return fn


class TestEVSolver:
    def test_fourth_tier_has_no_promotion_value(self):
        # FOURTH can't promote past itself; tier_ev_next should be 0.
        # With every 4th-job maxed and 0 promotion: EV at FOURTH = 0.
        max_4 = MAX_LEVELS[JobAdvancement.FOURTH]
        owned = {k: max_4 for k in companions_in_tier(JobAdvancement.FOURTH)}
        ev = calculate_ev_per_pull_at_tier(
            JobAdvancement.FOURTH,
            user_state={'owned': owned, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(100.0),
            tier_ev_next=0.0,
        )
        # All maxed AND no tier above → zero gain per pull at FOURTH.
        assert ev == 0.0

    def test_maxed_tier_just_returns_promotion_value(self):
        # Every 1st-job maxed → every pull rolls promotion at FIRST's rate.
        # EV at FIRST = PROMOTION_RATES[FIRST] × tier_ev_next.
        max_1 = MAX_LEVELS[JobAdvancement.FIRST]
        owned = {k: max_1 for k in companions_in_tier(JobAdvancement.FIRST)}
        tier_ev_next = 500.0
        ev = calculate_ev_per_pull_at_tier(
            JobAdvancement.FIRST,
            user_state={'owned': owned, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(100.0),
            tier_ev_next=tier_ev_next,
        )
        expected = PROMOTION_RATES[JobAdvancement.FIRST] * tier_ev_next
        assert abs(ev - expected) < 1e-9

    def test_no_owned_companions_is_avg_direct_gain(self):
        # Empty collection: every pull is a new companion at L1.
        # EV at each tier = average direct gain across companions = the
        # per-companion gain (since the mock returns a constant for every key).
        ev = calculate_ev_per_pull_at_tier(
            JobAdvancement.FOURTH,
            user_state={'owned': {}, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(42.0),
            tier_ev_next=0.0,
        )
        assert abs(ev - 42.0) < 1e-9

    def test_in_progress_uses_per_level_marginal_divided_by_cost(self):
        # Owned at L1, max=10 (4th-job). One pull = 1 progress unit.
        # cost(L1→L2) for FOURTH = LEVEL_UP_COSTS[FOURTH][1]. The marginal
        # we expect is (gain(L2) - gain(L1)) / cost(1).
        # Mock fn: gain ∝ level. So per_level_gain = const, per_pull = const / cost.
        fourth_keys = companions_in_tier(JobAdvancement.FOURTH)
        owned = {k: 1 for k in fourth_keys}   # all at L1
        per_level_step = 100.0

        def fn(overrides):
            # Linear in level: returns 100 × sum-of-levels.
            return per_level_step * sum(overrides.values())

        ev = calculate_ev_per_pull_at_tier(
            JobAdvancement.FOURTH,
            user_state={'owned': owned, 'equipped': []},
            marginal_dps_fn=fn,
            tier_ev_next=0.0,
        )
        cost_l1 = LEVEL_UP_COSTS[JobAdvancement.FOURTH][1]
        expected_per_pull = per_level_step / cost_l1
        # All companions identical → average == single-companion value
        assert abs(ev - expected_per_pull) < 1e-9

    def test_full_top_down_solve_aggregates_tier_evs(self):
        # No owned companions, constant per-companion gain: every tier's
        # EV = const, and the per-ticket EV = const × sum(TIER_RATES) = const.
        result = calculate_expected_value_per_ticket(
            user_state={'owned': {}, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(100.0),
        )
        assert abs(result['expected_value'] - 100.0) < 1e-9

    def test_top_down_solve_propagates_promotion_from_fourth_to_basic(self):
        # All 1st-job maxed, nothing else owned. 1st-tier EV pulls from
        # 2nd-tier EV via promotion. With everything else giving 50 per
        # pull, 2nd EV = 50, so 1st EV = 0.5 × 50 = 25. Per-ticket EV is
        # then 0.7521 × 50 (basic) + 0.22 × 25 (first) + 0.025 × 50 (second)
        # + 0.0025 × 50 (third) + 0.0004 × 50 (fourth) — note basic is
        # still direct since nothing in basic is owned.
        max_1 = MAX_LEVELS[JobAdvancement.FIRST]
        owned = {k: max_1 for k in companions_in_tier(JobAdvancement.FIRST)}
        result = calculate_expected_value_per_ticket(
            user_state={'owned': owned, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(50.0),
        )
        expected = (
            TIER_RATES[JobAdvancement.BASIC] * 50.0
            + TIER_RATES[JobAdvancement.FIRST] * (PROMOTION_RATES[JobAdvancement.FIRST] * 50.0)
            + TIER_RATES[JobAdvancement.SECOND] * 50.0
            + TIER_RATES[JobAdvancement.THIRD] * 50.0
            + TIER_RATES[JobAdvancement.FOURTH] * 50.0
        )
        assert abs(result['expected_value'] - expected) < 1e-9

    def test_breakdown_includes_every_tier(self):
        result = calculate_expected_value_per_ticket(
            user_state={'owned': {}, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(10.0),
        )
        for tier in JobAdvancement:
            assert tier.name in result['breakdown']


# ---------------------------------------------------------------------------
# Optimizer-wrapper shape
# ---------------------------------------------------------------------------

class TestOptimizerWrapper:
    def test_returns_none_when_baseline_zero(self):
        # Defensive: optimizer mustn't display a row with infinite efficiency.
        rec = get_companion_ticket_recommendation_for_optimizer(
            user_state={'owned': {}, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(100.0),
            baseline_dps=0.0,
        )
        assert rec is None

    def test_returns_none_when_ev_is_zero(self):
        # Zero marginal gain → no recommendation worth showing.
        rec = get_companion_ticket_recommendation_for_optimizer(
            user_state={'owned': {}, 'equipped': []},
            marginal_dps_fn=lambda _: 0.0,
            baseline_dps=1_000_000.0,
        )
        assert rec is None

    def test_returns_well_formed_recommendation(self):
        rec = get_companion_ticket_recommendation_for_optimizer(
            user_state={'owned': {}, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(100.0),
            baseline_dps=1_000_000.0,
            batch_size=100,
        )
        assert rec is not None
        # Must match the keys the optimizer's 'Summon' rendering block reads
        # (13_Upgrade_Optimizer.py:903-913).
        for key in ('type', 'subtype', 'target', 'target_display',
                    'description', 'cost', 'dps_gain', 'efficiency', 'details'):
            assert key in rec, f"missing key: {key}"
        assert rec['type'] == 'Summon'
        # Cost for 100 tickets ≈ 3529.41 diamonds.
        assert abs(rec['cost'] - 100 * DIAMONDS_PER_TICKET) < 1e-6
        # DPS gain expressed as % of baseline: positive, non-trivial.
        assert rec['dps_gain'] > 0
        # Efficiency = dps_gain / (cost / 1000), matches the optimizer's
        # cross-recommendation convention.
        assert abs(rec['efficiency'] - rec['dps_gain'] / (rec['cost'] / 1000.0)) < 1e-9

    def test_details_contain_per_tier_breakdown(self):
        rec = get_companion_ticket_recommendation_for_optimizer(
            user_state={'owned': {}, 'equipped': []},
            marginal_dps_fn=_const_gain_fn(100.0),
            baseline_dps=1_000_000.0,
        )
        assert rec is not None
        assert 'breakdown_per_tier_dps' in rec['details']
        assert 'top_contributors' in rec['details']
        # Top contributor (with this uniform mock) should be BASIC since
        # it has 75.21% of the per-ticket probability mass.
        top = rec['details']['top_contributors'][0]
        assert top['tier'] == 'BASIC'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
