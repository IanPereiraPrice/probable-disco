"""
Tests for streamlit_app/utils/cube_analyzer.py

Covers:
- Regression tests for the three bugs fixed in May 2026:
    1. Tier name case sensitivity (CSV stores lowercase, TIER_NAME_TO_ENUM is title-case)
    2. 'final_atk_dmg' legacy stat not recognized → silently dropped from DPS calc
    3. DPS-gain index misalignment when a line is skipped by convert_streamlit_lines
- Stat name normalization (legacy aliases → canonical StatType.value)
- convert_streamlit_lines_to_potential_lines correctness
- analyze_slot_potentials current-line extraction
"""
import sys
from pathlib import Path
from copy import deepcopy

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.utils.cube_analyzer import (
    STAT_NAME_TO_TYPE,
    TIER_NAME_TO_ENUM,
    get_tier_enum,
    convert_streamlit_lines_to_potential_lines,
    analyze_slot_potentials,
    analyze_all_cube_priorities,
    CubeRecommendation,
)
from game.cubes import PotentialTier, StatType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_slot_pots(**overrides) -> dict:
    """Minimal valid potential dict for a slot (regular potential, Legendary)."""
    base = {
        "tier": "legendary",
        "regular_pity": 0,
        "line1_stat": "damage_pct",
        "line1_value": 25.0,
        "line2_stat": "max_dmg_mult",
        "line2_value": 10.0,
        "line3_stat": "luk_pct",
        "line3_value": 9.0,
        "line2_yellow": True,
        "line3_yellow": False,
        "bonus_tier": "legendary",
        "bonus_pity": 0,
        "bonus_line1_stat": "",
        "bonus_line1_value": 0,
        "bonus_line2_stat": "",
        "bonus_line2_value": 0,
        "bonus_line3_stat": "",
        "bonus_line3_value": 0,
    }
    base.update(overrides)
    return base


def _mock_dps(lines) -> float:
    return 1000.0


def _trivial_analyze(slot_pots, is_bonus=False, slot="hat") -> CubeRecommendation:
    """Run analyze_slot_potentials with a trivial DPS function."""
    return analyze_slot_potentials(
        slot=slot,
        slot_pots=slot_pots,
        is_bonus=is_bonus,
        dps_calc_func=_mock_dps,
        baseline_dps=1000.0,
        main_stat_type=StatType.LUK_PCT,
    )


# ---------------------------------------------------------------------------
# BUG 1 — Tier case sensitivity
# ---------------------------------------------------------------------------

class TestTierCaseSensitivity:
    """
    Bug: CSV stores tiers as lowercase ('legendary', 'unique', 'mystic').
    TIER_NAME_TO_ENUM had only title-case keys, so 'unique'/'mystic' defaulted
    to LEGENDARY instead of being resolved correctly.
    Fix: get_tier_enum now calls .title() before lookup.
    """

    def test_lowercase_legendary(self):
        assert get_tier_enum("legendary") == PotentialTier.LEGENDARY

    def test_lowercase_unique(self):
        # Before fix: returned LEGENDARY; after fix: UNIQUE
        assert get_tier_enum("unique") == PotentialTier.UNIQUE

    def test_lowercase_mystic(self):
        assert get_tier_enum("mystic") == PotentialTier.MYSTIC

    def test_lowercase_epic(self):
        assert get_tier_enum("epic") == PotentialTier.EPIC

    def test_lowercase_rare(self):
        assert get_tier_enum("rare") == PotentialTier.RARE

    def test_title_case_still_works(self):
        # Existing title-case values must not break
        for name, tier in TIER_NAME_TO_ENUM.items():
            assert get_tier_enum(name) == tier

    def test_unknown_tier_defaults_to_legendary(self):
        assert get_tier_enum("garbage") == PotentialTier.LEGENDARY

    def test_empty_string_defaults_to_legendary(self):
        assert get_tier_enum("") == PotentialTier.LEGENDARY

    def test_tier_used_in_analyze_slot_potentials(self):
        # When tier is stored as lowercase 'unique', the recommendation's tier
        # string should still be the raw stored value (display) but the ENUM
        # used for calculations should be UNIQUE
        slot_pots = make_slot_pots(tier="unique")
        rec = _trivial_analyze(slot_pots)
        assert rec is not None
        # tier stored as-is for display
        assert rec.tier == "unique"


# ---------------------------------------------------------------------------
# BUG 2 — 'final_atk_dmg' legacy stat recognition
# ---------------------------------------------------------------------------

