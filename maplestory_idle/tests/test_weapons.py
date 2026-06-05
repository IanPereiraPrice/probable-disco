"""
Unit tests for game/weapons.py

Covers: get_level_multiplier, get_base_atk, get_inventory_ratio,
        get_attack_speed_bonus, calculate_level_cost, calculate_total_cost,
        calculate_weapon_atk_str / calculate_weapon_atk,
        WeaponDefinition, WeaponInstance.get_stats(), WeaponConfig
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.weapons import (
    WeaponRarity,
    WeaponDefinition,
    WeaponInstance,
    WeaponConfig,
    BASE_ATK,
    INVENTORY_RATIO_LOW,
    INVENTORY_RATIO_HIGH,
    get_inventory_ratio,
    get_level_multiplier,
    get_base_atk,
    get_cost_multiplier,
    get_base_cost,
    calculate_level_cost,
    calculate_total_cost,
    calculate_weapon_atk_str,
    calculate_weapon_atk,
    get_attack_speed_bonus,
    create_weapon_instance,
)


# ---------------------------------------------------------------------------
# get_level_multiplier — piecewise formula
# ---------------------------------------------------------------------------

class TestGetLevelMultiplier:
    def test_level_0_returns_zero(self):
        assert get_level_multiplier(0) == pytest.approx(0.0)

    def test_negative_level_returns_zero(self):
        assert get_level_multiplier(-5) == pytest.approx(0.0)

    def test_level_1_is_1(self):
        # 0.997 + 0.003*1 = 1.0
        assert get_level_multiplier(1) == pytest.approx(1.0)

    def test_level_100_boundary(self):
        # 0.997 + 0.003*100 = 1.297
        assert get_level_multiplier(100) == pytest.approx(1.297)

    def test_level_101_switches_formula(self):
        # 0.596 + 0.007*101 = 0.596 + 0.707 = 1.303
        assert get_level_multiplier(101) == pytest.approx(1.303)

    def test_level_130_boundary(self):
        # 0.596 + 0.007*130 = 0.596 + 0.91 = 1.506
        assert get_level_multiplier(130) == pytest.approx(1.506)

    def test_level_131_switches_formula(self):
        # 0.466 + 0.008*131 = 0.466 + 1.048 = 1.514
        assert get_level_multiplier(131) == pytest.approx(1.514)

    def test_level_155_boundary(self):
        # 0.466 + 0.008*155 = 0.466 + 1.24 = 1.706
        assert get_level_multiplier(155) == pytest.approx(1.706)

    def test_level_156_switches_formula(self):
        # 0.311 + 0.009*156 = 0.311 + 1.404 = 1.715
        assert get_level_multiplier(156) == pytest.approx(1.715)

    def test_level_175_boundary(self):
        # 0.311 + 0.009*175 = 0.311 + 1.575 = 1.886
        assert get_level_multiplier(175) == pytest.approx(1.886)

    def test_level_176_switches_formula(self):
        # 0.136 + 0.010*176 = 0.136 + 1.76 = 1.896
        assert get_level_multiplier(176) == pytest.approx(1.896)

    def test_level_200_max(self):
        # 0.136 + 0.010*200 = 0.136 + 2.0 = 2.136
        assert get_level_multiplier(200) == pytest.approx(2.136)

    def test_strictly_increasing(self):
        vals = [get_level_multiplier(i) for i in range(1, 201)]
        assert all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))


# ---------------------------------------------------------------------------
# get_base_atk — lookup table
# ---------------------------------------------------------------------------

class TestGetBaseAtk:
    def test_normal_t4(self):
        assert get_base_atk("normal", 4) == pytest.approx(15.0)

    def test_normal_t1(self):
        assert get_base_atk("normal", 1) == pytest.approx(25.0)

    def test_mystic_t1(self):
        assert get_base_atk("mystic", 1) == pytest.approx(3810.6)

    def test_legendary_t4(self):
        assert get_base_atk("legendary", 4) == pytest.approx(554.3)

    def test_uppercase_rarity_handled(self):
        # Should normalize to lowercase
        assert get_base_atk("NORMAL", 4) == pytest.approx(15.0)

    def test_unknown_key_returns_default(self):
        # Default is 15.0 (Normal T4)
        assert get_base_atk("unknown", 1) == pytest.approx(15.0)

    def test_higher_tier_is_lower_value(self):
        # T1 > T4 within same rarity (T1 is "highest")
        assert get_base_atk("epic", 1) > get_base_atk("epic", 4)

    def test_higher_rarity_is_higher_value(self):
        assert get_base_atk("legendary", 1) > get_base_atk("unique", 1)


# ---------------------------------------------------------------------------
# get_inventory_ratio — rarity-based ratio
# ---------------------------------------------------------------------------

class TestGetInventoryRatio:
    def test_normal_uses_low_ratio(self):
        assert get_inventory_ratio("normal") == pytest.approx(INVENTORY_RATIO_LOW)

    def test_rare_uses_low_ratio(self):
        assert get_inventory_ratio("rare") == pytest.approx(INVENTORY_RATIO_LOW)

    def test_epic_uses_low_ratio(self):
        assert get_inventory_ratio("epic") == pytest.approx(INVENTORY_RATIO_LOW)

    def test_unique_uses_low_ratio(self):
        assert get_inventory_ratio("unique") == pytest.approx(INVENTORY_RATIO_LOW)

    def test_legendary_uses_high_ratio(self):
        assert get_inventory_ratio("legendary") == pytest.approx(INVENTORY_RATIO_HIGH)

    def test_mystic_uses_high_ratio(self):
        assert get_inventory_ratio("mystic") == pytest.approx(INVENTORY_RATIO_HIGH)

    def test_ancient_uses_high_ratio(self):
        assert get_inventory_ratio("ancient") == pytest.approx(INVENTORY_RATIO_HIGH)

    def test_low_ratio_is_approximately_28_6_pct(self):
        assert INVENTORY_RATIO_LOW == pytest.approx(1 / 3.5)

    def test_high_ratio_is_25_pct(self):
        assert INVENTORY_RATIO_HIGH == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# get_attack_speed_bonus — fixed per-rarity bonuses
# ---------------------------------------------------------------------------

class TestGetAttackSpeedBonus:
    def test_normal_no_bonus(self):
        assert get_attack_speed_bonus("normal") == pytest.approx(0.0)

    def test_rare_no_bonus(self):
        assert get_attack_speed_bonus("rare") == pytest.approx(0.0)

    def test_epic_2_pct(self):
        assert get_attack_speed_bonus("epic") == pytest.approx(2.0)

    def test_unique_3_pct(self):
        assert get_attack_speed_bonus("unique") == pytest.approx(3.0)

    def test_legendary_4_pct(self):
        assert get_attack_speed_bonus("legendary") == pytest.approx(4.0)

    def test_mystic_6_pct(self):
        assert get_attack_speed_bonus("mystic") == pytest.approx(6.0)

    def test_ancient_8_pct(self):
        assert get_attack_speed_bonus("ancient") == pytest.approx(8.0)

    def test_unknown_rarity_returns_zero(self):
        assert get_attack_speed_bonus("unknown") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# calculate_level_cost and calculate_total_cost
# ---------------------------------------------------------------------------

class TestCalculateLevelCost:
    def test_normal_t4_from_level_1(self):
        # base=10, cost_mult at level 1 = 1.01^0 = 1.0 → ceil(10 * 1.0) = 10
        assert calculate_level_cost("normal", 4, 1) == 10

    def test_normal_t4_from_level_2(self):
        # base=10, cost_mult at level 2 = 1.01^1 = 1.01 → ceil(10.1) = 11
        assert calculate_level_cost("normal", 4, 2) == 11

    def test_legendary_t4_from_level_1(self):
        # base=1470, mult=1.0 → 1470
        assert calculate_level_cost("legendary", 4, 1) == 1470

    def test_cost_increases_with_level(self):
        c10 = calculate_level_cost("epic", 2, 10)
        c50 = calculate_level_cost("epic", 2, 50)
        c100 = calculate_level_cost("epic", 2, 100)
        assert c10 < c50 < c100

    def test_higher_tier_costs_less_than_lower_tier(self):
        # T1 > T4 base cost, so T1 level costs more
        t1 = calculate_level_cost("epic", 1, 10)
        t4 = calculate_level_cost("epic", 4, 10)
        assert t1 > t4


class TestCalculateTotalCost:
    def test_same_level_returns_zero(self):
        assert calculate_total_cost("normal", 4, 5, 5) == 0

    def test_backwards_returns_zero(self):
        assert calculate_total_cost("normal", 4, 10, 5) == 0

    def test_one_level_equals_single_upgrade_cost(self):
        single = calculate_level_cost("normal", 4, 3)
        total = calculate_total_cost("normal", 4, 3, 4)
        assert total == single

    def test_two_levels_sums_correctly(self):
        c1 = calculate_level_cost("normal", 4, 1)
        c2 = calculate_level_cost("normal", 4, 2)
        total = calculate_total_cost("normal", 4, 1, 3)
        assert total == c1 + c2

    def test_monotone_in_range(self):
        t1_10 = calculate_total_cost("legendary", 1, 1, 10)
        t1_50 = calculate_total_cost("legendary", 1, 1, 50)
        t1_100 = calculate_total_cost("legendary", 1, 1, 100)
        assert t1_10 < t1_50 < t1_100


# ---------------------------------------------------------------------------
# calculate_weapon_atk_str — main ATK% formula
# ---------------------------------------------------------------------------

class TestCalculateWeaponAtkStr:
    def test_returns_expected_keys(self):
        result = calculate_weapon_atk_str("normal", 4, 1)
        assert "on_equip_atk" in result
        assert "inventory_atk" in result
        assert "base_atk" in result
        assert "level_multiplier" in result
        assert "total_atk" in result

    def test_normal_t4_level_1_on_equip(self):
        # base=15.0, mult=1.0 → 15.0
        result = calculate_weapon_atk_str("normal", 4, 1)
        assert result["on_equip_atk"] == pytest.approx(15.0, rel=1e-3)

    def test_normal_t4_level_1_inventory_ratio(self):
        # 15.0 * (1/3.5) ≈ 4.3
        result = calculate_weapon_atk_str("normal", 4, 1)
        assert result["inventory_atk"] == pytest.approx(15.0 * INVENTORY_RATIO_LOW, rel=1e-2)

    def test_legendary_uses_high_inventory_ratio(self):
        result = calculate_weapon_atk_str("legendary", 1, 100)
        base = get_base_atk("legendary", 1)
        mult = get_level_multiplier(100)
        expected_inv = base * mult * INVENTORY_RATIO_HIGH
        assert result["inventory_atk"] == pytest.approx(expected_inv, rel=1e-2)

    def test_total_is_on_equip_plus_inventory(self):
        result = calculate_weapon_atk_str("mystic", 3, 80)
        assert result["total_atk"] == pytest.approx(
            result["on_equip_atk"] + result["inventory_atk"], rel=1e-3
        )

    def test_higher_level_gives_more_atk(self):
        r50 = calculate_weapon_atk_str("mystic", 1, 50)
        r100 = calculate_weapon_atk_str("mystic", 1, 100)
        assert r100["on_equip_atk"] > r50["on_equip_atk"]

    def test_enum_version_matches_str_version(self):
        str_result = calculate_weapon_atk_str("legendary", 2, 80)
        enum_result = calculate_weapon_atk(WeaponRarity.LEGENDARY, 2, 80)
        assert enum_result["on_equip_atk"] == pytest.approx(str_result["on_equip_atk"])
        assert enum_result["inventory_atk"] == pytest.approx(str_result["inventory_atk"])


# ---------------------------------------------------------------------------
# WeaponInstance.get_stats() — uses calculate_weapon_atk internally
# ---------------------------------------------------------------------------

class TestWeaponInstanceGetStats:
    def test_get_stats_matches_calculate_weapon_atk(self):
        weapon = create_weapon_instance("mystic", 1, 130, "bow")
        stats = weapon.get_stats()
        expected = calculate_weapon_atk(WeaponRarity.MYSTIC, 1, 130)
        assert stats["on_equip_atk"] == pytest.approx(expected["on_equip_atk"])

    def test_create_weapon_instance_sets_level(self):
        weapon = create_weapon_instance("legendary", 2, 80)
        assert weapon.level == 80

    def test_create_weapon_instance_is_not_equipped_by_default(self):
        weapon = create_weapon_instance("legendary", 2, 80)
        assert weapon.is_equipped is False

    def test_create_weapon_instance_equipped_flag(self):
        weapon = create_weapon_instance("legendary", 2, 80, "bow", is_equipped=True)
        assert weapon.is_equipped is True


# ---------------------------------------------------------------------------
# WeaponDefinition.get_rate_per_level — known bug (undefined function)
# ---------------------------------------------------------------------------

class TestWeaponDefinitionBug:
    @pytest.mark.xfail(reason="get_rate_per_level function not defined in weapons.py — known missing implementation")
    def test_get_rate_per_level_raises(self):
        defn = WeaponDefinition("Test", WeaponRarity.MYSTIC, 1)
        defn.get_rate_per_level()  # Should fail: calls undefined get_rate_per_level()


# ---------------------------------------------------------------------------
# WeaponConfig — aggregate ATK%
# ---------------------------------------------------------------------------

class TestWeaponConfig:
    def _make_config(self) -> WeaponConfig:
        config = WeaponConfig()
        config.equipped = create_weapon_instance("legendary", 1, 100, is_equipped=True)
        config.inventory.append(config.equipped)
        config.inventory.append(create_weapon_instance("epic", 2, 50))
        return config

    def test_no_equipped_gives_zero_equipped_atk(self):
        config = WeaponConfig()
        # get_equipped_atk uses self.equipped.get_on_equip_atk() which is buggy
        # but with no equipped weapon, returns 0 before calling it
        assert config.get_equipped_atk() == pytest.approx(0.0)

    def test_no_inventory_gives_zero_inventory_atk(self):
        config = WeaponConfig()
        assert config.get_total_inventory_atk() == pytest.approx(0.0)

    @pytest.mark.xfail(reason="get_rate_per_level undefined, making WeaponInstance.get_inventory_atk() fail")
    def test_inventory_atk_sums_weapons(self):
        config = self._make_config()
        config.get_total_inventory_atk()

    def test_get_all_stats_returns_expected_keys(self):
        config = WeaponConfig()
        stats = config.get_all_stats()
        assert "weapon_atk_percent" in stats
        assert "weapon_equipped_atk" in stats
        assert "weapon_inventory_atk" in stats

    def test_empty_config_all_stats_zero(self):
        config = WeaponConfig()
        stats = config.get_all_stats()
        assert stats["weapon_atk_percent"] == pytest.approx(0.0)
        assert stats["weapon_equipped_atk"] == pytest.approx(0.0)
        assert stats["weapon_inventory_atk"] == pytest.approx(0.0)
