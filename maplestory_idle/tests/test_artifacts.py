"""
Unit tests for game/artifacts.py

Covers: ArtifactEffect, ArtifactDefinition, ArtifactInstance, resonance formulas,
Hex Necklace multiplier, Fire Flower FD, Bottle of Emotions FD, scenario filtering.
"""
import sys
import math
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.artifacts import (
    ArtifactEffect,
    ArtifactDefinition,
    ArtifactInstance,
    ArtifactTier,
    EffectType,
    ARTIFACTS,
    POTENTIAL_SLOT_UNLOCKS,
    calculate_resonance_hp,
    calculate_resonance_main_stat,
    calculate_resonance_upgrade_cost,
    calculate_resonance_total_cost,
    calculate_hex_multiplier,
    calculate_hex_average_multiplier,
    calculate_fire_flower_fd,
    calculate_bottle_of_emotions_fd,
)


# ---------------------------------------------------------------------------
# ArtifactEffect.get_value()
# ---------------------------------------------------------------------------

class TestArtifactEffectGetValue:
    def test_flat_effect_no_stars(self):
        effect = ArtifactEffect(stat="crit_rate", base=0.10, per_star=0.02)
        assert effect.get_value(0) == pytest.approx(0.10)

    def test_flat_effect_at_max_stars(self):
        effect = ArtifactEffect(stat="crit_rate", base=0.10, per_star=0.02)
        assert effect.get_value(5) == pytest.approx(0.20)

    def test_linear_scaling(self):
        effect = ArtifactEffect(stat="boss_damage", base=0.50, per_star=0.10)
        for stars in range(6):
            expected = 0.50 + stars * 0.10
            assert effect.get_value(stars) == pytest.approx(expected)

    def test_multiplicative_with_stacks(self):
        effect = ArtifactEffect(
            stat="damage_multiplier", base=0.15, per_star=0.03,
            effect_type=EffectType.MULTIPLICATIVE, max_stacks=3,
        )
        # 3 stacks, ★0: 0.15 * 3 = 0.45
        assert effect.get_value(0, stacks=3) == pytest.approx(0.45)

    def test_multiplicative_stacks_capped(self):
        effect = ArtifactEffect(
            stat="damage_multiplier", base=0.15, per_star=0.03,
            effect_type=EffectType.MULTIPLICATIVE, max_stacks=3,
        )
        # 5 stacks requested but capped at 3
        assert effect.get_value(0, stacks=5) == effect.get_value(0, stacks=3)

    def test_multiplicative_default_stacks_is_max(self):
        effect = ArtifactEffect(
            stat="damage_multiplier", base=0.15, per_star=0.03,
            effect_type=EffectType.MULTIPLICATIVE, max_stacks=3,
        )
        # No stacks kwarg → uses max_stacks
        assert effect.get_value(0) == pytest.approx(0.45)


# ---------------------------------------------------------------------------
# ArtifactDefinition.get_inventory_value()
# ---------------------------------------------------------------------------

class TestArtifactDefinitionInventory:
    def test_chalice_inventory_zero_stars(self):
        chalice = ARTIFACTS["chalice"]
        # inventory_base=0.30, per_star=0.06
        assert chalice.get_inventory_value(0) == pytest.approx(0.30)

    def test_chalice_inventory_five_stars(self):
        chalice = ARTIFACTS["chalice"]
        # 0.30 + 5 * 0.06 = 0.60
        assert chalice.get_inventory_value(5) == pytest.approx(0.60)

    def test_shamaness_inventory_linear(self):
        art = ARTIFACTS["shamaness_marble"]
        # inventory_base=200, per_star=160
        assert art.get_inventory_value(0) == pytest.approx(200)
        assert art.get_inventory_value(5) == pytest.approx(1000)

    def test_book_of_ancient_inventory_crit_rate(self):
        book = ARTIFACTS["book_of_ancient"]
        # inventory_base=0.05, per_star=0.01 → 10% at ★5
        assert book.get_inventory_value(0) == pytest.approx(0.05)
        assert book.get_inventory_value(5) == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# ArtifactDefinition.applies_to_scenario()
# ---------------------------------------------------------------------------

