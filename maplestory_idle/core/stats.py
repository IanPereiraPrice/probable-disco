"""
MapleStory Idle - Stat Aggregation
==================================
Functions for aggregating stats from various sources (equipment, hero power, etc.)

This module handles collecting stats from user data and combining them properly.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .constants import EQUIPMENT_SLOTS
from .damage import calculate_defense_pen, calculate_attack_speed


@dataclass
class CharacterStats:
    """Container for all character stats needed for damage calculation."""

    # DEX
    dex_flat: float = 0
    dex_percent: float = 0
    str_flat: float = 0

    # Attack
    base_attack: float = 0

    # Damage multipliers
    damage_percent: float = 0
    damage_amp: float = 0
    boss_damage: float = 0
    normal_damage: float = 0

    # Final Damage sources (list for multiplicative stacking)
    final_damage_sources: List[float] = field(default_factory=list)

    # Critical
    crit_rate: float = 0
    crit_damage: float = 0

    # Defense Penetration sources (list for multiplicative stacking)
    defense_pen_sources: List[float] = field(default_factory=list)

    # Attack Speed sources (list of tuples for diminishing returns)
    attack_speed_sources: List[tuple] = field(default_factory=list)

    # Min/Max damage
    min_dmg_mult: float = 0
    max_dmg_mult: float = 0

    def get_total_defense_pen(self) -> float:
        """Calculate total defense penetration from all sources."""
        return calculate_defense_pen(self.defense_pen_sources)

    def get_total_attack_speed(self) -> float:
        """Calculate total attack speed from all sources."""
        return calculate_attack_speed(self.attack_speed_sources)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for compatibility with existing code."""
        return {
            'flat_dex': self.dex_flat,
            'dex_percent': self.dex_percent,
            'str_flat': self.str_flat,
            'base_attack': self.base_attack,
            'damage_percent': self.damage_percent,
            'damage_amp': self.damage_amp,
            'boss_damage': self.boss_damage,
            'normal_damage': self.normal_damage,
            'final_damage_sources': self.final_damage_sources,
            'crit_rate': self.crit_rate,
            'crit_damage': self.crit_damage,
            'defense_pen': self.get_total_defense_pen(),
            'defense_pen_sources': self.defense_pen_sources,
            'attack_speed': self.get_total_attack_speed(),
            'attack_speed_sources': self.attack_speed_sources,
            'min_dmg_mult': self.min_dmg_mult,
            'max_dmg_mult': self.max_dmg_mult,
        }


def aggregate_stats(user_data: Any) -> CharacterStats:
    """
    Aggregate stats from all sources in user data.

    This function collects stats from:
    - Equipment potentials
    - Hero Power
    - Companions
    - Maple Rank
    - Artifacts
    - Skills/Passives
    - Guild

    Args:
        user_data: The user data object containing all configuration

    Returns:
        CharacterStats with all stats aggregated properly
    """
    stats = CharacterStats()

    # Aggregate from each source
    _add_equipment_potential_stats(stats, user_data)
    _add_hero_power_stats(stats, user_data)
    _add_maple_rank_stats(stats, user_data)
    _add_companion_stats(stats, user_data)
    _add_artifact_stats(stats, user_data)
    _add_guild_stats(stats, user_data)
    _add_equipment_base_stats(stats, user_data)

    return stats


def _add_equipment_potential_stats(stats: CharacterStats, user_data: Any) -> None:
    """Add stats from equipment potentials."""
    pots = getattr(user_data, 'equipment_potentials', {})

    for slot in EQUIPMENT_SLOTS:
        slot_pots = pots.get(slot, {})

        # Regular and bonus potential lines
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat_type = slot_pots.get(f'{prefix}line{i}_stat', '')
                value = float(slot_pots.get(f'{prefix}line{i}_value', 0))

                if stat_type and value > 0:
                    _add_stat_by_type(stats, stat_type, value, f'{slot}_{prefix}pot')


def _add_hero_power_stats(stats: CharacterStats, user_data: Any) -> None:
    """Add stats from hero power lines."""
    lines = getattr(user_data, 'hero_power_lines', {})

    for line_key, line_data in lines.items():
        stat_type = line_data.get('stat', '')
        value = float(line_data.get('value', 0))

        if stat_type and value > 0:
            _add_stat_by_type(stats, stat_type, value, f'hero_power_{line_key}')