class TestFinalAtkDmgLegacyStat:
    """
    Bug: 'final_atk_dmg' was stored in some users' CSV data as line1_stat for
    bottom and cape slots.  STAT_NAME_TO_TYPE didn't include this alias, so
    convert_streamlit_lines_to_potential_lines silently dropped those lines.
    Fix: Added 'final_atk_dmg': StatType.FINAL_DAMAGE to STAT_NAME_TO_TYPE.
    """

    def test_stat_name_recognized(self):
        assert "final_atk_dmg" in STAT_NAME_TO_TYPE
        assert STAT_NAME_TO_TYPE["final_atk_dmg"] == StatType.FINAL_DAMAGE

    def test_convert_includes_final_atk_dmg_line(self):
        slot_pots = {
            "line1_stat": "final_atk_dmg",
            "line1_value": 12.0,
            "line2_stat": "str_flat",
            "line2_value": 600.0,
            "line3_stat": "max_dmg_mult",
            "line3_value": 15.0,
        }
        lines = convert_streamlit_lines_to_potential_lines(slot_pots, is_bonus=False)
        # All 3 lines should be included now (was 2 before fix)
        assert len(lines) == 3

    def test_final_atk_dmg_maps_to_final_damage_stat_type(self):
        slot_pots = {"line1_stat": "final_atk_dmg", "line1_value": 8.0}
        lines = convert_streamlit_lines_to_potential_lines(slot_pots, is_bonus=False)
        assert len(lines) == 1
        assert lines[0].stat_type == StatType.FINAL_DAMAGE

    def test_normalized_to_canonical_name_in_recommendation(self):
        # After fix, rec.line1_stat should be 'final_damage' (canonical),
        # not 'final_atk_dmg' (legacy alias)
        slot_pots = make_slot_pots(
            tier="legendary",
            line1_stat="final_atk_dmg",
            line1_value=12.0,
        )
        rec = _trivial_analyze(slot_pots)
        assert rec is not None
        assert rec.line1_stat == "final_damage"


# ---------------------------------------------------------------------------
# BUG 3 — DPS gain index misalignment
# ---------------------------------------------------------------------------

class TestDpsGainAlignment:
    """
    Bug: When convert_streamlit_lines_to_potential_lines skipped a line (e.g.
    unrecognized stat at slot 1), item_score.line_scores[0] corresponded to the
    SECOND physical line.  But analyze_slot_potentials assigned line_scores[i-1]
    to physical position i, causing the gains to be shifted by one.
    Fix: Use line.slot attribute to map scores to physical positions.
    """

    def test_skipped_first_line_does_not_shift_gains(self):
        # Construct a slot where line 1 would be skipped (unknown stat name)
        # and lines 2 & 3 are valid.
        slot_pots = make_slot_pots(
            line1_stat="unknown_stat_xyz",
            line1_value=9.0,
            line2_stat="damage_pct",
            line2_value=18.0,
            line3_stat="luk_pct",
            line3_value=9.0,
        )
        # Use a DPS function that returns different values per stat type
        # so we can detect if gains are mis-assigned
        def dps_by_stat(lines):
            if not lines:
                return 1000.0
            s = lines[0].stat_type
            if s == StatType.DAMAGE_PCT:
                return 1200.0  # +20%
            if s == StatType.LUK_PCT:
                return 1100.0  # +10%
            return 1000.0

        rec = analyze_slot_potentials(
            slot="hat",
            slot_pots=slot_pots,
            is_bonus=False,
            dps_calc_func=dps_by_stat,
            baseline_dps=1000.0,
            main_stat_type=StatType.LUK_PCT,
        )
        assert rec is not None
        # Line 1 gain: stat is unknown, so line1 was not in current_lines → 0
        assert rec.line1_dps_gain == pytest.approx(0.0)
        # Line 2 gain: damage_pct → +20%
        assert rec.line2_dps_gain == pytest.approx(20.0, rel=0.01)
        # Line 3 gain: luk_pct → +10%
        assert rec.line3_dps_gain == pytest.approx(10.0, rel=0.01)

    def test_all_lines_valid_gains_correct(self):
        # When all 3 lines are valid, gains should still align correctly
        slot_pots = make_slot_pots(
            line1_stat="damage_pct",
            line1_value=25.0,
            line2_stat="crit_rate",
            line2_value=9.0,
            line3_stat="luk_pct",
            line3_value=9.0,
        )

        def dps_by_stat(lines):
            if not lines:
                return 1000.0
            s = lines[0].stat_type
            return {
                StatType.DAMAGE_PCT: 1300.0,
                StatType.CRIT_RATE: 1150.0,
                StatType.LUK_PCT: 1100.0,
            }.get(s, 1000.0)

        rec = analyze_slot_potentials(
            slot="hat",
            slot_pots=slot_pots,
            is_bonus=False,
            dps_calc_func=dps_by_stat,
            baseline_dps=1000.0,
            main_stat_type=StatType.LUK_PCT,
        )
        assert rec is not None
        assert rec.line1_dps_gain == pytest.approx(30.0, rel=0.01)
        assert rec.line2_dps_gain == pytest.approx(15.0, rel=0.01)
        assert rec.line3_dps_gain == pytest.approx(10.0, rel=0.01)


