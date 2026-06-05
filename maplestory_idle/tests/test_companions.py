"""
Unit tests for game/companions.py

Covers: get_2nd_job_main_stat, get_4th_job_damage, CompanionDefinition stat
formulas (on-equip linear, inventory by tier), level clamping, CompanionInstance.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.companions import (
    CompanionDefinition,
    CompanionInstance,
    CompanionJob,
    JobAdvancement,
    OnEquipStatType,
    MAX_LEVELS,
    SECOND_JOB_MAIN_STAT_LOOKUP,
    get_2nd_job_main_stat,
    get_4th_job_damage,
    COMPANIONS,
)


# ---------------------------------------------------------------------------
# get_2nd_job_main_stat — lookup table + ratio extrapolation
# ---------------------------------------------------------------------------

class TestGet2ndJobMainStat:
    def test_level_zero_returns_zero(self):
        assert get_2nd_job_main_stat(0) == pytest.approx(0.0)

    def test_lookup_level_29(self):
        assert get_2nd_job_main_stat(29) == pytest.approx(577.0)

    def test_lookup_level_30(self):
        assert get_2nd_job_main_stat(30) == pytest.approx(601.0)

    def test_extrapolation_level_15(self):
        # ratio scaling: (15/30) * 601
        expected = (15 / 30.0) * 601
        assert get_2nd_job_main_stat(15) == pytest.approx(expected)

    def test_extrapolation_level_1(self):
        expected = (1 / 30.0) * 601
        assert get_2nd_job_main_stat(1) == pytest.approx(expected)

    def test_monotone_approx(self):
        # Values should generally increase from L1 to L30
        vals = [get_2nd_job_main_stat(i) for i in range(1, 31)]
        assert vals[0] < vals[-1]


# ---------------------------------------------------------------------------
# get_4th_job_damage — data mine lookup table (SupporterLevelStatFactorTable Factor[6])
# ---------------------------------------------------------------------------

class TestGet4thJobDamage:
    def test_level_1(self):
        assert get_4th_job_damage(1) == pytest.approx(10.0)

    def test_level_4(self):
        # Factor[6][4] = 1609 → 100 * 1609 / 1000 / 10 = 16.09
        assert get_4th_job_damage(4) == pytest.approx(16.09)

    def test_level_5(self):
        # Factor[6][5] = 1818 → 18.18
        assert get_4th_job_damage(5) == pytest.approx(18.18)

    def test_level_6(self):
        # Factor[6][6] = 2030 → 20.30
        assert get_4th_job_damage(6) == pytest.approx(20.30)

    def test_level_10(self):
        # Factor[6][10] = 2911 → 29.11
        assert get_4th_job_damage(10) == pytest.approx(29.11)

    def test_strictly_increasing(self):
        vals = [get_4th_job_damage(i) for i in range(1, 11)]
        assert all(vals[i] < vals[i+1] for i in range(len(vals)-1))

    def test_super_linear_growth(self):
        # Quadratic grows faster than linear
        d1 = get_4th_job_damage(1)
        d5 = get_4th_job_damage(5)
        d10 = get_4th_job_damage(10)
        # If linear: d10 - d5 == d5 - d1; quadratic: d10-d5 > d5-d1
        assert (d10 - d5) > (d5 - d1)


# ---------------------------------------------------------------------------
# CompanionDefinition.max_level
# ---------------------------------------------------------------------------

class TestCompanionMaxLevel:
    def _make(self, advancement: JobAdvancement) -> CompanionDefinition:
        return CompanionDefinition(
            name="Test", job=CompanionJob.BOWMASTER,
            advancement=advancement, on_equip_type=OnEquipStatType.BOSS_DAMAGE,
        )

    def test_basic_max_100(self):
        assert self._make(JobAdvancement.BASIC).max_level == 100

    def test_first_max_50(self):
        assert self._make(JobAdvancement.FIRST).max_level == 50

    def test_second_max_30(self):
        assert self._make(JobAdvancement.SECOND).max_level == 30

    def test_third_max_10(self):
        assert self._make(JobAdvancement.THIRD).max_level == 10

    def test_fourth_max_10(self):
        assert self._make(JobAdvancement.FOURTH).max_level == 10


# ---------------------------------------------------------------------------
# CompanionDefinition.get_on_equip_value — linear, clamped
# ---------------------------------------------------------------------------

class TestCompanionOnEquip:
    def _make_3rd(self, stat_type: OnEquipStatType) -> CompanionDefinition:
        return CompanionDefinition(
            name="Test", job=CompanionJob.BOWMASTER,
            advancement=JobAdvancement.THIRD, on_equip_type=stat_type,
        )

    def _make_2nd(self, stat_type: OnEquipStatType) -> CompanionDefinition:
        return CompanionDefinition(
            name="Test", job=CompanionJob.BOWMASTER,
            advancement=JobAdvancement.SECOND, on_equip_type=stat_type,
        )

    def test_boss_damage_3rd_level1(self):
        comp = self._make_3rd(OnEquipStatType.BOSS_DAMAGE)
        # base=10.0, per_level=1.0 → L1 = 10.0
        assert comp.get_on_equip_value(1) == pytest.approx(10.0)

    def test_boss_damage_3rd_level10(self):
        comp = self._make_3rd(OnEquipStatType.BOSS_DAMAGE)
        # 10.0 + 9 * 1.0 = 19.0
        assert comp.get_on_equip_value(10) == pytest.approx(19.0)

    def test_boss_damage_2nd_level1(self):
        comp = self._make_2nd(OnEquipStatType.BOSS_DAMAGE)
        # data mine: base=5.0, per_level=0.500 → L1 = 5.0
        assert comp.get_on_equip_value(1) == pytest.approx(5.0)

    def test_boss_damage_2nd_level30(self):
        comp = self._make_2nd(OnEquipStatType.BOSS_DAMAGE)
        # 5.0 + 29 * 0.500 = 5 + 14.5 = 19.5
        assert comp.get_on_equip_value(30) == pytest.approx(19.5)

    def test_level_clamped_to_max(self):
        comp = self._make_3rd(OnEquipStatType.BOSS_DAMAGE)
        # max_level=10; calling with L100 should give same as L10
        assert comp.get_on_equip_value(100) == comp.get_on_equip_value(10)

    def test_level_clamped_to_min_1(self):
        comp = self._make_3rd(OnEquipStatType.BOSS_DAMAGE)
        assert comp.get_on_equip_value(0) == comp.get_on_equip_value(1)

    def test_attack_speed_3rd_same_formula(self):
        comp = self._make_3rd(OnEquipStatType.ATTACK_SPEED)
        assert comp.get_on_equip_value(1) == pytest.approx(10.0)
        assert comp.get_on_equip_value(10) == pytest.approx(19.0)

    def test_crit_rate_2nd_lower_base(self):
        # F/P Arch Mage: data mine base=3.0, per_level=0.300 → L1=3.0, L30=11.7
        comp = CompanionDefinition(
            name="FP Test", job=CompanionJob.ARCH_MAGE_FP,
            advancement=JobAdvancement.SECOND, on_equip_type=OnEquipStatType.CRIT_RATE,
        )
        assert comp.get_on_equip_value(1) == pytest.approx(3.0)
        assert comp.get_on_equip_value(30) == pytest.approx(11.7)


# ---------------------------------------------------------------------------
# CompanionDefinition.get_inventory_stats — by tier
# ---------------------------------------------------------------------------

class TestCompanionInventoryStats:
    def _make(self, advancement: JobAdvancement) -> CompanionDefinition:
        return CompanionDefinition(
            name="Test", job=CompanionJob.BOWMASTER,
            advancement=advancement, on_equip_type=OnEquipStatType.BOSS_DAMAGE,
        )

    def test_basic_level_zero_returns_empty(self):
        comp = self._make(JobAdvancement.BASIC)
        assert comp.get_inventory_stats(0) == {}

    def test_basic_attack_flat(self):
        comp = self._make(JobAdvancement.BASIC)
        stats = comp.get_inventory_stats(100)
        # 100 * 17.03 = 1703
        assert stats["attack_flat"] == pytest.approx(1703.0)

    def test_basic_max_hp(self):
        comp = self._make(JobAdvancement.BASIC)
        stats = comp.get_inventory_stats(100)
        assert stats["max_hp"] == pytest.approx(100 * 170.34)

    def test_first_attack_flat_level_50(self):
        comp = self._make(JobAdvancement.FIRST)
        stats = comp.get_inventory_stats(50)
        # 50 * 19.02 = 951
        assert stats["attack_flat"] == pytest.approx(951.0)

    def test_second_main_stat_level_30(self):
        comp = self._make(JobAdvancement.SECOND)
        stats = comp.get_inventory_stats(30)
        assert stats["main_stat_flat"] == pytest.approx(601.0)

    def test_second_main_stat_level_29(self):
        comp = self._make(JobAdvancement.SECOND)
        stats = comp.get_inventory_stats(29)
        assert stats["main_stat_flat"] == pytest.approx(577.0)

    def test_third_damage_pct_level_1(self):
        comp = self._make(JobAdvancement.THIRD)
        stats = comp.get_inventory_stats(1)
        assert stats["damage_pct"] == pytest.approx(5.0)

    def test_third_damage_pct_level_10(self):
        comp = self._make(JobAdvancement.THIRD)
        stats = comp.get_inventory_stats(10)
        # 5 + (10-1)*1.0 = 14
        assert stats["damage_pct"] == pytest.approx(14.0)

    def test_fourth_damage_pct_level_1(self):
        comp = self._make(JobAdvancement.FOURTH)
        stats = comp.get_inventory_stats(1)
        assert stats["damage_pct"] == pytest.approx(10.0)

    def test_fourth_damage_pct_level_5(self):
        comp = self._make(JobAdvancement.FOURTH)
        stats = comp.get_inventory_stats(5)
        # data mine: Factor[6][5]=1818 → 18.18
        assert stats["damage_pct"] == pytest.approx(18.18)

    def test_inventory_level_clamped_to_max(self):
        comp = self._make(JobAdvancement.THIRD)
        # max_level=10; L20 should give same as L10
        assert comp.get_inventory_stats(20) == comp.get_inventory_stats(10)

    def test_third_has_no_attack_key(self):
        comp = self._make(JobAdvancement.THIRD)
        stats = comp.get_inventory_stats(5)
        assert "attack_flat" not in stats

    def test_fourth_has_no_attack_key(self):
        comp = self._make(JobAdvancement.FOURTH)
        stats = comp.get_inventory_stats(5)
        assert "attack_flat" not in stats


# ---------------------------------------------------------------------------
# CompanionInstance level clamping
# ---------------------------------------------------------------------------

class TestCompanionInstanceClamping:
    def _make_def(self, advancement: JobAdvancement) -> CompanionDefinition:
        return CompanionDefinition(
            name="Test", job=CompanionJob.BOWMASTER,
            advancement=advancement, on_equip_type=OnEquipStatType.BOSS_DAMAGE,
        )

    def test_level_above_max_clamped(self):
        defn = self._make_def(JobAdvancement.THIRD)  # max=10
        instance = CompanionInstance(definition=defn, level=50)
        assert instance.level == 10

    def test_level_zero_allowed(self):
        defn = self._make_def(JobAdvancement.THIRD)
        instance = CompanionInstance(definition=defn, level=0)
        assert instance.level == 0

    def test_negative_level_clamped_to_zero(self):
        defn = self._make_def(JobAdvancement.THIRD)
        instance = CompanionInstance(definition=defn, level=-5)
        assert instance.level == 0

    def test_normal_level_unchanged(self):
        defn = self._make_def(JobAdvancement.THIRD)
        instance = CompanionInstance(definition=defn, level=7)
        assert instance.level == 7

    def test_level_zero_on_equip_returns_zero(self):
        defn = self._make_def(JobAdvancement.THIRD)
        instance = CompanionInstance(definition=defn, level=0)
        assert instance.get_on_equip_value() == 0

    def test_level_zero_inventory_returns_empty(self):
        defn = self._make_def(JobAdvancement.THIRD)
        instance = CompanionInstance(definition=defn, level=0)
        assert instance.get_inventory_stats() == {}


# ---------------------------------------------------------------------------
# COMPANIONS registry sanity checks
# ---------------------------------------------------------------------------

class TestCompanionsRegistry:
    def test_companions_dict_not_empty(self):
        assert len(COMPANIONS) > 0

    def test_all_companions_have_valid_advancement(self):
        for key, comp in COMPANIONS.items():
            assert isinstance(comp.advancement, JobAdvancement), f"{key} has invalid advancement"

    def test_all_companions_have_valid_on_equip_type(self):
        for key, comp in COMPANIONS.items():
            assert isinstance(comp.on_equip_type, OnEquipStatType), f"{key} has invalid on_equip_type"

    def test_all_companions_have_nonzero_max_level(self):
        for key, comp in COMPANIONS.items():
            assert comp.max_level > 0, f"{key} has max_level=0"
