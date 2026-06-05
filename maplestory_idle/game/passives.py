"""
MapleStory Idle - Passive Skills System
=======================================
Passive skill bonuses for each job class.

Passive skills provide permanent stat bonuses that scale with skill level.
Each job class has unique passive skills.

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class JobClass(Enum):
    """Job classes in the game."""
    BOWMASTER = "bowmaster"
    MARKSMAN = "marksman"
    PATHFINDER = "pathfinder"
    # Can add more job classes as needed


class PassiveStatType(Enum):
    """Stats that passive skills can provide."""
    DAMAGE = "damage"
    BOSS_DAMAGE = "boss_damage"
    NORMAL_DAMAGE = "normal_damage"
    DEF_PEN = "def_pen"
    CRIT_RATE = "crit_rate"
    CRIT_DAMAGE = "crit_damage"
    MAIN_STAT_PCT = "main_stat_pct"
    ATTACK_PCT = "attack_pct"
    FINAL_DAMAGE = "final_damage"
    MIN_CRIT = "min_crit"
    MAX_CRIT = "max_crit"
    ACCURACY = "accuracy"
    EVASION = "evasion"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PassiveSkill:
    """Definition of a passive skill."""
    name: str
    job_class: JobClass
    job_advancement: int  # 1, 2, 3, or 4
    max_level: int
    stat_type: PassiveStatType
    per_level: float  # Stat value per level
    description: str = ""

    def get_value(self, level: int) -> float:
        """Get stat value at given level."""
        clamped_level = max(0, min(level, self.max_level))
        return clamped_level * self.per_level


# =============================================================================
# BOWMASTER PASSIVES
# =============================================================================

BOWMASTER_PASSIVES = {
    # 1st Job Passives
    "archery_mastery": PassiveSkill(
        name="Archery Mastery",
        job_class=JobClass.BOWMASTER,
        job_advancement=1,
        max_level=20,
        stat_type=PassiveStatType.ACCURACY,
        per_level=5.0,
        description="Increases accuracy",
    ),
    "critical_shot": PassiveSkill(
        name="Critical Shot",
        job_class=JobClass.BOWMASTER,
        job_advancement=1,
        max_level=20,
        stat_type=PassiveStatType.CRIT_RATE,
        per_level=1.0,
        description="Increases critical rate",
    ),

    # 2nd Job Passives
    "bow_mastery": PassiveSkill(
        name="Bow Mastery",
        job_class=JobClass.BOWMASTER,
        job_advancement=2,
        max_level=20,
        stat_type=PassiveStatType.MIN_CRIT,
        per_level=0.5,
        description="Increases minimum critical damage",
    ),
    "thrust": PassiveSkill(
        name="Thrust",
        job_class=JobClass.BOWMASTER,
        job_advancement=2,
        max_level=20,
        stat_type=PassiveStatType.DAMAGE,
        per_level=1.0,
        description="Increases damage",
    ),
    "physical_training": PassiveSkill(
        name="Physical Training",
        job_class=JobClass.BOWMASTER,
        job_advancement=2,
        max_level=10,
        stat_type=PassiveStatType.MAIN_STAT_PCT,
        per_level=1.0,
        description="Increases main stat",
    ),

    # 3rd Job Passives
    "marksmanship": PassiveSkill(
        name="Marksmanship",
        job_class=JobClass.BOWMASTER,
        job_advancement=3,
        max_level=20,
        stat_type=PassiveStatType.CRIT_DAMAGE,
        per_level=1.5,
        description="Increases critical damage",
    ),
    "mortal_blow_passive": PassiveSkill(
        name="Mortal Blow",
        job_class=JobClass.BOWMASTER,
        job_advancement=3,
        max_level=20,
        stat_type=PassiveStatType.FINAL_DAMAGE,
        per_level=0.5,
        description="Increases final damage",
    ),
    "evasion_boost": PassiveSkill(
        name="Evasion Boost",
        job_class=JobClass.BOWMASTER,
        job_advancement=3,
        max_level=20,
        stat_type=PassiveStatType.EVASION,
        per_level=2.0,
        description="Increases evasion",
    ),

    # 4th Job Passives
    "bow_expert": PassiveSkill(
        name="Bow Expert",
        job_class=JobClass.BOWMASTER,
        job_advancement=4,
        max_level=30,
        stat_type=PassiveStatType.BOSS_DAMAGE,
        per_level=1.0,
        description="Increases boss damage",
    ),
    "advanced_final_attack": PassiveSkill(
        name="Advanced Final Attack",
        job_class=JobClass.BOWMASTER,
        job_advancement=4,
        max_level=30,
        stat_type=PassiveStatType.ATTACK_PCT,
        per_level=0.5,
        description="Increases attack%",
    ),
    "sharp_eyes_passive": PassiveSkill(
        name="Sharp Eyes Enhance",
        job_class=JobClass.BOWMASTER,
        job_advancement=4,
        max_level=30,
        stat_type=PassiveStatType.CRIT_DAMAGE,
        per_level=1.0,
        description="Enhances Sharp Eyes critical damage",
    ),
    "illusion_step": PassiveSkill(
        name="Illusion Step",
        job_class=JobClass.BOWMASTER,
        job_advancement=4,
        max_level=20,
        stat_type=PassiveStatType.DEF_PEN,
        per_level=0.5,
        description="Increases defense penetration",
    ),
}

# Combine all job passives
ALL_PASSIVES = {
    JobClass.BOWMASTER: BOWMASTER_PASSIVES,
    # Add more jobs here
}


# =============================================================================
# PASSIVE CONFIG
# =============================================================================

@dataclass
class PassiveConfig:
    """Player's passive skill configuration."""
    job_class: JobClass = JobClass.BOWMASTER
    skill_levels: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize all skills to 0 if not provided
        passives = ALL_PASSIVES.get(self.job_class, {})
        for skill_key in passives:
            if skill_key not in self.skill_levels:
                self.skill_levels[skill_key] = 0

    def get_skill_level(self, skill_key: str) -> int:
        """Get current level of a skill."""
        return self.skill_levels.get(skill_key, 0)

    def set_skill_level(self, skill_key: str, level: int) -> None:
        """Set skill level, clamped to valid range."""
        passives = ALL_PASSIVES.get(self.job_class, {})
        if skill_key in passives:
            max_level = passives[skill_key].max_level
            self.skill_levels[skill_key] = max(0, min(level, max_level))

    def get_all_stats(self) -> Dict[str, float]:
        """
        Get all passive stats for damage calculation.
        Returns dict with stat keys matching damage calc expectations.
        """
        stats = {}
        passives = ALL_PASSIVES.get(self.job_class, {})

        for skill_key, skill in passives.items():
            level = self.get_skill_level(skill_key)
            if level > 0:
                stat_key = skill.stat_type.value
                value = skill.get_value(level)
                stats[stat_key] = stats.get(stat_key, 0) + value

        return stats

    def get_stats_by_job_advancement(self, advancement: int) -> Dict[str, float]:
        """Get stats from passives of a specific job advancement."""
        stats = {}
        passives = ALL_PASSIVES.get(self.job_class, {})

        for skill_key, skill in passives.items():
            if skill.job_advancement == advancement:
                level = self.get_skill_level(skill_key)
                if level > 0:
                    stat_key = skill.stat_type.value
                    value = skill.get_value(level)
                    stats[stat_key] = stats.get(stat_key, 0) + value

        return stats

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "job_class": self.job_class.value,
            "skill_levels": self.skill_levels.copy(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PassiveConfig":
        """Deserialize from dict."""
        job_class = JobClass(data.get("job_class", "bowmaster"))
        config = cls(job_class=job_class)
        config.skill_levels = data.get("skill_levels", {}).copy()
        return config


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_max_passive_stats(job_class: JobClass) -> Dict[str, float]:
    """Get stats if all passives are maxed."""
    config = PassiveConfig(job_class=job_class)
    passives = ALL_PASSIVES.get(job_class, {})

    for skill_key, skill in passives.items():
        config.set_skill_level(skill_key, skill.max_level)

    return config.get_all_stats()


def get_passive_skills_for_job(job_class: JobClass) -> List[PassiveSkill]:
    """Get list of all passive skills for a job class."""
    passives = ALL_PASSIVES.get(job_class, {})
    return list(passives.values())


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Passive Skills Module")
    print("=" * 60)

    # Test default config
    config = PassiveConfig(job_class=JobClass.BOWMASTER)
    print("\nDefault Bowmaster Config (all skills at 0):")
    print(f"  Stats: {config.get_all_stats()}")

    # Test with skills leveled
    config.set_skill_level("critical_shot", 20)
    config.set_skill_level("bow_mastery", 20)
    config.set_skill_level("marksmanship", 20)
    config.set_skill_level("bow_expert", 30)
    config.set_skill_level("mortal_blow_passive", 20)
    config.set_skill_level("illusion_step", 20)

    print("\nWith leveled skills:")
    stats = config.get_all_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test max stats
    print("\nMax Bowmaster Passive Stats:")
    max_stats = get_max_passive_stats(JobClass.BOWMASTER)
    for key, value in max_stats.items():
        print(f"  {key}: {value}")

    # List all passives by advancement
    print("\nBowmaster Passives by Job Advancement:")
    for adv in [1, 2, 3, 4]:
        print(f"\n  {adv}th Job:")
        for skill_key, skill in BOWMASTER_PASSIVES.items():
            if skill.job_advancement == adv:
                print(f"    - {skill.name}: {skill.stat_type.value} +{skill.per_level}/level (max {skill.max_level})")
