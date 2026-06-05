"""
Unit tests for cubes.py - Potential system, stat calculations, and helper functions.
"""
import pytest
from cubes import (
    # Enums
    PotentialTier,
    StatType,
    CubeType,
    # Data tables
    POTENTIAL_STATS,
    SPECIAL_POTENTIALS,
    TIER_COLORS,
    TIER_ABBREVIATIONS,
    TIER_UP_RATES,
    REGULAR_PITY,
    BONUS_PITY,
    # Classes
    PotentialStat,
    SpecialPotential,
    PotentialLine,
    EquipmentPotential,
    SlotPotentials,
    # Helper functions
    get_tier_color,
    get_tier_abbreviation,
    get_stat_display_name,
    get_stat_short_name,
    format_stat_value,
    get_tier_from_string,
    get_available_stats_for_slot,
    get_stat_value_at_tier,
    get_special_stat_for_slot,
    # Calculation functions
    calculate_expected_cubes_to_tier,
    calculate_realistic_cubes_to_tier,
    expected_cubes_with_pity,
)


class TestPotentialTierEnum:
    """Tests for PotentialTier enum."""

    def test_tier_ordering(self):
        """Tiers should be ordered from lowest to highest."""
        tiers = list(PotentialTier)
        assert tiers[0] == PotentialTier.NORMAL
        assert tiers[-1] == PotentialTier.MYSTIC

    def test_next_tier(self):
        """next_tier() should return the next higher tier."""
        assert PotentialTier.RARE.next_tier() == PotentialTier.EPIC
        assert PotentialTier.LEGENDARY.next_tier() == PotentialTier.MYSTIC
        assert PotentialTier.MYSTIC.next_tier() is None

    def test_prev_tier(self):
        """prev_tier() should return the previous tier."""
        assert PotentialTier.EPIC.prev_tier() == PotentialTier.RARE
        assert PotentialTier.RARE.prev_tier() == PotentialTier.NORMAL
        assert PotentialTier.NORMAL.prev_tier() is None


class TestStatTypeEnum:
    """Tests for StatType enum."""

    def test_final_damage_exists(self):
        """FINAL_DAMAGE should exist (not FINAL_ATK_DMG)."""
        assert hasattr(StatType, 'FINAL_DAMAGE')
        assert StatType.FINAL_DAMAGE.value == "final_damage"

    def test_all_main_stats_exist(self):
        """All main stat variants should exist."""
        assert StatType.DEX_PCT.value == "dex_pct"
        assert StatType.STR_PCT.value == "str_pct"
        assert StatType.INT_PCT.value == "int_pct"
        assert StatType.LUK_PCT.value == "luk_pct"
        assert StatType.DEX_FLAT.value == "dex_flat"
        assert StatType.STR_FLAT.value == "str_flat"
        assert StatType.INT_FLAT.value == "int_flat"
        assert StatType.LUK_FLAT.value == "luk_flat"

    def test_special_stats_exist(self):
        """Special potential stats should exist."""
        assert StatType.CRIT_DAMAGE.value == "crit_damage"
        assert StatType.DEF_PEN.value == "def_pen"
        assert StatType.ALL_SKILLS.value == "all_skills"
        assert StatType.BA_TARGETS.value == "ba_targets"
        assert StatType.SKILL_CD.value == "skill_cd"
        assert StatType.BUFF_DURATION.value == "buff_duration"


class TestPotentialStatsTable:
    """Tests for POTENTIAL_STATS data table."""

    def test_all_tiers_have_stats(self):
        """All tiers except NORMAL should have stat entries."""
        for tier in PotentialTier:
            if tier != PotentialTier.NORMAL:
                assert tier in POTENTIAL_STATS
                assert len(POTENTIAL_STATS[tier]) > 0

    def test_stat_values_increase_with_tier(self):
        """Stat values should increase from lower to higher tiers."""
        # Test DEX_PCT values across tiers
        rare_dex = next(s for s in POTENTIAL_STATS[PotentialTier.RARE] if s.stat_type == StatType.DEX_PCT)
        epic_dex = next(s for s in POTENTIAL_STATS[PotentialTier.EPIC] if s.stat_type == StatType.DEX_PCT)
        unique_dex = next(s for s in POTENTIAL_STATS[PotentialTier.UNIQUE] if s.stat_type == StatType.DEX_PCT)
        legendary_dex = next(s for s in POTENTIAL_STATS[PotentialTier.LEGENDARY] if s.stat_type == StatType.DEX_PCT)
        mystic_dex = next(s for s in POTENTIAL_STATS[PotentialTier.MYSTIC] if s.stat_type == StatType.DEX_PCT)

        assert rare_dex.value < epic_dex.value < unique_dex.value < legendary_dex.value < mystic_dex.value

    def test_legendary_main_stat_pct_is_12(self):
        """Legendary main stat % should be 12."""
        legendary_dex = next(s for s in POTENTIAL_STATS[PotentialTier.LEGENDARY] if s.stat_type == StatType.DEX_PCT)
        assert legendary_dex.value == 12.0

    def test_mystic_damage_pct_is_35(self):
        """Mystic damage % should be 35."""
        mystic_dmg = next(s for s in POTENTIAL_STATS[PotentialTier.MYSTIC] if s.stat_type == StatType.DAMAGE_PCT)
        assert mystic_dmg.value == 35.0


