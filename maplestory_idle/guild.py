"""
MapleStory Idle - Guild System
==============================
Guild skill bonuses and stats contribution.

Guild skills provide various bonuses including:
- Final Damage % (multiplicative with other FD sources)
- Damage %
- Main Stat %
- Critical Damage %
- Boss Damage %
- Defense Penetration %

Last Updated: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum

# Import standardized stat names
from stat_names import (
    FINAL_DAMAGE, DAMAGE_PCT, MAIN_STAT_PCT, CRIT_DAMAGE,
    BOSS_DAMAGE, DEF_PEN, ATTACK_FLAT, MAX_HP
)


# =============================================================================
# ENUMS
# =============================================================================

class GuildSkillType(Enum):
    """Guild skill types."""
    FINAL_DAMAGE = "final_damage"
    DAMAGE = "damage"
    MAIN_STAT = "main_stat"
    CRIT_DAMAGE = "crit_damage"
    BOSS_DAMAGE = "boss_damage"
    DEF_PEN = "def_pen"
    ATTACK = "attack"
    MAX_HP = "max_hp"


# =============================================================================
# CONSTANTS
# =============================================================================

# Guild skill max levels and values per level
# Based on typical guild skill progression
GUILD_SKILL_DATA = {
    GuildSkillType.FINAL_DAMAGE: {
        "name": "Guild Final Damage",
        "max_level": 10,
        "per_level": 1.0,  # 1% per level
        "description": "Final Damage +1% per level",
    },
    GuildSkillType.DAMAGE: {
        "name": "Guild Damage",
        "max_level": 10,
        "per_level": 2.0,  # 2% per level
        "description": "Damage +2% per level",
    },
    GuildSkillType.MAIN_STAT: {
        "name": "Guild Main Stat",
        "max_level": 10,
        "per_level": 1.0,  # 1% per level
        "description": "Main Stat +1% per level",
    },
    GuildSkillType.CRIT_DAMAGE: {
        "name": "Guild Crit Damage",
        "max_level": 10,
        "per_level": 1.5,  # 1.5% per level
        "description": "Critical Damage +1.5% per level",
    },
    GuildSkillType.BOSS_DAMAGE: {
        "name": "Guild Boss Damage",
        "max_level": 10,
        "per_level": 2.0,  # 2% per level
        "description": "Boss Damage +2% per level",
    },
    GuildSkillType.DEF_PEN: {
        "name": "Guild Defense Penetration",
        "max_level": 10,
        "per_level": 0.5,  # 0.5% per level
        "description": "Defense Penetration +0.5% per level",
    },
    GuildSkillType.ATTACK: {
        "name": "Guild Attack",
        "max_level": 10,
        "per_level": 100,  # 100 flat attack per level
        "description": "Attack +100 per level",
    },
    GuildSkillType.MAX_HP: {
        "name": "Guild Max HP",
        "max_level": 10,
        "per_level": 500,  # 500 HP per level
        "description": "Max HP +500 per level",
    },
}

# Display names for UI
SKILL_DISPLAY_NAMES = {
    GuildSkillType.FINAL_DAMAGE: "Final Damage %",
    GuildSkillType.DAMAGE: "Damage %",
    GuildSkillType.MAIN_STAT: "Main Stat %",
    GuildSkillType.CRIT_DAMAGE: "Crit Damage %",
    GuildSkillType.BOSS_DAMAGE: "Boss Damage %",
    GuildSkillType.DEF_PEN: "Defense Pen %",
    GuildSkillType.ATTACK: "Attack",
    GuildSkillType.MAX_HP: "Max HP",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class GuildConfig:
    """
    Player's guild skill configuration.
    Each skill can be leveled from 0 to max_level.
    """
    skill_levels: Dict[GuildSkillType, int] = field(default_factory=dict)
    guild_name: str = "Default Guild"

    def __post_init__(self):
        # Initialize all skills to 0 if not provided
        for skill in GuildSkillType:
            if skill not in self.skill_levels:
                self.skill_levels[skill] = 0

    def get_skill_level(self, skill: GuildSkillType) -> int:
        """Get current level of a skill."""
        return self.skill_levels.get(skill, 0)

    def set_skill_level(self, skill: GuildSkillType, level: int) -> None:
        """Set skill level, clamped to valid range."""
        max_level = GUILD_SKILL_DATA[skill]["max_level"]
        self.skill_levels[skill] = max(0, min(level, max_level))

    def get_skill_value(self, skill: GuildSkillType) -> float:
        """Get the total bonus value for a skill at current level."""
        level = self.get_skill_level(skill)
        per_level = GUILD_SKILL_DATA[skill]["per_level"]
        return level * per_level

    def get_all_stats(self) -> Dict[str, float]:
        """
        Get all guild stats for damage calculation.
        Returns dict with stat keys from stat_names.py.
        """
        return {
            FINAL_DAMAGE: self.get_skill_value(GuildSkillType.FINAL_DAMAGE),
            DAMAGE_PCT: self.get_skill_value(GuildSkillType.DAMAGE),
            MAIN_STAT_PCT: self.get_skill_value(GuildSkillType.MAIN_STAT),
            CRIT_DAMAGE: self.get_skill_value(GuildSkillType.CRIT_DAMAGE),
            BOSS_DAMAGE: self.get_skill_value(GuildSkillType.BOSS_DAMAGE),
            DEF_PEN: self.get_skill_value(GuildSkillType.DEF_PEN),
            ATTACK_FLAT: self.get_skill_value(GuildSkillType.ATTACK),
            MAX_HP: self.get_skill_value(GuildSkillType.MAX_HP),
        }

    def get_stats(self, job_class=None):
        """
        Get all guild stats as a StatBlock.

        Note: Defense Pen is NOT included here because it stacks multiplicatively
        and needs special handling. Use get_skill_value(GuildSkillType.DEF_PEN).

        Args:
            job_class: Job class for main_stat mapping (defaults to Bowmaster)

        Returns:
            StatBlock with all guild stats (except def_pen)
        """
        from stats import create_stat_block_for_job
        from job_classes import JobClass

        if job_class is None:
            job_class = JobClass.BOWMASTER

        all_stats = self.get_all_stats()

        return create_stat_block_for_job(
            job_class=job_class,
            main_stat_pct=all_stats.get(MAIN_STAT_PCT, 0),
            attack_flat=all_stats.get(ATTACK_FLAT, 0),
            damage_pct=all_stats.get(DAMAGE_PCT, 0),
            boss_damage=all_stats.get(BOSS_DAMAGE, 0),
            crit_damage=all_stats.get(CRIT_DAMAGE, 0),
            final_damage=all_stats.get(FINAL_DAMAGE, 0),
            max_hp=all_stats.get(MAX_HP, 0),
            # Note: def_pen excluded - needs multiplicative handling
        )

    def to_dict(self) -> Dict:
        """Serialize to dict for saving."""
        return {
            "guild_name": self.guild_name,
            "skill_levels": {
                skill.value: level
                for skill, level in self.skill_levels.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GuildConfig":
        """Deserialize from dict."""
        config = cls(guild_name=data.get("guild_name", "Default Guild"))
        skill_data = data.get("skill_levels", {})
        for skill in GuildSkillType:
            level = skill_data.get(skill.value, 0)
            config.skill_levels[skill] = level
        return config


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_max_guild_stats() -> Dict[str, float]:
    """Get stats if all guild skills are maxed."""
    config = GuildConfig()
    for skill in GuildSkillType:
        max_level = GUILD_SKILL_DATA[skill]["max_level"]
        config.set_skill_level(skill, max_level)
    return config.get_all_stats()


def calculate_guild_contribution(config: GuildConfig, stat_type: str) -> str:
    """Format guild contribution for a specific stat for display."""
    stats = config.get_all_stats()
    value = stats.get(stat_type, 0)
    if stat_type in ("attack_flat", "max_hp"):
        return f"+{value:.0f}"
    return f"+{value:.1f}%"


# =============================================================================
# MAIN (Testing)
# =============================================================================

if __name__ == "__main__":
    print("MapleStory Idle - Guild System Module")
    print("=" * 60)

    # Test default config
    config = GuildConfig()
    print("\nDefault Guild Config (all skills at 0):")
    print(f"  Stats: {config.get_all_stats()}")

    # Test with some skills leveled
    config.set_skill_level(GuildSkillType.FINAL_DAMAGE, 10)
    config.set_skill_level(GuildSkillType.DAMAGE, 10)
    config.set_skill_level(GuildSkillType.BOSS_DAMAGE, 5)
    print("\nWith FD 10, Damage 10, Boss 5:")
    stats = config.get_all_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Test max stats
    print("\nMax Guild Stats (all skills at 10):")
    max_stats = get_max_guild_stats()
    for key, value in max_stats.items():
        print(f"  {key}: {value}")

    # Test serialization
    print("\nSerialization Test:")
    data = config.to_dict()
    print(f"  Serialized: {data}")
    restored = GuildConfig.from_dict(data)
    print(f"  Restored stats: {restored.get_all_stats()}")
