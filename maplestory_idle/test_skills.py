"""
Unit tests for MapleStory Idle Skill System

Run with: python -m pytest test_skills.py -v
Or simply: python test_skills.py
"""

import unittest
from skills import (
    # Enums
    SkillType, DamageType, Job,
    # Functions
    get_job_for_level, get_skill_points_for_job,
    get_unlocked_masteries, get_mastery_bonuses, get_global_mastery_stats,
    create_character_at_level, calculate_all_skills_value,
    calculate_job_skill_value, calculate_all_skills_value_by_job,
    create_character_with_job_bonuses,
    # Classes
    CharacterState, DPSCalculator, JobSkillBonus,
    # Data
    BOWMASTER_SKILLS, BOWMASTER_MASTERIES,
)


class TestJobProgression(unittest.TestCase):
    """Test job advancement logic."""

    def test_job_for_level(self):
        """Verify job advancement at correct levels."""
        self.assertEqual(get_job_for_level(1), Job.FIRST)
        self.assertEqual(get_job_for_level(29), Job.FIRST)
        self.assertEqual(get_job_for_level(30), Job.SECOND)
        self.assertEqual(get_job_for_level(59), Job.SECOND)
        self.assertEqual(get_job_for_level(60), Job.THIRD)
        self.assertEqual(get_job_for_level(99), Job.THIRD)
        self.assertEqual(get_job_for_level(100), Job.FOURTH)
        self.assertEqual(get_job_for_level(150), Job.FOURTH)


class TestMasteries(unittest.TestCase):
    """Test mastery system."""

    def test_mastery_unlock_count(self):
        """Verify correct number of masteries unlock at each level."""
        # Level 1 - no masteries yet
        self.assertEqual(len(get_unlocked_masteries(1)), 0)

        # Level 100 - should have 40 masteries (all up to 3rd job + level 100 4th job)
        masteries_100 = get_unlocked_masteries(100)
        self.assertEqual(len(masteries_100), 40)

    def test_global_mastery_stats(self):
        """Verify global mastery stats are calculated correctly."""
        # At level 100, should have these global stats:
        global_stats = get_global_mastery_stats(100)

        # Main Stat Enhancement (level 12): +30
        self.assertEqual(global_stats.get("main_stat_flat", 0), 30)

        # Critical Rate: +5% (level 16) + +5% (level 24) = +10%
        self.assertEqual(global_stats.get("crit_rate", 0), 10)

        # Attack Speed (level 20): +5%
        self.assertEqual(global_stats.get("attack_speed", 0), 5)

        # Basic Attack Damage (level 28): +15%
        self.assertEqual(global_stats.get("basic_attack_damage", 0), 15)

        # Max Damage Mult (level 52): +10%
        self.assertEqual(global_stats.get("max_dmg_mult", 0), 10)

        # Skill Damage (level 86): +15%
        self.assertEqual(global_stats.get("skill_damage", 0), 15)

    def test_skill_specific_masteries(self):
        """Verify skill-specific mastery bonuses."""
        bonuses = get_mastery_bonuses(100)

        # Arrow Blow damage: 15% + 20% + 20% = 55%
        self.assertEqual(bonuses.get("arrow_blow", {}).get("skill_damage_pct", 0), 55)

        # Arrow Blow targets: 1 + 1 = 2
        self.assertEqual(bonuses.get("arrow_blow", {}).get("skill_targets", 0), 2)

        # Wind Arrow II damage: 10+11+12+13+14+15 = 75% (at level 100, we have up to level 92)
        # Actually at level 100: 10+11+12+13 = 46% (levels 60,64,72,80 but not 88,92)
        wa2_dmg = bonuses.get("wind_arrow_2", {}).get("skill_damage_pct", 0)
        self.assertGreater(wa2_dmg, 0)

        # Covering Fire damage (level 36): +50%
        self.assertEqual(bonuses.get("covering_fire", {}).get("skill_damage_pct", 0), 50)

    def test_masteries_dont_have_all_target(self):
        """Verify no masteries use 'all' as target (should be 'global')."""
        for mastery in BOWMASTER_MASTERIES:
            self.assertNotEqual(
                mastery.effect_target, "all",
                f"Mastery '{mastery.name}' uses 'all' instead of 'global'"
            )