class TestSpecialPotentials:
    """Tests for SPECIAL_POTENTIALS data table."""

    def test_all_special_slots_defined(self):
        """All slots with special potentials should be defined."""
        expected_slots = ["hat", "gloves", "shoulder", "ring", "necklace", "cape", "bottom", "belt", "face", "top"]
        for slot in expected_slots:
            assert slot in SPECIAL_POTENTIALS

    def test_special_stat_types(self):
        """Each slot should have the correct special stat type."""
        assert SPECIAL_POTENTIALS["hat"].stat_type == StatType.SKILL_CD
        assert SPECIAL_POTENTIALS["gloves"].stat_type == StatType.CRIT_DAMAGE
        assert SPECIAL_POTENTIALS["shoulder"].stat_type == StatType.DEF_PEN
        assert SPECIAL_POTENTIALS["ring"].stat_type == StatType.ALL_SKILLS
        assert SPECIAL_POTENTIALS["cape"].stat_type == StatType.FINAL_DAMAGE
        assert SPECIAL_POTENTIALS["bottom"].stat_type == StatType.FINAL_DAMAGE
        assert SPECIAL_POTENTIALS["top"].stat_type == StatType.BA_TARGETS

    def test_legendary_crit_damage_is_30(self):
        """Legendary crit damage (gloves) should be 30%."""
        gloves = SPECIAL_POTENTIALS["gloves"]
        assert gloves.values[PotentialTier.LEGENDARY] == 30.0

    def test_legendary_final_damage_is_8(self):
        """Legendary final damage (cape/bottom) should be 8%."""
        cape = SPECIAL_POTENTIALS["cape"]
        assert cape.values[PotentialTier.LEGENDARY] == 8.0


class TestTierDisplayHelpers:
    """Tests for tier display helper functions."""

    def test_get_tier_color(self):
        """get_tier_color should return correct hex colors."""
        assert get_tier_color(PotentialTier.RARE) == "#5599ff"
        assert get_tier_color(PotentialTier.EPIC) == "#cc77ff"
        assert get_tier_color(PotentialTier.UNIQUE) == "#ffcc00"
        assert get_tier_color(PotentialTier.LEGENDARY) == "#66ff66"
        assert get_tier_color(PotentialTier.MYSTIC) == "#ff6666"

    def test_get_tier_abbreviation(self):
        """get_tier_abbreviation should return 3-letter codes."""
        assert get_tier_abbreviation(PotentialTier.RARE) == "RAR"
        assert get_tier_abbreviation(PotentialTier.EPIC) == "EPC"
        assert get_tier_abbreviation(PotentialTier.UNIQUE) == "UNI"
        assert get_tier_abbreviation(PotentialTier.LEGENDARY) == "LEG"
        assert get_tier_abbreviation(PotentialTier.MYSTIC) == "MYS"

    def test_get_tier_from_string(self):
        """get_tier_from_string should parse tier strings."""
        assert get_tier_from_string("rare") == PotentialTier.RARE
        assert get_tier_from_string("Rare") == PotentialTier.RARE
        assert get_tier_from_string("RARE") == PotentialTier.RARE
        assert get_tier_from_string("legendary") == PotentialTier.LEGENDARY
        assert get_tier_from_string("invalid") == PotentialTier.LEGENDARY  # Default


