"""
StatAggregator - Unified stat calculation with source tracking.

This class replaces the separate aggregate_stats() and get_stat_sources() functions
to ensure both the calculated totals and the source breakdowns are always in sync.

Usage:
    agg = StatAggregator(job_class=JobClass.BOWMASTER)
    agg.add('dex_flat', 1000, 'Ring (Base)')
    agg.add('dex_flat', 500, 'Necklace (Base)')

    total = agg.get('dex_flat')  # Returns 1500
    sources = agg.get_sources('dex_flat')  # Returns [('Ring (Base)', 1000), ('Necklace (Base)', 500)]
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum


class StatType(Enum):
    """How a stat stacks."""
    ADDITIVE = "additive"           # Simple addition (most stats)
    MULTIPLICATIVE = "multiplicative"  # (1+a) * (1+b) * ... (final damage)
    DEFENSE_PEN = "defense_pen"     # 1 - (1-a)*(1-b)*... (defense penetration)
    DIMINISHING = "diminishing"     # Special diminishing returns (attack speed)


@dataclass
class TrackedStat:
    """A stat value with its contributing sources tracked."""
    stat_key: str
    stat_type: StatType = StatType.ADDITIVE
    baseline: float = 0.0  # Base value before any sources (e.g., 5% base crit rate)

    # Sources as (source_name, raw_value) tuples
    _sources: List[Tuple[str, float]] = field(default_factory=list)

    def add(self, value: float, source: str):
        """Add a value from a source."""
        if value != 0:  # Don't track zero contributions
            self._sources.append((source, value))

    @property
    def sources(self) -> List[Tuple[str, float]]:
        """Get list of (source_name, value) tuples."""
        return self._sources.copy()

    @property
    def raw_total(self) -> float:
        """Sum of all source values (before baseline)."""
        return sum(v for _, v in self._sources)

    @property
    def value(self) -> float:
        """Calculate the final stat value based on stat type."""
        if self.stat_type == StatType.ADDITIVE:
            return self.baseline + self.raw_total

        elif self.stat_type == StatType.MULTIPLICATIVE:
            # Final Damage: (1+a) * (1+b) * ... - 1
            mult = 1.0
            for _, v in self._sources:
                mult *= (1 + v / 100)
            return (mult - 1) * 100

        elif self.stat_type == StatType.DEFENSE_PEN:
            # Defense Pen: 1 - (1-a)*(1-b)*...
            remaining = 1.0
            for _, v in self._sources:
                remaining *= (1 - v / 100)
            return (1 - remaining) * 100

        elif self.stat_type == StatType.DIMINISHING:
            # Attack Speed: uses breakpoint-based diminishing returns
            # For now, just return raw total - actual calculation done elsewhere
            return self.raw_total

        return self.baseline + self.raw_total


# Stat configuration - defines baseline values and stacking types
STAT_CONFIG = {
    # Main stats (dynamic key based on job class)
    'main_flat': {'type': StatType.ADDITIVE, 'baseline': 0},
    'main_pct': {'type': StatType.ADDITIVE, 'baseline': 0},

    # Attack stats
    'attack_flat': {'type': StatType.ADDITIVE, 'baseline': 0},
    'attack_pct': {'type': StatType.ADDITIVE, 'baseline': 0},

    # Damage stats
    'damage_pct': {'type': StatType.ADDITIVE, 'baseline': 0},
    'boss_damage': {'type': StatType.ADDITIVE, 'baseline': 0},
    'normal_damage': {'type': StatType.ADDITIVE, 'baseline': 0},
    'damage_amp': {'type': StatType.ADDITIVE, 'baseline': 0},
    'basic_attack_damage': {'type': StatType.ADDITIVE, 'baseline': 0},
    'skill_damage': {'type': StatType.ADDITIVE, 'baseline': 0},

    # Crit stats (have baseline values)
    'crit_rate': {'type': StatType.ADDITIVE, 'baseline': 0.0},
    'crit_damage': {'type': StatType.ADDITIVE, 'baseline': 30.0},

    # Damage range stats (have baseline values)
    'min_dmg_mult': {'type': StatType.ADDITIVE, 'baseline': 50.0},
    'max_dmg_mult': {'type': StatType.ADDITIVE, 'baseline': 100.0},

    # Multiplicative stats
    'def_pen': {'type': StatType.DEFENSE_PEN, 'baseline': 0},
    'final_damage': {'type': StatType.MULTIPLICATIVE, 'baseline': 0},
    'attack_speed': {'type': StatType.DIMINISHING, 'baseline': 0},

    # Skill stats
    'skill_1st': {'type': StatType.ADDITIVE, 'baseline': 0},
    'skill_2nd': {'type': StatType.ADDITIVE, 'baseline': 0},
    'skill_3rd': {'type': StatType.ADDITIVE, 'baseline': 0},
    'skill_4th': {'type': StatType.ADDITIVE, 'baseline': 0},
    'all_skills': {'type': StatType.ADDITIVE, 'baseline': 0},
    'skill_cd': {'type': StatType.ADDITIVE, 'baseline': 0},
    'buff_duration': {'type': StatType.ADDITIVE, 'baseline': 0},

    # Utility
    'accuracy': {'type': StatType.ADDITIVE, 'baseline': 0},
    'ba_targets': {'type': StatType.ADDITIVE, 'baseline': 0},
}


class StatAggregator:
    """
    Unified stat aggregator that tracks both values and sources.

    This replaces the separate aggregate_stats() and get_stat_sources() functions,
    ensuring they always return consistent values.
    """

    def __init__(self, job_class=None, main_stat_name: str = 'dex'):
        """
        Initialize the stat aggregator.

        Args:
            job_class: JobClass enum for determining main stat
            main_stat_name: Name of main stat ('dex', 'str', 'int', 'luk')
        """
        from job_classes import JobClass, get_main_stat_name

        if job_class is None:
            job_class = JobClass.BOWMASTER

        self.job_class = job_class
        self.main_stat_name = get_main_stat_name(job_class)
        self.main_flat_key = f'{self.main_stat_name}_flat'
        self.main_pct_key = f'{self.main_stat_name}_pct'

        # Initialize all tracked stats
        self._stats: Dict[str, TrackedStat] = {}
        self._init_stats()

        # Character info (non-stat data)
        self.character_level: int = 1
        self.all_skills_bonus: int = 0

        # Special tracking for hex necklace
        self.hex_necklace_stars: int = 0
        self.hex_multiplier: float = 1.0

    def _init_stats(self):
        """Initialize TrackedStat objects for all stat keys."""
        for stat_key, config in STAT_CONFIG.items():
            # Handle dynamic main stat keys
            if stat_key == 'main_flat':
                actual_key = self.main_flat_key
            elif stat_key == 'main_pct':
                actual_key = self.main_pct_key
            else:
                actual_key = stat_key

            self._stats[actual_key] = TrackedStat(
                stat_key=actual_key,
                stat_type=config['type'],
                baseline=config['baseline'],
            )

    def _get_stat(self, stat_key: str) -> TrackedStat:
        """Get or create a TrackedStat for a key."""
        # Handle aliases
        stat_aliases = {
            'damage': 'damage_pct',
            'main_stat_flat': self.main_flat_key,
            'main_stat_pct': self.main_pct_key,
            f'{self.main_stat_name}': self.main_flat_key,  # e.g., 'dex' -> 'dex_flat'
        }
        resolved_key = stat_aliases.get(stat_key, stat_key)

        if resolved_key not in self._stats:
            # Create new stat with default additive type
            self._stats[resolved_key] = TrackedStat(
                stat_key=resolved_key,
                stat_type=StatType.ADDITIVE,
                baseline=0,
            )

        return self._stats[resolved_key]

    def add(self, stat_key: str, value: float, source: str):
        """
        Add a stat value from a source.

        Args:
            stat_key: The stat key (e.g., 'dex_flat', 'damage_pct')
            value: The value to add
            source: Description of where this value comes from
        """
        if value == 0:
            return

        stat = self._get_stat(stat_key)
        stat.add(value, source)

    def get(self, stat_key: str, include_baseline: bool = True) -> float:
        """
        Get the total value for a stat.

        Args:
            stat_key: The stat key
            include_baseline: Whether to include baseline value (default True)

        Returns:
            The calculated stat value
        """
        stat = self._get_stat(stat_key)
        if include_baseline:
            return stat.value
        else:
            return stat.raw_total

    def get_sources(self, stat_key: str) -> List[Tuple[str, float]]:
        """
        Get the list of sources for a stat.

        Args:
            stat_key: The stat key

        Returns:
            List of (source_name, value) tuples
        """
        stat = self._get_stat(stat_key)
        return stat.sources

    def get_baseline(self, stat_key: str) -> float:
        """Get the baseline value for a stat."""
        stat = self._get_stat(stat_key)
        return stat.baseline

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a dictionary format compatible with existing code.

        Returns:
            Dict with stat values (without source tracking)
        """
        result = {
            'main_stat_type': self.main_stat_name,
            'character_level': self.character_level,
            'hex_necklace_stars': self.hex_necklace_stars,
            'hex_multiplier': self.hex_multiplier,
        }

        for stat_key, stat in self._stats.items():
            # For additive stats, return raw_total (without baseline)
            # Baselines are added by consumers (for backward compatibility)
            if stat.stat_type == StatType.ADDITIVE:
                result[stat_key] = stat.raw_total
            else:
                # For multiplicative stats, store sources list for later calculation
                if stat.stat_type == StatType.DEFENSE_PEN:
                    result['def_pen_sources'] = [
                        (name, value, 0) for name, value in stat.sources
                    ]
                elif stat.stat_type == StatType.MULTIPLICATIVE:
                    result['final_damage_sources'] = [
                        value / 100 for _, value in stat.sources
                    ]
                elif stat.stat_type == StatType.DIMINISHING:
                    result['attack_speed_sources'] = stat.sources

        return result

    def __repr__(self) -> str:
        non_zero = {k: s.value for k, s in self._stats.items() if s.value != 0}
        return f"StatAggregator({non_zero})"