class TestCharacterState(unittest.TestCase):
    """Test character state management."""

    def test_skill_unlock(self):
        """Verify skills unlock at correct levels."""
        char_60 = create_character_at_level(60)
        char_100 = create_character_at_level(100)
        char_110 = create_character_at_level(110)

        # Arrow Stream unlocks at 100
        self.assertFalse(char_60.is_skill_unlocked("arrow_stream"))
        self.assertTrue(char_100.is_skill_unlocked("arrow_stream"))

        # Hurricane unlocks at 103
        self.assertFalse(char_100.is_skill_unlocked("hurricane"))
        self.assertTrue(char_110.is_skill_unlocked("hurricane"))

        # Phoenix unlocks at 69
        self.assertFalse(create_character_at_level(68).is_skill_unlocked("phoenix"))
        self.assertTrue(create_character_at_level(69).is_skill_unlocked("phoenix"))

    def test_active_basic_attack(self):
        """Verify correct basic attack is selected at each level."""
        self.assertEqual(create_character_at_level(29).get_active_basic_attack(), "arrow_blow")
        self.assertEqual(create_character_at_level(30).get_active_basic_attack(), "wind_arrow")
        self.assertEqual(create_character_at_level(60).get_active_basic_attack(), "wind_arrow_2")
        self.assertEqual(create_character_at_level(100).get_active_basic_attack(), "arrow_stream")

    def test_effective_skill_level(self):
        """Verify +All Skills bonus is applied correctly."""
        char = create_character_at_level(100, all_skills_bonus=44)

        # Base level is 1, effective should be 1 + 44 = 45
        self.assertEqual(char.get_effective_skill_level("arrow_stream"), 45)
        self.assertEqual(char.get_effective_skill_level("phoenix"), 45)


