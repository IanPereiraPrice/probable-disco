"""
Unit tests for constants.py - Shared display functions, rarity colors, stat names.
"""
import pytest
from constants import (
    # Enums
    Rarity,
    # Data tables
    RARITY_COLORS,
    RARITY_ABBREVIATIONS,
    STAT_SHORT_NAMES,
    STAT_DISPLAY_NAMES,
    # Helper functions
    get_rarity_color,
    get_rarity_abbreviation,
    rarity_from_string,
    get_stat_short_name,
    get_stat_display_name,
    format_stat_value,
    is_percentage_stat,
)


class TestRarityEnum:
    """Tests for Rarity enum."""

    def test_all_rarities_exist(self):
        """All expected rarities should exist."""
        assert Rarity.NORMAL
        assert Rarity.RARE
        assert Rarity.EPIC
        assert Rarity.UNIQUE
        assert Rarity.LEGENDARY
        assert Rarity.MYSTIC
        assert Rarity.ANCIENT

    def test_rarity_values(self):
        """Rarity values should be lowercase strings."""
        assert Rarity.RARE.value == "rare"
        assert Rarity.LEGENDARY.value == "legendary"
        assert Rarity.MYSTIC.value == "mystic"


class TestRarityColors:
    """Tests for RARITY_COLORS."""

    def test_all_rarities_have_colors(self):
        """All rarities should have a color defined."""
        for rarity in Rarity:
            assert rarity in RARITY_COLORS
            # Colors should be hex format
            assert RARITY_COLORS[rarity].startswith("#")

    def test_specific_colors(self):
        """Check specific expected colors."""
        assert RARITY_COLORS[Rarity.RARE] == "#5599ff"
        assert RARITY_COLORS[Rarity.EPIC] == "#cc77ff"
        assert RARITY_COLORS[Rarity.UNIQUE] == "#ffcc00"
        assert RARITY_COLORS[Rarity.LEGENDARY] == "#66ff66"
        assert RARITY_COLORS[Rarity.MYSTIC] == "#ff6666"


class TestRarityAbbreviations:
    """Tests for RARITY_ABBREVIATIONS."""

    def test_all_rarities_have_abbreviations(self):
        """All rarities should have an abbreviation."""
        for rarity in Rarity:
            assert rarity in RARITY_ABBREVIATIONS
            # Abbreviations should be 3 letters
            assert len(RARITY_ABBREVIATIONS[rarity]) == 3

    def test_specific_abbreviations(self):
        """Check specific expected abbreviations."""
        assert RARITY_ABBREVIATIONS[Rarity.RARE] == "RAR"
        assert RARITY_ABBREVIATIONS[Rarity.EPIC] == "EPC"
        assert RARITY_ABBREVIATIONS[Rarity.UNIQUE] == "UNI"
        assert RARITY_ABBREVIATIONS[Rarity.LEGENDARY] == "LEG"
        assert RARITY_ABBREVIATIONS[Rarity.MYSTIC] == "MYS"


class TestRarityHelpers:
    """Tests for rarity helper functions."""

    def test_get_rarity_color(self):
        """get_rarity_color should return correct colors."""
        assert get_rarity_color(Rarity.LEGENDARY) == "#66ff66"
        assert get_rarity_color(Rarity.MYSTIC) == "#ff6666"

    def test_get_rarity_abbreviation(self):
        """get_rarity_abbreviation should return correct abbreviations."""
        assert get_rarity_abbreviation(Rarity.LEGENDARY) == "LEG"
        assert get_rarity_abbreviation(Rarity.MYSTIC) == "MYS"

    def test_rarity_from_string_lowercase(self):
        """rarity_from_string should parse lowercase."""
        assert rarity_from_string("rare") == Rarity.RARE
        assert rarity_from_string("legendary") == Rarity.LEGENDARY

    def test_rarity_from_string_mixed_case(self):
        """rarity_from_string should handle mixed case."""
        assert rarity_from_string("Rare") == Rarity.RARE
        assert rarity_from_string("LEGENDARY") == Rarity.LEGENDARY
        assert rarity_from_string("LegEndary") == Rarity.LEGENDARY

    def test_rarity_from_string_invalid(self):
        """rarity_from_string should default to LEGENDARY for invalid input."""
        assert rarity_from_string("invalid") == Rarity.LEGENDARY
        assert rarity_from_string("") == Rarity.LEGENDARY


class TestStatShortNames:
    """Tests for STAT_SHORT_NAMES."""

    def test_main_stat_short_names(self):
        """Main stat % should have short names like DEX%."""
        assert STAT_SHORT_NAMES["dex_pct"] == "DEX%"
        assert STAT_SHORT_NAMES["str_pct"] == "STR%"
        assert STAT_SHORT_NAMES["int_pct"] == "INT%"
        assert STAT_SHORT_NAMES["luk_pct"] == "LUK%"

    def test_damage_stat_short_names(self):
        """Damage stats should have appropriate short names."""
        assert STAT_SHORT_NAMES["damage_pct"] == "DMG%"
        assert STAT_SHORT_NAMES["crit_rate"] == "CR%"
        assert STAT_SHORT_NAMES["crit_damage"] == "CD%"
        assert STAT_SHORT_NAMES["final_damage"] == "FD%"
        assert STAT_SHORT_NAMES["def_pen"] == "DP%"

    def test_special_stat_short_names(self):
        """Special stats should have appropriate short names."""
        assert STAT_SHORT_NAMES["all_skills"] == "AS"
        assert STAT_SHORT_NAMES["skill_cd"] == "CDR"
        assert STAT_SHORT_NAMES["ba_targets"] == "BA+"


