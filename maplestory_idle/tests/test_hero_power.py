"""
Unit tests for game/hero_power.py

Covers: HeroPowerPassiveConfig stat scaling, level clamping, HeroPowerLevelConfig
tier rates and reroll cost formula, HeroPowerConfig stat totals and locking.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.hero_power import (
    HeroPowerPassiveConfig,
    HeroPowerPassiveStatType,
    HeroPowerConfig,
    HeroPowerLine,
    HeroPowerStatType,
    HeroPowerTier,
    HeroPowerLevelConfig,
    HERO_POWER_PASSIVE_STATS,
    HERO_POWER_REROLL_COSTS,
    HERO_POWER_STAT_RANGES,
    STAT_PROBABILITIES,
    create_maxed_passive_config,
    create_default_passive_config,
    get_max_passive_stats,
)


# ---------------------------------------------------------------------------
# HERO_POWER_REROLL_COSTS constants
# ---------------------------------------------------------------------------

class TestRerollCosts:
    def test_zero_locked_is_86(self):
        assert HERO_POWER_REROLL_COSTS[0] == 86

    def test_one_locked_is_129(self):
        assert HERO_POWER_REROLL_COSTS[1] == 129

    def test_each_lock_adds_43(self):
        base = HERO_POWER_REROLL_COSTS[0]
        for locked in range(1, 6):
            assert HERO_POWER_REROLL_COSTS[locked] == base + locked * 43

    def test_five_locked_is_301(self):
        assert HERO_POWER_REROLL_COSTS[5] == 301


# ---------------------------------------------------------------------------
# HeroPowerPassiveConfig — passive stat scaling
# ---------------------------------------------------------------------------

class TestHeroPowerPassiveConfig:
    def test_default_all_zeros(self):
        cfg = create_default_passive_config()
        for stat_type in HeroPowerPassiveStatType:
            assert cfg.get_stat_level(stat_type) == 0

    def test_default_stat_value_zero(self):
        cfg = create_default_passive_config()
        for stat_type in HeroPowerPassiveStatType:
            assert cfg.get_stat_value(stat_type) == pytest.approx(0.0)

    def test_main_stat_per_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.MAIN_STAT, 1)
        assert cfg.get_stat_value(HeroPowerPassiveStatType.MAIN_STAT) == pytest.approx(27.5)

    def test_damage_percent_per_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.DAMAGE_PERCENT, 1)
        assert cfg.get_stat_value(HeroPowerPassiveStatType.DAMAGE_PERCENT) == pytest.approx(0.75)

    def test_attack_per_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.ATTACK, 1)
        assert cfg.get_stat_value(HeroPowerPassiveStatType.ATTACK) == pytest.approx(103.75)

    def test_max_hp_per_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.MAX_HP, 1)
        assert cfg.get_stat_value(HeroPowerPassiveStatType.MAX_HP) == pytest.approx(2075.0)

    def test_accuracy_per_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.ACCURACY, 1)
        assert cfg.get_stat_value(HeroPowerPassiveStatType.ACCURACY) == pytest.approx(2.25)

    def test_defense_per_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.DEFENSE, 1)
        assert cfg.get_stat_value(HeroPowerPassiveStatType.DEFENSE) == pytest.approx(93.75)

    def test_main_stat_at_max_level(self):
        cfg = create_default_passive_config()
        max_level = HERO_POWER_PASSIVE_STATS[HeroPowerPassiveStatType.MAIN_STAT]["max_level"]
        cfg.set_stat_level(HeroPowerPassiveStatType.MAIN_STAT, max_level)
        # 60 * 27.5 = 1650
        assert cfg.get_stat_value(HeroPowerPassiveStatType.MAIN_STAT) == pytest.approx(1650.0)

    def test_damage_percent_at_max_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.DAMAGE_PERCENT, 60)
        # 60 * 0.75 = 45
        assert cfg.get_stat_value(HeroPowerPassiveStatType.DAMAGE_PERCENT) == pytest.approx(45.0)

    def test_attack_at_max_level(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.ATTACK, 60)
        # 60 * 103.75 = 6225
        assert cfg.get_stat_value(HeroPowerPassiveStatType.ATTACK) == pytest.approx(6225.0)

    def test_level_clamped_to_max(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.MAIN_STAT, 999)
        assert cfg.get_stat_level(HeroPowerPassiveStatType.MAIN_STAT) == 60

    def test_level_clamped_to_zero(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.MAIN_STAT, -5)
        assert cfg.get_stat_level(HeroPowerPassiveStatType.MAIN_STAT) == 0

    def test_accuracy_max_level_is_20(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.ACCURACY, 25)
        assert cfg.get_stat_level(HeroPowerPassiveStatType.ACCURACY) == 20

    def test_value_scales_linearly(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.MAIN_STAT, 10)
        val_10 = cfg.get_stat_value(HeroPowerPassiveStatType.MAIN_STAT)
        cfg.set_stat_level(HeroPowerPassiveStatType.MAIN_STAT, 20)
        val_20 = cfg.get_stat_value(HeroPowerPassiveStatType.MAIN_STAT)
        assert val_20 == pytest.approx(val_10 * 2)


# ---------------------------------------------------------------------------
# create_maxed_passive_config / get_max_passive_stats
# ---------------------------------------------------------------------------

class TestMaxedPassiveConfig:
    def test_all_stats_at_max_level(self):
        cfg = create_maxed_passive_config()
        for stat_type in HeroPowerPassiveStatType:
            max_level = HERO_POWER_PASSIVE_STATS[stat_type]["max_level"]
            assert cfg.get_stat_level(stat_type) == max_level

    def test_main_stat_max_value(self):
        cfg = create_maxed_passive_config()
        assert cfg.get_stat_value(HeroPowerPassiveStatType.MAIN_STAT) == pytest.approx(1650.0)

    def test_get_max_passive_stats_returns_dict(self):
        stats = get_max_passive_stats()
        assert isinstance(stats, dict)
        assert len(stats) > 0

    def test_get_max_passive_stats_main_stat_nonzero(self):
        stats = get_max_passive_stats()
        # Key uses stat_names.py constant 'main_stat_flat'
        main_key = "main_stat_flat"
        assert main_key in stats
        assert stats[main_key] == pytest.approx(1650.0)

    def test_get_max_passive_stats_damage_percent(self):
        stats = get_max_passive_stats()
        dmg_key = "damage_pct"
        assert dmg_key in stats
        assert stats[dmg_key] == pytest.approx(45.0)


# ---------------------------------------------------------------------------
# HeroPowerPassiveConfig.get_all_stats()
# ---------------------------------------------------------------------------

class TestPassiveConfigGetAllStats:
    def test_get_all_stats_returns_dict(self):
        cfg = create_default_passive_config()
        stats = cfg.get_all_stats()
        assert isinstance(stats, dict)

    def test_get_all_stats_zero_by_default(self):
        cfg = create_default_passive_config()
        stats = cfg.get_all_stats()
        for v in stats.values():
            assert v == pytest.approx(0.0)

    def test_get_all_stats_reflects_set_levels(self):
        cfg = create_default_passive_config()
        cfg.set_stat_level(HeroPowerPassiveStatType.ATTACK, 10)
        stats = cfg.get_all_stats()
        assert stats.get("attack_flat", 0) == pytest.approx(10 * 103.75)


# ---------------------------------------------------------------------------
# HeroPowerLevelConfig
# ---------------------------------------------------------------------------

class TestHeroPowerLevelConfig:
    def test_default_tier_rates_sum_to_one(self):
        cfg = HeroPowerLevelConfig()
        rates = cfg.get_tier_rates()
        assert sum(rates.values()) == pytest.approx(1.0, abs=0.01)

    def test_get_tier_rates_converts_pct_to_decimal(self):
        cfg = HeroPowerLevelConfig(mystic_rate=0.14)
        rates = cfg.get_tier_rates()
        assert rates[HeroPowerTier.MYSTIC] == pytest.approx(0.0014)

    def test_get_reroll_cost_base_cost_only(self):
        cfg = HeroPowerLevelConfig(base_cost=89)
        assert cfg.get_reroll_cost(0) == 89

    def test_get_reroll_cost_per_lock_adds_43(self):
        cfg = HeroPowerLevelConfig(base_cost=89)
        assert cfg.get_reroll_cost(1) == 89 + 43
        assert cfg.get_reroll_cost(2) == 89 + 86
        assert cfg.get_reroll_cost(3) == 89 + 129

    def test_from_dict_roundtrip(self):
        cfg = HeroPowerLevelConfig(level=20, base_cost=100, mystic_rate=0.20)
        d = cfg.to_dict()
        cfg2 = HeroPowerLevelConfig.from_dict(d)
        assert cfg2.level == 20
        assert cfg2.base_cost == 100
        assert cfg2.mystic_rate == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# HeroPowerConfig — stat totals and locking
# ---------------------------------------------------------------------------

class TestHeroPowerConfig:
    def _make_line(self, slot, stat_type, value, tier, locked=False):
        return HeroPowerLine(slot=slot, stat_type=stat_type, value=value, tier=tier, is_locked=locked)

    def test_default_config_has_6_lines(self):
        cfg = HeroPowerConfig()
        assert len(cfg.lines) == 6

    def test_get_locked_count_none(self):
        cfg = HeroPowerConfig()
        assert cfg.get_locked_count() == 0

    def test_get_locked_count_two(self):
        cfg = HeroPowerConfig()
        cfg.lines[0].is_locked = True
        cfg.lines[2].is_locked = True
        assert cfg.get_locked_count() == 2

    def test_get_reroll_cost_zero_locked(self):
        cfg = HeroPowerConfig()
        assert cfg.get_reroll_cost() == HERO_POWER_REROLL_COSTS[0]

    def test_get_reroll_cost_with_locks(self):
        cfg = HeroPowerConfig()
        cfg.lines[0].is_locked = True
        cfg.lines[1].is_locked = True
        assert cfg.get_reroll_cost() == HERO_POWER_REROLL_COSTS[2]

    def test_get_stat_total_single_line(self):
        cfg = HeroPowerConfig()
        cfg.lines[0] = self._make_line(1, HeroPowerStatType.BOSS_DAMAGE, 35.0, HeroPowerTier.RARE)
        assert cfg.get_stat_total(HeroPowerStatType.BOSS_DAMAGE) == pytest.approx(35.0)

    def test_get_stat_total_multiple_lines(self):
        cfg = HeroPowerConfig()
        cfg.lines[0] = self._make_line(1, HeroPowerStatType.DEF_PEN, 18.0, HeroPowerTier.RARE)
        cfg.lines[1] = self._make_line(2, HeroPowerStatType.DEF_PEN, 14.0, HeroPowerTier.RARE)
        assert cfg.get_stat_total(HeroPowerStatType.DEF_PEN) == pytest.approx(32.0)

    def test_get_stat_total_absent_stat(self):
        cfg = HeroPowerConfig()
        assert cfg.get_stat_total(HeroPowerStatType.MAX_HP) == pytest.approx(0.0)

    def test_get_all_stats_includes_all_lines(self):
        cfg = HeroPowerConfig()
        cfg.lines[0] = self._make_line(1, HeroPowerStatType.DAMAGE, 30.0, HeroPowerTier.LEGENDARY)
        cfg.lines[1] = self._make_line(2, HeroPowerStatType.BOSS_DAMAGE, 35.0, HeroPowerTier.RARE)
        stats = cfg.get_all_stats()
        assert HeroPowerStatType.DAMAGE in stats
        assert HeroPowerStatType.BOSS_DAMAGE in stats
        assert stats[HeroPowerStatType.DAMAGE] == pytest.approx(30.0)

    def test_count_lines_meeting_criteria_tier_filter(self):
        # Tier order: COMMON < RARE < EPIC < UNIQUE < LEGENDARY < MYSTIC
        # min_tier=EPIC excludes RARE (below EPIC) but includes EPIC itself
        cfg = HeroPowerConfig()
        cfg.lines[0] = self._make_line(1, HeroPowerStatType.BOSS_DAMAGE, 35.0, HeroPowerTier.RARE)
        cfg.lines[1] = self._make_line(2, HeroPowerStatType.BOSS_DAMAGE, 20.0, HeroPowerTier.EPIC)
        count = cfg.count_lines_meeting_criteria([HeroPowerStatType.BOSS_DAMAGE], HeroPowerTier.EPIC)
        assert count == 1  # Only EPIC line qualifies (RARE is below EPIC)

    def test_count_lines_meeting_criteria_includes_higher_tiers(self):
        cfg = HeroPowerConfig()
        cfg.lines[0] = self._make_line(1, HeroPowerStatType.DAMAGE, 30.0, HeroPowerTier.LEGENDARY)
        cfg.lines[1] = self._make_line(2, HeroPowerStatType.DAMAGE, 10.0, HeroPowerTier.UNIQUE)
        # Unique+ counts both UNIQUE and LEGENDARY (both at or above UNIQUE)
        count = cfg.count_lines_meeting_criteria([HeroPowerStatType.DAMAGE], HeroPowerTier.UNIQUE)
        assert count == 2


# ---------------------------------------------------------------------------
# HERO_POWER_STAT_RANGES — data integrity
# ---------------------------------------------------------------------------

class TestStatRanges:
    def test_all_tiers_have_ranges(self):
        for tier in HeroPowerTier:
            assert tier in HERO_POWER_STAT_RANGES

    def test_range_min_le_max(self):
        for tier, stats in HERO_POWER_STAT_RANGES.items():
            for stat_type, (lo, hi) in stats.items():
                assert lo <= hi, f"{tier.value} {stat_type.value}: min > max"

    def test_mystic_boss_damage_best(self):
        # Per datamine HeroPowerAbilityOptionTable, Mystic (Grade6) has the
        # strictly best boss damage range; Legendary (Grade5) is second best.
        mystic_min, mystic_max = HERO_POWER_STAT_RANGES[HeroPowerTier.MYSTIC][HeroPowerStatType.BOSS_DAMAGE]
        legendary_min, legendary_max = HERO_POWER_STAT_RANGES[HeroPowerTier.LEGENDARY][HeroPowerStatType.BOSS_DAMAGE]
        assert mystic_min > legendary_max

    def test_def_pen_only_at_legendary_and_mystic(self):
        # PiercePower (Def Pen) only rolls at Grade5+ per datamine
        assert HeroPowerStatType.DEF_PEN in HERO_POWER_STAT_RANGES[HeroPowerTier.MYSTIC]
        assert HeroPowerStatType.DEF_PEN in HERO_POWER_STAT_RANGES[HeroPowerTier.LEGENDARY]
        for tier in (HeroPowerTier.UNIQUE, HeroPowerTier.EPIC,
                     HeroPowerTier.RARE, HeroPowerTier.COMMON):
            assert HeroPowerStatType.DEF_PEN not in HERO_POWER_STAT_RANGES[tier]

    def test_higher_tiers_strictly_dominate(self):
        # For every stat present at both tiers, the higher tier's max must
        # exceed the lower tier's max (and min should be >= lower tier's max).
        tier_order = [
            HeroPowerTier.COMMON, HeroPowerTier.RARE, HeroPowerTier.EPIC,
            HeroPowerTier.UNIQUE, HeroPowerTier.LEGENDARY, HeroPowerTier.MYSTIC,
        ]
        for i in range(len(tier_order) - 1):
            lo_tier, hi_tier = tier_order[i], tier_order[i+1]
            lo_ranges = HERO_POWER_STAT_RANGES[lo_tier]
            hi_ranges = HERO_POWER_STAT_RANGES[hi_tier]
            for stat in lo_ranges.keys() & hi_ranges.keys():
                assert hi_ranges[stat][1] > lo_ranges[stat][1], (
                    f"{hi_tier.value} {stat.value} max {hi_ranges[stat][1]} "
                    f"<= {lo_tier.value} max {lo_ranges[stat][1]}"
                )


# ---------------------------------------------------------------------------
# STAT_PROBABILITIES — data integrity
# ---------------------------------------------------------------------------

class TestStatProbabilities:
    def test_all_tiers_have_probabilities(self):
        for tier in HeroPowerTier:
            assert tier in STAT_PROBABILITIES

    def test_probabilities_sum_to_one(self):
        for tier, probs in STAT_PROBABILITIES.items():
            total = sum(probs.values())
            assert total == pytest.approx(1.0, abs=0.01), f"{tier.value} probs sum to {total}"


# ---------------------------------------------------------------------------
# analyze_budget — budget-driven optimizer
# ---------------------------------------------------------------------------

from game.hero_power import analyze_budget


def _make_config_with_lines(lines):
    """lines is a list of (slot, stat_type, value, tier, locked) tuples."""
    return HeroPowerConfig(lines=[
        HeroPowerLine(slot=s, stat_type=st, value=v, tier=t, is_locked=lk)
        for (s, st, v, t, lk) in lines
    ])


def _fake_dps_callbacks(per_stat_dps_per_unit):
    """
    Returns (calc_dps, get_stats) where current DPS reflects an additive
    contribution per (stat * value), so calculate_line_dps_value returns
    sensible per-line contributions for testing without invoking the real
    DPS engine.
    """
    base_stats = {
        # Source-list stats required by calculate_line_dps_value
        'def_pen_sources': [], 'attack_speed_sources': [],
        'final_damage_sources': [], 'main_stat_type': 'dex',
        # Tracked stats start at zero
        'damage_pct': 0.0, 'boss_damage': 0.0, 'normal_damage': 0.0,
        'crit_rate': 0.0, 'min_dmg_mult': 0.0, 'max_dmg_mult': 0.0,
        'dex_flat': 0.0,
    }

    def get_stats():
        return dict(base_stats)  # shallow copy so callers can mutate

    def calc_dps(stats):
        # Linear, additive scoring: sum (stat_value * per-unit-coefficient).
        # Returns a positive scalar so calculate_line_dps_value can ratio it.
        total = 100.0  # baseline non-stat DPS
        for stat_key, coeff in per_stat_dps_per_unit.items():
            total += stats.get(stat_key, 0.0) * coeff
        # def_pen and attack_speed are source lists; sum their (value/100 for
        # def_pen, value for attack_speed) entries.
        for src, val, *rest in stats.get('def_pen_sources', []):
            total += val * 100 * per_stat_dps_per_unit.get('def_pen', 0)
        for src, val in stats.get('attack_speed_sources', []):
            total += val * per_stat_dps_per_unit.get('attack_speed', 0)
        return total

    return calc_dps, get_stats


class TestAnalyzeBudget:
    """Verification cases from the plan."""

    def test_zero_budget_locks_everything(self):
        # Budget = 0 → no rerolls affordable → lock all 6 slots, gain = 0.
        cfg = _make_config_with_lines([
            (i, HeroPowerStatType.DAMAGE, 5.0, HeroPowerTier.RARE, False)
            for i in range(1, 7)
        ])
        calc, gs = _fake_dps_callbacks({'damage_pct': 1.0})
        result = analyze_budget(cfg, HeroPowerLevelConfig(), 0, calc, gs)
        assert result['recommended_locks'] == [1, 2, 3, 4, 5, 6]
        assert result['expected_gain_pct'] == pytest.approx(0.0, abs=1e-6)
        assert result['expected_rerolls'] == 0

    def test_huge_budget_recommends_aggressive_rerolling(self):
        # All lines start common-tier weak → at huge budget recommend
        # rerolling everything (no locks except user-locks; here none).
        cfg = _make_config_with_lines([
            (i, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, False)
            for i in range(1, 7)
        ])
        calc, gs = _fake_dps_callbacks({'damage_pct': 1.0})
        result = analyze_budget(cfg, HeroPowerLevelConfig(), 1_000_000_000, calc, gs)
        # All weak lines should be REROLL
        assert all(la['recommendation'] == 'REROLL' for la in result['line_analysis'])

    def test_respects_user_explicit_locks(self):
        # User locks line 3. Algorithm must include slot 3 in recommended_locks
        # regardless of budget.
        cfg = _make_config_with_lines([
            (1, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, False),
            (2, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, False),
            (3, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, True),  # user-locked
            (4, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, False),
            (5, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, False),
            (6, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, False),
        ])
        calc, gs = _fake_dps_callbacks({'damage_pct': 1.0})
        for budget in [0, 10_000, 1_000_000_000]:
            result = analyze_budget(cfg, HeroPowerLevelConfig(), budget, calc, gs)
            assert 3 in result['recommended_locks'], (
                f"slot 3 missing from locks at budget {budget}"
            )

    def test_cascade_is_monotonic_nonincreasing(self):
        # The user's stated property: R_0 >= R_1 >= ... >= R_5 for any
        # positive budget. Codifies "aggressive at 0 locks, lenient at 5".
        cfg = _make_config_with_lines([
            (i, HeroPowerStatType.DAMAGE, 5.0, HeroPowerTier.RARE, False)
            for i in range(1, 7)
        ])
        calc, gs = _fake_dps_callbacks({'damage_pct': 1.0})
        for budget in [1_000, 10_000, 100_000, 1_000_000, 10_000_000]:
            result = analyze_budget(cfg, HeroPowerLevelConfig(), budget, calc, gs)
            cascade = result['cascade']
            for i in range(len(cascade) - 1):
                assert cascade[i]['reservation_dps_pct'] >= cascade[i+1]['reservation_dps_pct'], (
                    f"cascade non-monotonic at budget {budget}: "
                    f"R_{i}={cascade[i]['reservation_dps_pct']:.4f} "
                    f"< R_{i+1}={cascade[i+1]['reservation_dps_pct']:.4f}"
                )

    def test_budget_monotonicity_of_expected_gain(self):
        # Doubling the budget should never decrease the expected gain.
        cfg = _make_config_with_lines([
            (i, HeroPowerStatType.DAMAGE, 4.0, HeroPowerTier.COMMON, False)
            for i in range(1, 7)
        ])
        calc, gs = _fake_dps_callbacks({'damage_pct': 1.0})
        prev_gain = -1.0
        for budget in [1_000, 10_000, 100_000, 1_000_000, 10_000_000]:
            result = analyze_budget(cfg, HeroPowerLevelConfig(), budget, calc, gs)
            assert result['expected_gain_pct'] >= prev_gain - 1e-6, (
                f"gain decreased at budget {budget}: "
                f"{result['expected_gain_pct']:.4f} < prev {prev_gain:.4f}"
            )
            prev_gain = result['expected_gain_pct']

    def test_lock_count_decreases_as_budget_grows(self):
        # Aggressive behaviour: at small budget many lines lock; at huge
        # budget fewer lines lock (the bar gets higher). Start with a config
        # whose lines are moderately strong so the threshold matters.
        cfg = _make_config_with_lines([
            (i, HeroPowerStatType.DAMAGE, 18.0, HeroPowerTier.UNIQUE, False)
            for i in range(1, 7)
        ])
        calc, gs = _fake_dps_callbacks({'damage_pct': 1.0})
        small = analyze_budget(cfg, HeroPowerLevelConfig(), 10_000, calc, gs)
        large = analyze_budget(cfg, HeroPowerLevelConfig(), 100_000_000, calc, gs)
        assert len(small['recommended_locks']) >= len(large['recommended_locks']), (
            f"expected fewer locks at large budget: "
            f"small_locks={small['recommended_locks']}, large_locks={large['recommended_locks']}"
        )
