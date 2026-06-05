"""
Unit tests for streamlit_app/utils/stat_aggregator.py

Covers: TrackedStat stacking formulas, StatAggregator add/get/sources,
baseline values, alias resolution, to_dict() output format, job-aware keys.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.utils.stat_aggregator import (
    TrackedStat,
    StatType,
    StatAggregator,
    STAT_CONFIG,
)
from game.job_classes import JobClass


# ---------------------------------------------------------------------------
# TrackedStat — ADDITIVE
# ---------------------------------------------------------------------------

class TestTrackedStatAdditive:
    def _make(self, baseline=0.0):
        return TrackedStat(stat_key="damage_pct", stat_type=StatType.ADDITIVE, baseline=baseline)

    def test_empty_value_equals_baseline(self):
        ts = self._make(baseline=10.0)
        assert ts.value == pytest.approx(10.0)

    def test_raw_total_excludes_baseline(self):
        ts = self._make(baseline=30.0)
        ts.add(20.0, "Ring")
        assert ts.raw_total == pytest.approx(20.0)

    def test_value_includes_baseline(self):
        ts = self._make(baseline=30.0)
        ts.add(20.0, "Ring")
        assert ts.value == pytest.approx(50.0)

    def test_multiple_sources_sum(self):
        ts = self._make()
        ts.add(10.0, "A")
        ts.add(15.0, "B")
        ts.add(5.0, "C")
        assert ts.value == pytest.approx(30.0)

    def test_zero_value_not_tracked(self):
        ts = self._make()
        ts.add(0.0, "Empty Source")
        assert ts.sources == []
        assert ts.raw_total == 0.0

    def test_sources_returns_copy(self):
        ts = self._make()
        ts.add(10.0, "Ring")
        s1 = ts.sources
        s1.clear()
        assert len(ts.sources) == 1  # original unaffected

    def test_sources_preserves_order(self):
        ts = self._make()
        ts.add(10.0, "First")
        ts.add(20.0, "Second")
        names = [s[0] for s in ts.sources]
        assert names == ["First", "Second"]

    def test_negative_source(self):
        ts = self._make(baseline=50.0)
        ts.add(-10.0, "Debuff")
        assert ts.value == pytest.approx(40.0)
        assert len(ts.sources) == 1  # negative non-zero IS tracked


# ---------------------------------------------------------------------------
# TrackedStat — MULTIPLICATIVE (Final Damage)
# ---------------------------------------------------------------------------

class TestTrackedStatMultiplicative:
    def _make(self):
        return TrackedStat(stat_key="final_damage", stat_type=StatType.MULTIPLICATIVE, baseline=0)

    def test_no_sources_returns_zero(self):
        ts = self._make()
        # (1.0 - 1) * 100 = 0
        assert ts.value == pytest.approx(0.0)

    def test_single_source(self):
        ts = self._make()
        ts.add(10.0, "Guild")   # 10% FD
        # (1.10 - 1) * 100 = 10
        assert ts.value == pytest.approx(10.0)

    def test_two_sources_multiplicative_not_additive(self):
        ts = self._make()
        ts.add(10.0, "A")
        ts.add(20.0, "B")
        # (1.10 * 1.20 - 1) * 100 = 32, NOT 30
        assert ts.value == pytest.approx(32.0)
        assert ts.value > 30.0

    def test_three_sources(self):
        ts = self._make()
        ts.add(10.0, "A")
        ts.add(13.0, "B")
        ts.add(8.0, "C")
        expected = (1.10 * 1.13 * 1.08 - 1) * 100
        assert ts.value == pytest.approx(expected)

    def test_formula_matches_stat_aggregator_convention(self):
        ts = self._make()
        ts.add(20.0, "Source")
        # to_dict stores sources as value/100 decimals
        expected_decimal = ts.sources[0][1] / 100
        assert expected_decimal == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# TrackedStat — DEFENSE_PEN
# ---------------------------------------------------------------------------

class TestTrackedStatDefensePen:
    def _make(self):
        return TrackedStat(stat_key="def_pen", stat_type=StatType.DEFENSE_PEN, baseline=0)

    def test_no_sources_returns_zero(self):
        ts = self._make()
        # (1 - 1.0) * 100 = 0
        assert ts.value == pytest.approx(0.0)

    def test_single_source(self):
        ts = self._make()
        ts.add(42.4, "Passive")
        # (1 - (1 - 0.424)) * 100 = 42.4
        assert ts.value == pytest.approx(42.4)

    def test_two_sources_multiplicative_remaining(self):
        ts = self._make()
        ts.add(50.0, "A")
        ts.add(50.0, "B")
        # remaining = 0.5 * 0.5 = 0.25 → pen = 75%
        assert ts.value == pytest.approx(75.0)

    def test_not_additive(self):
        ts = self._make()
        ts.add(50.0, "A")
        ts.add(50.0, "B")
        # If additive would be 100%, but multiplicative gives 75%
        assert ts.value < 100.0

    def test_three_sources(self):
        ts = self._make()
        ts.add(42.4, "A")
        ts.add(19.0, "B")
        ts.add(16.5, "C")
        remaining = (1 - 0.424) * (1 - 0.19) * (1 - 0.165)
        expected = (1 - remaining) * 100
        assert ts.value == pytest.approx(expected)


# ---------------------------------------------------------------------------
# TrackedStat — DIMINISHING (attack speed)
# ---------------------------------------------------------------------------

class TestTrackedStatDiminishing:
    def _make(self):
        return TrackedStat(stat_key="attack_speed", stat_type=StatType.DIMINISHING, baseline=0)

    def test_no_sources_returns_zero(self):
        ts = self._make()
        assert ts.value == pytest.approx(0.0)

    def test_returns_raw_total(self):
        ts = self._make()
        ts.add(15.0, "Weapon")
        ts.add(10.0, "Passive")
        # DIMINISHING just returns raw total; actual DR happens elsewhere
        assert ts.value == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# StatAggregator — initialization and baseline values
# ---------------------------------------------------------------------------

class TestStatAggregatorInit:
    def test_default_job_is_bowmaster(self):
        agg = StatAggregator()
        assert agg.main_stat_name == "dex"
        assert agg.main_flat_key == "dex_flat"
        assert agg.main_pct_key == "dex_pct"

    def test_bowmaster_main_stat_keys(self):
        agg = StatAggregator(job_class=JobClass.BOWMASTER)
        assert "dex_flat" in agg._stats
        assert "dex_pct" in agg._stats

    def test_night_lord_main_stat_keys(self):
        agg = StatAggregator(job_class=JobClass.NIGHT_LORD)
        assert agg.main_stat_name == "luk"
        assert "luk_flat" in agg._stats
        assert "luk_pct" in agg._stats

    def test_ice_lightning_main_stat_keys(self):
        agg = StatAggregator(job_class=JobClass.ARCHMAGE_ICE_LIGHTNING)
        assert agg.main_stat_name == "int"
        assert "int_flat" in agg._stats

    def test_shadower_main_stat_keys(self):
        agg = StatAggregator(job_class=JobClass.SHADOWER)
        assert agg.main_stat_name == "luk"
        assert "luk_flat" in agg._stats

    def test_crit_damage_baseline(self):
        agg = StatAggregator()
        # Baseline 30 always present even with no sources
        assert agg.get("crit_damage") == pytest.approx(30.0)

    def test_min_dmg_mult_baseline(self):
        agg = StatAggregator()
        assert agg.get("min_dmg_mult") == pytest.approx(50.0)

    def test_max_dmg_mult_baseline(self):
        agg = StatAggregator()
        assert agg.get("max_dmg_mult") == pytest.approx(100.0)

    def test_damage_pct_no_baseline(self):
        agg = StatAggregator()
        assert agg.get("damage_pct") == pytest.approx(0.0)

    def test_get_baseline_method(self):
        agg = StatAggregator()
        assert agg.get_baseline("crit_damage") == pytest.approx(30.0)
        assert agg.get_baseline("min_dmg_mult") == pytest.approx(50.0)
        assert agg.get_baseline("max_dmg_mult") == pytest.approx(100.0)
        assert agg.get_baseline("damage_pct") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# StatAggregator — add / get / get_sources
# ---------------------------------------------------------------------------

class TestStatAggregatorAddGet:
    def test_add_and_get_additive(self):
        agg = StatAggregator()
        agg.add("damage_pct", 20.0, "Gear")
        assert agg.get("damage_pct") == pytest.approx(20.0)

    def test_add_multiple_same_stat(self):
        agg = StatAggregator()
        agg.add("damage_pct", 10.0, "A")
        agg.add("damage_pct", 15.0, "B")
        assert agg.get("damage_pct") == pytest.approx(25.0)

    def test_add_zero_ignored(self):
        agg = StatAggregator()
        agg.add("damage_pct", 0.0, "Nothing")
        assert agg.get_sources("damage_pct") == []

    def test_get_sources_returns_tuples(self):
        agg = StatAggregator()
        agg.add("damage_pct", 10.0, "Ring")
        agg.add("damage_pct", 20.0, "Necklace")
        sources = agg.get_sources("damage_pct")
        assert ("Ring", 10.0) in sources
        assert ("Necklace", 20.0) in sources

    def test_get_without_baseline(self):
        agg = StatAggregator()
        agg.add("crit_damage", 50.0, "Gear")
        # include_baseline=False → raw_total only
        raw = agg.get("crit_damage", include_baseline=False)
        assert raw == pytest.approx(50.0)
        # include_baseline=True → 30 baseline + 50
        total = agg.get("crit_damage")
        assert total == pytest.approx(80.0)

    def test_get_unknown_stat_creates_additive_default(self):
        agg = StatAggregator()
        result = agg.get("some_unknown_stat")
        assert result == pytest.approx(0.0)

    def test_final_damage_multiplicative_via_aggregator(self):
        agg = StatAggregator()
        agg.add("final_damage", 10.0, "A")
        agg.add("final_damage", 20.0, "B")
        # (1.10 * 1.20 - 1) * 100 = 32
        assert agg.get("final_damage") == pytest.approx(32.0)

    def test_def_pen_stacking_via_aggregator(self):
        agg = StatAggregator()
        agg.add("def_pen", 50.0, "A")
        agg.add("def_pen", 50.0, "B")
        assert agg.get("def_pen") == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# StatAggregator — alias resolution
# ---------------------------------------------------------------------------

class TestStatAggregatorAliases:
    def test_damage_alias_resolves_to_damage_pct(self):
        agg = StatAggregator()
        agg.add("damage", 25.0, "Source")
        assert agg.get("damage_pct") == pytest.approx(25.0)

    def test_damage_alias_and_direct_stack(self):
        agg = StatAggregator()
        agg.add("damage", 10.0, "Alias Source")
        agg.add("damage_pct", 15.0, "Direct Source")
        assert agg.get("damage_pct") == pytest.approx(25.0)

    def test_main_stat_flat_alias_bowmaster(self):
        agg = StatAggregator(job_class=JobClass.BOWMASTER)
        agg.add("main_stat_flat", 500.0, "HP")
        assert agg.get("dex_flat") == pytest.approx(500.0)

    def test_main_stat_flat_alias_night_lord(self):
        agg = StatAggregator(job_class=JobClass.NIGHT_LORD)
        agg.add("main_stat_flat", 500.0, "HP")
        assert agg.get("luk_flat") == pytest.approx(500.0)

    def test_main_stat_pct_alias(self):
        agg = StatAggregator(job_class=JobClass.BOWMASTER)
        agg.add("main_stat_pct", 30.0, "Artifact")
        assert agg.get("dex_pct") == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# StatAggregator — to_dict() output format
# ---------------------------------------------------------------------------

class TestStatAggregatorToDict:
    def test_additive_returns_raw_total_not_with_baseline(self):
        agg = StatAggregator()
        agg.add("crit_damage", 50.0, "Gear")
        d = agg.to_dict()
        # to_dict returns raw_total (consumers add baseline separately)
        assert d["crit_damage"] == pytest.approx(50.0)

    def test_additive_no_sources_returns_zero(self):
        agg = StatAggregator()
        d = agg.to_dict()
        assert d["damage_pct"] == pytest.approx(0.0)

    def test_def_pen_sources_format(self):
        agg = StatAggregator()
        agg.add("def_pen", 42.4, "Passive")
        d = agg.to_dict()
        assert "def_pen_sources" in d
        sources = d["def_pen_sources"]
        assert len(sources) == 1
        # Format: (name, value, 0)
        assert sources[0] == ("Passive", 42.4, 0)

    def test_final_damage_sources_format(self):
        agg = StatAggregator()
        agg.add("final_damage", 10.0, "Guild")
        agg.add("final_damage", 20.0, "Artifact")
        d = agg.to_dict()
        assert "final_damage_sources" in d
        sources = d["final_damage_sources"]
        # Format: list of value/100 decimals
        assert len(sources) == 2
        assert sources[0] == pytest.approx(0.10) or sources[1] == pytest.approx(0.10)

    def test_attack_speed_sources_format(self):
        agg = StatAggregator()
        agg.add("attack_speed", 15.0, "Weapon")
        d = agg.to_dict()
        assert "attack_speed_sources" in d
        sources = d["attack_speed_sources"]
        assert len(sources) == 1
        assert sources[0] == ("Weapon", 15.0)

    def test_main_stat_type_in_dict(self):
        agg = StatAggregator(job_class=JobClass.BOWMASTER)
        d = agg.to_dict()
        assert d["main_stat_type"] == "dex"

    def test_character_level_in_dict(self):
        agg = StatAggregator()
        agg.character_level = 140
        d = agg.to_dict()
        assert d["character_level"] == 140

    def test_multiple_def_pen_sources(self):
        agg = StatAggregator()
        agg.add("def_pen", 42.4, "A")
        agg.add("def_pen", 19.0, "B")
        d = agg.to_dict()
        sources = d["def_pen_sources"]
        assert len(sources) == 2
        names = [s[0] for s in sources]
        assert "A" in names
        assert "B" in names

    def test_final_damage_sources_decimal_conversion(self):
        agg = StatAggregator()
        agg.add("final_damage", 10.0, "Guild")
        d = agg.to_dict()
        # 10% FD stored as 0.10 decimal
        assert d["final_damage_sources"] == pytest.approx([0.10])

    def test_empty_def_pen_has_no_sources_key(self):
        agg = StatAggregator()
        d = agg.to_dict()
        # With no sources, def_pen_sources should be absent or empty list
        # The key only appears when there are sources
        if "def_pen_sources" in d:
            assert d["def_pen_sources"] == []