def populate_from_user_data(user_data, job_class=None) -> StatAggregator:
    """
    Populate a StatAggregator from user data, tracking all sources.

    This mirrors the logic of aggregate_stats() but uses StatAggregator's
    add() method for proper source tracking.

    Args:
        user_data: The user's data object from session state
        job_class: JobClass enum (optional, inferred from user_data if not provided)

    Returns:
        A populated StatAggregator instance
    """
    from job_classes import JobClass, get_main_stat_name, get_secondary_stat_name
    from equipment import EQUIPMENT_SLOTS, SLOT_THIRD_MAIN_STAT, get_amplify_multiplier
    from companions import COMPANIONS
    from artifacts import (
        ARTIFACTS, ArtifactTier, EffectType, POTENTIAL_SLOT_UNLOCKS,
        calculate_hex_average_multiplier
    )
    from weapons import calculate_weapon_atk_str
    from weapon_mastery import calculate_mastery_stages_from_weapons, calculate_mastery_stats
    from stage_settings import get_combat_mode_from_string, CombatMode, COMBAT_SCENARIO_PARAMS

    # Get job class
    if job_class is None:
        job_class_str = getattr(user_data, 'job_class', 'bowmaster')
        try:
            job_class = JobClass(job_class_str)
        except ValueError:
            job_class = JobClass.BOWMASTER

    agg = StatAggregator(job_class=job_class)
    agg.character_level = user_data.character_level

    main_stat_type = agg.main_stat_name
    main_flat_key = agg.main_flat_key
    main_pct_key = agg.main_pct_key
    secondary_stat_type = get_secondary_stat_name(job_class)

    # Get combat scenario parameters
    combat_mode_enum = get_combat_mode_from_string(getattr(user_data, 'combat_mode', 'stage'))
    scenario_params = COMBAT_SCENARIO_PARAMS.get(combat_mode_enum, COMBAT_SCENARIO_PARAMS[CombatMode.STAGE])
    num_enemies = scenario_params.num_enemies
    mob_time_fraction = scenario_params.mob_time_fraction
    fight_duration = scenario_params.fight_duration

    # Determine scenario for artifact effects
    combat_mode = getattr(user_data, 'combat_mode', 'stage')
    if combat_mode == 'world_boss':
        scenario = 'world_boss'
    elif combat_mode == 'boss':
        scenario = 'boss'
    else:
        scenario = 'normal'

    # =========================================================================
    # Equipment Potentials (regular and bonus)
    # =========================================================================
    for slot in EQUIPMENT_SLOTS:
        pots = user_data.equipment_potentials.get(slot, {})
        slot_display = slot.replace('_', ' ').title()

        for prefix, prefix_label in [('', 'Pot'), ('bonus_', 'Bonus Pot')]:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = float(pots.get(f'{prefix}line{i}_value', 0))
                if value > 0 and stat:
                    source = f"{slot_display} ({prefix_label} L{i})"
                    # Map stat names to aggregator keys
                    if stat == 'main_stat_flat':
                        agg.add(main_flat_key, value, source)
                    elif stat == 'main_stat_pct':
                        agg.add(main_pct_key, value, source)
                    elif stat == 'damage':
                        agg.add('damage_pct', value, source)
                    elif stat == 'def_pen':
                        agg.add('def_pen', value, source)
                    elif stat == 'final_damage':
                        agg.add('final_damage', value, source)
                    elif stat == 'attack_speed':
                        agg.add('attack_speed', value, source)
                    elif stat in STAT_CONFIG or stat in [main_flat_key, main_pct_key]:
                        agg.add(stat, value, source)

    # =========================================================================
    # Equipment Scrolls
    # =========================================================================
    equipment_scrolls = getattr(user_data, 'equipment_scrolls', {}) or {}
    for slot in EQUIPMENT_SLOTS:
        scroll_data = equipment_scrolls.get(slot, {})
        if scroll_data:
            slot_display = slot.replace('_', ' ').title()
            damage_amp = float(scroll_data.get('damage_amp', 0))
            if damage_amp > 0:
                agg.add('damage_amp', damage_amp, f"{slot_display} (Scroll)")
            flat_atk = float(scroll_data.get('flat_attack', 0))
            if flat_atk > 0:
                agg.add('attack_flat', flat_atk, f"{slot_display} (Scroll)")
            flat_stat = float(scroll_data.get('flat_main_stat', 0))
            if flat_stat > 0:
                agg.add(main_flat_key, flat_stat, f"{slot_display} (Scroll)")

    # =========================================================================
    # Equipment Base Stats (with starforce amplification)
    # =========================================================================
    for slot in EQUIPMENT_SLOTS:
        item = user_data.equipment_items.get(slot, {})
        stars = int(item.get('stars', 0))
        main_mult = get_amplify_multiplier(stars, is_sub=False)
        sub_mult = get_amplify_multiplier(stars, is_sub=True)
        slot_display = slot.replace('_', ' ').title()

        # Base attack
        base_atk = item.get('base_attack', 0) * main_mult
        if base_atk > 0:
            agg.add('attack_flat', base_atk, f"{slot_display} (Base ATK)")

        sub_atk = item.get('sub_attack_flat', 0) * sub_mult
        if sub_atk > 0:
            agg.add('attack_flat', sub_atk, f"{slot_display} (Sub ATK)")

        # Main stat from third stat slot
        third_stat_type = SLOT_THIRD_MAIN_STAT.get(slot, 'main_stat')
        if third_stat_type == 'main_stat':
            third_stat = item.get('base_third_stat', 0) * main_mult
            if third_stat > 0:
                agg.add(main_flat_key, third_stat, f"{slot_display} (Base)")

        # Sub stats
        dmg_pct = item.get('sub_damage_pct', 0) * sub_mult
        if dmg_pct > 0:
            agg.add('damage_pct', dmg_pct, f"{slot_display} (Sub)")
        crit_dmg = item.get('sub_crit_damage', 0) * sub_mult
        if crit_dmg > 0:
            agg.add('crit_damage', crit_dmg, f"{slot_display} (Sub)")
        crit_rate = item.get('sub_crit_rate', 0) * sub_mult
        if crit_rate > 0:
            agg.add('crit_rate', crit_rate, f"{slot_display} (Sub)")
        boss_dmg = item.get('sub_boss_damage', 0) * sub_mult
        if boss_dmg > 0:
            agg.add('boss_damage', boss_dmg, f"{slot_display} (Sub)")
        normal_dmg = item.get('sub_normal_damage', 0) * sub_mult
        if normal_dmg > 0:
            agg.add('normal_damage', normal_dmg, f"{slot_display} (Sub)")

        # Special equipment stats
        if item.get('is_special', False):
            special_type = item.get('special_stat_type', 'damage_pct')
            special_value = item.get('special_stat_value', 0) * sub_mult
            if special_value > 0:
                if special_type == 'damage_pct':
                    agg.add('damage_pct', special_value, f"{slot_display} (Special)")
                elif special_type == 'final_damage':
                    agg.add('final_damage', special_value, f"{slot_display} (Special FD)")
                elif special_type == 'all_skills':
                    agg.add('all_skills', int(special_value), f"{slot_display} (Special)")

        # Skill level bonuses
        for suffix, skill_key in [('sub_skill_1st', 'skill_1st'), ('sub_skill_2nd', 'skill_2nd'),
                                   ('sub_skill_3rd', 'skill_3rd'), ('sub_skill_4th', 'skill_4th')]:
            skill_val = item.get(suffix, 0) * sub_mult
            if skill_val > 0:
                agg.add(skill_key, skill_val, f"{slot_display} (Sub)")

    # =========================================================================
    # Hero Power
    # =========================================================================
    active_preset = getattr(user_data, 'active_hero_power_preset', '1')
    hero_power_presets = getattr(user_data, 'hero_power_presets', {})

    if active_preset and active_preset in hero_power_presets:
        preset_data = hero_power_presets[active_preset]
        hp_lines = preset_data.get('lines', {})
    else:
        hp_lines = user_data.hero_power_lines

    for line_key, line in hp_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        if value > 0 and stat:
            source = f"Hero Power ({line_key})"
            if stat == 'main_stat_flat':
                # HP uses 'main_stat_flat' for flat main stat
                agg.add(main_flat_key, value, source)
            elif stat == 'def_pen':
                agg.add('def_pen', value, source)
            elif stat == 'attack_speed':
                agg.add('attack_speed', value, source)
            elif stat == 'damage':
                agg.add('damage_pct', value, source)
            elif stat in STAT_CONFIG or stat in [main_flat_key, main_pct_key]:
                agg.add(stat, value, source)

    # Hero Power passives
    passive_values = getattr(user_data, 'hero_power_passive_values', {}) or {}
    if passive_values.get('main_stat', 0) > 0:
        agg.add(main_flat_key, passive_values['main_stat'], "Hero Power (Passive)")
    if passive_values.get('damage_percent', 0) > 0:
        agg.add('damage_pct', passive_values['damage_percent'], "Hero Power (Passive)")
    if passive_values.get('attack', 0) > 0:
        agg.add('attack_flat', passive_values['attack'], "Hero Power (Passive)")

    # =========================================================================
    # Maple Rank - use correct cumulative formula
    # =========================================================================
    from maple_rank import get_cumulative_main_stat, MAIN_STAT_SPECIAL
    mr = user_data.maple_rank
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)
    special = mr.get('special_main_stat', 0)
    # Regular main stat uses cumulative formula with varying per-point values
    regular_ms = get_cumulative_main_stat(stage, ms_level)
    if regular_ms > 0:
        agg.add(main_flat_key, regular_ms, "Maple Rank (Regular)")
    # Special main stat has base value of 300 even at 0 points
    special_ms = MAIN_STAT_SPECIAL["base_value"] + special * MAIN_STAT_SPECIAL["per_point"]
    if special_ms > 0:
        agg.add(main_flat_key, special_ms, "Maple Rank (Special)")

    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        atk_spd = stat_levels.get('attack_speed', 0) * 0.35
        if atk_spd > 0:
            agg.add('attack_speed', atk_spd, "Maple Rank")
        cr = stat_levels.get('crit_rate', 0) * 1.0
        if cr > 0:
            agg.add('crit_rate', cr, "Maple Rank")
        dmg = stat_levels.get('damage_percent', 0) * 0.7
        if dmg > 0:
            agg.add('damage_pct', dmg, "Maple Rank")
        boss = stat_levels.get('boss_damage', 0) * 0.667
        if boss > 0:
            agg.add('boss_damage', boss, "Maple Rank")
        normal = stat_levels.get('normal_damage', 0) * 0.667
        if normal > 0:
            agg.add('normal_damage', normal, "Maple Rank")
        cd = stat_levels.get('crit_damage', 0) * 0.667
        if cd > 0:
            agg.add('crit_damage', cd, "Maple Rank")
        sd = stat_levels.get('skill_damage', 0) * 0.833
        if sd > 0:
            agg.add('skill_damage', sd, "Maple Rank")
        min_dmg = stat_levels.get('min_dmg_mult', 0) * 0.55
        if min_dmg > 0:
            agg.add('min_dmg_mult', min_dmg, "Maple Rank")
        max_dmg = stat_levels.get('max_dmg_mult', 0) * 0.55
        if max_dmg > 0:
            agg.add('max_dmg_mult', max_dmg, "Maple Rank")

    # =========================================================================
    # Equipment Sets
    # =========================================================================
    medal_set = user_data.equipment_sets.get('medal', 0)
    if medal_set > 0:
        agg.add(main_flat_key, medal_set, "Medal Set")
    costume_set = user_data.equipment_sets.get('costume', 0)
    if costume_set > 0:
        agg.add(main_flat_key, costume_set, "Costume Set")

    # =========================================================================
    # Weapons
    # =========================================================================
    weapons_data = getattr(user_data, 'weapons_data', {}) or {}
    equipped_weapon_key = getattr(user_data, 'equipped_weapon_key', '') or ''

    # Auto-select best weapon if none equipped
    if not equipped_weapon_key and weapons_data:
        best_key = ""
        best_atk = 0.0
        for key, w_data in weapons_data.items():
            lvl = w_data.get('level', 0)
            if lvl <= 0:
                continue
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                rarity, tier = parts[0], int(parts[1])
                w_stats = calculate_weapon_atk_str(rarity, tier, lvl)
                if w_stats['on_equip_atk'] > best_atk:
                    best_atk = w_stats['on_equip_atk']
                    best_key = key
        equipped_weapon_key = best_key

    for key, weapon_data in weapons_data.items():
        level = weapon_data.get('level', 0)
        if level > 0:
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                rarity, tier = parts[0], int(parts[1])
                weapon_stats = calculate_weapon_atk_str(rarity, tier, level)

                inv_atk = weapon_stats['inventory_atk']
                if inv_atk > 0:
                    agg.add('attack_pct', inv_atk, f"Weapon ({rarity.title()} T{tier} Inv)")

                if key == equipped_weapon_key:
                    equip_atk = weapon_stats['on_equip_atk']
                    if equip_atk > 0:
                        agg.add('attack_pct', equip_atk, f"Weapon ({rarity.title()} T{tier} Equip)")

    # Weapon Mastery
    if weapons_data:
        mastery_stages = calculate_mastery_stages_from_weapons(weapons_data)
        mastery_stats = calculate_mastery_stats(mastery_stages)
        if mastery_stats['attack'] > 0:
            agg.add('attack_flat', mastery_stats['attack'], "Weapon Mastery")
        if mastery_stats['main_stat'] > 0:
            agg.add(main_flat_key, mastery_stats['main_stat'], "Weapon Mastery")
        if mastery_stats['min_dmg_mult'] > 0:
            agg.add('min_dmg_mult', mastery_stats['min_dmg_mult'], "Weapon Mastery")
        if mastery_stats['max_dmg_mult'] > 0:
            agg.add('max_dmg_mult', mastery_stats['max_dmg_mult'], "Weapon Mastery")

    # =========================================================================
    # Companions
    # =========================================================================
    equipped_companions = getattr(user_data, 'equipped_companions', []) or []
    companion_levels = getattr(user_data, 'companion_levels', {}) or {}

    # On-equip stats
    for comp_key in equipped_companions:
        if not comp_key or comp_key not in COMPANIONS:
            continue
        level = companion_levels.get(comp_key, 0)
        if level <= 0:
            continue

        companion = COMPANIONS[comp_key]
        stat_type = companion.on_equip_type.value
        value = companion.get_on_equip_value(level)
        source = f"Companion ({companion.name} Equip)"

        if value > 0:
            if stat_type == 'attack_speed':
                agg.add('attack_speed', value, source)
            elif stat_type == 'flat_attack':
                agg.add('attack_flat', value, source)
            elif stat_type in STAT_CONFIG:
                agg.add(stat_type, value, source)

    # Inventory stats from all owned companions
    for comp_key, level in companion_levels.items():
        if level <= 0 or comp_key not in COMPANIONS:
            continue

        companion = COMPANIONS[comp_key]
        inv_stats = companion.get_inventory_stats(level)
        source = f"Companion ({companion.name} Inv)"

        if 'attack_flat' in inv_stats and inv_stats['attack_flat'] > 0:
            agg.add('attack_flat', inv_stats['attack_flat'], source)
        if 'main_stat_flat' in inv_stats and inv_stats['main_stat_flat'] > 0:
            agg.add(main_flat_key, inv_stats['main_stat_flat'], source)
        if 'damage_pct' in inv_stats and inv_stats['damage_pct'] > 0:
            agg.add('damage_pct', inv_stats['damage_pct'], source)

    # =========================================================================
    # Guild Skills
    # =========================================================================
    guild_skills = getattr(user_data, 'guild_skills', {})
    if guild_skills:
        if guild_skills.get('def_pen', 0) > 0:
            agg.add('def_pen', guild_skills['def_pen'], "Guild Skill")
        if guild_skills.get('final_damage', 0) > 0:
            agg.add('final_damage', guild_skills['final_damage'], "Guild Skill")
        if guild_skills.get('damage', 0) > 0:
            agg.add('damage_pct', guild_skills['damage'], "Guild Skill")
        if guild_skills.get('boss_damage', 0) > 0:
            agg.add('boss_damage', guild_skills['boss_damage'], "Guild Skill")
        if guild_skills.get('crit_damage', 0) > 0:
            agg.add('crit_damage', guild_skills['crit_damage'], "Guild Skill")
        if guild_skills.get('main_stat', 0) > 0:
            agg.add(main_pct_key, guild_skills['main_stat'], "Guild Skill")
        if guild_skills.get('attack', 0) > 0:
            agg.add('attack_flat', guild_skills['attack'], "Guild Skill")

    # =========================================================================
    # Artifacts
    # =========================================================================
    artifact_key_by_name = {defn.name: key for key, defn in ARTIFACTS.items()}
    artifacts_inventory = getattr(user_data, 'artifacts_inventory', {})
    artifacts_equipped = getattr(user_data, 'artifacts_equipped', {})

    # Build set of equipped artifact keys
    equipped_artifact_keys = set()
    if artifacts_equipped:
        for slot_key in ['slot0', 'slot1', 'slot2']:
            slot_data = artifacts_equipped.get(slot_key, {})
            if not isinstance(slot_data, dict):
                continue
            artifact_key = slot_data.get('artifact', '')
            if not artifact_key:
                name = slot_data.get('name', '')
                if name and name != '(Empty)':
                    artifact_key = artifact_key_by_name.get(name, '')
            if artifact_key:
                equipped_artifact_keys.add(artifact_key)

    # Inventory stats (from all owned artifacts)
    if artifacts_inventory:
        for art_key, art_data in artifacts_inventory.items():
            if art_key not in ARTIFACTS:
                continue
            if not isinstance(art_data, dict):
                continue

            defn = ARTIFACTS[art_key]
            stars = int(art_data.get('stars', 0))
            inv_stat = defn.inventory_stat
            inv_value = defn.get_inventory_value(stars)

            if inv_value > 0:
                source = f"Artifact ({defn.name} Inv)"
                if inv_stat == 'attack_flat':
                    agg.add('attack_flat', inv_value, source)
                elif inv_stat == 'damage':
                    agg.add('damage_pct', inv_value * 100, source)
                elif inv_stat == 'boss_damage':
                    agg.add('boss_damage', inv_value * 100, source)
                elif inv_stat == 'normal_damage':
                    agg.add('normal_damage', inv_value * 100, source)
                elif inv_stat == 'crit_rate':
                    agg.add('crit_rate', inv_value * 100, source)
                elif inv_stat == 'crit_damage':
                    agg.add('crit_damage', inv_value * 100, source)
                elif inv_stat == 'max_damage_mult':
                    agg.add('max_dmg_mult', inv_value * 100, source)
                elif inv_stat == 'def_pen':
                    agg.add('def_pen', inv_value * 100, source)
                elif inv_stat == 'basic_attack_damage':
                    agg.add('basic_attack_damage', inv_value * 100, source)
                elif inv_stat == 'skill_damage':
                    agg.add('skill_damage', inv_value * 100, source)

            # Potentials (only from equipped artifacts)
            if art_key not in equipped_artifact_keys:
                continue

            slots_unlocked = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
            if defn.tier != ArtifactTier.LEGENDARY and slots_unlocked > 2:
                slots_unlocked = 2

            potentials = art_data.get('potentials', [])
            if isinstance(potentials, list):
                for idx, pot in enumerate(potentials):
                    if idx >= slots_unlocked:
                        continue
                    if isinstance(pot, dict):
                        pot_stat = pot.get('stat', '')
                        pot_value = float(pot.get('value', 0) or 0)
                        if pot_value > 0:
                            source = f"Artifact ({defn.name} Pot)"
                            if pot_stat == 'main_stat_pct':
                                agg.add(main_pct_key, pot_value, source)
                            elif pot_stat == 'def_pen':
                                agg.add('def_pen', pot_value, source)
                            elif pot_stat in STAT_CONFIG or pot_stat in [main_flat_key, main_pct_key]:
                                agg.add(pot_stat, pot_value, source)

    # Artifact active effects (from equipped artifacts)
    if artifacts_equipped:
        for slot_key in ['slot0', 'slot1', 'slot2']:
            slot_data = artifacts_equipped.get(slot_key, {})
            if not isinstance(slot_data, dict):
                continue

            name = slot_data.get('name', '')
            artifact_key = ''
            if name and name != '(Empty)':
                artifact_key = artifact_key_by_name.get(name, '')
            if not artifact_key:
                artifact_key = slot_data.get('artifact', '')

            if not artifact_key or artifact_key not in ARTIFACTS:
                continue

            # Get stars from inventory
            if artifact_key in artifacts_inventory:
                inv_data = artifacts_inventory.get(artifact_key, {})
                stars = int(inv_data.get('stars', 0)) if isinstance(inv_data, dict) else 0
            else:
                stars = int(slot_data.get('stars', 0))

            defn = ARTIFACTS[artifact_key]

            if not defn.applies_to_scenario(scenario):
                continue

            uptime = defn.get_effective_uptime(fight_duration)

            if not defn.active_effects:
                continue

            for effect in defn.active_effects:
                effect_value = effect.get_value(stars) * uptime
                source = f"Artifact ({defn.name} Active)"

                if effect.effect_type == EffectType.DERIVED and effect.derived_from:
                    # Skip derived effects in this simplified version
                    continue
                elif effect.effect_type == EffectType.MULTIPLICATIVE:
                    # Hex Necklace
                    if artifact_key == 'hexagon_necklace' and stars > 0:
                        agg.hex_necklace_stars = stars
                        agg.hex_multiplier = calculate_hex_average_multiplier(stars, fight_duration)
                    continue

                # Handle per-target effects
                if effect.max_stacks > 0 and effect.stat == 'final_damage':
                    mob_stacks = min(num_enemies, effect.max_stacks)
                    boss_stacks = min(1, effect.max_stacks)
                    weighted_stacks = mob_stacks * mob_time_fraction + boss_stacks * (1 - mob_time_fraction)
                    effect_value = effect_value * weighted_stacks

                stat = effect.stat
                if stat == 'crit_rate':
                    agg.add('crit_rate', effect_value * 100, source)
                elif stat == 'crit_damage':
                    agg.add('crit_damage', effect_value * 100, source)
                elif stat == 'boss_damage':
                    agg.add('boss_damage', effect_value * 100, source)
                elif stat == 'normal_damage':
                    agg.add('normal_damage', effect_value * 100, source)
                elif stat in ('damage', 'damage_multiplier'):
                    agg.add('damage_pct', effect_value * 100, source)
                elif stat == 'final_damage':
                    if effect_value > 0:
                        agg.add('final_damage', effect_value * 100, source)
                elif stat == 'attack_speed':
                    agg.add('attack_speed', effect_value * 100, source)
                elif stat == 'max_damage_mult':
                    agg.add('max_dmg_mult', effect_value * 100, source)
                elif stat == 'attack_buff':
                    agg.add('attack_pct', effect_value * 100, source)
                elif stat == 'enemy_damage_taken':
                    if effect_value > 0:
                        agg.add('final_damage', effect_value * 100, source)

    # Artifact Resonance
    artifacts_resonance = getattr(user_data, 'artifacts_resonance', {}) or {}
    if artifacts_resonance:
        resonance_level = int(artifacts_resonance.get('resonance_level', 0))
        if resonance_level > 0:
            from artifacts import calculate_resonance_main_stat
            resonance_main = calculate_resonance_main_stat(resonance_level)
            if resonance_main > 0:
                agg.add(main_flat_key, resonance_main, "Artifact Resonance")

    # =========================================================================
    # Skill Passive Stats
    # =========================================================================
    try:
        from skills import DPSCalculator as SkillDPSCalculator, CharacterState, get_global_mastery_stats
        char_level = getattr(user_data, 'character_level', 100)
        all_skills_bonus = getattr(user_data, 'all_skills', 0)

        # Calculate job-specific skill bonuses from equipment sub-stats
        # These affect skills like Bow Mastery's min_dmg_mult calculation
        skill_1st_total = 0
        skill_2nd_total = 0
        skill_3rd_total = 0
        skill_4th_total = 0
        for slot in EQUIPMENT_SLOTS:
            item = user_data.equipment_items.get(slot, {})
            stars = int(item.get('stars', 0))
            sub_mult = get_amplify_multiplier(stars, is_sub=True)
            skill_1st_total += int(item.get('sub_skill_1st', 0) * sub_mult)
            skill_2nd_total += int(item.get('sub_skill_2nd', 0) * sub_mult)
            skill_3rd_total += int(item.get('sub_skill_3rd', 0) * sub_mult)
            skill_4th_total += int(item.get('sub_skill_4th', 0) * sub_mult)

        char = CharacterState(
            level=char_level,
            all_skills_bonus=all_skills_bonus,
            skill_1st_bonus=skill_1st_total,
            skill_2nd_bonus=skill_2nd_total,
            skill_3rd_bonus=skill_3rd_total,
            skill_4th_bonus=skill_4th_total,
        )
        calc = SkillDPSCalculator(char)

        skill_bonuses = calc.get_all_skill_stat_bonuses(is_boss_phase=None)

        if 'min_dmg_mult' in skill_bonuses:
            for val in skill_bonuses['min_dmg_mult']:
                agg.add('min_dmg_mult', val, "Passive Skill")
        if 'attack_speed' in skill_bonuses:
            for val in skill_bonuses['attack_speed']:
                agg.add('attack_speed', val, "Passive Skill")
        if 'defense_pen' in skill_bonuses:
            for val in skill_bonuses['defense_pen']:
                agg.add('def_pen', val, "Passive Skill")
        if 'final_damage' in skill_bonuses:
            for val in skill_bonuses['final_damage']:
                agg.add('final_damage', val, "Passive Skill")
        if 'crit_rate' in skill_bonuses:
            for val in skill_bonuses['crit_rate']:
                agg.add('crit_rate', val, "Passive Skill")
        if 'dex_flat' in skill_bonuses:
            for val in skill_bonuses['dex_flat']:
                agg.add(main_flat_key, val, "Passive Skill")
        if 'basic_attack_damage' in skill_bonuses:
            for val in skill_bonuses['basic_attack_damage']:
                agg.add('basic_attack_damage', val, "Passive Skill")

        # Global mastery stats
        mastery_stats = get_global_mastery_stats(char_level)
        if 'max_dmg_mult' in mastery_stats:
            agg.add('max_dmg_mult', mastery_stats['max_dmg_mult'], "Mastery Node")
        if 'crit_rate' in mastery_stats:
            agg.add('crit_rate', mastery_stats['crit_rate'], "Mastery Node")
        if 'attack_speed' in mastery_stats:
            agg.add('attack_speed', mastery_stats['attack_speed'], "Mastery Node")
        if 'main_stat_flat' in mastery_stats:
            agg.add(main_flat_key, mastery_stats['main_stat_flat'], "Mastery Node")
        if 'basic_attack_damage' in mastery_stats:
            agg.add('basic_attack_damage', mastery_stats['basic_attack_damage'], "Mastery Node")
        if 'skill_damage' in mastery_stats:
            agg.add('skill_damage', mastery_stats['skill_damage'], "Mastery Node")

    except Exception as e:
        import traceback
        print(f"Error in skill passive stats: {e}")
        traceback.print_exc()

    return agg