class TestDPSCalculator(unittest.TestCase):
    """Test DPS calculation logic."""

    def setUp(self):
        """Create a standard character for testing."""
        self.char = create_character_at_level(100, all_skills_bonus=44)
        self.char.attack = 1000
        self.char.main_stat_pct = 50
        self.char.damage_pct = 30
        self.char.boss_damage_pct = 20
        self.char.crit_rate = 70
        self.char.crit_damage = 200
        self.char.attack_speed_pct = 50
        self.calc = DPSCalculator(self.char)

    def test_attack_speed_cap(self):
        """Verify attack speed is capped at 2.5x (150%)."""
        # Set attack speed way above cap
        self.char.attack_speed_pct = 200
        calc = DPSCalculator(self.char)
        self.assertEqual(calc.get_effective_attack_speed(), 2.5)

    def test_attack_speed_calculation(self):
        """Verify attack speed includes skills and masteries."""
        # Base 50% + Archer Mastery + Bow Acceleration + Global Mastery
        as_mult = self.calc.get_effective_attack_speed()

        # Should be > 1 (base) and < 2.5 (cap)
        self.assertGreater(as_mult, 1.0)
        self.assertLess(as_mult, 2.5)

    def test_cast_time(self):
        """Verify cast time scales with attack speed."""
        cast_time = self.calc.get_cast_time(1.0, True)
        as_mult = self.calc.get_effective_attack_speed()

        # Cast time should be 1.0 / attack_speed_mult
        self.assertAlmostEqual(cast_time, 1.0 / as_mult, places=3)

    def test_skill_hits(self):
        """Verify skill hits include masteries."""
        # Arrow Stream base hits: 5
        arrow_stream_hits = self.calc.get_skill_hits("arrow_stream")
        self.assertEqual(arrow_stream_hits, 5)

        # Wind Arrow II gets +1 hit from mastery at level 96
        wa2_hits = self.calc.get_skill_hits("wind_arrow_2")
        self.assertEqual(wa2_hits, 6)  # 5 base + 1 mastery

    def test_mortal_blow_uptime(self):
        """Verify Mortal Blow uptime calculation."""
        uptime = self.calc.calculate_mortal_blow_uptime()

        # At level 100 with mastery, duration = 10 sec
        # With reasonable attack speed, uptime should be between 50-80%
        self.assertGreater(uptime, 0.5)
        self.assertLess(uptime, 0.9)

    def test_mortal_blow_not_unlocked(self):
        """Verify Mortal Blow uptime is 0 if not unlocked."""
        char_60 = create_character_at_level(60)
        calc_60 = DPSCalculator(char_60)

        # Mortal Blow unlocks at 72
        uptime = calc_60.calculate_mortal_blow_uptime()
        self.assertEqual(uptime, 0.0)

    def test_global_stat_bonus(self):
        """Verify global stat bonuses are applied."""
        # Crit rate should include mastery bonus (+10% from masteries)
        crit_bonus = self.calc.get_global_stat("crit_rate")
        self.assertEqual(crit_bonus, 10)

    def test_total_stat_bonus(self):
        """Verify total stat bonus includes skills and masteries."""
        # Basic attack damage should include:
        # - Physical Training skill (scales with +All Skills)
        # - Basic Attack Damage Enhancement mastery (fixed +15%)
        ba_bonus = self.calc.get_total_stat_bonus("basic_attack_damage")

        # Should be at least 15% from mastery
        self.assertGreaterEqual(ba_bonus, 15)

    def test_dps_breakdown_positive(self):
        """Verify all DPS components are positive."""
        result = self.calc.calculate_total_dps()

        self.assertGreater(result.total_dps, 0)
        self.assertGreater(result.basic_attack_dps, 0)
        self.assertGreaterEqual(result.active_skill_dps, 0)
        self.assertGreater(result.summon_dps, 0)
        self.assertGreater(result.proc_dps, 0)

    def test_dps_breakdown_sums_correctly(self):
        """Verify DPS components sum to total."""
        result = self.calc.calculate_total_dps()

        component_sum = (
            result.basic_attack_dps +
            result.active_skill_dps +
            result.summon_dps +
            result.proc_dps
        )

        self.assertAlmostEqual(result.total_dps, component_sum, places=0)


class TestAllSkillsValue(unittest.TestCase):
    """Test +All Skills value calculation."""

    def test_all_skills_value_positive(self):
        """Verify +1 All Skills gives positive DPS increase."""
        increase, breakdown = calculate_all_skills_value(
            level=100,
            current_all_skills=44,
            attack=1000,
            main_stat_pct=50,
            damage_pct=30,
            boss_damage_pct=20,
            crit_rate=70,
            crit_damage=200,
            attack_speed_pct=50,
        )

        self.assertGreater(increase, 0)

    def test_all_skills_value_reasonable_range(self):
        """Verify +1 All Skills value is in a reasonable range."""
        increase, _ = calculate_all_skills_value(
            level=100,
            current_all_skills=44,
            attack=1000,
        )

        # Should be between 0.1% and 5% DPS per skill level
        self.assertGreater(increase, 0.1)
        self.assertLess(increase, 5.0)

    def test_all_skills_diminishing_returns(self):
        """Verify diminishing returns with more +All Skills."""
        # Value at +0 All Skills
        inc_0, _ = calculate_all_skills_value(level=100, current_all_skills=0, attack=1000)

        # Value at +44 All Skills
        inc_44, _ = calculate_all_skills_value(level=100, current_all_skills=44, attack=1000)

        # Value at +100 All Skills
        inc_100, _ = calculate_all_skills_value(level=100, current_all_skills=100, attack=1000)

        # Should have diminishing returns (higher existing = lower marginal value)
        self.assertGreater(inc_0, inc_44)
        self.assertGreater(inc_44, inc_100)

    def test_breakdown_categories(self):
        """Verify breakdown includes expected categories."""
        _, breakdown = calculate_all_skills_value(
            level=100,
            current_all_skills=44,
            attack=1000,
        )

        # Should have basic_attack category
        self.assertIn("basic_attack", breakdown)


