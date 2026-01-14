"""
MapleStory Idle - Stat System
=============================
Type-safe stat classes with enforced attribute names and operator overloading.

Core Classes:
- StatBlock: Immutable container for all stats, supports + operator for combining
- SourcedStat: A stat value with its source for display/debugging
- SourcedStatBlock: StatBlock with full source tracking
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from job_classes import JobClass


@dataclass(frozen=True)
class StatBlock:
    """
    Immutable container for all stats. Supports addition via + operator.

    All stats are stored as absolute values (not percentages as decimals).
    E.g., 50% crit rate is stored as 50.0, not 0.5
    """
    # Main stats (flat)
    dex_flat: float = 0.0
    str_flat: float = 0.0
    int_flat: float = 0.0
    luk_flat: float = 0.0

    # Main stats (percent)
    dex_pct: float = 0.0
    str_pct: float = 0.0
    int_pct: float = 0.0
    luk_pct: float = 0.0

    # Attack
    attack_flat: float = 0.0
    attack_pct: float = 0.0

    # Damage
    damage_pct: float = 0.0
    boss_damage: float = 0.0
    normal_damage: float = 0.0

    # Critical
    crit_rate: float = 0.0
    crit_damage: float = 0.0

    # Damage range
    min_dmg_mult: float = 0.0
    max_dmg_mult: float = 0.0

    # Multiplicative stats (special handling in DPS calc)
    def_pen: float = 0.0          # Single value, stacks multiplicatively
    final_damage: float = 0.0     # Single value, stacks multiplicatively
    attack_speed: float = 0.0     # Single value, soft cap at 100%

    # Skills
    all_skills: int = 0
    skill_damage: float = 0.0
    skill_cd: float = 0.0
    buff_duration: float = 0.0
    skill_1st: int = 0
    skill_2nd: int = 0
    skill_3rd: int = 0
    skill_4th: int = 0

    # Utility
    accuracy: float = 0.0
    ba_targets: int = 0
    basic_attack_damage: float = 0.0

    # Defense (non-DPS)
    max_hp: float = 0.0
    max_mp: float = 0.0
    defense: float = 0.0

    def __add__(self, other: 'StatBlock') -> 'StatBlock':
        """Add two StatBlocks together."""
        if not isinstance(other, StatBlock):
            return NotImplemented

        return StatBlock(
            # Main stats flat
            dex_flat=self.dex_flat + other.dex_flat,
            str_flat=self.str_flat + other.str_flat,
            int_flat=self.int_flat + other.int_flat,
            luk_flat=self.luk_flat + other.luk_flat,
            # Main stats percent
            dex_pct=self.dex_pct + other.dex_pct,
            str_pct=self.str_pct + other.str_pct,
            int_pct=self.int_pct + other.int_pct,
            luk_pct=self.luk_pct + other.luk_pct,
            # Attack
            attack_flat=self.attack_flat + other.attack_flat,
            attack_pct=self.attack_pct + other.attack_pct,
            # Damage
            damage_pct=self.damage_pct + other.damage_pct,
            boss_damage=self.boss_damage + other.boss_damage,
            normal_damage=self.normal_damage + other.normal_damage,
            # Critical
            crit_rate=self.crit_rate + other.crit_rate,
            crit_damage=self.crit_damage + other.crit_damage,
            # Damage range
            min_dmg_mult=self.min_dmg_mult + other.min_dmg_mult,
            max_dmg_mult=self.max_dmg_mult + other.max_dmg_mult,
            # Multiplicative stats - use multiplicative combination
            def_pen=self._combine_multiplicative(self.def_pen, other.def_pen),
            final_damage=self._combine_multiplicative(self.final_damage, other.final_damage),
            attack_speed=min(100.0, self.attack_speed + other.attack_speed),  # Soft cap
            # Skills
            all_skills=self.all_skills + other.all_skills,
            skill_damage=self.skill_damage + other.skill_damage,
            skill_cd=self.skill_cd + other.skill_cd,
            buff_duration=self.buff_duration + other.buff_duration,
            skill_1st=self.skill_1st + other.skill_1st,
            skill_2nd=self.skill_2nd + other.skill_2nd,
            skill_3rd=self.skill_3rd + other.skill_3rd,
            skill_4th=self.skill_4th + other.skill_4th,
            # Utility
            accuracy=self.accuracy + other.accuracy,
            ba_targets=self.ba_targets + other.ba_targets,
            basic_attack_damage=self.basic_attack_damage + other.basic_attack_damage,
            # Defense
            max_hp=self.max_hp + other.max_hp,
            max_mp=self.max_mp + other.max_mp,
            defense=self.defense + other.defense,
        )

    def __radd__(self, other):
        """Support sum() by handling 0 + StatBlock."""
        if other == 0:
            return self
        return self.__add__(other)

    @staticmethod
    def _combine_multiplicative(a: float, b: float) -> float:
        """
        Combine multiplicative stats: (1+a)(1+b) - 1 = a + b + ab

        Values are stored as percentages (e.g., 10 for 10%).
        Convert to decimals, multiply, convert back.
        """
        if a == 0:
            return b
        if b == 0:
            return a
        a_dec = a / 100
        b_dec = b / 100
        combined = (1 + a_dec) * (1 + b_dec) - 1
        return combined * 100

    def get_main_stat_flat(self, job_class: 'JobClass') -> float:
        """Get the flat main stat value for a job class."""
        from job_classes import get_main_stat_name
        stat_name = get_main_stat_name(job_class)
        return getattr(self, f'{stat_name}_flat')

    def get_main_stat_pct(self, job_class: 'JobClass') -> float:
        """Get the percent main stat value for a job class."""
        from job_classes import get_main_stat_name
        stat_name = get_main_stat_name(job_class)
        return getattr(self, f'{stat_name}_pct')

    def get_secondary_stat_flat(self, job_class: 'JobClass') -> float:
        """Get the flat secondary stat value for a job class."""
        from job_classes import get_secondary_stat_name
        stat_name = get_secondary_stat_name(job_class)
        return getattr(self, f'{stat_name}_flat')

    def get_secondary_stat_pct(self, job_class: 'JobClass') -> float:
        """Get the percent secondary stat value for a job class."""
        from job_classes import get_secondary_stat_name
        stat_name = get_secondary_stat_name(job_class)
        return getattr(self, f'{stat_name}_pct')

    def with_main_stat_flat(self, job_class: 'JobClass', value: float) -> 'StatBlock':
        """Return new StatBlock with main stat flat set for job class."""
        from job_classes import get_main_stat_name
        stat_name = get_main_stat_name(job_class)
        kwargs = {f'{stat_name}_flat': value}
        return self._with_updates(**kwargs)

    def with_main_stat_pct(self, job_class: 'JobClass', value: float) -> 'StatBlock':
        """Return new StatBlock with main stat pct set for job class."""
        from job_classes import get_main_stat_name
        stat_name = get_main_stat_name(job_class)
        kwargs = {f'{stat_name}_pct': value}
        return self._with_updates(**kwargs)

    def _with_updates(self, **kwargs) -> 'StatBlock':
        """Return new StatBlock with specified fields updated."""
        # Get all current values
        current = {
            'dex_flat': self.dex_flat,
            'str_flat': self.str_flat,
            'int_flat': self.int_flat,
            'luk_flat': self.luk_flat,
            'dex_pct': self.dex_pct,
            'str_pct': self.str_pct,
            'int_pct': self.int_pct,
            'luk_pct': self.luk_pct,
            'attack_flat': self.attack_flat,
            'attack_pct': self.attack_pct,
            'damage_pct': self.damage_pct,
            'boss_damage': self.boss_damage,
            'normal_damage': self.normal_damage,
            'crit_rate': self.crit_rate,
            'crit_damage': self.crit_damage,
            'min_dmg_mult': self.min_dmg_mult,
            'max_dmg_mult': self.max_dmg_mult,
            'def_pen': self.def_pen,
            'final_damage': self.final_damage,
            'attack_speed': self.attack_speed,
            'all_skills': self.all_skills,
            'skill_damage': self.skill_damage,
            'skill_cd': self.skill_cd,
            'buff_duration': self.buff_duration,
            'skill_1st': self.skill_1st,
            'skill_2nd': self.skill_2nd,
            'skill_3rd': self.skill_3rd,
            'skill_4th': self.skill_4th,
            'accuracy': self.accuracy,
            'ba_targets': self.ba_targets,
            'basic_attack_damage': self.basic_attack_damage,
            'max_hp': self.max_hp,
            'max_mp': self.max_mp,
            'defense': self.defense,
        }
        # Apply updates
        current.update(kwargs)
        return StatBlock(**current)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        return {
            'dex_flat': self.dex_flat,
            'str_flat': self.str_flat,
            'int_flat': self.int_flat,
            'luk_flat': self.luk_flat,
            'dex_pct': self.dex_pct,
            'str_pct': self.str_pct,
            'int_pct': self.int_pct,
            'luk_pct': self.luk_pct,
            'attack_flat': self.attack_flat,
            'attack_pct': self.attack_pct,
            'damage_pct': self.damage_pct,
            'boss_damage': self.boss_damage,
            'normal_damage': self.normal_damage,
            'crit_rate': self.crit_rate,
            'crit_damage': self.crit_damage,
            'min_dmg_mult': self.min_dmg_mult,
            'max_dmg_mult': self.max_dmg_mult,
            'def_pen': self.def_pen,
            'final_damage': self.final_damage,
            'attack_speed': self.attack_speed,
            'all_skills': self.all_skills,
            'skill_damage': self.skill_damage,
            'skill_cd': self.skill_cd,
            'buff_duration': self.buff_duration,
            'skill_1st': self.skill_1st,
            'skill_2nd': self.skill_2nd,
            'skill_3rd': self.skill_3rd,
            'skill_4th': self.skill_4th,
            'accuracy': self.accuracy,
            'ba_targets': self.ba_targets,
            'basic_attack_damage': self.basic_attack_damage,
            'max_hp': self.max_hp,
            'max_mp': self.max_mp,
            'defense': self.defense,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'StatBlock':
        """Create StatBlock from dictionary."""
        return cls(
            dex_flat=data.get('dex_flat', 0.0),
            str_flat=data.get('str_flat', 0.0),
            int_flat=data.get('int_flat', 0.0),
            luk_flat=data.get('luk_flat', 0.0),
            dex_pct=data.get('dex_pct', 0.0),
            str_pct=data.get('str_pct', 0.0),
            int_pct=data.get('int_pct', 0.0),
            luk_pct=data.get('luk_pct', 0.0),
            attack_flat=data.get('attack_flat', 0.0),
            attack_pct=data.get('attack_pct', 0.0),
            damage_pct=data.get('damage_pct', 0.0),
            boss_damage=data.get('boss_damage', 0.0),
            normal_damage=data.get('normal_damage', 0.0),
            crit_rate=data.get('crit_rate', 0.0),
            crit_damage=data.get('crit_damage', 0.0),
            min_dmg_mult=data.get('min_dmg_mult', 0.0),
            max_dmg_mult=data.get('max_dmg_mult', 0.0),
            def_pen=data.get('def_pen', 0.0),
            final_damage=data.get('final_damage', 0.0),
            attack_speed=data.get('attack_speed', 0.0),
            all_skills=int(data.get('all_skills', 0)),
            skill_damage=data.get('skill_damage', 0.0),
            skill_cd=data.get('skill_cd', 0.0),
            buff_duration=data.get('buff_duration', 0.0),
            skill_1st=int(data.get('skill_1st', 0)),
            skill_2nd=int(data.get('skill_2nd', 0)),
            skill_3rd=int(data.get('skill_3rd', 0)),
            skill_4th=int(data.get('skill_4th', 0)),
            accuracy=data.get('accuracy', 0.0),
            ba_targets=int(data.get('ba_targets', 0)),
            basic_attack_damage=data.get('basic_attack_damage', 0.0),
            max_hp=data.get('max_hp', 0.0),
            max_mp=data.get('max_mp', 0.0),
            defense=data.get('defense', 0.0),
        )


# Empty stat block singleton for convenience
EMPTY_STATS = StatBlock()


@dataclass
class SourcedStat:
    """A stat value with its source for display/debugging."""
    source: str       # "Hat", "Artifact: Chalice", "Guild Skill: Attack"
    stat_name: str    # "boss_damage", "dex_pct"
    value: float

    def __repr__(self):
        return f"{self.source}: {self.stat_name} +{self.value}"


@dataclass
class SourcedStatBlock:
    """
    StatBlock with source tracking for each stat.
    Used for display/debugging - shows where each stat came from.
    """
    stats: StatBlock = field(default_factory=lambda: EMPTY_STATS)
    sources: Dict[str, List[SourcedStat]] = field(default_factory=dict)

    def add_stat(self, source: str, stat_name: str, value: float):
        """Add a stat from a source."""
        if value == 0:
            return
        if stat_name not in self.sources:
            self.sources[stat_name] = []
        self.sources[stat_name].append(SourcedStat(source, stat_name, value))

    def add_stats_from_block(self, source: str, block: StatBlock):
        """Add all non-zero stats from a StatBlock with the given source."""
        d = block.to_dict()
        for stat_name, value in d.items():
            if value != 0:
                self.add_stat(source, stat_name, value)

    def get_breakdown(self, stat_name: str) -> List[SourcedStat]:
        """Get all sources contributing to a stat."""
        return self.sources.get(stat_name, [])

    def get_total(self, stat_name: str) -> float:
        """Get total value for a stat across all sources."""
        return sum(s.value for s in self.sources.get(stat_name, []))

    def combine(self, other: 'SourcedStatBlock') -> 'SourcedStatBlock':
        """Combine two SourcedStatBlocks."""
        result = SourcedStatBlock(
            stats=self.stats + other.stats,
            sources={k: list(v) for k, v in self.sources.items()}
        )
        for stat_name, sources in other.sources.items():
            if stat_name not in result.sources:
                result.sources[stat_name] = []
            result.sources[stat_name].extend(sources)
        return result


def create_stat_block_for_job(
    job_class: 'JobClass',
    main_stat_flat: float = 0.0,
    main_stat_pct: float = 0.0,
    **kwargs
) -> StatBlock:
    """
    Create a StatBlock with main stat values set for the given job class.

    This is a helper for sources that use generic 'main_stat' keys.
    """
    from job_classes import get_main_stat_name
    stat_name = get_main_stat_name(job_class)

    # Start with provided kwargs
    block_kwargs = dict(kwargs)

    # Add main stat flat/pct to the correct job-specific field
    if main_stat_flat != 0:
        block_kwargs[f'{stat_name}_flat'] = main_stat_flat
    if main_stat_pct != 0:
        block_kwargs[f'{stat_name}_pct'] = main_stat_pct

    return StatBlock(**block_kwargs)


# =============================================================================
# STAT AGGREGATOR - Bridge between StatBlock and DPS Calculator
# =============================================================================

@dataclass
class MultStatSource:
    """A multiplicative stat source with priority for ordering."""
    source: str       # "Guild Skill", "Shoulder Pot L1", "Hero Power"
    value: float      # Decimal value (0.20 for 20%)
    priority: int     # Lower = applied first (guild=1, shoulder=2, hero=3, other=100)


@dataclass
class StatAggregator:
    """
    Aggregates stats from multiple sources for DPS calculation.

    Combines:
    - StatBlock for additive stats (type-safe, supports + operator)
    - Source lists for multiplicative stats (def_pen, final_damage, attack_speed)

    Multiplicative stats need source tracking because:
    - Defense Pen: Applied in priority order (guild > shoulder > hero_power)
    - Final Damage: Each source multiplies separately
    - Attack Speed: Has diminishing returns with soft cap
    """
    stats: StatBlock = field(default_factory=lambda: EMPTY_STATS)

    # Multiplicative stat sources (need special handling)
    def_pen_sources: List[MultStatSource] = field(default_factory=list)
    final_damage_sources: List[float] = field(default_factory=list)  # Decimal values
    attack_speed_sources: List[tuple] = field(default_factory=list)  # (source_name, value)

    # Context for conversions (All Skills → FD, etc.)
    character_level: int = 140
    book_of_ancient_stars: int = 0
    hex_multiplier: float = 1.0

    # Adjustment tracking (from Character Stats page)
    total_main_stat_adjustment: float = 0.0
    total_attack_adjustment: float = 0.0

    def add_stats(self, block: StatBlock, source: str = ""):
        """Add a StatBlock of stats."""
        self.stats = self.stats + block

    def add_def_pen(self, source: str, value_pct: float, priority: int = 100):
        """Add a defense penetration source (value as percentage, e.g., 20 for 20%)."""
        if value_pct > 0:
            self.def_pen_sources.append(MultStatSource(source, value_pct / 100, priority))

    def add_final_damage(self, value_pct: float):
        """Add a final damage source (value as percentage, e.g., 10 for 10%)."""
        if value_pct > 0:
            self.final_damage_sources.append(value_pct / 100)

    def add_attack_speed(self, source: str, value_pct: float):
        """Add an attack speed source (value as percentage, e.g., 15 for 15%)."""
        if value_pct > 0:
            self.attack_speed_sources.append((source, value_pct))

    def to_dps_dict(self, job_class: 'JobClass') -> Dict[str, any]:
        """
        Convert to the dict format expected by calculate_dps().

        This bridges the type-safe StatBlock with the existing DPS calculator.
        Uses standardized stat names from stat_names.py.
        """
        from job_classes import get_main_stat_name, get_secondary_stat_name

        main_stat = get_main_stat_name(job_class)
        secondary_stat = get_secondary_stat_name(job_class)

        # Get main/secondary stat values from StatBlock
        main_flat = self.stats.get_main_stat_flat(job_class)
        main_pct = self.stats.get_main_stat_pct(job_class)
        secondary_flat = self.stats.get_secondary_stat_flat(job_class)
        secondary_pct = self.stats.get_secondary_stat_pct(job_class)

        # Build the dict with standardized stat names
        result = {
            # Main stats (job-specific keys, e.g., 'dex_flat', 'dex_pct')
            f'{main_stat}_flat': main_flat,
            f'{main_stat}_pct': main_pct,
            f'{secondary_stat}_flat': secondary_flat,
            f'{secondary_stat}_pct': secondary_pct,

            # Damage stats
            'damage_pct': self.stats.damage_pct,
            'boss_damage': self.stats.boss_damage,
            'normal_damage': self.stats.normal_damage,

            # Critical stats
            'crit_rate': self.stats.crit_rate,
            'crit_damage': self.stats.crit_damage,

            # Damage range
            'min_dmg_mult': self.stats.min_dmg_mult,
            'max_dmg_mult': self.stats.max_dmg_mult,

            # Attack
            'attack_flat': self.stats.attack_flat,
            'attack_pct': self.stats.attack_pct,

            # Skills
            'skill_damage': self.stats.skill_damage,
            'all_skills': self.stats.all_skills,
            'skill_cd': self.stats.skill_cd,
            'buff_duration': self.stats.buff_duration,
            'skill_1st': self.stats.skill_1st,
            'skill_2nd': self.stats.skill_2nd,
            'skill_3rd': self.stats.skill_3rd,
            'skill_4th': self.stats.skill_4th,

            # Utility
            'accuracy': self.stats.accuracy,
            'ba_targets': self.stats.ba_targets,
            'basic_attack_damage': self.stats.basic_attack_damage,

            # Defense (non-DPS)
            'max_hp': self.stats.max_hp,
            'max_mp': self.stats.max_mp,
            'defense': self.stats.defense,

            # Multiplicative stat sources (lists for special handling)
            'def_pen_sources': [
                (s.source, s.value, s.priority) for s in self.def_pen_sources
            ],
            'final_damage_sources': self.final_damage_sources,
            'attack_speed_sources': self.attack_speed_sources,

            # Context
            'character_level': self.character_level,
            'book_of_ancient_stars': self.book_of_ancient_stars,
            'hex_multiplier': self.hex_multiplier,

            # Adjustments
            'total_main_stat_adjustment': self.total_main_stat_adjustment,
            'total_attack_adjustment': self.total_attack_adjustment,
        }

        return result

    def get_total_def_pen(self) -> float:
        """Calculate total defense penetration with priority-based stacking."""
        if not self.def_pen_sources:
            return 0.0

        # Sort by priority, then by value (highest first for same priority)
        sorted_sources = sorted(
            self.def_pen_sources,
            key=lambda s: (s.priority, -s.value)
        )

        remaining = 1.0
        for source in sorted_sources:
            remaining *= (1 - source.value)

        return min(1 - remaining, 1.0)

    def get_total_final_damage_mult(self) -> float:
        """Calculate total final damage multiplier."""
        mult = 1.0
        for fd in self.final_damage_sources:
            mult *= (1 + fd)
        return mult * self.hex_multiplier

    def get_total_attack_speed(self, cap: float = 150.0) -> float:
        """Calculate total attack speed with diminishing returns."""
        current = 0.0
        for source, value in sorted(self.attack_speed_sources, key=lambda x: -x[1]):
            if value > 0:
                gain = (cap - current) * (value / cap)
                current += gain
        return min(current, cap)


# Export list
__all__ = [
    'StatBlock',
    'EMPTY_STATS',
    'SourcedStat',
    'SourcedStatBlock',
    'create_stat_block_for_job',
    'MultStatSource',
    'StatAggregator',
]