class TestScenarioFiltering:
    def test_universal_artifact_applies_everywhere(self):
        # Chalice has no scenario restriction
        chalice = ARTIFACTS["chalice"]
        assert chalice.applies_to_scenario("normal")
        assert chalice.applies_to_scenario("boss")
        assert chalice.applies_to_scenario("world_boss")

    def test_world_boss_only_artifact(self):
        lit_lamp = ARTIFACTS["lit_lamp"]
        assert lit_lamp.applies_to_scenario("world_boss")
        assert not lit_lamp.applies_to_scenario("normal")
        assert not lit_lamp.applies_to_scenario("boss")

    def test_always_on_artifact(self):
        star_rock = ARTIFACTS["star_rock"]
        assert star_rock.scenario is None
        assert star_rock.applies_to_scenario("normal")
        assert star_rock.applies_to_scenario("world_boss")


# ---------------------------------------------------------------------------
# ArtifactDefinition.get_effective_uptime()
# ---------------------------------------------------------------------------

class TestEffectiveUptime:
    def test_always_on_returns_one(self):
        # star_rock has no buff timing → always on
        star_rock = ARTIFACTS["star_rock"]
        assert star_rock.get_effective_uptime(60.0) == pytest.approx(1.0)

    def test_proc_chance_artifact(self):
        # silver_pendant has proc_chance=0.15
        silver = ARTIFACTS["silver_pendant"]
        assert silver.get_effective_uptime(60.0) == pytest.approx(0.15)

    def test_timed_buff_charm_50pct(self):
        # charm_of_undead: buff_duration=5.0, buff_cooldown=10.0 → ~50% uptime
        charm = ARTIFACTS["charm_of_undead"]
        uptime = charm.get_effective_uptime(60.0)
        # Should be near 50% but exact value depends on cooldown_calc module
        assert 0.4 < uptime < 0.6

    def test_ramp_artifact_long_fight(self):
        # Rainbow snail shell: one-time 15s buff at battle start, cooldown=inf
        # At very long duration, uptime approaches 0
        snail = ARTIFACTS["rainbow_snail_shell"]
        uptime_long = snail.get_effective_uptime(300.0)
        uptime_short = snail.get_effective_uptime(15.0)
        assert uptime_long < uptime_short


# ---------------------------------------------------------------------------
# ArtifactInstance.potential_slots
# ---------------------------------------------------------------------------

class TestPotentialSlots:
    def test_legendary_zero_stars(self):
        chalice = ARTIFACTS["chalice"]
        instance = ArtifactInstance(definition=chalice, awakening_stars=0)
        assert instance.potential_slots == POTENTIAL_SLOT_UNLOCKS[0]  # 0

    def test_legendary_one_star(self):
        chalice = ARTIFACTS["chalice"]
        instance = ArtifactInstance(definition=chalice, awakening_stars=1)
        assert instance.potential_slots == 1

    def test_legendary_three_stars(self):
        chalice = ARTIFACTS["chalice"]
        instance = ArtifactInstance(definition=chalice, awakening_stars=3)
        assert instance.potential_slots == 2

    def test_legendary_five_stars_gets_three(self):
        chalice = ARTIFACTS["chalice"]
        instance = ArtifactInstance(definition=chalice, awakening_stars=5)
        assert instance.potential_slots == 3

    def test_unique_five_stars_capped_at_two(self):
        # Non-legendary cannot exceed 2 slots even at ★5
        snail = ARTIFACTS["rainbow_snail_shell"]
        instance = ArtifactInstance(definition=snail, awakening_stars=5)
        assert instance.potential_slots == 2

    def test_epic_one_star(self):
        marble = ARTIFACTS["shamaness_marble"]
        instance = ArtifactInstance(definition=marble, awakening_stars=1)
        assert instance.potential_slots == 1


# ---------------------------------------------------------------------------
# Resonance HP formula
# ---------------------------------------------------------------------------

class TestResonanceHp:
    def test_level_zero_returns_zero(self):
        assert calculate_resonance_hp(0) == 0

    def test_level_one_returns_1000(self):
        assert calculate_resonance_hp(1) == 1000

    def test_level_three_formula(self):
        # Docstring: L=3 → formula gives 1067 (int truncation)
        assert calculate_resonance_hp(3) == 1067

    def test_level_160_documented(self):
        assert calculate_resonance_hp(160) == 8112

    def test_strictly_increasing(self):
        vals = [calculate_resonance_hp(i) for i in range(1, 50)]
        assert all(vals[i] <= vals[i+1] for i in range(len(vals)-1))

    def test_large_level(self):
        # Should not raise; just verify it's positive and growing
        v_296 = calculate_resonance_hp(296)
        v_368 = calculate_resonance_hp(368)
        assert v_296 == 18263
        assert v_368 == 25939