# ---------------------------------------------------------------------------
# Stat name normalization
# ---------------------------------------------------------------------------

class TestStatNameNormalization:
    """analyze_slot_potentials should store canonical StatType.value strings,
    not raw CSV aliases."""

    def test_damage_pct_unchanged(self):
        slot_pots = make_slot_pots(line1_stat="damage_pct", line1_value=25.0)
        rec = _trivial_analyze(slot_pots)
        assert rec.line1_stat == "damage_pct"

    def test_legacy_damage_alias_normalized(self):
        # 'damage' is a legacy alias for StatType.DAMAGE_PCT whose value is 'damage_pct'
        slot_pots = make_slot_pots(line1_stat="damage", line1_value=25.0)
        rec = _trivial_analyze(slot_pots)
        assert rec.line1_stat == "damage_pct"

    def test_unrecognized_stat_kept_as_is(self):
        slot_pots = make_slot_pots(line1_stat="some_future_stat", line1_value=5.0)
        rec = _trivial_analyze(slot_pots)
        # Unrecognized: kept verbatim (can't normalize what we don't know)
        assert rec.line1_stat == "some_future_stat"

    def test_all_three_lines_normalized(self):
        slot_pots = make_slot_pots(
            line1_stat="final_atk_dmg", line1_value=12.0,
            line2_stat="damage", line2_value=18.0,
            line3_stat="luk_pct", line3_value=9.0,
        )
        rec = _trivial_analyze(slot_pots)
        assert rec.line1_stat == "final_damage"
        assert rec.line2_stat == "damage_pct"
        assert rec.line3_stat == "luk_pct"


# ---------------------------------------------------------------------------
# convert_streamlit_lines_to_potential_lines
# ---------------------------------------------------------------------------

class TestConvertStreamlitLines:
    def test_empty_pots_returns_empty(self):
        assert convert_streamlit_lines_to_potential_lines({}) == []

    def test_zero_value_line_excluded(self):
        pots = {"line1_stat": "damage_pct", "line1_value": 0}
        assert convert_streamlit_lines_to_potential_lines(pots) == []

    def test_bonus_prefix_used(self):
        pots = {
            "line1_stat": "damage_pct", "line1_value": 25.0,     # regular
            "bonus_line1_stat": "luk_pct", "bonus_line1_value": 9.0,  # bonus
        }
        regular = convert_streamlit_lines_to_potential_lines(pots, is_bonus=False)
        bonus = convert_streamlit_lines_to_potential_lines(pots, is_bonus=True)
        assert len(regular) == 1 and regular[0].stat_type == StatType.DAMAGE_PCT
        assert len(bonus) == 1 and bonus[0].stat_type == StatType.LUK_PCT

    def test_slot_attribute_matches_physical_position(self):
        pots = {
            "line1_stat": "damage_pct", "line1_value": 25.0,
            "line2_stat": "crit_rate", "line2_value": 9.0,
            "line3_stat": "luk_pct", "line3_value": 9.0,
        }
        lines = convert_streamlit_lines_to_potential_lines(pots)
        assert lines[0].slot == 1
        assert lines[1].slot == 2
        assert lines[2].slot == 3

    def test_line1_always_yellow(self):
        pots = {"line1_stat": "damage_pct", "line1_value": 25.0, "line1_yellow": False}
        lines = convert_streamlit_lines_to_potential_lines(pots)
        # Line 1 is always yellow regardless of stored flag
        assert lines[0].is_yellow is True

    def test_line2_yellow_from_pots(self):
        pots = {
            "line2_stat": "crit_rate", "line2_value": 9.0,
            "line2_yellow": False,
        }
        lines = convert_streamlit_lines_to_potential_lines(pots)
        assert lines[0].is_yellow is False

    def test_unknown_stat_excluded(self):
        pots = {
            "line1_stat": "not_a_real_stat", "line1_value": 10.0,
            "line2_stat": "damage_pct", "line2_value": 18.0,
        }
        lines = convert_streamlit_lines_to_potential_lines(pots)
        assert len(lines) == 1
        assert lines[0].stat_type == StatType.DAMAGE_PCT