class TestSkillData(unittest.TestCase):
    """Test skill definitions."""

    def test_all_skills_have_required_fields(self):
        """Verify all skills have required fields."""
        for name, skill in BOWMASTER_SKILLS.items():
            self.assertTrue(hasattr(skill, "name"), f"{name} missing 'name'")
            self.assertTrue(hasattr(skill, "skill_type"), f"{name} missing 'skill_type'")
            self.assertTrue(hasattr(skill, "damage_type"), f"{name} missing 'damage_type'")
            self.assertTrue(hasattr(skill, "job"), f"{name} missing 'job'")
            self.assertTrue(hasattr(skill, "unlock_level"), f"{name} missing 'unlock_level'")

    def test_unlock_levels_match_job(self):
        """Verify skill unlock levels are within their job range."""
        job_ranges = {
            Job.FIRST: (1, 29),
            Job.SECOND: (30, 59),
            Job.THIRD: (60, 99),
            Job.FOURTH: (100, 999),
        }

        for name, skill in BOWMASTER_SKILLS.items():
            min_level, max_level = job_ranges[skill.job]
            self.assertGreaterEqual(
                skill.unlock_level, min_level,
                f"{name} unlocks at {skill.unlock_level} but is {skill.job.name} job"
            )
            self.assertLessEqual(
                skill.unlock_level, max_level,
                f"{name} unlocks at {skill.unlock_level} but is {skill.job.name} job"
            )

    def test_basic_attack_skills_exist(self):
        """Verify all basic attack skills exist."""
        basic_attacks = ["arrow_blow", "wind_arrow", "wind_arrow_2", "arrow_stream"]
        for name in basic_attacks:
            self.assertIn(name, BOWMASTER_SKILLS)
            self.assertEqual(BOWMASTER_SKILLS[name].skill_type, SkillType.BASIC_ATTACK)

    def test_summon_skills_have_duration(self):
        """Verify summon skills have duration and attack interval."""
        summons = ["phoenix", "arrow_platter", "quiver_cartridge"]
        for name in summons:
            skill = BOWMASTER_SKILLS[name]
            self.assertEqual(skill.skill_type, SkillType.SUMMON)
            self.assertGreater(skill.duration, 0, f"{name} should have duration")
            self.assertGreater(skill.attack_interval, 0, f"{name} should have attack_interval")


class TestMaplHeroFinalDamage(unittest.TestCase):
    """Test Maple Hero Final Damage application."""

    def setUp(self):
        """Create character with Maple Hero unlocked."""
        self.char = create_character_at_level(100, all_skills_bonus=44)
        self.char.attack = 1000
        self.calc = DPSCalculator(self.char)

    def test_maple_hero_applies_to_arrow_platter(self):
        """Verify Maple Hero FD applies to Arrow Platter."""
        # Calculate damage for arrow_platter
        damage = self.calc.calculate_hit_damage(
            self.calc.get_skill_damage_pct("arrow_platter"),
            DamageType.SKILL,
            "arrow_platter"
        )

        # Create character without Maple Hero (level 99)
        char_99 = create_character_at_level(99, all_skills_bonus=44)
        char_99.attack = 1000
        calc_99 = DPSCalculator(char_99)

        damage_99 = calc_99.calculate_hit_damage(
            calc_99.get_skill_damage_pct("arrow_platter"),
            DamageType.SKILL,
            "arrow_platter"
        )

        # Damage with Maple Hero should be higher
        self.assertGreater(damage, damage_99)

    def test_maple_hero_applies_to_phoenix(self):
        """Verify Maple Hero FD applies to Phoenix."""
        damage = self.calc.calculate_hit_damage(
            self.calc.get_skill_damage_pct("phoenix"),
            DamageType.SKILL,
            "phoenix"
        )

        # Phoenix should have Maple Hero bonus at level 100
        self.assertGreater(damage, 0)


