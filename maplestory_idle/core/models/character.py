"""
CharacterModel — canonical, typed representation of a character's stats.

This is the unified replacement for three overlapping structures:
  - CharacterState (skills.py, 43 fields) — the DPS calculator's input
  - CharacterStats (core/stats.py, 16 fields) — the old aggregation result
  - aggregate_stats() dict (dps_calculator.py) — ~54 raw dict keys

Phase 2: CharacterModel is used as the output of aggregate_stats().
Phase 3: CharacterModel replaces CharacterState inside skills.py/DPSCalculator.

Unit convention (enforced by validators):
  All percentage stats are 0-100 space. The /100 division happens exactly once,
  inside core/damage.py formula functions.

List sources (final_damage_sources, def_pen_sources, attack_speed_sources) are
collapsed to scalars during aggregation — one place, clean interface.
"""

from __future__ import annotations

from typing import Dict, Optional, Set
from pydantic import BaseModel, Field

# JobClass imported inline in methods to avoid circular imports during Phase 2-3.
# CharacterModel lives here; skills.py is imported by DPSCalculator separately.


class CharacterModel(BaseModel):
    """
    All stats needed to run a DPS calculation, as a single typed object.

    Populated by aggregate_stats() in dps_calculator.py.
    Consumed by DPSCalculator (Phase 3) and calculate_dps() wrapper.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    job_class: str = "bowmaster"    # JobClass enum value — kept as str to avoid circular import
    level: int = 100

    # ── Attack ────────────────────────────────────────────────────────────────
    attack_flat: float = 0.0        # Total attack value (was 'attack' in CharacterState)
    attack_pct: float = 0.0         # % attack bonus from potentials

    # ── Main stat ─────────────────────────────────────────────────────────────
    # Job-agnostic names; get_main_stat_name(job_class) resolves to DEX/LUK/STR/INT
    main_stat_flat: float = 0.0
    main_stat_pct: float = 0.0
    main_stat_conversion: float = 0.0      # e.g. Shield Mastery flat DEX added post-%

    # ── Secondary stat ────────────────────────────────────────────────────────
    secondary_stat_flat: float = 0.0
    secondary_stat_pct: float = 0.0
    secondary_stat_conversion: float = 0.0

    # ── Damage % ──────────────────────────────────────────────────────────────
    damage_pct: float = 0.0
    boss_damage: float = 0.0            # was boss_damage_pct in CharacterState
    normal_damage: float = 0.0          # was normal_damage_pct
    skill_damage: float = 0.0           # was skill_damage_pct
    basic_attack_damage: float = 0.0    # was basic_attack_dmg_pct
    damage_amp: float = 0.0             # Scroll damage amplification %

    # ── Final Damage (scalar, 0-100) ──────────────────────────────────────────
    # Multiplicative sources pre-combined: value = (∏(1 + src/100) − 1) × 100
    # DPS calc uses: fd_mult = 1 + final_damage_pct / 100
    # Skill-based FD (Shadow Shifter, Smokescreen etc.) is added dynamically in DPSCalculator.
    final_damage_pct: float = 0.0

    # Additive % bonus from target debuffs (Venom Weaken, Coin/Peach artifacts).
    # Applied as an extra multiplicative source: final_mult *= (1 + correction/100)
    final_damage_correction: float = 0.0

    # ── Crit ──────────────────────────────────────────────────────────────────
    crit_rate: float = Field(0.0, ge=0, le=100)
    crit_damage: float = 0.0       # bonus crit dmg % excluding base 30% (see BASE_CRIT_DMG)

    # ── Defense Pen (scalar, 0-100) ───────────────────────────────────────────
    # Multiplicative sources pre-combined: value = (1 − remaining) × 100
    # was 'defense_pen' in CharacterState (0-1 decimal there — UNIT BUG fixed here)
    def_pen_pct: float = 0.0

    # ── Attack Speed (scalar, 0-100) ──────────────────────────────────────────
    # Diminishing-returns pre-combined across all sources
    attack_speed_pct: float = 0.0

    # ── Min/Max Damage ────────────────────────────────────────────────────────
    min_dmg_mult: float = 0.0      # % bonus to minimum damage roll
    max_dmg_mult: float = 0.0      # % bonus to maximum damage roll

    # ── Skill bonuses ─────────────────────────────────────────────────────────
    all_skills_bonus: int = 0
    skill_1st_bonus: int = 0
    skill_2nd_bonus: int = 0
    skill_3rd_bonus: int = 0
    skill_4th_bonus: int = 0
    skill_cd_reduction: float = 0.0     # flat seconds (hat special potential)

    # Base skill levels dict (skill_name -> base_level).
    # Effective level = base + job_skill_points + all_skills_bonus + job_equipment_bonus
    skill_levels: Dict[str, int] = Field(default_factory=dict)

    # Set of buff skills explicitly toggled off (runtime state, not persisted)
    enabled_buffs: Set[str] = Field(default_factory=set)

    # ── Combat config ─────────────────────────────────────────────────────────
    ba_target_bonus: int = 0        # bonus Basic Attack target count
    buff_duration: float = 0.0      # % buff duration bonus (affects buff uptime)

    # ── Unique stat levels ────────────────────────────────────────────────────
    unique_attack_speed_level: int = 0
    unique_crit_chance_level: int = 0
    unique_min_damage_level: int = 0
    unique_max_damage_level: int = 0
    unique_crit_power_level: int = 0
    unique_normal_damage_level: int = 0
    unique_boss_damage_level: int = 0
    unique_skill_power_level: int = 0
    unique_attack_power_level: int = 0
    unique_main_stat_level: int = 0

    # ── Misc ──────────────────────────────────────────────────────────────────
    hex_multiplier: float = 1.0
    hex_necklace_stars: int = 0
    book_of_ancient_stars: int = 0
    accuracy: float = 0.0
    total_main_stat_adjustment: float = 0.0
    total_attack_adjustment: float = 0.0

    # ── Methods ───────────────────────────────────────────────────────────────

    def get_effective_skill_cooldown(self, base_cd: float, percent_reduction: float = 0) -> float:
        """Apply hat CD reduction to a skill's base cooldown."""
        from cooldown_calc import calculate_effective_cooldown
        return calculate_effective_cooldown(base_cd, percent_reduction, self.skill_cd_reduction)

    def to_character_state_kwargs(self) -> Dict:
        """
        Build kwargs dict for populating a CharacterState from this model.
        Used as the migration bridge during Phase 2 until Phase 3 removes CharacterState.

        Both CharacterState.final_damage_pct and CharacterState.def_pen_pct are 0-100 space,
        matching CharacterModel — no unit conversion needed.
        """
        return {
            "level": self.level,
            "all_skills_bonus": self.all_skills_bonus,
            "attack": self.attack_flat,
            "main_stat_flat": self.main_stat_flat,
            "main_stat_pct": self.main_stat_pct,
            "main_stat_conversion": self.main_stat_conversion,
            "secondary_stat_flat": self.secondary_stat_flat,
            "secondary_stat_pct": self.secondary_stat_pct,
            "damage_pct": self.damage_pct,
            "boss_damage": self.boss_damage,
            "normal_damage": self.normal_damage,
            "crit_rate": self.crit_rate,
            "crit_damage": self.crit_damage,
            "min_dmg_mult": self.min_dmg_mult,
            "max_dmg_mult": self.max_dmg_mult,
            "skill_damage": self.skill_damage,
            "basic_attack_damage": self.basic_attack_damage,
            "final_damage_pct": self.final_damage_pct,
            "def_pen_pct": self.def_pen_pct,
            "attack_speed_pct": self.attack_speed_pct,
            "ba_target_bonus": self.ba_target_bonus,
            "skill_1st_bonus": self.skill_1st_bonus,
            "skill_2nd_bonus": self.skill_2nd_bonus,
            "skill_3rd_bonus": self.skill_3rd_bonus,
            "skill_4th_bonus": self.skill_4th_bonus,
            "skill_cd_reduction": self.skill_cd_reduction,
            "unique_attack_speed_level": self.unique_attack_speed_level,
            "unique_crit_chance_level": self.unique_crit_chance_level,
            "unique_min_damage_level": self.unique_min_damage_level,
            "unique_max_damage_level": self.unique_max_damage_level,
            "unique_crit_power_level": self.unique_crit_power_level,
            "unique_normal_damage_level": self.unique_normal_damage_level,
            "unique_boss_damage_level": self.unique_boss_damage_level,
            "unique_skill_power_level": self.unique_skill_power_level,
            "unique_attack_power_level": self.unique_attack_power_level,
            "unique_main_stat_level": self.unique_main_stat_level,
        }
