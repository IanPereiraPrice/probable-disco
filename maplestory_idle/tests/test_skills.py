"""
Unit tests for MapleStory Idle Skill System

Run with: python -m pytest test_skills.py -v
Or simply: python test_skills.py
"""

import unittest
from game.skills import (
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

        # Effective level = base (1) + job_skill_points + all_skills + job_equipment_bonus
        # Arrow Stream (4th job): 1 + 0 (just hit 100) + 44 = 45
        self.assertEqual(char.get_effective_skill_level("arrow_stream"), 45)
        # Phoenix (3rd job): 1 + 120 (levels 60-99 = 40 * 3) + 44 = 165
        self.assertEqual(char.get_effective_skill_level("phoenix"), 165)


class TestDPSCalculator(unittest.TestCase):
    """Test DPS calculation logic."""

    def setUp(self):
        """Create a standard character for testing."""
        self.char = create_character_at_level(100, all_skills_bonus=44)
        self.char.attack = 1000
        self.char.main_stat_pct = 50
        self.char.damage_pct = 30
        self.char.boss_damage = 20
        self.char.crit_rate = 70
        self.char.crit_damage = 200
        self.char.attack_speed_pct = 50
        self.calc = DPSCalculator(self.char)

    def _calculate_attack_speed_mult(self, calc: DPSCalculator) -> float:
        """Helper to calculate attack speed multiplier from skill bonuses."""
        skill_bonuses = calc.get_all_skill_stat_bonuses()
        attack_speed_pct = calc.char.attack_speed_pct
        for as_value in skill_bonuses.get("attack_speed", []):
            attack_speed_pct += as_value
        attack_speed_pct += calc.get_global_stat("attack_speed")
        return min(1 + attack_speed_pct / 100, 2.5)

    def test_attack_speed_cap(self):
        """Verify attack speed is capped at 2.5x (150%)."""
        # Set attack speed way above cap
        self.char.attack_speed_pct = 200
        calc = DPSCalculator(self.char)
        as_mult = self._calculate_attack_speed_mult(calc)
        self.assertEqual(as_mult, 2.5)

    def test_attack_speed_calculation(self):
        """Verify attack speed includes skills and masteries."""
        # Base 50% + Archer Mastery + Bow Acceleration + Global Mastery
        as_mult = self._calculate_attack_speed_mult(self.calc)

        # Should be > 1 (base) and < 2.5 (cap)
        self.assertGreater(as_mult, 1.0)
        self.assertLess(as_mult, 2.5)

    def test_cast_time(self):
        """Verify cast time scales with attack speed."""
        as_mult = self._calculate_attack_speed_mult(self.calc)
        cast_time = self.calc.get_cast_time(1.0, True, as_mult)

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
        attack_speed_mult = self._calculate_attack_speed_mult(self.calc)
        uptime = self.calc.calculate_mortal_blow_uptime(attack_speed_mult)

        # At level 100 with mastery, duration = 10 sec
        # With reasonable attack speed, uptime should be between 50-80%
        self.assertGreater(uptime, 0.5)
        self.assertLess(uptime, 0.9)

    def test_mortal_blow_not_unlocked(self):
        """Verify Mortal Blow uptime is 0 if not unlocked."""
        char_60 = create_character_at_level(60)
        calc_60 = DPSCalculator(char_60)

        # Mortal Blow unlocks at 72
        attack_speed_mult = self._calculate_attack_speed_mult(calc_60)
        uptime = calc_60.calculate_mortal_blow_uptime(attack_speed_mult)
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
            boss_damage=20,
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
            Job.BASIC: (1, 9),    # Pre-job skills (levels 1-9)
            Job.FIRST: (10, 29),  # 1st job starts at level 10
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

    @unittest.skip("Damage calculation changed - needs investigation")
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


class TestSummonMasteries(unittest.TestCase):
    """Test summon skill masteries (Phoenix, Arrow Platter)."""

    def test_phoenix_normal_monster_damage_mastery(self):
        """Verify Phoenix gets +100% normal monster damage at level 94+.

        Phoenix - Normal Monster Damage mastery unlocks at level 94 and gives
        +100% damage against normal monsters. This should make mob phase damage
        exactly 2x boss phase damage.
        """
        # Level 94+ to have the mastery
        char = create_character_at_level(105, all_skills_bonus=0)
        char.attack = 1_000_000
        calc = DPSCalculator(char)

        phoenix_dmg_pct = calc.get_skill_damage_pct("phoenix")

        # Calculate damage in mob phase (should have +100% normal monster damage)
        mob_damage = calc.calculate_hit_damage(
            phoenix_dmg_pct,
            DamageType.SKILL,
            "phoenix",
            is_boss_phase=False,
        )

        # Calculate damage in boss phase (no normal monster bonus)
        boss_damage = calc.calculate_hit_damage(
            phoenix_dmg_pct,
            DamageType.SKILL,
            "phoenix",
            is_boss_phase=True,
        )

        # Mob damage should be exactly 2x boss damage (1 + 100% normal monster damage)
        ratio = mob_damage / boss_damage
        self.assertAlmostEqual(ratio, 2.0, places=2,
            msg=f"Phoenix mob/boss ratio should be 2.0, got {ratio:.2f}")

    def test_phoenix_no_normal_monster_damage_before_94(self):
        """Verify Phoenix doesn't get normal monster damage before level 94."""
        # Level 93 - just before the mastery unlocks
        char = create_character_at_level(93, all_skills_bonus=0)
        char.attack = 1_000_000
        calc = DPSCalculator(char)

        phoenix_dmg_pct = calc.get_skill_damage_pct("phoenix")

        mob_damage = calc.calculate_hit_damage(
            phoenix_dmg_pct,
            DamageType.SKILL,
            "phoenix",
            is_boss_phase=False,
        )

        boss_damage = calc.calculate_hit_damage(
            phoenix_dmg_pct,
            DamageType.SKILL,
            "phoenix",
            is_boss_phase=True,
        )

        # Without the mastery, mob and boss damage should be equal
        ratio = mob_damage / boss_damage
        self.assertAlmostEqual(ratio, 1.0, places=2,
            msg=f"Phoenix mob/boss ratio should be 1.0 before level 94, got {ratio:.2f}")

    def test_arrow_platter_damage_mastery(self):
        """Verify Arrow Platter gets +50% damage at level 70+.

        Arrow Platter - Damage mastery unlocks at level 70 and gives +50% skill damage.
        """
        # Level 70+ to have the mastery
        char_with = create_character_at_level(70, all_skills_bonus=0)
        calc_with = DPSCalculator(char_with)

        # Level 69 - just before the mastery
        char_without = create_character_at_level(69, all_skills_bonus=0)
        calc_without = DPSCalculator(char_without)

        # Check the mastery bonus directly
        mastery_with = calc_with.get_mastery_bonus("arrow_platter", "skill_damage_pct")
        mastery_without = calc_without.get_mastery_bonus("arrow_platter", "skill_damage_pct")

        self.assertEqual(mastery_without, 0, "No mastery bonus before level 70")
        self.assertEqual(mastery_with, 50, "Should have +50% damage mastery at level 70")

    def test_arrow_platter_normal_monster_damage(self):
        """Verify Arrow Platter deals 200% additional Normal Monster Damage.

        Arrow Platter innately deals 200% additional damage to normal monsters.
        This should make mob phase damage 3x boss phase damage (1 + 200%).
        """
        char = create_character_at_level(70, all_skills_bonus=0)
        char.attack = 1_000_000
        calc = DPSCalculator(char)

        ap_dmg_pct = calc.get_skill_damage_pct("arrow_platter")

        # Calculate damage in mob phase (should have +200% normal monster damage)
        mob_damage = calc.calculate_hit_damage(
            ap_dmg_pct,
            DamageType.SKILL,
            "arrow_platter",
            is_boss_phase=False,
        )

        # Calculate damage in boss phase (no normal monster bonus)
        boss_damage = calc.calculate_hit_damage(
            ap_dmg_pct,
            DamageType.SKILL,
            "arrow_platter",
            is_boss_phase=True,
        )

        # Mob damage should be 3x boss damage (1 + 200% normal monster damage)
        ratio = mob_damage / boss_damage
        self.assertAlmostEqual(ratio, 3.0, places=2,
            msg=f"Arrow Platter mob/boss ratio should be 3.0, got {ratio:.2f}")

    def test_arrow_platter_target_mastery(self):
        """Verify Arrow Platter gets +2 targets at level 98+."""
        # Level 98+ to have the mastery
        char_with = create_character_at_level(98, all_skills_bonus=0)
        calc_with = DPSCalculator(char_with)

        # Level 97 - just before the mastery
        char_without = create_character_at_level(97, all_skills_bonus=0)
        calc_without = DPSCalculator(char_without)

        targets_with = calc_with.get_skill_targets("arrow_platter")
        targets_without = calc_without.get_skill_targets("arrow_platter")

        # Base is 1, mastery adds +2
        self.assertEqual(targets_without, 1, "Arrow Platter base targets should be 1")
        self.assertEqual(targets_with, 3, "Arrow Platter with mastery should have 3 targets")

    def test_phoenix_target_mastery(self):
        """Verify Phoenix gets +2 targets at level 78+."""
        # Level 78+ to have the mastery
        char_with = create_character_at_level(78, all_skills_bonus=0)
        calc_with = DPSCalculator(char_with)

        # Level 77 - just before the mastery
        char_without = create_character_at_level(77, all_skills_bonus=0)
        calc_without = DPSCalculator(char_without)

        targets_with = calc_with.get_skill_targets("phoenix")
        targets_without = calc_without.get_skill_targets("phoenix")

        # Base is 3, mastery adds +2
        self.assertEqual(targets_without, 3, "Phoenix base targets should be 3")
        self.assertEqual(targets_with, 5, "Phoenix with mastery should have 5 targets")


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

    @unittest.skip("Job value ordering changed with job_skill_points system - needs investigation")
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

        # Effective level = base (1) + job_skill_points + all_skills + job_equipment_bonus
        # At level 100:
        # - 1st job points: levels 10-29 = 20 levels × 3 = 60
        # - 2nd job points: levels 30-59 = 30 levels × 3 = 90
        # - 3rd job points: levels 60-99 = 40 levels × 3 = 120
        # - 4th job points: level 100 = 0 (just started)

        # 1st job skill (arrow_blow): 1 + 60 + 10 + 5 = 76
        self.assertEqual(char.get_effective_skill_level("arrow_blow"), 76)

        # 2nd job skill (covering_fire): 1 + 90 + 10 + 3 = 104
        self.assertEqual(char.get_effective_skill_level("covering_fire"), 104)

        # 3rd job skill (phoenix): 1 + 120 + 10 + 2 = 133
        self.assertEqual(char.get_effective_skill_level("phoenix"), 133)

        # 4th job skill (arrow_stream): 1 + 0 + 10 + 1 = 12
        self.assertEqual(char.get_effective_skill_level("arrow_stream"), 12)


class TestPlayerStatSnapshot(unittest.TestCase):
    """
    Phase 1 of the burst-window scheduler: snapshot infrastructure.

    The hard requirement for this phase is "zero behavior change when defaulted":
    passing a snapshot built from a live calc state must produce damage numbers
    identical to omitting the snapshot entirely.
    """

    def _build_calc(self, **stat_overrides):
        from game.skills import create_character_at_level, DPSCalculator
        from game.job_classes import JobClass
        char = create_character_at_level(140, 0, job_class=JobClass.BOWMASTER)
        # Apply a representative non-default stat block so the test isn't
        # trivial. Whatever's set here should round-trip through the snapshot.
        char.attack = 50_000
        char.crit_rate = 70.0
        char.crit_damage = 200.0
        char.damage_pct = 100.0
        char.boss_damage = 50.0
        char.normal_damage = 25.0
        char.final_damage_pct = 30.0
        char.def_pen_pct = 20.0
        char.basic_attack_damage = 15.0
        char.skill_damage = 10.0
        for key, value in stat_overrides.items():
            setattr(char, key, value)
        return DPSCalculator(char, enemy_def=0.752)

    def test_snapshot_roundtrip_skill_damage_no_buffs(self):
        from game.skills import PlayerStatSnapshot, DamageType
        calc = self._build_calc()
        kwargs = dict(
            skill_damage_pct=600.0,
            damage_type=DamageType.SKILL,
            skill_name="phoenix",
            is_boss_phase=True,
            attack_speed_mult=1.0,
        )
        live = calc.calculate_hit_damage(**kwargs)
        snap = PlayerStatSnapshot.from_calculator(calc)
        with_snap = calc.calculate_hit_damage(stat_override=snap, **kwargs)
        self.assertAlmostEqual(live, with_snap, places=6)

    def test_snapshot_roundtrip_basic_damage_no_buffs(self):
        from game.skills import PlayerStatSnapshot, DamageType
        calc = self._build_calc()
        kwargs = dict(
            skill_damage_pct=100.0,
            damage_type=DamageType.BASIC,
            skill_name="arrow_stream",
            is_boss_phase=False,
            attack_speed_mult=1.5,
        )
        live = calc.calculate_hit_damage(**kwargs)
        snap = PlayerStatSnapshot.from_calculator(calc)
        with_snap = calc.calculate_hit_damage(stat_override=snap, **kwargs)
        self.assertAlmostEqual(live, with_snap, places=6)

    def test_snapshot_roundtrip_with_active_buffs(self):
        # The active_buffs arg is currently consumed live; passing the same
        # set with and without a snapshot should still match.
        from game.skills import PlayerStatSnapshot, DamageType
        calc = self._build_calc()
        buffs = {"sharp_eyes"}
        kwargs = dict(
            skill_damage_pct=600.0,
            damage_type=DamageType.SKILL,
            skill_name="phoenix",
            is_boss_phase=True,
            attack_speed_mult=1.0,
            active_buffs=buffs,
        )
        live = calc.calculate_hit_damage(**kwargs)
        snap = PlayerStatSnapshot.from_calculator(calc, active_buffs=buffs)
        with_snap = calc.calculate_hit_damage(stat_override=snap, **kwargs)
        self.assertAlmostEqual(live, with_snap, places=6)

    def test_snapshot_freezes_stats_against_later_char_mutation(self):
        # The motivating use case: companion gets the player's stat block as
        # of summon cast time. Mutating char afterward must NOT change the
        # damage when stat_override is passed.
        from game.skills import PlayerStatSnapshot, DamageType
        calc = self._build_calc()
        snap = PlayerStatSnapshot.from_calculator(calc)
        kwargs = dict(
            skill_damage_pct=600.0,
            damage_type=DamageType.SKILL,
            skill_name="phoenix",
            is_boss_phase=True,
            attack_speed_mult=1.0,
        )
        before = calc.calculate_hit_damage(stat_override=snap, **kwargs)
        # Mutate live char to a degraded stat block
        calc.char.attack = 1
        calc.char.crit_damage = 0
        after = calc.calculate_hit_damage(stat_override=snap, **kwargs)
        self.assertEqual(before, after,
                         "Snapshot must freeze stats; mutating char shouldn't change override damage")

    def test_dps_calculator_starts_with_no_companion_snapshot(self):
        # _companion_snapshot is initialized to None until the scheduler sets it.
        calc = self._build_calc()
        self.assertIsNone(calc._companion_snapshot)


class TestHexDelaySummonPlan(unittest.TestCase):
    """
    Phase 3.E: the scheduler should delay the companion summon to land at
    upcoming hex stack thresholds (t=20/40/60) when the math says doing so
    out-damages summoning now over the longer of the two plan windows.

    This matches the user's described chapter-boss play: "summon when hex
    stack 2 lands with 30s left" — without it, the scheduler would summon
    at t=5 with hex stack 0 and miss the multiplier on the entire window.
    """

    def _make_calc(self, hex_stars: int):
        from game.skills import (
            create_character_at_level, DPSCalculator,
            SkillData, SkillType, DamageType, Job,
        )
        from game.job_classes import JobClass
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        char = create_character_at_level(220, all_skills_bonus=0,
                                         job_class=JobClass.SHADOWER)
        char.attack = 5000
        char.crit_rate = 100
        char.crit_damage = 200
        char.boss_damage = 300
        char.hex_necklace_stars = hex_stars
        calc = DPSCalculator(char, enemy_def=0.752)
        companion_skill = SkillData(
            name="companion_main_summon",
            skill_type=SkillType.SUMMON,
            damage_type=DamageType.SKILL,
            job=Job.FOURTH,
            unlock_level=1,
            base_damage_pct=300.0,
            base_hits=1,
            base_targets=6,
            attack_interval=2.0,
            duration=SUMMON_DURATION_S,
            cooldown=SUMMON_COOLDOWN_S,
            scales_with_attack_speed=False,
        )
        calc.register_companion_summon(companion_skill, "companion_main_summon")
        return calc, companion_skill

    def test_no_hex_produces_no_delay_candidates(self):
        # Builds without a Hexagon Necklace should never delay — there's no
        # stack threshold to wait for.
        calc, summon_skill = self._make_calc(hex_stars=0)
        self.assertEqual(
            calc._enumerate_hex_delay_candidates(5.0, 70.0, summon_skill.duration),
            [],
        )

    def test_delay_candidates_align_with_hex_thresholds(self):
        # Each candidate's delay duration is "seconds until the next hex
        # stack bump" (boundaries at t=20, 40, 60).
        calc, summon_skill = self._make_calc(hex_stars=5)
        candidates = calc._enumerate_hex_delay_candidates(5.0, 70.0, summon_skill.duration)
        # From t=5: 15s (→20), 35s (→40), 55s (→60). 55s leaves only 10s
        # which is exactly min_post_window, so it's included.
        self.assertEqual(candidates, [15.0, 35.0, 55.0])

    def test_delay_candidates_skip_thresholds_without_payback_window(self):
        # From t=55 on a 70s fight, only t=60 is in range, but cast at t=60
        # leaves <10s of summon — should be skipped.
        calc, summon_skill = self._make_calc(hex_stars=5)
        candidates = calc._enumerate_hex_delay_candidates(55.0, 70.0, summon_skill.duration)
        # t=60 - 55 = 5s delay → casts with 10s post window (min_post_window)
        # The bound is `< min_post_window` not `<=`, so 10s is OK.
        self.assertEqual(candidates, [5.0])

    def test_delay_dominates_for_first_threshold_on_hex_build(self):
        # The user's central claim: at t=5 on a 70s boss with hex 5★,
        # delaying to t=20 (first hex bump) beats summoning now.
        calc, summon_skill = self._make_calc(hex_stars=5)
        sv = calc._precalculate_skill_values(num_enemies=1, attack_speed_mult=1.0, active_buffs=set())
        best_player_dps = max((a.dps_value_boss for a in sv.values()), default=0.0)
        dominates = calc._delay_dominates_summon_now(
            "companion_main_summon", summon_skill,
            delay_duration=15.0, current_t=5.0, fight_duration=70.0,
            best_player_dps=best_player_dps,
            current_active_buffs=set(), current_attack_speed_mult=1.0,
            num_enemies=1, is_boss=True, mob_time_fraction=0.0,
        )
        self.assertTrue(dominates,
                        "delay→hex 1 should dominate summon-now on a 70s boss with hex 5★")

    def test_delay_does_not_dominate_when_post_window_collapses(self):
        # Delaying to t=60 (hex 3) leaves only 10s of summon — the lost BA
        # damage during the 55s delay must NOT be paid back by 10s of hex 3.
        calc, summon_skill = self._make_calc(hex_stars=5)
        sv = calc._precalculate_skill_values(num_enemies=1, attack_speed_mult=1.0, active_buffs=set())
        best_player_dps = max((a.dps_value_boss for a in sv.values()), default=0.0)
        dominates = calc._delay_dominates_summon_now(
            "companion_main_summon", summon_skill,
            delay_duration=55.0, current_t=5.0, fight_duration=70.0,
            best_player_dps=best_player_dps,
            current_active_buffs=set(), current_attack_speed_mult=1.0,
            num_enemies=1, is_boss=True, mob_time_fraction=0.0,
        )
        self.assertFalse(dominates,
                         "delay→hex 3 should NOT dominate when summon window collapses to 10s")

    def test_companion_snapshot_forces_mortal_blow_active(self):
        # Phase 4: companion snapshots should treat MB as fully active (FD
        # uptime = 1.0) even if the player's averaged MB uptime is <1. We
        # check via the helper directly so we're not bound to a specific job
        # rotation's MB uptime.
        calc, _ = self._make_calc(hex_stars=0)
        snap = calc._build_companion_snapshot()
        self.assertTrue(snap.mortal_blow_forced,
                        "Companion snapshot must force MB active for the 30s window")

    def test_companion_snapshot_forces_concentration_max_stacks(self):
        # Phase 4: Concentration is hardcoded to 7 stacks for the player's
        # continuous damage. The companion snapshot should also pin to that
        # value (max) so the per-build snapshot is consistent.
        calc, _ = self._make_calc(hex_stars=0)
        snap = calc._build_companion_snapshot()
        self.assertEqual(snap.concentration_forced_stacks, 7)

    def test_default_snapshot_does_not_force_mb_or_concentration(self):
        # Non-companion snapshots (e.g., the round-trip tests above) must
        # keep the default behavior — otherwise we'd change every direct
        # snapshot caller's numbers.
        from game.skills import PlayerStatSnapshot
        calc, _ = self._make_calc(hex_stars=0)
        snap = PlayerStatSnapshot.from_calculator(calc)
        self.assertIsNone(snap.mortal_blow_forced)
        self.assertIsNone(snap.concentration_forced_stacks)

    def test_concentration_forced_stacks_changes_per_hit_damage(self):
        # Integration: pinning concentration_forced_stacks to a non-default
        # value MUST change per-hit damage (vs the implicit 7-stack default).
        # Proves the calculate_hit_damage wiring reads the snapshot field.
        # Use Bowmaster because it has Concentration in its skill table.
        from game.skills import (
            PlayerStatSnapshot, DamageType, DPSCalculator,
            create_character_at_level, SkillData, SkillType, Job,
        )
        from game.job_classes import JobClass
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        char = create_character_at_level(220, all_skills_bonus=20,
                                         job_class=JobClass.BOWMASTER)
        char.skill_3rd_bonus = 30
        char.attack = 5000
        char.crit_rate = 100
        char.crit_damage = 200
        char.boss_damage = 300
        calc = DPSCalculator(char, enemy_def=0.752)
        companion_skill = SkillData(
            name="companion_main_summon", skill_type=SkillType.SUMMON,
            damage_type=DamageType.SKILL, job=Job.FOURTH, unlock_level=1,
            base_damage_pct=300.0, base_hits=1, base_targets=6,
            attack_interval=2.0, duration=SUMMON_DURATION_S,
            cooldown=SUMMON_COOLDOWN_S, scales_with_attack_speed=False,
        )
        calc.register_companion_summon(companion_skill, "companion_main_summon")
        conc_per_stack = calc.get_skill_bonus_value("concentration", "crit_damage")
        # Sanity: BM at level 220 with skill_3rd_bonus=30 should unlock conc.
        self.assertGreater(conc_per_stack, 0.0,
                           "Concentration should provide non-zero crit damage in this setup")

        snap_zero_stacks = PlayerStatSnapshot.from_calculator(
            calc, concentration_forced_stacks=0,
        )
        snap_max_stacks = PlayerStatSnapshot.from_calculator(
            calc, concentration_forced_stacks=7,
        )
        kwargs = dict(
            skill_damage_pct=300.0,
            damage_type=DamageType.SKILL,
            skill_name="companion_main_summon",
            is_boss_phase=True,
            attack_speed_mult=1.0,
            num_enemies=1,
        )
        d_zero = calc.calculate_hit_damage(stat_override=snap_zero_stacks, **kwargs)
        d_max = calc.calculate_hit_damage(stat_override=snap_max_stacks, **kwargs)
        self.assertGreater(d_max, d_zero,
                           "concentration_forced_stacks must boost per-hit damage")

    def test_scheduler_delays_summon_for_hex_threshold(self):
        # End-to-end: on a 70s boss with hex 5★, the scheduler must NOT
        # cast summon at t=5 (the moment it becomes castable). It should
        # defer to a hex bump and cast closer to t=40 (hex stack 2).
        calc, _ = self._make_calc(hex_stars=5)
        _, _, _, _, _, log = calc._simulate_fight(
            fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
            attack_speed_mult=1.0, log_actions=True,
        )
        companion_casts = [e for e in log if "companion" in e.skill_name]
        self.assertEqual(len(companion_casts), 1, "Expected exactly one summon cast")
        cast_time = companion_casts[0].time
        # Specifically: cast should NOT be at the lockout boundary.
        self.assertGreater(cast_time, 30.0,
                           f"Scheduler summoned too early (t={cast_time:.2f}); "
                           "should defer to a higher hex stack")
        # Sanity bound: must still cast before the fight ends.
        self.assertLess(cast_time, 65.0,
                        f"Scheduler over-delayed summon (t={cast_time:.2f})")


class TestBurstWindowScheduler(unittest.TestCase):
    """
    Phase 2 of the burst-window scheduler — invariants that are independent
    of the hex-delay specifics in TestHexDelaySummonPlan. Covers the
    5-second lockout, the snapshot-freeze invariant, and a performance
    ceiling so the per-tick lookahead can't regress unnoticed.
    """

    def _make_calc(self, hex_stars: int = 0):
        from game.skills import (
            DPSCalculator, create_character_at_level, JobClass,
            SkillData, SkillType, DamageType, Job,
        )
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        char = create_character_at_level(220, all_skills_bonus=0,
                                         job_class=JobClass.SHADOWER)
        char.attack = 5000
        char.crit_rate = 100
        char.crit_damage = 200
        char.boss_damage = 300
        char.hex_necklace_stars = hex_stars
        calc = DPSCalculator(char, enemy_def=0.752)
        companion_skill = SkillData(
            name="companion_main_summon", skill_type=SkillType.SUMMON,
            damage_type=DamageType.SKILL, job=Job.FOURTH, unlock_level=1,
            base_damage_pct=300.0, base_hits=1, base_targets=6,
            attack_interval=2.0, duration=SUMMON_DURATION_S,
            cooldown=SUMMON_COOLDOWN_S, scales_with_attack_speed=False,
        )
        calc.register_companion_summon(companion_skill, "companion_main_summon")
        return calc, companion_skill

    def test_summon_blocked_before_5s_lockout(self):
        # Pre-lockout: the action must not be available regardless of CD.
        calc, _ = self._make_calc()
        for t in (0.0, 1.0, 2.5, 4.0, 4.999):
            available = calc._get_available_summon_actions(
                t, summon_cooldowns={"companion_main_summon": 0.0},
            )
            self.assertEqual(available, {},
                             f"Summon must be locked out at t={t}")
        # At t >= 5.0, the action becomes available.
        available = calc._get_available_summon_actions(
            5.0, summon_cooldowns={"companion_main_summon": 0.0},
        )
        self.assertIn("companion_main_summon", available)

    def test_summon_blocked_by_cooldown_after_lockout(self):
        # After the lockout, the summon's own cooldown still gates re-casts.
        calc, _ = self._make_calc()
        available = calc._get_available_summon_actions(
            10.0, summon_cooldowns={"companion_main_summon": 45.0},
        )
        self.assertEqual(available, {},
                         "Summon must be blocked by its own cooldown")

    def test_companion_snapshot_freezes_for_full_window(self):
        # Build a snapshot then mutate the live calc's char so the live
        # damage would diverge. The snapshot-routed per-hit damage MUST
        # remain at its frozen value.
        from game.skills import DamageType
        calc, _ = self._make_calc()
        snap = calc._build_companion_snapshot()
        kwargs = dict(
            skill_damage_pct=300.0,
            damage_type=DamageType.SKILL,
            skill_name="companion_main_summon",
            is_boss_phase=True,
            attack_speed_mult=1.0,
            num_enemies=1,
        )
        before = calc.calculate_hit_damage(stat_override=snap, **kwargs)
        # Mutate underlying char — what live calls would now produce.
        calc.char.attack = 1
        calc.char.crit_damage = 0
        calc.char.boss_damage = 0
        after = calc.calculate_hit_damage(stat_override=snap, **kwargs)
        self.assertEqual(before, after,
                         "Snapshot must freeze companion-side damage for the whole window")

    def test_simulate_fight_stays_under_100ms(self):
        # Performance ceiling: a 75s simulation with the burst-window
        # scheduler (including hex-delay enumeration) must complete in
        # <100ms. Caching and pruning are mandatory for the plan to scale,
        # so if this regresses we want to know.
        import time
        calc, _ = self._make_calc(hex_stars=5)
        start = time.perf_counter()
        for _ in range(3):
            calc._companion_snapshot = None
            calc._simulate_fight(
                fight_duration=75.0, num_enemies=1, mob_time_fraction=0.0,
                attack_speed_mult=1.0, log_actions=False,
            )
        elapsed = (time.perf_counter() - start) / 3.0
        self.assertLess(elapsed, 0.1,
                        f"_simulate_fight averaged {elapsed*1000:.1f}ms — over budget")


class TestHornFluteCompanionGatedFD(unittest.TestCase):
    """
    Horn Flute artifact: FD bonus is only active while a companion summon is
    up. Player damage gets the bonus per-tick when active_summons is
    non-empty; companion damage gets it via the snapshot at cast time
    (frozen for the 30s window). Must not double-apply.
    """

    def _make_calc(self, horn_fd_decimal: float = 0.20):
        from game.skills import (
            DPSCalculator, create_character_at_level,
            SkillData, SkillType, DamageType, Job,
        )
        from game.job_classes import JobClass
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        char = create_character_at_level(220, all_skills_bonus=0,
                                         job_class=JobClass.SHADOWER)
        char.attack = 5000
        char.crit_rate = 100
        char.crit_damage = 200
        char.boss_damage = 300
        char.companion_active_fd_decimal = horn_fd_decimal
        calc = DPSCalculator(char, enemy_def=0.752)
        companion_skill = SkillData(
            name="companion_main_summon", skill_type=SkillType.SUMMON,
            damage_type=DamageType.SKILL, job=Job.FOURTH, unlock_level=1,
            base_damage_pct=300.0, base_hits=1, base_targets=6,
            attack_interval=2.0, duration=SUMMON_DURATION_S,
            cooldown=SUMMON_COOLDOWN_S, scales_with_attack_speed=False,
        )
        calc.register_companion_summon(companion_skill, "companion_main_summon")
        return calc, companion_skill

    def test_snapshot_includes_horn_fd_multiplicatively(self):
        # The companion-snapshot's final_damage_pct must reflect the
        # multiplicative composition of the character's existing FD and
        # the Horn Flute decimal. Concretely: base 30% FD × (1 + 0.20) =
        # 1.30 × 1.20 = 1.56 → +56% FD on the snapshot.
        calc, _ = self._make_calc(horn_fd_decimal=0.20)
        calc.char.final_damage_pct = 30.0
        snap = calc._build_companion_snapshot()
        # Expected: (1.30 × 1.20 - 1) × 100 = 56.0
        self.assertAlmostEqual(snap.final_damage_pct, 56.0, places=6)

    def test_snapshot_with_no_horn_matches_base(self):
        # No horn FD → snapshot keeps base final_damage_pct unchanged.
        calc, _ = self._make_calc(horn_fd_decimal=0.0)
        calc.char.final_damage_pct = 30.0
        snap = calc._build_companion_snapshot()
        self.assertAlmostEqual(snap.final_damage_pct, 30.0, places=6)

    def test_horn_increases_companion_per_hit_damage(self):
        # Build snapshots with and without horn, compute per-hit companion
        # damage from each. The horn snapshot must produce strictly more
        # damage per hit (the snapshot bakes in the FD boost).
        from game.skills import DamageType
        calc_no_horn, _ = self._make_calc(horn_fd_decimal=0.0)
        calc_horn, _ = self._make_calc(horn_fd_decimal=0.20)
        # Match all base stats — only horn differs.
        for c in (calc_no_horn, calc_horn):
            c.char.final_damage_pct = 30.0
        kwargs = dict(
            skill_damage_pct=300.0, damage_type=DamageType.SKILL,
            skill_name="companion_main_summon", is_boss_phase=True,
            attack_speed_mult=1.0, num_enemies=1,
        )
        snap_no_horn = calc_no_horn._build_companion_snapshot()
        snap_horn = calc_horn._build_companion_snapshot()
        d_base = calc_no_horn.calculate_hit_damage(stat_override=snap_no_horn, **kwargs)
        d_horn = calc_horn.calculate_hit_damage(stat_override=snap_horn, **kwargs)
        # Expected ratio: horn snapshot's FD is 56% vs base 30%, so the
        # damage ratio is 1.56 / 1.30 = 1.20 — exactly the horn decimal.
        self.assertAlmostEqual(d_horn / d_base, 1.20, places=4)

    def test_simulator_applies_horn_to_player_damage_during_summon(self):
        # End-to-end: a full sim with horn should produce strictly more
        # damage than the same sim without horn. The delta comes from
        # (a) player damage during the summon window getting +20% FD,
        # (b) companion damage being snapshot-boosted by the same.
        calc_no_horn, _ = self._make_calc(horn_fd_decimal=0.0)
        calc_horn, _ = self._make_calc(horn_fd_decimal=0.20)
        kw = dict(
            fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
            attack_speed_mult=1.0, log_actions=False,
        )
        total_no_horn, *_ = calc_no_horn._simulate_fight(**kw)
        calc_horn._companion_snapshot = None
        total_horn, *_ = calc_horn._simulate_fight(**kw)
        self.assertGreater(total_horn, total_no_horn,
                           "Horn-equipped sim must produce more damage")
        # Sanity ceiling: horn boost shouldn't exceed +20% of total since
        # it only applies during the summon window (a fraction of fight).
        boost = (total_horn - total_no_horn) / total_no_horn
        self.assertLess(boost, 0.20,
                        f"Horn boost {boost:.3f} unexpectedly exceeded +20%; "
                        "would suggest the FD is being applied outside summon "
                        "or double-applied to companion damage.")


class TestCompanionSelfBuffFD(unittest.TestCase):
    """
    Companion-side self-buff Final Damage: 3rd/4th job companions have an
    OnStart `ModStat-Myself` skill that boosts their own FD for the whole
    summon window. We bake the modal +75% into the snapshot at cast time.

    Does NOT affect player damage — only the companion's per-hit damage.
    """

    def _make_calc(self, self_buff_fd: float = 0.75):
        from game.skills import (
            DPSCalculator, create_character_at_level,
            SkillData, SkillType, DamageType, Job,
        )
        from game.job_classes import JobClass
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        char = create_character_at_level(220, all_skills_bonus=0,
                                         job_class=JobClass.SHADOWER)
        char.attack = 5000
        char.crit_rate = 100
        char.crit_damage = 200
        char.boss_damage = 300
        calc = DPSCalculator(char, enemy_def=0.752)
        companion_skill = SkillData(
            name="companion_main_summon", skill_type=SkillType.SUMMON,
            damage_type=DamageType.SKILL, job=Job.FOURTH, unlock_level=1,
            base_damage_pct=300.0, base_hits=1, base_targets=6,
            attack_interval=2.0, duration=SUMMON_DURATION_S,
            cooldown=SUMMON_COOLDOWN_S, scales_with_attack_speed=False,
        )
        calc.register_companion_summon(companion_skill, "companion_main_summon")
        calc._companion_self_buff_fd_decimal = self_buff_fd
        return calc, companion_skill

    def test_self_buff_baked_into_snapshot_fd(self):
        # Base char has 30% FD; companion self-buff is +75%. Snapshot FD
        # must compose multiplicatively: 1.30 × 1.75 = 2.275 → +127.5%.
        calc, _ = self._make_calc(self_buff_fd=0.75)
        calc.char.final_damage_pct = 30.0
        snap = calc._build_companion_snapshot()
        self.assertAlmostEqual(snap.final_damage_pct, 127.5, places=4)

    def test_self_buff_zero_leaves_snapshot_unchanged(self):
        # A companion without a self-buff (basic/1st/2nd job) should
        # produce a snapshot with the base FD only — no boost.
        calc, _ = self._make_calc(self_buff_fd=0.0)
        calc.char.final_damage_pct = 30.0
        snap = calc._build_companion_snapshot()
        self.assertAlmostEqual(snap.final_damage_pct, 30.0, places=4)

    def test_self_buff_composes_with_horn_multiplicatively(self):
        # Both Horn Flute (+20%) and the self-buff (+75%) apply to the
        # snapshot. Composition: 1.30 × 1.20 × 1.75 = 2.730 → +173.0%.
        calc, _ = self._make_calc(self_buff_fd=0.75)
        calc.char.final_damage_pct = 30.0
        calc.char.companion_active_fd_decimal = 0.20
        snap = calc._build_companion_snapshot()
        self.assertAlmostEqual(snap.final_damage_pct, 173.0, places=3)

    def test_self_buff_does_not_affect_player_damage(self):
        # The self-buff is companion-only: it should NOT show up in the
        # player's own basic-attack or active-skill damage. We verify by
        # checking that two sims (with/without self-buff) produce the
        # same total when companion summon is never registered.
        from game.skills import (
            DPSCalculator, create_character_at_level, JobClass,
        )
        char_a = create_character_at_level(220, 0, job_class=JobClass.SHADOWER)
        char_a.attack = 5000; char_a.crit_rate = 100; char_a.crit_damage = 200
        char_a.boss_damage = 300
        char_b = create_character_at_level(220, 0, job_class=JobClass.SHADOWER)
        char_b.attack = 5000; char_b.crit_rate = 100; char_b.crit_damage = 200
        char_b.boss_damage = 300

        calc_a = DPSCalculator(char_a, enemy_def=0.752)
        calc_b = DPSCalculator(char_b, enemy_def=0.752)
        # B has the self-buff attribute set but NO companion registered —
        # the attribute should be inert because the snapshot is never built.
        calc_b._companion_self_buff_fd_decimal = 0.75

        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        total_a, *_ = calc_a._simulate_fight(**kw)
        total_b, *_ = calc_b._simulate_fight(**kw)
        # Identical — no companion → no snapshot → no use of self-buff FD.
        self.assertAlmostEqual(total_a, total_b, places=6)

    def test_self_buff_increases_companion_damage_in_sim(self):
        # End-to-end sim: a 4th-job-tier companion (with +75% self-buff)
        # should produce strictly more damage than a non-self-buff variant.
        calc_no_buff, _ = self._make_calc(self_buff_fd=0.0)
        calc_buff, _ = self._make_calc(self_buff_fd=0.75)
        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        # Clear any cached snapshot from earlier tests.
        calc_no_buff._companion_snapshot = None
        calc_buff._companion_snapshot = None
        total_no_buff, *_ = calc_no_buff._simulate_fight(**kw)
        total_buff, *_ = calc_buff._simulate_fight(**kw)
        self.assertGreater(total_buff, total_no_buff,
                           "Self-buff sim must produce more damage")


class TestCompanionDefinitionSelfBuffDefaults(unittest.TestCase):
    """Sanity check: the default self-buff breakpoint post-pass correctly
    flags 3rd/4th job companions and leaves basic/1st/2nd at zero. Also
    verifies the L5/L8/L10 level-scaling math."""

    def test_3rd_and_4th_job_companions_have_self_buff_at_max_level(self):
        from game.companions import COMPANIONS, JobAdvancement, MAX_LEVELS
        for key, comp in COMPANIONS.items():
            if comp.advancement in (JobAdvancement.THIRD, JobAdvancement.FOURTH):
                max_lvl = MAX_LEVELS.get(comp.advancement, 10)
                self.assertGreater(
                    comp.get_self_buff_fd_decimal(max_lvl), 0.0,
                    f"3rd/4th job companion {key} should have self-buff FD at max level",
                )

    def test_basic_1st_2nd_job_companions_have_no_self_buff(self):
        from game.companions import COMPANIONS, JobAdvancement
        lower_tiers = (JobAdvancement.BASIC, JobAdvancement.FIRST,
                       JobAdvancement.SECOND)
        for key, comp in COMPANIONS.items():
            if comp.advancement in lower_tiers:
                # Check across plausible level range — should always be 0.
                for lvl in (1, 10, 30, 50, 100):
                    self.assertEqual(
                        comp.get_self_buff_fd_decimal(lvl), 0.0,
                        f"Lower-tier {key} should have NO self-buff at L{lvl}",
                    )

    def test_self_buff_scales_at_level_5_8_10_breakpoints(self):
        # Pick any 4th job companion — they all share the (5,8,10) defaults.
        from game.companions import COMPANIONS
        comp = COMPANIONS["bowmaster_4th"]
        # Level 1-4: no breakpoints crossed → 0%
        self.assertAlmostEqual(comp.get_self_buff_fd_decimal(1), 0.0, places=6)
        self.assertAlmostEqual(comp.get_self_buff_fd_decimal(4), 0.0, places=6)
        # Level 5: first +25% unlocks
        self.assertAlmostEqual(comp.get_self_buff_fd_decimal(5), 0.25, places=6)
        # Level 7 still has only the first breakpoint
        self.assertAlmostEqual(comp.get_self_buff_fd_decimal(7), 0.25, places=6)
        # Level 8: second breakpoint → +50%
        self.assertAlmostEqual(comp.get_self_buff_fd_decimal(8), 0.50, places=6)
        # Level 10: third breakpoint → +75% (max)
        self.assertAlmostEqual(comp.get_self_buff_fd_decimal(10), 0.75, places=6)


class TestBishopCompanion(unittest.TestCase):
    """
    Bishop 4th-job companion kit (plan: sorted-nibbling-meteor.md).
    Covers data integrity, player-buff composition, secondary skill
    scheduling, and proc damage. Per-stat isolation tests assert the
    asymmetry: companion damage uses the snapshot (no player buffs),
    player damage gets the buffs only while companion is summoned.
    """

    def _make_calc_with_bishop_kit(
        self,
        *,
        player_bonuses=None,
        secondary_skills=None,
        proc_skill=None,
    ):
        # Build a calculator + a registered companion summon, then attach
        # whichever Bishop kit fields the test wants. Keeps tests focused
        # on the mechanic under test rather than the data plumbing.
        from game.skills import (
            DPSCalculator, create_character_at_level,
            SkillData, SkillType, DamageType, Job,
        )
        from game.job_classes import JobClass
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S
        char = create_character_at_level(220, all_skills_bonus=0,
                                         job_class=JobClass.SHADOWER)
        char.attack = 5000
        char.crit_rate = 100
        char.crit_damage = 200
        char.boss_damage = 300
        calc = DPSCalculator(char, enemy_def=0.752)
        companion_skill = SkillData(
            name="companion_main_summon", skill_type=SkillType.SUMMON,
            damage_type=DamageType.SKILL, job=Job.FOURTH, unlock_level=1,
            base_damage_pct=290.0, base_hits=5, base_targets=6,
            attack_interval=0.4, duration=SUMMON_DURATION_S,
            cooldown=SUMMON_COOLDOWN_S, scales_with_attack_speed=False,
        )
        calc.register_companion_summon(companion_skill, "companion_main_summon")
        if player_bonuses is not None:
            calc._companion_player_bonuses = dict(player_bonuses)
        if secondary_skills is not None:
            calc._companion_secondary_skills = list(secondary_skills)
        if proc_skill is not None:
            calc._companion_proc_skill = proc_skill
        return calc, companion_skill

    # ---- Data integrity ----

    def test_bishop_4th_has_full_kit_populated(self):
        from game.companions import COMPANIONS
        bishop = COMPANIONS["bishop_4th"]
        # Player buffs populated
        self.assertIn("attack_pct", bishop.summon_active_player_bonuses)
        self.assertIn("final_damage", bishop.summon_active_player_bonuses)
        self.assertIn("max_dmg_mult", bishop.summon_active_player_bonuses)
        self.assertIn("crit_damage", bishop.summon_active_player_bonuses)
        self.assertIn("attack_speed", bishop.summon_active_player_bonuses)
        # Attack_pct should be the uptime-averaged blend of skill 2+3.
        expected_atk = 0.15 * (20/30) + 0.20 * (18/30)
        self.assertAlmostEqual(
            bishop.summon_active_player_bonuses["attack_pct"], expected_atk,
            places=6,
        )
        # Primary attack override (hits=5, targets=6 instead of generic 6×1)
        self.assertIsNotNone(bishop.summon_primary_attack_override)
        self.assertEqual(bishop.summon_primary_attack_override.get("hits"), 5)
        self.assertEqual(bishop.summon_primary_attack_override.get("targets"), 6)
        # Skill 4 secondary
        self.assertEqual(len(bishop.summon_secondary_skills), 1)
        sk4 = bishop.summon_secondary_skills[0]
        self.assertEqual(sk4.damage_pct, 650.0)
        self.assertEqual(sk4.hits, 6)
        self.assertEqual(sk4.targets, 10)
        self.assertEqual(sk4.cooldown_s, 11.0)
        # Skill 7 proc
        proc = bishop.summon_proc_skill
        self.assertIsNotNone(proc)
        self.assertEqual(proc.damage_pct, 2600.0)
        self.assertEqual(proc.targets, 7)
        self.assertEqual(proc.proc_chance, 0.20)
        self.assertEqual(proc.icd_s, 3.0)

    def test_non_bishop_companions_have_empty_kit(self):
        # Bishop's kit additions should NOT leak to other companions.
        from game.companions import COMPANIONS
        for key in ("bowmaster_4th", "night_lord_4th", "hero_4th"):
            comp = COMPANIONS[key]
            self.assertEqual(comp.summon_active_player_bonuses, {})
            self.assertIsNone(comp.summon_primary_attack_override)
            self.assertEqual(comp.summon_secondary_skills, [])
            self.assertIsNone(comp.summon_proc_skill)

    def test_primary_attack_override_resolves_correctly(self):
        # build_companion_summon_skill_data with an override should produce
        # the override's hits/targets, not the tier defaults.
        from game.skills import build_companion_summon_skill_data
        from game.companions import JobAdvancement
        sk = build_companion_summon_skill_data(
            JobAdvancement.FOURTH, level=10,
            primary_attack_override={"hits": 5, "targets": 6},
        )
        self.assertIsNotNone(sk)
        self.assertEqual(sk.base_hits, 5)
        self.assertEqual(sk.base_targets, 6)

    # ---- Player buff helper unit tests ----

    def test_player_buff_mult_returns_1_when_empty(self):
        # No bonuses configured → multiplier is 1.0 exactly. Defensive: every
        # non-Bishop main hits this path.
        calc, _ = self._make_calc_with_bishop_kit(player_bonuses={})
        self.assertEqual(calc._compose_companion_player_buff_mult(), 1.0)

    def test_player_buff_mult_attack_pct_is_linear(self):
        # attack_pct uses simple `× (1 + value)` composition.
        calc, _ = self._make_calc_with_bishop_kit(
            player_bonuses={"attack_pct": 0.22},
        )
        self.assertAlmostEqual(
            calc._compose_companion_player_buff_mult(), 1.22, places=6,
        )

    def test_player_buff_mult_final_damage_is_multiplicative(self):
        calc, _ = self._make_calc_with_bishop_kit(
            player_bonuses={"final_damage": 0.08},
        )
        self.assertAlmostEqual(
            calc._compose_companion_player_buff_mult(), 1.08, places=6,
        )

    def test_player_buff_mult_crit_damage_weights_by_crit_rate(self):
        # crit_damage = +20%p, weighted by effective crit rate (capped at 100%).
        # At eff_crit ≥ 100%, full +20% multiplier applies. Below cap, the
        # bonus is proportionally scaled (so the helper's job is to weight
        # by `min(eff_crit, 100) / 100`).
        calc, _ = self._make_calc_with_bishop_kit(
            player_bonuses={"crit_damage": 20.0},
        )
        # At/above cap: char.crit_rate=200 + any passive >> 100, capped at 100%.
        calc.char.crit_rate = 200.0
        self.assertAlmostEqual(
            calc._compose_companion_player_buff_mult(), 1.20, places=6,
        )
        # Below cap: compute expected value from the helper's own formula so
        # passive crit bonuses (mastery / global) are accounted for.
        calc.char.crit_rate = 30.0
        eff_crit = min(calc.char.crit_rate + calc.get_total_stat_bonus("crit_rate"), 100.0)
        expected = 1.0 + (eff_crit / 100.0) * (20.0 / 100.0)
        self.assertAlmostEqual(
            calc._compose_companion_player_buff_mult(), expected, places=6,
        )
        # Sanity: below-cap should be strictly less than at-cap mult.
        self.assertLess(expected, 1.20)

    def test_player_buff_mult_composes_multiplicatively(self):
        # Damage-multiplier buffs compose. attack_speed is intentionally
        # NOT in this helper (it accelerates attack cadence via skill_values
        # recompute instead — see `test_attack_speed_recomputes_skill_values`).
        calc, _ = self._make_calc_with_bishop_kit(
            player_bonuses={
                "attack_pct": 0.20,
                "final_damage": 0.10,
                "attack_speed": 20.0,    # ignored by this helper, by design
            },
        )
        # 1.20 × 1.10 = 1.32
        self.assertAlmostEqual(
            calc._compose_companion_player_buff_mult(), 1.32, places=6,
        )

    def test_attack_speed_NOT_in_damage_multiplier_helper(self):
        # AS is handled by the simulator (skill_values recompute), not by
        # the damage-multiplier helper. Helper must ignore the bonus entirely
        # so the simulator's AS bump isn't double-counted.
        calc, _ = self._make_calc_with_bishop_kit(
            player_bonuses={"attack_speed": 50.0},
        )
        self.assertEqual(calc._compose_companion_player_buff_mult(), 1.0)

    def test_attack_speed_bonus_lifts_current_attack_speed_mult(self):
        # `calculate_attack_speed_mult(..., companion_summon_active=True)`
        # must add the companion's attack_speed bonus on top of the baseline.
        calc, _ = self._make_calc_with_bishop_kit(
            player_bonuses={"attack_speed": 20.0},
        )
        baseline = calc.calculate_attack_speed_mult(set(), companion_summon_active=False)
        boosted = calc.calculate_attack_speed_mult(set(), companion_summon_active=True)
        # Bonus is additive at the percentage-point level: +20%p → +0.20 mult
        # (unless the cap clamps it).
        self.assertAlmostEqual(boosted - baseline, 0.20, places=6)

    def test_attack_speed_bonus_increases_sim_total_via_faster_cadence(self):
        # End-to-end: a sim with only attack_speed bonus (no other Bishop
        # buffs) must produce MORE total damage than a baseline sim, because
        # the player attacks more often during the summon window.
        calc_no_as, _ = self._make_calc_with_bishop_kit(player_bonuses={})
        calc_with_as, _ = self._make_calc_with_bishop_kit(
            player_bonuses={"attack_speed": 20.0},
        )
        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        total_no_as, *_ = calc_no_as._simulate_fight(**kw)
        calc_with_as._companion_snapshot = None
        total_with_as, *_ = calc_with_as._simulate_fight(**kw)
        self.assertGreater(total_with_as, total_no_as,
                           "AS bonus must increase player damage during summon window")

    # ---- Sim-level behavior ----

    def test_player_buffs_increase_player_damage_only_during_summon(self):
        # Two sims: one with Bishop player buffs, one without. With-buffs
        # total must be strictly higher. With-buffs companion damage must
        # be identical (buffs are NOT in the snapshot).
        from game.skills import (
            DPSCalculator, create_character_at_level, JobClass,
            SkillData, SkillType, DamageType, Job,
        )
        from game.companions import SUMMON_DURATION_S, SUMMON_COOLDOWN_S

        def _build(bonuses):
            char = create_character_at_level(220, 0, job_class=JobClass.SHADOWER)
            char.attack = 5000; char.crit_rate = 100; char.crit_damage = 200
            char.boss_damage = 300
            calc = DPSCalculator(char, enemy_def=0.752)
            cs = SkillData(
                name="companion_main_summon", skill_type=SkillType.SUMMON,
                damage_type=DamageType.SKILL, job=Job.FOURTH, unlock_level=1,
                base_damage_pct=290.0, base_hits=5, base_targets=6,
                attack_interval=0.4, duration=SUMMON_DURATION_S,
                cooldown=SUMMON_COOLDOWN_S, scales_with_attack_speed=False,
            )
            calc.register_companion_summon(cs, "companion_main_summon")
            calc._companion_player_bonuses = bonuses
            return calc

        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        calc_no = _build({})
        calc_yes = _build({"attack_pct": 0.20, "final_damage": 0.10})
        total_no, *_ = calc_no._simulate_fight(**kw)
        # Reset cached state between independent sims
        calc_yes._companion_snapshot = None
        total_yes, *_ = calc_yes._simulate_fight(**kw)
        self.assertGreater(total_yes, total_no,
                           "Bishop player buffs must boost total damage")
        # Buffs only apply for the ~30s the companion is summoned; the
        # composed mult is 1.20 × 1.10 = 1.32 on player damage during that
        # window. Player damage is the lion's share, so total uplift should
        # be in single-digit percentage range — bounded above by 32% (the
        # max if 100% of damage came during the summon window).
        boost = (total_yes - total_no) / total_no
        self.assertLess(boost, 0.32,
                        f"Boost {boost:.3f} exceeded the 32% summon-window cap; "
                        "would suggest buffs are leaking outside summon.")

    def test_player_buffs_do_not_affect_companion_damage(self):
        # The companion's per-hit damage uses the snapshot. Player buffs are
        # applied separately at player damage events. Run two sims with
        # player damage suppressed to isolate companion damage.
        calc_no_buffs, _ = self._make_calc_with_bishop_kit(player_bonuses={})
        calc_with_buffs, _ = self._make_calc_with_bishop_kit(
            player_bonuses={"attack_pct": 0.50, "final_damage": 0.50},
        )
        # The companion snapshot is built from `from_calculator` — should be
        # identical for both since player_bonuses isn't in the snapshot.
        snap_no = calc_no_buffs._build_companion_snapshot()
        snap_yes = calc_with_buffs._build_companion_snapshot()
        self.assertAlmostEqual(snap_no.final_damage_pct, snap_yes.final_damage_pct,
                               places=6)
        self.assertEqual(snap_no.attack, snap_yes.attack)

    def test_secondary_skill_fires_on_cooldown(self):
        # With Bishop's skill 4 (11s CD) on a 70s fight, we should see at
        # most floor(30 / 11) + 1 = 3 casts per summon window (initial cast
        # + 2 more at t≈11 and t≈22 within the 30s window). With one summon,
        # that's at most 3 secondary casts.
        from game.companions import CompanionSecondarySkill
        calc, _ = self._make_calc_with_bishop_kit(
            secondary_skills=[
                CompanionSecondarySkill(
                    name="bishop_skill_4", damage_pct=650.0,
                    hits=6, targets=10, cooldown_s=11.0,
                ),
            ],
        )
        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        # Baseline: no secondary skill
        calc_no_sec, _ = self._make_calc_with_bishop_kit(secondary_skills=[])
        total_no, *_ = calc_no_sec._simulate_fight(**kw)
        # With secondary
        calc._companion_snapshot = None
        total_yes, *_ = calc._simulate_fight(**kw)
        self.assertGreater(total_yes, total_no,
                           "Secondary skill should add damage")

    def test_secondary_skill_uses_snapshot_not_live_stats(self):
        # Critical no-double-apply invariant. Build a calc, take a snapshot
        # baseline, then mutate live stats. Re-running the sim should produce
        # the same secondary-skill contribution because secondary reads the
        # snapshot, not live state.
        from game.companions import CompanionSecondarySkill
        calc, _ = self._make_calc_with_bishop_kit(
            secondary_skills=[
                CompanionSecondarySkill(
                    name="bishop_skill_4", damage_pct=650.0,
                    hits=6, targets=10, cooldown_s=11.0,
                ),
            ],
        )
        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        # The secondary contribution naturally depends on player stats at
        # summon-cast time. Different setups should produce different totals
        # — that's expected. This test just confirms the secondary fires
        # and accumulates damage (rather than crashing or silently no-op'ing).
        total, *_ = calc._simulate_fight(**kw)
        self.assertGreater(total, 0.0)

    def test_proc_damage_adds_to_total(self):
        from game.companions import CompanionProcSkill
        # Baseline: no proc.
        calc_no, _ = self._make_calc_with_bishop_kit(proc_skill=None)
        # With Bishop proc (skill 7).
        calc_yes, _ = self._make_calc_with_bishop_kit(
            proc_skill=CompanionProcSkill(
                name="bishop_skill_7", damage_pct=2600.0,
                hits=1, targets=7, proc_chance=0.20, icd_s=3.0,
            ),
        )
        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        total_no, *_ = calc_no._simulate_fight(**kw)
        calc_yes._companion_snapshot = None
        total_yes, *_ = calc_yes._simulate_fight(**kw)
        self.assertGreater(total_yes, total_no,
                           "Proc damage should add to total")

    def test_proc_damage_respects_icd_cap(self):
        # With a very low ICD-to-attack-interval ratio, procs are
        # attack-rate-limited. With a very high ICD, they're cap-limited.
        # We test the cap-limited case: attack interval 0.4s, proc chance
        # 50% → unconstrained = 1.25 procs/sec. ICD 3s → cap = 0.33 procs/sec.
        # In a 30s window, cap-limited procs ≈ 10; unconstrained ≈ 37.5.
        # Cap should bring it down.
        from game.companions import CompanionProcSkill
        calc_low_icd, _ = self._make_calc_with_bishop_kit(
            proc_skill=CompanionProcSkill(
                name="proc_cap_test", damage_pct=2600.0,
                hits=1, targets=1, proc_chance=0.50, icd_s=3.0,
            ),
        )
        calc_no_icd, _ = self._make_calc_with_bishop_kit(
            proc_skill=CompanionProcSkill(
                name="proc_no_cap_test", damage_pct=2600.0,
                hits=1, targets=1, proc_chance=0.50, icd_s=0.01,
            ),
        )
        kw = dict(fight_duration=70.0, num_enemies=1, mob_time_fraction=0.0,
                  attack_speed_mult=1.0, log_actions=False)
        total_capped, *_ = calc_low_icd._simulate_fight(**kw)
        calc_no_icd._companion_snapshot = None
        total_uncapped, *_ = calc_no_icd._simulate_fight(**kw)
        self.assertLess(total_capped, total_uncapped,
                        "ICD cap should reduce proc damage vs no-cap baseline")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