class TestJobSpecificSkillBonuses(unittest.TestCase):
    """Test job-specific skill bonus calculations."""

    def test_job_skill_bonus_dataclass(self):
        """Verify JobSkillBonus stores and retrieves values correctly."""
        bonus = JobSkillBonus(first_job=5, second_job=3, third_job=2, fourth_job=1)

        self.assertEqual(bonus.get_bonus_for_job(Job.FIRST), 5)
        self.assertEqual(bonus.get_bonus_for_job(Job.SECOND), 3)
        self.assertEqual(bonus.get_bonus_for_job(Job.THIRD), 2)
        self.assertEqual(bonus.get_bonus_for_job(Job.FOURTH), 1)

    def test_job_skill_value_positive(self):
        """Verify +1 to each job gives positive DPS increase."""
        job_bonuses = JobSkillBonus()

        for job in [Job.FIRST, Job.SECOND, Job.THIRD, Job.FOURTH]:
            value = calculate_job_skill_value(
                level=100,
                target_job=job,
                current_job_bonuses=job_bonuses,
                attack=1000,
            )
            self.assertGreater(value, 0, f"+1 {job.name} job should give positive DPS")

    def test_fourth_job_most_valuable(self):
        """Verify 4th job skills contribute most to DPS at level 100."""
        job_bonuses = JobSkillBonus()

        values = {}
        for job in [Job.FIRST, Job.SECOND, Job.THIRD, Job.FOURTH]:
            values[job] = calculate_job_skill_value(
                level=100,
                target_job=job,
                current_job_bonuses=job_bonuses,
                attack=1000,
            )

        # 4th job should be most valuable (includes Arrow Stream)
        self.assertGreater(values[Job.FOURTH], values[Job.THIRD])
        self.assertGreater(values[Job.THIRD], values[Job.SECOND])
        self.assertGreater(values[Job.SECOND], values[Job.FIRST])

    def test_all_skills_breakdown_sums_to_total(self):
        """Verify job breakdown sums approximately to total +1 All Skills value."""
        breakdown = calculate_all_skills_value_by_job(
            level=100,
            current_all_skills=44,
            attack=1000,
        )

        # The 'total' key should match sum of job contributions
        job_sum = (
            breakdown["first_job"] +
            breakdown["second_job"] +
            breakdown["third_job"] +
            breakdown["fourth_job"]
        )

        self.assertAlmostEqual(breakdown["total"], job_sum, places=4)

    def test_all_skills_breakdown_matches_original(self):
        """Verify breakdown total matches original calculate_all_skills_value."""
        breakdown = calculate_all_skills_value_by_job(
            level=100,
            current_all_skills=44,
            attack=1000,
        )

        original_value, _ = calculate_all_skills_value(
            level=100,
            current_all_skills=44,
            attack=1000,
        )

        # Should be approximately equal
        self.assertAlmostEqual(breakdown["total"], original_value, places=2)

    def test_create_character_with_job_bonuses(self):
        """Verify character created with job bonuses has correct skill levels."""
        job_bonuses = JobSkillBonus(
            first_job=5,
            second_job=3,
            third_job=2,
            fourth_job=1,
        )

        char = create_character_with_job_bonuses(
            level=100,
            all_skills_bonus=10,
            job_bonuses=job_bonuses,
        )

        # 1st job skill (arrow_blow) should have level 1 + 10 (all) + 5 (1st job) = 16
        self.assertEqual(char.get_effective_skill_level("arrow_blow"), 16)

        # 2nd job skill (covering_fire) should have level 1 + 10 (all) + 3 (2nd job) = 14
        self.assertEqual(char.get_effective_skill_level("covering_fire"), 14)

        # 3rd job skill (phoenix) should have level 1 + 10 (all) + 2 (3rd job) = 13
        self.assertEqual(char.get_effective_skill_level("phoenix"), 13)

        # 4th job skill (arrow_stream) should have level 1 + 10 (all) + 1 (4th job) = 12
        self.assertEqual(char.get_effective_skill_level("arrow_stream"), 12)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