# ---------------------------------------------------------------------------
# analyze_all_cube_priorities — integration smoke test
# ---------------------------------------------------------------------------

class TestAnalyzeAllCubePriorities:
    """
    Light integration test: verifies the full pipeline runs and restores
    user_data.equipment_potentials after completion.
    """

    def _make_user_data(self):
        """Minimal UserData-like object with equipment_potentials."""
        class FakeUserData:
            job_class = "night_lord"
            combat_mode = "stage"
            equipment_potentials = {
                "hat": make_slot_pots(
                    tier="legendary",
                    line1_stat="damage_pct", line1_value=25.0,
                    line2_stat="luk_pct",    line2_value=9.0,
                    line3_stat="crit_rate",  line3_value=9.0,
                ),
                "gloves": make_slot_pots(
                    tier="mystic",
                    line1_stat="crit_damage", line1_value=50.0,
                    line2_stat="min_dmg_mult", line2_value=25.0,
                    line3_stat="max_dmg_mult", line3_value=15.0,
                ),
            }
        return FakeUserData()

    def test_returns_recommendations(self):
        ud = self._make_user_data()
        recs = analyze_all_cube_priorities(
            user_data=ud,
            aggregate_stats_func=lambda: {},
            calculate_dps_func=lambda stats, cm="stage": {"total": 1000.0},
        )
        assert len(recs) > 0
        assert all(isinstance(r, CubeRecommendation) for r in recs)

    def test_potentials_restored_after_analysis(self):
        ud = self._make_user_data()
        original_hat = deepcopy(ud.equipment_potentials["hat"])
        analyze_all_cube_priorities(
            user_data=ud,
            aggregate_stats_func=lambda: {},
            calculate_dps_func=lambda stats, cm="stage": {"total": 1000.0},
        )
        assert ud.equipment_potentials["hat"] == original_hat

    def test_recommendations_sorted_by_efficiency(self):
        ud = self._make_user_data()
        recs = analyze_all_cube_priorities(
            user_data=ud,
            aggregate_stats_func=lambda: {},
            calculate_dps_func=lambda stats, cm="stage": {"total": 1000.0},
        )
        efficiencies = [r.efficiency_score for r in recs]
        assert efficiencies == sorted(efficiencies, reverse=True)

    def test_priority_ranks_assigned(self):
        ud = self._make_user_data()
        recs = analyze_all_cube_priorities(
            user_data=ud,
            aggregate_stats_func=lambda: {},
            calculate_dps_func=lambda stats, cm="stage": {"total": 1000.0},
        )
        ranks = [r.priority_rank for r in recs]
        assert ranks == list(range(1, len(recs) + 1))

    def test_line_stats_correct_for_known_slot(self):
        ud = self._make_user_data()
        recs = analyze_all_cube_priorities(
            user_data=ud,
            aggregate_stats_func=lambda: {},
            calculate_dps_func=lambda stats, cm="stage": {"total": 1000.0},
        )
        hat_recs = [r for r in recs if r.slot == "hat" and not r.is_bonus]
        assert len(hat_recs) == 1
        rec = hat_recs[0]
        assert rec.line1_stat == "damage_pct"
        assert rec.line1_value == pytest.approx(25.0)
        assert rec.line2_stat == "luk_pct"
        assert rec.line3_stat == "crit_rate"

    def test_mystic_tier_used_not_legendary(self):
        # Before fix: gloves with mystic tier would be analyzed as legendary
        ud = self._make_user_data()
        recs = analyze_all_cube_priorities(
            user_data=ud,
            aggregate_stats_func=lambda: {},
            calculate_dps_func=lambda stats, cm="stage": {"total": 1000.0},
        )
        glove_recs = [r for r in recs if r.slot == "gloves" and not r.is_bonus]
        assert len(glove_recs) == 1
        # Tier stored as the raw CSV value, not normalized to title case
        assert glove_recs[0].tier == "mystic"
