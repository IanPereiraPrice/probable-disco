"""
Unit tests for core/damage.py — damage formula correctness.

Each test validates one formula in isolation.  Numbers are derived from the
formula definitions, not from game observation, so they double as regression
guards if formulas ever change.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.damage import (
    calculate_total_dex,
    calculate_stat_proportional_damage,
    calculate_damage_amp_multiplier,
    calculate_final_damage_mult,
    calculate_final_damage_total,
    calculate_effective_crit_multiplier,
    calculate_defense_pen,
    calculate_defense_multiplier,
    calculate_attack_speed,
    calculate_damage,
    calculate_damage_simple,
    DamageResult,
)
from core.constants import BASE_CRIT_DMG, DEF_PEN_CAP, ATK_SPD_CAP


# ---------------------------------------------------------------------------
# calculate_total_dex
# ---------------------------------------------------------------------------

class TestCalculateTotalDex:
    def test_zero_percent_returns_flat(self):
        assert calculate_total_dex(10_000, 0) == 10_000.0

    def test_100_percent_doubles(self):
        assert calculate_total_dex(10_000, 100) == 20_000.0

    def test_formula(self):
        # flat=5000, pct=50 → 5000 * 1.5 = 7500
        assert calculate_total_dex(5_000, 50) == pytest.approx(7_500.0)

    def test_zero_flat(self):
        assert calculate_total_dex(0, 200) == 0.0


# ---------------------------------------------------------------------------
# calculate_stat_proportional_damage
# ---------------------------------------------------------------------------

class TestStatProportionalDamage:
    def test_dex_only(self):
        # 10000 DEX → 10000 * 0.01 = 100
        assert calculate_stat_proportional_damage(10_000) == pytest.approx(100.0)

    def test_dex_and_str(self):
        # 10000 DEX + 4000 STR → 100 + 10 = 110
        assert calculate_stat_proportional_damage(10_000, 4_000) == pytest.approx(110.0)

    def test_zero_stats(self):
        assert calculate_stat_proportional_damage(0, 0) == 0.0

    def test_str_coefficient_is_quarter_of_dex(self):
        dex_only = calculate_stat_proportional_damage(400, 0)
        str_only = calculate_stat_proportional_damage(0, 400)
        assert dex_only == pytest.approx(str_only * 4)


# ---------------------------------------------------------------------------
# calculate_damage_amp_multiplier
# ---------------------------------------------------------------------------

class TestDamageAmpMultiplier:
    def test_zero_amp(self):
        assert calculate_damage_amp_multiplier(0) == 1.0

    def test_100_pct(self):
        assert calculate_damage_amp_multiplier(100) == pytest.approx(2.0)

    def test_23_pct(self):
        assert calculate_damage_amp_multiplier(23) == pytest.approx(1.23)

    def test_negative_not_below_zero(self):
        # Negative amp is unusual but formula should still hold
        assert calculate_damage_amp_multiplier(-50) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# calculate_final_damage_mult / total
# ---------------------------------------------------------------------------

class TestFinalDamage:
    def test_empty_sources(self):
        assert calculate_final_damage_mult([]) == 1.0

    def test_single_source(self):
        # 10% FD (0.10) → 1.10
        assert calculate_final_damage_mult([0.10]) == pytest.approx(1.10)

    def test_two_sources_multiplicative(self):
        # 10% and 20% → 1.10 * 1.20 = 1.32  (NOT 1.30 additive)
        assert calculate_final_damage_mult([0.10, 0.20]) == pytest.approx(1.32)

    def test_three_sources(self):
        # 13%, 10%, 8%  →  1.13 * 1.10 * 1.08 = 1.342584
        result = calculate_final_damage_mult([0.13, 0.10, 0.08])
        assert result == pytest.approx(1.13 * 1.10 * 1.08)

    def test_total_is_mult_minus_one(self):
        sources = [0.13, 0.217, 0.10]
        assert calculate_final_damage_total(sources) == pytest.approx(
            calculate_final_damage_mult(sources) - 1
        )

    def test_order_independent(self):
        s1 = calculate_final_damage_mult([0.10, 0.20, 0.05])
        s2 = calculate_final_damage_mult([0.20, 0.05, 0.10])
        assert s1 == pytest.approx(s2)


# ---------------------------------------------------------------------------
# calculate_effective_crit_multiplier
# ---------------------------------------------------------------------------

class TestCritMultiplier:
    def test_zero_crit_rate(self):
        # No crits → multiplier = 1.0
        assert calculate_effective_crit_multiplier(0, BASE_CRIT_DMG) == pytest.approx(1.0)

    def test_100_crit_rate(self):
        # Always crit, BASE_CRIT_DMG=30 → 1 + 1.0 * 0.30 = 1.30
        assert calculate_effective_crit_multiplier(100, BASE_CRIT_DMG) == pytest.approx(1.30)

    def test_100_crit_rate_with_bonus(self):
        # 100% crit, 200% total crit dmg → 1 + 2.0 = 3.0
        assert calculate_effective_crit_multiplier(100, 200) == pytest.approx(3.0)

    def test_50_crit_rate(self):
        # 50% chance to crit: 0.5 * (1 + 1.0) + 0.5 * 1 = 1.5  (crit_dmg=100)
        # Simplified: 1 + 0.50 * 1.0 = 1.5
        assert calculate_effective_crit_multiplier(50, 100) == pytest.approx(1.5)

    def test_crit_rate_capped_at_100(self):
        # 120% crit rate should behave same as 100%
        mult_100 = calculate_effective_crit_multiplier(100, 200)
        mult_120 = calculate_effective_crit_multiplier(120, 200)
        assert mult_100 == pytest.approx(mult_120)

    def test_formula_weighted_average(self):
        # For rate=75, crit_dmg=150:
        # mult = 1 + (75/100) * (150/100) = 1 + 0.75 * 1.5 = 2.125
        assert calculate_effective_crit_multiplier(75, 150) == pytest.approx(2.125)


# ---------------------------------------------------------------------------
# calculate_defense_pen
# ---------------------------------------------------------------------------

class TestDefensePen:
    def test_no_sources(self):
        # No pen → 0% pen
        assert calculate_defense_pen([]) == pytest.approx(0.0)

    def test_single_source(self):
        # 42.4% pen → remaining = 0.576; pen = 0.424
        assert calculate_defense_pen([0.424]) == pytest.approx(0.424)

    def test_multiple_sources_multiplicative(self):
        # 42.4% + 19% + 16.5%
        remaining = (1 - 0.424) * (1 - 0.19) * (1 - 0.165)
        expected = 1 - remaining
        assert calculate_defense_pen([0.424, 0.19, 0.165]) == pytest.approx(expected)

    def test_not_additive(self):
        # Two 50% sources → 75%, NOT 100% (multiplicative)
        result = calculate_defense_pen([0.50, 0.50])
        assert result == pytest.approx(0.75)
        assert result < 1.0

    def test_cap_at_100_pct(self):
        # Even absurd values can't exceed 1.0
        result = calculate_defense_pen([0.99, 0.99, 0.99])
        assert result <= 1.0

    def test_single_100_pct_source(self):
        assert calculate_defense_pen([1.0]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# calculate_defense_multiplier
# ---------------------------------------------------------------------------

class TestDefenseMultiplier:
    def test_no_defense(self):
        # enemy_def=0 → multiplier = 1.0 regardless of pen
        assert calculate_defense_multiplier(0.0, 0.0) == pytest.approx(1.0)
        assert calculate_defense_multiplier(0.5, 0.0) == pytest.approx(1.0)

    def test_full_pen_nullifies_defense(self):
        # 100% pen → 1/(1 + def*0) = 1.0
        assert calculate_defense_multiplier(1.0, 0.752) == pytest.approx(1.0)

    def test_chapter_27_no_pen(self):
        # enemy_def=0.752, pen=0 → 1/(1+0.752) ≈ 0.5707
        expected = 1 / (1 + 0.752)
        assert calculate_defense_multiplier(0.0, 0.752) == pytest.approx(expected)

    def test_chapter_27_with_pen(self):
        # 60% pen, enemy_def=0.752 → 1/(1 + 0.752*0.4) ≈ 0.7686
        expected = 1 / (1 + 0.752 * 0.4)
        assert calculate_defense_multiplier(0.6, 0.752) == pytest.approx(expected)

    def test_world_boss(self):
        # World boss def=6.527, no pen → multiplier ≈ 0.133
        expected = 1 / (1 + 6.527)
        assert calculate_defense_multiplier(0.0, 6.527) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# calculate_attack_speed (diminishing returns)
# ---------------------------------------------------------------------------

class TestAttackSpeed:
    def test_no_sources(self):
        assert calculate_attack_speed([]) == pytest.approx(0.0)

    def test_single_source(self):
        # +15% → 150 * (1 - (1-15/150)) = 15.0  (no diminishing on first source)
        # Actually: gain = (150 - 0) * (15/150) = 15.0
        assert calculate_attack_speed([("weapon", 15)]) == pytest.approx(15.0)

    def test_two_sources_diminishing(self):
        # 15% + 10%: second source applies to remaining gap (150-15=135)
        # gain2 = 135 * (10/150) = 9.0  →  total = 24.0
        result = calculate_attack_speed([("a", 15), ("b", 10)])
        assert result == pytest.approx(24.0)

    def test_cap_at_150(self):
        sources = [("a", 100), ("b", 100), ("c", 100)]
        assert calculate_attack_speed(sources) <= ATK_SPD_CAP

    def test_zero_value_source_ignored(self):
        # Source with value 0 should not affect result
        result_without = calculate_attack_speed([("a", 15)])
        result_with_zero = calculate_attack_speed([("a", 15), ("b", 0)])
        assert result_without == pytest.approx(result_with_zero)

    def test_example_from_docstring(self):
        # Sources: 15%, 10%, 7%, 5%
        # Expected: 150 * (1 - (1-15/150)*(1-10/150)*(1-7/150)*(1-5/150))
        sources = [("a", 15), ("b", 10), ("c", 7), ("d", 5)]
        expected = 150 * (1 - (1-15/150) * (1-10/150) * (1-7/150) * (1-5/150))
        assert calculate_attack_speed(sources) == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# calculate_damage (master formula)
# ---------------------------------------------------------------------------

class TestCalculateDamage:
    """Integration-style tests that verify the master formula assembles correctly."""

    def _base_kwargs(self):
        return dict(
            base_atk=10_000,
            dex_flat=20_000,
            dex_percent=100.0,     # total_dex = 40000
            damage_percent=100.0,
            damage_amp=0.0,
            final_damage_sources=[],
            crit_rate=100.0,
            crit_damage=100.0,     # total crit_dmg = BASE_CRIT_DMG(30) + 100 = 130 → mult 2.30
            defense_pen=1.0,       # full pen → def_mult = 1.0
            enemy_def=0.752,
            boss_damage=0.0,
        )

    def test_returns_damage_result(self):
        result = calculate_damage(**self._base_kwargs())
        assert isinstance(result, DamageResult)

    def test_total_equals_product_of_components(self):
        result = calculate_damage(**self._base_kwargs())
        product = (
            result.base_atk * result.stat_mult * result.damage_mult
            * result.amp_mult * result.fd_mult * result.crit_mult * result.def_mult
        )
        assert result.total == pytest.approx(product)

    def test_zero_damage_percent(self):
        kwargs = self._base_kwargs()
        kwargs["damage_percent"] = 0
        result = calculate_damage(**kwargs)
        assert result.damage_mult == pytest.approx(1.0)

    def test_boss_damage_additive_with_damage_pct(self):
        base = calculate_damage(**self._base_kwargs())
        kwargs = self._base_kwargs()
        kwargs["boss_damage"] = 50.0
        boss = calculate_damage(**kwargs)
        # damage_mult should increase by 50%/100 = 0.5
        assert boss.damage_mult == pytest.approx(base.damage_mult + 0.5)

    def test_final_damage_multiplicative(self):
        base = calculate_damage(**self._base_kwargs())
        kwargs = self._base_kwargs()
        kwargs["final_damage_sources"] = [0.20]
        with_fd = calculate_damage(**kwargs)
        assert with_fd.fd_mult == pytest.approx(1.20)
        assert with_fd.total == pytest.approx(base.total * 1.20)

    def test_no_defense_pen_reduces_damage(self):
        kwargs = self._base_kwargs()
        kwargs["defense_pen"] = 0.0
        no_pen = calculate_damage(**kwargs)
        full_pen = calculate_damage(**self._base_kwargs())  # defense_pen=1.0
        assert no_pen.total < full_pen.total

    def test_dex_flat_conversion_added_after_pct(self):
        # dex_flat_conversion adds AFTER percentage scaling
        base_result = calculate_damage(**self._base_kwargs())
        kwargs = self._base_kwargs()
        kwargs["dex_flat_conversion"] = 5_000
        conv_result = calculate_damage(**kwargs)
        assert conv_result.total_dex == pytest.approx(base_result.total_dex + 5_000)

    def test_total_dex_stored(self):
        result = calculate_damage(**self._base_kwargs())
        # dex_flat=20000, dex_percent=100 → total_dex = 40000
        assert result.total_dex == pytest.approx(40_000.0)


# ---------------------------------------------------------------------------
# calculate_damage_simple
# ---------------------------------------------------------------------------

class TestCalculateDamageSimple:
    def test_known_result(self):
        # Minimal controllable case: no bonuses except stat scaling
        result = calculate_damage_simple(
            base_atk=1_000,
            total_dex=10_000,
            damage_percent=0,
            final_damage=0.0,
            crit_rate=0,
            crit_damage=BASE_CRIT_DMG,
            defense_pen=1.0,
            enemy_def=0.0,
        )
        # stat_mult = 1 + 10000/10000 = 2.0  (1% per 100 DEX)
        # Wait — formula is 1 + (total_dex / 10000) + ...
        # = 1 + 1.0 = 2.0
        # damage_mult = 1.0, amp_mult = 1.0, fd_mult = 1.0
        # crit_mult = 1 + 0 * (BASE_CRIT_DMG/100) = 1.0
        # def_mult = 1.0
        assert result == pytest.approx(1_000 * 2.0)

    def test_manual_formula_verification(self):
        # Verify each component manually for calculate_damage_simple.
        # Note: this function uses TOTAL crit_damage (including base),
        # and final_damage as a pre-combined decimal.
        base_atk = 5_000
        total_dex = 20_000   # stat_mult = 1 + 2.0 = 3.0
        damage_percent = 50  # damage_mult = 1.5
        final_damage = 0.10  # fd_mult = 1.10
        crit_rate = 100
        crit_damage = 130    # crit_mult = 1 + 1.0 * 1.30 = 2.30
        defense_pen = 1.0    # def_mult = 1.0
        enemy_def = 0.752

        result = calculate_damage_simple(
            base_atk=base_atk,
            total_dex=total_dex,
            damage_percent=damage_percent,
            final_damage=final_damage,
            crit_rate=crit_rate,
            crit_damage=crit_damage,
            defense_pen=defense_pen,
            enemy_def=enemy_def,
        )
        expected = 5_000 * 3.0 * 1.5 * 1.0 * 1.10 * 2.30 * 1.0
        assert result == pytest.approx(expected)