def _add_maple_rank_stats(stats: CharacterStats, user_data: Any) -> None:
    """Add stats from maple rank."""
    mr = getattr(user_data, 'maple_rank', {})
    stat_levels = mr.get('stat_levels', {})

    if isinstance(stat_levels, dict):
        # Each level gives a certain amount per level
        stats.attack_speed_sources.append(('Maple Rank', stat_levels.get('attack_speed', 0) * 0.5))
        stats.crit_rate += stat_levels.get('crit_rate', 0) * 1
        stats.damage_percent += stat_levels.get('damage', 0) * 2
        stats.boss_damage += stat_levels.get('boss_damage', 0) * 2
        stats.normal_damage += stat_levels.get('normal_damage', 0) * 2
        stats.crit_damage += stat_levels.get('crit_damage', 0) * 2


def _add_companion_stats(stats: CharacterStats, user_data: Any) -> None:
    """Add stats from companions."""
    companions = getattr(user_data, 'companions', {})

    # On-equip stats from equipped companions
    for comp_data in companions.values():
        if comp_data.get('equipped', False):
            stat_type = comp_data.get('on_equip_type', '')
            value = float(comp_data.get('on_equip_value', 0))

            if stat_type and value > 0:
                if stat_type == 'attack_speed':
                    stats.attack_speed_sources.append(('Companion', value))
                else:
                    _add_stat_by_type(stats, stat_type, value, 'companion')


def _add_artifact_stats(stats: CharacterStats, user_data: Any) -> None:
    """Add stats from artifacts."""
    artifacts = getattr(user_data, 'artifacts', {})

    for artifact_data in artifacts.values():
        if artifact_data.get('equipped', False):
            # Artifact potentials
            for i in range(1, 4):
                stat_type = artifact_data.get(f'pot{i}_stat', '')
                value = float(artifact_data.get(f'pot{i}_value', 0))

                if stat_type and value > 0:
                    _add_stat_by_type(stats, stat_type, value, 'artifact')


def _add_guild_stats(stats: CharacterStats, user_data: Any) -> None:
    """Add stats from guild."""
    guild = getattr(user_data, 'guild', {})

    # Guild final damage
    fd = float(guild.get('final_damage', 0))
    if fd > 0:
        stats.final_damage_sources.append(fd / 100)

    # Other guild stats
    stats.damage_percent += float(guild.get('damage', 0))
    stats.crit_rate += float(guild.get('crit_rate', 0))


def _add_equipment_base_stats(stats: CharacterStats, user_data: Any) -> None:
    """Add base stats from equipment (attack, DEX, etc.)."""
    equipment = getattr(user_data, 'equipment', {})

    for slot, item_data in equipment.items():
        stats.base_attack += float(item_data.get('attack', 0))
        stats.dex_flat += float(item_data.get('dex', 0))
        stats.str_flat += float(item_data.get('str', 0))


def _add_stat_by_type(stats: CharacterStats, stat_type: str, value: float, source: str) -> None:
    """
    Add a stat value to the appropriate field based on stat type.

    Args:
        stats: The CharacterStats to modify
        stat_type: The type of stat (e.g., 'damage', 'crit_rate', 'def_pen')
        value: The value to add
        source: The source name (for attack speed tracking)
    """
    # Normalize stat type names
    stat_type = stat_type.lower().replace(' ', '_')

    # Map stat types to CharacterStats fields
    if stat_type in ('damage', 'damage_percent', 'dmg', 'dmg%'):
        stats.damage_percent += value
    elif stat_type in ('boss', 'boss_damage', 'boss_dmg', 'boss%'):
        stats.boss_damage += value
    elif stat_type in ('normal', 'normal_damage', 'normal_dmg'):
        stats.normal_damage += value
    elif stat_type in ('crit_rate', 'cr', 'crit%'):
        stats.crit_rate += value
    elif stat_type in ('crit_damage', 'cd', 'crit_dmg'):
        stats.crit_damage += value
    elif stat_type in ('def_pen', 'defense_pen', 'ied', 'ignore_defense'):
        stats.defense_pen_sources.append(value / 100)  # Convert to decimal
    elif stat_type in ('final_damage', 'fd', 'final_dmg', 'final_atk_dmg'):
        stats.final_damage_sources.append(value / 100)  # Convert to decimal
    elif stat_type in ('attack_speed', 'atk_spd', 'as'):
        stats.attack_speed_sources.append((source, value))
    elif stat_type in ('dex', 'dex%', 'dex_percent'):
        stats.dex_percent += value
    elif stat_type in ('flat_dex', 'dex_flat'):
        stats.dex_flat += value
    elif stat_type in ('min_dmg', 'min_damage', 'min_dmg_mult'):
        stats.min_dmg_mult += value
    elif stat_type in ('max_dmg', 'max_damage', 'max_dmg_mult'):
        stats.max_dmg_mult += value
    elif stat_type in ('damage_amp', 'dmg_amp'):
        stats.damage_amp += value
    # Add more mappings as needed