class TestStatDisplayHelpers:
    """Tests for stat display helper functions."""

    def test_get_stat_display_name(self):
        """get_stat_display_name should return full names."""
        assert get_stat_display_name(StatType.DEX_PCT) == "DEX %"
        assert get_stat_display_name(StatType.CRIT_DAMAGE) == "Crit Damage %"
        assert get_stat_display_name(StatType.FINAL_DAMAGE) == "Final Damage %"

    def test_get_stat_short_name(self):
        """get_stat_short_name should return abbreviated names."""
        assert get_stat_short_name(StatType.DEX_PCT) == "DEX%"
        assert get_stat_short_name(StatType.CRIT_DAMAGE) == "CD%"
        assert get_stat_short_name(StatType.FINAL_DAMAGE) == "FD%"
        assert get_stat_short_name(StatType.ALL_SKILLS) == "AS"

    def test_format_stat_value_percentage(self):
        """format_stat_value should format % stats correctly."""
        assert format_stat_value(StatType.DEX_PCT, 12.0) == "+12.0%"
        assert format_stat_value(StatType.DAMAGE_PCT, 25.0) == "+25.0%"

    def test_format_stat_value_flat(self):
        """format_stat_value should format flat stats without %."""
        assert format_stat_value(StatType.DEX_FLAT, 600) == "+600"
        assert format_stat_value(StatType.ALL_SKILLS, 12) == "+12"

    def test_format_stat_value_skill_cd(self):
        """format_stat_value should format skill CD as negative seconds."""
        assert format_stat_value(StatType.SKILL_CD, 1.5) == "-1.5s"

    def test_format_stat_value_zero(self):
        """format_stat_value should return dash for zero."""
        assert format_stat_value(StatType.DEX_PCT, 0) == "—"


class TestSlotHelpers:
    """Tests for slot-related helper functions."""

    def test_get_available_stats_for_slot_with_special(self):
        """Slots with special potentials should have special stat first."""
        gloves_stats = get_available_stats_for_slot("gloves")
        assert gloves_stats[0] == StatType.CRIT_DAMAGE  # Special stat first
        assert StatType.DEX_PCT in gloves_stats  # Base stats included

    def test_get_available_stats_for_slot_without_special(self):
        """Slots without special potentials should only have base stats."""
        shoes_stats = get_available_stats_for_slot("shoes")
        assert StatType.CRIT_DAMAGE not in shoes_stats  # No special
        assert StatType.DEX_PCT in shoes_stats  # Base stats included

    def test_get_special_stat_for_slot(self):
        """get_special_stat_for_slot should return correct special stat."""
        assert get_special_stat_for_slot("gloves") == StatType.CRIT_DAMAGE
        assert get_special_stat_for_slot("cape") == StatType.FINAL_DAMAGE
        assert get_special_stat_for_slot("shoes") is None

    def test_get_stat_value_at_tier_regular_stat(self):
        """get_stat_value_at_tier should return correct values for regular stats."""
        # Legendary DEX% should be 12
        value = get_stat_value_at_tier(StatType.DEX_PCT, PotentialTier.LEGENDARY, "hat", is_yellow=True)
        assert value == 12.0

        # Grey line should use previous tier (Unique = 9)
        value_grey = get_stat_value_at_tier(StatType.DEX_PCT, PotentialTier.LEGENDARY, "hat", is_yellow=False)
        assert value_grey == 9.0

    def test_get_stat_value_at_tier_special_stat(self):
        """get_stat_value_at_tier should return correct values for special stats."""
        # Legendary Crit Damage on gloves should be 30
        value = get_stat_value_at_tier(StatType.CRIT_DAMAGE, PotentialTier.LEGENDARY, "gloves", is_yellow=True)
        assert value == 30.0

        # Grey line should use Unique tier (20)
        value_grey = get_stat_value_at_tier(StatType.CRIT_DAMAGE, PotentialTier.LEGENDARY, "gloves", is_yellow=False)
        assert value_grey == 20.0