# ---------------------------------------------------------------------------
# Resonance main stat = HP // 10
# ---------------------------------------------------------------------------

class TestResonanceMainStat:
    def test_level_zero_returns_zero(self):
        assert calculate_resonance_main_stat(0) == 0

    def test_level_one(self):
        assert calculate_resonance_main_stat(1) == 100

    def test_floor_division(self):
        # HP at L=3 is 1067 → main = 106
        assert calculate_resonance_main_stat(3) == 106

    def test_always_floor_of_hp_over_10(self):
        for lvl in [1, 2, 5, 10, 50, 100]:
            hp = calculate_resonance_hp(lvl)
            assert calculate_resonance_main_stat(lvl) == hp // 10


# ---------------------------------------------------------------------------
# Resonance upgrade cost
# ---------------------------------------------------------------------------

class TestResonanceUpgradeCost:
    def test_level_zero_returns_zero(self):
        assert calculate_resonance_upgrade_cost(0) == 0

    def test_level_one_is_1500(self):
        assert calculate_resonance_upgrade_cost(1) == 1500

    def test_level_two(self):
        # int(1500 + 18 * ((1.002^1 - 1) / 0.002))
        expected = int(1500 + 18 * ((1.002**1 - 1) / 0.002))
        assert calculate_resonance_upgrade_cost(2) == expected

    def test_strictly_increasing(self):
        costs = [calculate_resonance_upgrade_cost(i) for i in range(1, 20)]
        assert all(costs[i] <= costs[i+1] for i in range(len(costs)-1))

    def test_level_150(self):
        # Formula gives 4620 (docstring says 4621 but int() truncation yields 4620)
        assert calculate_resonance_upgrade_cost(150) == 4620


# ---------------------------------------------------------------------------
# Resonance total cost
# ---------------------------------------------------------------------------

class TestResonanceTotalCost:
    def test_same_level_is_zero(self):
        assert calculate_resonance_total_cost(5, 5) == 0

    def test_backwards_is_zero(self):
        assert calculate_resonance_total_cost(10, 5) == 0

    def test_one_level_equals_single_upgrade(self):
        assert calculate_resonance_total_cost(1, 2) == calculate_resonance_upgrade_cost(1)

    def test_two_levels(self):
        expected = calculate_resonance_upgrade_cost(1) + calculate_resonance_upgrade_cost(2)
        assert calculate_resonance_total_cost(1, 3) == expected

    def test_strictly_greater_for_wider_range(self):
        cost_1_5 = calculate_resonance_total_cost(1, 5)
        cost_1_3 = calculate_resonance_total_cost(1, 3)
        assert cost_1_5 > cost_1_3


# ---------------------------------------------------------------------------
# Hex Necklace multiplier
# ---------------------------------------------------------------------------

class TestHexMultiplier:
    def test_zero_stars_three_stacks(self):
        # per_stack=0.15, 3 stacks: 1 + 0.45 = 1.45
        assert calculate_hex_multiplier(0, 3) == pytest.approx(1.45)

    def test_one_star_three_stacks(self):
        # per_stack = 0.15 + 0.03 = 0.18, 3 stacks: 1 + 0.54 = 1.54
        assert calculate_hex_multiplier(1, 3) == pytest.approx(1.54)

    def test_five_stars_three_stacks(self):
        # per_stack = 0.15 + 5*0.03 = 0.30, 3 stacks: 1 + 0.90 = 1.90
        assert calculate_hex_multiplier(5, 3) == pytest.approx(1.90)

    def test_one_stack(self):
        # per_stack=0.15, 1 stack: 1 + 0.15 = 1.15
        assert calculate_hex_multiplier(0, 1) == pytest.approx(1.15)

    def test_stacks_beyond_three_capped(self):
        assert calculate_hex_multiplier(0, 10) == calculate_hex_multiplier(0, 3)

    def test_monotone_in_stars(self):
        mults = [calculate_hex_multiplier(s, 3) for s in range(6)]
        assert all(mults[i] < mults[i+1] for i in range(5))


# ---------------------------------------------------------------------------
# Hex average multiplier (time-weighted)
# ---------------------------------------------------------------------------

