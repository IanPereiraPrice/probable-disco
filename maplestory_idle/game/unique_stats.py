"""
Unique Stat Point system.

Derived directly from datamine:
- HeroStatStepTable.json: AddUniqueStatCount per StatStep (10 for steps 3-10, 20 for 11-26)
- HeroUniqueStatOptionTable.json: per-stat base value, added value, max level, point cost, unlock level

Each StatStep covers 5 character levels (StatStep N starts at character level 5N).
A character at level L is at StatStep floor(L / 5), and has earned the cumulative
sum of AddUniqueStatCount across all steps up to and including that one.
"""

from typing import Dict, List, NamedTuple


# HeroStatStepTable.json - cumulative points awarded by character level breakpoint.
# StatStep N starts at character level 5*N. The first step that awards any points
# is StatStep 3 (level 15+). Last entry in the table is StatStep 26 (level 130+).
_STEP_POINTS: Dict[int, int] = {
    3: 10,  4: 10,  5: 10,  6: 10,  7: 10,  8: 10,  9: 10,  10: 10,
    11: 20, 12: 20, 13: 20, 14: 20, 15: 20, 16: 20, 17: 20, 18: 20,
    19: 20, 20: 20, 21: 20, 22: 20, 23: 20, 24: 20, 25: 20, 26: 20,
}

# Max StatStep covered by the table. Characters above level 5*MAX_STEP do not
# earn additional unique stat points (only stats they can still allocate into
# higher-unlock options).
_MAX_STEP = max(_STEP_POINTS)


class UniqueStatOption(NamedTuple):
    """One row from HeroUniqueStatOptionTable.json.

    bonus_at(level) returns (base_value + added_value * level) / 10, matching
    the in-game display where datamine raw integers are tenths-of-a-percent.
    """
    key: str            # snake_case stat key used in CharacterState
    display_name: str   # user-facing label
    base_value: int     # raw value at level 1 (before /10)
    added_value: int    # raw value added per level (before /10)
    max_level: int      # max investment level
    point_cost: int     # unique stat points per level
    unlock_level: int   # character level required to allocate into this stat
    is_flat: bool       # True = flat stat (no % suffix), False = percentage

    def bonus_at(self, level: int) -> float:
        if level <= 0:
            return 0.0
        return (self.base_value + self.added_value * level) / 10


# HeroUniqueStatOptionTable.json - one entry per unique stat slot.
# Order matches StatIndex 1..11 in the datamine.
UNIQUE_STAT_OPTIONS: List[UniqueStatOption] = [
    UniqueStatOption("attack_speed",  "Attack Speed",       30,  2, 20, 1, 10,  False),
    UniqueStatOption("crit_chance",   "Crit Chance",        50,  5, 10, 1, 20,  False),
    UniqueStatOption("min_damage",    "Min Damage",         50,  3, 20, 1, 25,  False),
    UniqueStatOption("max_damage",    "Max Damage",         50,  3, 20, 1, 35,  False),
    UniqueStatOption("hit_chance",    "Hit Chance / Accuracy", 3,  1, 20, 2, 45,  False),
    UniqueStatOption("crit_power",    "Crit Power",         50,  5, 30, 1, 55,  False),
    UniqueStatOption("normal_damage", "Normal Monster Dmg", 50,  5, 30, 1, 65,  False),
    UniqueStatOption("boss_damage",   "Boss Damage",        50,  5, 30, 1, 65,  False),
    UniqueStatOption("skill_power",   "Skill Power",       100,  5, 30, 1, 75,  False),
    UniqueStatOption("attack_power",  "Attack Power",      100,  5, 50, 1, 85,  False),
    UniqueStatOption("main_stat",     "Main Stat",         300,  5, 160, 1, 100, True),
]


def stat_step_for_level(character_level: int) -> int:
    """StatStep covered by a character at the given level."""
    if character_level < 5:
        return 0
    return character_level // 5


def available_unique_stat_points(character_level: int) -> int:
    """Total unique stat points earned by a character at the given level.

    Cumulative sum of AddUniqueStatCount across every StatStep the character
    has reached. Cap at the datamine's max step — levels above 5*MAX_STEP do
    not award additional points.
    """
    step = min(stat_step_for_level(character_level), _MAX_STEP)
    return sum(_STEP_POINTS.get(s, 0) for s in range(1, step + 1))


def points_spent(allocations: Dict[str, int]) -> int:
    """Total unique stat points spent given a {key: level} allocation map."""
    by_key = {opt.key: opt for opt in UNIQUE_STAT_OPTIONS}
    return sum(
        by_key[k].point_cost * lv
        for k, lv in allocations.items()
        if k in by_key and lv > 0
    )


# Unique stat keys that don't affect our DPS model and therefore shouldn't
# absorb points during auto-allocation. Hit Chance is in the datamine table
# but our DPS calc has no accuracy/evasion term — points there would silently
# vanish. Keeping this configurable so future "real" stats can plug in.
SKIP_FOR_DPS: set = {"hit_chance"}


def auto_allocate(character_level: int) -> Dict[str, int]:
    """Distribute the character's earned unique stat points greedily in unlock
    order: each option is maxed before any points spill into the next one.

    Skips options the character hasn't reached the unlock level for AND skips
    options in SKIP_FOR_DPS (currently Hit Chance), since allocating into a
    stat the DPS model can't read just wastes the points.

    Returns a {key: level} map for every option in UNIQUE_STAT_OPTIONS — keys
    that received nothing map to 0.
    """
    remaining = available_unique_stat_points(character_level)
    out: Dict[str, int] = {opt.key: 0 for opt in UNIQUE_STAT_OPTIONS}
    for opt in UNIQUE_STAT_OPTIONS:
        if opt.key in SKIP_FOR_DPS:
            continue
        if character_level < opt.unlock_level or remaining <= 0:
            continue
        affordable_levels = remaining // opt.point_cost
        allocated = min(opt.max_level, affordable_levels)
        out[opt.key] = allocated
        remaining -= allocated * opt.point_cost
    return out