class TestEquipmentPotential:
    """Tests for EquipmentPotential class."""

    def test_create_empty_potential(self):
        """Creating potential with no stats should have zero values."""
        pot = EquipmentPotential(slot="hat")
        assert pot.line1_value == 0.0
        assert pot.line2_value == 0.0
        assert pot.line3_value == 0.0

    def test_auto_calculated_values(self):
        """Values should be auto-calculated from tier and stat."""
        pot = EquipmentPotential(
            slot="hat",
            tier=PotentialTier.LEGENDARY,
            line1_stat=StatType.DEX_PCT,
        )
        assert pot.line1_value == 12.0  # Legendary DEX%

    def test_yellow_vs_grey_values(self):
        """Grey lines should have lower tier values."""
        pot = EquipmentPotential(
            slot="hat",
            tier=PotentialTier.LEGENDARY,
            line1_stat=StatType.DEX_PCT,
            line2_stat=StatType.DEX_PCT,
            line2_yellow=True,
            line3_stat=StatType.DEX_PCT,
            line3_yellow=False,
        )
        assert pot.line1_value == 12.0  # Yellow (always)
        assert pot.line2_value == 12.0  # Yellow
        assert pot.line3_value == 9.0   # Grey (Unique tier)

    def test_special_potential_values(self):
        """Special potentials should have correct values."""
        pot = EquipmentPotential(
            slot="gloves",
            tier=PotentialTier.LEGENDARY,
            line1_stat=StatType.CRIT_DAMAGE,
        )
        assert pot.line1_value == 30.0  # Legendary Crit Damage

    def test_to_dict_and_from_dict(self):
        """Serialization should be reversible."""
        original = EquipmentPotential(
            slot="cape",
            tier=PotentialTier.LEGENDARY,
            line1_stat=StatType.FINAL_DAMAGE,
            line2_stat=StatType.DEX_PCT,
            line2_yellow=False,
            line3_stat=StatType.DAMAGE_PCT,
            line3_yellow=True,
            pity=50,
        )

        data = original.to_dict()
        restored = EquipmentPotential.from_dict("cape", data)

        assert restored.tier == original.tier
        assert restored.line1_stat == original.line1_stat
        assert restored.line2_stat == original.line2_stat
        assert restored.line2_yellow == original.line2_yellow
        assert restored.pity == original.pity


class TestSlotPotentials:
    """Tests for SlotPotentials class."""

    def test_create_slot_potentials(self):
        """SlotPotentials should initialize both regular and bonus."""
        slot_pots = SlotPotentials(slot="gloves")
        assert slot_pots.regular is not None
        assert slot_pots.bonus is not None
        assert slot_pots.regular.slot == "gloves"
        assert slot_pots.bonus.slot == "gloves"

    def test_to_dict_and_from_dict(self):
        """Serialization should be reversible."""
        original = SlotPotentials(slot="cape")
        original.regular.tier = PotentialTier.LEGENDARY
        original.regular.line1_stat = StatType.FINAL_DAMAGE
        original.bonus.tier = PotentialTier.UNIQUE
        original.bonus.line1_stat = StatType.DEX_PCT

        data = original.to_dict()
        restored = SlotPotentials.from_dict("cape", data)

        assert restored.regular.tier == original.regular.tier
        assert restored.regular.line1_stat == original.regular.line1_stat
        assert restored.bonus.tier == original.bonus.tier


class TestCubeCalculations:
    """Tests for cube probability calculations."""

    def test_tier_up_rates_exist(self):
        """All tiers should have tier-up rates."""
        for tier in PotentialTier:
            assert tier in TIER_UP_RATES

    def test_mystic_cannot_tier_up(self):
        """Mystic tier-up rate should be 0."""
        assert TIER_UP_RATES[PotentialTier.MYSTIC] == 0.0

    def test_pity_thresholds_exist(self):
        """All tiers should have pity thresholds."""
        for tier in PotentialTier:
            assert tier in REGULAR_PITY
            assert tier in BONUS_PITY

    def test_expected_cubes_calculation(self):
        """expected_cubes_with_pity should calculate correctly."""
        # With 100% chance, should take 1 cube
        assert expected_cubes_with_pity(1.0, 100) == 1.0

        # With 0% chance, should take exactly pity cubes
        assert expected_cubes_with_pity(0.0, 100) == 100

    def test_realistic_cubes_to_tier(self):
        """Realistic cube calculation should be less than pity."""
        # Epic -> Unique with pity 150 and 0.6% rate
        expected = calculate_realistic_cubes_to_tier(PotentialTier.EPIC, CubeType.REGULAR)
        assert expected < 150  # Should be less than pity due to natural tier-up chance
        assert expected > 0

    def test_mystic_tier_up_is_infinite(self):
        """Mystic should return infinite cubes to tier up."""
        expected = calculate_realistic_cubes_to_tier(PotentialTier.MYSTIC)
        assert expected == float('inf')


class TestPotentialLine:
    """Tests for PotentialLine class."""

    def test_get_stats_returns_statblock(self):
        """get_stats should return a StatBlock."""
        from stats import StatBlock
        line = PotentialLine(slot=1, stat_type=StatType.DEX_PCT, value=12.0, is_yellow=True)
        stats = line.get_stats()
        assert isinstance(stats, StatBlock)
        assert stats.dex_pct == 12.0

    def test_get_stats_zero_value(self):
        """get_stats should return empty StatBlock for zero value."""
        from stats import EMPTY_STATS
        line = PotentialLine(slot=1, stat_type=StatType.DEX_PCT, value=0.0, is_yellow=True)
        stats = line.get_stats()
        assert stats == EMPTY_STATS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
