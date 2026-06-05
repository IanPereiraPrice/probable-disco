"""
Unit tests for game/maple_rank.py

Covers: get_main_stat_per_point, get_cumulative_main_stat,
        MapleRankConfig (stat levels, values, main stat, serialization),
        get_max_maple_rank_stats
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.maple_rank import (
    MapleRankStatType,
    MapleRankConfig,
    MAPLE_RANK_STATS,
    MAIN_STAT_SPECIAL,
    get_main_stat_per_point,
    get_cumulative_main_stat,
    get_stage_main_stat_table,
    get_max_maple_rank_stats,
    create_default_config,
)


# ---------------------------------------------------------------------------
# get_main_stat_per_point — piecewise formula
# ---------------------------------------------------------------------------

class TestGetMainStatPerPoint:
    def test_stage_0_returns_0(self):
        assert get_main_stat_per_point(0) == 0

    def test_negative_stage_returns_0(self):
        assert get_main_stat_per_point(-5) == 0

    def test_stage_1(self):
        assert get_main_stat_per_point(1) == 1

    def test_stage_2(self):
        assert get_main_stat_per_point(2) == 3

    def test_stage_7(self):
        assert get_main_stat_per_point(7) == 13  # 1 + 2*(7-1) = 13

    def test_stage_8_jumps_to_17(self):
        assert get_main_stat_per_point(8) == 17

    def test_stage_9(self):
        assert get_main_stat_per_point(9) == 21

    def test_stage_10(self):
        assert get_main_stat_per_point(10) == 25

    def test_stage_11_jumps_to_30(self):
        assert get_main_stat_per_point(11) == 30

    def test_stage_12(self):
        assert get_main_stat_per_point(12) == 35

    def test_stage_21(self):
        assert get_main_stat_per_point(21) == 80  # 30 + 5*(21-11) = 80

    def test_strictly_increasing(self):
        vals = [get_main_stat_per_point(s) for s in range(1, 22)]
        assert all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))

    def test_stages_1_to_7_increment_by_2(self):
        for s in range(1, 7):
            assert get_main_stat_per_point(s + 1) - get_main_stat_per_point(s) == 2

    def test_stages_8_to_10_increment_by_4(self):
        for s in range(8, 10):
            assert get_main_stat_per_point(s + 1) - get_main_stat_per_point(s) == 4

    def test_stages_11_plus_increment_by_5(self):
        for s in range(11, 20):
            assert get_main_stat_per_point(s + 1) - get_main_stat_per_point(s) == 5


# ---------------------------------------------------------------------------
# get_cumulative_main_stat — sum across stages
# ---------------------------------------------------------------------------

class TestGetCumulativeMainStat:
    def test_stage_1_level_0_is_zero(self):
        assert get_cumulative_main_stat(1, 0) == 0

    def test_stage_1_level_1(self):
        assert get_cumulative_main_stat(1, 1) == 1

    def test_stage_1_level_10(self):
        assert get_cumulative_main_stat(1, 10) == 10

    def test_stage_2_level_0_equals_stage_1_max(self):
        # Completing stage 1 = 10 points
        assert get_cumulative_main_stat(2, 0) == 10

    def test_stage_2_level_5(self):
        # stage 1 max (10) + stage 2 per_point (3) * 5 = 10 + 15 = 25
        assert get_cumulative_main_stat(2, 5) == 25

    def test_stage_21_level_5_matches_docstring(self):
        # Code comment says Stage 21 @ 5/10 = 6770
        assert get_cumulative_main_stat(21, 5) == 6770

    def test_stage_21_level_10_is_max_regular(self):
        # Stages 1-20 complete + stage 21 fully: 6770 + 80*5 = 7170
        assert get_cumulative_main_stat(21, 10) == 7170

    def test_monotone_in_level(self):
        for level in range(9):
            assert get_cumulative_main_stat(5, level) < get_cumulative_main_stat(5, level + 1)

    def test_monotone_in_stage(self):
        # Full completion of each stage > previous
        for s in range(1, 20):
            assert get_cumulative_main_stat(s, 10) < get_cumulative_main_stat(s + 1, 10)


# ---------------------------------------------------------------------------
# MapleRankConfig — initialization and defaults
# ---------------------------------------------------------------------------

class TestMapleRankConfigDefaults:
    def test_default_stage_is_1(self):
        config = create_default_config()
        assert config.current_stage == 1

    def test_default_main_stat_level_is_0(self):
        config = create_default_config()
        assert config.main_stat_level == 0

    def test_default_special_points_is_0(self):
        config = create_default_config()
        assert config.special_main_stat_points == 0

    def test_all_stat_levels_initialized_to_0(self):
        config = create_default_config()
        for stat_type in MAPLE_RANK_STATS:
            assert config.get_stat_level(stat_type) == 0


# ---------------------------------------------------------------------------
# MapleRankConfig.set_stat_level — clamping
# ---------------------------------------------------------------------------

class TestMapleRankConfigSetStatLevel:
    def test_set_within_bounds(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.CRIT_RATE, 5)
        assert config.get_stat_level(MapleRankStatType.CRIT_RATE) == 5

    def test_clamp_above_max(self):
        config = MapleRankConfig()
        max_level = MAPLE_RANK_STATS[MapleRankStatType.CRIT_RATE]["max_level"]
        config.set_stat_level(MapleRankStatType.CRIT_RATE, max_level + 50)
        assert config.get_stat_level(MapleRankStatType.CRIT_RATE) == max_level

    def test_clamp_below_zero(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.CRIT_RATE, -10)
        assert config.get_stat_level(MapleRankStatType.CRIT_RATE) == 0

    def test_set_to_max_level(self):
        config = MapleRankConfig()
        max_level = MAPLE_RANK_STATS[MapleRankStatType.DAMAGE_PERCENT]["max_level"]
        config.set_stat_level(MapleRankStatType.DAMAGE_PERCENT, max_level)
        assert config.get_stat_level(MapleRankStatType.DAMAGE_PERCENT) == max_level


# ---------------------------------------------------------------------------
# MapleRankConfig.get_stat_value — level × per_level
# ---------------------------------------------------------------------------

class TestMapleRankConfigGetStatValue:
    def test_zero_level_returns_zero(self):
        config = MapleRankConfig()
        assert config.get_stat_value(MapleRankStatType.CRIT_RATE) == pytest.approx(0.0)

    def test_crit_rate_1_level_equals_1_pct(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.CRIT_RATE, 1)
        assert config.get_stat_value(MapleRankStatType.CRIT_RATE) == pytest.approx(1.0)

    def test_crit_rate_max_level_equals_10_pct(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.CRIT_RATE, 10)
        assert config.get_stat_value(MapleRankStatType.CRIT_RATE) == pytest.approx(10.0)

    def test_attack_speed_max_level_equals_7_pct(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.ATTACK_SPEED, 20)
        assert config.get_stat_value(MapleRankStatType.ATTACK_SPEED) == pytest.approx(7.0, rel=1e-3)

    def test_damage_percent_max_level_equals_35_pct(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.DAMAGE_PERCENT, 50)
        assert config.get_stat_value(MapleRankStatType.DAMAGE_PERCENT) == pytest.approx(35.0)

    def test_crit_damage_max_level_equals_20_pct(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.CRIT_DAMAGE, 30)
        assert config.get_stat_value(MapleRankStatType.CRIT_DAMAGE) == pytest.approx(20.01, rel=1e-2)

    def test_min_dmg_mult_max_level_equals_11_pct(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.MIN_DMG_MULT, 20)
        assert config.get_stat_value(MapleRankStatType.MIN_DMG_MULT) == pytest.approx(11.0)

    def test_skill_damage_max_level_equals_25_pct(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.SKILL_DAMAGE, 30)
        assert config.get_stat_value(MapleRankStatType.SKILL_DAMAGE) == pytest.approx(24.99, rel=1e-2)


# ---------------------------------------------------------------------------
# MapleRankConfig — main stat calculations
# ---------------------------------------------------------------------------

class TestMapleRankConfigMainStat:
    def test_regular_main_stat_default_is_zero(self):
        config = MapleRankConfig()
        assert config.get_regular_main_stat() == 0

    def test_regular_main_stat_stage_1_level_5(self):
        config = MapleRankConfig(current_stage=1, main_stat_level=5)
        assert config.get_regular_main_stat() == 5  # 1 per point * 5

    def test_special_main_stat_base_is_300(self):
        config = MapleRankConfig(special_main_stat_points=0)
        assert config.get_special_main_stat() == 300

    def test_special_main_stat_20_points(self):
        config = MapleRankConfig(special_main_stat_points=20)
        assert config.get_special_main_stat() == 400  # 300 + 20*5

    def test_special_main_stat_max_is_1100(self):
        config = MapleRankConfig(special_main_stat_points=160)
        assert config.get_special_main_stat() == 1100  # 300 + 160*5

    def test_total_main_stat_is_sum(self):
        config = MapleRankConfig(
            current_stage=21, main_stat_level=5, special_main_stat_points=0
        )
        assert config.get_total_main_stat() == config.get_regular_main_stat() + 300

    def test_total_main_stat_stage_21_level_10_special_max(self):
        config = MapleRankConfig(
            current_stage=21, main_stat_level=10, special_main_stat_points=160
        )
        assert config.get_total_main_stat() == 7170 + 1100  # 8270


# ---------------------------------------------------------------------------
# MapleRankConfig.get_all_stats — dict output
# ---------------------------------------------------------------------------

class TestMapleRankConfigGetAllStats:
    def test_returns_dict_with_expected_keys(self):
        config = MapleRankConfig()
        stats = config.get_all_stats()
        assert "main_stat_flat" in stats
        assert "crit_rate" in stats
        assert "damage_percent" in stats
        assert "boss_damage" in stats
        assert "attack_speed" in stats

    def test_main_stat_flat_includes_special_base(self):
        # Even at stage 1, level 0: special base = 300
        config = MapleRankConfig()
        stats = config.get_all_stats()
        assert stats["main_stat_flat"] == pytest.approx(300.0)

    def test_crit_rate_reflects_stat_level(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.CRIT_RATE, 7)
        stats = config.get_all_stats()
        assert stats["crit_rate"] == pytest.approx(7.0)

    def test_all_numeric_values(self):
        config = MapleRankConfig()
        for key, val in config.get_all_stats().items():
            assert isinstance(val, (int, float)), f"{key} is not numeric"


# ---------------------------------------------------------------------------
# MapleRankConfig serialization — to_dict / from_dict round-trip
# ---------------------------------------------------------------------------

class TestMapleRankConfigSerialization:
    def test_round_trip_preserves_stage(self):
        config = MapleRankConfig(current_stage=15, main_stat_level=7)
        restored = MapleRankConfig.from_dict(config.to_dict())
        assert restored.current_stage == 15
        assert restored.main_stat_level == 7

    def test_round_trip_preserves_special_points(self):
        config = MapleRankConfig(special_main_stat_points=80)
        restored = MapleRankConfig.from_dict(config.to_dict())
        assert restored.special_main_stat_points == 80

    def test_round_trip_preserves_stat_levels(self):
        config = MapleRankConfig()
        config.set_stat_level(MapleRankStatType.DAMAGE_PERCENT, 35)
        config.set_stat_level(MapleRankStatType.BOSS_DAMAGE, 20)
        restored = MapleRankConfig.from_dict(config.to_dict())
        assert restored.get_stat_level(MapleRankStatType.DAMAGE_PERCENT) == 35
        assert restored.get_stat_level(MapleRankStatType.BOSS_DAMAGE) == 20

    def test_from_empty_dict_uses_defaults(self):
        config = MapleRankConfig.from_dict({})
        assert config.current_stage == 1
        assert config.main_stat_level == 0
        assert config.special_main_stat_points == 0

    def test_to_dict_has_expected_keys(self):
        config = MapleRankConfig()
        d = config.to_dict()
        assert "current_stage" in d
        assert "main_stat_level" in d
        assert "special_main_stat_points" in d
        assert "stat_levels" in d


# ---------------------------------------------------------------------------
# get_max_maple_rank_stats — fully maxed config
# ---------------------------------------------------------------------------

class TestGetMaxMapleRankStats:
    def test_returns_dict(self):
        stats = get_max_maple_rank_stats()
        assert isinstance(stats, dict)

    def test_crit_rate_is_10_pct(self):
        stats = get_max_maple_rank_stats()
        assert stats["crit_rate"] == pytest.approx(10.0)

    def test_damage_percent_is_35_pct(self):
        stats = get_max_maple_rank_stats()
        assert stats["damage_percent"] == pytest.approx(35.0)

    def test_attack_speed_is_7_pct(self):
        stats = get_max_maple_rank_stats()
        assert stats["attack_speed"] == pytest.approx(7.0, rel=1e-3)

    def test_main_stat_flat_is_8270(self):
        # regular stage 21 max (7170) + special max (1100)
        stats = get_max_maple_rank_stats()
        assert stats["main_stat_flat"] == pytest.approx(8270)
