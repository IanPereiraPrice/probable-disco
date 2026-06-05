"""
Integration / regression tests for the DPS pipeline:
  create_character_at_level → DPSCalculator → calculate_total_dps / get_skill_damage_breakdown

These tests verify:
  - Stat changes produce correct proportional DPS changes
  - Multi-target effects increase DPS with more enemies
  - Boss damage / def pen / final damage multipliers work correctly
  - Per-job DPS outputs are stable (regression guards)
  - Skill breakdown sums to total DPS
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from game.skills import create_character_at_level, DPSCalculator
from game.job_classes import JobClass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_char(job=JobClass.BOWMASTER, level=140, all_skills=44,
              attack=50_000, main_stat=100_000, crit_rate=70.0,
              crit_damage=200.0, damage_pct=100.0, attack_speed_pct=50.0,
              boss_damage=0.0, def_pen=0.0, final_damage_pct=0.0):
    char = create_character_at_level(level, all_skills, job_class=job)
    char.attack = attack
    char.main_stat_flat = main_stat
    char.main_stat_pct = 0
    char.crit_rate = crit_rate
    char.crit_damage = crit_damage
    char.damage_pct = damage_pct
    char.attack_speed_pct = attack_speed_pct
    char.boss_damage = boss_damage
    char.def_pen_pct = def_pen
    char.final_damage_pct = final_damage_pct
    return char


# ---------------------------------------------------------------------------
# DPS result structure
# ---------------------------------------------------------------------------

class TestDPSResultStructure:
    def test_total_dps_positive(self):
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)
        result = calc.calculate_total_dps(num_enemies=12, mob_time_fraction=0.6)
        assert result.total_dps > 0

    def test_has_expected_fields(self):
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)
        result = calc.calculate_total_dps(num_enemies=12, mob_time_fraction=0.6)
        assert hasattr(result, 'total_dps')
        assert hasattr(result, 'basic_attack_dps')
        assert hasattr(result, 'active_skill_dps')
        assert hasattr(result, 'summon_dps')

    def test_components_sum_roughly_to_total(self):
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)
        result = calc.calculate_total_dps(num_enemies=12, mob_time_fraction=0.6)
        component_sum = (
            result.basic_attack_dps + result.active_skill_dps
            + result.summon_dps + result.proc_dps
        )
        # Total should approximately match sum of components (some rounding OK)
        assert component_sum == pytest.approx(result.total_dps, rel=0.01)


# ---------------------------------------------------------------------------
# Stat scaling — proportional damage checks
# ---------------------------------------------------------------------------

class TestStatScaling:
    def test_100_pct_damage_doubles_dps(self):
        # With 100% crit and no defense, 100% damage_pct should double DPS
        base = make_char(crit_rate=100, damage_pct=0)
        doubled = make_char(crit_rate=100, damage_pct=100)

        calc_base = DPSCalculator(base, enemy_def=0.0)
        calc_doubled = DPSCalculator(doubled, enemy_def=0.0)

        r_base = calc_base.calculate_total_dps(num_enemies=1, mob_time_fraction=0.0)
        r_doubled = calc_doubled.calculate_total_dps(num_enemies=1, mob_time_fraction=0.0)

        assert r_doubled.total_dps == pytest.approx(r_base.total_dps * 2.0, rel=0.001)

    def test_full_defense_pen_removes_defense_penalty(self):
        no_pen = make_char(crit_rate=100, damage_pct=0, def_pen=0.0)
        full_pen = make_char(crit_rate=100, damage_pct=0, def_pen=100.0)

        enemy_def = 0.752  # Chapter 27 defense
        r_no_pen = DPSCalculator(no_pen, enemy_def=enemy_def).calculate_total_dps(
            num_enemies=1, mob_time_fraction=0.0)
        r_full_pen = DPSCalculator(full_pen, enemy_def=enemy_def).calculate_total_dps(
            num_enemies=1, mob_time_fraction=0.0)
        r_no_def = DPSCalculator(no_pen, enemy_def=0.0).calculate_total_dps(
            num_enemies=1, mob_time_fraction=0.0)

        assert r_full_pen.total_dps > r_no_pen.total_dps
        # Full pen should match no-defense scenario
        assert r_full_pen.total_dps == pytest.approx(r_no_def.total_dps, rel=0.01)

    def test_boss_damage_increases_boss_dps(self):
        base = make_char(crit_rate=100, damage_pct=0, boss_damage=0.0)
        with_boss = make_char(crit_rate=100, damage_pct=0, boss_damage=100.0)

        # boss-only fight (mob_time_fraction=0.0)
        r_base = DPSCalculator(base, enemy_def=0.0).calculate_total_dps(
            num_enemies=1, mob_time_fraction=0.0)
        r_boss = DPSCalculator(with_boss, enemy_def=0.0).calculate_total_dps(
            num_enemies=1, mob_time_fraction=0.0)

        assert r_boss.total_dps > r_base.total_dps

    def test_more_enemies_increases_mob_dps(self):
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)

        r_1 = calc.calculate_total_dps(num_enemies=1, mob_time_fraction=1.0)
        r_12 = calc.calculate_total_dps(num_enemies=12, mob_time_fraction=1.0)

        assert r_12.total_dps > r_1.total_dps

    def test_higher_attack_increases_dps_proportionally(self):
        char_1x = make_char(attack=10_000, main_stat=100_000, crit_rate=100)
        char_2x = make_char(attack=20_000, main_stat=100_000, crit_rate=100)

        r_1x = DPSCalculator(char_1x, enemy_def=0.0).calculate_total_dps(
            num_enemies=1, mob_time_fraction=0.0)
        r_2x = DPSCalculator(char_2x, enemy_def=0.0).calculate_total_dps(
            num_enemies=1, mob_time_fraction=0.0)

        assert r_2x.total_dps == pytest.approx(r_1x.total_dps * 2.0, rel=0.01)


# ---------------------------------------------------------------------------
# Skill breakdown
# ---------------------------------------------------------------------------

class TestSkillBreakdown:
    def test_breakdown_dps_consistent_with_pct(self):
        # pct_of_total for each skill should be derived from its dps / sum(all dps)
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)
        breakdown = calc.get_skill_damage_breakdown(
            fight_duration=60.0, num_enemies=12, mob_time_fraction=0.6)
        total_from_breakdown = sum(v["dps"] for v in breakdown.values())
        for skill_name, data in breakdown.items():
            expected_pct = 100.0 * data["dps"] / total_from_breakdown
            assert data["pct_of_total"] == pytest.approx(expected_pct, rel=0.01), \
                f"{skill_name}: pct_of_total={data['pct_of_total']:.2f} != expected {expected_pct:.2f}"

    def test_breakdown_has_display_name(self):
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)
        breakdown = calc.get_skill_damage_breakdown(
            fight_duration=60.0, num_enemies=12, mob_time_fraction=0.6)
        for skill_name, data in breakdown.items():
            assert "display_name" in data
            assert "dps" in data
            assert "pct_of_total" in data

    def test_breakdown_pct_sums_to_100(self):
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)
        breakdown = calc.get_skill_damage_breakdown(
            fight_duration=60.0, num_enemies=12, mob_time_fraction=0.6)
        total_pct = sum(v["pct_of_total"] for v in breakdown.values())
        assert total_pct == pytest.approx(100.0, rel=0.01)

    def test_basic_attack_present_in_breakdown(self):
        char = make_char()
        calc = DPSCalculator(char, enemy_def=0.752)
        breakdown = calc.get_skill_damage_breakdown(
            fight_duration=60.0, num_enemies=12, mob_time_fraction=0.6)
        assert len(breakdown) > 0
        # At least one skill present
        skill_names = list(breakdown.keys())
        assert any('arrow' in n.lower() or 'stream' in n.lower() or 'basic' in n.lower()
                   for n in skill_names)


# ---------------------------------------------------------------------------
# Regression baselines — per-job DPS at fixed stats
# (These are not from game observations, they lock the output against future regressions)
# ---------------------------------------------------------------------------

class TestDPSRegression:
    """
    Regression guards: if any of these fail after code changes, the DPS formula changed.
    Baseline values captured at test-writing time.
    """

    REGRESSION_STATS = dict(
        level=140, all_skills=44, attack=50_000, main_stat=100_000,
        crit_rate=70.0, crit_damage=200.0, damage_pct=100.0,
        attack_speed_pct=50.0, boss_damage=0.0, def_pen=0.0,
    )
    NUM_ENEMIES = 12
    MOB_FRACTION = 0.6
    ENEMY_DEF = 0.752
    REL_TOL = 0.001  # 0.1% — tighter than typical approx

    def _run(self, job):
        char = make_char(job=job, **self.REGRESSION_STATS)
        calc = DPSCalculator(char, enemy_def=self.ENEMY_DEF)
        return calc.calculate_total_dps(
            num_enemies=self.NUM_ENEMIES,
            mob_time_fraction=self.MOB_FRACTION,
        )

    def test_bowmaster_baseline(self):
        result = self._run(JobClass.BOWMASTER)
        assert result.total_dps == pytest.approx(1_702_646_040, rel=self.REL_TOL)

    def test_night_lord_baseline(self):
        result = self._run(JobClass.NIGHT_LORD)
        assert result.total_dps == pytest.approx(1_368_602_499, rel=self.REL_TOL)

    def test_shadower_baseline(self):
        result = self._run(JobClass.SHADOWER)
        assert result.total_dps == pytest.approx(1_843_854_251, rel=self.REL_TOL)

    def test_bowmaster_basic_attack_is_positive_fraction(self):
        result = self._run(JobClass.BOWMASTER)
        fraction = result.basic_attack_dps / result.total_dps
        assert 0.1 < fraction < 0.8  # BA contributes 10-80% of total

    def test_skills_contribute_to_bowmaster_dps(self):
        result = self._run(JobClass.BOWMASTER)
        assert result.active_skill_dps > 0


# ---------------------------------------------------------------------------
# Cooldown reduction effect
# ---------------------------------------------------------------------------

class TestCooldownReduction:
    def test_cd_reduction_increases_dps(self):
        char_no_cd = make_char()
        char_with_cd = make_char()
        char_with_cd.skill_cd_reduction = 4.0  # 4 seconds flat CD reduction

        calc_no = DPSCalculator(char_no_cd, enemy_def=0.752)
        calc_with = DPSCalculator(char_with_cd, enemy_def=0.752)

        r_no = calc_no.calculate_total_dps(num_enemies=1, mob_time_fraction=0.0)
        r_with = calc_with.calculate_total_dps(num_enemies=1, mob_time_fraction=0.0)

        assert r_with.total_dps >= r_no.total_dps

    def test_high_all_skills_bonus_increases_dps(self):
        char_low = make_char(all_skills=0)
        char_high = make_char(all_skills=80)

        calc_low = DPSCalculator(char_low, enemy_def=0.752)
        calc_high = DPSCalculator(char_high, enemy_def=0.752)

        r_low = calc_low.calculate_total_dps(num_enemies=12, mob_time_fraction=0.6)
        r_high = calc_high.calculate_total_dps(num_enemies=12, mob_time_fraction=0.6)

        assert r_high.total_dps > r_low.total_dps