class TestStatDisplayNames:
    """Tests for STAT_DISPLAY_NAMES."""

    def test_main_stat_display_names(self):
        """Main stats should have full display names."""
        assert STAT_DISPLAY_NAMES["dex_pct"] == "DEX %"
        assert STAT_DISPLAY_NAMES["dex_flat"] == "DEX (Flat)"

    def test_damage_stat_display_names(self):
        """Damage stats should have full display names."""
        assert STAT_DISPLAY_NAMES["damage_pct"] == "Damage %"
        assert STAT_DISPLAY_NAMES["crit_damage"] == "Crit Damage %"
        assert STAT_DISPLAY_NAMES["final_damage"] == "Final Damage %"

    def test_special_stat_display_names(self):
        """Special stats should have full display names."""
        assert STAT_DISPLAY_NAMES["all_skills"] == "All Skills Level"
        assert STAT_DISPLAY_NAMES["skill_cd"] == "Skill CD Reduction"


class TestStatHelpers:
    """Tests for stat helper functions."""

    def test_get_stat_short_name_known(self):
        """get_stat_short_name should return short name for known stats."""
        assert get_stat_short_name("dex_pct") == "DEX%"
        assert get_stat_short_name("crit_damage") == "CD%"
        assert get_stat_short_name("final_damage") == "FD%"

    def test_get_stat_short_name_unknown(self):
        """get_stat_short_name should return input for unknown stats."""
        assert get_stat_short_name("unknown_stat") == "unknown_stat"

    def test_get_stat_display_name_known(self):
        """get_stat_display_name should return display name for known stats."""
        assert get_stat_display_name("dex_pct") == "DEX %"
        assert get_stat_display_name("final_damage") == "Final Damage %"

    def test_get_stat_display_name_unknown(self):
        """get_stat_display_name should format unknown stats nicely."""
        # Should convert underscores to spaces and title case
        assert get_stat_display_name("some_new_stat") == "Some New Stat"

    def test_format_stat_value_percentage(self):
        """format_stat_value should format percentage stats."""
        assert format_stat_value("dex_pct", 12.0) == "+12.0%"
        assert format_stat_value("damage_pct", 25.5) == "+25.5%"
        assert format_stat_value("crit_rate", 15.0) == "+15.0%"

    def test_format_stat_value_flat(self):
        """format_stat_value should format flat stats without %."""
        assert format_stat_value("dex_flat", 600) == "+600"
        assert format_stat_value("str_flat", 1000) == "+1000"
        assert format_stat_value("all_skills", 12) == "+12"
        assert format_stat_value("ba_targets", 2) == "+2"

    def test_format_stat_value_skill_cd(self):
        """format_stat_value should format skill CD specially."""
        assert format_stat_value("skill_cd", 1.5) == "-1.5s"
        assert format_stat_value("skill_cd", 2.0) == "-2.0s"

    def test_format_stat_value_zero(self):
        """format_stat_value should return dash for zero values."""
        assert format_stat_value("dex_pct", 0) == "—"
        assert format_stat_value("dex_flat", 0) == "—"


class TestIsPercentageStat:
    """Tests for is_percentage_stat function."""

    def test_flat_stats_return_false(self):
        """Flat stats should return False."""
        assert is_percentage_stat("dex_flat") is False
        assert is_percentage_stat("str_flat") is False
        assert is_percentage_stat("int_flat") is False
        assert is_percentage_stat("luk_flat") is False
        assert is_percentage_stat("attack_flat") is False
        assert is_percentage_stat("main_stat_flat") is False

    def test_utility_flat_stats_return_false(self):
        """Utility flat stats should return False."""
        assert is_percentage_stat("all_skills") is False
        assert is_percentage_stat("ba_targets") is False
        assert is_percentage_stat("accuracy") is False

    def test_percentage_stats_return_true(self):
        """Percentage stats should return True."""
        assert is_percentage_stat("dex_pct") is True
        assert is_percentage_stat("damage_pct") is True
        assert is_percentage_stat("crit_rate") is True
        assert is_percentage_stat("crit_damage") is True
        assert is_percentage_stat("def_pen") is True
        assert is_percentage_stat("final_damage") is True
        assert is_percentage_stat("attack_speed") is True
        assert is_percentage_stat("boss_damage") is True
        assert is_percentage_stat("normal_damage") is True

    def test_dynamic_stat_suffix(self):
        """Stats with _pct suffix should be percentage, _flat should not."""
        assert is_percentage_stat("any_pct") is True
        assert is_percentage_stat("custom_flat") is False


class TestConsistency:
    """Tests for consistency between short and display names."""

    def test_all_short_names_have_display_names(self):
        """Every stat with a short name should have a display name."""
        for stat_name in STAT_SHORT_NAMES:
            assert stat_name in STAT_DISPLAY_NAMES, f"{stat_name} has short name but no display name"

    def test_all_display_names_have_short_names(self):
        """Every stat with a display name should have a short name."""
        for stat_name in STAT_DISPLAY_NAMES:
            assert stat_name in STAT_SHORT_NAMES, f"{stat_name} has display name but no short name"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