class TestHexAverageMultiplier:
    def test_zero_duration_returns_one(self):
        assert calculate_hex_average_multiplier(0, 0.0) == pytest.approx(1.0)

    def test_infinite_fight_returns_max_stacks(self):
        # Max stacks = 3, per_stack=0.15 at ★0 → 1.45
        assert calculate_hex_average_multiplier(0, float('inf')) == pytest.approx(1.45)

    def test_infinite_fight_five_stars(self):
        assert calculate_hex_average_multiplier(5, float('inf')) == pytest.approx(1.90)

    def test_short_fight_below_first_threshold(self):
        # Fight ends at 10s: all time at 0 stacks → multiplier = 1.0
        result = calculate_hex_average_multiplier(0, 10.0)
        assert result == pytest.approx(1.0)

    def test_60s_fight_weighted_average(self):
        # ★0: per_stack=0.15
        # 0-20s: 0 stacks (mult=1.00), 20-40s: 1 stack (mult=1.15), 40-60s: 2 stacks (mult=1.30)
        # weighted = (20*1.0 + 20*1.15 + 20*1.30) / 60 = (20+23+26)/60 = 69/60 = 1.15
        result = calculate_hex_average_multiplier(0, 60.0)
        assert result == pytest.approx(1.15)

    def test_long_fight_approaches_max(self):
        # At 3600s, nearly all time at 3 stacks
        result = calculate_hex_average_multiplier(0, 3600.0)
        assert result > 1.40  # Close to 1.45 max


# ---------------------------------------------------------------------------
# Fire Flower FD
# ---------------------------------------------------------------------------

class TestFireFlowerFD:
    def test_zero_stars_single_target(self):
        # per_target=0.01 at ★0
        assert calculate_fire_flower_fd(0, 1) == pytest.approx(0.01)

    def test_zero_stars_ten_targets(self):
        # 10 * 0.01 = 0.10
        assert calculate_fire_flower_fd(0, 10) == pytest.approx(0.10)

    def test_five_stars_ten_targets(self):
        # per_target = 0.01 + 5*0.002 = 0.02, 10 targets: 0.20
        assert calculate_fire_flower_fd(5, 10) == pytest.approx(0.20)

    def test_capped_at_ten_targets(self):
        assert calculate_fire_flower_fd(0, 15) == calculate_fire_flower_fd(0, 10)

    def test_zero_targets_returns_zero(self):
        assert calculate_fire_flower_fd(0, 0) == pytest.approx(0.0)

    def test_monotone_in_stars(self):
        vals = [calculate_fire_flower_fd(s, 10) for s in range(6)]
        assert all(vals[i] < vals[i+1] for i in range(5))


# ---------------------------------------------------------------------------
# Bottle of Emotions FD
# ---------------------------------------------------------------------------

class TestBottleOfEmotionsFD:
    def test_speed_below_60_returns_zero(self):
        assert calculate_bottle_of_emotions_fd(0, 59.0) == pytest.approx(0.0)

    def test_speed_exactly_60_returns_zero(self):
        assert calculate_bottle_of_emotions_fd(0, 60.0) == pytest.approx(0.0)

    def test_zero_stars_speed_90(self):
        # excess=30, ticks=10, rate=0.005, cap=0.10
        # min(0.10, 10*0.005) = min(0.10, 0.05) = 0.05
        assert calculate_bottle_of_emotions_fd(0, 90.0) == pytest.approx(0.05)

    def test_five_stars_speed_90(self):
        # excess=30, ticks=10, rate=0.010, cap=0.20
        # min(0.20, 10*0.010) = min(0.20, 0.10) = 0.10
        assert calculate_bottle_of_emotions_fd(5, 90.0) == pytest.approx(0.10)

    def test_cap_triggered(self):
        # ★0, speed=180: excess=120, ticks=40, min(0.10, 40*0.005=0.20) = 0.10 (capped)
        assert calculate_bottle_of_emotions_fd(0, 180.0) == pytest.approx(0.10)

    def test_five_stars_cap(self):
        # ★5 cap = 0.20
        assert calculate_bottle_of_emotions_fd(5, 200.0) == pytest.approx(0.20)

    def test_cap_increases_with_stars(self):
        caps = [calculate_bottle_of_emotions_fd(s, 300.0) for s in range(6)]
        assert all(caps[i] < caps[i+1] for i in range(5))

    def test_rate_increases_with_stars(self):
        # At low speed (excess=3, ticks=1), still below cap
        vals = [calculate_bottle_of_emotions_fd(s, 63.0) for s in range(6)]
        assert all(vals[i] < vals[i+1] for i in range(5))
