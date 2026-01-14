"""
MapleStory Idle - Unified Calculator App
=========================================
Combines Damage Calculator and Cube Tools in one tabbed interface.
Cube rolls are integrated with damage calculator to show real DPS impact.

Features:
- Tab 1: Damage Calculator with stat optimization
- Tab 2: Cube Simulator with pity tracking (integrated with damage calc)
- Tab 3: Cube Cost Calculator
- Tab 4: Cube Optimizer (which equipment to cube for best DPS)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Tuple, Optional
import random
import csv
import os

from cubes import (
    PotentialTier, CubeType, StatType, CubeSimulator, PotentialLine,
    TIER_UP_RATES, REGULAR_PITY, BONUS_PITY, SLOT_YELLOW_RATES,
    POTENTIAL_STATS, SPECIAL_POTENTIALS, SPECIAL_POTENTIAL_RATE,
    CUBE_PRICES, STAT_TIER_RANKINGS,
    calculate_expected_cubes_to_tier, calculate_realistic_cubes_to_tier,
    calculate_cost_to_tier, calculate_prob_hit_stat_in_n_cubes,
    get_stat_display_name, get_tier_color, format_line,
    PotentialRollScorer, simulate_n_cubes_keep_best, format_simulation_result,
    # New enhanced cube recommendation system
    ItemScoreResult, ExpectedCubesMetrics, EnhancedCubeRecommendation,
    create_item_score_result, calculate_expected_cubes_to_improve,
    calculate_expected_cubes_fast, clear_roll_distribution_cache,
    calculate_stat_rankings, detect_diminishing_returns,
    calculate_efficiency_score,
    # Combat mode for BA Targets valuation
    CombatMode, BA_TARGETS_MODE_MULTIPLIER,
)
from equipment import (
    EquipmentItem, EQUIPMENT_SLOTS as EQUIPMENT_SLOTS_LIST,
    STARFORCE_TABLE, get_amplify_multiplier, calculate_base_stat,
    calculate_starforce_expected_cost, SLOT_THIRD_MAIN_STAT
)
from skills import (
    calculate_all_skills_value, calculate_all_skills_value_by_job,
    Job, JobSkillBonus, calculate_job_skill_value,
    get_global_mastery_stats, BOWMASTER_SKILLS, SkillType,
    DPSCalculator, create_character_at_level,
)
from starforce_optimizer import (
    find_optimal_strategy, find_optimal_per_stage_strategy,
    calculate_total_cost_markov,
    MESO_TO_DIAMOND, SCROLL_DIAMOND_COST, DESTRUCTION_FEE_DIAMONDS
)
from hero_power import (
    HeroPowerTier, HeroPowerStatType, HeroPowerLine, HeroPowerConfig,
    HeroPowerPassiveStatType, HeroPowerPassiveConfig, HERO_POWER_PASSIVE_STATS,
    PASSIVE_STAT_DISPLAY_NAMES, create_default_passive_config, create_maxed_passive_config,
    SimulationTarget, HeroPowerSimulationResult,
    HERO_POWER_REROLL_COSTS, HERO_POWER_TIER_RATES, HERO_POWER_STAT_RANGES,
    STAT_DISPLAY_NAMES, TIER_COLORS, VALUABLE_STATS,
    simulate_hero_power_reroll, check_target_achieved, run_custom_target_simulation,
    HeroPowerLevelConfig, create_default_level_config, score_hero_power_line, get_line_score_category,
    STAT_DPS_WEIGHTS, TIER_SCORE_MULTIPLIERS
)
from upgrade_optimizer import (
    UpgradeOptimizer, UpgradeOption, UpgradePath, UpgradeType, EquipmentSummary
)
from artifacts import (
    ArtifactTier, PotentialTier as ArtifactPotentialTier,
    ArtifactDefinition, ArtifactInstance, ArtifactConfig, ArtifactPotentialLine,
    ARTIFACTS, POTENTIAL_TIER_RATES as ARTIFACT_POTENTIAL_RATES,
    POTENTIAL_VALUES as ARTIFACT_POTENTIAL_VALUES, POTENTIAL_SLOT_UNLOCKS,
    ARTIFACT_DROP_RATES, ARTIFACT_TIER_DROP_RATES, ARTIFACT_CHEST_COSTS,
    SYNTHESIS_COSTS, TOTAL_DUPLICATES_TO_STAR, AWAKENING_COSTS,
    calculate_hex_multiplier, calculate_book_of_ancient_bonus, calculate_fire_flower_fd,
    calculate_expected_rolls as calculate_artifact_expected_rolls, create_artifact_instance,
    calculate_expected_chests_for_artifact, calculate_chests_for_max_star,
    calculate_synthesis_cost, calculate_specific_legendary_cost, calculate_artifact_upgrade_efficiency
)
from weapons import (
    WeaponRarity, WeaponDefinition, WeaponInstance, WeaponConfig,
    RARITY_COLORS as WEAPON_RARITY_COLORS, MAX_LEVELS as WEAPON_MAX_LEVELS,
    calculate_weapon_atk, create_weapon_instance, get_rarity_color
)
from guild import (
    GuildConfig, GuildSkillType, GUILD_SKILL_DATA, SKILL_DISPLAY_NAMES as GUILD_SKILL_NAMES
)
from companions import (
    CompanionConfig, CompanionInstance, CompanionDefinition, CompanionJob,
    JobAdvancement, OnEquipStatType, COMPANIONS, create_companion_instance,
    create_full_companion_inventory
)
# Note: passives.py is deprecated - passive skills are now calculated from skills.py
# The skills.py module has accurate skill data including PASSIVE_STAT skills and mastery bonuses
from maple_rank import (
    MapleRankConfig, MapleRankStatType, MAPLE_RANK_STATS, MAIN_STAT_SPECIAL,
    STAT_DISPLAY_NAMES as MAPLE_RANK_STAT_NAMES, get_main_stat_per_point,
    get_stage_main_stat_table, get_max_maple_rank_stats
)
from equipment_sets import (
    MedalConfig, CostumeConfig, EquipmentSetsConfig,
    MEDAL_INVENTORY_EFFECT, COSTUME_INVENTORY_EFFECT
)
from stat_efficiency_guide import (
    StatCategory, SystemType, StatEfficiency, SlotRecommendation,
    MAX_STAT_VALUES, EQUIPMENT_SLOT_RECOMMENDATIONS, STAT_INSIGHTS,
    get_stat_rankings, get_system_priorities, get_priority_slots,
)
from constants import ENEMY_DEFENSE_VALUES


# =============================================================================
# EQUIPMENT SLOTS THAT CAN BE CUBED
# =============================================================================

EQUIPMENT_SLOTS = [
    "hat", "top", "bottom", "gloves", "shoes",
    "belt", "shoulder", "cape", "ring", "necklace", "face"
]

# Default save files (in same directory as script)
POTENTIALS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "potentials_save.csv")
EQUIPMENT_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equipment_save.csv")
HERO_POWER_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hero_power_save.csv")
HERO_POWER_PRESETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hero_power_presets.csv")
HERO_POWER_PASSIVE_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hero_power_passive_save.csv")
HERO_POWER_LEVEL_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hero_power_level_save.csv")
ARTIFACTS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts_save.csv")
WEAPONS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weapons_save.csv")
COMPANIONS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "companions_save.csv")
MAPLE_RANK_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maple_rank_save.csv")
RESONANCE_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resonance_save.csv")
EQUIPMENT_SETS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equipment_sets_save.csv")
MANUAL_ADJUSTMENTS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_adjustments_save.csv")
ACTUAL_STATS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "actual_stats_save.csv")
CHARACTER_SETTINGS_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "character_settings_save.csv")


# =============================================================================
# DAMAGE CALCULATION
# =============================================================================

DAMAGE_AMP_DIVISOR = 396.5
HEX_MULTIPLIER = 1.24


def calculate_ba_percent_of_dps(level: int, all_skills_bonus: int = 0) -> float:
    """
    Calculate what percentage of total DPS comes from Basic Attack.

    Uses the skill DPS calculator to get an accurate breakdown.

    Args:
        level: Character level (affects which basic attack skill is used)
        all_skills_bonus: +All Skills bonus from equipment

    Returns:
        Percentage of total DPS from basic attack (e.g., 35.5 for 35.5%)
    """
    char = create_character_at_level(level, all_skills_bonus)
    # Set reasonable default stats for the calculation
    char.attack = 1000
    char.main_stat_pct = 50
    char.damage_pct = 30
    char.boss_damage_pct = 20
    char.crit_rate = 70
    char.crit_damage = 200
    char.attack_speed_pct = 50

    calc = DPSCalculator(char)
    result = calc.calculate_total_dps()

    if result.total_dps > 0:
        return (result.basic_attack_dps / result.total_dps) * 100
    return 40.0  # Fallback to estimate if calculation fails


def calculate_damage(
    base_atk: float,
    dex_flat: float,
    dex_percent: float,
    damage_percent: float,
    hex_stacks: int,
    damage_amp: float,
    final_damage_sources: list,
    crit_damage: float,
    defense_pen: float,
    enemy_def: float,
    boss_damage: float,
    min_dmg_mult: float = 0,
    max_dmg_mult: float = 0,
    attack_speed: float = 0,
    normal_damage: float = 0,
    combat_mode: str = "stage",
) -> Dict[str, float]:
    """Calculate damage with full breakdown.

    Args:
        min_dmg_mult: Min damage multiplier % (e.g., 264 for 264%)
        max_dmg_mult: Max damage multiplier % (e.g., 294 for 294%)
        attack_speed: Attack speed % (e.g., 103.5 for 103.5%)
        normal_damage: Normal monster damage % bonus
        combat_mode: "stage" (60% normal, 40% boss), "boss", or "world_boss" (100% boss)

    The min/max damage multipliers affect the damage range.
    Average damage = base × (1 + (min% + max%) / 200)
    For the priority chart, we use the average multiplier.

    Attack speed directly scales DPS - more attacks per second = more damage.
    """
    total_dex = dex_flat * (1 + dex_percent / 100)
    # Every 100 DEX = 1% damage → 70,000 DEX = 700% = 8x multiplier (1 + 7)
    stat_multiplier = 1 + (total_dex / 10000)  # /100 for %, /100 again for decimal

    hex_mult = HEX_MULTIPLIER ** min(hex_stacks, 3)
    total_damage_percent = (damage_percent / 100) * hex_mult

    # Combat mode determines how normal% and boss% affect damage
    # Normal damage% is a MULTIPLIER vs normal monsters
    # Boss damage% is a MULTIPLIER vs boss monsters
    # Stage: 60% normal monsters, 40% bosses - weighted average of two separate calculations
    # Boss/World Boss: 100% boss damage

    # Base damage multiplier (from damage%)
    base_damage_mult = 1 + total_damage_percent

    if combat_mode in ("boss", "world_boss"):
        # 100% boss - apply boss damage multiplier
        damage_multiplier = base_damage_mult * (1 + boss_damage / 100)
    else:
        # Stage mode: weighted average of DPS vs normals and DPS vs bosses
        # DPS vs normals = base × (1 + normal_damage%)
        # DPS vs bosses = base × (1 + boss_damage%)
        # Total = 60% × DPS_normal + 40% × DPS_boss
        normal_weight = 0.60
        boss_weight = 0.40
        mult_vs_normal = base_damage_mult * (1 + normal_damage / 100)
        mult_vs_boss = base_damage_mult * (1 + boss_damage / 100)
        damage_multiplier = (normal_weight * mult_vs_normal) + (boss_weight * mult_vs_boss)

    amp_multiplier = 1 + (damage_amp / DAMAGE_AMP_DIVISOR)

    fd_multiplier = 1.0
    for fd in final_damage_sources:
        fd_multiplier *= (1 + fd / 100)

    # Crit damage baseline is 30%, input is bonus on top of that
    # e.g., +200% crit damage bonus → total crit damage = 230%
    # Crit multiplier = 1 + total_crit_damage/100 = 1 + 2.30 = 3.30x
    BASE_CRIT_DAMAGE = 30.0  # Baseline crit damage %
    total_crit_damage = BASE_CRIT_DAMAGE + crit_damage
    crit_multiplier = 1 + (total_crit_damage / 100)

    def_pen_decimal = defense_pen / 100
    defense_multiplier = 1 / (1 + enemy_def * (1 - def_pen_decimal))

    # Min/Max damage multiplier - affects the damage range
    # Baseline values: min = 60%, max = 100% (average = 80%)
    # Input values are BONUS percentages added to baseline
    # e.g., +204.3% min bonus → final min = 264.3%
    # e.g., +193.7% max bonus → final max = 293.7%
    # For DPS calculation, use average of (baseline + bonus)
    BASE_MIN_DMG = 60.0  # Baseline min damage %
    BASE_MAX_DMG = 100.0  # Baseline max damage %
    final_min = BASE_MIN_DMG + min_dmg_mult
    final_max = BASE_MAX_DMG + max_dmg_mult
    avg_mult = (final_min + final_max) / 2
    dmg_range_mult = avg_mult / 100  # 279% → 2.79x (with bonuses), 80% → 0.8x (baseline)

    # Attack speed multiplier - directly scales DPS
    # Input is the BONUS percentage (e.g., 3.5 for +3.5% attack speed)
    # 0% bonus = baseline (1.0x), 3.5% bonus = 1.035x DPS
    atk_spd_mult = 1.0
    if attack_speed > 0:
        atk_spd_mult = 1 + (attack_speed / 100)  # 3.5% → 1.035x

    total = (base_atk * stat_multiplier * damage_multiplier *
             amp_multiplier * fd_multiplier * crit_multiplier * defense_multiplier *
             dmg_range_mult * atk_spd_mult)

    return {
        "total": total,
        "stat_mult": stat_multiplier,
        "damage_mult": damage_multiplier,
        "amp_mult": amp_multiplier,
        "fd_mult": fd_multiplier,
        "crit_mult": crit_multiplier,
        "def_mult": defense_multiplier,
        "dmg_range_mult": dmg_range_mult,
        "atk_spd_mult": atk_spd_mult,
        "total_dex": total_dex,
        "effective_damage_pct": total_damage_percent * 100,
    }


# =============================================================================
# CANVAS CHARTS
# =============================================================================

class BarChart:
    """Simple horizontal bar chart using tkinter Canvas."""

    def __init__(self, parent, width=380, height=200):
        self.width = width
        self.height = height
        self.bar_height = 28
        self.padding = 10
        self.label_width = 100

        self.canvas = tk.Canvas(parent, width=width, height=height,
                                bg='#1a1a2e', highlightthickness=0)
        self.canvas.pack(pady=5)

    def update(self, data: List[Tuple[str, float, str]]):
        self.canvas.delete("all")
        if not data:
            return

        max_val = max(d[1] for d in data) if data else 1
        bar_area_width = self.width - self.label_width - self.padding * 2
        data = sorted(data, key=lambda x: x[1], reverse=True)

        for i, (label, value, color) in enumerate(data):
            y = self.padding + i * (self.bar_height + 5)
            self.canvas.create_text(
                self.label_width - 5, y + self.bar_height // 2,
                text=label, anchor=tk.E, fill='#ccc', font=('Segoe UI', 9)
            )
            self.canvas.create_rectangle(
                self.label_width, y,
                self.label_width + bar_area_width, y + self.bar_height,
                fill='#2a2a4e', outline=''
            )
            bar_width = (value / max_val) * bar_area_width if max_val > 0 else 0
            self.canvas.create_rectangle(
                self.label_width, y,
                self.label_width + bar_width, y + self.bar_height,
                fill=color, outline=''
            )
            self.canvas.create_text(
                self.label_width + bar_width + 5, y + self.bar_height // 2,
                text=f"+{value:.2f}%", anchor=tk.W, fill='white',
                font=('Consolas', 9, 'bold')
            )


class PityBar:
    """Visual pity progress bar."""

    def __init__(self, parent, width=300, height=30):
        self.width = width
        self.height = height
        self.canvas = tk.Canvas(parent, width=width, height=height,
                                bg='#1a1a2e', highlightthickness=0)
        self.canvas.pack(pady=5)

    def update(self, current: int, maximum: int, tier_color: str = "#ffd700"):
        self.canvas.delete("all")

        self.canvas.create_rectangle(0, 5, self.width, self.height - 5,
                                     fill='#2a2a4e', outline='#444')

        progress = min(current / maximum, 1.0) if maximum > 0 else 0
        bar_width = progress * self.width
        self.canvas.create_rectangle(0, 5, bar_width, self.height - 5,
                                     fill=tier_color, outline='')

        self.canvas.create_text(self.width // 2, self.height // 2,
                               text=f"{current} / {maximum} ({progress*100:.1f}%)",
                               fill='white', font=('Consolas', 10, 'bold'))


# =============================================================================
# EQUIPMENT POTENTIAL STATE
# =============================================================================

class EquipmentPotential:
    """Tracks potential lines for a piece of equipment."""

    def __init__(self, slot: str, tier: PotentialTier = PotentialTier.LEGENDARY):
        self.slot = slot
        self.tier = tier
        self.bonus_tier = tier  # Bonus potential tier (separate from regular)
        self.lines: List[PotentialLine] = []
        self.bonus_lines: List[PotentialLine] = []
        # Pity counters for tier-up tracking
        self.regular_pity: int = 0   # Cubes used since last regular tier-up
        self.bonus_pity: int = 0     # Cubes used since last bonus tier-up

    def get_stat_contribution(self, stat_type: StatType) -> float:
        """Get total contribution of a stat type from all lines."""
        total = 0.0
        for line in self.lines + self.bonus_lines:
            if line.stat_type == stat_type:
                total += line.value
        return total

    def get_all_stats(self) -> Dict[StatType, float]:
        """Get all stat contributions."""
        stats = {}
        for line in self.lines + self.bonus_lines:
            if line.stat_type not in stats:
                stats[line.stat_type] = 0.0
            stats[line.stat_type] += line.value
        return stats


# =============================================================================
# MAIN APP
# =============================================================================

class MapleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MapleStory Idle - Complete Calculator")
        self.root.geometry("1350x900")
        self.root.configure(bg='#1a1a2e')

        # Equipment potential state (tracks all equipment potentials)
        self.equipment: Dict[str, EquipmentPotential] = {}
        for slot in EQUIPMENT_SLOTS:
            self.equipment[slot] = EquipmentPotential(slot)

        # Equipment items state (tracks stats for equipment/starforce tab)
        self.equipment_items: Dict[str, EquipmentItem] = {}
        for slot in EQUIPMENT_SLOTS:
            self.equipment_items[slot] = EquipmentItem(slot)

        # Character state for skill calculations
        self.character_level = 100  # Default level
        self.current_all_skills = 44  # Current +All Skills from equipment (excluding cube lines)
        self._cached_all_skills_value = None  # Cache for dynamic All Skills value
        self.combat_mode = CombatMode.STAGE  # Default: mixed stage clearing + boss

        # Hero Power state
        self.hero_power_config = HeroPowerConfig()
        self.hero_power_passive_config = HeroPowerPassiveConfig()  # Passive stats (leveled, not rerolled)
        self.hero_power_level_config = HeroPowerLevelConfig()  # Level-based tier rates and costs
        self.hero_power_presets: Dict[str, HeroPowerConfig] = {}
        self.hero_power_line_widgets: Dict[int, Dict] = {}  # slot -> {stat_var, value_var, tier_var, lock_var}
        self.hero_power_passive_widgets: Dict[HeroPowerPassiveStatType, Dict] = {}  # passive stat -> {var, label}
        self.hero_power_level_widgets: Dict[str, tk.StringVar] = {}  # level config field -> var

        # Artifacts state
        self.artifact_config = ArtifactConfig()
        self.artifact_slot_widgets: Dict[int, Dict] = {}  # slot 0-2 -> {artifact_var, stars_var, widgets}
        self.artifact_inventory_widgets: Dict[str, Dict] = {}  # artifact_key -> {stars_var, potential_vars}

        # Resonance state (manual override values)
        self.resonance_stars_var = tk.StringVar(value="0")
        self.resonance_main_stat_var = tk.StringVar(value="0")
        self.resonance_hp_var = tk.StringVar(value="0")
        self.resonance_level_var = tk.StringVar(value="0")

        # Weapons state
        self.weapon_config = WeaponConfig()
        self.weapon_inventory_widgets: List[Dict] = []  # list of weapon row widgets

        # Guild state
        self.guild_config = GuildConfig()

        # Companions state
        self.companion_config = CompanionConfig()

        # Note: Passive skills are now calculated dynamically from skills.py
        # using character_level and current_all_skills (no passive_config needed)

        # Maple Rank state
        self.maple_rank_config = MapleRankConfig()

        # Equipment Sets (Medals & Costumes) state
        self.equipment_sets_config = EquipmentSetsConfig()

        # Manual stat adjustments (for fine-tuning when calculated stats don't match in-game)
        self.manual_stat_adjustments = {
            "dex_flat": 0.0,
            "dex_percent": 0.0,
            "damage_percent": 0.0,
            "boss_damage": 0.0,
            "crit_damage": 0.0,
            "crit_rate": 0.0,
            "defense_pen": 0.0,
            "final_damage": 0.0,
            "attack_flat": 0.0,
            "attack_speed": 0.0,
            "min_dmg_mult": 0.0,
            "max_dmg_mult": 0.0,
            "normal_damage": 0.0,
            "skill_damage": 0.0,
        }
        self.manual_stat_vars = {}  # Will hold StringVars for UI

        # DPS calculation mode toggle
        # False = Simple formula (fast, approximate)
        # True = Skill-based (accurate, includes skill CD reduction effects)
        self.use_skill_based_dps = tk.BooleanVar(value=False)

        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='#1a1a2e')
        style.configure('TNotebook.Tab', background='#2a2a4e', foreground='#ccc',
                       padding=[15, 5], font=('Segoe UI', 10))
        style.map('TNotebook.Tab', background=[('selected', '#4a4a6a')],
                 foreground=[('selected', '#ffd700')])
        style.configure('TFrame', background='#1a1a2e')
        style.configure('TScale', background='#1a1a2e')
        style.configure('TLabel', background='#1a1a2e', foreground='#eee')

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.damage_tab = ttk.Frame(self.notebook)
        self.simulator_tab = ttk.Frame(self.notebook)
        self.cost_tab = ttk.Frame(self.notebook)
        self.optimizer_tab = ttk.Frame(self.notebook)
        self.equipment_tab = ttk.Frame(self.notebook)
        self.starforce_tab = ttk.Frame(self.notebook)
        self.hero_power_tab = ttk.Frame(self.notebook)
        self.artifacts_tab = ttk.Frame(self.notebook)
        self.weapons_tab = ttk.Frame(self.notebook)
        self.companions_tab = ttk.Frame(self.notebook)
        self.maple_rank_tab = ttk.Frame(self.notebook)
        self.character_stats_tab = ttk.Frame(self.notebook)
        self.upgrade_optimizer_tab = ttk.Frame(self.notebook)
        self.stat_efficiency_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.damage_tab, text="  Damage Calculator  ")
        self.notebook.add(self.simulator_tab, text="  Cube Simulator  ")
        self.notebook.add(self.cost_tab, text="  Cube Cost Calculator  ")
        self.notebook.add(self.optimizer_tab, text="  Cube Optimizer  ")
        self.notebook.add(self.equipment_tab, text="  Equipment  ")
        self.notebook.add(self.starforce_tab, text="  Starforce  ")
        self.notebook.add(self.hero_power_tab, text="  Hero Power  ")
        self.notebook.add(self.artifacts_tab, text="  Artifacts  ")
        self.notebook.add(self.weapons_tab, text="  Weapons  ")
        self.notebook.add(self.companions_tab, text="  Companions  ")
        self.notebook.add(self.maple_rank_tab, text="  Maple Rank  ")
        self.notebook.add(self.character_stats_tab, text="  Character Stats  ")
        self.notebook.add(self.upgrade_optimizer_tab, text="  Upgrade Path  ")
        self.notebook.add(self.stat_efficiency_tab, text="  Stat Guide  ")

        # Build each tab
        self.build_damage_tab()
        self.build_simulator_tab()
        self.build_cost_tab()
        self.build_optimizer_tab()
        self.build_equipment_tab()
        self.build_starforce_tab()
        self.build_hero_power_tab()
        self.build_artifacts_tab()
        self.build_weapons_tab()
        self.build_companions_tab()
        self.build_maple_rank_tab()
        self.build_character_stats_tab()
        self.build_upgrade_optimizer_tab()
        self.build_stat_efficiency_tab()

        # Auto-load from save files if they exist
        self.auto_load_potentials()
        self.auto_load_equipment()
        self.auto_load_artifacts()
        self.auto_load_resonance()
        self.auto_load_weapons()
        self.auto_load_hero_power()
        self.auto_load_hero_power_passive()
        self.auto_load_hero_power_level()
        self.auto_load_companions()
        self.auto_load_maple_rank()
        self.auto_load_equipment_sets()
        self.load_manual_adjustments()

    def auto_load_equipment_sets(self):
        """Auto-load equipment sets (medals & costumes) from default save file if it exists."""
        if os.path.exists(EQUIPMENT_SETS_SAVE_FILE):
            try:
                self.load_equipment_sets_from_csv(EQUIPMENT_SETS_SAVE_FILE, silent=True)
            except Exception:
                pass  # Silent fail

    # =========================================================================
    # POTENTIAL -> DAMAGE STAT MAPPING
    # =========================================================================

    def get_all_skills_dps_value(self) -> float:
        """
        Calculate the DPS value of +1 All Skills based on character level and current stats.
        Uses skills.py DPS calculator for accurate calculation.
        Returns percentage DPS increase per +1 All Skills.
        """
        if self._cached_all_skills_value is not None:
            return self._cached_all_skills_value

        # Get base stats from damage calculator for accurate calculation
        try:
            base_stats = self._get_base_stats() if hasattr(self, '_sliders_ready') and self._sliders_ready else {}
            value, _ = calculate_all_skills_value(
                level=self.character_level,
                current_all_skills=self.current_all_skills,
                attack=base_stats.get("base_atk", 50000),
                crit_rate=70,  # Assume reasonable crit rate
                crit_damage=base_stats.get("crit_damage", 200),
                attack_speed_pct=50,  # Assume moderate attack speed
            )
            self._cached_all_skills_value = value
        except Exception:
            # Fallback to hardcoded value if calculation fails
            self._cached_all_skills_value = 0.68

        return self._cached_all_skills_value

    def invalidate_all_skills_cache(self):
        """Call this when character level or All Skills changes."""
        self._cached_all_skills_value = None

    def get_potential_stats_total(self) -> Dict[str, any]:
        """
        Calculate total stats from all equipment potentials.
        Returns dict mapping to damage calc stat names.

        All Skills Level is converted to DPS using the skill DPS calculator.
        Value varies based on character level and current +All Skills.

        IMPORTANT: Final Damage lines are returned as a LIST of individual values
        because each FD line is MULTIPLICATIVE with every other FD line.
        """
        # Get dynamic All Skills value from skill DPS calculator
        all_skills_to_dps = self.get_all_skills_dps_value()

        totals = {
            "dex_percent": 0.0,
            "dex_flat": 0.0,
            "damage_percent": 0.0,
            "crit_rate": 0.0,
            "crit_damage": 0.0,
            "defense_pen": 0.0,
            "boss_damage": 0.0,
            "min_dmg_mult": 0.0,
            "max_dmg_mult": 0.0,
            "final_damage_lines": [],  # List of individual FD values (multiplicative)
            "attack_speed": 0.0,
            "all_skills": 0.0,  # Track separately for display
            "skill_cd": 0.0,  # Skill cooldown reduction from hat special potential
        }

        for equip in self.equipment.values():
            stats = equip.get_all_stats()
            for stat_type, value in stats.items():
                # Handle main stat % types - ONLY DEX counts for Bowmaster (DEX class)
                # Wrong-class stats (STR/INT/LUK) give 0 DPS contribution
                if stat_type in (StatType.DEX_PCT, StatType.MAIN_STAT_PCT):
                    totals["dex_percent"] += value
                # STR_PCT, INT_PCT, LUK_PCT are ignored (wrong class, 0 DPS)
                elif stat_type in (StatType.STR_PCT, StatType.INT_PCT, StatType.LUK_PCT):
                    pass  # Wrong class stats give 0 DPS for DEX class
                # Handle flat main stats - ONLY DEX counts for Bowmaster
                elif stat_type in (StatType.DEX_FLAT, StatType.MAIN_STAT_FLAT):
                    totals["dex_flat"] += value
                # STR_FLAT, INT_FLAT, LUK_FLAT are ignored (wrong class, 0 DPS)
                elif stat_type in (StatType.STR_FLAT, StatType.INT_FLAT, StatType.LUK_FLAT):
                    pass  # Wrong class stats give 0 DPS for DEX class
                elif stat_type == StatType.DAMAGE_PCT:
                    totals["damage_percent"] += value
                elif stat_type == StatType.CRIT_RATE:
                    totals["crit_rate"] += value
                elif stat_type == StatType.CRIT_DAMAGE:
                    totals["crit_damage"] += value
                elif stat_type == StatType.DEF_PEN:
                    totals["defense_pen"] += value
                elif stat_type == StatType.MIN_DMG_MULT:
                    totals["min_dmg_mult"] += value
                elif stat_type == StatType.MAX_DMG_MULT:
                    totals["max_dmg_mult"] += value
                elif stat_type == StatType.FINAL_DAMAGE:
                    # Each FD line is a separate multiplicative source
                    totals["final_damage_lines"].append(value)
                elif stat_type == StatType.ATTACK_SPEED:
                    totals["attack_speed"] += value
                elif stat_type == StatType.ALL_SKILLS:
                    # All Skills: DPS value calculated from skill DPS model
                    totals["all_skills"] += value
                    # All Skills FD contribution is also multiplicative
                    fd_from_all_skills = value * all_skills_to_dps
                    if fd_from_all_skills > 0:
                        totals["final_damage_lines"].append(fd_from_all_skills)
                elif stat_type == StatType.BA_TARGETS:
                    # BA Targets: value depends on combat mode
                    # Basic attack already hits 7 enemies at base
                    # +1 target means 8/7 = 14.3% more BA damage per extra target
                    # Formula: (base_targets + extra) / base_targets - 1
                    BASE_BA_TARGETS = 7
                    ba_mult = BA_TARGETS_MODE_MULTIPLIER.get(self.combat_mode, 0)
                    # Calculate BA% from skill data based on character level
                    ba_dps_pct = calculate_ba_percent_of_dps(
                        self.character_level, self.current_all_skills
                    )
                    # Each +1 target = +1/7 = 14.3% more BA damage
                    # DPS gain = BA% * (extra_targets / base_targets) * mode_mult
                    ba_increase_pct = (value / BASE_BA_TARGETS) * 100  # +14.3% per target
                    dps_gain = (ba_dps_pct / 100) * ba_increase_pct * ba_mult
                    if dps_gain > 0:
                        totals["final_damage_lines"].append(dps_gain)
                elif stat_type == StatType.SKILL_CD:
                    # Skill Cooldown Reduction: flat seconds off skill cooldowns
                    # Value is stored and passed to DPS calculator for skill CD adjustments
                    totals["skill_cd"] += value

        # Calculate final_damage as sum of all FD lines (for display purposes)
        # Note: actual DPS calculation uses multiplicative formula with final_damage_lines
        totals["final_damage"] = sum(totals["final_damage_lines"])

        return totals

    def get_equipment_base_stats_total(self) -> Dict[str, float]:
        """
        Calculate total stats from all equipment items (base stats with starforce amplification).
        This aggregates attack, boss damage, normal damage, crit rate, crit damage, etc.
        from the equipment items (NOT potentials - those are separate).
        """
        totals = {
            "attack": 0.0,
            "attack_flat": 0.0,
            "max_hp": 0.0,
            "boss_damage": 0.0,
            "normal_damage": 0.0,
            "crit_rate": 0.0,
            "crit_damage": 0.0,
            "damage_pct": 0.0,
            "final_damage": 0.0,
            "main_stat": 0.0,
            "defense": 0.0,
            "accuracy": 0.0,
            "evasion": 0.0,
            "first_job": 0,
            "second_job": 0,
            "third_job": 0,
            "fourth_job": 0,
            "all_skills": 0,
        }

        for slot, item in self.equipment_items.items():
            stats = item.get_all_stats()

            # Sum up stats from each equipment item
            totals["attack"] += stats.get("attack", 0)
            totals["attack_flat"] += stats.get("attack_flat", 0)
            totals["max_hp"] += stats.get("max_hp", 0)
            totals["boss_damage"] += stats.get("boss_damage", 0)
            totals["normal_damage"] += stats.get("normal_damage", 0)
            totals["crit_rate"] += stats.get("crit_rate", 0)
            totals["crit_damage"] += stats.get("crit_damage", 0)

            # Special stats (only special items have these)
            totals["damage_pct"] += stats.get("damage_pct", 0)
            totals["final_damage"] += stats.get("final_damage", 0)
            totals["all_skills"] += stats.get("all_skills", 0)

            # Main stat (3rd stat on some items like shoulder/belt)
            totals["main_stat"] += stats.get("main_stat", 0)

            # Defense stats (3rd stat on armor pieces)
            totals["defense"] += stats.get("defense", 0)
            totals["accuracy"] += stats.get("accuracy", 0)
            totals["evasion"] += stats.get("evasion", 0)

            # Skill level bonuses
            totals["first_job"] += stats.get("first_job", 0)
            totals["second_job"] += stats.get("second_job", 0)
            totals["third_job"] += stats.get("third_job", 0)
            totals["fourth_job"] += stats.get("fourth_job", 0)

        return totals

    def apply_potential_to_damage_calc(self, pending_lines: List[PotentialLine] = None,
                                       pending_slot: str = None):
        """
        Update damage calculator with current potential stats.
        If pending_lines provided, calculate what the new damage WOULD be.
        Returns (current_damage, new_damage) if pending provided.

        IMPORTANT: Compares total DPS with ALL current equipped potentials vs
        total DPS with the new pending lines replacing the current slot's lines.
        """
        # Current damage uses _get_damage_stats which already includes potentials
        current_damage = self._calc_damage(self._get_damage_stats())

        if pending_lines and pending_slot:
            # Calculate NEW damage with pending lines replacing the slot's current lines
            old_equip = self.equipment[pending_slot]
            old_lines = old_equip.lines

            # Temporarily apply new lines to calculate new total
            old_equip.lines = pending_lines
            new_damage = self._calc_damage(self._get_damage_stats())
            old_equip.lines = old_lines  # Restore immediately

            return (current_damage, new_damage)

        return (current_damage, current_damage)

    # =========================================================================
    # TAB 1: DAMAGE CALCULATOR
    # =========================================================================

    def build_damage_tab(self):
        """Build the damage calculator tab."""
        self.damage_sliders = {}
        self.damage_value_labels = {}
        self.baseline_damage = None

        main_frame = ttk.Frame(self.damage_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Three columns
        columns = ttk.Frame(main_frame)
        columns.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(columns)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        middle = ttk.Frame(columns)
        middle.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        right = ttk.Frame(columns)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Left column - Character Settings first
        self._section_header(left, "Character Settings")
        self._build_character_settings(left)

        self._section_header(left, "Base Stats")
        self._damage_slider(left, "base_atk", "Base ATK", 0, 10000000, 50000, 10000)
        self._damage_slider(left, "dex_flat", "Flat DEX Pool", 0, 100000, 18700, 100)
        self._damage_slider(left, "dex_percent", "DEX %", 0, 500, 126.5, 0.5)

        self._section_header(left, "Damage Multipliers")
        self._damage_slider(left, "damage_percent", "Damage %", 0, 2000, 484.1, 1)
        self._damage_slider(left, "hex_stacks", "Hex Stacks", 0, 3, 3, 1)
        self._damage_slider(left, "damage_amp", "Damage Amp %", 0, 100, 23.2, 0.1)
        self._damage_slider(left, "boss_damage", "Boss Damage %", 0, 300, 64.5, 0.5)

        # Middle column
        self._section_header(middle, "Final Damage")
        # Guild FD is the only manual FD input - can be 0/3/6/10% depending on guild level
        # Other FD sources are calculated from equipment, potentials, passives, etc.
        self._damage_slider(middle, "fd_guild", "Guild FD %", 0, 10, 6, 1)

        self._section_header(middle, "Critical & Defense")
        self._damage_slider(middle, "crit_damage", "Crit Damage %", 0, 500, 184.5, 0.5)
        self._damage_slider(middle, "defense_pen", "Defense Pen %", 0, 100, 60.9, 0.5)
        self._damage_slider(middle, "enemy_def", "Enemy Defense", 0, 10, 0.752, 0.01)

        # Calculated Attack section - shows predicted flat attack from sources
        self._section_header(middle, "Calculated Attack (from sources)")

        # Input for actual in-game attack to compare
        actual_row = tk.Frame(middle, bg='#1a1a2e')
        actual_row.pack(fill=tk.X, pady=(0, 5))
        tk.Label(actual_row, text="Actual In-Game ATK:", font=('Segoe UI', 9),
                 bg='#1a1a2e', fg='#aaa').pack(side=tk.LEFT)
        self.actual_attack_var = tk.StringVar(value="48788000")
        self.actual_attack_entry = tk.Entry(actual_row, textvariable=self.actual_attack_var,
                                            width=12, font=('Consolas', 9))
        self.actual_attack_entry.pack(side=tk.LEFT, padx=5)
        self.actual_attack_entry.bind('<KeyRelease>', lambda e: self.update_calc_attack_display())

        self.calc_attack_label = tk.Label(middle, text="Loading...",
                                          font=('Consolas', 9), bg='#1a1a2e', fg='#aaa',
                                          justify=tk.LEFT)
        self.calc_attack_label.pack(pady=5, anchor=tk.W)

        # Right column - visualization
        self._section_header(right, "Which Stat to Upgrade?")
        self.priority_chart = BarChart(right, width=420, height=380)

        self._section_header(right, "Recommendation")
        self.recommendation_label = tk.Label(right, text="", font=('Segoe UI', 10),
                                             bg='#1a1a2e', fg='#00ff88',
                                             wraplength=360, justify=tk.LEFT)
        self.recommendation_label.pack(pady=5)

        # Potential stats from cubing
        self._section_header(right, "Stats from Equipment Potentials")
        self.potential_stats_label = tk.Label(right, text="No potentials set yet.\nUse the Cube Simulator to roll!",
                                              font=('Consolas', 9), bg='#1a1a2e', fg='#aaa',
                                              justify=tk.LEFT)
        self.potential_stats_label.pack(pady=5, anchor=tk.W)

        # Results section
        results = ttk.Frame(main_frame)
        results.pack(fill=tk.X, pady=15)

        self.damage_label = tk.Label(results, text="Total Damage: ---",
                                     font=('Segoe UI', 22, 'bold'),
                                     bg='#1a1a2e', fg='#00ff88')
        self.damage_label.pack(side=tk.LEFT, padx=20)

        self.change_label = tk.Label(results, text="", font=('Segoe UI', 12),
                                     bg='#1a1a2e', fg='#888')
        self.change_label.pack(side=tk.LEFT)

        self.breakdown_label = tk.Label(results, text="", font=('Consolas', 9),
                                        bg='#1a1a2e', fg='#aaa', justify=tk.LEFT)
        self.breakdown_label.pack(side=tk.LEFT, padx=40)

        # Buttons
        buttons = ttk.Frame(main_frame)
        buttons.pack(fill=tk.X, pady=5)

        tk.Button(buttons, text="Set Baseline", command=self.set_damage_baseline,
                 bg='#4a4a6a', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(buttons, text="Load Calculated", command=self.load_calculated_baseline,
                 bg='#2a6a4a', fg='white').pack(side=tk.LEFT, padx=5)
        tk.Button(buttons, text="Reset", command=self.reset_damage_defaults,
                 bg='#4a4a6a', fg='white').pack(side=tk.LEFT, padx=5)

        # Chapter/Stage selector dropdown
        tk.Label(buttons, text="Chapter:", bg='#1a1a2e', fg='#aaa').pack(side=tk.LEFT, padx=(20, 5))
        self.chapter_var = tk.StringVar(value="Chapter 27")  # Default to Mu Lung
        chapter_dropdown = ttk.Combobox(
            buttons, textvariable=self.chapter_var,
            values=list(ENEMY_DEFENSE_VALUES.keys()),
            state='readonly', width=15, font=('Segoe UI', 9)
        )
        chapter_dropdown.pack(side=tk.LEFT, padx=2)
        chapter_dropdown.bind('<<ComboboxSelected>>', self._on_chapter_change)

        # Show current defense value
        self.chapter_def_label = tk.Label(buttons, text="(Def: 0.752)",
                                          bg='#1a1a2e', fg='#888', font=('Segoe UI', 8))
        self.chapter_def_label.pack(side=tk.LEFT, padx=5)

        # Manual stat adjustments button
        tk.Button(buttons, text="⚙ Manual Adjustments", command=self.open_manual_adjustments,
                 bg='#6a4a6a', fg='white', font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=5)

        # DPS calculation mode toggle
        tk.Checkbutton(buttons, text="Skill-Based DPS", variable=self.use_skill_based_dps,
                      command=self.update_damage, bg='#1a1a2e', fg='#ffd700',
                      selectcolor='#2a2a4e', activebackground='#1a1a2e',
                      font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=10)

        # Mark sliders as ready so callbacks work
        self._sliders_ready = True
        self.update_damage()
        self.set_damage_baseline()

    def _section_header(self, parent, text):
        tk.Label(parent, text=text, font=('Segoe UI', 11, 'bold'),
                bg='#1a1a2e', fg='#ffd700').pack(anchor=tk.W, pady=(10, 5))

    def _build_character_settings(self, parent):
        """Build character level and All Skills inputs."""
        # Character Level
        level_frame = ttk.Frame(parent)
        level_frame.pack(fill=tk.X, pady=2)

        tk.Label(level_frame, text="Character Level", width=20, anchor=tk.W,
                font=('Segoe UI', 9), bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT)

        self.level_var = tk.StringVar(value=str(self.character_level))
        tk.Label(level_frame, textvariable=self.level_var, width=10,
                font=('Consolas', 9), bg='#1a1a2e', fg='#00ff88').pack(side=tk.RIGHT)

        self.level_slider = ttk.Scale(level_frame, from_=60, to=200, orient=tk.HORIZONTAL, length=160,
                                      command=self._on_level_change)
        self.level_slider.set(self.character_level)
        self.level_slider.pack(side=tk.RIGHT, padx=5)

        # Current All Skills (from equipment, not potentials)
        as_frame = ttk.Frame(parent)
        as_frame.pack(fill=tk.X, pady=2)

        tk.Label(as_frame, text="Current +All Skills", width=20, anchor=tk.W,
                font=('Segoe UI', 9), bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT)

        self.all_skills_var = tk.StringVar(value=str(self.current_all_skills))
        tk.Label(as_frame, textvariable=self.all_skills_var, width=10,
                font=('Consolas', 9), bg='#1a1a2e', fg='#00ff88').pack(side=tk.RIGHT)

        self.all_skills_slider = ttk.Scale(as_frame, from_=0, to=100, orient=tk.HORIZONTAL, length=160,
                                           command=self._on_all_skills_change)
        self.all_skills_slider.set(self.current_all_skills)
        self.all_skills_slider.pack(side=tk.RIGHT, padx=5)

        # All Skills DPS value display
        self.all_skills_value_label = tk.Label(parent, text="",
                                               font=('Consolas', 8), bg='#1a1a2e', fg='#888')
        self.all_skills_value_label.pack(anchor=tk.W, pady=(0, 5))
        self._update_all_skills_value_display()

    def _on_level_change(self, value):
        """Handle character level change."""
        self.character_level = int(float(value))
        self.level_var.set(str(self.character_level))
        self.invalidate_all_skills_cache()
        self._update_all_skills_value_display()
        # Sync with Character Stats tab
        if hasattr(self, 'char_settings_level_var'):
            self.char_settings_level_var.set(self.character_level)
        self.save_character_settings()
        if hasattr(self, '_sliders_ready') and self._sliders_ready:
            self.update_damage()

    def _on_all_skills_change(self, value):
        """Handle All Skills change."""
        self.current_all_skills = int(float(value))
        self.all_skills_var.set(str(self.current_all_skills))
        self.invalidate_all_skills_cache()
        self._update_all_skills_value_display()
        # Sync with Character Stats tab
        if hasattr(self, 'char_settings_all_skills_var'):
            self.char_settings_all_skills_var.set(self.current_all_skills)
        self._update_skill_totals_display()
        self.save_character_settings()
        if hasattr(self, '_sliders_ready') and self._sliders_ready:
            self.update_damage()

    def _update_all_skills_value_display(self):
        """Update the display showing +1 All Skills DPS value."""
        if hasattr(self, 'all_skills_value_label'):
            value = self.get_all_skills_dps_value()
            self.all_skills_value_label.config(
                text=f"+1 All Skills = +{value:.2f}% DPS (Lvl {self.character_level}, +{self.current_all_skills} AS)"
            )

    def _damage_slider(self, parent, key, label, min_v, max_v, default, res):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)

        # Label with info button for stat breakdown
        label_frame = ttk.Frame(frame)
        label_frame.pack(side=tk.LEFT)

        # Stats that have breakdown popups
        has_breakdown = key in ["base_atk", "dex_flat", "dex_percent", "damage_percent",
                                "boss_damage", "crit_damage", "defense_pen", "fd_guild"]

        stat_label = tk.Label(label_frame, text=label, width=16, anchor=tk.W,
                             font=('Segoe UI', 9), bg='#1a1a2e', fg='#ccc')
        stat_label.pack(side=tk.LEFT)

        if has_breakdown:
            # Add info button (ℹ️) to show breakdown
            info_btn = tk.Label(label_frame, text="ⓘ", font=('Segoe UI', 9),
                               bg='#1a1a2e', fg='#4a9eff', cursor='hand2')
            info_btn.pack(side=tk.LEFT, padx=2)
            info_btn.bind("<Button-1>", lambda e, k=key: self.show_stat_breakdown(k))
            # Tooltip on hover
            info_btn.bind("<Enter>", lambda e: e.widget.config(fg='#00ff88'))
            info_btn.bind("<Leave>", lambda e: e.widget.config(fg='#4a9eff'))

        value_var = tk.StringVar(value=str(default))
        tk.Label(frame, textvariable=value_var, width=12,
                font=('Consolas', 9), bg='#1a1a2e', fg='#00ff88').pack(side=tk.RIGHT)

        slider = ttk.Scale(frame, from_=min_v, to=max_v, orient=tk.HORIZONTAL, length=140,
                          command=lambda v, k=key, vv=value_var, r=res: self._on_damage_slider(k, v, vv, r))
        slider.set(default)
        slider.pack(side=tk.RIGHT, padx=5)

        self.damage_sliders[key] = slider
        self.damage_value_labels[key] = value_var

    def _on_damage_slider(self, key, value, value_var, res):
        val = float(value)
        if res >= 1:
            # Format large numbers with K/M suffix for readability
            if val >= 1000000:
                value_var.set(f"{val/1000000:.2f}M")
            elif val >= 10000:
                value_var.set(f"{val/1000:.1f}K")
            else:
                value_var.set(f"{int(round(val)):,}")
        else:
            value_var.set(f"{round(val / res) * res:.1f}")
        # Only update damage if all sliders exist
        if hasattr(self, '_sliders_ready') and self._sliders_ready:
            self.update_damage()

    def _get_damage_slider(self, key):
        return float(self.damage_sliders[key].get())

    # =========================================================================
    # STAT BREAKDOWN POPUP SYSTEM
    # =========================================================================

    def show_stat_breakdown(self, stat_key: str):
        """
        Show a popup modal with detailed breakdown of sources for a stat.
        """
        breakdown = self._get_stat_breakdown(stat_key)
        if not breakdown:
            return

        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title(f"Stat Breakdown: {breakdown['name']}")
        popup.geometry("450x500")
        popup.configure(bg='#1a1a2e')
        popup.transient(self.root)
        popup.grab_set()

        # Header
        header = tk.Label(popup, text=breakdown['name'],
                         font=('Segoe UI', 14, 'bold'), bg='#1a1a2e', fg='#ffd700')
        header.pack(pady=(15, 5))

        # Total value
        total_text = f"Total: {breakdown['total']:,.1f}" if isinstance(breakdown['total'], float) else f"Total: {breakdown['total']:,}"
        if breakdown.get('unit'):
            total_text += breakdown['unit']
        total_label = tk.Label(popup, text=total_text,
                              font=('Consolas', 12, 'bold'), bg='#1a1a2e', fg='#00ff88')
        total_label.pack(pady=(0, 15))

        # Scrollable frame for sources
        canvas_frame = ttk.Frame(popup)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(canvas_frame, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Sources list
        for source in breakdown['sources']:
            source_frame = ttk.Frame(scrollable_frame)
            source_frame.pack(fill=tk.X, pady=2, padx=5)

            # Source name
            name_label = tk.Label(source_frame, text=source['name'],
                                 font=('Segoe UI', 10), bg='#1a1a2e', fg='#ccc',
                                 anchor='w', width=25)
            name_label.pack(side=tk.LEFT)

            # Source value - handle separators (empty string values)
            value = source['value']
            if value == "":
                # Separator line - no value label needed
                continue
            elif value == 0:
                value_text = "0"
                color = '#666'
            elif isinstance(value, float):
                if abs(value) < 0.01:
                    value_text = "0"
                    color = '#666'
                else:
                    value_text = f"{value:,.2f}"
                    color = '#00ff88' if value > 0 else '#ff4444'
            else:
                value_text = f"{value:,}"
                color = '#00ff88' if value > 0 else '#ff4444'

            if breakdown.get('unit') and value != 0:
                value_text += breakdown['unit']

            value_label = tk.Label(source_frame, text=value_text,
                                  font=('Consolas', 10), bg='#1a1a2e', fg=color,
                                  anchor='e', width=15)
            value_label.pack(side=tk.RIGHT)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Note about multiplicative stacking if applicable
        if breakdown.get('note'):
            note_label = tk.Label(popup, text=breakdown['note'],
                                 font=('Segoe UI', 9, 'italic'), bg='#1a1a2e', fg='#aaa',
                                 wraplength=400)
            note_label.pack(pady=10)

        # Close button
        close_btn = tk.Button(popup, text="Close", command=popup.destroy,
                             bg='#4a4a6a', fg='white', font=('Segoe UI', 10))
        close_btn.pack(pady=15)

        # Center the popup
        popup.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - popup.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - popup.winfo_height()) // 2
        popup.geometry(f"+{x}+{y}")

    def _get_stat_breakdown(self, stat_key: str) -> Optional[Dict]:
        """
        Get breakdown of all sources contributing to a stat.
        Returns dict with 'name', 'total', 'unit', 'sources', 'note'.
        """
        # Collect all stat sources
        pot = self.get_potential_stats_total()
        weapon = self.get_weapon_stats_total()
        artifact = self.get_artifact_stats_total()
        hero_power = self.get_hero_power_stats_total()
        hero_power_passive = self.get_hero_power_passive_stats_total()
        equip_base = self.get_equipment_base_stats_total()
        guild = self.get_guild_stats_total()
        companion = self.get_companion_stats_total()
        passive = self.get_passive_stats_total()
        maple_rank = self.get_maple_rank_stats_total()

        if stat_key == "base_atk":
            # Equipment attack (main + sub)
            equip_main = equip_base.get("attack", 0)
            equip_sub = equip_base.get("attack_flat", 0)
            weapon_atk_pct = weapon.get("weapon_atk_percent", 0)
            weapon_mult = 1 + weapon_atk_pct / 100

            raw_flat = (
                equip_main + equip_sub +
                artifact.get("attack_flat", 0) +
                guild.get("attack_flat", 0) +
                companion.get("flat_attack", 0) +
                hero_power_passive.get("attack_flat", 0)
            )
            slider_value = self._get_damage_slider("base_atk")

            return {
                "name": "Base Attack",
                "total": slider_value,
                "unit": "",
                "sources": [
                    {"name": "Equipment (Main ATK)", "value": equip_main},
                    {"name": "Equipment (Sub Flat ATK)", "value": equip_sub},
                    {"name": "Artifacts", "value": artifact.get("attack_flat", 0)},
                    {"name": "Guild", "value": guild.get("attack_flat", 0)},
                    {"name": "Companions", "value": companion.get("flat_attack", 0)},
                    {"name": "Hero Power Passive", "value": hero_power_passive.get("attack_flat", 0)},
                    {"name": "─" * 20, "value": ""},
                    {"name": "Raw Flat Attack Total", "value": raw_flat},
                    {"name": f"Weapon ATK% (×{weapon_mult:.2f})", "value": weapon_atk_pct},
                    {"name": "Calculated Base ATK", "value": raw_flat * weapon_mult},
                    {"name": "─" * 20, "value": ""},
                    {"name": "Slider Value", "value": slider_value},
                    {"name": "Difference", "value": slider_value - (raw_flat * weapon_mult)},
                ],
                "note": "Base ATK = Raw Flat Attack × (1 + Weapon ATK%)",
            }

        elif stat_key == "dex_flat":
            return {
                "name": "Flat DEX (Main Stat)",
                "total": self._get_damage_slider("dex_flat"),
                "unit": "",
                "sources": [
                    {"name": "Potentials", "value": pot.get("dex_flat", 0)},
                    {"name": "Equipment (3rd stat)", "value": equip_base.get("main_stat", 0)},
                    {"name": "Artifacts (Resonance)", "value": artifact.get("main_stat_flat", 0)},
                    {"name": "Companions (2nd Job)", "value": companion.get("flat_main_stat", 0)},
                    {"name": "Maple Rank", "value": maple_rank.get("main_stat_flat", 0)},
                    {"name": "Hero Power Passive", "value": hero_power_passive.get("main_stat_flat", 0)},
                    {"name": "Hero Power (Ability)", "value": hero_power.get("main_stat_pct", 0)},  # FLAT main stat despite the key name
                    {"name": "Passive Skills (Soul Arrow)", "value": passive.get("dex_flat", 0)},
                    {"name": "Passive Skills (Mastery)", "value": passive.get("main_stat_flat", 0)},
                ],
            }

        elif stat_key == "dex_percent":
            # DEX% only comes from cube potentials and artifact potentials
            # Hero Power "Main Stat" is FLAT DEX, not DEX%
            artifact_main_pct = artifact.get("main_stat", 0) * 100  # Artifact potentials store as decimal
            return {
                "name": "DEX % (Main Stat %)",
                "total": self._get_damage_slider("dex_percent"),
                "unit": "%",
                "sources": [
                    {"name": "Potentials (Cube)", "value": pot.get("dex_percent", 0)},
                    {"name": "Artifact Potentials", "value": artifact_main_pct},
                ],
            }

        elif stat_key == "damage_percent":
            return {
                "name": "Damage %",
                "total": self._get_damage_slider("damage_percent"),
                "unit": "%",
                "sources": [
                    {"name": "Potentials", "value": pot.get("damage_percent", 0)},
                    {"name": "Artifacts", "value": artifact.get("damage", 0) * 100},
                    {"name": "Hero Power (Ability)", "value": hero_power.get("damage", 0)},
                    {"name": "Hero Power Passive", "value": hero_power_passive.get("damage_percent", 0)},
                    {"name": "Equipment (Special)", "value": equip_base.get("damage_pct", 0)},
                    {"name": "Guild", "value": guild.get("damage", 0)},
                    {"name": "Companions (3rd/4th Job)", "value": companion.get("damage", 0)},
                    {"name": "Maple Rank", "value": maple_rank.get("damage_percent", 0)},
                ],
            }

        elif stat_key == "boss_damage":
            return {
                "name": "Boss Damage %",
                "total": self._get_damage_slider("boss_damage"),
                "unit": "%",
                "sources": [
                    {"name": "Artifacts", "value": artifact.get("boss_damage", 0) * 100},
                    {"name": "Hero Power (Ability)", "value": hero_power.get("boss_damage", 0)},
                    {"name": "Equipment (Sub stat)", "value": equip_base.get("boss_damage", 0)},
                    {"name": "Guild", "value": guild.get("boss_damage", 0)},
                    {"name": "Companions", "value": companion.get("boss_damage", 0)},
                    {"name": "Maple Rank", "value": maple_rank.get("boss_damage", 0)},
                ],
            }

        elif stat_key == "crit_damage":
            return {
                "name": "Critical Damage %",
                "total": self._get_damage_slider("crit_damage"),
                "unit": "%",
                "sources": [
                    {"name": "Potentials", "value": pot.get("crit_damage", 0)},
                    {"name": "Artifacts", "value": artifact.get("crit_damage", 0) * 100},
                    {"name": "Hero Power (Ability)", "value": hero_power.get("crit_damage", 0)},
                    {"name": "Equipment (Sub stat)", "value": equip_base.get("crit_damage", 0)},
                    {"name": "Guild", "value": guild.get("crit_damage", 0)},
                    {"name": "Passive Skills", "value": passive.get("crit_damage", 0)},
                    {"name": "Maple Rank", "value": maple_rank.get("crit_damage", 0)},
                ],
            }

        elif stat_key == "defense_pen":
            # Defense pen is multiplicative
            sources = [
                ("Base (Slider)", self._get_damage_slider("defense_pen") / 100),
                ("Potentials", pot.get("defense_pen", 0) / 100),
                ("Artifacts", artifact.get("def_pen", 0)),
                ("Hero Power (Ability)", hero_power.get("def_pen", 0) / 100),
                ("Guild", guild.get("def_pen", 0) / 100),
                ("Passive Skills", passive.get("def_pen", 0) / 100),
            ]

            # Calculate multiplicative total
            remaining = 1.0
            source_list = []
            for name, value in sources:
                source_list.append({"name": name, "value": value * 100})
                if value > 0:
                    remaining *= (1 - value)

            total_def_pen = (1 - remaining) * 100

            return {
                "name": "Defense Penetration %",
                "total": total_def_pen,
                "unit": "%",
                "sources": source_list,
                "note": "Defense Pen stacks multiplicatively: Total = 1 - (1-A) × (1-B) × ...",
            }

        elif stat_key == "fd_guild":
            # Final Damage breakdown
            # Each FD line from potentials is multiplicative
            pot_fd_lines = pot.get("final_damage_lines", [])
            pot_fd_mult = 1.0
            for fd in pot_fd_lines:
                pot_fd_mult *= (1 + fd / 100)
            pot_fd = (pot_fd_mult - 1) * 100  # Convert back to percentage

            equip_fd = equip_base.get("final_damage", 0)
            comp_fd = companion.get("final_damage", 0)
            passive_fd = passive.get("final_damage", 0)
            guild_fd = self._get_damage_slider("fd_guild")

            # Total is multiplicative: (1+pot)*(1+equip)*(1+comp)*(1+passive)*(1+guild) - 1
            total_mult = pot_fd_mult * (1 + equip_fd/100) * (1 + comp_fd/100) * (1 + passive_fd/100) * (1 + guild_fd/100)
            total_fd = (total_mult - 1) * 100

            return {
                "name": "Final Damage %",
                "total": total_fd,
                "unit": "%",
                "sources": [
                    {"name": f"Potentials ({len(pot_fd_lines)} lines)", "value": pot_fd},
                    {"name": "Equipment (Special)", "value": equip_fd},
                    {"name": "Companions", "value": comp_fd},
                    {"name": "Passive Skills", "value": passive_fd},
                    {"name": "Guild (Slider)", "value": guild_fd},
                ],
                "note": "Final Damage sources are multiplicative: (1+A) × (1+B) × ...",
            }

        return None

    def _get_calculated_stat_breakdown(self, stat_key: str) -> Optional[Dict]:
        """
        Get breakdown of all sources contributing to a stat using ONLY calculated values.
        This is used by the Character Stats tab which shows modeled sources only.

        Returns dict with 'name', 'total', 'unit', 'sources', 'note'.
        """
        # Collect all stat sources
        pot = self.get_potential_stats_total()
        weapon = self.get_weapon_stats_total()
        artifact = self.get_artifact_stats_total()
        hero_power = self.get_hero_power_stats_total()
        hero_power_passive = self.get_hero_power_passive_stats_total()
        equip_base = self.get_equipment_base_stats_total()
        guild = self.get_guild_stats_total()
        companion = self.get_companion_stats_total()
        passive = self.get_passive_stats_total()
        maple_rank = self.get_maple_rank_stats_total()
        equip_sets = self.get_equipment_sets_stats_total()

        if stat_key == "base_atk":
            # Equipment attack (main + sub)
            equip_main = equip_base.get("attack", 0)
            equip_sub = equip_base.get("attack_flat", 0)
            weapon_atk_pct = weapon.get("weapon_atk_percent", 0)
            weapon_mult = 1 + weapon_atk_pct / 100

            # All flat attack sources
            artifact_atk = artifact.get("attack_flat", 0)
            guild_atk = guild.get("attack_flat", 0)
            comp_atk = companion.get("flat_attack", 0)
            hpp_atk = hero_power_passive.get("attack_flat", 0)

            raw_flat = equip_main + equip_sub + artifact_atk + guild_atk + comp_atk + hpp_atk
            calculated_total = raw_flat * weapon_mult

            return {
                "name": "Base Attack (Calculated)",
                "total": calculated_total,
                "unit": "",
                "sources": [
                    {"name": "Equipment (Main ATK)", "value": equip_main},
                    {"name": "Equipment (Sub Flat ATK)", "value": equip_sub},
                    {"name": "Artifacts (Inventory)", "value": artifact_atk},
                    {"name": "Guild Skills", "value": guild_atk},
                    {"name": "Companions (Inventory)", "value": comp_atk},
                    {"name": "Hero Power Passive", "value": hpp_atk},
                    {"name": "─" * 20, "value": ""},
                    {"name": "Raw Flat Attack Total", "value": raw_flat},
                    {"name": f"Weapon ATK% Multiplier", "value": f"×{weapon_mult:.2f} ({weapon_atk_pct:.1f}%)"},
                    {"name": "─" * 20, "value": ""},
                    {"name": "Calculated Total", "value": calculated_total},
                ],
                "note": "Base ATK = Raw Flat Attack × (1 + Weapon ATK%)",
            }

        elif stat_key == "dex_flat":
            # All flat DEX sources
            pot_dex = pot.get("dex_flat", 0)
            equip_dex = equip_base.get("main_stat", 0)
            artifact_dex = artifact.get("main_stat_flat", 0)
            comp_dex = companion.get("flat_main_stat", 0)
            mr_dex = maple_rank.get("main_stat_flat", 0)
            hpp_dex = hero_power_passive.get("main_stat_flat", 0)
            hp_dex = hero_power.get("main_stat_pct", 0)  # Hero Power ability lines provide FLAT main stat (despite the name)
            passive_dex = passive.get("dex_flat", 0)
            passive_main = passive.get("main_stat_flat", 0)
            medal_dex = self.equipment_sets_config.medal_config.get_main_stat()
            costume_dex = self.equipment_sets_config.costume_config.get_main_stat()

            total = (pot_dex + equip_dex + artifact_dex + comp_dex + mr_dex +
                     hpp_dex + hp_dex + passive_dex + passive_main + medal_dex + costume_dex)

            return {
                "name": "Flat DEX (Calculated)",
                "total": total,
                "unit": "",
                "sources": [
                    {"name": "Potentials", "value": pot_dex},
                    {"name": "Equipment (3rd stat)", "value": equip_dex},
                    {"name": "Artifacts (Resonance)", "value": artifact_dex},
                    {"name": "Companions (2nd Job Inv)", "value": comp_dex},
                    {"name": "Maple Rank", "value": mr_dex},
                    {"name": "Hero Power Passive", "value": hpp_dex},
                    {"name": "Hero Power (Ability)", "value": hp_dex},
                    {"name": "Passive Skills (Soul Arrow)", "value": passive_dex},
                    {"name": "Passive Skills (Mastery)", "value": passive_main},
                    {"name": "Medals (Inventory)", "value": medal_dex},
                    {"name": "Costumes (Inventory)", "value": costume_dex},
                ],
            }

        elif stat_key == "dex_percent":
            # DEX% only comes from cube potentials and artifact potentials
            # Hero Power "Main Stat" is FLAT DEX, not DEX%
            pot_pct = pot.get("dex_percent", 0)
            artifact_main_pct = artifact.get("main_stat", 0) * 100  # Artifact potentials store as decimal

            total = pot_pct + artifact_main_pct

            return {
                "name": "DEX % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Potentials (Cube)", "value": pot_pct},
                    {"name": "Artifact Potentials", "value": artifact_main_pct},
                ],
            }

        elif stat_key == "damage_percent":
            pot_dmg = pot.get("damage_percent", 0)
            artifact_dmg = artifact.get("damage", 0) * 100
            hp_dmg = hero_power.get("damage", 0)
            hpp_dmg = hero_power_passive.get("damage_percent", 0)
            equip_dmg = equip_base.get("damage_pct", 0)
            guild_dmg = guild.get("damage", 0)
            comp_dmg = companion.get("damage", 0)
            mr_dmg = maple_rank.get("damage_percent", 0)

            total = pot_dmg + artifact_dmg + hp_dmg + hpp_dmg + equip_dmg + guild_dmg + comp_dmg + mr_dmg

            return {
                "name": "Damage % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Potentials", "value": pot_dmg},
                    {"name": "Artifacts (Inventory)", "value": artifact_dmg},
                    {"name": "Hero Power (Ability)", "value": hp_dmg},
                    {"name": "Hero Power Passive", "value": hpp_dmg},
                    {"name": "Equipment (Special)", "value": equip_dmg},
                    {"name": "Guild Skills", "value": guild_dmg},
                    {"name": "Companions (3rd/4th Job Inv)", "value": comp_dmg},
                    {"name": "Maple Rank", "value": mr_dmg},
                ],
            }

        elif stat_key == "boss_damage":
            artifact_bd = artifact.get("boss_damage", 0) * 100
            hp_bd = hero_power.get("boss_damage", 0)
            equip_bd = equip_base.get("boss_damage", 0)
            guild_bd = guild.get("boss_damage", 0)
            comp_bd = companion.get("boss_damage", 0)
            mr_bd = maple_rank.get("boss_damage", 0)

            total = artifact_bd + hp_bd + equip_bd + guild_bd + comp_bd + mr_bd

            return {
                "name": "Boss Damage % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Artifacts (Inventory)", "value": artifact_bd},
                    {"name": "Hero Power (Ability)", "value": hp_bd},
                    {"name": "Equipment (Sub stat)", "value": equip_bd},
                    {"name": "Guild Skills", "value": guild_bd},
                    {"name": "Companions (On-Equip)", "value": comp_bd},
                    {"name": "Maple Rank", "value": mr_bd},
                ],
            }

        elif stat_key == "crit_damage":
            pot_cd = pot.get("crit_damage", 0)
            artifact_cd = artifact.get("crit_damage", 0) * 100  # Includes Book of Ancient conversion
            hp_cd = hero_power.get("crit_damage", 0)
            equip_cd = equip_base.get("crit_damage", 0)
            guild_cd = guild.get("crit_damage", 0)
            passive_cd = passive.get("crit_damage", 0)
            mr_cd = maple_rank.get("crit_damage", 0)

            # Separate out Book of Ancient contribution if equipped
            book_cd = 0
            book_note = ""
            for art in self.artifact_config.equipped:
                if art and art.definition.name == "Book of Ancient":
                    total_cr = self._get_total_crit_rate_for_book()
                    _, cd_bonus = calculate_book_of_ancient_bonus(art.awakening_stars, total_cr)
                    book_cd = cd_bonus * 100
                    book_note = f" (from {total_cr*100:.1f}% CR)"
                    break

            # artifact_cd already includes book_cd from get_artifact_stats_total()
            # Split it out for clearer display
            artifact_inv_cd = artifact_cd - book_cd  # Pure inventory crit damage

            total = pot_cd + artifact_cd + hp_cd + equip_cd + guild_cd + passive_cd + mr_cd

            sources = [
                {"name": "Potentials", "value": pot_cd},
                {"name": "Artifacts (Inventory)", "value": artifact_inv_cd},
            ]
            if book_cd > 0:
                sources.append({"name": f"Book of Ancient{book_note}", "value": book_cd})
            sources.extend([
                {"name": "Hero Power (Ability)", "value": hp_cd},
                {"name": "Equipment (Sub stat)", "value": equip_cd},
                {"name": "Guild Skills", "value": guild_cd},
                {"name": "Passive Skills", "value": passive_cd},
                {"name": "Maple Rank", "value": mr_cd},
            ])

            return {
                "name": "Critical Damage % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": sources,
            }

        elif stat_key == "defense_pen":
            # Defense pen is multiplicative
            sources = [
                ("Potentials", pot.get("defense_pen", 0) / 100),
                ("Artifacts (Inventory)", artifact.get("def_pen", 0)),
                ("Hero Power (Ability)", hero_power.get("def_pen", 0) / 100),
                ("Guild Skills", guild.get("def_pen", 0) / 100),
                ("Passive Skills", passive.get("def_pen", 0) / 100),
            ]

            # Calculate multiplicative total
            remaining = 1.0
            source_list = []
            for name, value in sources:
                source_list.append({"name": name, "value": value * 100})
                if value > 0:
                    remaining *= (1 - value)

            total_def_pen = (1 - remaining) * 100

            return {
                "name": "Defense Penetration % (Calculated)",
                "total": total_def_pen,
                "unit": "%",
                "sources": source_list,
                "note": "Defense Pen stacks multiplicatively: Total = 1 - (1-A) × (1-B) × ...",
            }

        elif stat_key == "final_damage":
            # Each FD line from potentials is multiplicative
            pot_fd_lines = pot.get("final_damage_lines", [])
            pot_fd_mult = 1.0
            for fd in pot_fd_lines:
                pot_fd_mult *= (1 + fd / 100)
            pot_fd = (pot_fd_mult - 1) * 100  # Convert back to percentage

            equip_fd = equip_base.get("final_damage", 0)
            comp_fd = companion.get("final_damage", 0)
            passive_fd = passive.get("final_damage", 0)
            guild_fd = guild.get("final_damage", 0)

            # Total is multiplicative: (1+pot)*(1+equip)*(1+comp)*(1+passive)*(1+guild) - 1
            total_mult = pot_fd_mult * (1 + equip_fd/100) * (1 + comp_fd/100) * (1 + passive_fd/100) * (1 + guild_fd/100)
            total = (total_mult - 1) * 100

            return {
                "name": "Final Damage % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": f"Potentials ({len(pot_fd_lines)} lines)", "value": pot_fd},
                    {"name": "Equipment (Special)", "value": equip_fd},
                    {"name": "Companions", "value": comp_fd},
                    {"name": "Passive Skills", "value": passive_fd},
                    {"name": "Guild Skills", "value": guild_fd},
                ],
                "note": "Final Damage sources are multiplicative: (1+A) × (1+B) × ...",
            }

        elif stat_key == "crit_rate":
            pot_cr = pot.get("crit_rate", 0)
            equip_cr = equip_base.get("crit_rate", 0)
            mr_cr = maple_rank.get("crit_rate", 0)
            comp_cr = companion.get("crit_rate", 0)
            passive_cr = passive.get("crit_rate", 0)

            total = pot_cr + equip_cr + mr_cr + comp_cr + passive_cr

            return {
                "name": "Critical Rate % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Potentials", "value": pot_cr},
                    {"name": "Equipment (Sub stat)", "value": equip_cr},
                    {"name": "Maple Rank", "value": mr_cr},
                    {"name": "Companions (On-Equip)", "value": comp_cr},
                    {"name": "Passive Skills", "value": passive_cr},
                ],
            }

        elif stat_key == "normal_damage":
            equip_nd = equip_base.get("normal_damage", 0)
            mr_nd = maple_rank.get("normal_damage", 0)
            comp_nd = companion.get("normal_damage", 0)
            artifact_nd = artifact.get("normal_damage", 0) * 100

            total = equip_nd + mr_nd + comp_nd + artifact_nd

            return {
                "name": "Normal Monster Damage % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Equipment (Sub stat)", "value": equip_nd},
                    {"name": "Maple Rank", "value": mr_nd},
                    {"name": "Companions (On-Equip)", "value": comp_nd},
                    {"name": "Artifacts (Inventory)", "value": artifact_nd},
                ],
            }

        elif stat_key == "skill_damage":
            mr_sd = maple_rank.get("skill_damage", 0)
            passive_sd = passive.get("skill_damage", 0)

            total = mr_sd + passive_sd

            return {
                "name": "Skill Damage % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Maple Rank", "value": mr_sd},
                    {"name": "Passive Skills", "value": passive_sd},
                ],
            }

        elif stat_key == "min_dmg_mult":
            pot_min = pot.get("min_dmg_mult", 0)
            mr_min = maple_rank.get("min_dmg_mult", 0)
            comp_min = companion.get("min_dmg_mult", 0)
            passive_min = passive.get("min_dmg_mult", 0)

            total = pot_min + mr_min + comp_min + passive_min

            return {
                "name": "Min Damage Multiplier % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Potentials (Cubes)", "value": pot_min},
                    {"name": "Maple Rank", "value": mr_min},
                    {"name": "Companions (On-Equip)", "value": comp_min},
                    {"name": "Passive Skills", "value": passive_min},
                ],
            }

        elif stat_key == "max_dmg_mult":
            pot_max = pot.get("max_dmg_mult", 0)
            mr_max = maple_rank.get("max_dmg_mult", 0)
            comp_max = companion.get("max_dmg_mult", 0)
            passive_max = passive.get("max_dmg_mult", 0)
            artifact_max = artifact.get("max_damage_mult", 0) * 100

            total = pot_max + mr_max + comp_max + passive_max + artifact_max

            return {
                "name": "Max Damage Multiplier % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Potentials (Cubes)", "value": pot_max},
                    {"name": "Maple Rank", "value": mr_max},
                    {"name": "Companions (On-Equip)", "value": comp_max},
                    {"name": "Passive Skills", "value": passive_max},
                    {"name": "Artifacts (Inventory)", "value": artifact_max},
                ],
            }

        elif stat_key == "attack_speed":
            mr_as = maple_rank.get("attack_speed", 0)
            comp_as = companion.get("attack_speed", 0)
            passive_as = passive.get("attack_speed", 0)

            total = mr_as + comp_as + passive_as

            return {
                "name": "Attack Speed % (Calculated)",
                "total": total,
                "unit": "%",
                "sources": [
                    {"name": "Maple Rank", "value": mr_as},
                    {"name": "Companions (On-Equip)", "value": comp_as},
                    {"name": "Passive Skills", "value": passive_as},
                ],
            }

        elif stat_key == "accuracy":
            mr_acc = maple_rank.get("accuracy", 0)
            hpp_acc = hero_power_passive.get("accuracy", 0)
            passive_acc = passive.get("accuracy", 0)

            total = mr_acc + hpp_acc + passive_acc

            return {
                "name": "Accuracy (Calculated)",
                "total": total,
                "unit": "",
                "sources": [
                    {"name": "Maple Rank", "value": mr_acc},
                    {"name": "Hero Power Passive", "value": hpp_acc},
                    {"name": "Passive Skills", "value": passive_acc},
                ],
            }

        return None

    def _show_calculated_stat_breakdown(self, stat_key: str):
        """Show a popup modal with detailed breakdown of sources for a stat (calculated values only)."""
        breakdown = self._get_calculated_stat_breakdown(stat_key)
        if not breakdown:
            return

        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title(f"Stat Breakdown: {breakdown['name']}")
        popup.geometry("500x450")
        popup.configure(bg='#1a1a2e')
        popup.transient(self.root)
        popup.grab_set()

        # Header
        header = tk.Label(popup, text=breakdown['name'],
                         font=('Segoe UI', 14, 'bold'), bg='#1a1a2e', fg='#ffd700')
        header.pack(pady=(15, 5))

        # Total value
        total = breakdown['total']
        if isinstance(total, str):
            total_text = f"Total: {total}"
        elif isinstance(total, float):
            total_text = f"Total: {total:,.1f}"
        else:
            total_text = f"Total: {total:,}"
        if breakdown.get('unit'):
            total_text += breakdown['unit']
        total_label = tk.Label(popup, text=total_text,
                              font=('Consolas', 12, 'bold'), bg='#1a1a2e', fg='#00ff88')
        total_label.pack(pady=(0, 15))

        # Scrollable frame for sources
        canvas_frame = ttk.Frame(popup)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(canvas_frame, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Sources list
        for source in breakdown['sources']:
            source_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
            source_frame.pack(fill=tk.X, pady=2, padx=5)

            # Source name
            name_label = tk.Label(source_frame, text=source['name'],
                                 font=('Segoe UI', 10), bg='#1a1a2e', fg='#ccc',
                                 anchor='w', width=28)
            name_label.pack(side=tk.LEFT)

            # Source value - handle separators (empty string values)
            value = source['value']
            if value == "":
                # Separator line - no value label needed
                continue
            elif isinstance(value, str):
                # String value (like the multiplier display)
                value_text = value
                color = '#00d4ff'
            elif value == 0:
                value_text = "0"
                color = '#666'
            elif isinstance(value, float):
                if abs(value) < 0.01:
                    value_text = "0"
                    color = '#666'
                else:
                    value_text = f"{value:,.1f}"
                    color = '#00ff88' if value > 0 else '#ff4444'
            else:
                value_text = f"{value:,}"
                color = '#00ff88' if value > 0 else '#ff4444'

            if breakdown.get('unit') and value != 0 and not isinstance(value, str):
                value_text += breakdown['unit']

            value_label = tk.Label(source_frame, text=value_text,
                                  font=('Consolas', 10), bg='#1a1a2e', fg=color,
                                  anchor='e', width=15)
            value_label.pack(side=tk.RIGHT)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Note (if any)
        if breakdown.get('note'):
            note_label = tk.Label(popup, text=breakdown['note'],
                                 font=('Segoe UI', 9, 'italic'), bg='#1a1a2e', fg='#888',
                                 wraplength=450)
            note_label.pack(pady=10)

        # Close button
        close_btn = tk.Button(popup, text="Close", command=popup.destroy,
                             font=('Segoe UI', 10), bg='#4a4a6e', fg='white',
                             activebackground='#5a5a7e', activeforeground='white',
                             relief=tk.FLAT, padx=20, pady=5)
        close_btn.pack(pady=10)

        # Unbind mousewheel when closing
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_close)
        close_btn.configure(command=on_close)

    def _get_base_stats(self):
        """Get base stats from sliders (before equipment potentials)."""
        return {
            "base_atk": self._get_damage_slider("base_atk"),
            "dex_flat": self._get_damage_slider("dex_flat"),
            "dex_percent": self._get_damage_slider("dex_percent"),
            "damage_percent": self._get_damage_slider("damage_percent"),
            "hex_stacks": int(self._get_damage_slider("hex_stacks")),
            "damage_amp": self._get_damage_slider("damage_amp"),
            "boss_damage": self._get_damage_slider("boss_damage"),
            # FD sources are MULTIPLICATIVE: (1+A) × (1+B) × (1+C) × ...
            # Each source is a separate element so 12% FD always = 12% DPS gain
            "fd_sources": [
                0,  # Potentials FD (cubes)
                0,  # Equipment special potential FD
                0,  # Passive skills FD (Extreme Archery + Armor Break)
                self._get_damage_slider("fd_guild"),  # Guild FD (manual slider: 0/3/6/10%)
                0,  # Manual adjustment FD
            ],
            "crit_damage": self._get_damage_slider("crit_damage"),
            "defense_pen": self._get_damage_slider("defense_pen"),
            "enemy_def": self._get_damage_slider("enemy_def"),
        }

    def _calc_attack_speed_diminishing(self, sources: list) -> float:
        """
        Calculate attack speed using diminishing returns formula.

        Formula: Total = 150 × (1 − (1−as1/150) × (1−as2/150) × ... × (1−asn/150))

        Iteratively: atk_spd += (150 - atk_spd) * (source / 150)

        Each source is applied against the remaining gap to the 150% cap.
        This means sources have diminishing returns as you approach the cap.

        Example: +15%, +10%, +7%, +5% = 33.884% total
        150 × (1 - (1-15/150) × (1-10/150) × (1-7/150) × (1-5/150)) = 33.884%

        Args:
            sources: List of (source_name, value) tuples where value is in percent (e.g., 7 for 7%)

        Returns:
            Total attack speed percentage
        """
        ATK_SPD_CAP = 150.0
        atk_spd = 0.0

        for source_name, source_value in sources:
            if source_value > 0:
                # Apply diminishing returns: each source multiplies against remaining gap
                # Divide by 150 (the cap), not 100!
                gain = (ATK_SPD_CAP - atk_spd) * (source_value / ATK_SPD_CAP)
                atk_spd += gain

        return min(atk_spd, ATK_SPD_CAP)

    def _get_damage_stats(self):
        """Get combined stats from all sources: base stats, equipment, potentials, weapons, artifacts, hero power, guild, companions, passives, maple rank."""
        base = self._get_base_stats()
        pot = self.get_potential_stats_total()
        weapon = self.get_weapon_stats_total()
        artifact = self.get_artifact_stats_total()
        hero_power = self.get_hero_power_stats_total()  # Ability lines (rerollable)
        hero_power_passive = self.get_hero_power_passive_stats_total()  # Passive stats (leveled)
        equip_base = self.get_equipment_base_stats_total()
        guild = self.get_guild_stats_total()
        companion = self.get_companion_stats_total()
        passive = self.get_passive_stats_total()
        maple_rank = self.get_maple_rank_stats_total()

        # Apply weapon ATK% to base attack
        # Weapon ATK% multiplies the base attack value
        weapon_atk_percent = weapon.get("weapon_atk_percent", 0)
        modified_base_atk = base["base_atk"] * (1 + weapon_atk_percent / 100)

        # Map artifact stats to damage calc stats
        # Artifact keys: damage, boss_damage, crit_damage, def_pen, normal_damage,
        #                hex_damage_per_stack, final_damage_conditional, main_stat_flat, attack_flat, main_stat
        artifact_damage = artifact.get("damage", 0) * 100  # Convert decimal to percent
        artifact_boss_damage = artifact.get("boss_damage", 0) * 100
        artifact_crit_damage = artifact.get("crit_damage", 0) * 100
        artifact_def_pen = artifact.get("def_pen", 0) * 100
        artifact_main_stat_flat = artifact.get("main_stat_flat", 0)
        artifact_main_stat_pct = artifact.get("main_stat", 0) * 100  # Artifact potentials: main stat % (stored as decimal)
        artifact_attack_flat = artifact.get("attack_flat", 0)

        # Map hero power ABILITY LINE stats (already in percent form, except main_stat which is flat)
        hp_damage = hero_power.get("damage", 0)
        hp_boss_damage = hero_power.get("boss_damage", 0)
        hp_crit_damage = hero_power.get("crit_damage", 0)
        hp_def_pen = hero_power.get("def_pen", 0)
        hp_main_stat_flat = hero_power.get("main_stat_pct", 0)  # This is actually FLAT main stat applied before DEX%!
        hp_attack_pct = hero_power.get("attack_pct", 0)

        # Map hero power PASSIVE stats (leveled, not rerolled)
        # These are flat bonuses from Hero Power Stage 6 passive stat levels
        hpp_main_stat_flat = hero_power_passive.get("main_stat_flat", 0)
        hpp_damage = hero_power_passive.get("damage_percent", 0)
        hpp_attack_flat = hero_power_passive.get("attack_flat", 0)
        hpp_accuracy = hero_power_passive.get("accuracy", 0)
        # hpp_max_hp and hpp_defense are not currently used in damage calc

        # Map equipment base stats (already amplified by starforce)
        equip_boss_damage = equip_base.get("boss_damage", 0)
        equip_crit_damage = equip_base.get("crit_damage", 0)
        equip_damage_pct = equip_base.get("damage_pct", 0)
        equip_final_damage = equip_base.get("final_damage", 0)
        equip_main_stat = equip_base.get("main_stat", 0)
        # Equipment attack has two sources:
        # 1. Main attack stat (base_attack × main_amplify) - the primary attack value
        # 2. Sub attack flat (sub_attack_flat × sub_amplify) - the sub stat bonus
        equip_attack_main = equip_base.get("attack", 0)  # Main attack stat with main amplify
        equip_attack_sub = equip_base.get("attack_flat", 0)  # Sub stat flat attack with sub amplify
        equip_attack_total = equip_attack_main + equip_attack_sub  # Total flat attack from equipment

        # Map guild stats (already in percent form)
        # Note: guild main_stat_pct is NOT used - only cube potentials and artifact potentials provide DEX%
        guild_damage = guild.get("damage", 0)
        guild_boss_damage = guild.get("boss_damage", 0)
        guild_crit_damage = guild.get("crit_damage", 0)
        guild_def_pen = guild.get("def_pen", 0)
        guild_final_damage = guild.get("final_damage", 0)
        guild_attack_flat = guild.get("attack_flat", 0)

        # Map companion stats
        # Inventory effects: damage (from 3rd/4th job), flat_main_stat (from 2nd job)
        # On-equip effects: boss_damage, normal_damage, crit_rate, min_dmg_mult, max_dmg_mult, attack_speed
        comp_damage = companion.get("damage", 0)  # Inventory damage % from 3rd/4th job
        comp_flat_main_stat = companion.get("flat_main_stat", 0)  # Inventory flat DEX from 2nd job
        comp_boss_damage = companion.get("boss_damage", 0)  # On-equip
        comp_crit_rate = companion.get("crit_rate", 0)  # On-equip
        comp_min_dmg_mult = companion.get("min_dmg_mult", 0)  # On-equip
        comp_max_dmg_mult = companion.get("max_dmg_mult", 0)  # On-equip
        comp_normal_damage = companion.get("normal_damage", 0)  # On-equip
        # Note: companions don't provide def_pen, final_damage, attack_pct, crit_damage, or main_stat_pct
        comp_def_pen = 0
        comp_final_damage = 0
        comp_attack_pct = 0
        comp_crit_damage = 0
        comp_main_stat_pct = 0

        # Map passive stats from skills.py
        # Global mastery stats (fixed per level) + PASSIVE_STAT skill contributions
        passive_crit_rate = passive.get("crit_rate", 0)  # critical_shot + mastery
        passive_attack_speed = passive.get("attack_speed", 0)  # archer_mastery + bow_acceleration + mastery
        passive_min_dmg_mult = passive.get("min_dmg_mult", 0)  # bow_mastery
        passive_dex_flat = passive.get("dex_flat", 0)  # soul_arrow
        passive_main_stat_flat = passive.get("main_stat_flat", 0)  # mastery (+30 DEX)
        passive_basic_attack_dmg = passive.get("basic_attack_damage", 0)  # physical_training + mastery
        passive_final_damage = passive.get("final_damage", 0)  # extreme_archery + armor_break
        passive_attack_pct = passive.get("attack_pct", 0)  # marksmanship + illusion_step
        passive_skill_damage = passive.get("skill_damage", 0)  # bow_expert + mastery
        passive_def_pen = passive.get("def_pen", 0)  # armor_break
        passive_max_dmg_mult = passive.get("max_dmg_mult", 0)  # mastery
        passive_accuracy = passive.get("accuracy", 0)  # mastery
        # Note: skills.py doesn't provide damage%, boss_damage%, crit_damage%, main_stat_pct
        # These were incorrect in the old passives.py
        passive_damage = 0
        passive_boss_damage = 0
        passive_crit_damage = 0
        passive_main_stat_pct = 0

        # Map Maple Rank stats (already in percent form)
        mr_main_stat_flat = maple_rank.get("main_stat_flat", 0)
        mr_damage = maple_rank.get("damage_percent", 0)
        mr_boss_damage = maple_rank.get("boss_damage", 0)
        mr_normal_damage = maple_rank.get("normal_damage", 0)
        mr_crit_damage = maple_rank.get("crit_damage", 0)
        mr_crit_rate = maple_rank.get("crit_rate", 0)
        mr_skill_damage = maple_rank.get("skill_damage", 0)
        mr_min_dmg_mult = maple_rank.get("min_dmg_mult", 0)
        mr_max_dmg_mult = maple_rank.get("max_dmg_mult", 0)
        mr_attack_speed = maple_rank.get("attack_speed", 0)
        mr_accuracy = maple_rank.get("accuracy", 0)
        # Note: Maple Rank doesn't provide def_pen, final_damage, attack_pct, or main_stat_pct
        mr_def_pen = 0
        mr_final_damage = 0
        mr_attack_pct = 0
        mr_main_stat_pct = 0

        # Calculate flat attack from all sources (before ATK% multiplier)
        # Equipment attack includes main attack stat (with main amplify) + sub attack flat (with sub amplify)
        # Companion flat attack from Basic/1st job inventory effects and on-equip
        comp_flat_attack = companion.get("flat_attack", 0)
        raw_flat_attack = base["base_atk"] + artifact_attack_flat + equip_attack_total + guild_attack_flat + comp_flat_attack + hpp_attack_flat

        # ATK% only comes from weapons
        total_attack_pct = weapon_atk_percent

        # Apply attack% multiplier to flat attack
        modified_base_atk = raw_flat_attack * (1 + total_attack_pct / 100)

        # Defense penetration stacks multiplicatively
        # total_def_pen = 1 - (1 - source1) * (1 - source2) * ...
        base_def_pen = (base["defense_pen"] + pot["defense_pen"]) / 100
        art_def_pen = artifact_def_pen / 100
        hp_def_pen_decimal = hp_def_pen / 100
        guild_def_pen_decimal = guild_def_pen / 100
        comp_def_pen_decimal = comp_def_pen / 100
        passive_def_pen_decimal = passive_def_pen / 100
        combined_def_pen = 1 - (1 - base_def_pen) * (1 - art_def_pen) * (1 - hp_def_pen_decimal) * (1 - guild_def_pen_decimal) * (1 - comp_def_pen_decimal) * (1 - passive_def_pen_decimal)
        combined_def_pen_percent = combined_def_pen * 100

        # DEX% only comes from cube potentials and artifact potentials
        # Guild, Companion, Passive, and Maple Rank don't provide DEX% in this game
        # (NOTE: hp_main_stat_flat is flat, not %)
        # artifact_main_stat_pct already calculated above from artifact.get("main_stat", 0) * 100

        # Sum damage % from all sources (including Hero Power passive damage %)
        total_damage_pct = artifact_damage + hp_damage + hpp_damage + equip_damage_pct + guild_damage + comp_damage + passive_damage + mr_damage

        # Sum boss damage from all sources
        total_boss_damage = artifact_boss_damage + hp_boss_damage + equip_boss_damage + guild_boss_damage + comp_boss_damage + passive_boss_damage + mr_boss_damage

        # Sum crit damage from all sources
        total_crit_damage = artifact_crit_damage + hp_crit_damage + equip_crit_damage + guild_crit_damage + comp_crit_damage + passive_crit_damage + mr_crit_damage

        # Sum crit rate from all sources (NEW - for Maple Rank integration)
        total_crit_rate = comp_crit_rate + passive_crit_rate + mr_crit_rate

        # Sum normal monster damage from all sources (NEW - for Maple Rank integration)
        total_normal_damage = comp_normal_damage + mr_normal_damage

        # Calculate attack speed using diminishing returns formula
        # Formula: atk_spd += (150 - atk_spd) * (source / 100)
        # Each source is applied against the remaining gap to 150% cap
        atk_spd_sources = []
        # Add passive skill attack speed (archer_mastery + bow_acceleration + mastery)
        if passive_attack_speed > 0:
            atk_spd_sources.append(("Passive Skills", passive_attack_speed))
        # Add Maple Rank attack speed
        if mr_attack_speed > 0:
            atk_spd_sources.append(("Maple Rank", mr_attack_speed))
        # Add equipment potential attack speed
        pot_attack_speed = pot.get("attack_speed", 0)
        if pot_attack_speed > 0:
            atk_spd_sources.append(("Equipment Potentials", pot_attack_speed))
        # Add companion on-equip attack speed sources (each companion separately)
        comp_atk_spd_sources = self.companion_config.get_attack_speed_sources()
        atk_spd_sources.extend(comp_atk_spd_sources)
        # Calculate total with diminishing returns
        total_attack_speed = self._calc_attack_speed_diminishing(atk_spd_sources)

        # Get manual stat adjustments
        adj = self.manual_stat_adjustments

        # Add all stat sources together (including manual adjustments)
        return {
            "base_atk": modified_base_atk + adj.get("attack_flat", 0),
            "attack_flat": raw_flat_attack + adj.get("attack_flat", 0),  # Flat attack before ATK% multiplier
            "attack_percent": total_attack_pct + passive_attack_pct,  # ATK% from weapons + passive skills (marksmanship + illusion_step)
            "dex_flat": base["dex_flat"] + pot["dex_flat"] + artifact_main_stat_flat + equip_main_stat + comp_flat_main_stat + mr_main_stat_flat + hpp_main_stat_flat + hp_main_stat_flat + passive_dex_flat + passive_main_stat_flat + adj.get("dex_flat", 0),
            "dex_percent": base["dex_percent"] + pot["dex_percent"] + artifact_main_stat_pct + adj.get("dex_percent", 0),
            "damage_percent": base["damage_percent"] + pot["damage_percent"] + total_damage_pct + adj.get("damage_percent", 0),
            "hex_stacks": base["hex_stacks"],
            "damage_amp": base["damage_amp"],
            "boss_damage": base["boss_damage"] + total_boss_damage + adj.get("boss_damage", 0),
            # FD sources are MULTIPLICATIVE with each other: (1+A) × (1+B) × (1+C) × ...
            # Each line/source is a separate element so 8% FD always = 8% DPS gain
            # pot["final_damage_lines"] is a list of individual FD lines from potentials
            "fd_sources": (
                pot["final_damage_lines"] +  # Each potential FD line is multiplicative
                [equip_final_damage] +       # Equipment special potential FD
                [passive_final_damage] +     # Passive skills FD (Extreme Archery + Armor Break)
                [base["fd_sources"][3]] +    # Guild FD (manual slider at index 3)
                [adj.get("final_damage", 0)] # Manual adjustment FD
            ),
            "crit_damage": base["crit_damage"] + pot["crit_damage"] + total_crit_damage + adj.get("crit_damage", 0),
            "defense_pen": combined_def_pen_percent + adj.get("defense_pen", 0),
            "enemy_def": base["enemy_def"],
            # Stats from multiple sources (for display/tracking, some not yet in damage formula)
            "crit_rate": total_crit_rate + adj.get("crit_rate", 0),
            "normal_damage": total_normal_damage + adj.get("normal_damage", 0),
            "skill_damage": mr_skill_damage + passive_skill_damage + adj.get("skill_damage", 0),  # Maple Rank + passive (bow_expert + mastery) + manual
            "basic_attack_damage": passive_basic_attack_dmg,  # Passive (physical_training + mastery)
            "min_dmg_mult": pot["min_dmg_mult"] + mr_min_dmg_mult + comp_min_dmg_mult + passive_min_dmg_mult + adj.get("min_dmg_mult", 0),  # Potentials + Maple Rank + companions + passive (bow_mastery) + manual
            "max_dmg_mult": pot["max_dmg_mult"] + mr_max_dmg_mult + comp_max_dmg_mult + passive_max_dmg_mult + adj.get("max_dmg_mult", 0),  # Potentials + Maple Rank + companions + passive (mastery) + manual
            "attack_speed": total_attack_speed + adj.get("attack_speed", 0),
            "accuracy": mr_accuracy + hpp_accuracy + passive_accuracy,  # Maple Rank + Hero Power Passive + passive skills (mastery)
            "skill_cd": pot.get("skill_cd", 0),  # Skill Cooldown Reduction from hat special potential
        }

    def _calc_damage(self, stats):
        # Get combat mode value for calculate_damage
        combat_mode_str = self.combat_mode.value if hasattr(self.combat_mode, 'value') else str(self.combat_mode)
        return calculate_damage(
            stats["base_atk"], stats["dex_flat"], stats["dex_percent"],
            stats["damage_percent"], stats["hex_stacks"], stats["damage_amp"],
            stats["fd_sources"], stats["crit_damage"], stats["defense_pen"],
            stats["enemy_def"], stats["boss_damage"],
            stats.get("min_dmg_mult", 0), stats.get("max_dmg_mult", 0),
            stats.get("attack_speed", 0),
            stats.get("normal_damage", 0),
            combat_mode_str
        )["total"]

    def _calc_skill_based_dps(self, stats) -> float:
        """Calculate DPS using the skill-based DPSCalculator.

        This method provides more accurate DPS calculations that account for:
        - Individual skill damage and cooldowns
        - Skill CD reduction from hat special potential
        - Attack speed effects on skill rotations
        - Proc rates and summon uptimes
        """
        # Get all skills bonus from potentials
        pot = self.get_potential_stats_total()
        all_skills = int(pot.get("all_skills", 0)) + self.current_all_skills

        # Create character at current level with all skills bonus
        char = create_character_at_level(self.character_level, all_skills)

        # Set character stats from our damage stats
        char.attack = stats["base_atk"]
        char.main_stat_flat = stats["dex_flat"]
        char.main_stat_pct = stats["dex_percent"]
        char.damage_pct = stats["damage_percent"]
        char.boss_damage_pct = stats["boss_damage"]
        char.crit_rate = stats.get("crit_rate", 50)
        char.crit_damage = stats["crit_damage"]
        char.defense_pen = stats["defense_pen"]
        char.attack_speed_pct = stats.get("attack_speed", 0)
        # FD sources are multiplicative - calculate total as (1+a)*(1+b)*... - 1
        fd_mult = 1.0
        for fd in stats["fd_sources"]:
            fd_mult *= (1 + fd / 100)
        char.final_damage_pct = (fd_mult - 1) * 100
        char.min_dmg_mult = stats.get("min_dmg_mult", 0)
        char.max_dmg_mult = stats.get("max_dmg_mult", 0)
        char.skill_damage_pct = stats.get("skill_damage", 0)
        char.basic_attack_dmg_pct = stats.get("basic_attack_damage", 0)

        # Set skill CD reduction from hat special potential
        char.skill_cd_reduction = stats.get("skill_cd", 0)

        # Calculate DPS using the skill calculator
        calc = DPSCalculator(char)
        result = calc.calculate_total_dps()

        return result.total_dps

    def update_damage(self):
        stats = self._get_damage_stats()

        # Choose calculation method based on toggle
        if self.use_skill_based_dps.get():
            result = self._calc_skill_based_dps(stats)
            calc_mode = "Skill-Based"
        else:
            result = self._calc_damage(stats)
            calc_mode = "Simple"

        combat_mode_str = self.combat_mode.value if hasattr(self.combat_mode, 'value') else str(self.combat_mode)
        full = calculate_damage(
            stats["base_atk"], stats["dex_flat"], stats["dex_percent"],
            stats["damage_percent"], stats["hex_stacks"], stats["damage_amp"],
            stats["fd_sources"], stats["crit_damage"], stats["defense_pen"],
            stats["enemy_def"], stats["boss_damage"],
            stats.get("min_dmg_mult", 0), stats.get("max_dmg_mult", 0),
            stats.get("attack_speed", 0),
            stats.get("normal_damage", 0),
            combat_mode_str
        )

        self.damage_label.config(text=f"Total DPS: {result:,.0f} ({calc_mode})")

        if self.baseline_damage and self.baseline_damage > 0:
            change = ((result / self.baseline_damage) - 1) * 100
            color = '#00ff88' if change >= 0 else '#ff4444'
            sign = '+' if change >= 0 else ''
            self.change_label.config(text=f"  {sign}{change:.2f}% from baseline", fg=color)

        # Include min/max damage range multiplier and attack speed in breakdown if present
        dmg_range = full.get('dmg_range_mult', 1.0)
        atk_spd = full.get('atk_spd_mult', 1.0)

        # Build breakdown string with optional multipliers
        breakdown = f"x{full['stat_mult']:.2f} Stat | x{full['damage_mult']:.2f} Dmg | x{full['fd_mult']:.2f} FD | x{full['crit_mult']:.2f} CD"
        if dmg_range > 1.0:
            breakdown += f" | x{dmg_range:.2f} Range"
        if atk_spd > 1.0:
            breakdown += f" | x{atk_spd:.2f} AtkSpd"
        breakdown += f" | x{full['def_mult']:.3f} Def"
        self.breakdown_label.config(text=breakdown)

        # Update priority chart
        priorities = self._calc_stat_priorities(stats)
        self.priority_chart.update(priorities)

        # Update recommendation (guard against empty priorities)
        if len(priorities) >= 2:
            sorted_p = sorted(priorities, key=lambda x: x[1], reverse=True)
            best, second = sorted_p[0], sorted_p[1]
            gap = best[1] - second[1]
            if gap > 0.5:
                self.recommendation_label.config(
                    text=f"Focus on {best[0]}! +{gap:.2f}% more DPS/investment than {second[0]}.")
            else:
                self.recommendation_label.config(
                    text=f"{best[0]} and {second[0]} are close. Either is good.")
        else:
            self.recommendation_label.config(
                text="Configure stat sources to see recommendations.")

        # Update potential stats display
        self.update_potential_stats_display()

        # Update calculated attack display
        self.update_calc_attack_display()

    def update_calc_attack_display(self):
        """Update the calculated attack display showing flat attack from sources."""
        # Get all flat attack sources
        artifact = self.get_artifact_stats_total()
        equip_base = self.get_equipment_base_stats_total()
        guild = self.get_guild_stats_total()
        companion = self.get_companion_stats_total()
        hero_power_passive = self.get_hero_power_passive_stats_total()
        weapon = self.get_weapon_stats_total()

        # Equipment attack has two sources
        equip_attack_main = equip_base.get("attack", 0)  # Main attack stat
        equip_attack_sub = equip_base.get("attack_flat", 0)  # Sub stat flat attack
        equip_attack_total = equip_attack_main + equip_attack_sub

        # Calculate raw flat attack from all sources
        artifact_attack = artifact.get("attack_flat", 0)
        guild_attack = guild.get("attack_flat", 0)
        comp_attack = companion.get("flat_attack", 0)
        hpp_attack = hero_power_passive.get("attack_flat", 0)

        raw_flat_attack = artifact_attack + equip_attack_total + guild_attack + comp_attack + hpp_attack

        # Weapon ATK% multiplier
        weapon_atk_pct = weapon.get("weapon_atk_percent", 0)
        weapon_mult = 1 + weapon_atk_pct / 100

        # Final base_atk = raw_flat_attack × weapon_mult
        calc_base_atk = raw_flat_attack * weapon_mult

        # Get actual in-game attack and divide by ATK% to get comparable flat attack
        try:
            actual_attack_str = self.actual_attack_var.get().replace(",", "").replace("M", "000000").replace("K", "000")
            actual_attack = float(actual_attack_str) if actual_attack_str else 0
        except (ValueError, AttributeError):
            actual_attack = 0

        # Actual flat attack = actual / weapon_mult (reverse the ATK% multiplication)
        actual_flat_attack = actual_attack / weapon_mult if weapon_mult > 0 else 0

        # Compare calculated flat attack to actual flat attack
        flat_diff = calc_base_atk - actual_flat_attack
        flat_diff_pct = (flat_diff / actual_flat_attack * 100) if actual_flat_attack > 0 else 0

        text = f"── Calculated Sources ──\n"
        text += f"  Equipment: {equip_attack_total:,.0f} (main:{equip_attack_main:,.0f} + sub:{equip_attack_sub:,.0f})\n"
        text += f"  Artifact: {artifact_attack:,.0f}\n"
        text += f"  Guild: {guild_attack:,.0f}\n"
        text += f"  Companion: {comp_attack:,.0f}\n"
        text += f"  Hero Power: {hpp_attack:,.0f}\n"
        text += f"  Raw Flat Total: {raw_flat_attack:,.0f}\n"
        text += f"── Weapon ATK% ──\n"
        text += f"  Weapon ATK%: +{weapon_atk_pct:.1f}% (×{weapon_mult:.2f})\n"
        text += f"── Comparison ──\n"
        text += f"  Calc (flat×ATK%): {calc_base_atk:,.0f}\n"
        if actual_attack > 0:
            text += f"  Actual ÷ ATK%:   {actual_flat_attack:,.0f}\n"
            text += f"  Difference:       {'+' if flat_diff >= 0 else ''}{flat_diff:,.0f} ({flat_diff_pct:+.1f}%)"

            if abs(flat_diff_pct) > 5:
                color = '#ff4444'  # Red - significant difference
            elif abs(flat_diff_pct) > 2:
                color = '#ffaa00'  # Orange - moderate difference
            else:
                color = '#00ff88'  # Green - close match
        else:
            text += f"  (Enter actual ATK above to compare)"
            color = '#aaa'

        self.calc_attack_label.config(text=text, fg=color)

    def update_potential_stats_display(self):
        """Update the display showing stats from equipment potentials."""
        base = self._get_base_stats()
        pot = self.get_potential_stats_total()
        # Check if any stat has value (handle list for final_damage_lines)
        has_any = any(
            (len(v) > 0 if isinstance(v, list) else v > 0)
            for v in pot.values()
        )

        if not has_any:
            self.potential_stats_label.config(
                text="No potentials set yet.\nUse Cube Optimizer tab to set potentials!")
            return

        # Show Base + Potential = Total for each stat
        text = "Stats (Base + Potential = Total):\n"

        # Main Stat %
        base_dex = base["dex_percent"]
        pot_dex = pot["dex_percent"]
        if pot_dex > 0:
            text += f"  Main Stat %: {base_dex:.1f} + {pot_dex:.1f} = {base_dex + pot_dex:.1f}%\n"

        # Main Stat (Flat)
        base_flat = base["dex_flat"]
        pot_flat = pot["dex_flat"]
        if pot_flat > 0:
            text += f"  Main Stat: {base_flat:,.0f} + {pot_flat:,.0f} = {base_flat + pot_flat:,.0f}\n"

        # Damage %
        base_dmg = base["damage_percent"]
        pot_dmg = pot["damage_percent"]
        if pot_dmg > 0:
            text += f"  Damage: {base_dmg:.1f} + {pot_dmg:.1f} = {base_dmg + pot_dmg:.1f}%\n"

        # Crit Damage %
        base_cd = base["crit_damage"]
        pot_cd = pot["crit_damage"]
        if pot_cd > 0:
            text += f"  Crit Dmg: {base_cd:.1f} + {pot_cd:.1f} = {base_cd + pot_cd:.1f}%\n"

        # Defense Pen %
        base_pen = base["defense_pen"]
        pot_pen = pot["defense_pen"]
        if pot_pen > 0:
            text += f"  Def Pen: {base_pen:.1f} + {pot_pen:.1f} = {base_pen + pot_pen:.1f}%\n"

        # Final Damage % (now fully calculated, show pot contribution)
        # Each FD line is multiplicative, but for display we show total contribution
        pot_fd_lines = pot["final_damage_lines"]
        if pot_fd_lines:
            # Calculate total multiplicative FD: (1+a)*(1+b)*... - 1
            pot_fd_mult = 1.0
            for fd in pot_fd_lines:
                pot_fd_mult *= (1 + fd / 100)
            pot_fd_total = (pot_fd_mult - 1) * 100
            text += f"  Final Dmg: +{pot_fd_total:.1f}% ({len(pot_fd_lines)} lines, multiplicative)\n"

        # Crit Rate (informational, not in damage calc currently)
        if pot["crit_rate"] > 0:
            text += f"  Crit Rate: +{pot['crit_rate']:.1f}% (from pot)\n"

        # All Skills
        if pot["all_skills"] > 0:
            all_skills_value = self.get_all_skills_dps_value()
            text += f"  All Skills: +{pot['all_skills']:.0f} (→ +{pot['all_skills'] * all_skills_value:.2f}% DPS)\n"

        self.potential_stats_label.config(text=text.strip())

    def _get_calculated_stats_for_priority(self):
        """
        Get stats calculated purely from modeled sources (not sliders).
        This is used for the priority chart to show recommendations based on
        your actual character, not test values from sliders.
        """
        # Get all sources
        pot = self.get_potential_stats_total()
        weapon = self.get_weapon_stats_total()
        artifact = self.get_artifact_stats_total()
        hero_power = self.get_hero_power_stats_total()
        hero_power_passive = self.get_hero_power_passive_stats_total()
        equip_base = self.get_equipment_base_stats_total()
        guild = self.get_guild_stats_total()
        companion = self.get_companion_stats_total()
        passive = self.get_passive_stats_total()
        maple_rank = self.get_maple_rank_stats_total()
        equip_sets = self.get_equipment_sets_stats_total()

        # Equipment attack
        equip_attack_main = equip_base.get("attack", 0)
        equip_attack_sub = equip_base.get("attack_flat", 0)
        equip_attack_total = equip_attack_main + equip_attack_sub

        # Flat attack from all sources
        artifact_attack = artifact.get("attack_flat", 0)
        guild_attack = guild.get("attack_flat", 0)
        comp_attack = companion.get("flat_attack", 0)
        hpp_attack = hero_power_passive.get("attack_flat", 0)
        raw_flat_attack = equip_attack_total + artifact_attack + guild_attack + comp_attack + hpp_attack

        # Weapon ATK%
        weapon_atk_pct = weapon.get("weapon_atk_percent", 0)
        base_atk = raw_flat_attack * (1 + weapon_atk_pct / 100)

        # Flat DEX
        flat_dex = (
            pot.get("dex_flat", 0) +
            equip_base.get("main_stat", 0) +
            artifact.get("main_stat_flat", 0) +
            companion.get("flat_main_stat", 0) +
            maple_rank.get("main_stat_flat", 0) +
            hero_power_passive.get("main_stat_flat", 0) +
            hero_power.get("main_stat_pct", 0) +  # Hero Power ability lines provide FLAT main stat (despite the name)
            passive.get("dex_flat", 0) +
            passive.get("main_stat_flat", 0) +
            equip_sets.get("main_stat_flat", 0)  # Medals + Costumes
        )

        # DEX % (only from cube potentials and artifact potentials)
        dex_pct = (
            pot.get("dex_percent", 0) +
            artifact.get("main_stat", 0) * 100  # Artifact potentials store as decimal
        )

        # Damage %
        damage_pct = (
            pot.get("damage_percent", 0) +
            artifact.get("damage", 0) * 100 +
            hero_power.get("damage", 0) +
            hero_power_passive.get("damage_percent", 0) +
            equip_base.get("damage_pct", 0) +
            guild.get("damage", 0) +
            companion.get("damage", 0) +
            maple_rank.get("damage_percent", 0)
        )

        # Boss Damage
        boss_damage = (
            artifact.get("boss_damage", 0) * 100 +
            hero_power.get("boss_damage", 0) +
            equip_base.get("boss_damage", 0) +
            guild.get("boss_damage", 0) +
            companion.get("boss_damage", 0) +
            maple_rank.get("boss_damage", 0)
        )

        # Crit Damage
        crit_damage = (
            pot.get("crit_damage", 0) +
            artifact.get("crit_damage", 0) * 100 +
            hero_power.get("crit_damage", 0) +
            equip_base.get("crit_damage", 0) +
            guild.get("crit_damage", 0) +
            passive.get("crit_damage", 0) +
            maple_rank.get("crit_damage", 0)
        )

        # Defense Pen (multiplicative)
        def_pen_sources = [
            pot.get("defense_pen", 0) / 100,
            artifact.get("def_pen", 0),
            hero_power.get("def_pen", 0) / 100,
            guild.get("def_pen", 0) / 100,
            passive.get("def_pen", 0) / 100,
        ]
        remaining = 1.0
        for src in def_pen_sources:
            if src > 0:
                remaining *= (1 - src)
        defense_pen = (1 - remaining) * 100

        # Final Damage - each line/source is multiplicative
        # pot["final_damage_lines"] is a list of individual FD lines
        pot_fd_lines = pot.get("final_damage_lines", [])
        equip_fd = equip_base.get("final_damage", 0)
        passive_fd = passive.get("final_damage", 0)
        guild_fd = guild.get("final_damage", 0)
        # Calculate total multiplicative FD for display: (1+a)*(1+b)*... - 1
        total_fd_mult = 1.0
        for fd in pot_fd_lines:
            total_fd_mult *= (1 + fd / 100)
        total_fd_mult *= (1 + equip_fd / 100) * (1 + passive_fd / 100) * (1 + guild_fd / 100)
        final_damage = (total_fd_mult - 1) * 100

        # Min/Max Damage Multiplier (includes potentials from cubes)
        min_dmg_mult = (
            pot.get("min_dmg_mult", 0) +
            maple_rank.get("min_dmg_mult", 0) +
            companion.get("min_dmg_mult", 0) +
            passive.get("min_dmg_mult", 0)
        )
        max_dmg_mult = (
            pot.get("max_dmg_mult", 0) +
            maple_rank.get("max_dmg_mult", 0) +
            companion.get("max_dmg_mult", 0) +
            passive.get("max_dmg_mult", 0)
        )

        # Crit Rate (from equipment sub stats, maple rank, companions, passives)
        crit_rate = (
            pot.get("crit_rate", 0) +
            equip_base.get("crit_rate", 0) +
            maple_rank.get("crit_rate", 0) +
            companion.get("crit_rate", 0) +
            passive.get("crit_rate", 0)
        )

        # Normal Damage (from equipment sub stats, maple rank, companions)
        normal_damage = (
            equip_base.get("normal_damage", 0) +
            maple_rank.get("normal_damage", 0) +
            companion.get("normal_damage", 0) +
            artifact.get("normal_damage", 0) * 100
        )

        # Skill Damage (from maple rank, passives)
        skill_damage = (
            maple_rank.get("skill_damage", 0) +
            passive.get("skill_damage", 0)
        )

        # Attack Speed (from maple rank, companions, passives)
        attack_speed = (
            maple_rank.get("attack_speed", 0) +
            companion.get("attack_speed", 0) +
            passive.get("attack_speed", 0)
        )

        # Accuracy (from maple rank, hero power passive, passives)
        accuracy = (
            maple_rank.get("accuracy", 0) +
            hero_power_passive.get("accuracy", 0) +
            passive.get("accuracy", 0)
        )

        return {
            "base_atk": base_atk,
            "attack_flat": raw_flat_attack,
            "weapon_atk_pct": weapon_atk_pct,
            "dex_flat": flat_dex,
            "dex_percent": dex_pct,
            "damage_percent": damage_pct,
            "hex_stacks": 3,  # Assume max hex stacks
            "damage_amp": 0,  # No modeled source yet
            "boss_damage": boss_damage,
            # FD sources are MULTIPLICATIVE: (1+A) × (1+B) × (1+C) × ...
            # Each potential FD line is a separate multiplicative source
            "fd_sources": pot_fd_lines + [equip_fd, passive_fd, guild_fd],
            "crit_damage": crit_damage,
            "defense_pen": defense_pen,
            "enemy_def": 0.752,  # Default enemy defense
            "min_dmg_mult": min_dmg_mult,
            "max_dmg_mult": max_dmg_mult,
            "crit_rate": crit_rate,
            "normal_damage": normal_damage,
            "skill_damage": skill_damage,
            "attack_speed": attack_speed,
            "accuracy": accuracy,
            "final_damage": final_damage,
        }

    def _calc_stat_priorities(self, stats):
        """
        Calculate DPS priority for each stat based on TYPICAL CUBE ROLL VALUES.

        Uses calculated stats from sources (not sliders) so the chart shows
        accurate recommendations for your actual character.

        Stats are weighted by typical Mystic tier cube roll values:
        - Damage %: 30% per line
        - Main Stat %: 15% per line
        - Crit Damage %: 15% per line
        - Boss Damage %: 30% per line (but rare)
        - Defense Pen %: ~10% per line (multiplicative)
        - Final Damage %: 8% per line (rare, excluded)
        - All Skills: +2 per line
        - Flat Attack: ~225 per line
        - Flat Main Stat: ~300 per line (Mystic)
        """
        # Use calculated stats from sources for accurate recommendations
        calc_stats = self._get_calculated_stats_for_priority()
        base = self._calc_damage(calc_stats)
        results = []

        # Guard against division by zero when stats aren't configured yet
        if base <= 0:
            # Return empty results - chart will show no bars
            return []

        # Get All Skills DPS value for conversion
        all_skills_dps_value = self.get_all_skills_dps_value()

        # Get weapon ATK% for flat attack calculation
        weapon_atk_pct = calc_stats.get("weapon_atk_pct", 0)
        weapon_mult = 1 + weapon_atk_pct / 100

        # Typical Mystic tier cube roll values for each stat
        # This makes the chart show "if I roll this stat, how much DPS do I gain?"
        TYPICAL_ROLL_VALUES = {
            "damage_percent": 30,      # Mystic Damage % line
            "dex_percent": 15,         # Mystic Main Stat % line
            "crit_damage": 15,         # Mystic Crit Damage % line
            "boss_damage": 30,         # Mystic Boss Damage % line
            "defense_pen": 10,         # ~10% per line (stacks multiplicatively)
            "dex_flat": 300,           # Mystic flat main stat (rare)
            "flat_atk": 225,           # Mystic flat attack line
            "all_skills": 2,           # +2 All Skills line (rare special)
            "weapon_atk": 10,          # Weapon level gain estimate
            "min_dmg_mult": 10,        # Maple Rank / companion source
            "max_dmg_mult": 10,        # Maple Rank / companion source
        }

        # Stats to test with their display names and colors
        tests = [
            ("Damage % (+30)", "damage_percent", "#4a9eff"),
            ("Main Stat % (+15)", "dex_percent", "#ff9f43"),
            ("Crit Damage (+15)", "crit_damage", "#ffd93d"),
            ("Boss Damage (+30)", "boss_damage", "#6bcb77"),
            ("Defense Pen (+10)", "defense_pen", "#9d65c9"),
            ("Min Dmg Mult (+10)", "min_dmg_mult", "#ff69b4"),
            ("Max Dmg Mult (+10)", "max_dmg_mult", "#ff1493"),
            ("Flat Main Stat (+300)", "dex_flat", "#a5b1c2"),
            ("Flat Attack (+225)", "flat_atk", "#ff9999"),
            ("All Skills (+2)", "all_skills", "#00ffcc"),
        ]

        for label, key, color in tests:
            mod = dict(calc_stats)
            mod["fd_sources"] = list(calc_stats["fd_sources"])
            roll_value = TYPICAL_ROLL_VALUES.get(key, 10)

            if key == "defense_pen":
                # Defense pen stacks multiplicatively
                remaining = 100 - mod[key]
                mod[key] = 100 - remaining * (1 - roll_value / 100)
            elif key == "dex_flat":
                mod[key] += roll_value
            elif key == "flat_atk":
                # Flat attack is multiplied by weapon ATK%
                mod["base_atk"] = calc_stats["base_atk"] + roll_value * weapon_mult
            elif key == "all_skills":
                # All Skills converts to FD via DPS value - add as new multiplicative source
                mod["fd_sources"] = list(mod["fd_sources"]) + [all_skills_dps_value * roll_value]
            elif key == "min_dmg_mult":
                mod[key] = mod.get(key, 0) + roll_value
            elif key == "max_dmg_mult":
                mod[key] = mod.get(key, 0) + roll_value
            else:
                mod[key] += roll_value

            gain = ((self._calc_damage(mod) / base) - 1) * 100
            results.append((label, gain, color))

        return results

    def set_damage_baseline(self):
        self.baseline_damage = self._calc_damage(self._get_damage_stats())
        self.change_label.config(text="  Baseline set!", fg='#ffd700')

    def load_calculated_baseline(self):
        """Load slider values from all calculated stat sources.

        This aggregates stats from: weapons, potentials, artifacts, hero power,
        maple rank, companions, guild, passives, and equipment base stats.
        The sliders will reflect the total calculated values.
        """
        # Get stats from all modeled sources
        pot = self.get_potential_stats_total()
        weapon = self.get_weapon_stats_total()
        artifact = self.get_artifact_stats_total()
        hero_power = self.get_hero_power_stats_total()
        hero_power_passive = self.get_hero_power_passive_stats_total()
        equip_base = self.get_equipment_base_stats_total()
        guild = self.get_guild_stats_total()
        companion = self.get_companion_stats_total()
        passive = self.get_passive_stats_total()
        maple_rank = self.get_maple_rank_stats_total()

        # Calculate flat attack (before ATK% multiplier)
        # Equipment attack has two sources:
        # 1. Main attack stat (base_attack × main_amplify) - the primary attack value
        # 2. Sub attack flat (sub_attack_flat × sub_amplify) - the sub stat bonus
        equip_attack_main = equip_base.get("attack", 0)
        equip_attack_sub = equip_base.get("attack_flat", 0)
        equip_attack_total = equip_attack_main + equip_attack_sub

        flat_attack = (
            artifact.get("attack_flat", 0) +
            equip_attack_total +
            guild.get("attack_flat", 0) +
            companion.get("flat_attack", 0) +
            hero_power_passive.get("attack_flat", 0)
        )

        # Weapon ATK% is the multiplier
        weapon_atk_pct = weapon.get("weapon_atk_percent", 0)

        # Total base_atk = flat_attack * (1 + weapon_atk_pct/100)
        total_base_atk = flat_attack * (1 + weapon_atk_pct / 100)

        # Flat DEX from all sources
        flat_dex = (
            pot.get("dex_flat", 0) +
            artifact.get("main_stat_flat", 0) +
            equip_base.get("main_stat", 0) +
            companion.get("flat_main_stat", 0) +
            maple_rank.get("main_stat_flat", 0) +
            hero_power_passive.get("main_stat_flat", 0) +
            hero_power.get("main_stat_pct", 0)  # Hero Power ability lines provide FLAT main stat (despite the name)
        )

        # DEX % from cube potentials and artifact potentials only
        dex_pct = (
            pot.get("dex_percent", 0) +
            artifact.get("main_stat", 0) * 100  # Artifact potentials store as decimal
        )

        # Damage % from all sources
        damage_pct = (
            pot.get("damage_percent", 0) +
            artifact.get("damage", 0) * 100 +  # Convert decimal to percent
            hero_power.get("damage", 0) +
            hero_power_passive.get("damage_percent", 0) +
            equip_base.get("damage_pct", 0) +
            guild.get("damage", 0) +
            companion.get("damage", 0) +
            passive.get("damage", 0) +
            maple_rank.get("damage_percent", 0)
        )

        # Boss Damage from all sources
        boss_damage = (
            artifact.get("boss_damage", 0) * 100 +
            hero_power.get("boss_damage", 0) +
            equip_base.get("boss_damage", 0) +
            guild.get("boss_damage", 0) +
            companion.get("boss_damage", 0) +
            passive.get("boss_damage", 0) +
            maple_rank.get("boss_damage", 0)
        )

        # Crit Damage from all sources
        crit_damage = (
            pot.get("crit_damage", 0) +
            artifact.get("crit_damage", 0) * 100 +
            hero_power.get("crit_damage", 0) +
            equip_base.get("crit_damage", 0) +
            guild.get("crit_damage", 0) +
            passive.get("crit_damage", 0) +
            maple_rank.get("crit_damage", 0)
        )

        # Defense Penetration - multiplicative stacking
        # total = 1 - (1-src1) * (1-src2) * ...
        def_pen_sources = [
            pot.get("defense_pen", 0) / 100,
            artifact.get("def_pen", 0),  # Already decimal
            hero_power.get("def_pen", 0) / 100,
            guild.get("def_pen", 0) / 100,
            passive.get("def_pen", 0) / 100,
        ]
        combined_def_pen = 1.0
        for src in def_pen_sources:
            combined_def_pen *= (1 - src)
        defense_pen = (1 - combined_def_pen) * 100

        # Set the slider values (FD is now fully calculated, only Guild FD is manual)
        calculated = {
            "base_atk": total_base_atk,
            "dex_flat": flat_dex,
            "dex_percent": dex_pct,
            "damage_percent": damage_pct,
            "boss_damage": boss_damage,
            "crit_damage": crit_damage,
            "defense_pen": defense_pen,
            "fd_guild": guild.get("final_damage", 0),  # Guild FD from modeled source
            # Keep current values for stats not calculated from sources
            "hex_stacks": self._get_damage_slider("hex_stacks"),
            "damage_amp": self._get_damage_slider("damage_amp"),
            "enemy_def": self._get_damage_slider("enemy_def"),
        }

        for k, v in calculated.items():
            if k in self.damage_sliders:
                self.damage_sliders[k].set(v)

        self.update_damage()
        self.set_damage_baseline()
        self.change_label.config(text="  Loaded from calculated sources!", fg='#00ff88')

    def reset_damage_defaults(self):
        defaults = {"base_atk": 50000, "dex_flat": 18700, "dex_percent": 126.5,
                   "damage_percent": 484.1, "hex_stacks": 3, "damage_amp": 23.2,
                   "boss_damage": 64.5, "fd_guild": 6,
                   "crit_damage": 184.5, "defense_pen": 60.9, "enemy_def": 0.752}
        for k, v in defaults.items():
            if k in self.damage_sliders:
                self.damage_sliders[k].set(v)
        self.update_damage()

    def set_enemy(self, defense):
        self.damage_sliders["enemy_def"].set(defense)
        self.update_damage()

    def _on_chapter_change(self, event=None):
        """Handle chapter selection change - update enemy defense."""
        chapter = self.chapter_var.get()
        if chapter in ENEMY_DEFENSE_VALUES:
            defense = ENEMY_DEFENSE_VALUES[chapter]
            self.set_enemy(defense)
            self.chapter_def_label.config(text=f"(Def: {defense:.3f})")
            # Also update the Character Stats tab defense label if it exists
            if hasattr(self, 'char_stats_def_label'):
                self.char_stats_def_label.config(text=f"(Def: {defense:.3f})")

    def open_manual_adjustments(self):
        """Open a popup window for manual stat adjustments."""
        popup = tk.Toplevel(self.root)
        popup.title("Manual Stat Adjustments")
        popup.geometry("500x600")
        popup.configure(bg='#1a1a2e')
        popup.transient(self.root)
        popup.grab_set()

        # Title
        tk.Label(popup, text="Manual Stat Adjustments",
                font=('Segoe UI', 14, 'bold'), bg='#1a1a2e', fg='#ffd700').pack(pady=10)

        tk.Label(popup, text="Add or subtract stats to fine-tune calculations.\nPositive = add, Negative = subtract",
                font=('Segoe UI', 9), bg='#1a1a2e', fg='#aaa').pack(pady=(0, 10))

        # Scrollable frame for stats
        canvas = tk.Canvas(popup, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(popup, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Stat definitions with display names and units
        stat_info = [
            ("dex_flat", "Flat DEX", ""),
            ("dex_percent", "DEX %", "%"),
            ("damage_percent", "Damage %", "%"),
            ("boss_damage", "Boss Damage %", "%"),
            ("normal_damage", "Normal Damage %", "%"),
            ("crit_damage", "Crit Damage %", "%"),
            ("crit_rate", "Crit Rate %", "%"),
            ("defense_pen", "Defense Pen %", "%"),
            ("final_damage", "Final Damage %", "%"),
            ("attack_flat", "Flat Attack", ""),
            ("attack_speed", "Attack Speed %", "%"),
            ("min_dmg_mult", "Min Damage Mult %", "%"),
            ("max_dmg_mult", "Max Damage Mult %", "%"),
            ("skill_damage", "Skill Damage %", "%"),
        ]

        # Create entry for each stat
        for stat_key, display_name, unit in stat_info:
            row = tk.Frame(scroll_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, pady=2, padx=5)

            tk.Label(row, text=f"{display_name}:", width=20, anchor=tk.W,
                    font=('Segoe UI', 10), bg='#2a2a4e', fg='#ccc').pack(side=tk.LEFT, padx=5)

            # Create or reuse StringVar
            if stat_key not in self.manual_stat_vars:
                self.manual_stat_vars[stat_key] = tk.StringVar(value=str(self.manual_stat_adjustments.get(stat_key, 0)))
            else:
                self.manual_stat_vars[stat_key].set(str(self.manual_stat_adjustments.get(stat_key, 0)))

            entry = tk.Entry(row, textvariable=self.manual_stat_vars[stat_key],
                           width=12, font=('Consolas', 10), bg='#1a1a2e', fg='#00ff88',
                           insertbackground='#00ff88', justify=tk.RIGHT)
            entry.pack(side=tk.LEFT, padx=5)

            tk.Label(row, text=unit, width=3, anchor=tk.W,
                    font=('Segoe UI', 9), bg='#2a2a4e', fg='#888').pack(side=tk.LEFT)

            # Current calculated value (for reference)
            try:
                stats = self._get_damage_stats()
                current_val = stats.get(stat_key, 0)
                tk.Label(row, text=f"(current: {current_val:,.1f})",
                        font=('Consolas', 8), bg='#2a2a4e', fg='#666').pack(side=tk.RIGHT, padx=5)
            except:
                pass

        # Buttons frame
        btn_frame = tk.Frame(popup, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=15, padx=10)

        def apply_adjustments():
            """Apply the manual adjustments and update damage."""
            for stat_key in self.manual_stat_adjustments:
                try:
                    val = float(self.manual_stat_vars.get(stat_key, tk.StringVar(value="0")).get())
                    self.manual_stat_adjustments[stat_key] = val
                except ValueError:
                    self.manual_stat_adjustments[stat_key] = 0.0
            self.save_manual_adjustments()
            self.update_damage()
            popup.destroy()

        def reset_adjustments():
            """Reset all adjustments to zero."""
            for stat_key in self.manual_stat_adjustments:
                self.manual_stat_adjustments[stat_key] = 0.0
                if stat_key in self.manual_stat_vars:
                    self.manual_stat_vars[stat_key].set("0")

        def cancel():
            popup.destroy()

        tk.Button(btn_frame, text="Apply", command=apply_adjustments,
                 bg='#4a9eff', fg='white', font=('Segoe UI', 10, 'bold'),
                 width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset All", command=reset_adjustments,
                 bg='#ff6b6b', fg='white', font=('Segoe UI', 10),
                 width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=cancel,
                 bg='#4a4a6a', fg='white', font=('Segoe UI', 10),
                 width=12).pack(side=tk.RIGHT, padx=5)

        # Summary at bottom
        summary_frame = tk.Frame(popup, bg='#1a1a2e')
        summary_frame.pack(fill=tk.X, pady=5, padx=10)

        active_adjustments = [(k, v) for k, v in self.manual_stat_adjustments.items() if v != 0]
        if active_adjustments:
            summary_text = "Active adjustments: " + ", ".join([f"{k}: {v:+.1f}" for k, v in active_adjustments])
            tk.Label(summary_frame, text=summary_text, font=('Consolas', 8),
                    bg='#1a1a2e', fg='#ffd700', wraplength=450).pack()

    def save_manual_adjustments(self):
        """Save manual stat adjustments to CSV."""
        try:
            with open(MANUAL_ADJUSTMENTS_SAVE_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["stat", "adjustment"])
                for stat_key, value in self.manual_stat_adjustments.items():
                    writer.writerow([stat_key, value])
        except Exception as e:
            print(f"Failed to save manual adjustments: {e}")

        # Also save actual stats
        self.save_actual_stats()

    def load_manual_adjustments(self):
        """Load manual stat adjustments from CSV."""
        if not os.path.exists(MANUAL_ADJUSTMENTS_SAVE_FILE):
            return
        try:
            with open(MANUAL_ADJUSTMENTS_SAVE_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stat_key = row.get("stat", "")
                    if stat_key in self.manual_stat_adjustments:
                        try:
                            self.manual_stat_adjustments[stat_key] = float(row.get("adjustment", 0))
                        except ValueError:
                            pass
        except Exception as e:
            print(f"Failed to load manual adjustments: {e}")

    def save_actual_stats(self):
        """Save actual stat values (from in-game) to CSV."""
        # Only save if actual_stat_vars has been initialized
        if not hasattr(self, 'actual_stat_vars') or not self.actual_stat_vars:
            return
        try:
            with open(ACTUAL_STATS_SAVE_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["stat", "value"])
                for stat_key, var in self.actual_stat_vars.items():
                    try:
                        value = var.get()
                        writer.writerow([stat_key, value])
                    except:
                        pass
        except Exception as e:
            print(f"Failed to save actual stats: {e}")

    def load_actual_stats(self):
        """Load actual stat values from CSV."""
        if not os.path.exists(ACTUAL_STATS_SAVE_FILE):
            return
        # Only load if actual_stat_vars has been initialized
        if not hasattr(self, 'actual_stat_vars') or not self.actual_stat_vars:
            return
        try:
            with open(ACTUAL_STATS_SAVE_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stat_key = row.get("stat", "")
                    if stat_key in self.actual_stat_vars:
                        try:
                            value = float(row.get("value", 0))
                            self.actual_stat_vars[stat_key].set(value)
                        except ValueError:
                            pass
        except Exception as e:
            print(f"Failed to load actual stats: {e}")

    def save_character_settings(self):
        """Save character settings (level, skill levels) to CSV."""
        try:
            with open(CHARACTER_SETTINGS_SAVE_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["setting", "value"])
                writer.writerow(["character_level", self.character_level])
                writer.writerow(["all_skills", self.current_all_skills])
                writer.writerow(["combat_mode", self.combat_mode.value])
                # Save base skill levels (before All Skills bonus)
                if hasattr(self, 'char_settings_skill_1st_var'):
                    writer.writerow(["skill_1st", self.char_settings_skill_1st_var.get()])
                    writer.writerow(["skill_2nd", self.char_settings_skill_2nd_var.get()])
                    writer.writerow(["skill_3rd", self.char_settings_skill_3rd_var.get()])
                    writer.writerow(["skill_4th", self.char_settings_skill_4th_var.get()])
        except Exception as e:
            print(f"Failed to save character settings: {e}")

    def load_character_settings(self):
        """Load character settings from CSV."""
        if not os.path.exists(CHARACTER_SETTINGS_SAVE_FILE):
            self._update_skill_totals_display()
            return
        try:
            with open(CHARACTER_SETTINGS_SAVE_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    setting = row.get("setting", "")
                    try:
                        value = int(float(row.get("value", 0)))
                    except ValueError:
                        value = 0

                    if setting == "character_level":
                        self.character_level = max(1, min(300, value))
                        if hasattr(self, 'char_settings_level_var'):
                            self.char_settings_level_var.set(self.character_level)
                        # Also update damage calc tab slider if it exists
                        if hasattr(self, 'level_slider'):
                            self.level_slider.set(self.character_level)
                            self.level_var.set(str(self.character_level))
                    elif setting == "all_skills":
                        self.current_all_skills = max(0, min(200, value))
                        if hasattr(self, 'char_settings_all_skills_var'):
                            self.char_settings_all_skills_var.set(self.current_all_skills)
                        # Also update damage calc tab slider if it exists
                        if hasattr(self, 'all_skills_slider'):
                            self.all_skills_slider.set(self.current_all_skills)
                            self.all_skills_var.set(str(self.current_all_skills))
                    elif setting == "combat_mode":
                        mode_str = row.get("value", "stage")
                        try:
                            self.combat_mode = CombatMode(mode_str)
                            if hasattr(self, 'combat_mode_var'):
                                self.combat_mode_var.set(mode_str)
                        except ValueError:
                            self.combat_mode = CombatMode.STAGE
                    elif setting == "skill_1st" and hasattr(self, 'char_settings_skill_1st_var'):
                        self.char_settings_skill_1st_var.set(max(0, value))
                    elif setting == "skill_2nd" and hasattr(self, 'char_settings_skill_2nd_var'):
                        self.char_settings_skill_2nd_var.set(max(0, value))
                    elif setting == "skill_3rd" and hasattr(self, 'char_settings_skill_3rd_var'):
                        self.char_settings_skill_3rd_var.set(max(0, value))
                    elif setting == "skill_4th" and hasattr(self, 'char_settings_skill_4th_var'):
                        self.char_settings_skill_4th_var.set(max(0, value))

            # Update the totals display after loading
            self._update_combat_mode_info()
            self._update_skill_totals_display()
        except Exception as e:
            print(f"Failed to load character settings: {e}")
            self._update_skill_totals_display()

    def _on_char_settings_change(self, event=None):
        """Handle changes to character settings."""
        try:
            # Update character level
            if hasattr(self, 'char_settings_level_var'):
                new_level = max(1, min(300, self.char_settings_level_var.get()))
                self.character_level = new_level
                # Sync with damage calc tab
                if hasattr(self, 'level_slider'):
                    self.level_slider.set(new_level)
                    self.level_var.set(str(new_level))

            # Update all skills
            if hasattr(self, 'char_settings_all_skills_var'):
                new_all_skills = max(0, min(200, self.char_settings_all_skills_var.get()))
                self.current_all_skills = new_all_skills
                self.invalidate_all_skills_cache()
                # Sync with damage calc tab
                if hasattr(self, 'all_skills_slider'):
                    self.all_skills_slider.set(new_all_skills)
                    self.all_skills_var.set(str(new_all_skills))
                if hasattr(self, '_update_all_skills_value_display'):
                    self._update_all_skills_value_display()

            # Update totals display
            self._update_skill_totals_display()

            # Save settings
            self.save_character_settings()

            # Refresh displays
            self.refresh_all_displays()

        except Exception as e:
            print(f"Error updating character settings: {e}")

    def _update_skill_totals_display(self):
        """Update the skill totals label showing base + All Skills bonus."""
        if not hasattr(self, 'char_settings_total_label'):
            return

        try:
            all_skills = self.current_all_skills if hasattr(self, 'current_all_skills') else 0
            skill_1st = self.char_settings_skill_1st_var.get() if hasattr(self, 'char_settings_skill_1st_var') else 0
            skill_2nd = self.char_settings_skill_2nd_var.get() if hasattr(self, 'char_settings_skill_2nd_var') else 0
            skill_3rd = self.char_settings_skill_3rd_var.get() if hasattr(self, 'char_settings_skill_3rd_var') else 0
            skill_4th = self.char_settings_skill_4th_var.get() if hasattr(self, 'char_settings_skill_4th_var') else 0

            # Total = base + all skills bonus
            total_1st = skill_1st + all_skills
            total_2nd = skill_2nd + all_skills
            total_3rd = skill_3rd + all_skills
            total_4th = skill_4th + all_skills

            self.char_settings_total_label.config(
                text=f"1st: {total_1st}  |  2nd: {total_2nd}  |  3rd: {total_3rd}  |  4th: {total_4th}"
            )
        except Exception as e:
            print(f"Error updating skill totals: {e}")

    def _on_combat_mode_change(self):
        """Handle combat mode change."""
        try:
            mode_str = self.combat_mode_var.get()
            self.combat_mode = CombatMode(mode_str)
            self._update_combat_mode_info()
            self.save_character_settings()
            self.refresh_all_displays()
        except Exception as e:
            print(f"Error changing combat mode: {e}")

    def _update_combat_mode_info(self):
        """Update the combat mode info label."""
        if not hasattr(self, 'combat_mode_info'):
            return

        mode = self.combat_mode
        ba_mult = BA_TARGETS_MODE_MULTIPLIER.get(mode, 0)
        # Calculate actual BA% from skill data
        ba_pct = calculate_ba_percent_of_dps(self.character_level, self.current_all_skills)
        # BA already hits 7 targets, so +1 = +14.3% more BA damage
        BASE_BA_TARGETS = 7
        per_target_increase = (1 / BASE_BA_TARGETS) * 100  # 14.3%

        if mode == CombatMode.STAGE:
            # DPS gain per target = BA% * 14.3% * mode_mult
            dps_per_target = (ba_pct / 100) * per_target_increase * ba_mult
            info = f"BA={ba_pct:.0f}% of DPS, +1 target = +{dps_per_target:.1f}% DPS"
        elif mode == CombatMode.BOSS:
            info = f"BA={ba_pct:.0f}% of DPS, targets: 0% (single target)"
        else:
            info = f"BA={ba_pct:.0f}% of DPS, targets: 0% (world boss)"

        self.combat_mode_info.config(text=info)

    def calculate_skill_bonuses_from_equipment(self) -> dict:
        """
        Calculate total skill bonuses from all equipment sources.

        Returns dict with:
        - all_skills: Total +All Skills from equipment special stats and potentials
        - skill_1st: Total +1st Job Skill from equipment sub stats
        - skill_2nd: Total +2nd Job Skill from equipment sub stats
        - skill_3rd: Total +3rd Job Skill from equipment sub stats
        - skill_4th: Total +4th Job Skill from equipment sub stats
        """
        totals = {
            "all_skills": 0,
            "skill_1st": 0,
            "skill_2nd": 0,
            "skill_3rd": 0,
            "skill_4th": 0,
        }

        # Sum from equipment items (sub stats and special stats)
        for slot, item in self.equipment_items.items():
            # Get sub amplify multiplier for skill bonuses
            sub_mult = item.get_sub_multiplier()

            # Individual job skill bonuses (sub stats, affected by sub amplify)
            totals["skill_1st"] += int(item.sub_skill_first_job * sub_mult)
            totals["skill_2nd"] += int(item.sub_skill_second_job * sub_mult)
            totals["skill_3rd"] += int(item.sub_skill_third_job * sub_mult)
            totals["skill_4th"] += int(item.sub_skill_fourth_job * sub_mult)

            # All Skills from special stat (if this item has it)
            if item.is_special and item.special_stat_type == "all_skills":
                totals["all_skills"] += int(item.special_stat_value * sub_mult)

        # Sum from potentials (ALL_SKILLS stat type)
        from cubes import StatType
        for slot, equip in self.equipment.items():
            # Regular potential lines
            for line in equip.lines:
                if line.stat_type == StatType.ALL_SKILLS:
                    totals["all_skills"] += int(line.value)
            # Bonus potential lines
            for line in equip.bonus_lines:
                if line.stat_type == StatType.ALL_SKILLS:
                    totals["all_skills"] += int(line.value)

        return totals

    def auto_update_skill_bonuses(self):
        """Auto-update the Character Stats skill levels from equipment/potentials."""
        totals = self.calculate_skill_bonuses_from_equipment()

        # Update All Skills
        self.current_all_skills = totals["all_skills"]
        if hasattr(self, 'char_settings_all_skills_var'):
            self.char_settings_all_skills_var.set(self.current_all_skills)
        if hasattr(self, 'all_skills_slider'):
            self.all_skills_slider.set(self.current_all_skills)
            self.all_skills_var.set(str(self.current_all_skills))

        # Update individual job skill levels
        if hasattr(self, 'char_settings_skill_1st_var'):
            self.char_settings_skill_1st_var.set(totals["skill_1st"])
        if hasattr(self, 'char_settings_skill_2nd_var'):
            self.char_settings_skill_2nd_var.set(totals["skill_2nd"])
        if hasattr(self, 'char_settings_skill_3rd_var'):
            self.char_settings_skill_3rd_var.set(totals["skill_3rd"])
        if hasattr(self, 'char_settings_skill_4th_var'):
            self.char_settings_skill_4th_var.set(totals["skill_4th"])

        # Update display and save
        self.invalidate_all_skills_cache()
        self._update_skill_totals_display()
        self._update_all_skills_value_display()
        self.save_character_settings()

    # =========================================================================
    # TAB 2: CUBE SIMULATOR (INTEGRATED)
    # =========================================================================

    def build_simulator_tab(self):
        """Build the cube simulator tab with damage integration."""
        main = ttk.Frame(self.simulator_tab)
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Top section - settings
        settings = ttk.Frame(main)
        settings.pack(fill=tk.X, pady=5)

        tk.Label(settings, text="Equipment:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT)
        self.sim_slot = ttk.Combobox(settings, values=EQUIPMENT_SLOTS, width=12)
        self.sim_slot.set("gloves")
        self.sim_slot.pack(side=tk.LEFT, padx=10)
        self.sim_slot.bind("<<ComboboxSelected>>", lambda e: self.on_slot_change())

        tk.Label(settings, text="Current Tier:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT, padx=(20, 0))
        self.sim_tier = ttk.Combobox(settings, values=["normal", "rare", "epic", "unique", "legendary", "mystic"], width=12)
        self.sim_tier.set("legendary")
        self.sim_tier.pack(side=tk.LEFT, padx=10)
        self.sim_tier.bind("<<ComboboxSelected>>", lambda e: self.on_tier_change())

        tk.Label(settings, text="Cube Type:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT, padx=(20, 0))
        self.sim_cube_type = ttk.Combobox(settings, values=["regular", "bonus"], width=10)
        self.sim_cube_type.set("regular")
        self.sim_cube_type.pack(side=tk.LEFT, padx=10)

        tk.Button(settings, text="Reset Simulator", command=self.reset_simulator,
                 bg='#4a4a6a', fg='white').pack(side=tk.RIGHT)

        # Two columns: left for cube, right for comparison
        cols = ttk.Frame(main)
        cols.pack(fill=tk.BOTH, expand=True, pady=10)

        left_col = ttk.Frame(cols)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_col = ttk.Frame(cols)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # LEFT: Pity + Current Lines
        self._section_header(left_col, "Pity Progress")
        self.pity_bar = PityBar(left_col, width=450, height=35)

        self._section_header(left_col, "Current Equipped Potential")
        self.current_lines_display = tk.Text(left_col, height=5, width=50, bg='#2a2a4e', fg='#aaa',
                                             font=('Consolas', 11), state=tk.DISABLED)
        self.current_lines_display.pack(pady=5)

        self._section_header(left_col, "NEW Roll (Pending)")
        self.pending_lines_display = tk.Text(left_col, height=5, width=50, bg='#2a2a4e', fg='#eee',
                                             font=('Consolas', 11), state=tk.DISABLED)
        self.pending_lines_display.pack(pady=5)

        # RIGHT: DPS Comparison
        self._section_header(right_col, "DPS Comparison")

        self.dps_current_label = tk.Label(right_col, text="Current DPS: ---",
                                          font=('Segoe UI', 14), bg='#1a1a2e', fg='#aaa')
        self.dps_current_label.pack(anchor=tk.W, pady=5)

        self.dps_new_label = tk.Label(right_col, text="New DPS: ---",
                                      font=('Segoe UI', 14), bg='#1a1a2e', fg='#00ff88')
        self.dps_new_label.pack(anchor=tk.W, pady=5)

        self.dps_change_label = tk.Label(right_col, text="",
                                         font=('Segoe UI', 16, 'bold'), bg='#1a1a2e', fg='#ffd700')
        self.dps_change_label.pack(anchor=tk.W, pady=10)

        self.verdict_label = tk.Label(right_col, text="",
                                      font=('Segoe UI', 12), bg='#1a1a2e', fg='#ccc',
                                      wraplength=300, justify=tk.LEFT)
        self.verdict_label.pack(anchor=tk.W, pady=5)

        # Accept/Reject buttons
        decision_frame = ttk.Frame(right_col)
        decision_frame.pack(pady=15)

        self.accept_btn = tk.Button(decision_frame, text="Accept New Lines",
                                    command=self.accept_cube_roll,
                                    bg='#6bcb77', fg='white', font=('Segoe UI', 11, 'bold'),
                                    width=16, height=2, state=tk.DISABLED)
        self.accept_btn.pack(side=tk.LEFT, padx=10)

        self.reject_btn = tk.Button(decision_frame, text="Keep Current",
                                    command=self.reject_cube_roll,
                                    bg='#ff6b6b', fg='white', font=('Segoe UI', 11, 'bold'),
                                    width=16, height=2, state=tk.DISABLED)
        self.reject_btn.pack(side=tk.LEFT, padx=10)

        # Roll buttons
        roll_frame = ttk.Frame(main)
        roll_frame.pack(pady=10)

        tk.Button(roll_frame, text="Use 1 Cube", command=lambda: self.use_cubes(1),
                 bg='#4a9eff', fg='white', font=('Segoe UI', 12, 'bold'),
                 width=12, height=2).pack(side=tk.LEFT, padx=10)
        tk.Button(roll_frame, text="Use 10 Cubes (auto)", command=lambda: self.use_cubes_auto(10),
                 bg='#9d65c9', fg='white', font=('Segoe UI', 12, 'bold'),
                 width=16, height=2).pack(side=tk.LEFT, padx=10)

        # Stats display
        stats_frame = ttk.Frame(main)
        stats_frame.pack(fill=tk.X, pady=5)

        self.sim_stats_label = tk.Label(stats_frame, text="Cubes: 0 | Tier Ups: 0 | Specials: 0",
                                        bg='#1a1a2e', fg='#888', font=('Consolas', 10))
        self.sim_stats_label.pack()

        # Potential Line Value Rankings (RIGHT SIDE)
        self._section_header(right_col, "Potential Line Values (Slot 1)")

        # Create a frame for the rankings with scrollable text
        rankings_frame = ttk.Frame(right_col)
        rankings_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.line_values_text = tk.Text(rankings_frame, height=12, width=45, bg='#2a2a4e', fg='#eee',
                                        font=('Consolas', 9), state=tk.DISABLED)
        self.line_values_text.pack(fill=tk.BOTH, expand=True)

        # Button to refresh the rankings
        tk.Button(right_col, text="Refresh DPS Values", command=self.update_line_value_rankings,
                 bg='#4a4a6a', fg='white', font=('Segoe UI', 9)).pack(pady=5)

        # History
        history_frame = ttk.Frame(main)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        tk.Label(history_frame, text="Roll History:", bg='#1a1a2e', fg='#ffd700',
                font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W)

        self.history_text = tk.Text(history_frame, height=4, bg='#2a2a4e', fg='#aaa',
                                   font=('Consolas', 9))
        self.history_text.pack(fill=tk.BOTH, expand=True)

        # Initialize
        self.simulator = None
        self.pending_lines = []
        self.reset_simulator()

    def on_slot_change(self):
        """When equipment slot changes, update display."""
        self.reset_simulator()

    def on_tier_change(self):
        """When tier changes, update the line value rankings."""
        self.reset_simulator()

    def reset_simulator(self):
        slot = self.sim_slot.get()
        tier_str = self.sim_tier.get()
        cube_str = self.sim_cube_type.get()

        tier = PotentialTier(tier_str)
        cube_type = CubeType(cube_str)

        self.simulator = CubeSimulator(slot, tier, cube_type)
        self.pending_lines = []

        # Update equipment tier
        self.equipment[slot].tier = tier

        self.update_simulator_display()
        self.update_line_value_rankings()  # Update potential line values
        self.history_text.delete(1.0, tk.END)
        self.history_text.insert(tk.END, f"Simulator reset for {slot.upper()}. Ready to cube!\n")

        # Disable accept/reject until we roll
        self.accept_btn.config(state=tk.DISABLED)
        self.reject_btn.config(state=tk.DISABLED)
        self.dps_change_label.config(text="")
        self.verdict_label.config(text="")

    def use_cubes(self, count: int):
        """Use cube(s) and show pending result."""
        if not self.simulator:
            self.reset_simulator()

        # Only do 1 cube at a time for manual decision
        result = self.simulator.use_cube()
        self.pending_lines = result.lines

        # Log
        slot = self.sim_slot.get()
        log = f"Cube #{self.simulator.total_cubes_used} on {slot}: "
        if result.tier_up:
            log += f"** TIER UP to {result.new_tier.value.upper()}! ** "
            self.equipment[slot].tier = result.new_tier

        for line in result.lines:
            if line.is_special:
                log += f"[SPECIAL!] "
                break

        self.history_text.insert(tk.END, log + "\n")
        self.history_text.see(tk.END)

        # Update display and enable accept/reject
        self.update_simulator_display()
        self.update_dps_comparison()

        self.accept_btn.config(state=tk.NORMAL)
        self.reject_btn.config(state=tk.NORMAL)

    def use_cubes_auto(self, count: int):
        """Use multiple cubes, auto-accepting any improvement."""
        if not self.simulator:
            self.reset_simulator()

        slot = self.sim_slot.get()
        accepted = 0
        best_gain = 0

        for i in range(count):
            result = self.simulator.use_cube()

            # Calculate DPS change
            current, new = self.apply_potential_to_damage_calc(result.lines, slot)

            if new > current:
                # Accept this roll
                self.equipment[slot].lines = result.lines
                accepted += 1
                gain = ((new / current) - 1) * 100 if current > 0 else 0
                if gain > best_gain:
                    best_gain = gain

            if result.tier_up:
                self.equipment[slot].tier = result.new_tier

        self.pending_lines = []
        self.update_simulator_display()
        self.update_damage()
        self.update_all_equipment_displays()  # Update optimizer tab

        self.history_text.insert(tk.END,
            f"Auto-rolled {count} cubes: Accepted {accepted} improvements, best +{best_gain:.2f}% DPS\n")
        self.history_text.see(tk.END)

        self.accept_btn.config(state=tk.DISABLED)
        self.reject_btn.config(state=tk.DISABLED)

    def accept_cube_roll(self):
        """Accept the pending cube roll."""
        if not self.pending_lines:
            return

        slot = self.sim_slot.get()
        self.equipment[slot].lines = self.pending_lines
        self.pending_lines = []

        self.history_text.insert(tk.END, "  -> ACCEPTED new lines\n")
        self.history_text.see(tk.END)

        self.accept_btn.config(state=tk.DISABLED)
        self.reject_btn.config(state=tk.DISABLED)
        self.dps_change_label.config(text="Accepted!", fg='#6bcb77')
        self.verdict_label.config(text="")

        self.update_simulator_display()
        self.update_damage()
        self.update_all_equipment_displays()  # Update optimizer tab

    def reject_cube_roll(self):
        """Reject the pending cube roll."""
        self.pending_lines = []

        self.history_text.insert(tk.END, "  -> KEPT current lines\n")
        self.history_text.see(tk.END)

        self.accept_btn.config(state=tk.DISABLED)
        self.reject_btn.config(state=tk.DISABLED)
        self.dps_change_label.config(text="Kept current", fg='#ff6b6b')
        self.verdict_label.config(text="")

        self.update_simulator_display()

    def update_dps_comparison(self):
        """Update the DPS comparison between current and pending."""
        slot = self.sim_slot.get()
        current_dmg, new_dmg = self.apply_potential_to_damage_calc(self.pending_lines, slot)

        self.dps_current_label.config(text=f"Current DPS: {current_dmg:,.0f}")
        self.dps_new_label.config(text=f"New DPS: {new_dmg:,.0f}")

        if current_dmg > 0:
            change = ((new_dmg / current_dmg) - 1) * 100
            if change > 0:
                self.dps_change_label.config(text=f"+{change:.2f}% DPS", fg='#00ff88')
                self.verdict_label.config(text="This is an UPGRADE! Consider accepting.", fg='#6bcb77')
            elif change < 0:
                self.dps_change_label.config(text=f"{change:.2f}% DPS", fg='#ff4444')
                self.verdict_label.config(text="This is a DOWNGRADE. Consider keeping current.", fg='#ff6b6b')
            else:
                self.dps_change_label.config(text="No change", fg='#ffd700')
                self.verdict_label.config(text="Same DPS. Your choice.", fg='#aaa')

    def update_simulator_display(self):
        if not self.simulator:
            return

        # Update pity bar
        pity = self.simulator.pity_count
        max_pity = self.simulator._get_pity_threshold()
        tier_color = get_tier_color(self.simulator.current_tier)
        self.pity_bar.update(pity, max_pity, tier_color)

        # Update current equipped lines
        slot = self.sim_slot.get()
        equip = self.equipment[slot]

        self.current_lines_display.config(state=tk.NORMAL)
        self.current_lines_display.delete(1.0, tk.END)
        self.current_lines_display.insert(tk.END, f"[{equip.tier.value.upper()}] {slot.upper()}\n\n")
        if equip.lines:
            for line in equip.lines:
                self.current_lines_display.insert(tk.END, format_line(line) + "\n")
        else:
            self.current_lines_display.insert(tk.END, "(No lines - roll a cube!)")
        self.current_lines_display.config(state=tk.DISABLED)

        # Update pending lines
        self.pending_lines_display.config(state=tk.NORMAL)
        self.pending_lines_display.delete(1.0, tk.END)
        if self.pending_lines:
            self.pending_lines_display.insert(tk.END, f"[{self.simulator.current_tier.value.upper()}] NEW ROLL\n\n")
            for line in self.pending_lines:
                text = format_line(line)
                self.pending_lines_display.insert(tk.END, text + "\n")
        else:
            self.pending_lines_display.insert(tk.END, "(Roll a cube to see new lines)")
        self.pending_lines_display.config(state=tk.DISABLED)

        # Update stats
        stats = self.simulator.get_stats()
        self.sim_stats_label.config(
            text=f"Cubes: {stats['total_cubes']} | Tier Ups: {stats['tier_ups']} | "
                 f"Specials: {stats['specials_seen']} | Pity: {stats['current_pity']}/{stats['pity_threshold']}")

    def update_line_value_rankings(self):
        """Calculate and display the DPS value of each potential line, sorted best to worst."""
        # Get current damage stats
        base_stats = self._get_damage_stats()
        base_damage = self._calc_damage(base_stats)

        if base_damage <= 0:
            return

        # Get current tier from simulator
        current_tier = PotentialTier.LEGENDARY
        if self.simulator:
            current_tier = self.simulator.current_tier

        # Get current equipment slot
        slot = self.sim_slot.get()

        # Define all potential lines to test with their stat values at current tier
        potential_lines_to_test = []

        # Get regular stats for current tier
        tier_stats = POTENTIAL_STATS.get(current_tier, [])
        for stat in tier_stats:
            potential_lines_to_test.append({
                "name": get_stat_display_name(stat.stat_type),
                "stat_type": stat.stat_type,
                "value": stat.value,
                "prob": stat.probability,
                "is_special": False,
                "tier": STAT_TIER_RANKINGS.get(stat.stat_type, "?")
            })

        # Get special potential for this slot if available
        if slot in SPECIAL_POTENTIALS:
            special = SPECIAL_POTENTIALS[slot]
            if current_tier in special.values:
                potential_lines_to_test.append({
                    "name": f"{get_stat_display_name(special.stat_type)} (Special)",
                    "stat_type": special.stat_type,
                    "value": special.values[current_tier],
                    "prob": SPECIAL_POTENTIAL_RATE,
                    "is_special": True,
                    "tier": "S"
                })

        # Calculate DPS increase for each line
        results = []
        for line_info in potential_lines_to_test:
            stat_type = line_info["stat_type"]
            value = line_info["value"]

            # Create modified stats
            mod_stats = dict(base_stats)
            mod_stats["fd_sources"] = list(base_stats["fd_sources"])

            # Apply the stat based on type
            if stat_type in (StatType.DEX_PCT, StatType.STR_PCT,
                             StatType.INT_PCT, StatType.LUK_PCT,
                             StatType.MAIN_STAT_PCT):
                mod_stats["dex_percent"] += value
            elif stat_type in (StatType.DEX_FLAT, StatType.STR_FLAT,
                               StatType.INT_FLAT, StatType.LUK_FLAT,
                               StatType.MAIN_STAT_FLAT):
                mod_stats["dex_flat"] += value
            elif stat_type == StatType.DAMAGE_PCT:
                mod_stats["damage_percent"] += value
            elif stat_type == StatType.CRIT_DAMAGE:
                mod_stats["crit_damage"] += value
            elif stat_type == StatType.DEF_PEN:
                mod_stats["defense_pen"] += value
            elif stat_type == StatType.FINAL_DAMAGE:
                # Each FD line is a separate multiplicative source
                mod_stats["fd_sources"] = list(mod_stats["fd_sources"]) + [value]
            elif stat_type == StatType.CRIT_RATE:
                # Crit rate doesn't directly affect damage in this formula
                # but we can estimate it as a multiplier to crit damage
                pass  # Skip for now
            elif stat_type == StatType.MAX_DMG_MULT or stat_type == StatType.MIN_DMG_MULT:
                # These affect damage variance, estimate as partial damage%
                mod_stats["damage_percent"] += value * 0.5
            elif stat_type == StatType.ATTACK_SPEED:
                # Attack speed directly scales DPS - more attacks per second
                mod_stats["attack_speed"] = mod_stats.get("attack_speed", 0) + value
            elif stat_type in (StatType.DEFENSE, StatType.MAX_HP, StatType.MAX_MP,
                              StatType.SKILL_CD):
                # These don't directly increase DPS
                pass

            new_damage = self._calc_damage(mod_stats)
            dps_increase = ((new_damage / base_damage) - 1) * 100

            results.append({
                "name": line_info["name"],
                "stat_type": stat_type,
                "value": value,
                "dps_increase": dps_increase,
                "prob": line_info["prob"],
                "is_special": line_info["is_special"],
                "tier": line_info["tier"]
            })

        # Sort by DPS increase (highest first)
        results.sort(key=lambda x: x["dps_increase"], reverse=True)

        # Get tier color
        def tier_color(t):
            colors = {"S": "#00ff88", "A": "#ffd700", "B": "#4a9eff", "F": "#ff4444", "?": "#888"}
            return colors.get(t, "#888")

        # Display results
        self.line_values_text.config(state=tk.NORMAL)
        self.line_values_text.delete(1.0, tk.END)

        header = f"[{current_tier.value.upper()}] Potential Lines for {slot.upper()}\n"
        header += f"{'='*42}\n\n"
        self.line_values_text.insert(tk.END, header)

        for i, r in enumerate(results, 1):
            # Format: rank. stat name: +value% -> +X.XX% DPS [Tier]
            if r["stat_type"] in (StatType.MAIN_STAT_FLAT, StatType.ALL_SKILLS):
                val_str = f"+{int(r['value'])}"
            elif r["stat_type"] == StatType.SKILL_CD:
                val_str = f"-{r['value']}s"
            else:
                val_str = f"+{r['value']:.1f}%"

            line = f"{i:2}. {r['name'][:22]:<22} {val_str:>8}"
            dps_str = f" -> +{r['dps_increase']:.2f}% DPS"
            tier_str = f" [{r['tier']}]"
            special_str = " *" if r["is_special"] else ""

            self.line_values_text.insert(tk.END, line)
            self.line_values_text.insert(tk.END, dps_str)
            self.line_values_text.insert(tk.END, tier_str + special_str + "\n")

        # Add legend
        self.line_values_text.insert(tk.END, f"\n{'='*42}\n")
        self.line_values_text.insert(tk.END, "[S]=Best [A]=Good [B]=Situational [F]=Useless\n")
        self.line_values_text.insert(tk.END, "* = Special potential (1% chance)\n")

        self.line_values_text.config(state=tk.DISABLED)

    # =========================================================================
    # TAB 3: CUBE COST CALCULATOR
    # =========================================================================

    def build_cost_tab(self):
        """Build the cost calculator tab."""
        main = ttk.Frame(self.cost_tab)
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(main, text="Cube Cost Calculator", font=('Segoe UI', 16, 'bold'),
                bg='#1a1a2e', fg='#ffd700').pack(pady=10)

        # Settings
        settings = ttk.Frame(main)
        settings.pack(fill=tk.X, pady=10)

        tk.Label(settings, text="From Tier:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT)
        self.cost_from = ttk.Combobox(settings, values=["normal", "rare", "epic", "unique", "legendary"], width=12)
        self.cost_from.set("unique")
        self.cost_from.pack(side=tk.LEFT, padx=10)

        tk.Label(settings, text="To Tier:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT, padx=(20, 0))
        self.cost_to = ttk.Combobox(settings, values=["rare", "epic", "unique", "legendary", "mystic"], width=12)
        self.cost_to.set("legendary")
        self.cost_to.pack(side=tk.LEFT, padx=10)

        tk.Label(settings, text="Cube Type:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT, padx=(20, 0))
        self.cost_cube_type = ttk.Combobox(settings, values=["regular", "bonus"], width=10)
        self.cost_cube_type.set("regular")
        self.cost_cube_type.pack(side=tk.LEFT, padx=10)

        tk.Button(settings, text="Calculate", command=self.calculate_cost,
                 bg='#6bcb77', fg='white', font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=20)

        # Results
        self.cost_result = tk.Label(main, text="", font=('Consolas', 12),
                                   bg='#1a1a2e', fg='#eee', justify=tk.LEFT)
        self.cost_result.pack(pady=20)

        # Price reference
        tk.Label(main, text="Cube Price Reference:", font=('Segoe UI', 12, 'bold'),
                bg='#1a1a2e', fg='#ffd700').pack(pady=(30, 10))

        price_text = """
Regular Cubes:                          Bonus Cubes:
  Normal Shop:     3,000/cube             Normal Shop:     2,000/cube (100/week)
  Monthly Package: 600/cube (best!)       Monthly Package: 1,200/cube (best!)
  Weekly Package:  700/cube               Weekly Package:  1,400/cube
  World Boss:      500 coins (10/week)    World Boss:      700 coins (3/week)
"""
        tk.Label(main, text=price_text, font=('Consolas', 10),
                bg='#1a1a2e', fg='#aaa', justify=tk.LEFT).pack()

    def calculate_cost(self):
        from_tier = PotentialTier(self.cost_from.get())
        to_tier = PotentialTier(self.cost_to.get())
        cube_type = CubeType(self.cost_cube_type.get())

        tiers = list(PotentialTier)
        if tiers.index(from_tier) >= tiers.index(to_tier):
            self.cost_result.config(text="Target tier must be higher than current tier!")
            return

        if cube_type == CubeType.REGULAR:
            prices = [("Monthly (Best)", 600), ("Weekly", 700), ("Normal Shop", 3000)]
        else:
            prices = [("Monthly (Best)", 1200), ("Weekly", 1400), ("Normal Shop", 2000)]

        result = f"Cost to go from {from_tier.value.upper()} to {to_tier.value.upper()}:\n\n"

        cubes, _ = calculate_cost_to_tier(from_tier, to_tier, cube_type, 1)
        result += f"Expected Cubes Needed: {cubes:,}\n\n"

        for name, price in prices:
            total = cubes * price
            result += f"  {name}: {total:,} diamonds ({price}/cube)\n"

        result += f"\nPity Thresholds:\n"
        pity = REGULAR_PITY if cube_type == CubeType.REGULAR else BONUS_PITY
        tier = from_tier
        while tier != to_tier and tier != PotentialTier.MYSTIC:
            p = pity.get(tier, 0)
            next_t = tier.next_tier()
            if next_t:
                result += f"  {tier.value.upper()} -> {next_t.value.upper()}: {p} cubes guaranteed\n"
            tier = next_t

        self.cost_result.config(text=result)

    # =========================================================================
    # TAB 4: CUBE OPTIMIZER (Equipment Manager)
    # =========================================================================

    def build_optimizer_tab(self):
        """Build the optimizer tab with equipment management."""
        main = ttk.Frame(self.optimizer_tab)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        tk.Label(main, text="Equipment Potential Manager", font=('Segoe UI', 16, 'bold'),
                bg='#1a1a2e', fg='#ffd700').pack(pady=(5, 10))

        # Two columns layout
        cols = ttk.Frame(main)
        cols.pack(fill=tk.BOTH, expand=True)

        left_col = ttk.Frame(cols)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        right_col = ttk.Frame(cols)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # LEFT: Equipment list with current potentials
        self._section_header(left_col, "All Equipment Potentials")

        # Create scrollable frame for equipment
        equip_canvas = tk.Canvas(left_col, bg='#1a1a2e', highlightthickness=0, height=400)
        scrollbar = ttk.Scrollbar(left_col, orient="vertical", command=equip_canvas.yview)
        self.equip_scroll_frame = ttk.Frame(equip_canvas)

        self.equip_scroll_frame.bind(
            "<Configure>",
            lambda e: equip_canvas.configure(scrollregion=equip_canvas.bbox("all"))
        )

        equip_canvas.create_window((0, 0), window=self.equip_scroll_frame, anchor="nw")
        equip_canvas.configure(yscrollcommand=scrollbar.set)

        equip_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Build equipment displays
        self.equip_displays = {}
        for slot in EQUIPMENT_SLOTS:
            self._build_equipment_display(self.equip_scroll_frame, slot)

        # RIGHT: Recommendations and actions
        self._section_header(right_col, "Cube Recommendation")

        self.recommendation_text = tk.Text(right_col, height=10, width=45, bg='#2a2a4e', fg='#eee',
                                           font=('Consolas', 9), state=tk.DISABLED)
        self.recommendation_text.pack(pady=5, fill=tk.X)

        tk.Button(right_col, text="Analyze & Recommend", command=self.analyze_cube_priority,
                 bg='#6bcb77', fg='white', font=('Segoe UI', 11, 'bold'),
                 width=20).pack(pady=10)

        # Manual potential editor
        self._section_header(right_col, "Quick Set Potential")

        # Row 1: Slot, Tier, Regular/Bonus toggle
        editor_frame = ttk.Frame(right_col)
        editor_frame.pack(fill=tk.X, pady=5)

        tk.Label(editor_frame, text="Slot:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT)
        self.edit_slot = ttk.Combobox(editor_frame, values=EQUIPMENT_SLOTS, width=10)
        self.edit_slot.set("gloves")
        self.edit_slot.pack(side=tk.LEFT, padx=5)
        self.edit_slot.bind("<<ComboboxSelected>>", lambda e: self._on_slot_change())

        tk.Label(editor_frame, text="Tier:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT, padx=(10, 0))
        all_tiers = ["normal", "rare", "epic", "unique", "legendary", "mystic"]
        self.edit_tier = ttk.Combobox(editor_frame, values=all_tiers, width=10)
        self.edit_tier.set("legendary")
        self.edit_tier.pack(side=tk.LEFT, padx=5)
        self.edit_tier.bind("<<ComboboxSelected>>", lambda e: self._update_auto_values())

        # Regular/Bonus toggle
        tk.Label(editor_frame, text="Type:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT, padx=(10, 0))
        self.edit_pot_type = ttk.Combobox(editor_frame, values=["Regular", "Bonus"], width=8)
        self.edit_pot_type.set("Regular")
        self.edit_pot_type.pack(side=tk.LEFT, padx=5)

        # Line editors with Yellow/Grey dropdowns and auto-values
        self.line_editors = []  # Store references to line editor components

        # Line 1 editor (always Yellow)
        line1_frame = ttk.Frame(right_col)
        line1_frame.pack(fill=tk.X, pady=2)
        tk.Label(line1_frame, text="Line 1:", bg='#1a1a2e', fg='#ffd700', width=8).pack(side=tk.LEFT)
        line1_stat = ttk.Combobox(line1_frame, values=self._get_stat_options("gloves"), width=16)
        line1_stat.set("Crit Damage % (Special)")  # Default to gloves special
        line1_stat.pack(side=tk.LEFT, padx=3)
        line1_stat.bind("<<ComboboxSelected>>", lambda e: self._update_auto_values())
        line1_color = tk.Label(line1_frame, text="Yellow", bg='#ffd700', fg='black', width=6,
                               font=('Segoe UI', 8, 'bold'))
        line1_color.pack(side=tk.LEFT, padx=3)
        line1_val = tk.Label(line1_frame, text="25%", bg='#2a2a4e', fg='#ffd700', width=8,
                            font=('Consolas', 9, 'bold'))
        line1_val.pack(side=tk.LEFT, padx=3)
        self.line_editors.append({
            "stat": line1_stat, "color": None, "value": line1_val, "is_yellow": True
        })

        # Line 2 editor (Yellow/Grey toggle)
        line2_frame = ttk.Frame(right_col)
        line2_frame.pack(fill=tk.X, pady=2)
        tk.Label(line2_frame, text="Line 2:", bg='#1a1a2e', fg='#aaa', width=8).pack(side=tk.LEFT)
        line2_stat = ttk.Combobox(line2_frame, values=self._get_stat_options("gloves"), width=16)
        line2_stat.set("DEX %")
        line2_stat.pack(side=tk.LEFT, padx=3)
        line2_stat.bind("<<ComboboxSelected>>", lambda e: self._update_auto_values())
        line2_color = ttk.Combobox(line2_frame, values=["Yellow", "Grey"], width=6)
        line2_color.set("Grey")
        line2_color.pack(side=tk.LEFT, padx=3)
        line2_color.bind("<<ComboboxSelected>>", lambda e: self._update_auto_values())
        line2_val = tk.Label(line2_frame, text="9%", bg='#2a2a4e', fg='#888', width=8,
                            font=('Consolas', 9))
        line2_val.pack(side=tk.LEFT, padx=3)
        self.line_editors.append({
            "stat": line2_stat, "color": line2_color, "value": line2_val, "is_yellow": False
        })

        # Line 3 editor (Yellow/Grey toggle)
        line3_frame = ttk.Frame(right_col)
        line3_frame.pack(fill=tk.X, pady=2)
        tk.Label(line3_frame, text="Line 3:", bg='#1a1a2e', fg='#888', width=8).pack(side=tk.LEFT)
        line3_stat = ttk.Combobox(line3_frame, values=self._get_stat_options("gloves"), width=16)
        line3_stat.set("Defense %")
        line3_stat.pack(side=tk.LEFT, padx=3)
        line3_stat.bind("<<ComboboxSelected>>", lambda e: self._update_auto_values())
        line3_color = ttk.Combobox(line3_frame, values=["Yellow", "Grey"], width=6)
        line3_color.set("Grey")
        line3_color.pack(side=tk.LEFT, padx=3)
        line3_color.bind("<<ComboboxSelected>>", lambda e: self._update_auto_values())
        line3_val = tk.Label(line3_frame, text="9%", bg='#2a2a4e', fg='#888', width=8,
                            font=('Consolas', 9))
        line3_val.pack(side=tk.LEFT, padx=3)
        self.line_editors.append({
            "stat": line3_stat, "color": line3_color, "value": line3_val, "is_yellow": False
        })

        # Initialize auto-values
        self._update_auto_values()

        btn_frame = ttk.Frame(right_col)
        btn_frame.pack(fill=tk.X, pady=10)
        tk.Button(btn_frame, text="Set Potential", command=self.set_manual_potential,
                 bg='#4a9eff', fg='white', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Clear All", command=self.clear_all_potentials,
                 bg='#ff6b6b', fg='white', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)

        # Save/Load buttons
        save_load_frame = ttk.Frame(right_col)
        save_load_frame.pack(fill=tk.X, pady=5)
        tk.Button(save_load_frame, text="💾 Save Potentials", command=self.save_potentials_to_csv,
                 bg='#28a745', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(save_load_frame, text="📂 Load Potentials", command=self.load_potentials_from_csv,
                 bg='#17a2b8', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        # Stats summary
        self._section_header(right_col, "Total Stats from Potentials")
        self.total_stats_label = tk.Label(right_col, text="No potentials set",
                                          font=('Consolas', 9), bg='#1a1a2e', fg='#aaa',
                                          justify=tk.LEFT)
        self.total_stats_label.pack(anchor=tk.W, pady=5)

        # N-Cube Simulation Section
        self._section_header(right_col, "Upgrade Probability (N Cubes)")

        sim_input_frame = ttk.Frame(right_col)
        sim_input_frame.pack(fill=tk.X, pady=5)

        tk.Label(sim_input_frame, text="Cubes:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT)
        self.sim_cube_count = tk.Entry(sim_input_frame, width=6, bg='#2a2a4e', fg='#fff',
                                        insertbackground='#fff')
        self.sim_cube_count.insert(0, "100")
        self.sim_cube_count.pack(side=tk.LEFT, padx=3)

        tk.Label(sim_input_frame, text="Pity:", bg='#1a1a2e', fg='#ccc').pack(side=tk.LEFT, padx=(5, 0))
        self.sim_pity_count = tk.Entry(sim_input_frame, width=5, bg='#2a2a4e', fg='#fff',
                                        insertbackground='#fff')
        self.sim_pity_count.insert(0, "0")
        self.sim_pity_count.pack(side=tk.LEFT, padx=3)

        tk.Button(sim_input_frame, text="Simulate", command=self.run_cube_simulation,
                 bg='#9d65c9', fg='white', font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)

        # Simulation results display
        self.sim_results_text = tk.Text(right_col, height=16, width=45, bg='#2a2a4e', fg='#eee',
                                        font=('Consolas', 9), state=tk.DISABLED)
        self.sim_results_text.pack(pady=5, fill=tk.X)

    def _get_stat_options(self, slot: str = None):
        """Get list of stat names for combobox, including slot-specific special potential."""
        # Base stats available on all equipment - individual main stats
        base_stats = [
            "Damage %", "DEX %", "STR %", "INT %", "LUK %",
            "Crit Rate %", "Attack Speed %", "Max Damage Mult %", "Min Damage Mult %",
            "Defense %", "Max HP %", "Max MP %",
            "DEX (Flat)", "STR (Flat)", "INT (Flat)", "LUK (Flat)"
        ]

        # Add slot-specific special potential
        if slot and slot in SPECIAL_POTENTIALS:
            special = SPECIAL_POTENTIALS[slot]
            special_name = get_stat_display_name(special.stat_type)
            # Insert at the beginning for visibility
            return [f"{special_name} (Special)"] + base_stats

        return base_stats

    def _on_slot_change(self):
        """When equipment slot changes, update stat dropdown options to show slot-specific specials."""
        slot = self.edit_slot.get()
        new_options = self._get_stat_options(slot)

        # Update all line editor stat dropdowns
        for editor in self.line_editors:
            stat_combo = editor["stat"]
            current_value = stat_combo.get()
            stat_combo["values"] = new_options

            # If current selection was a special from another slot, reset to Damage %
            if "(Special)" in current_value and current_value not in new_options:
                stat_combo.set("Damage %")

        # Update auto-values
        self._update_auto_values()

    def _stat_name_to_type(self, name: str) -> StatType:
        """Convert display name to StatType."""
        # Handle special potential names (e.g., "Crit Damage % (Special)")
        clean_name = name.replace(" (Special)", "")

        mapping = {
            "Damage %": StatType.DAMAGE_PCT,
            # Individual main stats (%)
            "DEX %": StatType.DEX_PCT,
            "STR %": StatType.STR_PCT,
            "INT %": StatType.INT_PCT,
            "LUK %": StatType.LUK_PCT,
            # Individual main stats (flat)
            "DEX (Flat)": StatType.DEX_FLAT,
            "STR (Flat)": StatType.STR_FLAT,
            "INT (Flat)": StatType.INT_FLAT,
            "LUK (Flat)": StatType.LUK_FLAT,
            # Legacy support
            "Main Stat %": StatType.MAIN_STAT_PCT,
            "Flat Main Stat": StatType.MAIN_STAT_FLAT,
            # Other stats
            "Crit Damage %": StatType.CRIT_DAMAGE,
            "Defense Pen %": StatType.DEF_PEN,
            "Final Damage %": StatType.FINAL_DAMAGE,
            "Final Attack Damage %": StatType.FINAL_DAMAGE,
            "Crit Rate %": StatType.CRIT_RATE,
            "Attack Speed %": StatType.ATTACK_SPEED,
            "Max Damage %": StatType.MAX_DMG_MULT,
            "Min Damage %": StatType.MIN_DMG_MULT,
            "Max Damage Mult %": StatType.MAX_DMG_MULT,
            "Min Damage Mult %": StatType.MIN_DMG_MULT,
            "Defense %": StatType.DEFENSE,
            "Max HP %": StatType.MAX_HP,
            "Max MP %": StatType.MAX_MP,
            "All Skills Level": StatType.ALL_SKILLS,
            # Special potentials - these were missing and causing defaults to DEFENSE!
            "Skill CD Reduction": StatType.SKILL_CD,
            "Skill Cooldown": StatType.SKILL_CD,
            "Skill CD": StatType.SKILL_CD,
            "Buff Duration %": StatType.BUFF_DURATION,
            "Buff Duration": StatType.BUFF_DURATION,
            "BA Targets": StatType.BA_TARGETS,
            "BA Targets +": StatType.BA_TARGETS,  # Matches get_stat_display_name() output
            "Basic Attack Targets": StatType.BA_TARGETS,
            "Main Stat per Level": StatType.MAIN_STAT_PER_LEVEL,
            "Main Stat Per Level": StatType.MAIN_STAT_PER_LEVEL,
        }
        return mapping.get(clean_name, StatType.DEFENSE)

    def _get_stat_value_for_tier(self, stat_type: StatType, tier: PotentialTier, is_yellow: bool, slot: str) -> float:
        """Get stat value from POTENTIAL_STATS based on tier and yellow/grey."""
        # For grey slots, use previous tier values
        lookup_tier = tier if is_yellow else tier.prev_tier()
        if not lookup_tier:
            lookup_tier = tier  # Fallback for Normal tier (no previous)

        # Check for special potentials first (slot-specific)
        if slot in SPECIAL_POTENTIALS:
            special = SPECIAL_POTENTIALS[slot]
            if stat_type == special.stat_type:
                if lookup_tier in special.values:
                    return special.values[lookup_tier]

        # Look up in regular potential stats
        stats = POTENTIAL_STATS.get(lookup_tier, [])
        for stat in stats:
            if stat.stat_type == stat_type:
                return stat.value

        return 0.0

    def _update_auto_values(self):
        """Update auto-calculated values based on tier and yellow/grey selection."""
        if not hasattr(self, 'line_editors'):
            return

        tier_str = self.edit_tier.get()
        try:
            tier = PotentialTier(tier_str)
        except ValueError:
            tier = PotentialTier.LEGENDARY

        slot = self.edit_slot.get()

        for i, editor in enumerate(self.line_editors):
            # Determine if this line is yellow
            if i == 0:
                is_yellow = True  # Line 1 is always yellow
            else:
                color_combo = editor["color"]
                is_yellow = color_combo.get() == "Yellow" if color_combo else True

            # Get stat type from dropdown
            stat_name = editor["stat"].get()
            stat_type = self._stat_name_to_type(stat_name)

            # Get value for this stat at this tier
            value = self._get_stat_value_for_tier(stat_type, tier, is_yellow, slot)

            # Format the display
            if stat_type == StatType.MAIN_STAT_FLAT:
                value_text = f"{value:.0f}"
            elif stat_type == StatType.SKILL_CD:
                value_text = f"{value:.1f}s"
            else:
                value_text = f"{value:.1f}%"

            # Update the value label
            value_label = editor["value"]
            if is_yellow:
                value_label.config(text=value_text, fg='#ffd700', font=('Consolas', 9, 'bold'))
            else:
                value_label.config(text=value_text, fg='#888', font=('Consolas', 9))

    def _build_equipment_display(self, parent, slot: str):
        """Build a compact display for one equipment slot showing Regular and Bonus potentials."""
        frame = tk.Frame(parent, bg='#2a2a4e', padx=5, pady=3)
        frame.pack(fill=tk.X, pady=2, padx=2)

        # Slot name and tier
        header = tk.Frame(frame, bg='#2a2a4e')
        header.pack(fill=tk.X)

        slot_label = tk.Label(header, text=f"{slot.upper()}", width=10, anchor=tk.W,
                             font=('Segoe UI', 9, 'bold'), bg='#2a2a4e', fg='#ffd700')
        slot_label.pack(side=tk.LEFT)

        # Regular tier
        reg_tier_label = tk.Label(header, text="R:[LEG]", font=('Consolas', 7),
                                  bg='#2a2a4e', fg='#00ff88')
        reg_tier_label.pack(side=tk.LEFT, padx=2)

        # Bonus tier
        bonus_tier_label = tk.Label(header, text="B:[LEG]", font=('Consolas', 7),
                                    bg='#2a2a4e', fg='#ff88ff')
        bonus_tier_label.pack(side=tk.LEFT, padx=2)

        # Pity counters (compact layout on header right side)
        pity_frame = tk.Frame(header, bg='#2a2a4e')
        pity_frame.pack(side=tk.RIGHT, padx=2)

        # Regular pity
        tk.Label(pity_frame, text="R:", font=('Consolas', 7), bg='#2a2a4e', fg='#888').pack(side=tk.LEFT)
        reg_pity_var = tk.StringVar(value="0")
        reg_pity_entry = tk.Entry(pity_frame, textvariable=reg_pity_var, width=4,
                                  font=('Consolas', 7), bg='#1a1a2e', fg='#00ff88',
                                  insertbackground='#00ff88', justify=tk.CENTER)
        reg_pity_entry.pack(side=tk.LEFT, padx=1)
        reg_pity_entry.bind('<FocusOut>', lambda e, s=slot: self._on_pity_change(s, 'regular'))
        reg_pity_entry.bind('<Return>', lambda e, s=slot: self._on_pity_change(s, 'regular'))

        # Bonus pity
        tk.Label(pity_frame, text="B:", font=('Consolas', 7), bg='#2a2a4e', fg='#888').pack(side=tk.LEFT, padx=(3, 0))
        bonus_pity_var = tk.StringVar(value="0")
        bonus_pity_entry = tk.Entry(pity_frame, textvariable=bonus_pity_var, width=4,
                                    font=('Consolas', 7), bg='#1a1a2e', fg='#ff88ff',
                                    insertbackground='#ff88ff', justify=tk.CENTER)
        bonus_pity_entry.pack(side=tk.LEFT, padx=1)
        bonus_pity_entry.bind('<FocusOut>', lambda e, s=slot: self._on_pity_change(s, 'bonus'))
        bonus_pity_entry.bind('<Return>', lambda e, s=slot: self._on_pity_change(s, 'bonus'))

        # Regular lines display with score
        reg_row = tk.Frame(frame, bg='#2a2a4e')
        reg_row.pack(fill=tk.X)
        reg_lines_label = tk.Label(reg_row, text="Reg: (empty)", font=('Consolas', 7),
                                   bg='#2a2a4e', fg='#888', anchor=tk.W, justify=tk.LEFT)
        reg_lines_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        reg_score_label = tk.Label(reg_row, text="", font=('Consolas', 7, 'bold'),
                                   bg='#2a2a4e', fg='#888', anchor=tk.E)
        reg_score_label.pack(side=tk.RIGHT)

        # Bonus lines display with score
        bonus_row = tk.Frame(frame, bg='#2a2a4e')
        bonus_row.pack(fill=tk.X)
        bonus_lines_label = tk.Label(bonus_row, text="Bon: (empty)", font=('Consolas', 7),
                                     bg='#2a2a4e', fg='#888', anchor=tk.W, justify=tk.LEFT)
        bonus_lines_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        bonus_score_label = tk.Label(bonus_row, text="", font=('Consolas', 7, 'bold'),
                                     bg='#2a2a4e', fg='#888', anchor=tk.E)
        bonus_score_label.pack(side=tk.RIGHT)

        self.equip_displays[slot] = {
            "frame": frame,
            "reg_tier_label": reg_tier_label,
            "bonus_tier_label": bonus_tier_label,
            "reg_lines_label": reg_lines_label,
            "bonus_lines_label": bonus_lines_label,
            "reg_score_label": reg_score_label,
            "bonus_score_label": bonus_score_label,
            "reg_pity_var": reg_pity_var,
            "bonus_pity_var": bonus_pity_var,
            "reg_pity_entry": reg_pity_entry,
            "bonus_pity_entry": bonus_pity_entry,
        }

    def update_all_equipment_displays(self):
        """Update all equipment displays with current potential data."""
        # Calculate current DPS for scoring
        try:
            current_dps = self._calc_damage(self._get_damage_stats())
        except:
            current_dps = 0

        for slot, display in self.equip_displays.items():
            equip = self.equipment[slot]

            # Update Regular tier
            reg_tier_color = get_tier_color(equip.tier)
            tier_abbrev = equip.tier.value[:3].upper()
            display["reg_tier_label"].config(text=f"R:[{tier_abbrev}]", fg=reg_tier_color)

            # Update Bonus tier
            bonus_tier_color = get_tier_color(equip.bonus_tier)
            bonus_abbrev = equip.bonus_tier.value[:3].upper()
            display["bonus_tier_label"].config(text=f"B:[{bonus_abbrev}]", fg=bonus_tier_color)

            # Update pity counters (sync UI with data)
            if "reg_pity_var" in display:
                display["reg_pity_var"].set(str(equip.regular_pity))
            if "bonus_pity_var" in display:
                display["bonus_pity_var"].set(str(equip.bonus_pity))

            # Update Regular lines
            if equip.lines:
                lines_text = "Reg: "
                line_parts = []
                for line in equip.lines:
                    line_parts.append(format_line(line))
                lines_text += " | ".join(line_parts)
                display["reg_lines_label"].config(text=lines_text, fg='#ccc')
            else:
                display["reg_lines_label"].config(text="Reg: (none)", fg='#666')

            # Update Bonus lines
            if equip.bonus_lines:
                lines_text = "Bon: "
                line_parts = []
                for line in equip.bonus_lines:
                    line_parts.append(format_line(line))
                lines_text += " | ".join(line_parts)
                display["bonus_lines_label"].config(text=lines_text, fg='#d8b4ff')
            else:
                display["bonus_lines_label"].config(text="Bon: (none)", fg='#666')

            # Calculate and display DPS scores for each potential
            self._update_slot_dps_scores(slot, equip, display, current_dps)

        # Update total stats display
        self.update_total_stats_display()

    def _update_slot_dps_scores(self, slot: str, equip, display: dict, current_dps: float):
        """Calculate and display DPS scores for a slot's potentials."""
        if current_dps <= 0:
            # Can't calculate scores without DPS
            if "reg_score_label" in display:
                display["reg_score_label"].config(text="", fg='#666')
            if "bonus_score_label" in display:
                display["bonus_score_label"].config(text="", fg='#666')
            return

        # Calculate Regular potential score
        if equip.lines and "reg_score_label" in display:
            try:
                reg_result = self._analyze_potential_for_slot(
                    equip, slot, current_dps, is_bonus=False, diamond_cost=600
                )
                if reg_result and hasattr(reg_result, 'item_score'):
                    score = reg_result.item_score.dps_relative_score
                    # Color based on score
                    if score >= 70:
                        color = '#00ff88'  # Green
                    elif score >= 40:
                        color = '#ffd700'  # Yellow
                    else:
                        color = '#ff6b6b'  # Red
                    display["reg_score_label"].config(text=f"{score:.0f}%", fg=color)
                else:
                    display["reg_score_label"].config(text="", fg='#666')
            except Exception:
                display["reg_score_label"].config(text="", fg='#666')
        elif "reg_score_label" in display:
            display["reg_score_label"].config(text="", fg='#666')

        # Calculate Bonus potential score
        if equip.bonus_lines and "bonus_score_label" in display:
            try:
                bonus_result = self._analyze_potential_for_slot(
                    equip, slot, current_dps, is_bonus=True, diamond_cost=900
                )
                if bonus_result and hasattr(bonus_result, 'item_score'):
                    score = bonus_result.item_score.dps_relative_score
                    # Color based on score
                    if score >= 70:
                        color = '#00ff88'  # Green
                    elif score >= 40:
                        color = '#ffd700'  # Yellow
                    else:
                        color = '#ff6b6b'  # Red
                    display["bonus_score_label"].config(text=f"{score:.0f}%", fg=color)
                else:
                    display["bonus_score_label"].config(text="", fg='#666')
            except Exception:
                display["bonus_score_label"].config(text="", fg='#666')
        elif "bonus_score_label" in display:
            display["bonus_score_label"].config(text="", fg='#666')

    def _on_pity_change(self, slot: str, pot_type: str):
        """Handle pity counter value change from user input."""
        if slot not in self.equip_displays:
            return

        display = self.equip_displays[slot]
        equip = self.equipment[slot]

        try:
            if pot_type == 'regular':
                value = int(display["reg_pity_var"].get())
                equip.regular_pity = max(0, value)  # Ensure non-negative
                display["reg_pity_var"].set(str(equip.regular_pity))
            else:
                value = int(display["bonus_pity_var"].get())
                equip.bonus_pity = max(0, value)  # Ensure non-negative
                display["bonus_pity_var"].set(str(equip.bonus_pity))
        except ValueError:
            # Reset to current stored value if invalid input
            if pot_type == 'regular':
                display["reg_pity_var"].set(str(equip.regular_pity))
            else:
                display["bonus_pity_var"].set(str(equip.bonus_pity))

    def update_total_stats_display(self):
        """Update the total stats summary."""
        totals = self.get_potential_stats_total()
        # Check if any stat has value (handle list for final_damage_lines)
        has_any = any(
            (len(v) > 0 if isinstance(v, list) else v > 0)
            for v in totals.values()
        )

        if not has_any:
            self.total_stats_label.config(text="No potentials set yet")
            return

        text = ""
        if totals["damage_percent"] > 0:
            text += f"Damage %:      +{totals['damage_percent']:.1f}%\n"
        if totals["dex_percent"] > 0:
            text += f"Main Stat %:   +{totals['dex_percent']:.1f}%\n"
        if totals["crit_damage"] > 0:
            text += f"Crit Damage %: +{totals['crit_damage']:.1f}%\n"
        if totals["defense_pen"] > 0:
            text += f"Defense Pen %: +{totals['defense_pen']:.1f}%\n"
        if totals["final_damage"] > 0:
            text += f"Final Damage %: +{totals['final_damage']:.1f}%\n"
        if totals["crit_rate"] > 0:
            text += f"Crit Rate %:   +{totals['crit_rate']:.1f}%\n"
        if totals["all_skills"] > 0:
            text += f"All Skills:    +{totals['all_skills']:.0f}\n"

        self.total_stats_label.config(text=text.strip())

    def set_manual_potential(self):
        """Set potential lines manually from the editor."""
        slot = self.edit_slot.get()
        tier_str = self.edit_tier.get()
        tier = PotentialTier(tier_str)
        pot_type = self.edit_pot_type.get()  # "Regular" or "Bonus"
        is_bonus = (pot_type == "Bonus")

        # Parse lines using the line_editors structure
        lines = []
        for i, editor in enumerate(self.line_editors):
            stat_name = editor["stat"].get()
            stat_type = self._stat_name_to_type(stat_name)

            # Determine if yellow
            if i == 0:
                is_yellow = True
            else:
                color_combo = editor["color"]
                is_yellow = color_combo.get() == "Yellow" if color_combo else True

            # Get the auto-calculated value
            value = self._get_stat_value_for_tier(stat_type, tier, is_yellow, slot)

            # Check if this is a special potential
            is_special = False
            if slot in SPECIAL_POTENTIALS:
                special = SPECIAL_POTENTIALS[slot]
                if stat_type == special.stat_type:
                    is_special = True

            lines.append(PotentialLine(
                slot=i + 1,
                stat_type=stat_type,
                value=value,
                is_yellow=is_yellow,
                is_special=is_special
            ))

        # Apply to equipment (Regular or Bonus)
        if is_bonus:
            self.equipment[slot].bonus_tier = tier
            self.equipment[slot].bonus_lines = lines
        else:
            self.equipment[slot].tier = tier
            self.equipment[slot].lines = lines

        # Update displays
        self.update_all_equipment_displays()
        self.update_damage()

    def clear_all_potentials(self):
        """Clear all equipment potentials (both Regular and Bonus)."""
        for slot in EQUIPMENT_SLOTS:
            self.equipment[slot].lines = []
            self.equipment[slot].bonus_lines = []
            self.equipment[slot].tier = PotentialTier.LEGENDARY
            self.equipment[slot].bonus_tier = PotentialTier.LEGENDARY

        self.update_all_equipment_displays()
        self.update_damage()

    def save_potentials_to_csv(self, filepath: str = None):
        """Save all equipment potentials to a CSV file."""
        if filepath is None:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="potentials_save.csv",
                title="Save Potentials"
            )
            if not filepath:
                return  # User cancelled

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header row (added pity column)
                writer.writerow([
                    "slot", "pot_type", "tier", "pity",
                    "line1_stat", "line1_value", "line1_yellow", "line1_special",
                    "line2_stat", "line2_value", "line2_yellow", "line2_special",
                    "line3_stat", "line3_value", "line3_yellow", "line3_special"
                ])

                for slot in EQUIPMENT_SLOTS:
                    equip = self.equipment[slot]

                    # Save Regular potential (always save even if no lines, to preserve pity)
                    row = [slot, "regular", equip.tier.value, equip.regular_pity]
                    if equip.lines:
                        for i in range(3):
                            if i < len(equip.lines):
                                line = equip.lines[i]
                                row.extend([line.stat_type.value, line.value, line.is_yellow, line.is_special])
                            else:
                                row.extend(["", 0, False, False])
                    else:
                        # No lines but still save pity
                        row.extend(["", 0, False, False] * 3)
                    writer.writerow(row)

                    # Save Bonus potential (always save even if no lines, to preserve pity)
                    row = [slot, "bonus", equip.bonus_tier.value, equip.bonus_pity]
                    if equip.bonus_lines:
                        for i in range(3):
                            if i < len(equip.bonus_lines):
                                line = equip.bonus_lines[i]
                                row.extend([line.stat_type.value, line.value, line.is_yellow, line.is_special])
                            else:
                                row.extend(["", 0, False, False])
                    else:
                        # No lines but still save pity
                        row.extend(["", 0, False, False] * 3)
                    writer.writerow(row)

            messagebox.showinfo("Saved", f"Potentials saved to:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save potentials:\n{str(e)}")

    def load_potentials_from_csv(self, filepath: str = None, silent: bool = False):
        """Load equipment potentials from a CSV file."""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Load Potentials"
            )
            if not filepath:
                return  # User cancelled

        try:
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    slot = row["slot"]
                    if slot not in EQUIPMENT_SLOTS:
                        continue

                    pot_type = row["pot_type"]
                    tier = PotentialTier(row["tier"])

                    # Parse pity counter (default to 0 for backward compatibility)
                    try:
                        pity = int(row.get("pity", 0))
                    except (ValueError, TypeError):
                        pity = 0

                    # Parse the 3 lines
                    lines = []
                    for i in range(1, 4):
                        stat_str = row.get(f"line{i}_stat", "")
                        if not stat_str:
                            continue

                        try:
                            stat_type = StatType(stat_str)
                            value = float(row.get(f"line{i}_value", 0))
                            is_yellow = row.get(f"line{i}_yellow", "False").lower() == "true"
                            is_special = row.get(f"line{i}_special", "False").lower() == "true"

                            lines.append(PotentialLine(
                                slot=i,
                                stat_type=stat_type,
                                value=value,
                                is_yellow=is_yellow,
                                is_special=is_special
                            ))
                        except (ValueError, KeyError):
                            continue

                    # Apply to equipment
                    if pot_type == "regular":
                        self.equipment[slot].tier = tier
                        self.equipment[slot].lines = lines
                        self.equipment[slot].regular_pity = pity
                    elif pot_type == "bonus":
                        self.equipment[slot].bonus_tier = tier
                        self.equipment[slot].bonus_lines = lines
                        self.equipment[slot].bonus_pity = pity

            self.update_all_equipment_displays()
            self.update_damage()
            # Auto-update skill bonuses from potentials
            self.auto_update_skill_bonuses()
            if not silent:
                messagebox.showinfo("Loaded", f"Potentials loaded from:\n{filepath}")

        except FileNotFoundError:
            if not silent:
                messagebox.showwarning("Not Found", f"File not found:\n{filepath}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load potentials:\n{str(e)}")

    def auto_load_potentials(self):
        """Automatically load potentials from default save file on startup."""
        if os.path.exists(POTENTIALS_SAVE_FILE):
            self.load_potentials_from_csv(POTENTIALS_SAVE_FILE, silent=True)

    def analyze_cube_priority(self):
        """
        Analyze which equipment to cube next using the enhanced scoring system.

        New system features:
        1. Item Score (0-100): Rates current roll quality relative to best possible
        2. Expected Cubes: Monte Carlo simulation for improvement thresholds
        3. Efficiency Formula: (Improvement_Room × Tier_Weight) / (Expected_Cubes × Cost)
        4. Stat Rankings: Top 5 stats by DPS gain for each slot
        5. Diminishing Returns: Warnings when 2+ useful yellows already exist

        This properly prioritizes:
        - Bad mythic rolls over decent legendary rolls
        - Easy improvements over marginal gains on good rolls
        """
        REGULAR_DIAMOND_PER_CUBE = 600   # Best rate from monthly package
        BONUS_DIAMOND_PER_CUBE = 1200    # Best rate from monthly package (2x regular)

        # Calculate current DPS (includes all equipped potentials)
        current_dps = self._calc_damage(self._get_damage_stats())

        if current_dps <= 0:
            current_dps = 1  # Avoid division by zero

        # Show loading message
        self.recommendation_text.config(state=tk.NORMAL)
        self.recommendation_text.delete(1.0, tk.END)
        self.recommendation_text.insert(tk.END, "Analyzing cube priorities...\n")
        self.recommendation_text.config(state=tk.DISABLED)
        self.root.update()

        results: List[EnhancedCubeRecommendation] = []

        for slot in EQUIPMENT_SLOTS:
            equip = self.equipment[slot]

            # Analyze REGULAR potential
            reg_result = self._analyze_potential_for_slot(
                equip, slot, current_dps,
                is_bonus=False,
                diamond_cost=REGULAR_DIAMOND_PER_CUBE,
            )
            if reg_result:
                results.append(reg_result)

            # Analyze BONUS potential
            bonus_result = self._analyze_potential_for_slot(
                equip, slot, current_dps,
                is_bonus=True,
                diamond_cost=BONUS_DIAMOND_PER_CUBE,
            )
            if bonus_result:
                results.append(bonus_result)

        # Sort by efficiency score (higher = better to cube)
        results.sort(key=lambda x: x.efficiency_score, reverse=True)

        # Assign priority ranks
        for i, r in enumerate(results):
            # Create a new recommendation with the rank set
            results[i] = EnhancedCubeRecommendation(
                slot=r.slot,
                tier=r.tier,
                is_bonus=r.is_bonus,
                item_score=r.item_score,
                expected_cubes=r.expected_cubes,
                efficiency_score=r.efficiency_score,
                top_stats=r.top_stats,
                current_lines_formatted=r.current_lines_formatted,
                priority_rank=i + 1
            )

        # Build recommendation text with new format
        self.recommendation_text.config(state=tk.NORMAL)
        self.recommendation_text.delete(1.0, tk.END)

        self.recommendation_text.insert(tk.END, "CUBE PRIORITY (Enhanced Scoring System)\n")
        self.recommendation_text.insert(tk.END, "═" * 54 + "\n\n")

        self.recommendation_text.insert(tk.END, f"Current DPS: {current_dps:,.0f}\n\n")

        # Show top 10 recommendations
        for r in results[:10]:
            slot_upper = r.slot.upper()
            tier_upper = r.tier.value.upper()
            pot_type = "REG" if not r.is_bonus else "BON"
            dps_score = r.item_score.dps_relative_score  # DPS-based score (main display)
            pct_score = r.item_score.total_score  # Percentile score
            current_dps = r.item_score.current_dps_gain
            max_dps = r.item_score.best_possible_dps_gain

            # Score color indicator based on DPS-relative score
            if dps_score < 30:
                score_indicator = "🔴"  # Poor
            elif dps_score < 60:
                score_indicator = "🟡"  # Okay
            else:
                score_indicator = "🟢"  # Good

            # Header line - show DPS score and current/max DPS
            line = f"#{r.priority_rank}. {slot_upper:<10} [{tier_upper}] {pot_type}\n"
            self.recommendation_text.insert(tk.END, line)

            # DPS Impact Summary
            self.recommendation_text.insert(tk.END, "\n")
            self.recommendation_text.insert(tk.END, "    📈 DPS Impact:\n")
            self.recommendation_text.insert(tk.END,
                f"    ├─ Current Roll: +{current_dps:.2f}% DPS\n")
            self.recommendation_text.insert(tk.END,
                f"    ├─ Best Possible: +{max_dps:.2f}% DPS\n")
            self.recommendation_text.insert(tk.END,
                f"    ├─ Room to Improve: +{max_dps - current_dps:.2f}% DPS\n")
            self.recommendation_text.insert(tk.END,
                f"    └─ Efficiency: {dps_score:.0f}% of max {score_indicator}\n")

            # Current lines with individual DPS contributions
            self.recommendation_text.insert(tk.END, "\n")
            self.recommendation_text.insert(tk.END, "    📋 Current Lines:\n")
            for cl in r.current_lines_formatted:
                self.recommendation_text.insert(tk.END, f"    ├─ {cl}\n")

            # Expected cubes section
            self.recommendation_text.insert(tk.END, "\n")
            self.recommendation_text.insert(tk.END, "    📊 Expected Cubes:\n")

            exp = r.expected_cubes
            if exp.cubes_to_any_improvement < 500:
                self.recommendation_text.insert(tk.END,
                    f"    ├─ Any improvement: ~{exp.cubes_to_any_improvement:.0f} cubes\n")
            else:
                self.recommendation_text.insert(tk.END,
                    f"    ├─ Any improvement: Very difficult (500+ cubes)\n")

            # Show DPS-based thresholds (50%, 70%, 85% of max)
            if exp.cubes_to_score_60 > 0 and exp.cubes_to_score_60 < 500:
                self.recommendation_text.insert(tk.END,
                    f"    ├─ 50% of max DPS: ~{exp.cubes_to_score_60:.0f} cubes\n")
            if exp.cubes_to_score_80 > 0 and exp.cubes_to_score_80 < 500:
                self.recommendation_text.insert(tk.END,
                    f"    ├─ 70% of max DPS: ~{exp.cubes_to_score_80:.0f} cubes\n")

            # Improvement probability
            self.recommendation_text.insert(tk.END,
                f"    └─ {exp.prob_improve_10_cubes*100:.0f}% chance to improve in 10 cubes\n")

            # Pity and tier-up section (only if not Mystic tier)
            if r.tier != PotentialTier.MYSTIC and exp.pity_threshold < 999999:
                self.recommendation_text.insert(tk.END, "\n")
                self.recommendation_text.insert(tk.END, "    🎲 Tier-Up Progress:\n")

                # Pity counter
                pity_pct = (exp.current_pity / exp.pity_threshold) * 100 if exp.pity_threshold > 0 else 0
                pity_bar_len = int(pity_pct / 10)  # 10 chars max
                pity_bar = "█" * pity_bar_len + "░" * (10 - pity_bar_len)
                self.recommendation_text.insert(tk.END,
                    f"    ├─ Pity: {exp.current_pity}/{exp.pity_threshold} [{pity_bar}] {pity_pct:.0f}%\n")

                # Expected cubes to tier up
                if exp.cubes_to_tier_up < float('inf'):
                    self.recommendation_text.insert(tk.END,
                        f"    ├─ Expected tier-up: ~{exp.cubes_to_tier_up:.0f} cubes\n")

                # Score gain from tier-up
                if exp.tier_up_score_gain > 0:
                    self.recommendation_text.insert(tk.END,
                        f"    └─ Tier-up score boost: +{exp.tier_up_score_gain:.0f} pts potential\n")

                # Tier-up bonus indicator
                if exp.tier_up_efficiency_bonus > 0.01:
                    self.recommendation_text.insert(tk.END,
                        f"    📈 Tier-up bonus applied to efficiency!\n")

            # Diminishing returns warning
            if exp.improvement_difficulty in ("Hard", "Very Hard"):
                self.recommendation_text.insert(tk.END, "\n")
                self.recommendation_text.insert(tk.END,
                    f"    ⚠️ DIMINISHING RETURNS: {exp.diminishing_returns_warning}\n")

            # Efficiency score
            self.recommendation_text.insert(tk.END, "\n")
            self.recommendation_text.insert(tk.END,
                f"    ⚡ Difficulty: {exp.improvement_difficulty.upper()}\n")
            self.recommendation_text.insert(tk.END,
                f"    💎 Efficiency: {r.efficiency_score:.2f}")
            if r.priority_rank == 1:
                self.recommendation_text.insert(tk.END, " (BEST)")
            self.recommendation_text.insert(tk.END, "\n")

            # Top stats to target
            if r.top_stats:
                self.recommendation_text.insert(tk.END, "\n")
                self.recommendation_text.insert(tk.END, "    🎯 Stats to Target:\n")
                for j, (stat_name, dps_gain, prob) in enumerate(r.top_stats[:5], 1):
                    self.recommendation_text.insert(tk.END,
                        f"    {j}. {stat_name}: +{dps_gain:.2f}% DPS ({prob:.1f}% chance)\n")

            self.recommendation_text.insert(tk.END, "\n")
            self.recommendation_text.insert(tk.END, "─" * 54 + "\n\n")

        # Legend
        self.recommendation_text.insert(tk.END, "═" * 54 + "\n")
        self.recommendation_text.insert(tk.END, "LEGEND\n")
        self.recommendation_text.insert(tk.END, "─" * 54 + "\n")
        self.recommendation_text.insert(tk.END, "📈 DPS Impact: How much this potential adds to your damage\n")
        self.recommendation_text.insert(tk.END, "   • Current Roll: DPS gain from your current lines\n")
        self.recommendation_text.insert(tk.END, "   • Best Possible: DPS from perfect 3-line roll\n")
        self.recommendation_text.insert(tk.END, "   • Room to Improve: Gap between current and best\n")
        self.recommendation_text.insert(tk.END, "\n")
        self.recommendation_text.insert(tk.END, "Efficiency Score: 🔴 <30%  🟡 30-59%  🟢 60%+\n")
        self.recommendation_text.insert(tk.END, "[Y] = Yellow line (current tier)  [G] = Grey line (lower tier)\n")
        self.recommendation_text.insert(tk.END, "⭐ = Special potential | REG = Regular | BON = Bonus\n")
        self.recommendation_text.insert(tk.END, "\nItems sorted by: Most improvement potential per cube\n")

        self.recommendation_text.config(state=tk.DISABLED)

    def _analyze_potential_for_slot(
        self, equip, slot: str, current_dps: float,
        is_bonus: bool, diamond_cost: int,
    ) -> Optional[EnhancedCubeRecommendation]:
        """
        Analyze a single potential type (regular or bonus) for an equipment slot.

        Returns EnhancedCubeRecommendation with:
        - Item score (0-100) rating current roll quality
        - Expected cubes to reach improvement thresholds
        - Efficiency score for prioritization
        - Top stats by DPS gain
        - Diminishing returns warnings

        Args:
            equip: Equipment item to analyze
            slot: Equipment slot name
            current_dps: Current calculated DPS
            is_bonus: True for bonus potential, False for regular
            diamond_cost: Cost per cube in diamonds
            run_simulation: Whether to run Monte Carlo simulation (slower but more accurate)
            simulation_iterations: Number of iterations for simulation

        Returns:
            EnhancedCubeRecommendation or None if no stats available
        """
        # Get the appropriate tier and lines based on potential type
        tier = equip.bonus_tier if is_bonus else equip.tier
        current_lines = equip.bonus_lines if is_bonus else equip.lines

        tier_stats = POTENTIAL_STATS.get(tier, [])
        if not tier_stats:
            return None

        # Calculate BASELINE DPS (with empty potential lines on this slot)
        # This is what we compare test rolls against
        if is_bonus:
            old_lines = equip.bonus_lines
            equip.bonus_lines = []
            baseline_dps = self._calc_damage(self._get_damage_stats())
            equip.bonus_lines = old_lines
        else:
            old_lines = equip.lines
            equip.lines = []
            baseline_dps = self._calc_damage(self._get_damage_stats())
            equip.lines = old_lines

        if baseline_dps <= 0:
            baseline_dps = 1  # Avoid division by zero

        # Create DPS calculation function that temporarily swaps lines
        # NOTE: This returns DPS with test_lines, compared against baseline_dps (empty slot)
        def calc_dps_with_lines(test_lines: List[PotentialLine]) -> float:
            """Calculate DPS with the given potential lines on this slot."""
            if is_bonus:
                old_lines = equip.bonus_lines
                equip.bonus_lines = test_lines
                new_dps = self._calc_damage(self._get_damage_stats())
                equip.bonus_lines = old_lines
            else:
                old_lines = equip.lines
                equip.lines = test_lines
                new_dps = self._calc_damage(self._get_damage_stats())
                equip.lines = old_lines
            return new_dps

        # Get main stat type (TODO: make configurable for other classes)
        main_stat_type = StatType.DEX_PCT

        # Calculate item score using new system
        # Use baseline_dps (empty slot) as reference, not current_dps (which includes current lines)
        item_score = create_item_score_result(
            lines=current_lines,
            tier=tier,
            slot=slot,
            dps_calc_func=calc_dps_with_lines,
            current_dps=baseline_dps,  # Compare against empty slot, not current roll
            main_stat_type=main_stat_type
        )

        # Get current pity counter
        current_pity = equip.bonus_pity if is_bonus else equip.regular_pity
        cube_type = CubeType.BONUS if is_bonus else CubeType.REGULAR

        # Calculate expected cubes metrics using FAST cached roll distribution
        # This is ~50-100x faster than the old Monte Carlo approach
        # Use baseline_dps for consistent comparison
        expected_cubes = calculate_expected_cubes_fast(
            slot=slot,
            tier=tier,
            current_lines=current_lines,
            dps_calc_func=calc_dps_with_lines,
            current_dps=baseline_dps,  # Compare against empty slot
            main_stat_type=main_stat_type,
            current_pity=current_pity,
            cube_type=cube_type,
            n_cached_rolls=5000,  # 5000 rolls gives good accuracy
        )

        # Calculate efficiency score (now includes tier-up bonus)
        # Use dps_relative_score for efficiency (how much of max potential are we getting?)
        efficiency = calculate_efficiency_score(
            current_score=item_score.dps_relative_score,  # Use DPS-based score for efficiency
            tier=tier,
            expected_cubes_to_improve=expected_cubes.cubes_to_any_improvement,
            diamond_cost_per_cube=diamond_cost,
            tier_up_efficiency_bonus=expected_cubes.tier_up_efficiency_bonus,
        )

        # Get top stats by DPS gain
        top_stats = calculate_stat_rankings(
            slot=slot,
            tier=tier,
            dps_calc_func=calc_dps_with_lines,
            current_dps=baseline_dps,  # Compare against empty slot
            main_stat_type=main_stat_type,
            top_n=5
        )

        # Format current lines for display
        current_lines_formatted = []
        for i, line in enumerate(current_lines[:3], 1):
            stat_name = get_stat_display_name(line.stat_type)
            # Format value (flat stats vs percentage)
            if line.stat_type in (StatType.DEX_FLAT, StatType.STR_FLAT,
                                  StatType.INT_FLAT, StatType.LUK_FLAT,
                                  StatType.MAIN_STAT_FLAT, StatType.ALL_SKILLS):
                val_str = f"+{int(line.value)}"
            else:
                val_str = f"+{line.value:.1f}%"

            tier_marker = "Y" if line.is_yellow else "G"
            special_marker = " ⭐" if line.is_special else ""

            # Include per-line DPS gain (line_scores now contains DPS gain %)
            line_dps_gain = item_score.line_scores[i-1] if i <= len(item_score.line_scores) else 0
            current_lines_formatted.append(
                f"L{i} [{tier_marker}]: {stat_name} {val_str}{special_marker} (+{line_dps_gain:.2f}% DPS)"
            )

        return EnhancedCubeRecommendation(
            slot=slot,
            tier=tier,
            is_bonus=is_bonus,
            item_score=item_score,
            expected_cubes=expected_cubes,
            efficiency_score=efficiency,
            top_stats=top_stats,
            current_lines_formatted=current_lines_formatted,
            priority_rank=0  # Will be set after sorting
        )

    def run_cube_simulation(self):
        """
        Run Monte Carlo simulation for the selected equipment slot.
        Shows probability of improvement with N cubes, including tier-up tracking.
        """
        # Get cube count from input
        try:
            n_cubes = int(self.sim_cube_count.get())
            if n_cubes <= 0:
                raise ValueError("Must be positive")
            if n_cubes > 10000:
                n_cubes = 10000  # Cap at 10k for performance
        except ValueError:
            self.sim_results_text.config(state=tk.NORMAL)
            self.sim_results_text.delete(1.0, tk.END)
            self.sim_results_text.insert(tk.END, "Error: Enter a valid number of cubes (1-10000)")
            self.sim_results_text.config(state=tk.DISABLED)
            return

        # Get starting pity from input
        try:
            starting_pity = int(self.sim_pity_count.get())
            if starting_pity < 0:
                starting_pity = 0
        except ValueError:
            starting_pity = 0

        # Get selected slot and type
        slot = self.edit_slot.get()
        tier_str = self.edit_tier.get()
        pot_type = self.edit_pot_type.get()
        is_bonus = pot_type == "Bonus"

        try:
            tier = PotentialTier(tier_str)
        except ValueError:
            tier = PotentialTier.LEGENDARY

        # Get current lines for this slot
        equip = self.equipment[slot]
        current_lines = equip.bonus_lines if is_bonus else equip.lines
        current_dps = self._calc_damage(self._get_damage_stats())

        if current_dps <= 0:
            current_dps = 1

        # Create DPS calculation function for scorer
        def calc_dps_with_lines(test_lines: List[PotentialLine]) -> float:
            """Calculate DPS with the given potential lines on the selected slot."""
            if is_bonus:
                old_lines = equip.bonus_lines
                equip.bonus_lines = test_lines
                new_dps = self._calc_damage(self._get_damage_stats())
                equip.bonus_lines = old_lines
            else:
                old_lines = equip.lines
                equip.lines = test_lines
                new_dps = self._calc_damage(self._get_damage_stats())
                equip.lines = old_lines
            return new_dps

        # Create scorer
        scorer = PotentialRollScorer(
            slot=slot,
            tier=tier,
            dps_calc_func=calc_dps_with_lines,
            current_dps=current_dps,
            main_stat_type=StatType.DEX_PCT  # Bowmaster uses DEX
        )

        # Update UI to show running
        self.sim_results_text.config(state=tk.NORMAL)
        self.sim_results_text.delete(1.0, tk.END)
        self.sim_results_text.insert(tk.END, f"Running simulation ({n_cubes} cubes, 500 iterations)...\n")
        self.sim_results_text.config(state=tk.DISABLED)
        self.root.update()

        # Run simulation with starting pity
        result = simulate_n_cubes_keep_best(
            scorer=scorer,
            current_lines=current_lines,
            n_cubes=n_cubes,
            iterations=500,  # 500 iterations for reasonable speed
            starting_pity=starting_pity
        )

        # Format and display results
        output_lines = []

        # Header with slot info
        pot_type_str = "BONUS" if is_bonus else "REG"
        output_lines.append(f"{slot.upper()} [{tier.value.upper()}] {pot_type_str}")
        output_lines.append(f"Current Score: {result.current_score:.0f}/100 (+{result.current_dps_gain:.2f}% DPS)")

        # Show current lines
        if current_lines:
            output_lines.append("")
            output_lines.append("Current lines:")
            for i, line in enumerate(current_lines[:3], 1):
                stat_name = get_stat_display_name(line.stat_type)
                if line.stat_type in (StatType.DEX_FLAT, StatType.STR_FLAT,
                                      StatType.INT_FLAT, StatType.LUK_FLAT,
                                      StatType.MAIN_STAT_FLAT, StatType.ALL_SKILLS):
                    val_str = f"+{int(line.value)}"
                else:
                    val_str = f"+{line.value:.1f}%"
                tier_marker = "Y" if line.is_yellow else "G"
                special_marker = " ⭐" if line.is_special else ""
                output_lines.append(f"  L{i}[{tier_marker}]: {stat_name} {val_str}{special_marker}")

        output_lines.append("")
        output_lines.append(f"With {n_cubes} cubes (500 simulations):")
        output_lines.append(f"├─ {result.prob_improve * 100:.0f}% chance to improve")

        # Show threshold probabilities (only relevant ones)
        for thresh in sorted(result.prob_score_thresholds.keys(), reverse=True):
            prob = result.prob_score_thresholds[thresh]
            if prob > 0.01:  # Only show if > 1% chance
                output_lines.append(f"├─ {prob * 100:.0f}% chance to hit {thresh}+ score")

        output_lines.append(f"├─ Expected best: Score {result.expected_best_score:.0f} (+{result.expected_best_dps_gain:.2f}% DPS)")
        output_lines.append(f"├─ Median best: Score {result.median_best_score:.0f}")

        # Risk analysis
        if result.prob_worse > 0:
            output_lines.append(f"└─ {result.prob_worse * 100:.0f}% risk of not improving")
        else:
            output_lines.append(f"└─ 0% risk (will always improve or tie)")

        # Tier-up and Pity section
        output_lines.append("")
        output_lines.append("TIER-UP PROGRESS:")
        output_lines.append(f"├─ Starting pity: {starting_pity}/{result.pity_threshold}")
        output_lines.append(f"├─ {result.prob_tier_up * 100:.0f}% chance to tier up")
        output_lines.append(f"├─ Expected tier-ups: {result.expected_tier_ups:.2f}")
        output_lines.append(f"└─ Expected pity after: {result.expected_pity_after:.0f}/{result.pity_threshold}")

        # Show next tier potential if not already Mystic
        next_tier = tier.next_tier()
        if next_tier and result.prob_tier_up > 0:
            output_lines.append("")
            output_lines.append(f"If tier up to {next_tier.value.upper()}:")
            output_lines.append(f"  Better stats available at higher tier!")

        # Diamond cost estimate
        diamond_cost = n_cubes * (1200 if is_bonus else 600)
        output_lines.append("")
        output_lines.append(f"Cost: {diamond_cost:,} diamonds ({n_cubes} x {'1200' if is_bonus else '600'})")

        # Recommendation - now considers tier-up potential
        output_lines.append("")
        if result.prob_tier_up >= 0.50:
            output_lines.append("VERDICT: Good chance to TIER UP - worth cubing!")
        elif result.prob_improve >= 0.90:
            output_lines.append("VERDICT: HIGHLY LIKELY to improve")
        elif result.prob_improve >= 0.70:
            output_lines.append("VERDICT: Good chance to improve")
        elif result.prob_improve >= 0.50:
            output_lines.append("VERDICT: Coin flip - consider more cubes")
        elif result.expected_pity_after > starting_pity + n_cubes * 0.8:
            # Close to pity
            pity_remaining = result.pity_threshold - result.expected_pity_after
            output_lines.append(f"VERDICT: Building pity (~{pity_remaining:.0f} more to guarantee)")
        else:
            output_lines.append("VERDICT: Low chance - current roll is solid")

        self.sim_results_text.config(state=tk.NORMAL)
        self.sim_results_text.delete(1.0, tk.END)
        self.sim_results_text.insert(tk.END, "\n".join(output_lines))
        self.sim_results_text.config(state=tk.DISABLED)


    # =========================================================================
    # EQUIPMENT TAB
    # =========================================================================

    def build_equipment_tab(self):
        """Build the Equipment tracking tab with list and editor."""
        # Main container with two columns
        main_frame = ttk.Frame(self.equipment_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEFT COLUMN - Equipment List
        left_frame = tk.Frame(main_frame, bg='#1a1a2e')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Title
        tk.Label(left_frame, text="EQUIPMENT LIST", font=('Segoe UI', 14, 'bold'),
                 fg='#ffd700', bg='#1a1a2e').pack(anchor=tk.W, pady=(0, 10))

        # Equipment list with scrollbar
        list_container = tk.Frame(left_frame, bg='#2a2a4e')
        list_container.pack(fill=tk.BOTH, expand=True)

        # Headers
        header_frame = tk.Frame(list_container, bg='#3a3a5e')
        header_frame.pack(fill=tk.X)
        headers = [("Slot", 80), ("Name", 120), ("Rarity", 50), ("Tier", 40), ("Stars", 50)]
        for text, width in headers:
            tk.Label(header_frame, text=text, font=('Segoe UI', 9, 'bold'),
                     fg='#ccc', bg='#3a3a5e', width=width // 8).pack(side=tk.LEFT, padx=2, pady=3)

        # Scrollable equipment rows
        canvas = tk.Canvas(list_container, bg='#2a2a4e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        self.equip_list_frame = tk.Frame(canvas, bg='#2a2a4e')

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=self.equip_list_frame, anchor=tk.NW)

        self.equip_list_frame.bind('<Configure>',
                                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Create row widgets for each slot
        self.equip_row_widgets = {}
        for slot in EQUIPMENT_SLOTS:
            self._create_equipment_row(slot)

        # Total stats section
        stats_frame = tk.Frame(left_frame, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(stats_frame, text="TOTAL STATS (with Starforce)", font=('Segoe UI', 11, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(anchor=tk.W, padx=10, pady=5)

        self.equip_total_stats = tk.Label(stats_frame, text="",
                                          font=('Consolas', 10), fg='#aaa', bg='#2a2a4e',
                                          justify=tk.LEFT)
        self.equip_total_stats.pack(anchor=tk.W, padx=10, pady=5)

        # Save/Load buttons
        btn_frame = tk.Frame(left_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(btn_frame, text="Save Equipment", command=self.save_equipment_to_csv,
                  bg='#4a4a6a', fg='white', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Load Equipment", command=self.load_equipment_from_csv,
                  bg='#4a4a6a', fg='white', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=5)

        # RIGHT COLUMN - Equipment Editor (scrollable)
        right_container = tk.Frame(main_frame, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(10, 0))

        # Create canvas and scrollbar for the editor
        right_canvas = tk.Canvas(right_container, bg='#2a2a4e', highlightthickness=0, width=340)
        right_scrollbar = ttk.Scrollbar(right_container, orient="vertical", command=right_canvas.yview)
        right_frame = tk.Frame(right_canvas, bg='#2a2a4e')

        right_frame.bind("<Configure>", lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all")))
        right_canvas.create_window((0, 0), window=right_frame, anchor="nw")
        right_canvas.configure(yscrollcommand=right_scrollbar.set)

        right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mouse wheel scrolling on the editor
        def _on_mousewheel(event):
            right_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        right_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        tk.Label(right_frame, text="EDIT EQUIPMENT", font=('Segoe UI', 14, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(anchor=tk.W, padx=10, pady=10)

        # Slot selector
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="Slot:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_slot = ttk.Combobox(row, values=EQUIPMENT_SLOTS, width=15)
        self.equip_edit_slot.pack(side=tk.LEFT)
        self.equip_edit_slot.set(EQUIPMENT_SLOTS[0])
        self.equip_edit_slot.bind('<<ComboboxSelected>>', self._on_equip_slot_selected)

        # Name entry
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="Name:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_name = tk.Entry(row, width=18, bg='#3a3a5e', fg='white',
                                        insertbackground='white')
        self.equip_edit_name.pack(side=tk.LEFT)

        # Rarity selector
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="Rarity:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_rarity = ttk.Combobox(row,
                                               values=["epic", "unique", "legendary", "mystic"],
                                               width=15)
        self.equip_edit_rarity.pack(side=tk.LEFT)
        self.equip_edit_rarity.set("unique")

        # Tier selector (radio buttons)
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="Tier:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_tier = tk.IntVar(value=4)
        for t in [4, 3, 2, 1]:
            tk.Radiobutton(row, text=f"T{t}", variable=self.equip_edit_tier, value=t,
                           bg='#2a2a4e', fg='#ccc', selectcolor='#4a4a6a',
                           activebackground='#2a2a4e').pack(side=tk.LEFT)

        # Stars slider
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="Stars:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_stars = tk.Scale(row, from_=0, to=25, orient=tk.HORIZONTAL,
                                         bg='#2a2a4e', fg='#ffd700', highlightthickness=0,
                                         length=150, command=self._update_equip_preview)
        self.equip_edit_stars.pack(side=tk.LEFT)

        # Separator
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=10)

        # BASE STATS section (Main Amplify)
        tk.Label(right_frame, text="MAIN STATS (Main Amplify)", font=('Segoe UI', 11, 'bold'),
                 fg='#4a9eff', bg='#2a2a4e').pack(anchor=tk.W, padx=10)

        # Base Attack
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Attack:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_attack = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                          insertbackground='white')
        self.equip_edit_attack.pack(side=tk.LEFT)
        self.equip_edit_attack.insert(0, "0")

        # Base Max HP
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Max HP:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_hp = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                      insertbackground='white')
        self.equip_edit_hp.pack(side=tk.LEFT)
        self.equip_edit_hp.insert(0, "0")

        # 3rd Main Stat (label changes based on slot)
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        self.equip_third_stat_label = tk.Label(row, text="Main Stat:", font=('Segoe UI', 10),
                                               fg='#ccc', bg='#2a2a4e', width=12, anchor=tk.W)
        self.equip_third_stat_label.pack(side=tk.LEFT)
        self.equip_edit_third_stat = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                              insertbackground='white')
        self.equip_edit_third_stat.pack(side=tk.LEFT)
        self.equip_edit_third_stat.insert(0, "0")

        # Separator
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # SUB STATS section (Sub Amplify)
        tk.Label(right_frame, text="SUB STATS (Sub Amplify)", font=('Segoe UI', 11, 'bold'),
                 fg='#ff9f43', bg='#2a2a4e').pack(anchor=tk.W, padx=10)

        # Boss Damage
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Boss Dmg %:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_boss_dmg = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                            insertbackground='white')
        self.equip_edit_boss_dmg.pack(side=tk.LEFT)
        self.equip_edit_boss_dmg.insert(0, "0")

        # Normal Damage
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Normal Dmg %:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_normal_dmg = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                              insertbackground='white')
        self.equip_edit_normal_dmg.pack(side=tk.LEFT)
        self.equip_edit_normal_dmg.insert(0, "0")

        # Crit Rate
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Crit Rate %:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_crit_rate = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                             insertbackground='white')
        self.equip_edit_crit_rate.pack(side=tk.LEFT)
        self.equip_edit_crit_rate.insert(0, "0")

        # Crit Damage
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Crit Dmg %:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_crit_dmg = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                            insertbackground='white')
        self.equip_edit_crit_dmg.pack(side=tk.LEFT)
        self.equip_edit_crit_dmg.insert(0, "0")

        # Flat Attack
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Attack (flat):", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_edit_attack_flat = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                               insertbackground='white')
        self.equip_edit_attack_flat.pack(side=tk.LEFT)
        self.equip_edit_attack_flat.insert(0, "0")

        # Job-specific skills in a compact row (available on all equipment)
        row = tk.Frame(right_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Job Skills:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)

        tk.Label(row, text="1st:", font=('Segoe UI', 9), fg='#888', bg='#2a2a4e').pack(side=tk.LEFT)
        self.equip_edit_skill_1st = tk.Entry(row, width=4, bg='#3a3a5e', fg='white',
                                             insertbackground='white')
        self.equip_edit_skill_1st.pack(side=tk.LEFT, padx=2)
        self.equip_edit_skill_1st.insert(0, "0")

        tk.Label(row, text="2nd:", font=('Segoe UI', 9), fg='#888', bg='#2a2a4e').pack(side=tk.LEFT)
        self.equip_edit_skill_2nd = tk.Entry(row, width=4, bg='#3a3a5e', fg='white',
                                             insertbackground='white')
        self.equip_edit_skill_2nd.pack(side=tk.LEFT, padx=2)
        self.equip_edit_skill_2nd.insert(0, "0")

        tk.Label(row, text="3rd:", font=('Segoe UI', 9), fg='#888', bg='#2a2a4e').pack(side=tk.LEFT)
        self.equip_edit_skill_3rd = tk.Entry(row, width=4, bg='#3a3a5e', fg='white',
                                             insertbackground='white')
        self.equip_edit_skill_3rd.pack(side=tk.LEFT, padx=2)
        self.equip_edit_skill_3rd.insert(0, "0")

        tk.Label(row, text="4th:", font=('Segoe UI', 9), fg='#888', bg='#2a2a4e').pack(side=tk.LEFT)
        self.equip_edit_skill_4th = tk.Entry(row, width=4, bg='#3a3a5e', fg='white',
                                             insertbackground='white')
        self.equip_edit_skill_4th.pack(side=tk.LEFT, padx=2)
        self.equip_edit_skill_4th.insert(0, "0")

        # Separator
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        # SPECIAL STATS section (for special items only)
        special_header = tk.Frame(right_frame, bg='#2a2a4e')
        special_header.pack(fill=tk.X, padx=10)
        tk.Label(special_header, text="SPECIAL", font=('Segoe UI', 11, 'bold'),
                 fg='#ff6b6b', bg='#2a2a4e').pack(side=tk.LEFT)
        self.equip_edit_is_special = tk.BooleanVar(value=False)
        tk.Checkbutton(special_header, text="Special Item", variable=self.equip_edit_is_special,
                       bg='#2a2a4e', fg='#ccc', selectcolor='#4a4a6a',
                       activebackground='#2a2a4e', command=self._update_special_stats_visibility
                       ).pack(side=tk.LEFT, padx=10)

        # Container for special sub stats (hidden by default)
        self.equip_special_stats_frame = tk.Frame(right_frame, bg='#2a2a4e')
        self.equip_special_stats_frame.pack(fill=tk.X)

        # Special stat type dropdown
        row = tk.Frame(self.equip_special_stats_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(row, text="Stat Type:", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                 width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.equip_special_stat_options = {
            "damage_pct": "Damage %",
            "all_skills": "All Skills",
            "final_damage": "Final Damage %"
        }
        self.equip_special_stat_dropdown = ttk.Combobox(
            row, values=list(self.equip_special_stat_options.values()),
            state="readonly", width=15
        )
        self.equip_special_stat_dropdown.pack(side=tk.LEFT, padx=5)
        self.equip_special_stat_dropdown.set("Damage %")
        self.equip_special_stat_dropdown.bind("<<ComboboxSelected>>", self._on_special_stat_type_changed)

        # Special stat value entry
        row = tk.Frame(self.equip_special_stats_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=2)
        self.equip_special_stat_label = tk.Label(row, text="Value:", font=('Segoe UI', 10),
                                                  fg='#ccc', bg='#2a2a4e', width=12, anchor=tk.W)
        self.equip_special_stat_label.pack(side=tk.LEFT)
        self.equip_edit_special_value = tk.Entry(row, width=10, bg='#3a3a5e', fg='white',
                                                  insertbackground='white')
        self.equip_edit_special_value.pack(side=tk.LEFT)
        self.equip_edit_special_value.insert(0, "0")

        # Initially hide special stats
        self.equip_special_stats_frame.pack_forget()

        # Preview section
        self.equip_preview_separator = ttk.Separator(right_frame, orient=tk.HORIZONTAL)
        self.equip_preview_separator.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(right_frame, text="PREVIEW (after SF)", font=('Segoe UI', 11, 'bold'),
                 fg='#7bed9f', bg='#2a2a4e').pack(anchor=tk.W, padx=10)

        self.equip_preview_label = tk.Label(right_frame, text="",
                                            font=('Consolas', 10), fg='#aaa', bg='#2a2a4e',
                                            justify=tk.LEFT)
        self.equip_preview_label.pack(anchor=tk.W, padx=10, pady=5)

        # Buttons
        btn_row = tk.Frame(right_frame, bg='#2a2a4e')
        btn_row.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(btn_row, text="Apply", command=self._apply_equipment_edit,
                  bg='#4a9eff', fg='white', font=('Segoe UI', 10, 'bold'),
                  width=10).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_row, text="Calc Base", command=self._calc_base_from_total,
                  bg='#ff9f43', fg='white', font=('Segoe UI', 10),
                  width=10).pack(side=tk.LEFT, padx=5)

        # Initialize with first slot
        self._on_equip_slot_selected(None)
        self._update_equip_total_stats()

    def _create_equipment_row(self, slot: str):
        """Create a row widget for an equipment slot."""
        row = tk.Frame(self.equip_list_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, pady=1)

        # Make row clickable
        row.bind('<Button-1>', lambda e, s=slot: self._select_equipment_slot(s))

        slot_label = tk.Label(row, text=slot.capitalize(), font=('Segoe UI', 9),
                              fg='#ccc', bg='#2a2a4e', width=10, anchor=tk.W)
        slot_label.pack(side=tk.LEFT, padx=2)
        slot_label.bind('<Button-1>', lambda e, s=slot: self._select_equipment_slot(s))

        name_label = tk.Label(row, text="-", font=('Segoe UI', 9),
                              fg='#888', bg='#2a2a4e', width=15, anchor=tk.W)
        name_label.pack(side=tk.LEFT, padx=2)
        name_label.bind('<Button-1>', lambda e, s=slot: self._select_equipment_slot(s))

        rarity_label = tk.Label(row, text="-", font=('Segoe UI', 9),
                                fg='#888', bg='#2a2a4e', width=6)
        rarity_label.pack(side=tk.LEFT, padx=2)
        rarity_label.bind('<Button-1>', lambda e, s=slot: self._select_equipment_slot(s))

        tier_label = tk.Label(row, text="-", font=('Segoe UI', 9),
                              fg='#888', bg='#2a2a4e', width=5)
        tier_label.pack(side=tk.LEFT, padx=2)
        tier_label.bind('<Button-1>', lambda e, s=slot: self._select_equipment_slot(s))

        stars_label = tk.Label(row, text="★0", font=('Segoe UI', 9),
                               fg='#ffd700', bg='#2a2a4e', width=6)
        stars_label.pack(side=tk.LEFT, padx=2)
        stars_label.bind('<Button-1>', lambda e, s=slot: self._select_equipment_slot(s))

        self.equip_row_widgets[slot] = {
            'row': row,
            'name': name_label,
            'rarity': rarity_label,
            'tier': tier_label,
            'stars': stars_label,
        }

    def _select_equipment_slot(self, slot: str):
        """Select an equipment slot for editing."""
        self.equip_edit_slot.set(slot)
        self._on_equip_slot_selected(None)

    def _on_equip_slot_selected(self, event):
        """Called when a slot is selected in the editor."""
        slot = self.equip_edit_slot.get()
        item = self.equipment_items.get(slot)
        if not item:
            return

        # Update form with item data
        self.equip_edit_name.delete(0, tk.END)
        self.equip_edit_name.insert(0, item.name)

        self.equip_edit_rarity.set(item.rarity)
        self.equip_edit_tier.set(item.tier)
        self.equip_edit_stars.set(item.stars)

        # Base stats
        self.equip_edit_attack.delete(0, tk.END)
        self.equip_edit_attack.insert(0, str(item.base_attack))

        self.equip_edit_hp.delete(0, tk.END)
        self.equip_edit_hp.insert(0, str(item.base_max_hp))

        self.equip_edit_third_stat.delete(0, tk.END)
        self.equip_edit_third_stat.insert(0, str(item.base_third_stat))

        # Update 3rd stat label based on slot
        third_stat_name = item.get_third_stat_name().replace("_", " ").title()
        self.equip_third_stat_label.config(text=f"{third_stat_name}:")

        # Default sub stats
        self.equip_edit_boss_dmg.delete(0, tk.END)
        self.equip_edit_boss_dmg.insert(0, str(item.sub_boss_damage))

        self.equip_edit_normal_dmg.delete(0, tk.END)
        self.equip_edit_normal_dmg.insert(0, str(item.sub_normal_damage))

        self.equip_edit_crit_rate.delete(0, tk.END)
        self.equip_edit_crit_rate.insert(0, str(item.sub_crit_rate))

        self.equip_edit_crit_dmg.delete(0, tk.END)
        self.equip_edit_crit_dmg.insert(0, str(item.sub_crit_damage))

        self.equip_edit_attack_flat.delete(0, tk.END)
        self.equip_edit_attack_flat.insert(0, str(item.sub_attack_flat))

        # Default sub stats - Job skills (available on all items)
        self.equip_edit_skill_1st.delete(0, tk.END)
        self.equip_edit_skill_1st.insert(0, str(item.sub_skill_first_job))

        self.equip_edit_skill_2nd.delete(0, tk.END)
        self.equip_edit_skill_2nd.insert(0, str(item.sub_skill_second_job))

        self.equip_edit_skill_3rd.delete(0, tk.END)
        self.equip_edit_skill_3rd.insert(0, str(item.sub_skill_third_job))

        self.equip_edit_skill_4th.delete(0, tk.END)
        self.equip_edit_skill_4th.insert(0, str(item.sub_skill_fourth_job))

        # Special checkbox and stat
        self.equip_edit_is_special.set(item.is_special)

        # Set dropdown to the correct special stat type
        display_name = self.equip_special_stat_options.get(item.special_stat_type, "Damage %")
        self.equip_special_stat_dropdown.set(display_name)

        # Set special stat value
        self.equip_edit_special_value.delete(0, tk.END)
        self.equip_edit_special_value.insert(0, str(item.special_stat_value))

        # Show/hide special sub stats based on is_special
        self._update_special_stats_visibility()

        self._update_equip_preview(None)

    def _update_equip_preview(self, value):
        """Update the preview showing stats after starforce."""
        try:
            stars = int(self.equip_edit_stars.get())
            slot = self.equip_edit_slot.get()
            is_special = self.equip_edit_is_special.get()

            # Main stats
            base_atk = float(self.equip_edit_attack.get() or 0)
            base_hp = float(self.equip_edit_hp.get() or 0)
            base_third = float(self.equip_edit_third_stat.get() or 0)

            # Default sub stats
            boss_dmg = float(self.equip_edit_boss_dmg.get() or 0)
            normal_dmg = float(self.equip_edit_normal_dmg.get() or 0)
            crit_rate = float(self.equip_edit_crit_rate.get() or 0)
            crit_dmg = float(self.equip_edit_crit_dmg.get() or 0)
            atk_flat = float(self.equip_edit_attack_flat.get() or 0)
            skill_1st = int(self.equip_edit_skill_1st.get() or 0)
            skill_2nd = int(self.equip_edit_skill_2nd.get() or 0)
            skill_3rd = int(self.equip_edit_skill_3rd.get() or 0)
            skill_4th = int(self.equip_edit_skill_4th.get() or 0)

            # Special stat
            special_value = float(self.equip_edit_special_value.get() or 0)

            main_mult = get_amplify_multiplier(stars, is_sub=False)
            sub_mult = get_amplify_multiplier(stars, is_sub=True)

            # Get third stat label
            third_stat_name = SLOT_THIRD_MAIN_STAT.get(slot, "main_stat").replace("_", " ").title()

            preview_text = f"★{stars} ({main_mult:.2f}x Main / {sub_mult:.2f}x Sub)\n"
            preview_text += f"───────────────────\n"
            preview_text += f"Attack: {base_atk * main_mult:,.0f}\n"
            preview_text += f"Max HP: {base_hp * main_mult:,.0f}\n"
            preview_text += f"{third_stat_name}: {base_third * main_mult:,.0f}\n"

            # Default sub stats
            if boss_dmg > 0:
                preview_text += f"Boss Dmg: {boss_dmg * sub_mult:.1f}%\n"
            if normal_dmg > 0:
                preview_text += f"Normal Dmg: {normal_dmg * sub_mult:.1f}%\n"
            if crit_rate > 0:
                preview_text += f"Crit Rate: {crit_rate * sub_mult:.1f}%\n"
            if crit_dmg > 0:
                preview_text += f"Crit Dmg: {crit_dmg * sub_mult:.1f}%\n"
            if atk_flat > 0:
                preview_text += f"Attack (flat): {atk_flat * sub_mult:.0f}\n"
            if skill_1st > 0:
                preview_text += f"1st Job: +{int(skill_1st * sub_mult)}\n"
            if skill_2nd > 0:
                preview_text += f"2nd Job: +{int(skill_2nd * sub_mult)}\n"
            if skill_3rd > 0:
                preview_text += f"3rd Job: +{int(skill_3rd * sub_mult)}\n"
            if skill_4th > 0:
                preview_text += f"4th Job: +{int(skill_4th * sub_mult)}\n"

            # Special stat (only if special item and has value)
            if is_special and special_value > 0:
                special_type = self._get_special_stat_type_key()
                if special_type == "damage_pct":
                    preview_text += f"Damage %: {special_value * sub_mult:.1f}%\n"
                elif special_type == "all_skills":
                    preview_text += f"All Skills: +{int(special_value * sub_mult)}\n"
                elif special_type == "final_damage":
                    preview_text += f"Final Dmg: {special_value * sub_mult:.1f}%\n"

            self.equip_preview_label.config(text=preview_text)
        except ValueError:
            pass

    def _get_special_stat_type_key(self) -> str:
        """Get the internal key for the selected special stat type."""
        display_value = self.equip_special_stat_dropdown.get()
        for key, display in self.equip_special_stat_options.items():
            if display == display_value:
                return key
        return "damage_pct"

    def _on_special_stat_type_changed(self, event):
        """Handle special stat type dropdown change."""
        self._update_equip_preview(None)

    def _update_special_stats_visibility(self):
        """Show/hide special stats based on is_special checkbox."""
        if self.equip_edit_is_special.get():
            # Pack before the preview separator to maintain correct position
            self.equip_special_stats_frame.pack(fill=tk.X, before=self.equip_preview_separator)
        else:
            self.equip_special_stats_frame.pack_forget()

    def _apply_equipment_edit(self):
        """Apply the current editor values to the equipment item."""
        slot = self.equip_edit_slot.get()
        item = self.equipment_items.get(slot)
        if not item:
            return

        try:
            item.name = self.equip_edit_name.get()
            item.rarity = self.equip_edit_rarity.get()
            item.tier = self.equip_edit_tier.get()
            item.stars = int(self.equip_edit_stars.get())
            item.is_special = self.equip_edit_is_special.get()

            # Main stats
            item.base_attack = float(self.equip_edit_attack.get() or 0)
            item.base_max_hp = float(self.equip_edit_hp.get() or 0)
            item.base_third_stat = float(self.equip_edit_third_stat.get() or 0)

            # Default sub stats
            item.sub_boss_damage = float(self.equip_edit_boss_dmg.get() or 0)
            item.sub_normal_damage = float(self.equip_edit_normal_dmg.get() or 0)
            item.sub_crit_rate = float(self.equip_edit_crit_rate.get() or 0)
            item.sub_crit_damage = float(self.equip_edit_crit_dmg.get() or 0)
            item.sub_attack_flat = float(self.equip_edit_attack_flat.get() or 0)
            item.sub_skill_first_job = int(self.equip_edit_skill_1st.get() or 0)
            item.sub_skill_second_job = int(self.equip_edit_skill_2nd.get() or 0)
            item.sub_skill_third_job = int(self.equip_edit_skill_3rd.get() or 0)
            item.sub_skill_fourth_job = int(self.equip_edit_skill_4th.get() or 0)

            # Special stat (only on special items)
            item.special_stat_type = self._get_special_stat_type_key()
            item.special_stat_value = float(self.equip_edit_special_value.get() or 0)

            self._update_equipment_row(slot)
            self._update_equip_total_stats()

            # Auto-save equipment to CSV
            self.save_equipment_to_csv(silent=True)

            # Auto-update skill bonuses from equipment
            self.auto_update_skill_bonuses()

            # Show confirmation
            self._flash_apply_confirmation(slot)

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")

    def _flash_apply_confirmation(self, slot: str):
        """Briefly flash a confirmation that changes were applied."""
        # Update the preview label to show confirmation
        original_text = self.equip_preview_label.cget('text')
        original_fg = self.equip_preview_label.cget('fg')
        self.equip_preview_label.config(text=f"✓ {slot.upper()} SAVED!", fg='#00ff88')

        # Reset after 1.5 seconds
        def reset_label():
            self._update_equip_preview(None)
        self.root.after(1500, reset_label)

    def _calc_base_from_total(self):
        """Calculate base stats from displayed total (reverse SF calculation)."""
        try:
            stars = int(self.equip_edit_stars.get())

            # Ask user for the total values they see in-game
            dialog = tk.Toplevel(self.root)
            dialog.title("Calculate Base Stats")
            dialog.configure(bg='#1a1a2e')
            dialog.geometry("300x250")
            dialog.transient(self.root)
            dialog.grab_set()

            tk.Label(dialog, text="Enter DISPLAYED stats from game:",
                     font=('Segoe UI', 11, 'bold'), fg='#ffd700', bg='#1a1a2e').pack(pady=10)

            entries = {}
            for label_text in ["Total Attack", "Total HP", "Total Main Stat", "Total Damage %"]:
                row = tk.Frame(dialog, bg='#1a1a2e')
                row.pack(fill=tk.X, padx=20, pady=3)
                tk.Label(row, text=f"{label_text}:", font=('Segoe UI', 10),
                         fg='#ccc', bg='#1a1a2e', width=15, anchor=tk.W).pack(side=tk.LEFT)
                entry = tk.Entry(row, width=12, bg='#3a3a5e', fg='white')
                entry.pack(side=tk.LEFT)
                entry.insert(0, "0")
                entries[label_text] = entry

            def calculate():
                main_mult = get_amplify_multiplier(stars, is_sub=False)
                sub_mult = get_amplify_multiplier(stars, is_sub=True)

                total_atk = float(entries["Total Attack"].get() or 0)
                total_hp = float(entries["Total HP"].get() or 0)
                total_main = float(entries["Total Main Stat"].get() or 0)
                total_dmg = float(entries["Total Damage %"].get() or 0)

                self.equip_edit_attack.delete(0, tk.END)
                self.equip_edit_attack.insert(0, f"{total_atk / main_mult:.1f}")

                self.equip_edit_hp.delete(0, tk.END)
                self.equip_edit_hp.insert(0, f"{total_hp / main_mult:.1f}")

                self.equip_edit_mainstat.delete(0, tk.END)
                self.equip_edit_mainstat.insert(0, f"{total_main / main_mult:.1f}")

                self.equip_edit_dmg_pct.delete(0, tk.END)
                self.equip_edit_dmg_pct.insert(0, f"{total_dmg / sub_mult:.1f}")

                self._update_equip_preview(None)
                dialog.destroy()

            tk.Button(dialog, text="Calculate Base", command=calculate,
                      bg='#4a9eff', fg='white', font=('Segoe UI', 10, 'bold')).pack(pady=15)

        except ValueError:
            pass

    def _update_equipment_row(self, slot: str):
        """Update the display for a single equipment row."""
        item = self.equipment_items.get(slot)
        widgets = self.equip_row_widgets.get(slot)
        if not item or not widgets:
            return

        # Rarity colors
        rarity_colors = {
            "epic": "#b388ff",
            "unique": "#ffd700",
            "legendary": "#7bed9f",
            "mystic": "#ff6b6b"
        }

        widgets['name'].config(text=item.name if item.name else "-",
                               fg='#ccc' if item.name else '#888')

        rarity_short = {"epic": "E", "unique": "U", "legendary": "L", "mystic": "M"}
        widgets['rarity'].config(text=rarity_short.get(item.rarity, "-"),
                                 fg=rarity_colors.get(item.rarity, '#888'))

        widgets['tier'].config(text=f"T{item.tier}")
        widgets['stars'].config(text=f"★{item.stars}")

    def _update_equip_total_stats(self):
        """Update the total stats display."""
        totals = self.get_equipment_stats_total()

        text = f"Attack: {totals['total_attack']:,.0f}\n"
        text += f"Max HP: {totals['total_hp']:,.0f}\n"
        text += f"Main Stat: {totals['total_main_stat']:,.0f}\n"
        text += f"Damage %: {totals['total_damage_pct']:.1f}%\n"
        text += f"Boss Dmg %: {totals['total_boss_damage']:.1f}%\n"
        text += f"Crit Rate %: {totals['total_crit_rate']:.1f}%\n"
        text += f"Crit Dmg %: {totals['total_crit_damage']:.1f}%"

        self.equip_total_stats.config(text=text)

    def get_equipment_stats_total(self) -> Dict[str, float]:
        """Get total stats from all equipment after starforce."""
        totals = {
            "total_attack": 0.0,
            "total_hp": 0.0,
            "total_main_stat": 0.0,
            "total_damage_pct": 0.0,
            "total_boss_damage": 0.0,
            "total_crit_rate": 0.0,
            "total_crit_damage": 0.0,
        }

        for slot, item in self.equipment_items.items():
            totals["total_attack"] += item.get_final_attack()
            totals["total_hp"] += item.get_final_hp()
            totals["total_main_stat"] += item.get_final_main_stat()
            totals["total_damage_pct"] += item.get_final_damage_pct()
            totals["total_boss_damage"] += item.get_final_boss_damage()
            totals["total_crit_rate"] += item.get_final_crit_rate()
            totals["total_crit_damage"] += item.get_final_crit_damage()

        return totals

    # =========================================================================
    # STARFORCE TAB
    # =========================================================================

    def build_starforce_tab(self):
        """Build the Starforce calculator and simulator tab."""
        # Create scrollable frame
        canvas = tk.Canvas(self.starforce_tab, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.starforce_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling when mouse is over this tab
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        # Main container with two columns
        main_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEFT COLUMN - Calculator and Simulator
        left_frame = tk.Frame(main_frame, bg='#1a1a2e')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Cost Calculator section
        calc_frame = tk.Frame(left_frame, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        calc_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(calc_frame, text="STARFORCE CALCULATOR", font=('Segoe UI', 14, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(anchor=tk.W, padx=10, pady=10)

        # Current stars
        row = tk.Frame(calc_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="Current Stars:", font=('Segoe UI', 10), fg='#ccc',
                 bg='#2a2a4e', width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.sf_current_stars = ttk.Combobox(row, values=list(range(0, 25)), width=8)
        self.sf_current_stars.pack(side=tk.LEFT)
        self.sf_current_stars.set("10")

        # Target stars
        row = tk.Frame(calc_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="Target Stars:", font=('Segoe UI', 10), fg='#ccc',
                 bg='#2a2a4e', width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.sf_target_stars = ttk.Combobox(row, values=list(range(1, 26)), width=8)
        self.sf_target_stars.pack(side=tk.LEFT)
        self.sf_target_stars.set("16")

        # Info label
        row = tk.Frame(calc_frame, bg='#2a2a4e')
        row.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(row, text="(Uses optimal per-stage protection strategy)",
                 font=('Segoe UI', 9, 'italic'), fg='#888', bg='#2a2a4e').pack(side=tk.LEFT)

        # Buttons
        btn_row = tk.Frame(calc_frame, bg='#2a2a4e')
        btn_row.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(btn_row, text="Calculate", command=self._calculate_sf_cost,
                  bg='#4a9eff', fg='white', font=('Segoe UI', 10, 'bold'),
                  width=12).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_row, text="Simulate (1000x)", command=self._run_sf_simulation,
                  bg='#ff9f43', fg='white', font=('Segoe UI', 10, 'bold'),
                  width=15).pack(side=tk.LEFT, padx=5)

        # Expected costs display
        ttk.Separator(calc_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=5)

        tk.Label(calc_frame, text="EXPECTED COSTS", font=('Segoe UI', 11, 'bold'),
                 fg='#7bed9f', bg='#2a2a4e').pack(anchor=tk.W, padx=10)

        self.sf_expected_label = tk.Label(calc_frame, text="Select stars and click Calculate",
                                          font=('Consolas', 10), fg='#aaa', bg='#2a2a4e',
                                          justify=tk.LEFT, anchor=tk.NW, wraplength=500)
        self.sf_expected_label.pack(anchor=tk.W, padx=10, pady=10, fill=tk.X)

        # Optimal Strategy section
        optimal_frame = tk.Frame(left_frame, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        optimal_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(optimal_frame, text="OPTIMAL STRATEGY (Markov Analysis)", font=('Segoe UI', 14, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(anchor=tk.W, padx=10, pady=10)

        tk.Label(optimal_frame, text="Properly accounts for decrease chains and cumulative destruction probability",
                 font=('Segoe UI', 9, 'italic'), fg='#888', bg='#2a2a4e').pack(anchor=tk.W, padx=10)

        self.sf_optimal_label = tk.Label(optimal_frame, text="Click 'Calculate' to see optimal strategy",
                                         font=('Consolas', 10), fg='#aaa', bg='#2a2a4e',
                                         justify=tk.LEFT, anchor=tk.NW, wraplength=500)
        self.sf_optimal_label.pack(anchor=tk.W, padx=10, pady=10, fill=tk.X)

        # Simulation results section
        sim_frame = tk.Frame(left_frame, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        sim_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(sim_frame, text="SIMULATION RESULTS", font=('Segoe UI', 14, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(anchor=tk.W, padx=10, pady=10)

        self.sf_sim_label = tk.Label(sim_frame, text="Click 'Simulate (1000x)' to run Monte Carlo simulation",
                                     font=('Consolas', 10), fg='#aaa', bg='#2a2a4e',
                                     justify=tk.LEFT, anchor=tk.NW, wraplength=500)
        self.sf_sim_label.pack(anchor=tk.W, padx=10, pady=10, fill=tk.X)

        # RIGHT COLUMN - Reference Tables
        right_frame = tk.Frame(main_frame, bg='#1a1a2e')
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # Starforce table
        sf_table_frame = tk.Frame(right_frame, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        sf_table_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(sf_table_frame, text="STARFORCE TABLE", font=('Segoe UI', 12, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(anchor=tk.W, padx=10, pady=5)

        # Headers
        header_row = tk.Frame(sf_table_frame, bg='#3a3a5e')
        header_row.pack(fill=tk.X, padx=5)
        for text in ["★", "Succ", "Dec", "Dest", "Meso"]:
            tk.Label(header_row, text=text, font=('Consolas', 9, 'bold'),
                     fg='#ccc', bg='#3a3a5e', width=7).pack(side=tk.LEFT)

        # Table rows (show 15-25 - the destruction zone)
        for stage in range(15, 25):
            if stage not in STARFORCE_TABLE:
                continue
            data = STARFORCE_TABLE[stage]

            row = tk.Frame(sf_table_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=5)

            # Star
            tk.Label(row, text=f"★{stage}", font=('Consolas', 9),
                     fg='#ffd700', bg='#2a2a4e', width=7).pack(side=tk.LEFT)
            # Success
            tk.Label(row, text=f"{data.success_rate*100:.1f}%", font=('Consolas', 9),
                     fg='#7bed9f', bg='#2a2a4e', width=7).pack(side=tk.LEFT)
            # Decrease
            dec_color = '#ff6b6b' if data.decrease_rate > 0 else '#888'
            tk.Label(row, text=f"{data.decrease_rate*100:.0f}%", font=('Consolas', 9),
                     fg=dec_color, bg='#2a2a4e', width=7).pack(side=tk.LEFT)
            # Destroy
            dest_color = '#ff4757' if data.destroy_rate > 0 else '#888'
            tk.Label(row, text=f"{data.destroy_rate*100:.1f}%", font=('Consolas', 9),
                     fg=dest_color, bg='#2a2a4e', width=7).pack(side=tk.LEFT)
            # Meso
            tk.Label(row, text=f"{data.meso//1000}k", font=('Consolas', 9),
                     fg='#ccc', bg='#2a2a4e', width=7).pack(side=tk.LEFT)

        # Amplification table
        amp_table_frame = tk.Frame(right_frame, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        amp_table_frame.pack(fill=tk.X)

        tk.Label(amp_table_frame, text="AMPLIFICATION TABLE", font=('Segoe UI', 12, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(anchor=tk.W, padx=10, pady=5)

        # Headers
        header_row = tk.Frame(amp_table_frame, bg='#3a3a5e')
        header_row.pack(fill=tk.X, padx=5)
        for text in ["Stars", "Main", "Sub"]:
            tk.Label(header_row, text=text, font=('Consolas', 9, 'bold'),
                     fg='#ccc', bg='#3a3a5e', width=10).pack(side=tk.LEFT)

        # Key milestones
        for stars in [0, 5, 10, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]:
            main_mult = get_amplify_multiplier(stars, is_sub=False)
            sub_mult = get_amplify_multiplier(stars, is_sub=True)

            row = tk.Frame(amp_table_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=5)

            tk.Label(row, text=f"★{stars}", font=('Consolas', 9),
                     fg='#ffd700', bg='#2a2a4e', width=10).pack(side=tk.LEFT)
            tk.Label(row, text=f"{main_mult:.1f}x", font=('Consolas', 9),
                     fg='#4a9eff', bg='#2a2a4e', width=10).pack(side=tk.LEFT)
            tk.Label(row, text=f"{sub_mult:.2f}x", font=('Consolas', 9),
                     fg='#ff9f43', bg='#2a2a4e', width=10).pack(side=tk.LEFT)

    def _calculate_sf_cost(self):
        """Calculate expected starforce costs using optimal strategy."""
        try:
            current = int(self.sf_current_stars.get())
            target = int(self.sf_target_stars.get())

            if target <= current:
                self.sf_expected_label.config(text="Target must be higher than current stars!")
                self.sf_optimal_label.config(text="Target must be higher than current stars!")
                return

            # Use optimal per-stage strategy for cost calculation
            stage_names, result = find_optimal_per_stage_strategy(current, target)

            # Back-calculate meso and scrolls from diamond cost
            # Account for per-stage protection costs
            total_meso_weight = 0
            total_scroll_weight = 0
            for stage in range(current, target):
                data = STARFORCE_TABLE.get(stage)
                if data:
                    strat = stage_names.get(stage, 'none')
                    cost_mult = 1.0
                    if strat in ('decrease', 'both') and data.decrease_rate > 0:
                        cost_mult += 1.0
                    if strat in ('destroy', 'both') and data.destroy_rate > 0:
                        cost_mult += 1.0
                    total_meso_weight += data.meso * cost_mult
                    total_scroll_weight += data.stones * cost_mult

            # Estimate meso and scrolls proportionally
            if total_meso_weight + total_scroll_weight > 0:
                meso_diamonds = total_meso_weight * MESO_TO_DIAMOND
                scroll_diamonds = total_scroll_weight * SCROLL_DIAMOND_COST
                meso_ratio = meso_diamonds / (meso_diamonds + scroll_diamonds)
                scroll_ratio = scroll_diamonds / (meso_diamonds + scroll_diamonds)

                total_meso = int((result.total_cost * meso_ratio) / MESO_TO_DIAMOND)
                total_scrolls = int((result.total_cost * scroll_ratio) / SCROLL_DIAMOND_COST)
            else:
                total_meso = 0
                total_scrolls = 0

            text = f"★{current} → ★{target} (Optimal)\n"
            text += f"───────────────────\n"
            text += f"Expected Meso: {total_meso:,}\n"
            text += f"Expected Scrolls: {total_scrolls:,}\n"
            text += f"P(Destroy): {result.destroy_probability * 100:.1f}%\n"
            text += f"Total Diamonds: {result.total_cost:,.0f}\n"

            self.sf_expected_label.config(text=text)

            # Update optimal strategy display
            self._update_optimal_strategy(current, target, stage_names, result)

        except ValueError:
            self.sf_expected_label.config(text="Invalid input!")
            self.sf_optimal_label.config(text="Invalid input!")

    def _update_optimal_strategy(self, current: int, target: int, stage_names: dict = None, per_stage_result = None):
        """Calculate and display the optimal protection strategy."""
        try:
            # Use provided values or calculate if not provided
            if stage_names is None or per_stage_result is None:
                stage_names, per_stage_result = find_optimal_per_stage_strategy(current, target)

            # Also get uniform strategies for comparison
            best_uniform, best_uniform_result, all_results = find_optimal_strategy(current, target)

            # Format strategy names
            strat_names_full = {
                'none': 'No Protection',
                'decrease': 'Decrease Only',
                'destroy': 'Destroy Only',
                'both': 'Both Protections'
            }

            # Group consecutive stages with same strategy
            zones = []
            zone_start = current
            zone_strat = stage_names.get(current, 'none')

            for stage in range(current, target):
                strat = stage_names.get(stage, 'none')
                if strat != zone_strat:
                    zones.append((zone_start, stage, zone_strat))
                    zone_start = stage
                    zone_strat = strat
            zones.append((zone_start, target, zone_strat))

            # Build compact strategy display
            text = "PROTECTION BY STAGE:\n"
            for start, end, strat in zones:
                text += f"  ★{start}→{end}: {strat_names_full[strat]}\n"

            text += f"\n{'─' * 35}\n"
            text += f"COST: {per_stage_result.total_cost:,.0f} diamonds\n"
            text += f"P(Destroy): {per_stage_result.destroy_probability * 100:.1f}%\n"

            # Show savings vs no protection
            none_cost = all_results['none'].total_cost
            if none_cost > per_stage_result.total_cost:
                total_savings = none_cost - per_stage_result.total_cost
                total_pct = total_savings / none_cost * 100
                text += f"\nSaves {total_savings:,.0f} ({total_pct:.1f}%)\n"
                text += f"vs no protection"

            self.sf_optimal_label.config(text=text)

        except Exception as e:
            import traceback
            self.sf_optimal_label.config(text=f"Error: {e}\n{traceback.format_exc()}")

    def _run_sf_simulation(self):
        """Run Monte Carlo simulation for starforce using optimal strategy."""
        try:
            current = int(self.sf_current_stars.get())
            target = int(self.sf_target_stars.get())

            if target <= current:
                self.sf_sim_label.config(text="Target must be higher than current stars!")
                return

            # Get optimal strategies for simulation
            stage_names, _ = find_optimal_per_stage_strategy(current, target)

            iterations = 1000
            results = []

            for _ in range(iterations):
                result = self._simulate_single_path_optimal(current, target, stage_names)
                results.append(result)

            # Calculate statistics
            mesos = [r['meso'] for r in results]
            stones = [r['stones'] for r in results]
            attempts = [r['attempts'] for r in results]
            destructions = [r['destructions'] for r in results]

            avg_meso = sum(mesos) / len(mesos)
            med_meso = sorted(mesos)[len(mesos) // 2]
            min_meso = min(mesos)
            max_meso = max(mesos)
            p95_meso = sorted(mesos)[int(len(mesos) * 0.95)]

            avg_dest = sum(destructions) / len(destructions)
            success_rate = sum(1 for r in results if r['success']) / len(results) * 100

            text = f"SIMULATION: ★{current} → ★{target} ({iterations} runs)\n"
            text += f"{'═' * 40}\n\n"
            text += f"MESO COSTS:\n"
            text += f"  Average: {avg_meso:,.0f}\n"
            text += f"  Median: {med_meso:,.0f}\n"
            text += f"  Min: {min_meso:,.0f}\n"
            text += f"  Max: {max_meso:,.0f}\n"
            text += f"  95th %ile: {p95_meso:,.0f}\n\n"
            text += f"STONES:\n"
            text += f"  Average: {sum(stones)/len(stones):.0f}\n\n"
            text += f"ATTEMPTS:\n"
            text += f"  Average: {sum(attempts)/len(attempts):.1f}\n\n"
            text += f"DESTRUCTIONS:\n"
            text += f"  Average: {avg_dest:.2f}\n"
            text += f"  Total across all runs: {sum(destructions)}\n\n"
            text += f"SUCCESS RATE: {success_rate:.1f}%"

            self.sf_sim_label.config(text=text)

        except ValueError:
            self.sf_sim_label.config(text="Invalid input!")

    def _simulate_single_path_optimal(self, start: int, target: int, stage_strategies: dict) -> dict:
        """Simulate one enhancement path using optimal per-stage strategies."""
        stars = start
        meso = 0
        stones = 0
        attempts = 0
        destructions = 0

        # Safety limit to prevent infinite loops
        max_attempts = 10000

        while stars < target and attempts < max_attempts:
            if stars not in STARFORCE_TABLE:
                break

            stage = STARFORCE_TABLE[stars]

            # Get strategy for current stage
            strat = stage_strategies.get(stars, 'none')
            protect_dec = strat in ('decrease', 'both')
            protect_dest = strat in ('destroy', 'both')

            # Calculate cost with protections
            cost_mult = 1.0
            if protect_dec and stage.decrease_rate > 0:
                cost_mult += 1.0
            if protect_dest and stage.destroy_rate > 0:
                cost_mult += 1.0

            meso += int(stage.meso * cost_mult)
            stones += int(stage.stones * cost_mult)
            attempts += 1

            # Adjust probabilities based on protection
            success_rate = stage.success_rate
            maintain_rate = stage.maintain_rate
            decrease_rate = 0 if protect_dec else stage.decrease_rate
            destroy_rate = stage.destroy_rate * (0.5 if protect_dest else 1.0)

            # Maintain rate absorbs the protected decrease
            if protect_dec and stage.decrease_rate > 0:
                maintain_rate += stage.decrease_rate

            roll = random.random()

            if roll < success_rate:
                # Success - gain a star
                stars += 1
            elif roll < success_rate + maintain_rate:
                # Maintain - no change
                pass
            elif roll < success_rate + maintain_rate + decrease_rate:
                # Decrease
                stars = max(start, stars - 1)
            else:
                # Destruction
                destructions += 1
                meso += 1_000_000  # Destruction fee
                stars = 12  # Reset to 12 on destruction

        return {
            "meso": meso,
            "stones": stones,
            "attempts": attempts,
            "destructions": destructions,
            "success": stars >= target
        }

    # =========================================================================
    # EQUIPMENT SAVE/LOAD
    # =========================================================================

    def save_equipment_to_csv(self, filepath: str = None, silent: bool = False):
        """Save equipment data to CSV file."""
        if filepath is None and not silent:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="equipment_save.csv"
            )
            if not filepath:
                return
        elif filepath is None:
            filepath = EQUIPMENT_SAVE_FILE

        try:
            # Use fieldnames that match EquipmentItem.to_dict()
            fieldnames = [
                "slot", "name", "rarity", "tier", "stars", "is_special",
                "base_attack", "base_hp", "base_third",
                "boss_dmg", "normal_dmg", "crit_rate", "crit_dmg", "attack_flat",
                "skill_1st", "skill_2nd", "skill_3rd", "skill_4th",
                "special_stat_type", "special_stat_value"
            ]
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for slot, item in self.equipment_items.items():
                    writer.writerow(item.to_dict())

            if not silent:
                messagebox.showinfo("Success", f"Equipment saved to {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def load_equipment_from_csv(self, filepath: str = None, silent: bool = False):
        """Load equipment data from CSV file."""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv")],
                initialfile="equipment_save.csv"
            )
            if not filepath:
                return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    slot = row.get("slot", "")
                    if slot in self.equipment_items:
                        self.equipment_items[slot] = EquipmentItem.from_dict(row)
                        self._update_equipment_row(slot)

            self._update_equip_total_stats()

            # Auto-update skill bonuses from equipment
            self.auto_update_skill_bonuses()

            if not silent:
                messagebox.showinfo("Success", f"Equipment loaded from {filepath}")

        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load: {e}")

    def auto_load_equipment(self):
        """Automatically load equipment from default save file on startup."""
        if os.path.exists(EQUIPMENT_SAVE_FILE):
            self.load_equipment_from_csv(EQUIPMENT_SAVE_FILE, silent=True)

    # =========================================================================
    # HERO POWER TAB
    # =========================================================================

    def build_hero_power_tab(self):
        """Build the Hero Power calculator tab."""
        # Create scrollable frame
        canvas = tk.Canvas(self.hero_power_tab, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.hero_power_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling when mouse is over this tab
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        main_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Two-column layout
        cols = tk.Frame(main_frame, bg='#1a1a2e')
        cols.pack(fill=tk.BOTH, expand=True, pady=10)

        left_col = tk.Frame(cols, bg='#1a1a2e')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_col = tk.Frame(cols, bg='#1a1a2e')
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # =====================================================================
        # LEFT COLUMN - Hero Power Preset Tabs (1-10)
        # =====================================================================

        self._section_header(left_col, "Hero Power Presets (Tabs 1-10)")

        # Create inner notebook for preset tabs
        self.hero_power_preset_notebook = ttk.Notebook(left_col)
        self.hero_power_preset_notebook.pack(fill=tk.X, pady=5)

        # Store per-tab widget references
        self.hero_power_tab_widgets: Dict[int, Dict] = {}  # tab_idx -> {slot -> widgets}
        self.hero_power_tab_frames: Dict[int, tk.Frame] = {}

        # Create 10 preset tabs
        for tab_idx in range(1, 11):
            tab_frame = tk.Frame(self.hero_power_preset_notebook, bg='#2a2a4e')
            self.hero_power_tab_frames[tab_idx] = tab_frame

            # Add tab to notebook
            tab_name = f"Tab {tab_idx}" if tab_idx > 1 else "Default"
            self.hero_power_preset_notebook.add(tab_frame, text=f" {tab_idx} ")

            # Initialize widget storage for this tab
            self.hero_power_tab_widgets[tab_idx] = {}

            # Build 6 line editors for this tab
            for slot in range(1, 7):
                self._build_hero_power_line_editor_for_tab(tab_frame, tab_idx, slot)

        # Bind tab change event to sync with presets
        self.hero_power_preset_notebook.bind("<<NotebookTabChanged>>", self._on_hero_power_tab_changed)

        # Track current tab
        self.hero_power_current_tab = 1

        # Medal cost display
        self._section_header(left_col, "Reroll Cost")

        cost_frame = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        cost_frame.pack(fill=tk.X, pady=5)

        self.hero_power_locked_label = tk.Label(
            cost_frame, text="Locked Lines: 0",
            font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e'
        )
        self.hero_power_locked_label.pack(anchor=tk.W, padx=10, pady=5)

        self.hero_power_cost_label = tk.Label(
            cost_frame, text="Cost per Reroll: 86 medals",
            font=('Segoe UI', 12, 'bold'), fg='#ffd700', bg='#2a2a4e'
        )
        self.hero_power_cost_label.pack(anchor=tk.W, padx=10, pady=5)

        # Cost table reference
        cost_ref = tk.Label(
            cost_frame,
            text="0 locked: 86 | 1: 129 | 2: 172 | 3: 215 | 4: 258",
            font=('Consolas', 9), fg='#888', bg='#2a2a4e'
        )
        cost_ref.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Stat contribution summary
        self._section_header(left_col, "Stat Contribution")

        stats_frame = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        stats_frame.pack(fill=tk.X, pady=5)

        self.hero_power_stats_label = tk.Label(
            stats_frame, text="No stats configured",
            font=('Consolas', 10), fg='#ccc', bg='#2a2a4e',
            justify=tk.LEFT, anchor=tk.NW
        )
        self.hero_power_stats_label.pack(anchor=tk.W, padx=10, pady=10)

        self.hero_power_dps_label = tk.Label(
            stats_frame, text="DPS Impact: ---",
            font=('Segoe UI', 11, 'bold'), fg='#00ff88', bg='#2a2a4e'
        )
        self.hero_power_dps_label.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # =====================================================================
        # Passive Stats Section (Stage 6 levelable stats)
        # =====================================================================
        self._section_header(left_col, "Passive Stats (Stage 6)")

        passive_frame = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        passive_frame.pack(fill=tk.X, pady=5)

        passive_info = tk.Label(
            passive_frame,
            text="Leveled stats (not rerolled) - set your current levels:",
            font=('Segoe UI', 9), fg='#888', bg='#2a2a4e'
        )
        passive_info.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Build passive stat level inputs
        self._build_hero_power_passive_section(passive_frame)

        # Passive stats summary
        self.hero_power_passive_summary_label = tk.Label(
            passive_frame,
            text="Passive Stats: +0 Main Stat, +0% Damage, +0 Attack",
            font=('Segoe UI', 10), fg='#00ff88', bg='#2a2a4e'
        )
        self.hero_power_passive_summary_label.pack(anchor=tk.W, padx=10, pady=(5, 10))

        # Export/Import section (for all presets)
        self._section_header(left_col, "Import/Export All Presets")

        export_frame = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        export_frame.pack(fill=tk.X, pady=5)

        csv_row = tk.Frame(export_frame, bg='#2a2a4e')
        csv_row.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(csv_row, text="Export All to CSV", command=self.export_hero_power_csv,
                  bg='#4a4a6a', fg='white', font=('Segoe UI', 9),
                  width=15).pack(side=tk.LEFT, padx=2)

        tk.Button(csv_row, text="Import from CSV", command=self.import_hero_power_csv,
                  bg='#4a4a6a', fg='white', font=('Segoe UI', 9),
                  width=15).pack(side=tk.LEFT, padx=2)

        # Keep preset_var for compatibility (set to current tab name)
        self.hero_power_preset_var = tk.StringVar(value="Tab 1")

        # =====================================================================
        # RIGHT COLUMN - Level Config & Simulation Settings
        # =====================================================================

        # Hero Power Level Configuration
        self._section_header(right_col, "Hero Power Level")

        level_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        level_frame.pack(fill=tk.X, pady=5)

        level_info = tk.Label(
            level_frame,
            text="Set your Hero Power level to adjust tier probabilities and costs:",
            font=('Segoe UI', 9), fg='#888', bg='#2a2a4e'
        )
        level_info.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Level selector row
        level_row = tk.Frame(level_frame, bg='#2a2a4e')
        level_row.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(level_row, text="Level:", font=('Segoe UI', 10, 'bold'),
                 fg='#ffd700', bg='#2a2a4e').pack(side=tk.LEFT)

        self.hero_power_level_widgets['level'] = tk.StringVar(value="15")
        level_dropdown = ttk.Combobox(
            level_row, textvariable=self.hero_power_level_widgets['level'],
            values=[str(i) for i in range(1, 21)], width=5
        )
        level_dropdown.pack(side=tk.LEFT, padx=5)

        tk.Label(level_row, text="Base Cost:", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT, padx=(15, 5))

        self.hero_power_level_widgets['base_cost'] = tk.StringVar(value="89")
        base_cost_entry = tk.Entry(
            level_row, textvariable=self.hero_power_level_widgets['base_cost'],
            width=5, font=('Consolas', 10), bg='#3a3a5a', fg='#eee', insertbackground='white'
        )
        base_cost_entry.pack(side=tk.LEFT)
        tk.Label(level_row, text="medals", font=('Segoe UI', 9),
                 fg='#888', bg='#2a2a4e').pack(side=tk.LEFT, padx=2)

        # Tier probabilities grid
        probs_label = tk.Label(
            level_frame, text="Tier Probabilities (%):",
            font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e'
        )
        probs_label.pack(anchor=tk.W, padx=10, pady=(10, 2))

        probs_grid = tk.Frame(level_frame, bg='#2a2a4e')
        probs_grid.pack(fill=tk.X, padx=10, pady=5)

        tier_fields = [
            ('mystic', 'Mystic', '0.14', '#ff4444'),
            ('legendary', 'Leg', '1.63', '#00ff88'),
            ('unique', 'Uniq', '3.3', '#ffd700'),
            ('epic', 'Epic', '37.93', '#9d65c9'),
            ('rare', 'Rare', '32', '#4a9eff'),
            ('common', 'Com', '25', '#888888'),
        ]

        for i, (key, label, default, color) in enumerate(tier_fields):
            col_frame = tk.Frame(probs_grid, bg='#2a2a4e')
            col_frame.pack(side=tk.LEFT, padx=3)

            tk.Label(col_frame, text=label, font=('Segoe UI', 8),
                     fg=color, bg='#2a2a4e').pack()

            self.hero_power_level_widgets[f'{key}_rate'] = tk.StringVar(value=default)
            entry = tk.Entry(
                col_frame, textvariable=self.hero_power_level_widgets[f'{key}_rate'],
                width=6, font=('Consolas', 9), bg='#3a3a5a', fg='#eee',
                insertbackground='white', justify='center'
            )
            entry.pack()

        # Apply button
        btn_row = tk.Frame(level_frame, bg='#2a2a4e')
        btn_row.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(
            btn_row, text="Apply Level Config",
            command=self._apply_hero_power_level_config,
            bg='#4a9eff', fg='white', font=('Segoe UI', 9, 'bold'), width=18
        ).pack(side=tk.LEFT)

        self.hero_level_status_label = tk.Label(
            btn_row, text="", font=('Segoe UI', 9), fg='#00ff88', bg='#2a2a4e'
        )
        self.hero_level_status_label.pack(side=tk.LEFT, padx=10)

        # Simulation Settings section
        self._section_header(right_col, "Simulation Settings")

        sim_settings_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        sim_settings_frame.pack(fill=tk.X, pady=5)

        # Simulation mode selection
        mode_row = tk.Frame(sim_settings_frame, bg='#2a2a4e')
        mode_row.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(mode_row, text="Mode:", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT)

        self.hero_sim_mode_var = tk.StringVar(value="custom")
        tk.Radiobutton(
            mode_row, text="Custom Stats", variable=self.hero_sim_mode_var,
            value="custom", bg='#2a2a4e', fg='#ccc', selectcolor='#3a3a5a',
            activebackground='#2a2a4e', activeforeground='#ffd700',
            command=self._update_hero_sim_mode
        ).pack(side=tk.LEFT, padx=10)

        tk.Radiobutton(
            mode_row, text="DPS Target", variable=self.hero_sim_mode_var,
            value="dps", bg='#2a2a4e', fg='#ccc', selectcolor='#3a3a5a',
            activebackground='#2a2a4e', activeforeground='#ffd700',
            command=self._update_hero_sim_mode
        ).pack(side=tk.LEFT, padx=10)

        # Custom stats target settings
        self.hero_custom_frame = tk.Frame(sim_settings_frame, bg='#2a2a4e')
        self.hero_custom_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(self.hero_custom_frame, text="Target Stats (at least X lines):",
                 font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e').pack(anchor=tk.W)

        # Target 1
        target1_row = tk.Frame(self.hero_custom_frame, bg='#2a2a4e')
        target1_row.pack(fill=tk.X, pady=2)

        stat_options = [STAT_DISPLAY_NAMES[s] for s in VALUABLE_STATS]
        self.hero_target1_stat = ttk.Combobox(target1_row, values=stat_options, width=20)
        self.hero_target1_stat.pack(side=tk.LEFT, padx=5)
        self.hero_target1_stat.set("Defense Penetration %")

        tk.Label(target1_row, text="x", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT)

        self.hero_target1_count = ttk.Combobox(target1_row, values=[1, 2, 3, 4, 5], width=5)
        self.hero_target1_count.pack(side=tk.LEFT, padx=5)
        self.hero_target1_count.set("2")

        # Target 2
        target2_row = tk.Frame(self.hero_custom_frame, bg='#2a2a4e')
        target2_row.pack(fill=tk.X, pady=2)

        self.hero_target2_stat = ttk.Combobox(target2_row, values=["(none)"] + stat_options, width=20)
        self.hero_target2_stat.pack(side=tk.LEFT, padx=5)
        self.hero_target2_stat.set("Damage %")

        tk.Label(target2_row, text="x", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT)

        self.hero_target2_count = ttk.Combobox(target2_row, values=[1, 2, 3], width=5)
        self.hero_target2_count.pack(side=tk.LEFT, padx=5)
        self.hero_target2_count.set("2")

        # Min tier
        tier_row = tk.Frame(self.hero_custom_frame, bg='#2a2a4e')
        tier_row.pack(fill=tk.X, pady=5)

        tk.Label(tier_row, text="Min Tier:", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT)

        tier_options = ["legendary", "mystic"]
        self.hero_min_tier = ttk.Combobox(tier_row, values=tier_options, width=12)
        self.hero_min_tier.pack(side=tk.LEFT, padx=5)
        self.hero_min_tier.set("legendary")

        # DPS target settings (hidden by default)
        self.hero_dps_frame = tk.Frame(sim_settings_frame, bg='#2a2a4e')

        tk.Label(self.hero_dps_frame, text="Improve DPS by (%):",
                 font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e').pack(anchor=tk.W)

        dps_row = tk.Frame(self.hero_dps_frame, bg='#2a2a4e')
        dps_row.pack(fill=tk.X, pady=5)

        self.hero_dps_target_var = tk.DoubleVar(value=5.0)
        self.hero_dps_slider = ttk.Scale(
            dps_row, from_=1, to=50, variable=self.hero_dps_target_var,
            orient=tk.HORIZONTAL, length=200,
            command=self._on_hero_dps_slider
        )
        self.hero_dps_slider.pack(side=tk.LEFT, padx=5)

        self.hero_dps_value_label = tk.Label(
            dps_row, text="5.0%", font=('Consolas', 10),
            fg='#00ff88', bg='#2a2a4e'
        )
        self.hero_dps_value_label.pack(side=tk.LEFT, padx=5)

        # Run simulation button
        btn_row = tk.Frame(sim_settings_frame, bg='#2a2a4e')
        btn_row.pack(fill=tk.X, padx=10, pady=10)

        self.hero_sim_btn = tk.Button(
            btn_row, text="Run Simulation (10,000 iterations)",
            command=self.run_hero_power_simulation,
            bg='#ff9f43', fg='white', font=('Segoe UI', 11, 'bold'),
            width=30
        )
        self.hero_sim_btn.pack(pady=5)

        # Simulation results section
        self._section_header(right_col, "Simulation Results")

        results_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.hero_sim_results_label = tk.Label(
            results_frame,
            text="Configure target and click 'Run Simulation'",
            font=('Consolas', 10), fg='#aaa', bg='#2a2a4e',
            justify=tk.LEFT, anchor=tk.NW
        )
        self.hero_sim_results_label.pack(anchor=tk.W, padx=10, pady=10, fill=tk.X)

        # Distribution chart (BarChart packs itself internally)
        self.hero_sim_chart = BarChart(results_frame, width=380, height=150)

        # Tier probabilities reference
        self._section_header(right_col, "Tier Probabilities (per line)")

        prob_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        prob_frame.pack(fill=tk.X, pady=5)

        prob_text = (
            "Mystic:    0.12%\n"
            "Legendary: 1.54%\n\n"
            "Mystic Stats:\n"
            "  Damage: 28-40%\n"
            "  Boss Damage: 28-40%\n"
            "  Def Pen: 14-20%\n"
            "  Max Dmg Mult: 28-40%"
        )
        tk.Label(
            prob_frame, text=prob_text,
            font=('Consolas', 9), fg='#ccc', bg='#2a2a4e',
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=10, pady=10)

        # =====================================================================
        # REROLL ADVISOR - Shows which lines to lock/reroll for current tab
        # =====================================================================
        self._section_header(right_col, "Reroll Advisor")

        advisor_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        advisor_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        advisor_info = tk.Label(
            advisor_frame,
            text="Analyzes current tab and tells you what to lock/reroll:",
            font=('Segoe UI', 9), fg='#888', bg='#2a2a4e'
        )
        advisor_info.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Analyze button
        analyze_btn = tk.Button(
            advisor_frame, text="Analyze Current Tab",
            command=self._analyze_hero_power_for_reroll,
            bg='#4a9eff', fg='white', font=('Segoe UI', 10, 'bold'), width=20
        )
        analyze_btn.pack(pady=5)

        # Results display - Lines to LOCK
        lock_header = tk.Label(
            advisor_frame, text="LINES TO LOCK (keep these):",
            font=('Segoe UI', 10, 'bold'), fg='#00ff88', bg='#2a2a4e'
        )
        lock_header.pack(anchor=tk.W, padx=10, pady=(10, 2))

        self.advisor_lock_label = tk.Label(
            advisor_frame, text="Click 'Analyze' to see recommendations",
            font=('Consolas', 9), fg='#ccc', bg='#2a2a4e',
            justify=tk.LEFT, anchor=tk.NW
        )
        self.advisor_lock_label.pack(anchor=tk.W, padx=15, pady=2)

        # Results display - Lines to REROLL
        reroll_header = tk.Label(
            advisor_frame, text="LINES TO REROLL (trash these):",
            font=('Segoe UI', 10, 'bold'), fg='#ff6b6b', bg='#2a2a4e'
        )
        reroll_header.pack(anchor=tk.W, padx=10, pady=(10, 2))

        self.advisor_reroll_label = tk.Label(
            advisor_frame, text="",
            font=('Consolas', 9), fg='#ccc', bg='#2a2a4e',
            justify=tk.LEFT, anchor=tk.NW
        )
        self.advisor_reroll_label.pack(anchor=tk.W, padx=15, pady=2)

        # Target lines to aim for
        target_header = tk.Label(
            advisor_frame, text="LINES TO AIM FOR (best stats by mode):",
            font=('Segoe UI', 10, 'bold'), fg='#ffd700', bg='#2a2a4e'
        )
        target_header.pack(anchor=tk.W, padx=10, pady=(10, 2))

        self.advisor_target_label = tk.Label(
            advisor_frame, text="",
            font=('Consolas', 9), fg='#ccc', bg='#2a2a4e',
            justify=tk.LEFT, anchor=tk.NW
        )
        self.advisor_target_label.pack(anchor=tk.W, padx=15, pady=2)

        # Lock threshold explanation
        threshold_header = tk.Label(
            advisor_frame, text="KEEP/REROLL THRESHOLDS:",
            font=('Segoe UI', 10, 'bold'), fg='#9d65c9', bg='#2a2a4e'
        )
        threshold_header.pack(anchor=tk.W, padx=10, pady=(10, 2))

        self.advisor_threshold_label = tk.Label(
            advisor_frame, text="",
            font=('Consolas', 9), fg='#ccc', bg='#2a2a4e',
            justify=tk.LEFT, anchor=tk.NW
        )
        self.advisor_threshold_label.pack(anchor=tk.W, padx=15, pady=(2, 10))

        # Initial display update
        self.update_hero_power_display()

    def _build_hero_power_line_editor(self, parent, slot: int):
        """Build editor widgets for a single Hero Power line."""
        frame = tk.Frame(parent, bg='#2a2a4e')
        frame.pack(fill=tk.X, padx=10, pady=3)

        # Line number label
        tk.Label(frame, text=f"Line {slot}:", font=('Segoe UI', 10, 'bold'),
                 fg='#ffd700', bg='#2a2a4e', width=7).pack(side=tk.LEFT)

        # Stat type dropdown
        stat_options = [STAT_DISPLAY_NAMES[s] for s in HeroPowerStatType]
        stat_var = tk.StringVar(value=STAT_DISPLAY_NAMES[HeroPowerStatType.DAMAGE])
        stat_dropdown = ttk.Combobox(frame, textvariable=stat_var,
                                     values=stat_options, width=18)
        stat_dropdown.pack(side=tk.LEFT, padx=3)
        stat_dropdown.bind('<<ComboboxSelected>>',
                          lambda e, s=slot: self._on_hero_line_change(s))

        # Value entry
        value_var = tk.StringVar(value="0.0")
        value_entry = tk.Entry(frame, textvariable=value_var, width=8,
                               font=('Consolas', 10), bg='#3a3a5a', fg='#eee',
                               insertbackground='white')
        value_entry.pack(side=tk.LEFT, padx=3)
        value_entry.bind('<FocusOut>', lambda e, s=slot: self._on_hero_line_change(s))
        value_entry.bind('<Return>', lambda e, s=slot: self._on_hero_line_change(s))

        tk.Label(frame, text="%", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT)

        # Tier dropdown
        tier_options = [t.value.capitalize() for t in HeroPowerTier]
        tier_var = tk.StringVar(value="Common")
        tier_dropdown = ttk.Combobox(frame, textvariable=tier_var,
                                     values=tier_options, width=10)
        tier_dropdown.pack(side=tk.LEFT, padx=3)
        tier_dropdown.bind('<<ComboboxSelected>>',
                          lambda e, s=slot: self._on_hero_line_change(s))

        # Lock checkbox
        lock_var = tk.BooleanVar(value=False)
        lock_cb = tk.Checkbutton(frame, text="Lock", variable=lock_var,
                                 bg='#2a2a4e', fg='#ccc', selectcolor='#3a3a5a',
                                 activebackground='#2a2a4e', activeforeground='#ffd700',
                                 command=lambda s=slot: self._on_hero_lock_change(s))
        lock_cb.pack(side=tk.LEFT, padx=5)

        # Store widget references
        self.hero_power_line_widgets[slot] = {
            'stat_var': stat_var,
            'stat_dropdown': stat_dropdown,
            'value_var': value_var,
            'value_entry': value_entry,
            'tier_var': tier_var,
            'tier_dropdown': tier_dropdown,
            'lock_var': lock_var,
            'lock_cb': lock_cb,
        }

    def _on_hero_line_change(self, slot: int):
        """Handle changes to a hero power line."""
        widgets = self.hero_power_line_widgets[slot]

        # Get values from widgets
        stat_name = widgets['stat_var'].get()
        try:
            value = float(widgets['value_var'].get())
        except ValueError:
            value = 0.0

        tier_name = widgets['tier_var'].get().lower()
        is_locked = widgets['lock_var'].get()

        # Map stat name back to enum
        stat_type = HeroPowerStatType.DAMAGE
        for st, name in STAT_DISPLAY_NAMES.items():
            if name == stat_name:
                stat_type = st
                break

        # Map tier name back to enum
        tier = HeroPowerTier.COMMON
        for t in HeroPowerTier:
            if t.value == tier_name:
                tier = t
                break

        # Update config
        line = self.hero_power_config.lines[slot - 1]
        line.stat_type = stat_type
        line.value = value
        line.tier = tier
        line.is_locked = is_locked

        # Update displays
        self.update_hero_power_display()

    def _on_hero_lock_change(self, slot: int):
        """Handle lock checkbox change."""
        widgets = self.hero_power_line_widgets[slot]
        self.hero_power_config.lines[slot - 1].is_locked = widgets['lock_var'].get()
        self.update_hero_power_cost_display()

    # =========================================================================
    # HERO POWER TAB-BASED PRESET MANAGEMENT
    # =========================================================================

    def _build_hero_power_line_editor_for_tab(self, parent, tab_idx: int, slot: int):
        """Build editor widgets for a single Hero Power line in a specific tab."""
        frame = tk.Frame(parent, bg='#2a2a4e')
        frame.pack(fill=tk.X, padx=10, pady=3)

        # Line number label
        tk.Label(frame, text=f"Line {slot}:", font=('Segoe UI', 10, 'bold'),
                 fg='#ffd700', bg='#2a2a4e', width=7).pack(side=tk.LEFT)

        # Stat type dropdown
        stat_options = [STAT_DISPLAY_NAMES[s] for s in HeroPowerStatType]
        stat_var = tk.StringVar(value=STAT_DISPLAY_NAMES[HeroPowerStatType.DAMAGE])
        stat_dropdown = ttk.Combobox(frame, textvariable=stat_var,
                                     values=stat_options, width=18)
        stat_dropdown.pack(side=tk.LEFT, padx=3)
        stat_dropdown.bind('<<ComboboxSelected>>',
                          lambda e, t=tab_idx, s=slot: self._on_hero_tab_line_change(t, s))

        # Value entry
        value_var = tk.StringVar(value="0.0")
        value_entry = tk.Entry(frame, textvariable=value_var, width=8,
                               font=('Consolas', 10), bg='#3a3a5a', fg='#eee',
                               insertbackground='white')
        value_entry.pack(side=tk.LEFT, padx=3)
        value_entry.bind('<FocusOut>', lambda e, t=tab_idx, s=slot: self._on_hero_tab_line_change(t, s))
        value_entry.bind('<Return>', lambda e, t=tab_idx, s=slot: self._on_hero_tab_line_change(t, s))

        tk.Label(frame, text="%", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT)

        # Tier dropdown
        tier_options = [t.value.capitalize() for t in HeroPowerTier]
        tier_var = tk.StringVar(value="Common")
        tier_dropdown = ttk.Combobox(frame, textvariable=tier_var,
                                     values=tier_options, width=10)
        tier_dropdown.pack(side=tk.LEFT, padx=3)
        tier_dropdown.bind('<<ComboboxSelected>>',
                          lambda e, t=tab_idx, s=slot: self._on_hero_tab_line_change(t, s))

        # Lock checkbox
        lock_var = tk.BooleanVar(value=False)
        lock_cb = tk.Checkbutton(frame, text="Lock", variable=lock_var,
                                 bg='#2a2a4e', fg='#ccc', selectcolor='#3a3a5a',
                                 activebackground='#2a2a4e', activeforeground='#ffd700',
                                 command=lambda t=tab_idx, s=slot: self._on_hero_tab_lock_change(t, s))
        lock_cb.pack(side=tk.LEFT, padx=5)

        # Store widget references by tab and slot
        self.hero_power_tab_widgets[tab_idx][slot] = {
            'stat_var': stat_var,
            'stat_dropdown': stat_dropdown,
            'value_var': value_var,
            'value_entry': value_entry,
            'tier_var': tier_var,
            'tier_dropdown': tier_dropdown,
            'lock_var': lock_var,
            'lock_cb': lock_cb,
        }

    def _on_hero_tab_line_change(self, tab_idx: int, slot: int):
        """Handle changes to a hero power line in a specific tab."""
        widgets = self.hero_power_tab_widgets[tab_idx][slot]

        # Get values from widgets
        stat_name = widgets['stat_var'].get()
        try:
            value = float(widgets['value_var'].get())
        except ValueError:
            value = 0.0

        tier_name = widgets['tier_var'].get().lower()
        is_locked = widgets['lock_var'].get()

        # Map stat name back to enum
        stat_type = HeroPowerStatType.DAMAGE
        for st, name in STAT_DISPLAY_NAMES.items():
            if name == stat_name:
                stat_type = st
                break

        # Map tier name back to enum
        tier = HeroPowerTier.COMMON
        for t in HeroPowerTier:
            if t.value == tier_name:
                tier = t
                break

        # Get the preset for this tab
        preset_name = f"Tab {tab_idx}"
        if preset_name not in self.hero_power_presets:
            # Create new preset if it doesn't exist
            self.hero_power_presets[preset_name] = HeroPowerConfig(preset_name=preset_name)

        config = self.hero_power_presets[preset_name]

        # Update config
        line = config.lines[slot - 1]
        line.stat_type = stat_type
        line.value = value
        line.tier = tier
        line.is_locked = is_locked

        # If this is the current tab, also update the main config
        if tab_idx == self.hero_power_current_tab:
            self.hero_power_config = config
            self.update_hero_power_display()

        # Auto-save all presets
        self.save_all_hero_power_presets()

    def _on_hero_tab_lock_change(self, tab_idx: int, slot: int):
        """Handle lock checkbox change in a specific tab."""
        widgets = self.hero_power_tab_widgets[tab_idx][slot]
        is_locked = widgets['lock_var'].get()

        # Get the preset for this tab
        preset_name = f"Tab {tab_idx}"
        if preset_name in self.hero_power_presets:
            self.hero_power_presets[preset_name].lines[slot - 1].is_locked = is_locked

        # If this is the current tab, update displays
        if tab_idx == self.hero_power_current_tab:
            self.hero_power_config.lines[slot - 1].is_locked = is_locked
            self.update_hero_power_cost_display()

        # Auto-save
        self.save_all_hero_power_presets()

    def _on_hero_power_tab_changed(self, event):
        """Handle switching between Hero Power preset tabs."""
        try:
            # Get the newly selected tab index (0-based)
            selected_idx = self.hero_power_preset_notebook.index(
                self.hero_power_preset_notebook.select()
            )
            tab_idx = selected_idx + 1  # Convert to 1-based

            self.hero_power_current_tab = tab_idx
            preset_name = f"Tab {tab_idx}"

            # Ensure preset exists
            if preset_name not in self.hero_power_presets:
                self.hero_power_presets[preset_name] = HeroPowerConfig(preset_name=preset_name)

            # Set current config to this preset
            self.hero_power_config = self.hero_power_presets[preset_name]

            # Update preset var for compatibility
            self.hero_power_preset_var.set(preset_name)

            # Update displays
            self.update_hero_power_display()

        except Exception as e:
            print(f"Error switching HP tab: {e}")

    def _update_hero_power_tab_widgets_from_preset(self, tab_idx: int):
        """Update a tab's widgets from its preset config."""
        preset_name = f"Tab {tab_idx}"
        if preset_name not in self.hero_power_presets:
            return

        config = self.hero_power_presets[preset_name]

        for slot in range(1, 7):
            if tab_idx not in self.hero_power_tab_widgets:
                continue
            if slot not in self.hero_power_tab_widgets[tab_idx]:
                continue

            widgets = self.hero_power_tab_widgets[tab_idx][slot]
            line = config.lines[slot - 1]

            # Update widget values
            widgets['stat_var'].set(STAT_DISPLAY_NAMES.get(line.stat_type, "Damage"))
            widgets['value_var'].set(f"{line.value:.1f}")
            widgets['tier_var'].set(line.tier.value.capitalize())
            widgets['lock_var'].set(line.is_locked)

    def _initialize_hero_power_tabs(self):
        """Initialize all hero power tabs from saved presets."""
        # Ensure we have presets for all 10 tabs
        for tab_idx in range(1, 11):
            preset_name = f"Tab {tab_idx}"
            if preset_name not in self.hero_power_presets:
                self.hero_power_presets[preset_name] = HeroPowerConfig(preset_name=preset_name)

            # Update tab widgets from preset
            self._update_hero_power_tab_widgets_from_preset(tab_idx)

        # Set current tab to 1 and load that config
        self.hero_power_current_tab = 1
        self.hero_power_config = self.hero_power_presets.get("Tab 1", HeroPowerConfig(preset_name="Tab 1"))

    # =========================================================================
    # HERO POWER PASSIVE STATS UI
    # =========================================================================

    def _build_hero_power_passive_section(self, parent):
        """Build the passive stats input section for Hero Power."""
        # Create a grid of passive stat level inputs
        stats_grid = tk.Frame(parent, bg='#2a2a4e')
        stats_grid.pack(fill=tk.X, padx=10, pady=5)

        # Define the passive stats with their display info
        passive_stats = [
            (HeroPowerPassiveStatType.MAIN_STAT, "Main Stat", 60, "+27.5/lv"),
            (HeroPowerPassiveStatType.DAMAGE_PERCENT, "Damage %", 60, "+0.75%/lv"),
            (HeroPowerPassiveStatType.ATTACK, "Attack", 60, "+103.75/lv"),
            (HeroPowerPassiveStatType.MAX_HP, "Max HP", 60, "+2,075/lv"),
            (HeroPowerPassiveStatType.ACCURACY, "Accuracy", 20, "+2.25/lv"),
            (HeroPowerPassiveStatType.DEFENSE, "Defense", 60, "+93.75/lv"),
        ]

        # Build two columns of stats
        row = 0
        col = 0
        for stat_type, display_name, max_level, per_level_text in passive_stats:
            stat_frame = tk.Frame(stats_grid, bg='#2a2a4e')
            stat_frame.grid(row=row, column=col, sticky='w', padx=5, pady=2)

            # Label
            tk.Label(
                stat_frame, text=f"{display_name}:",
                font=('Segoe UI', 9), fg='#ccc', bg='#2a2a4e', width=10, anchor='w'
            ).pack(side=tk.LEFT)

            # Level entry
            level_var = tk.StringVar(value="0")
            level_entry = tk.Entry(
                stat_frame, textvariable=level_var, width=4,
                font=('Consolas', 10), bg='#3a3a5a', fg='#eee',
                insertbackground='white', justify='center'
            )
            level_entry.pack(side=tk.LEFT, padx=2)
            level_entry.bind('<FocusOut>', lambda e, st=stat_type: self._on_hero_passive_change(st))
            level_entry.bind('<Return>', lambda e, st=stat_type: self._on_hero_passive_change(st))

            # Max level label
            tk.Label(
                stat_frame, text=f"/{max_level}",
                font=('Segoe UI', 9), fg='#888', bg='#2a2a4e'
            ).pack(side=tk.LEFT)

            # Per-level hint
            tk.Label(
                stat_frame, text=f"({per_level_text})",
                font=('Segoe UI', 8), fg='#666', bg='#2a2a4e'
            ).pack(side=tk.LEFT, padx=3)

            # Store widget reference
            self.hero_power_passive_widgets[stat_type] = {
                'level_var': level_var,
                'level_entry': level_entry,
            }

            # Alternate columns
            col += 1
            if col > 1:
                col = 0
                row += 1

        # Quick action buttons
        button_row = tk.Frame(parent, bg='#2a2a4e')
        button_row.pack(fill=tk.X, padx=10, pady=(5, 0))

        tk.Button(
            button_row, text="Set All Max", command=self._set_hero_passive_max,
            bg='#4a9eff', fg='white', font=('Segoe UI', 8), width=10
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            button_row, text="Clear All", command=self._set_hero_passive_clear,
            bg='#ff6b6b', fg='white', font=('Segoe UI', 8), width=10
        ).pack(side=tk.LEFT, padx=2)

    def _on_hero_passive_change(self, stat_type: HeroPowerPassiveStatType):
        """Handle changes to a passive stat level."""
        widgets = self.hero_power_passive_widgets.get(stat_type)
        if not widgets:
            return

        try:
            level = int(widgets['level_var'].get())
        except ValueError:
            level = 0

        # Update the config
        self.hero_power_passive_config.set_stat_level(stat_type, level)

        # Sync the widget with clamped value
        actual_level = self.hero_power_passive_config.get_stat_level(stat_type)
        widgets['level_var'].set(str(actual_level))

        # Update displays
        self._update_hero_passive_summary()
        self.update_damage()
        self.save_hero_power_passive_to_csv()

    def _set_hero_passive_max(self):
        """Set all passive stats to their maximum levels."""
        for stat_type in HeroPowerPassiveStatType:
            max_level = HERO_POWER_PASSIVE_STATS[stat_type]["max_level"]
            self.hero_power_passive_config.set_stat_level(stat_type, max_level)

            widgets = self.hero_power_passive_widgets.get(stat_type)
            if widgets:
                widgets['level_var'].set(str(max_level))

        self._update_hero_passive_summary()
        self.update_damage()
        self.save_hero_power_passive_to_csv()

    def _set_hero_passive_clear(self):
        """Clear all passive stats to zero."""
        for stat_type in HeroPowerPassiveStatType:
            self.hero_power_passive_config.set_stat_level(stat_type, 0)

            widgets = self.hero_power_passive_widgets.get(stat_type)
            if widgets:
                widgets['level_var'].set("0")

        self._update_hero_passive_summary()
        self.update_damage()
        self.save_hero_power_passive_to_csv()

    def _update_hero_passive_summary(self):
        """Update the passive stats summary label."""
        stats = self.hero_power_passive_config.get_all_stats()

        main_stat = stats.get("main_stat_flat", 0)
        damage_pct = stats.get("damage_percent", 0)
        attack = stats.get("attack_flat", 0)

        summary = f"+{main_stat:,.0f} Main Stat, +{damage_pct:.1f}% Damage, +{attack:,.0f} Attack"
        self.hero_power_passive_summary_label.config(text=summary)

    def _update_hero_passive_widgets_from_config(self):
        """Sync widgets with the current passive config."""
        for stat_type in HeroPowerPassiveStatType:
            level = self.hero_power_passive_config.get_stat_level(stat_type)
            widgets = self.hero_power_passive_widgets.get(stat_type)
            if widgets:
                widgets['level_var'].set(str(level))
        self._update_hero_passive_summary()

    # =========================================================================
    # HERO POWER LEVEL CONFIG METHODS
    # =========================================================================

    def _apply_hero_power_level_config(self):
        """Apply the level config from UI widgets."""
        try:
            level = int(self.hero_power_level_widgets['level'].get())
            base_cost = int(self.hero_power_level_widgets['base_cost'].get())
            mystic_rate = float(self.hero_power_level_widgets['mystic_rate'].get())
            legendary_rate = float(self.hero_power_level_widgets['legendary_rate'].get())
            unique_rate = float(self.hero_power_level_widgets['unique_rate'].get())
            epic_rate = float(self.hero_power_level_widgets['epic_rate'].get())
            rare_rate = float(self.hero_power_level_widgets['rare_rate'].get())
            common_rate = float(self.hero_power_level_widgets['common_rate'].get())

            # Update the level config
            self.hero_power_level_config = HeroPowerLevelConfig(
                level=level,
                mystic_rate=mystic_rate,
                legendary_rate=legendary_rate,
                unique_rate=unique_rate,
                epic_rate=epic_rate,
                rare_rate=rare_rate,
                common_rate=common_rate,
                base_cost=base_cost
            )

            # Save to file
            self.save_hero_power_level_to_csv()

            # Update cost display to use new base cost
            self.update_hero_power_cost_display()

            # Show confirmation
            self.hero_level_status_label.config(text=f"Level {level} applied!", fg='#00ff88')
            self.after(2000, lambda: self.hero_level_status_label.config(text=""))

        except ValueError as e:
            self.hero_level_status_label.config(text="Invalid values!", fg='#ff6b6b')

    def save_hero_power_level_to_csv(self, filepath: str = None):
        """Save Hero Power level config to CSV file."""
        if filepath is None:
            filepath = HERO_POWER_LEVEL_SAVE_FILE

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['field', 'value'])
                config_dict = self.hero_power_level_config.to_dict()
                for field, value in config_dict.items():
                    writer.writerow([field, value])
        except Exception as e:
            print(f"Error saving hero power level config: {e}")

    def load_hero_power_level_from_csv(self, filepath: str = None, silent: bool = False):
        """Load Hero Power level config from CSV file."""
        if filepath is None:
            filepath = HERO_POWER_LEVEL_SAVE_FILE

        if not os.path.exists(filepath):
            return

        try:
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                data = {}
                for row in reader:
                    field = row['field']
                    value = row['value']
                    # Convert to appropriate type
                    if field == 'level' or field == 'base_cost':
                        data[field] = int(value)
                    else:
                        data[field] = float(value)

                self.hero_power_level_config = HeroPowerLevelConfig.from_dict(data)
                self._update_hero_level_widgets_from_config()

                if not silent:
                    messagebox.showinfo("Success", "Hero Power level config loaded successfully")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load level config: {e}")

    def _update_hero_level_widgets_from_config(self):
        """Sync level config widgets with the current config."""
        config = self.hero_power_level_config
        self.hero_power_level_widgets['level'].set(str(config.level))
        self.hero_power_level_widgets['base_cost'].set(str(config.base_cost))
        self.hero_power_level_widgets['mystic_rate'].set(str(config.mystic_rate))
        self.hero_power_level_widgets['legendary_rate'].set(str(config.legendary_rate))
        self.hero_power_level_widgets['unique_rate'].set(str(config.unique_rate))
        self.hero_power_level_widgets['epic_rate'].set(str(config.epic_rate))
        self.hero_power_level_widgets['rare_rate'].set(str(config.rare_rate))
        self.hero_power_level_widgets['common_rate'].set(str(config.common_rate))

    def auto_load_hero_power_level(self):
        """Automatically load Hero Power level config on startup."""
        if os.path.exists(HERO_POWER_LEVEL_SAVE_FILE):
            self.load_hero_power_level_from_csv(HERO_POWER_LEVEL_SAVE_FILE, silent=True)

    def _update_hero_sim_mode(self):
        """Toggle between custom stats and DPS target modes."""
        mode = self.hero_sim_mode_var.get()
        if mode == "custom":
            self.hero_dps_frame.pack_forget()
            self.hero_custom_frame.pack(fill=tk.X, padx=10, pady=5)
        else:
            self.hero_custom_frame.pack_forget()
            self.hero_dps_frame.pack(fill=tk.X, padx=10, pady=5)

    def _on_hero_dps_slider(self, value):
        """Handle DPS slider change."""
        val = float(value)
        self.hero_dps_value_label.config(text=f"{val:.1f}%")

    def update_hero_power_display(self):
        """Update all Hero Power UI elements."""
        self.update_hero_power_cost_display()
        self.update_hero_power_stats_display()
        self.update_hero_power_dps_display()

    def update_hero_power_cost_display(self):
        """Update the medal cost display based on locked lines and level config."""
        locked = self.hero_power_config.get_locked_count()
        # Use level config for cost calculation if available
        cost = self.hero_power_level_config.get_reroll_cost(locked)

        self.hero_power_locked_label.config(text=f"Locked Lines: {locked}")
        self.hero_power_cost_label.config(text=f"Cost per Reroll: {cost} medals")

    def update_hero_power_stats_display(self):
        """Update the stat contribution summary."""
        stats = self.hero_power_config.get_all_stats()

        if not stats or all(v == 0 for v in stats.values()):
            self.hero_power_stats_label.config(text="No stats configured")
            return

        lines = []
        for stat_type, value in stats.items():
            if value > 0:
                name = STAT_DISPLAY_NAMES.get(stat_type, stat_type.value)
                if stat_type in (HeroPowerStatType.DEFENSE, HeroPowerStatType.MAX_HP):
                    lines.append(f"{name}: +{value:.0f}")
                else:
                    lines.append(f"{name}: +{value:.1f}%")

        self.hero_power_stats_label.config(text="\n".join(lines))

    def update_hero_power_dps_display(self):
        """Update the DPS impact display."""
        # Calculate DPS with and without hero power
        base_stats = self._get_damage_stats()
        base_dps = self._calc_damage(base_stats)

        # Add hero power stats
        hero_stats = self.get_hero_power_stats_total()
        modified_stats = base_stats.copy()
        modified_stats['damage_percent'] = base_stats.get('damage_percent', 0) + hero_stats.get('damage', 0)
        modified_stats['boss_damage'] = base_stats.get('boss_damage', 0) + hero_stats.get('boss_damage', 0)
        modified_stats['defense_pen'] = base_stats.get('defense_pen', 0) + hero_stats.get('def_pen', 0)
        modified_stats['crit_damage'] = base_stats.get('crit_damage', 0) + hero_stats.get('crit_damage', 0)

        hero_dps = self._calc_damage(modified_stats)

        if base_dps > 0:
            change = ((hero_dps / base_dps) - 1) * 100
            if change > 0:
                self.hero_power_dps_label.config(
                    text=f"DPS Impact: +{change:.2f}%",
                    fg='#00ff88'
                )
            else:
                self.hero_power_dps_label.config(
                    text=f"DPS Impact: {change:.2f}%",
                    fg='#ff6b6b'
                )
        else:
            self.hero_power_dps_label.config(text="DPS Impact: ---", fg='#888')

    def get_hero_power_stats_total(self) -> Dict[str, float]:
        """Calculate total stats from Hero Power ABILITY LINES for damage calculation."""
        stats = self.hero_power_config.get_all_stats()

        return {
            'damage': stats.get(HeroPowerStatType.DAMAGE, 0),
            'boss_damage': stats.get(HeroPowerStatType.BOSS_DAMAGE, 0),
            'normal_damage': stats.get(HeroPowerStatType.NORMAL_DAMAGE, 0),
            'def_pen': stats.get(HeroPowerStatType.DEF_PEN, 0),
            'max_dmg_mult': stats.get(HeroPowerStatType.MAX_DMG_MULT, 0),
            'min_dmg_mult': stats.get(HeroPowerStatType.MIN_DMG_MULT, 0),
            'crit_rate': stats.get(HeroPowerStatType.CRIT_RATE, 0),
            'crit_damage': stats.get(HeroPowerStatType.CRIT_DAMAGE, 0),
            'main_stat_pct': stats.get(HeroPowerStatType.MAIN_STAT_PCT, 0),
            'attack_pct': stats.get(HeroPowerStatType.ATTACK_PCT, 0),
        }

    def get_hero_power_passive_stats_total(self) -> Dict[str, float]:
        """Calculate total stats from Hero Power PASSIVE STATS for damage calculation.

        Passive stats are leveled (not rerolled) and provide flat bonuses:
        - Main Stat (flat): +27.5 per level, max 1,650 at 60/60
        - Damage %: +0.75% per level, max 45% at 60/60
        - Attack (flat): +103.75 per level, max 6,225 at 60/60
        - Max HP (flat): +2,075 per level, max 124,500 at 60/60
        - Accuracy: +2.25 per level, max 45 at 20/20
        - Defense (flat): +93.75 per level, max 5,625 at 60/60
        """
        return self.hero_power_passive_config.get_all_stats()

    # =========================================================================
    # HERO POWER REROLL ADVISOR
    # =========================================================================

    def _analyze_hero_power_for_reroll(self):
        """
        Analyze current Hero Power tab and provide reroll recommendations.

        Shows:
        1. Which lines to LOCK (worth keeping)
        2. Which lines to REROLL (trash)
        3. What stats to aim for when rolling
        4. Thresholds for what to keep vs reroll during rolling
        """
        from hero_power import (
            score_hero_power_line, get_line_score_category,
            calculate_line_dps_value, STAT_DISPLAY_NAMES as HP_STAT_NAMES,
            HERO_POWER_STAT_RANGES, HeroPowerTier, HeroPowerStatType,
            MODE_STAT_ADJUSTMENTS, STAT_DPS_WEIGHTS,
        )

        config = self.hero_power_config
        mode = self.combat_mode.value if hasattr(self.combat_mode, 'value') else str(self.combat_mode)

        # Analyze each line
        line_analysis = []
        for i, line in enumerate(config.lines):
            # Calculate DPS contribution
            dps_value = calculate_line_dps_value(line, self._calc_damage, self._get_damage_stats)
            score = score_hero_power_line(line, self._calc_damage, self._get_damage_stats)
            category, color = get_line_score_category(score)

            stat_name = HP_STAT_NAMES.get(line.stat_type, line.stat_type.value)
            tier_name = line.tier.value.capitalize()

            line_analysis.append({
                'slot': i + 1,
                'stat_name': stat_name,
                'tier': tier_name,
                'tier_enum': line.tier,
                'value': line.value,
                'dps': dps_value,
                'score': score,
                'category': category,
                'stat_type': line.stat_type,
            })

        # Sort by score for recommendations
        sorted_by_score = sorted(line_analysis, key=lambda x: x['score'], reverse=True)

        # Determine lock threshold based on tier
        # Mystic/Legendary with good stats = LOCK
        # Unique with top stats = maybe LOCK
        # Epic and below = REROLL

        lines_to_lock = []
        lines_to_reroll = []

        for la in line_analysis:
            # Lock criteria:
            # 1. Mystic tier with any offensive stat
            # 2. Legendary tier with good stat (score >= 40)
            # 3. Unique tier with excellent stat (score >= 60)
            tier = la['tier_enum']
            score = la['score']
            stat_type = la['stat_type']

            # Offensive stats worth keeping
            offensive_stats = {
                HeroPowerStatType.DEF_PEN, HeroPowerStatType.BOSS_DAMAGE,
                HeroPowerStatType.DAMAGE, HeroPowerStatType.CRIT_DAMAGE,
                HeroPowerStatType.MAX_DMG_MULT, HeroPowerStatType.MAIN_STAT_PCT,
                HeroPowerStatType.CRIT_RATE, HeroPowerStatType.ATTACK_PCT,
            }

            is_offensive = stat_type in offensive_stats

            should_lock = False
            if tier == HeroPowerTier.MYSTIC and is_offensive:
                should_lock = True
            elif tier == HeroPowerTier.LEGENDARY and is_offensive and score >= 35:
                should_lock = True
            elif tier == HeroPowerTier.UNIQUE and is_offensive and score >= 50:
                should_lock = True

            if should_lock:
                lines_to_lock.append(la)
            else:
                lines_to_reroll.append(la)

        # Format LOCK recommendations
        if lines_to_lock:
            lock_text_lines = []
            for la in sorted(lines_to_lock, key=lambda x: x['slot']):
                lock_text_lines.append(
                    f"L{la['slot']}: {la['tier'][:3]} {la['stat_name'][:15]} "
                    f"{la['value']:.0f}% (+{la['dps']:.2f}% DPS)"
                )
            lock_text = "\n".join(lock_text_lines)
        else:
            lock_text = "None - reroll all lines"

        # Format REROLL recommendations
        if lines_to_reroll:
            reroll_text_lines = []
            for la in sorted(lines_to_reroll, key=lambda x: x['slot']):
                reroll_text_lines.append(
                    f"L{la['slot']}: {la['tier'][:3]} {la['stat_name'][:15]} "
                    f"{la['value']:.0f}% (+{la['dps']:.2f}% DPS)"
                )
            reroll_text = "\n".join(reroll_text_lines)
        else:
            reroll_text = "None - all lines are good!"

        # Format TARGET stats to aim for (mode-specific)
        mode_display = {"stage": "Stage", "boss": "Boss", "world_boss": "World Boss"}
        current_mode_name = mode_display.get(mode, "Stage")

        # Get best stats for current mode
        mode_adjustments = MODE_STAT_ADJUSTMENTS.get(mode, {})

        # Calculate effective weight for each stat
        stat_rankings = []
        for stat_type in [
            HeroPowerStatType.DEF_PEN, HeroPowerStatType.BOSS_DAMAGE,
            HeroPowerStatType.DAMAGE, HeroPowerStatType.CRIT_DAMAGE,
            HeroPowerStatType.MAX_DMG_MULT, HeroPowerStatType.NORMAL_DAMAGE,
            HeroPowerStatType.MAIN_STAT_PCT, HeroPowerStatType.CRIT_RATE,
        ]:
            base_weight = STAT_DPS_WEIGHTS.get(stat_type, 0.5)
            mode_mult = mode_adjustments.get(stat_type, 1.0)
            effective_weight = base_weight * mode_mult

            if effective_weight > 0:  # Skip useless stats (normal dmg in boss mode)
                stat_name = HP_STAT_NAMES.get(stat_type, stat_type.value)
                # Get mystic range
                mystic_range = HERO_POWER_STAT_RANGES.get(HeroPowerTier.MYSTIC, {}).get(stat_type)
                if mystic_range:
                    range_str = f"{mystic_range[0]:.0f}-{mystic_range[1]:.0f}%"
                else:
                    range_str = "N/A"

                stat_rankings.append({
                    'stat': stat_name,
                    'weight': effective_weight,
                    'range': range_str,
                })

        # Sort by weight
        stat_rankings.sort(key=lambda x: x['weight'], reverse=True)

        target_text_lines = [f"Best stats for {current_mode_name}:"]
        for i, sr in enumerate(stat_rankings[:5], 1):
            target_text_lines.append(f"{i}. {sr['stat'][:18]} (Mystic: {sr['range']})")
        target_text = "\n".join(target_text_lines)

        # Format THRESHOLD guide
        threshold_text = (
            "When rolling, KEEP if:\n"
            "• Mystic: Any offensive stat\n"
            "• Legendary: Def Pen, Boss Dmg, Dmg%, Crit Dmg\n"
            "• Unique: Only Def Pen 8%+ or Boss Dmg 15%+\n\n"
            "REROLL if:\n"
            "• Epic or lower tier\n"
            "• Defensive stats (Defense, Max HP)\n"
            "• Normal Damage (unless Stage mode)"
        )

        # Update UI labels
        self.advisor_lock_label.config(text=lock_text)
        self.advisor_reroll_label.config(text=reroll_text)
        self.advisor_target_label.config(text=target_text)
        self.advisor_threshold_label.config(text=threshold_text)

    # =========================================================================
    # HERO POWER SIMULATION
    # =========================================================================

    def run_hero_power_simulation(self):
        """Run Monte Carlo simulation with current settings."""
        mode = self.hero_sim_mode_var.get()

        if mode == "custom":
            self._run_custom_target_simulation()
        else:
            self._run_dps_target_simulation()

    def _run_custom_target_simulation(self):
        """Run simulation for custom stat targets."""
        # Build target from UI
        stat_requirements = []

        # Target 1
        stat1_name = self.hero_target1_stat.get()
        count1 = int(self.hero_target1_count.get())

        stat1_type = None
        for st, name in STAT_DISPLAY_NAMES.items():
            if name == stat1_name:
                stat1_type = st
                break

        if stat1_type:
            stat_requirements.append((stat1_type, count1))

        # Target 2 (optional)
        stat2_name = self.hero_target2_stat.get()
        if stat2_name != "(none)":
            count2 = int(self.hero_target2_count.get())
            stat2_type = None
            for st, name in STAT_DISPLAY_NAMES.items():
                if name == stat2_name:
                    stat2_type = st
                    break
            if stat2_type:
                stat_requirements.append((stat2_type, count2))

        # Min tier
        min_tier_name = self.hero_min_tier.get()
        min_tier = HeroPowerTier.LEGENDARY
        for t in HeroPowerTier:
            if t.value == min_tier_name:
                min_tier = t
                break

        target = SimulationTarget(
            stat_requirements=stat_requirements,
            min_tier=min_tier
        )

        # Get locked lines
        locked_slots = [
            line.slot for line in self.hero_power_config.lines
            if line.is_locked
        ]

        # Run simulation
        self.hero_sim_btn.config(state=tk.DISABLED, text="Running...")
        self.root.update()

        try:
            result = run_custom_target_simulation(
                target=target,
                locked_lines=locked_slots,
                iterations=10000,
                max_rerolls=50000
            )

            self._display_simulation_results(result)

        finally:
            self.hero_sim_btn.config(state=tk.NORMAL, text="Run Simulation (10,000 iterations)")

    def _run_dps_target_simulation(self):
        """Run simulation for DPS improvement target."""
        target_pct = self.hero_dps_target_var.get()

        self.hero_sim_btn.config(state=tk.DISABLED, text="Running...")
        self.root.update()

        try:
            # Get current DPS
            base_stats = self._get_damage_stats()
            current_dps = self._calc_damage(base_stats)
            target_dps = current_dps * (1 + target_pct / 100)

            # Get locked lines
            locked_slots = [
                line.slot for line in self.hero_power_config.lines
                if line.is_locked
            ]

            # Run simulation with DPS checking
            import copy
            reroll_counts = []
            successes = 0
            iterations = 5000  # Fewer iterations for DPS mode (more expensive)
            max_rerolls = 100000

            for _ in range(iterations):
                config = copy.deepcopy(self.hero_power_config)
                # Unlock all non-locked lines for simulation
                for line in config.lines:
                    if line.slot not in locked_slots:
                        line.is_locked = False
                    else:
                        line.is_locked = True

                best_dps = current_dps
                rerolls = 0

                while rerolls < max_rerolls:
                    # Simulate reroll
                    new_config = simulate_hero_power_reroll(config)

                    # Calculate new DPS
                    hero_stats = new_config.get_all_stats()
                    test_stats = base_stats.copy()
                    test_stats['damage_percent'] = base_stats.get('damage_percent', 0) + hero_stats.get(HeroPowerStatType.DAMAGE, 0)
                    test_stats['boss_damage'] = base_stats.get('boss_damage', 0) + hero_stats.get(HeroPowerStatType.BOSS_DAMAGE, 0)
                    test_stats['defense_pen'] = base_stats.get('defense_pen', 0) + hero_stats.get(HeroPowerStatType.DEF_PEN, 0)
                    test_stats['crit_damage'] = base_stats.get('crit_damage', 0) + hero_stats.get(HeroPowerStatType.CRIT_DAMAGE, 0)

                    new_dps = self._calc_damage(test_stats)

                    # Keep if better
                    if new_dps > best_dps:
                        config = new_config
                        best_dps = new_dps

                    rerolls += 1

                    # Check target
                    if best_dps >= target_dps:
                        successes += 1
                        break

                reroll_counts.append(rerolls)

            # Calculate statistics
            sorted_counts = sorted(reroll_counts)
            median_idx = len(sorted_counts) // 2
            p90_idx = int(len(sorted_counts) * 0.9)
            cost_per_reroll = self.hero_power_config.get_reroll_cost()

            result = HeroPowerSimulationResult(
                iterations=iterations,
                target=SimulationTarget(dps_improvement_pct=target_pct),
                success_rate=successes / iterations if iterations > 0 else 0,
                expected_rerolls=sum(reroll_counts) / len(reroll_counts) if reroll_counts else 0,
                expected_medals=(sum(reroll_counts) / len(reroll_counts) * cost_per_reroll) if reroll_counts else 0,
                median_rerolls=sorted_counts[median_idx] if sorted_counts else 0,
                percentile_90_rerolls=sorted_counts[p90_idx] if sorted_counts else 0,
                reroll_distribution=reroll_counts,
                capped_iterations=sum(1 for c in reroll_counts if c >= max_rerolls),
            )

            self._display_simulation_results(result)

        finally:
            self.hero_sim_btn.config(state=tk.NORMAL, text="Run Simulation (10,000 iterations)")

    def _display_simulation_results(self, result: HeroPowerSimulationResult):
        """Display simulation results in the UI."""
        lines = [
            f"Iterations: {result.iterations:,}",
            f"Success Rate: {result.success_rate * 100:.1f}%",
            "",
            f"Expected Rerolls: {result.expected_rerolls:,.0f}",
            f"Expected Medals: {result.expected_medals:,.0f}",
            "",
            f"Median Rerolls: {result.median_rerolls:,}",
            f"90th Percentile: {result.percentile_90_rerolls:,}",
        ]

        if result.capped_iterations > 0:
            lines.append("")
            lines.append(f"WARNING: {result.capped_iterations} iterations hit max rerolls")
            lines.append("(Target may be unrealistic)")

        self.hero_sim_results_label.config(text="\n".join(lines))

        # Update distribution chart
        if result.reroll_distribution:
            # Create histogram buckets
            distribution = result.reroll_distribution
            max_val = max(distribution)
            min_val = min(distribution)

            if max_val > min_val:
                # Create 5 buckets
                bucket_size = (max_val - min_val) / 5
                buckets = [0] * 5

                for val in distribution:
                    bucket_idx = min(4, int((val - min_val) / bucket_size))
                    buckets[bucket_idx] += 1

                # Format for chart
                chart_data = []
                for i, count in enumerate(buckets):
                    low = int(min_val + i * bucket_size)
                    high = int(min_val + (i + 1) * bucket_size)
                    pct = (count / len(distribution)) * 100
                    chart_data.append((f"{low}-{high}", pct, "#4a9eff"))

                self.hero_sim_chart.update(chart_data)

    # =========================================================================
    # HERO POWER SAVE/LOAD
    # =========================================================================

    def save_hero_power_to_csv(self, filepath: str = None):
        """Save Hero Power configuration to CSV file."""
        if filepath is None:
            filepath = HERO_POWER_SAVE_FILE

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['slot', 'stat_type', 'value', 'tier', 'is_locked', 'preset_name'])

                for line in self.hero_power_config.lines:
                    writer.writerow([
                        line.slot,
                        line.stat_type.value,
                        line.value,
                        line.tier.value,
                        line.is_locked,
                        self.hero_power_config.preset_name
                    ])

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def load_hero_power_from_csv(self, filepath: str = None, silent: bool = False):
        """Load Hero Power configuration from CSV file."""
        if filepath is None:
            filepath = HERO_POWER_SAVE_FILE

        if not os.path.exists(filepath):
            if not silent:
                messagebox.showwarning("Warning", f"File not found: {filepath}")
            return

        try:
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                lines = []
                preset_name = "Default"

                for row in reader:
                    slot = int(row['slot'])
                    stat_type = HeroPowerStatType(row['stat_type'])
                    value = float(row['value'])
                    tier = HeroPowerTier(row['tier'])
                    is_locked = row['is_locked'].lower() == 'true'
                    preset_name = row.get('preset_name', 'Default')

                    lines.append(HeroPowerLine(
                        slot=slot,
                        stat_type=stat_type,
                        value=value,
                        tier=tier,
                        is_locked=is_locked
                    ))

                # Sort by slot and update config
                lines.sort(key=lambda x: x.slot)
                self.hero_power_config = HeroPowerConfig(lines=lines, preset_name=preset_name)

                # Update UI widgets
                self._update_hero_power_widgets_from_config()
                self.update_hero_power_display()

                if not silent:
                    messagebox.showinfo("Success", f"Loaded {len(lines)} Hero Power lines")

        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load: {e}")

    def auto_load_hero_power(self):
        """Automatically load Hero Power from default save file on startup."""
        if os.path.exists(HERO_POWER_SAVE_FILE):
            self.load_hero_power_from_csv(HERO_POWER_SAVE_FILE, silent=True)
        # Load all saved presets
        self.load_all_hero_power_presets(silent=True)
        # Initialize all 10 hero power tabs from loaded presets
        self._initialize_hero_power_tabs()

    # =========================================================================
    # HERO POWER PASSIVE STATS SAVE/LOAD
    # =========================================================================

    def save_hero_power_passive_to_csv(self, filepath: str = None):
        """Save Hero Power passive stats to CSV file."""
        if filepath is None:
            filepath = HERO_POWER_PASSIVE_SAVE_FILE

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['stat_type', 'level'])
                for stat_type in HeroPowerPassiveStatType:
                    level = self.hero_power_passive_config.get_stat_level(stat_type)
                    writer.writerow([stat_type.value, level])
        except Exception as e:
            pass  # Silent fail for auto-save

    def load_hero_power_passive_from_csv(self, filepath: str = None, silent: bool = False):
        """Load Hero Power passive stats from CSV file."""
        if filepath is None:
            filepath = HERO_POWER_PASSIVE_SAVE_FILE

        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stat_type_value = row.get('stat_type', '')
                    level = int(row.get('level', 0))

                    # Find matching stat type
                    for stat_type in HeroPowerPassiveStatType:
                        if stat_type.value == stat_type_value:
                            self.hero_power_passive_config.set_stat_level(stat_type, level)
                            break

            # Update widgets
            self._update_hero_passive_widgets_from_config()

            if not silent:
                messagebox.showinfo("Success", "Hero Power passive stats loaded successfully")
        except FileNotFoundError:
            if not silent:
                messagebox.showwarning("Warning", f"File not found: {filepath}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load: {e}")

    def auto_load_hero_power_passive(self):
        """Automatically load Hero Power passive stats from default save file on startup."""
        if os.path.exists(HERO_POWER_PASSIVE_SAVE_FILE):
            self.load_hero_power_passive_from_csv(HERO_POWER_PASSIVE_SAVE_FILE, silent=True)

    def _update_hero_power_widgets_from_config(self):
        """Update UI widgets to match current config."""
        for line in self.hero_power_config.lines:
            widgets = self.hero_power_line_widgets.get(line.slot)
            if widgets:
                widgets['stat_var'].set(STAT_DISPLAY_NAMES.get(line.stat_type, "Damage %"))
                widgets['value_var'].set(f"{line.value:.1f}")
                widgets['tier_var'].set(line.tier.value.capitalize())
                widgets['lock_var'].set(line.is_locked)

    def export_hero_power_csv(self):
        """Export Hero Power to user-selected CSV file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="hero_power_export.csv"
        )
        if filepath:
            self.save_hero_power_to_csv(filepath)
            messagebox.showinfo("Success", f"Exported to {filepath}")

    def import_hero_power_csv(self):
        """Import Hero Power from user-selected CSV file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv")]
        )
        if filepath:
            self.load_hero_power_from_csv(filepath)

    # =========================================================================
    # HERO POWER PRESETS
    # =========================================================================

    def save_hero_power_preset(self):
        """Save current tab's config. With tabbed interface, this auto-saves the current tab."""
        tab_idx = self.hero_power_current_tab
        preset_name = f"Tab {tab_idx}"

        import copy
        self.hero_power_presets[preset_name] = copy.deepcopy(self.hero_power_config)
        self.hero_power_presets[preset_name].preset_name = preset_name
        self.hero_power_config.preset_name = preset_name

        # Auto-save to default file and presets file
        self.save_hero_power_to_csv()
        self.save_all_hero_power_presets()

        messagebox.showinfo("Success", f"Saved Tab {tab_idx}")

    def load_hero_power_preset(self):
        """Load a saved preset for the current tab. Mainly used internally when switching tabs."""
        tab_idx = self.hero_power_current_tab
        preset_name = f"Tab {tab_idx}"

        if preset_name not in self.hero_power_presets:
            # Create empty preset for this tab
            self.hero_power_presets[preset_name] = HeroPowerConfig(preset_name=preset_name)

        import copy
        self.hero_power_config = copy.deepcopy(self.hero_power_presets[preset_name])
        self._update_hero_power_widgets_from_config()
        self.update_hero_power_display()

    def delete_hero_power_preset(self):
        """Clear the current tab's Hero Power lines (reset to empty)."""
        tab_idx = self.hero_power_current_tab
        preset_name = f"Tab {tab_idx}"

        # Reset this tab to empty config
        self.hero_power_presets[preset_name] = HeroPowerConfig(preset_name=preset_name)
        self.hero_power_config = HeroPowerConfig(preset_name=preset_name)

        # Update widgets
        self._update_hero_power_widgets_from_config()
        self._update_hero_power_tab_widgets_from_preset(tab_idx)
        self.update_hero_power_display()

        # Persist the change
        self.save_all_hero_power_presets()

        messagebox.showinfo("Success", f"Cleared Tab {tab_idx}")

    def save_all_hero_power_presets(self):
        """Save all hero power presets to a single CSV file."""
        try:
            with open(HERO_POWER_PRESETS_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['preset_name', 'slot', 'stat_type', 'value', 'tier', 'is_locked'])

                for preset_name, config in self.hero_power_presets.items():
                    for line in config.lines:
                        writer.writerow([
                            preset_name,
                            line.slot,
                            line.stat_type.value,
                            line.value,
                            line.tier.value,
                            line.is_locked
                        ])
        except Exception as e:
            pass  # Silent fail for auto-save

    def load_all_hero_power_presets(self, silent: bool = True):
        """Load all hero power presets from CSV file."""
        if not os.path.exists(HERO_POWER_PRESETS_FILE):
            return

        try:
            with open(HERO_POWER_PRESETS_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # Group rows by preset name
                presets_data = {}
                for row in reader:
                    preset_name = row['preset_name']
                    if preset_name not in presets_data:
                        presets_data[preset_name] = []

                    presets_data[preset_name].append(HeroPowerLine(
                        slot=int(row['slot']),
                        stat_type=HeroPowerStatType(row['stat_type']),
                        value=float(row['value']),
                        tier=HeroPowerTier(row['tier']),
                        is_locked=row['is_locked'].lower() == 'true'
                    ))

                # Create configs from grouped data
                self.hero_power_presets.clear()
                for preset_name, lines in presets_data.items():
                    lines.sort(key=lambda x: x.slot)
                    self.hero_power_presets[preset_name] = HeroPowerConfig(
                        lines=lines,
                        preset_name=preset_name
                    )

                if not silent:
                    messagebox.showinfo("Success", f"Loaded {len(presets_data)} presets")

        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load presets: {e}")

    # =========================================================================
    # ARTIFACTS TAB
    # =========================================================================

    def build_artifacts_tab(self):
        """Build the Artifacts tab for tracking and calculating artifact effects."""
        # Create scrollable frame
        canvas = tk.Canvas(self.artifacts_tab, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.artifacts_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling when mouse is over this tab
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        main_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Two-column layout
        cols = tk.Frame(main_frame, bg='#1a1a2e')
        cols.pack(fill=tk.BOTH, expand=True, pady=10)

        left_col = tk.Frame(cols, bg='#1a1a2e')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_col = tk.Frame(cols, bg='#1a1a2e')
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # =====================================================================
        # LEFT COLUMN: Equipped Artifacts (3 slots)
        # =====================================================================
        self._section_header(left_col, "Equipped Artifacts (Active Effects)")

        equipped_frame = tk.Frame(left_col, bg='#1a1a2e')
        equipped_frame.pack(fill=tk.X, pady=5)

        for slot_idx in range(3):
            self._build_artifact_slot_editor(equipped_frame, slot_idx)

        # Equipped stats summary
        self._section_header(left_col, "Active Effect Summary")

        self.artifact_active_summary = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        self.artifact_active_summary.pack(fill=tk.X, pady=5, padx=5)

        self.artifact_active_labels = {}
        active_stats = ["Hex Multiplier", "Crit Rate", "Crit Dmg (Book)", "Boss Damage", "Final Damage"]
        for stat in active_stats:
            row = tk.Frame(self.artifact_active_summary, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)
            tk.Label(row, text=f"{stat}:", bg='#252545', fg='#aaa', width=18, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="---", bg='#252545', fg='#7fff7f', font=('Segoe UI', 10, 'bold'))
            lbl.pack(side=tk.LEFT)
            self.artifact_active_labels[stat] = lbl

        # =====================================================================
        # LEFT COLUMN: Artifact Inventory
        # =====================================================================
        self._section_header(left_col, "Artifact Inventory (Awakening Levels)")

        # Scrollable inventory frame
        inv_canvas = tk.Canvas(left_col, bg='#1a1a2e', highlightthickness=0, height=250)
        inv_scrollbar = ttk.Scrollbar(left_col, orient="vertical", command=inv_canvas.yview)
        self.artifact_inv_frame = tk.Frame(inv_canvas, bg='#1a1a2e')

        self.artifact_inv_frame.bind(
            "<Configure>",
            lambda e: inv_canvas.configure(scrollregion=inv_canvas.bbox("all"))
        )

        inv_canvas.create_window((0, 0), window=self.artifact_inv_frame, anchor="nw")
        inv_canvas.configure(yscrollcommand=inv_scrollbar.set)

        inv_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        inv_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Build inventory rows for each artifact type
        self._build_artifact_inventory_list()

        # =====================================================================
        # RIGHT COLUMN: Inventory Effects Summary
        # =====================================================================
        self._section_header(right_col, "Inventory Effects (Always Active)")

        self.artifact_inv_summary = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        self.artifact_inv_summary.pack(fill=tk.X, pady=5, padx=5)

        self.artifact_inv_labels = {}
        inv_stats = [
            ("Attack Flat", "attack_flat"),
            ("Damage %", "damage"),
            ("Boss Damage %", "boss_damage"),
            ("Normal Damage %", "normal_damage"),
            ("Crit Damage %", "crit_damage"),
            ("Def Pen %", "def_pen"),
            ("Max Dmg Mult %", "max_damage_mult"),
        ]
        for display_name, stat_key in inv_stats:
            row = tk.Frame(self.artifact_inv_summary, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)
            tk.Label(row, text=f"{display_name}:", bg='#252545', fg='#aaa', width=18, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="---", bg='#252545', fg='#7fff7f', font=('Segoe UI', 10, 'bold'))
            lbl.pack(side=tk.LEFT)
            self.artifact_inv_labels[stat_key] = lbl

        # Resonance display (editable)
        self._section_header(right_col, "Resonance (Editable)")

        res_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        res_frame.pack(fill=tk.X, pady=5, padx=5)

        # Total Stars (editable) - uses vars initialized in __init__
        row = tk.Frame(res_frame, bg='#252545')
        row.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(row, text="Total Stars:", bg='#252545', fg='#aaa', width=16, anchor='w').pack(side=tk.LEFT)
        stars_entry = tk.Entry(row, textvariable=self.resonance_stars_var, width=8, bg='#333', fg='#ffd700',
                              insertbackground='#fff', font=('Segoe UI', 10, 'bold'))
        stars_entry.pack(side=tk.LEFT, padx=2)
        stars_entry.bind('<FocusOut>', self._on_resonance_change)
        stars_entry.bind('<Return>', self._on_resonance_change)
        self.artifact_resonance_label = tk.Label(row, text="", bg='#252545', fg='#888', font=('Segoe UI', 9))
        self.artifact_resonance_label.pack(side=tk.LEFT, padx=5)

        # Main Stat Bonus (editable)
        row2 = tk.Frame(res_frame, bg='#252545')
        row2.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(row2, text="Main Stat Bonus:", bg='#252545', fg='#aaa', width=16, anchor='w').pack(side=tk.LEFT)
        main_stat_entry = tk.Entry(row2, textvariable=self.resonance_main_stat_var, width=8, bg='#333', fg='#7fff7f',
                                   insertbackground='#fff', font=('Segoe UI', 10, 'bold'))
        main_stat_entry.pack(side=tk.LEFT, padx=2)
        main_stat_entry.bind('<FocusOut>', self._on_resonance_change)
        main_stat_entry.bind('<Return>', self._on_resonance_change)
        self.artifact_res_main_stat = tk.Label(row2, text="", bg='#252545', fg='#888', font=('Segoe UI', 9))
        self.artifact_res_main_stat.pack(side=tk.LEFT, padx=5)

        # HP Bonus (editable)
        row3 = tk.Frame(res_frame, bg='#252545')
        row3.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(row3, text="HP Bonus:", bg='#252545', fg='#aaa', width=16, anchor='w').pack(side=tk.LEFT)
        hp_entry = tk.Entry(row3, textvariable=self.resonance_hp_var, width=8, bg='#333', fg='#ff7f7f',
                           insertbackground='#fff', font=('Segoe UI', 10, 'bold'))
        hp_entry.pack(side=tk.LEFT, padx=2)
        hp_entry.bind('<FocusOut>', self._on_resonance_change)
        hp_entry.bind('<Return>', self._on_resonance_change)
        self.artifact_res_hp = tk.Label(row3, text="", bg='#252545', fg='#888', font=('Segoe UI', 9))
        self.artifact_res_hp.pack(side=tk.LEFT, padx=5)

        # Resonance Level (for reference) - uses var initialized in __init__
        row4 = tk.Frame(res_frame, bg='#252545')
        row4.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(row4, text="Resonance Level:", bg='#252545', fg='#aaa', width=16, anchor='w').pack(side=tk.LEFT)
        level_entry = tk.Entry(row4, textvariable=self.resonance_level_var, width=8, bg='#333', fg='#aaf',
                              insertbackground='#fff', font=('Segoe UI', 10))
        level_entry.pack(side=tk.LEFT, padx=2)
        tk.Label(row4, text="/ 440", bg='#252545', fg='#888').pack(side=tk.LEFT)

        # =====================================================================
        # RIGHT COLUMN: Artifact Cost Calculator
        # =====================================================================
        self._section_header(right_col, "Artifact Cost Calculator")

        cost_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        cost_frame.pack(fill=tk.X, pady=5, padx=5)

        # Artifact selector for cost calculation
        cost_sel_row = tk.Frame(cost_frame, bg='#252545')
        cost_sel_row.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(cost_sel_row, text="Artifact:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)

        # Build list with tier info
        cost_artifact_names = []
        for k, v in ARTIFACTS.items():
            tier_label = v.tier.value.capitalize()
            cost_artifact_names.append(f"{v.name} ({tier_label})")

        self.artifact_cost_selector = ttk.Combobox(cost_sel_row, values=cost_artifact_names, width=30, state='readonly')
        self.artifact_cost_selector.pack(side=tk.LEFT, padx=5)
        self.artifact_cost_selector.bind('<<ComboboxSelected>>', self._on_artifact_cost_select)

        # Current/Target stars row
        stars_row = tk.Frame(cost_frame, bg='#252545')
        stars_row.pack(fill=tk.X, padx=5, pady=3)

        tk.Label(stars_row, text="Current ★:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.artifact_cost_current_stars = ttk.Combobox(stars_row, values=list(range(6)), width=3, state='readonly')
        self.artifact_cost_current_stars.set("0")
        self.artifact_cost_current_stars.pack(side=tk.LEFT, padx=2)
        self.artifact_cost_current_stars.bind('<<ComboboxSelected>>', self._update_artifact_cost_display)

        tk.Label(stars_row, text="  Target ★:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.artifact_cost_target_stars = ttk.Combobox(stars_row, values=list(range(6)), width=3, state='readonly')
        self.artifact_cost_target_stars.set("5")
        self.artifact_cost_target_stars.pack(side=tk.LEFT, padx=2)
        self.artifact_cost_target_stars.bind('<<ComboboxSelected>>', self._update_artifact_cost_display)

        # Calculate button
        tk.Button(cost_frame, text="Calculate Cost", command=self._update_artifact_cost_display,
                  bg='#4a7c4a', fg='white', font=('Segoe UI', 9)).pack(pady=5)

        # Cost results display
        self.artifact_cost_results = tk.Frame(cost_frame, bg='#252545')
        self.artifact_cost_results.pack(fill=tk.X, padx=5, pady=5)

        self.artifact_cost_labels = {}
        cost_display_items = [
            ("Drop Rate", "drop_rate"),
            ("Duplicates Needed", "dupes_needed"),
            ("Expected Chests", "expected_chests"),
            ("Blue Diamonds", "blue_diamonds"),
            ("Effect Gain", "effect_gain"),
        ]
        for display_name, key in cost_display_items:
            row = tk.Frame(self.artifact_cost_results, bg='#252545')
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=f"{display_name}:", bg='#252545', fg='#aaa', width=16, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="---", bg='#252545', fg='#7fff7f', font=('Segoe UI', 9))
            lbl.pack(side=tk.LEFT)
            self.artifact_cost_labels[key] = lbl

        # Synthesis comparison (for legendaries)
        self._section_header(right_col, "Synthesis vs Direct Drop")

        synth_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        synth_frame.pack(fill=tk.X, pady=5, padx=5)

        self.artifact_synth_labels = {}
        synth_items = [
            ("Direct Drop Chests", "direct_chests"),
            ("Direct Drop Diamonds", "direct_diamonds"),
            ("Synthesis Chests", "synth_chests"),
            ("Synthesis Diamonds", "synth_diamonds"),
            ("Recommendation", "recommendation"),
        ]
        for display_name, key in synth_items:
            row = tk.Frame(synth_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=1)
            tk.Label(row, text=f"{display_name}:", bg='#252545', fg='#aaa', width=18, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="---", bg='#252545', fg='#ffaa00', font=('Segoe UI', 9))
            lbl.pack(side=tk.LEFT)
            self.artifact_synth_labels[key] = lbl

        # =====================================================================
        # RIGHT COLUMN: Artifact Potentials (for selected artifact)
        # =====================================================================
        self._section_header(right_col, "Artifact Potentials")

        pot_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        pot_frame.pack(fill=tk.X, pady=5, padx=5)

        # Artifact selector for potentials
        sel_row = tk.Frame(pot_frame, bg='#252545')
        sel_row.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(sel_row, text="Artifact:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)

        artifact_names = [ARTIFACTS[k].name for k in ARTIFACTS.keys()]
        self.artifact_potential_selector = ttk.Combobox(sel_row, values=artifact_names, width=25, state='readonly')
        self.artifact_potential_selector.pack(side=tk.LEFT, padx=5)
        self.artifact_potential_selector.bind('<<ComboboxSelected>>', self._on_artifact_potential_select)

        # Potential line editors (up to 3)
        self.artifact_potential_lines = []
        for i in range(3):
            line_frame = tk.Frame(pot_frame, bg='#252545')
            line_frame.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(line_frame, text=f"Slot {i+1}:", bg='#252545', fg='#aaa', width=6).pack(side=tk.LEFT)

            stat_var = tk.StringVar(value="---")
            stat_cb = ttk.Combobox(line_frame, textvariable=stat_var, width=12, state='readonly',
                                   values=["---", "main_stat", "damage", "boss_damage", "normal_damage",
                                          "def_pen", "crit_rate", "min_max_damage"])
            stat_cb.pack(side=tk.LEFT, padx=2)

            value_var = tk.StringVar(value="0")
            value_entry = tk.Entry(line_frame, textvariable=value_var, width=6, bg='#333', fg='#fff',
                                   insertbackground='#fff')
            value_entry.pack(side=tk.LEFT, padx=2)
            tk.Label(line_frame, text="%", bg='#252545', fg='#aaa').pack(side=tk.LEFT)

            tier_var = tk.StringVar(value="legendary")
            tier_cb = ttk.Combobox(line_frame, textvariable=tier_var, width=10, state='readonly',
                                   values=["rare", "epic", "unique", "legendary", "mystic"])
            tier_cb.pack(side=tk.LEFT, padx=2)

            self.artifact_potential_lines.append({
                'frame': line_frame,
                'stat_var': stat_var,
                'value_var': value_var,
                'tier_var': tier_var,
                'stat_cb': stat_cb,
                'value_entry': value_entry,
                'tier_cb': tier_cb,
            })

        # Apply potentials button
        tk.Button(pot_frame, text="Apply Potentials", command=self._apply_artifact_potentials,
                  bg='#4a7c4a', fg='white', font=('Segoe UI', 9)).pack(pady=5)

        # =====================================================================
        # BOTTOM: Save/Load buttons
        # =====================================================================
        btn_frame = tk.Frame(main_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=10)

        tk.Button(btn_frame, text="Export Artifacts", command=self.export_artifacts_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Import Artifacts", command=self.import_artifacts_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Update Stats", command=self._update_artifact_displays,
                  bg='#7a4a4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

    def _build_artifact_slot_editor(self, parent, slot_idx: int):
        """Build editor for one equipped artifact slot."""
        frame = tk.Frame(parent, bg='#252545', relief='ridge', bd=1)
        frame.pack(fill=tk.X, pady=3, padx=5)

        # Slot label
        tk.Label(frame, text=f"Slot {slot_idx + 1}:", bg='#252545', fg='#ffd700',
                font=('Segoe UI', 9, 'bold'), width=8).pack(side=tk.LEFT, padx=5)

        # Artifact selector
        artifact_names = ["(Empty)"] + [ARTIFACTS[k].name for k in ARTIFACTS.keys()]
        artifact_var = tk.StringVar(value="(Empty)")
        artifact_cb = ttk.Combobox(frame, textvariable=artifact_var, values=artifact_names,
                                   width=22, state='readonly')
        artifact_cb.pack(side=tk.LEFT, padx=5)
        artifact_cb.bind('<<ComboboxSelected>>', lambda e, s=slot_idx: self._on_equipped_artifact_change(s))

        # Stars display (read from inventory)
        tk.Label(frame, text="Stars:", bg='#252545', fg='#aaa').pack(side=tk.LEFT, padx=(10, 2))
        stars_label = tk.Label(frame, text="0", bg='#252545', fg='#7fff7f', font=('Segoe UI', 9, 'bold'))
        stars_label.pack(side=tk.LEFT)

        # Effect preview
        effect_label = tk.Label(frame, text="", bg='#252545', fg='#aaa', font=('Segoe UI', 8))
        effect_label.pack(side=tk.LEFT, padx=10)

        self.artifact_slot_widgets[slot_idx] = {
            'artifact_var': artifact_var,
            'artifact_cb': artifact_cb,
            'stars_label': stars_label,
            'effect_label': effect_label,
        }

    def _build_artifact_inventory_list(self):
        """Build the list of all artifacts with awakening level selectors."""
        # Group by tier
        legendary = [(k, v) for k, v in ARTIFACTS.items() if v.tier == ArtifactTier.LEGENDARY]
        unique = [(k, v) for k, v in ARTIFACTS.items() if v.tier == ArtifactTier.UNIQUE]
        epic = [(k, v) for k, v in ARTIFACTS.items() if v.tier == ArtifactTier.EPIC]

        tier_colors = {
            ArtifactTier.LEGENDARY: '#7fff7f',
            ArtifactTier.UNIQUE: '#ffaa00',
            ArtifactTier.EPIC: '#aa77ff',
        }

        for tier_name, artifacts in [("Legendary", legendary), ("Unique", unique), ("Epic", epic)]:
            if not artifacts:
                continue

            # Tier header
            header = tk.Label(self.artifact_inv_frame, text=f"── {tier_name} ──",
                            bg='#1a1a2e', fg='#888', font=('Segoe UI', 9, 'bold'))
            header.pack(fill=tk.X, pady=(5, 2))

            for key, definition in artifacts:
                row = tk.Frame(self.artifact_inv_frame, bg='#202040')
                row.pack(fill=tk.X, pady=1, padx=5)

                # Artifact name
                name_color = tier_colors.get(definition.tier, '#fff')
                tk.Label(row, text=definition.name, bg='#202040', fg=name_color,
                        font=('Segoe UI', 9), width=24, anchor='w').pack(side=tk.LEFT, padx=5)

                # Stars selector
                tk.Label(row, text="★", bg='#202040', fg='#ffd700').pack(side=tk.LEFT)
                stars_var = tk.StringVar(value="0")
                stars_cb = ttk.Combobox(row, textvariable=stars_var, values=list(range(6)),
                                        width=3, state='readonly')
                stars_cb.pack(side=tk.LEFT, padx=2)
                stars_cb.bind('<<ComboboxSelected>>', lambda e, k=key: self._on_artifact_stars_change(k))

                # Potentials button
                pot_btn = tk.Button(row, text="Pot", command=lambda k=key: self._open_artifact_potential_editor(k),
                                   bg='#4a4a6a', fg='white', font=('Segoe UI', 8), width=3)
                pot_btn.pack(side=tk.LEFT, padx=2)

                # Potentials summary label
                pot_summary = tk.Label(row, text="", bg='#202040', fg='#aaf', font=('Segoe UI', 8))
                pot_summary.pack(side=tk.LEFT, padx=2)

                # Inventory effect preview
                inv_effect = tk.Label(row, text="", bg='#202040', fg='#888', font=('Segoe UI', 8))
                inv_effect.pack(side=tk.LEFT, padx=10)

                self.artifact_inventory_widgets[key] = {
                    'stars_var': stars_var,
                    'stars_cb': stars_cb,
                    'pot_btn': pot_btn,
                    'pot_summary': pot_summary,
                    'inv_effect_label': inv_effect,
                    'definition': definition,
                }

                # Initialize effect display
                self._update_artifact_inv_effect(key)

    def _on_artifact_stars_change(self, artifact_key: str):
        """Called when an artifact's awakening level changes."""
        widgets = self.artifact_inventory_widgets.get(artifact_key)
        if not widgets:
            return

        stars = int(widgets['stars_var'].get())
        definition = widgets['definition']

        # Update or create artifact instance in config
        existing = None
        for i, art in enumerate(self.artifact_config.inventory):
            if art.definition.name == definition.name:
                existing = i
                break

        if existing is not None:
            if stars == 0:
                # Remove from inventory
                self.artifact_config.inventory.pop(existing)
            else:
                self.artifact_config.inventory[existing].awakening_stars = stars
        else:
            if stars > 0:
                instance = ArtifactInstance(definition=definition, awakening_stars=stars)
                self.artifact_config.inventory.append(instance)

        self._update_artifact_inv_effect(artifact_key)
        self._update_artifact_displays()

    def _update_artifact_inv_effect(self, artifact_key: str):
        """Update the inventory effect preview for an artifact."""
        widgets = self.artifact_inventory_widgets.get(artifact_key)
        if not widgets:
            return

        stars = int(widgets['stars_var'].get())
        definition = widgets['definition']

        if stars == 0:
            widgets['inv_effect_label'].config(text="(not owned)")
            widgets['pot_summary'].config(text="")
        else:
            inv_value = definition.get_inventory_value(stars)
            stat = definition.inventory_stat
            if stat == "attack_flat":
                widgets['inv_effect_label'].config(text=f"Inv: +{inv_value:.0f} ATK")
            elif "damage" in stat or stat == "def_pen" or stat == "crit" in stat:
                widgets['inv_effect_label'].config(text=f"Inv: +{inv_value*100:.1f}%")
            else:
                widgets['inv_effect_label'].config(text=f"Inv: +{inv_value*100:.1f}%")

            # Update potentials summary
            self._update_artifact_pot_summary(artifact_key)

    def _update_artifact_pot_summary(self, artifact_key: str):
        """Update the potentials summary label for an artifact."""
        widgets = self.artifact_inventory_widgets.get(artifact_key)
        if not widgets:
            return

        # Find the artifact instance
        definition = widgets['definition']
        instance = None
        for art in self.artifact_config.inventory:
            if art.definition.name == definition.name:
                instance = art
                break

        if not instance or not instance.potentials:
            widgets['pot_summary'].config(text="")
            return

        # Build summary: show active potentials based on stars
        slots_unlocked = POTENTIAL_SLOT_UNLOCKS.get(instance.awakening_stars, 0)
        if definition.tier != ArtifactTier.LEGENDARY and slots_unlocked > 2:
            slots_unlocked = 2

        active_pots = instance.potentials[:slots_unlocked]
        if not active_pots:
            widgets['pot_summary'].config(text="")
            return

        # Compact summary
        summary_parts = []
        for pot in active_pots:
            stat_abbrev = {
                "main_stat": "MS",
                "damage": "Dmg",
                "boss_damage": "Boss",
                "normal_damage": "Norm",
                "def_pen": "Pen",
                "crit_rate": "CR",
                "crit_damage": "CD",
                "min_max_damage": "MM",
            }.get(pot.stat, pot.stat[:3])
            summary_parts.append(f"{stat_abbrev}:{pot.value:.0f}%")

        widgets['pot_summary'].config(text=" ".join(summary_parts))

    def _open_artifact_potential_editor(self, artifact_key: str):
        """Open a dialog to edit artifact potentials."""
        widgets = self.artifact_inventory_widgets.get(artifact_key)
        if not widgets:
            return

        definition = widgets['definition']
        stars = int(widgets['stars_var'].get())

        # Find or create artifact instance
        instance = None
        for art in self.artifact_config.inventory:
            if art.definition.name == definition.name:
                instance = art
                break

        if not instance:
            if stars == 0:
                messagebox.showinfo("Info", "Set awakening stars first to add potentials.")
                return
            # Create new instance
            instance = ArtifactInstance(definition=definition, awakening_stars=stars)
            self.artifact_config.inventory.append(instance)

        # Calculate unlocked slots
        slots_unlocked = POTENTIAL_SLOT_UNLOCKS.get(stars, 0)
        if definition.tier != ArtifactTier.LEGENDARY and slots_unlocked > 2:
            slots_unlocked = 2

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Potentials - {definition.name}")
        dialog.geometry("450x350")
        dialog.configure(bg='#1a1a2e')
        dialog.transient(self.root)
        dialog.grab_set()

        # Header
        header = tk.Label(dialog, text=f"{definition.name} - ★{stars}",
                         font=('Segoe UI', 12, 'bold'), bg='#1a1a2e', fg='#ffd700')
        header.pack(pady=10)

        # Slot unlock info
        unlock_text = f"Slots unlocked: {slots_unlocked}/3  (★1=1, ★3=2, ★5=3)"
        if definition.tier != ArtifactTier.LEGENDARY:
            unlock_text += " [Max 2 for non-Legendary]"
        info_lbl = tk.Label(dialog, text=unlock_text, bg='#1a1a2e', fg='#888', font=('Segoe UI', 9))
        info_lbl.pack(pady=5)

        # Potential stat options
        pot_stat_options = ["", "main_stat", "damage", "boss_damage", "normal_damage",
                           "def_pen", "crit_rate", "crit_damage", "min_max_damage"]
        pot_tier_options = ["", "rare", "epic", "unique", "legendary", "mystic"]

        # Store entry variables
        pot_vars = []

        # Create slot editors
        slots_frame = tk.Frame(dialog, bg='#1a1a2e')
        slots_frame.pack(pady=10, padx=20, fill=tk.X)

        for slot_idx in range(3):
            slot_frame = tk.Frame(slots_frame, bg='#252545', relief='ridge', bd=1)
            slot_frame.pack(fill=tk.X, pady=5, padx=5)

            # Slot header
            slot_unlocked = slot_idx < slots_unlocked
            unlock_star = {0: 1, 1: 3, 2: 5}.get(slot_idx, 5)
            header_text = f"Slot {slot_idx + 1}"
            if not slot_unlocked:
                header_text += f" (Unlocks at ★{unlock_star})"
            header_color = '#7fff7f' if slot_unlocked else '#666'

            tk.Label(slot_frame, text=header_text, bg='#252545', fg=header_color,
                    font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=5, pady=2)

            # Get existing potential for this slot
            existing_pot = None
            if slot_idx < len(instance.potentials):
                existing_pot = instance.potentials[slot_idx]

            # Row for inputs
            input_row = tk.Frame(slot_frame, bg='#252545')
            input_row.pack(fill=tk.X, padx=5, pady=5)

            # Stat selector
            tk.Label(input_row, text="Stat:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
            stat_var = tk.StringVar(value=existing_pot.stat if existing_pot else "")
            stat_cb = ttk.Combobox(input_row, textvariable=stat_var, values=pot_stat_options,
                                   width=14, state='readonly' if slot_unlocked else 'disabled')
            stat_cb.pack(side=tk.LEFT, padx=5)

            # Value entry
            tk.Label(input_row, text="Value:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
            value_var = tk.StringVar(value=str(existing_pot.value) if existing_pot else "0")
            value_entry = tk.Entry(input_row, textvariable=value_var, width=6,
                                   bg='#333' if slot_unlocked else '#222',
                                   fg='#fff', state='normal' if slot_unlocked else 'disabled')
            value_entry.pack(side=tk.LEFT, padx=5)
            tk.Label(input_row, text="%", bg='#252545', fg='#aaa').pack(side=tk.LEFT)

            # Tier selector
            tk.Label(input_row, text="Tier:", bg='#252545', fg='#aaa').pack(side=tk.LEFT, padx=(10, 0))
            tier_var = tk.StringVar(value=existing_pot.tier.value if existing_pot else "")
            tier_cb = ttk.Combobox(input_row, textvariable=tier_var, values=pot_tier_options,
                                   width=10, state='readonly' if slot_unlocked else 'disabled')
            tier_cb.pack(side=tk.LEFT, padx=5)

            pot_vars.append({
                'stat': stat_var,
                'value': value_var,
                'tier': tier_var,
                'unlocked': slot_unlocked,
            })

        # Buttons
        btn_frame = tk.Frame(dialog, bg='#1a1a2e')
        btn_frame.pack(pady=20)

        def save_potentials():
            # Clear existing potentials
            instance.potentials = []

            for slot_idx, vars in enumerate(pot_vars):
                if not vars['unlocked']:
                    continue

                stat = vars['stat'].get()
                tier_str = vars['tier'].get()
                try:
                    value = float(vars['value'].get())
                except ValueError:
                    value = 0

                if stat and tier_str and value > 0:
                    try:
                        tier = ArtifactPotentialTier[tier_str.upper()]
                        instance.potentials.append(ArtifactPotentialLine(
                            stat=stat, value=value, tier=tier, slot=slot_idx + 1
                        ))
                    except KeyError:
                        pass

            # Update displays
            self._update_artifact_pot_summary(artifact_key)
            self._update_artifact_displays()
            self.save_artifacts_to_csv(silent=True)
            dialog.destroy()

        def clear_potentials():
            for vars in pot_vars:
                vars['stat'].set("")
                vars['value'].set("0")
                vars['tier'].set("")

        tk.Button(btn_frame, text="Save", command=save_potentials,
                 bg='#4a7c4a', fg='white', font=('Segoe UI', 10), width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Clear", command=clear_potentials,
                 bg='#7c4a4a', fg='white', font=('Segoe UI', 10), width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                 bg='#4a4a6a', fg='white', font=('Segoe UI', 10), width=10).pack(side=tk.LEFT, padx=10)

    def _on_equipped_artifact_change(self, slot_idx: int):
        """Called when an equipped artifact slot selection changes."""
        widgets = self.artifact_slot_widgets.get(slot_idx)
        if not widgets:
            return

        artifact_name = widgets['artifact_var'].get()

        if artifact_name == "(Empty)":
            self.artifact_config.equipped[slot_idx] = None
            widgets['stars_label'].config(text="0")
            widgets['effect_label'].config(text="")
        else:
            # Find the artifact definition and instance
            definition = None
            for key, defn in ARTIFACTS.items():
                if defn.name == artifact_name:
                    definition = defn
                    break

            if definition:
                # Find if we have it in inventory
                instance = None
                for art in self.artifact_config.inventory:
                    if art.definition.name == artifact_name:
                        instance = art
                        break

                if instance is None:
                    # Create new instance with 0 stars
                    instance = ArtifactInstance(definition=definition, awakening_stars=0)

                self.artifact_config.equipped[slot_idx] = instance
                widgets['stars_label'].config(text=str(instance.awakening_stars))

                # Show effect preview
                effect_val = instance.get_active_value()
                if definition.active_stat == "hex_damage_per_stack":
                    mult = calculate_hex_multiplier(instance.awakening_stars, 3)
                    widgets['effect_label'].config(text=f"×{mult:.2f} (3 stacks)")
                elif definition.active_stat == "crit_rate":
                    cr, cd = calculate_book_of_ancient_bonus(instance.awakening_stars, 1.0)
                    widgets['effect_label'].config(text=f"+{cr*100:.0f}% CR")
                else:
                    widgets['effect_label'].config(text=f"+{effect_val*100:.1f}%")

        self._update_artifact_displays()

    def _on_artifact_potential_select(self, event=None):
        """Called when user selects an artifact to edit potentials."""
        artifact_name = self.artifact_potential_selector.get()

        # Find the instance
        instance = None
        for art in self.artifact_config.inventory:
            if art.definition.name == artifact_name:
                instance = art
                break

        # Update potential line editors
        for i, line_widgets in enumerate(self.artifact_potential_lines):
            if instance and i < len(instance.potentials):
                pot = instance.potentials[i]
                line_widgets['stat_var'].set(pot.stat)
                line_widgets['value_var'].set(f"{pot.value:.1f}")
                line_widgets['tier_var'].set(pot.tier.value)
            else:
                line_widgets['stat_var'].set("---")
                line_widgets['value_var'].set("0")
                line_widgets['tier_var'].set("legendary")

            # Enable/disable based on available slots
            if instance:
                available_slots = instance.potential_slots
                state = 'readonly' if i < available_slots else 'disabled'
                line_widgets['stat_cb'].config(state=state)
                line_widgets['tier_cb'].config(state=state)
                line_widgets['value_entry'].config(state='normal' if i < available_slots else 'disabled')
            else:
                line_widgets['stat_cb'].config(state='disabled')
                line_widgets['tier_cb'].config(state='disabled')
                line_widgets['value_entry'].config(state='disabled')

    def _apply_artifact_potentials(self):
        """Apply the edited potentials to the selected artifact."""
        artifact_name = self.artifact_potential_selector.get()
        if not artifact_name:
            return

        # Find the instance
        instance = None
        for art in self.artifact_config.inventory:
            if art.definition.name == artifact_name:
                instance = art
                break

        if not instance:
            messagebox.showwarning("Warning", "Artifact not found in inventory. Add awakening stars first.")
            return

        # Update potentials
        instance.potentials = []
        for i, line_widgets in enumerate(self.artifact_potential_lines):
            if i >= instance.potential_slots:
                break

            stat = line_widgets['stat_var'].get()
            if stat == "---":
                continue

            try:
                value = float(line_widgets['value_var'].get())
            except ValueError:
                value = 0

            tier_str = line_widgets['tier_var'].get()
            tier = ArtifactPotentialTier[tier_str.upper()]

            instance.potentials.append(ArtifactPotentialLine(
                stat=stat, value=value, tier=tier, slot=i+1
            ))

        self._update_artifact_displays()
        messagebox.showinfo("Success", f"Updated potentials for {artifact_name}")

    def _update_artifact_displays(self):
        """Update all artifact stat displays."""
        # Update equipped slot stars display
        for slot_idx, widgets in self.artifact_slot_widgets.items():
            artifact = self.artifact_config.equipped[slot_idx]
            if artifact:
                widgets['stars_label'].config(text=str(artifact.awakening_stars))

        # Update active effects summary
        all_stats = self.artifact_config.get_all_stats()

        # Hex multiplier (special calculation)
        hex_equipped = None
        for art in self.artifact_config.equipped:
            if art and art.definition.name == "Hexagon Necklace":
                hex_equipped = art
                break

        if hex_equipped:
            mult = calculate_hex_multiplier(hex_equipped.awakening_stars, 3)
            self.artifact_active_labels["Hex Multiplier"].config(text=f"×{mult:.2f}")
        else:
            self.artifact_active_labels["Hex Multiplier"].config(text="---")

        # Book of Ancient (special calculation)
        book_equipped = None
        for art in self.artifact_config.equipped:
            if art and art.definition.name == "Book of Ancient":
                book_equipped = art
                break

        if book_equipped:
            # Use actual total crit rate for conversion (can exceed 100%)
            total_cr = self._get_total_crit_rate_for_book()
            cr_bonus, cd_bonus = calculate_book_of_ancient_bonus(book_equipped.awakening_stars, total_cr)
            self.artifact_active_labels["Crit Rate"].config(text=f"+{cr_bonus*100:.0f}%")
            self.artifact_active_labels["Crit Dmg (Book)"].config(text=f"+{cd_bonus*100:.1f}% (from {total_cr*100:.1f}% CR)")
        else:
            self.artifact_active_labels["Crit Rate"].config(text="---")
            self.artifact_active_labels["Crit Dmg (Book)"].config(text="---")

        # Boss damage from Star Rock
        boss_dmg = all_stats.get("boss_damage", 0)
        self.artifact_active_labels["Boss Damage"].config(text=f"+{boss_dmg*100:.1f}%" if boss_dmg else "---")

        # Final damage (sum from various sources)
        fd_keys = ["final_damage_conditional", "final_damage_world_boss", "final_damage_guild", "final_damage_growth"]
        total_fd = sum(all_stats.get(k, 0) for k in fd_keys)
        self.artifact_active_labels["Final Damage"].config(text=f"+{total_fd*100:.1f}%" if total_fd else "---")

        # Update inventory effects summary
        inv_stats = self.artifact_config.get_inventory_stats()

        for stat_key, label in self.artifact_inv_labels.items():
            value = inv_stats.get(stat_key, 0)
            if stat_key == "attack_flat":
                label.config(text=f"+{value:.0f}" if value else "---")
            else:
                label.config(text=f"+{value*100:.1f}%" if value else "---")

        # Update resonance - show calculated values as hints (don't overwrite user input)
        calculated_stars = self.artifact_config.get_resonance()
        calculated_bonus = self.artifact_config.get_resonance_bonus()
        self.artifact_resonance_label.config(text=f"(calc: ★{calculated_stars})")
        self.artifact_res_main_stat.config(text=f"(calc: +{calculated_bonus.get('main_stat_flat', 0):.0f})")
        self.artifact_res_hp.config(text=f"(calc: +{calculated_bonus.get('max_hp_flat', 0):.0f})")

        # Auto-save artifacts
        self.save_artifacts_to_csv(silent=True)

        # Update damage
        self.update_damage()

    def _get_total_crit_rate_for_book(self) -> float:
        """
        Calculate total crit rate from all sources for Book of Ancient conversion.

        This is used to calculate how much crit damage the Book of Ancient provides
        based on converting crit rate to crit damage. Crit rate can exceed 100%.

        Returns crit rate as a decimal (e.g., 1.289 for 128.9%)
        """
        # Get crit rate from all sources
        pot = self.get_potential_stats_total()
        equip_base = self.get_equipment_base_stats_total()
        companion = self.get_companion_stats_total()
        passive = self.get_passive_stats_total()
        maple_rank = self.get_maple_rank_stats_total()

        # Sum all crit rate sources (all in percent form)
        pot_cr = pot.get("crit_rate", 0)  # From potentials
        equip_cr = equip_base.get("crit_rate", 0)  # From equipment sub stats
        comp_cr = companion.get("crit_rate", 0)  # From companion on-equip
        passive_cr = passive.get("crit_rate", 0)  # From critical_shot + mastery
        mr_cr = maple_rank.get("crit_rate", 0)  # From Maple Rank

        # Base crit rate from sliders (if any)
        try:
            base_cr = self._get_damage_slider("crit_rate") if hasattr(self, '_sliders_ready') and self._sliders_ready else 0
        except (ValueError, AttributeError, KeyError):
            base_cr = 0

        # Total crit rate in percent
        total_cr_percent = base_cr + pot_cr + equip_cr + comp_cr + passive_cr + mr_cr

        # Book of Ancient's active CR bonus is included when equipped
        book_cr_bonus = 0
        for art in self.artifact_config.equipped:
            if art and art.definition.name == "Book of Ancient":
                book_cr_bonus = art.definition.get_active_value(art.awakening_stars) * 100
                break

        # Return as decimal (including Book's CR bonus for the conversion)
        return (total_cr_percent + book_cr_bonus) / 100

    def get_artifact_stats_total(self) -> Dict[str, float]:
        """Get total stats contribution from artifacts for damage calculation.

        Uses manual resonance values from UI instead of auto-calculated values.
        Includes Book of Ancient's crit damage conversion based on total crit rate.
        """
        # Get base stats (active + inventory effects)
        stats = {}

        # Active effects from equipped
        for key, value in self.artifact_config.get_equipped_active_stats().items():
            stats[key] = stats.get(key, 0) + value

        # Inventory effects from all
        for key, value in self.artifact_config.get_inventory_stats().items():
            stats[key] = stats.get(key, 0) + value

        # Use manual resonance values instead of auto-calculated
        resonance_stats = self.get_resonance_stats()
        for key, value in resonance_stats.items():
            stats[key] = stats.get(key, 0) + value

        # Special handling: Book of Ancient crit damage conversion
        # Book converts crit rate to crit damage based on conversion rate
        # Crit rate CAN exceed 100%!
        for art in self.artifact_config.equipped:
            if art and art.definition.name == "Book of Ancient":
                # Get total crit rate for conversion (can exceed 100%)
                total_cr = self._get_total_crit_rate_for_book()
                # Calculate CD bonus: conversion_rate × total_crit_rate
                _, cd_bonus = calculate_book_of_ancient_bonus(art.awakening_stars, total_cr)
                # Add to crit_damage (as decimal to match other stats)
                stats["crit_damage"] = stats.get("crit_damage", 0) + cd_bonus
                break

        return stats

    def get_guild_stats_total(self) -> Dict[str, float]:
        """Get total stats contribution from guild skills for damage calculation."""
        return self.guild_config.get_all_stats()

    def get_companion_stats_total(self) -> Dict[str, float]:
        """Get total stats contribution from companions for damage calculation."""
        return self.companion_config.get_all_stats()

    def get_passive_stats_total(self) -> Dict[str, float]:
        """
        Get passive stat bonuses from skills.py (replaces passives.py).

        This extracts:
        1. Global mastery stats (fixed per level, don't scale with +All Skills)
        2. PASSIVE_STAT skill contributions (scale with skill levels)

        Stats returned:
        - crit_rate: from critical_shot + mastery
        - attack_speed: from archer_mastery + bow_acceleration + mastery
        - min_dmg_mult: from bow_mastery
        - dex_flat: from soul_arrow + mastery
        - basic_attack_damage: from physical_training + mastery
        - final_damage: from extreme_archery + armor_break
        - attack_pct: from marksmanship + illusion_step
        - skill_damage: from bow_expert + mastery
        - def_pen: from armor_break
        - max_dmg_mult: from mastery
        - accuracy: from mastery
        """
        level = self.character_level

        # Get total All Skills from all sources:
        # 1. Base All Skills (from slider - equipment/other sources)
        # 2. All Skills from potentials
        # 3. All Skills from equipment sub stats
        base_all_skills = self.current_all_skills
        pot_all_skills = self.get_potential_stats_total().get("all_skills", 0)
        equip_all_skills = self.get_equipment_base_stats_total().get("all_skills", 0)
        all_skills = int(base_all_skills + pot_all_skills + equip_all_skills)

        stats = {}

        # 1. Global mastery stats (fixed bonuses from mastery tree, don't scale with +All Skills)
        mastery_stats = get_global_mastery_stats(level)
        for stat_key, value in mastery_stats.items():
            stats[stat_key] = stats.get(stat_key, 0) + value

        # 2. PASSIVE_STAT skills (scale with skill levels = base 1 + All Skills bonus)
        for skill_name, skill in BOWMASTER_SKILLS.items():
            if skill.skill_type == SkillType.PASSIVE_STAT:
                if level >= skill.unlock_level:
                    # Effective level = base level 1 + All Skills bonus
                    effective_level = 1 + all_skills
                    value = skill.base_stat_value + skill.stat_per_level * (effective_level - 1)
                    stat_key = skill.stat_type

                    # Special handling for armor_break which gives both def_pen AND final_damage
                    if stat_key == "defense_pen_and_final_damage":
                        stats["def_pen"] = stats.get("def_pen", 0) + value
                        stats["final_damage"] = stats.get("final_damage", 0) + value
                    else:
                        stats[stat_key] = stats.get(stat_key, 0) + value

        # Include total All Skills used for skill scaling (for display purposes)
        stats["total_all_skills"] = all_skills

        return stats

    def _on_resonance_change(self, event=None):
        """Called when user changes resonance values."""
        # Save resonance and update damage calculation
        self.save_resonance_to_csv(silent=True)
        self.update_damage()

    def get_resonance_stats(self) -> Dict[str, float]:
        """Get resonance stats from manual input fields."""
        try:
            main_stat = float(self.resonance_main_stat_var.get() or 0)
        except ValueError:
            main_stat = 0
        try:
            hp = float(self.resonance_hp_var.get() or 0)
        except ValueError:
            hp = 0
        return {
            "main_stat_flat": main_stat,
            "max_hp_flat": hp,
        }

    def _on_artifact_cost_select(self, event=None):
        """Called when user selects an artifact in the cost calculator."""
        selection = self.artifact_cost_selector.get()
        if not selection:
            return

        # Parse artifact name from selection (remove tier suffix)
        artifact_name = selection.rsplit(" (", 1)[0]

        # Find current stars from inventory if owned
        for art in self.artifact_config.inventory:
            if art.definition.name == artifact_name:
                self.artifact_cost_current_stars.set(str(art.awakening_stars))
                break
        else:
            self.artifact_cost_current_stars.set("0")

        self._update_artifact_cost_display()

    def _update_artifact_cost_display(self, event=None):
        """Update the artifact cost calculator display."""
        selection = self.artifact_cost_selector.get()
        if not selection:
            # Clear all labels
            for lbl in self.artifact_cost_labels.values():
                lbl.config(text="---")
            for lbl in self.artifact_synth_labels.values():
                lbl.config(text="---")
            return

        # Parse artifact name and find key
        artifact_name = selection.rsplit(" (", 1)[0]
        artifact_key = None
        definition = None
        for key, defn in ARTIFACTS.items():
            if defn.name == artifact_name:
                artifact_key = key
                definition = defn
                break

        if not artifact_key or not definition:
            return

        current_stars = int(self.artifact_cost_current_stars.get())
        target_stars = int(self.artifact_cost_target_stars.get())

        # Get drop rate
        drop_rate = ARTIFACT_DROP_RATES.get(artifact_key, 0)
        if drop_rate > 0:
            self.artifact_cost_labels["drop_rate"].config(text=f"{drop_rate*100:.4f}%")
        else:
            self.artifact_cost_labels["drop_rate"].config(text="Unknown")

        # Calculate upgrade cost
        if target_stars > current_stars and drop_rate > 0:
            result = calculate_artifact_upgrade_efficiency(
                artifact_key, current_stars, target_stars
            )

            if "error" not in result:
                self.artifact_cost_labels["dupes_needed"].config(
                    text=f"{result['duplicates_needed']}"
                )
                self.artifact_cost_labels["expected_chests"].config(
                    text=f"{result['expected_chests']:,.0f}"
                )
                self.artifact_cost_labels["blue_diamonds"].config(
                    text=f"{result['expected_diamonds']:,.0f}"
                )

                # Effect gain display
                active_gain = result.get('active_effect_gain', 0)
                inv_gain = result.get('inventory_effect_gain', 0)
                if active_gain or inv_gain:
                    effect_text = []
                    if active_gain:
                        if definition.active_stat == "attack_flat":
                            effect_text.append(f"Active: +{active_gain:.0f}")
                        else:
                            effect_text.append(f"Active: +{active_gain*100:.1f}%")
                    if inv_gain:
                        if definition.inventory_stat == "attack_flat":
                            effect_text.append(f"Inv: +{inv_gain:.0f}")
                        else:
                            effect_text.append(f"Inv: +{inv_gain*100:.1f}%")
                    self.artifact_cost_labels["effect_gain"].config(
                        text=", ".join(effect_text)
                    )
                else:
                    self.artifact_cost_labels["effect_gain"].config(text="---")
            else:
                self.artifact_cost_labels["dupes_needed"].config(text="---")
                self.artifact_cost_labels["expected_chests"].config(text="---")
                self.artifact_cost_labels["blue_diamonds"].config(text="---")
                self.artifact_cost_labels["effect_gain"].config(text=result.get("error", "---"))
        else:
            self.artifact_cost_labels["dupes_needed"].config(text="0" if target_stars <= current_stars else "---")
            self.artifact_cost_labels["expected_chests"].config(text="0" if target_stars <= current_stars else "---")
            self.artifact_cost_labels["blue_diamonds"].config(text="0" if target_stars <= current_stars else "---")
            self.artifact_cost_labels["effect_gain"].config(text="Already at target" if target_stars <= current_stars else "---")

        # Synthesis comparison (only for legendaries)
        if definition.tier == ArtifactTier.LEGENDARY and drop_rate > 0:
            synth_result = calculate_specific_legendary_cost(artifact_key)

            if "error" not in synth_result:
                direct = synth_result.get("direct_drop", {})
                synth = synth_result.get("synthesis", {})

                self.artifact_synth_labels["direct_chests"].config(
                    text=f"{direct.get('chests', 0):,.0f}"
                )
                self.artifact_synth_labels["direct_diamonds"].config(
                    text=f"{direct.get('diamonds', 0):,.0f}"
                )
                self.artifact_synth_labels["synth_chests"].config(
                    text=f"{synth.get('chests', 0):,.0f}"
                )
                self.artifact_synth_labels["synth_diamonds"].config(
                    text=f"{synth.get('diamonds', 0):,.0f}"
                )

                recommendation = synth_result.get("recommendation", "Direct drop")
                rec_color = '#7fff7f' if recommendation == "Direct drop" else '#ffaa00'
                self.artifact_synth_labels["recommendation"].config(
                    text=recommendation, fg=rec_color
                )
            else:
                for lbl in self.artifact_synth_labels.values():
                    lbl.config(text="---")
        else:
            # Not a legendary or unknown drop rate
            for key, lbl in self.artifact_synth_labels.items():
                if definition.tier != ArtifactTier.LEGENDARY:
                    lbl.config(text="N/A (Not Legendary)", fg='#888')
                else:
                    lbl.config(text="---")

    def save_artifacts_to_csv(self, filepath: str = None, silent: bool = False):
        """Save artifact configuration to CSV."""
        if filepath is None:
            filepath = ARTIFACTS_SAVE_FILE

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["artifact_key", "awakening_stars", "equipped_slot",
                               "pot1_stat", "pot1_value", "pot1_tier",
                               "pot2_stat", "pot2_value", "pot2_tier",
                               "pot3_stat", "pot3_value", "pot3_tier"])

                for artifact in self.artifact_config.inventory:
                    # Find artifact key
                    artifact_key = None
                    for key, defn in ARTIFACTS.items():
                        if defn.name == artifact.definition.name:
                            artifact_key = key
                            break

                    if not artifact_key:
                        continue

                    # Find if equipped
                    equipped_slot = -1
                    for i, eq in enumerate(self.artifact_config.equipped):
                        if eq and eq.definition.name == artifact.definition.name:
                            equipped_slot = i
                            break

                    # Build row
                    row = [artifact_key, artifact.awakening_stars, equipped_slot]

                    for i in range(3):
                        if i < len(artifact.potentials):
                            pot = artifact.potentials[i]
                            row.extend([pot.stat, pot.value, pot.tier.value])
                        else:
                            row.extend(["", 0, ""])

                    writer.writerow(row)

            if not silent:
                messagebox.showinfo("Success", f"Artifacts saved to {filepath}")

        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save: {e}")

    def load_artifacts_from_csv(self, filepath: str = None, silent: bool = False):
        """Load artifact configuration from CSV."""
        if filepath is None:
            filepath = ARTIFACTS_SAVE_FILE

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                self.artifact_config = ArtifactConfig()

                for row in reader:
                    artifact_key = row.get("artifact_key", "")
                    if artifact_key not in ARTIFACTS:
                        continue

                    stars = int(row.get("awakening_stars", 0))
                    equipped_slot = int(row.get("equipped_slot", -1))

                    # Create instance
                    instance = create_artifact_instance(artifact_key, stars)
                    if not instance:
                        continue

                    # Load potentials
                    for i in range(3):
                        stat = row.get(f"pot{i+1}_stat", "")
                        value_str = row.get(f"pot{i+1}_value", "0")
                        tier_str = row.get(f"pot{i+1}_tier", "")

                        if stat and tier_str:
                            try:
                                value = float(value_str)
                                tier = ArtifactPotentialTier[tier_str.upper()]
                                instance.potentials.append(ArtifactPotentialLine(
                                    stat=stat, value=value, tier=tier, slot=i+1
                                ))
                            except (ValueError, KeyError):
                                pass

                    self.artifact_config.inventory.append(instance)

                    # Set equipped slot
                    if 0 <= equipped_slot < 3:
                        self.artifact_config.equipped[equipped_slot] = instance

                    # Update UI widget
                    if artifact_key in self.artifact_inventory_widgets:
                        self.artifact_inventory_widgets[artifact_key]['stars_var'].set(str(stars))
                        self._update_artifact_inv_effect(artifact_key)

                # Update equipped slots UI
                for slot_idx, widgets in self.artifact_slot_widgets.items():
                    artifact = self.artifact_config.equipped[slot_idx]
                    if artifact:
                        widgets['artifact_var'].set(artifact.definition.name)
                        widgets['stars_label'].config(text=str(artifact.awakening_stars))
                    else:
                        widgets['artifact_var'].set("(Empty)")
                        widgets['stars_label'].config(text="0")

                self._update_artifact_displays()

            if not silent:
                messagebox.showinfo("Success", f"Artifacts loaded from {filepath}")

        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load: {e}")

    def auto_load_artifacts(self):
        """Automatically load artifacts from default save file on startup."""
        if os.path.exists(ARTIFACTS_SAVE_FILE):
            self.load_artifacts_from_csv(ARTIFACTS_SAVE_FILE, silent=True)

    def export_artifacts_csv(self):
        """Export artifacts to user-selected CSV file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="artifacts_export.csv"
        )
        if filepath:
            self.save_artifacts_to_csv(filepath)
            messagebox.showinfo("Success", f"Artifacts exported to {filepath}")

    def import_artifacts_csv(self):
        """Import artifacts from user-selected CSV file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv")]
        )
        if filepath:
            self.load_artifacts_from_csv(filepath)
            messagebox.showinfo("Success", f"Artifacts imported from {filepath}")

    def save_resonance_to_csv(self, silent: bool = True):
        """Save resonance values to CSV."""
        try:
            with open(RESONANCE_SAVE_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["field", "value"])
                writer.writerow(["stars", self.resonance_stars_var.get()])
                writer.writerow(["main_stat", self.resonance_main_stat_var.get()])
                writer.writerow(["hp", self.resonance_hp_var.get()])
                writer.writerow(["level", self.resonance_level_var.get()])
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save resonance: {e}")

    def load_resonance_from_csv(self, silent: bool = True):
        """Load resonance values from CSV."""
        if not os.path.exists(RESONANCE_SAVE_FILE):
            return

        try:
            with open(RESONANCE_SAVE_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    field = row.get("field", "")
                    value = row.get("value", "0")
                    if field == "stars":
                        self.resonance_stars_var.set(value)
                    elif field == "main_stat":
                        self.resonance_main_stat_var.set(value)
                    elif field == "hp":
                        self.resonance_hp_var.set(value)
                    elif field == "level":
                        self.resonance_level_var.set(value)
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load resonance: {e}")

    def auto_load_resonance(self):
        """Automatically load resonance from default save file on startup."""
        self.load_resonance_from_csv(silent=True)

    # =========================================================================
    # WEAPONS TAB
    # =========================================================================

    def build_weapons_tab(self):
        """Build the Weapons tab for tracking weapon ATK% bonuses."""
        # Create scrollable frame
        canvas = tk.Canvas(self.weapons_tab, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.weapons_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling when mouse is over this tab
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        main_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Two-column layout
        cols = tk.Frame(main_frame, bg='#1a1a2e')
        cols.pack(fill=tk.BOTH, expand=True, pady=10)

        left_col = tk.Frame(cols, bg='#1a1a2e')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_col = tk.Frame(cols, bg='#1a1a2e')
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # =====================================================================
        # LEFT COLUMN: Equipped Weapon
        # =====================================================================
        self._section_header(left_col, "Equipped Weapon")

        equipped_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        equipped_frame.pack(fill=tk.X, pady=5, padx=5)

        # Rarity selector
        row1 = tk.Frame(equipped_frame, bg='#252545')
        row1.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(row1, text="Rarity:", bg='#252545', fg='#aaa', width=10, anchor='w').pack(side=tk.LEFT)
        rarities = ["normal", "rare", "epic", "unique", "legendary", "mystic", "ancient"]
        self.weapon_equipped_rarity = ttk.Combobox(row1, values=rarities, width=12, state='readonly')
        self.weapon_equipped_rarity.set("mystic")
        self.weapon_equipped_rarity.pack(side=tk.LEFT, padx=5)
        self.weapon_equipped_rarity.bind('<<ComboboxSelected>>', self._on_weapon_equipped_change)

        tk.Label(row1, text="Tier:", bg='#252545', fg='#aaa').pack(side=tk.LEFT, padx=(10, 0))
        self.weapon_equipped_tier = ttk.Combobox(row1, values=[1, 2, 3, 4], width=4, state='readonly')
        self.weapon_equipped_tier.set("1")
        self.weapon_equipped_tier.pack(side=tk.LEFT, padx=5)
        self.weapon_equipped_tier.bind('<<ComboboxSelected>>', self._on_weapon_equipped_change)

        # Level input
        row2 = tk.Frame(equipped_frame, bg='#252545')
        row2.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(row2, text="Level:", bg='#252545', fg='#aaa', width=10, anchor='w').pack(side=tk.LEFT)
        self.weapon_equipped_level = tk.Entry(row2, width=8, bg='#333', fg='#fff', insertbackground='#fff')
        self.weapon_equipped_level.insert(0, "130")
        self.weapon_equipped_level.pack(side=tk.LEFT, padx=5)
        self.weapon_equipped_level.bind('<KeyRelease>', self._on_weapon_equipped_change)

        tk.Label(row2, text="Weapon Class:", bg='#252545', fg='#aaa').pack(side=tk.LEFT, padx=(10, 0))
        weapon_classes = ["bow", "staff", "wand", "sword", "spear", "claw", "gun", "knuckle", "crossbow"]
        self.weapon_equipped_class = ttk.Combobox(row2, values=weapon_classes, width=10, state='readonly')
        self.weapon_equipped_class.set("bow")
        self.weapon_equipped_class.pack(side=tk.LEFT, padx=5)

        # Equipped weapon stats display
        self._section_header(left_col, "Equipped Weapon Stats")

        eq_stats_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        eq_stats_frame.pack(fill=tk.X, pady=5, padx=5)

        self.weapon_equipped_stats = {}
        eq_stat_items = [
            ("Rate per Level", "rate_per_level"),
            ("On-Equip ATK%", "on_equip_atk"),
            ("Inventory ATK%", "inventory_atk"),
            ("Total ATK%", "total_atk"),
        ]
        for display_name, key in eq_stat_items:
            row = tk.Frame(eq_stats_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)
            tk.Label(row, text=f"{display_name}:", bg='#252545', fg='#aaa', width=16, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="---", bg='#252545', fg='#7fff7f', font=('Segoe UI', 10, 'bold'))
            lbl.pack(side=tk.LEFT)
            self.weapon_equipped_stats[key] = lbl

        # =====================================================================
        # LEFT COLUMN: Weapon Inventory
        # =====================================================================
        self._section_header(left_col, "Weapon Inventory (Add Weapons)")

        # Add weapon form
        add_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        add_frame.pack(fill=tk.X, pady=5, padx=5)

        add_row1 = tk.Frame(add_frame, bg='#252545')
        add_row1.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(add_row1, text="Rarity:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.weapon_add_rarity = ttk.Combobox(add_row1, values=rarities, width=10, state='readonly')
        self.weapon_add_rarity.set("legendary")
        self.weapon_add_rarity.pack(side=tk.LEFT, padx=5)

        tk.Label(add_row1, text="Tier:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.weapon_add_tier = ttk.Combobox(add_row1, values=[1, 2, 3, 4], width=3, state='readonly')
        self.weapon_add_tier.set("2")
        self.weapon_add_tier.pack(side=tk.LEFT, padx=5)

        tk.Label(add_row1, text="Level:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.weapon_add_level = tk.Entry(add_row1, width=6, bg='#333', fg='#fff', insertbackground='#fff')
        self.weapon_add_level.insert(0, "80")
        self.weapon_add_level.pack(side=tk.LEFT, padx=5)

        tk.Button(add_row1, text="Add to Inventory", command=self._add_weapon_to_inventory,
                  bg='#4a7c4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=10)

        # Scrollable inventory list
        inv_canvas = tk.Canvas(left_col, bg='#1a1a2e', highlightthickness=0, height=200)
        inv_scrollbar = ttk.Scrollbar(left_col, orient="vertical", command=inv_canvas.yview)
        self.weapon_inv_frame = tk.Frame(inv_canvas, bg='#1a1a2e')

        self.weapon_inv_frame.bind(
            "<Configure>",
            lambda e: inv_canvas.configure(scrollregion=inv_canvas.bbox("all"))
        )

        inv_canvas.create_window((0, 0), window=self.weapon_inv_frame, anchor="nw")
        inv_canvas.configure(yscrollcommand=inv_scrollbar.set)

        inv_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        inv_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # =====================================================================
        # RIGHT COLUMN: Total Weapon Stats
        # =====================================================================
        self._section_header(right_col, "Total Weapon ATK% Summary")

        summary_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        summary_frame.pack(fill=tk.X, pady=5, padx=5)

        self.weapon_summary_labels = {}
        summary_items = [
            ("Equipped ATK%", "equipped_atk"),
            ("Inventory ATK% (Total)", "inventory_atk"),
            ("TOTAL ATK%", "total_atk"),
        ]
        for display_name, key in summary_items:
            row = tk.Frame(summary_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=3)
            tk.Label(row, text=f"{display_name}:", bg='#252545', fg='#aaa', width=20, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="---", bg='#252545', fg='#ffd700', font=('Segoe UI', 12, 'bold'))
            lbl.pack(side=tk.LEFT)
            self.weapon_summary_labels[key] = lbl

        # Info text
        info_frame = tk.Frame(right_col, bg='#1a1a2e')
        info_frame.pack(fill=tk.X, pady=10, padx=5)

        info_text = """
How Weapon ATK% Works:
• On-Equip ATK%: Only applies when the weapon is equipped
• Inventory ATK%: Always applies (1/4 of On-Equip value)
• Total ATK% is multiplied against your base attack

Rarity (T4 baseline rates):
• Normal: 0.16%/level    • Rare: 0.09%/level
• Epic: 0.23%/level      • Unique: 0.60%/level
• Legendary: 1.65%/level • Mystic: 4.90%/level
• Ancient: 28.0%/level

Tier Scaling: Higher tiers have 1.3x multiplier per tier
• T4: 1.0x, T3: 1.3x, T2: 1.69x, T1: 2.2x
• Mystic T1 has special 3.22x bonus
        """
        tk.Label(info_frame, text=info_text, bg='#1a1a2e', fg='#888',
                font=('Segoe UI', 9), justify='left').pack(anchor='w')

        # =====================================================================
        # RIGHT COLUMN: ATK% Calculator
        # =====================================================================
        self._section_header(right_col, "ATK% Calculator")

        calc_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        calc_frame.pack(fill=tk.X, pady=5, padx=5)

        calc_row = tk.Frame(calc_frame, bg='#252545')
        calc_row.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(calc_row, text="Rarity:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.weapon_calc_rarity = ttk.Combobox(calc_row, values=rarities, width=10, state='readonly')
        self.weapon_calc_rarity.set("mystic")
        self.weapon_calc_rarity.pack(side=tk.LEFT, padx=5)

        tk.Label(calc_row, text="Tier:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.weapon_calc_tier = ttk.Combobox(calc_row, values=[1, 2, 3, 4], width=3, state='readonly')
        self.weapon_calc_tier.set("1")
        self.weapon_calc_tier.pack(side=tk.LEFT, padx=5)

        tk.Label(calc_row, text="Level:", bg='#252545', fg='#aaa').pack(side=tk.LEFT)
        self.weapon_calc_level = tk.Entry(calc_row, width=6, bg='#333', fg='#fff', insertbackground='#fff')
        self.weapon_calc_level.insert(0, "100")
        self.weapon_calc_level.pack(side=tk.LEFT, padx=5)

        tk.Button(calc_row, text="Calculate", command=self._calculate_weapon_preview,
                  bg='#4a7c4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=10)

        # Calculator results
        self.weapon_calc_results = {}
        calc_result_items = [
            ("Rate/Level", "rate"),
            ("On-Equip ATK%", "on_equip"),
            ("Inventory ATK%", "inventory"),
            ("Total ATK%", "total"),
        ]
        for display_name, key in calc_result_items:
            row = tk.Frame(calc_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=1)
            tk.Label(row, text=f"{display_name}:", bg='#252545', fg='#aaa', width=16, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="---", bg='#252545', fg='#7fff7f', font=('Segoe UI', 9))
            lbl.pack(side=tk.LEFT)
            self.weapon_calc_results[key] = lbl

        # =====================================================================
        # BOTTOM: Save/Load buttons
        # =====================================================================
        btn_frame = tk.Frame(main_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=10)

        tk.Button(btn_frame, text="Save Weapons", command=self.save_weapons_to_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Load Weapons", command=self.load_weapons_from_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Update Stats", command=self._update_weapon_displays,
                  bg='#7a4a4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        # Initialize displays
        self._on_weapon_equipped_change()

    def _on_weapon_equipped_change(self, event=None):
        """Called when equipped weapon parameters change."""
        try:
            rarity = self.weapon_equipped_rarity.get()
            tier = int(self.weapon_equipped_tier.get())
            level = int(self.weapon_equipped_level.get())
            weapon_class = self.weapon_equipped_class.get()
        except (ValueError, tk.TclError):
            return

        # Update equipped weapon in config
        self.weapon_config.equipped = create_weapon_instance(rarity, tier, level, weapon_class, True)

        # Make sure equipped weapon is in inventory
        found = False
        for i, weapon in enumerate(self.weapon_config.inventory):
            if weapon.is_equipped:
                self.weapon_config.inventory[i] = self.weapon_config.equipped
                found = True
                break
        if not found:
            self.weapon_config.inventory.append(self.weapon_config.equipped)

        # Update stats display
        stats = calculate_weapon_atk(WeaponRarity(rarity.lower()), tier, level)
        self.weapon_equipped_stats["rate_per_level"].config(text=f"+{stats['rate_per_level']:.2f}%")
        self.weapon_equipped_stats["on_equip_atk"].config(text=f"+{stats['on_equip_atk']:.1f}%")
        self.weapon_equipped_stats["inventory_atk"].config(text=f"+{stats['inventory_atk']:.1f}%")
        self.weapon_equipped_stats["total_atk"].config(text=f"+{stats['total_atk']:.1f}%")

        self._update_weapon_displays()

    def _add_weapon_to_inventory(self):
        """Add a weapon to the inventory."""
        try:
            rarity = self.weapon_add_rarity.get()
            tier = int(self.weapon_add_tier.get())
            level = int(self.weapon_add_level.get())
        except (ValueError, tk.TclError):
            return

        weapon = create_weapon_instance(rarity, tier, level, "bow", False)
        self.weapon_config.inventory.append(weapon)
        self._rebuild_weapon_inventory_list()
        self._update_weapon_displays()

    def _rebuild_weapon_inventory_list(self):
        """Rebuild the weapon inventory display."""
        # Clear existing widgets
        for widget in self.weapon_inv_frame.winfo_children():
            widget.destroy()
        self.weapon_inventory_widgets = []

        # Add header
        header = tk.Frame(self.weapon_inv_frame, bg='#1a1a2e')
        header.pack(fill=tk.X, pady=2)
        tk.Label(header, text="Rarity", bg='#1a1a2e', fg='#888', width=12, anchor='w').pack(side=tk.LEFT, padx=2)
        tk.Label(header, text="Tier", bg='#1a1a2e', fg='#888', width=5).pack(side=tk.LEFT, padx=2)
        tk.Label(header, text="Level", bg='#1a1a2e', fg='#888', width=6).pack(side=tk.LEFT, padx=2)
        tk.Label(header, text="Inv ATK%", bg='#1a1a2e', fg='#888', width=10).pack(side=tk.LEFT, padx=2)
        tk.Label(header, text="Equipped", bg='#1a1a2e', fg='#888', width=8).pack(side=tk.LEFT, padx=2)

        # Add each weapon
        for i, weapon in enumerate(self.weapon_config.inventory):
            row = tk.Frame(self.weapon_inv_frame, bg='#202040')
            row.pack(fill=tk.X, pady=1, padx=2)

            # Rarity with color
            rarity_color = get_rarity_color(weapon.definition.rarity)
            tk.Label(row, text=weapon.definition.rarity.value.capitalize(),
                    bg='#202040', fg=rarity_color, width=12, anchor='w',
                    font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=2)

            # Tier
            tk.Label(row, text=f"T{weapon.definition.tier}",
                    bg='#202040', fg='#aaa', width=5).pack(side=tk.LEFT, padx=2)

            # Level
            tk.Label(row, text=str(weapon.level),
                    bg='#202040', fg='#fff', width=6).pack(side=tk.LEFT, padx=2)

            # Inventory ATK%
            inv_atk = weapon.get_inventory_atk()
            tk.Label(row, text=f"+{inv_atk:.1f}%",
                    bg='#202040', fg='#7fff7f', width=10).pack(side=tk.LEFT, padx=2)

            # Equipped indicator
            eq_text = "YES" if weapon.is_equipped else ""
            eq_color = '#ffd700' if weapon.is_equipped else '#202040'
            tk.Label(row, text=eq_text, bg='#202040', fg=eq_color, width=8).pack(side=tk.LEFT, padx=2)

            # Delete button (only for non-equipped)
            if not weapon.is_equipped:
                tk.Button(row, text="X", command=lambda idx=i: self._remove_weapon(idx),
                         bg='#7a4a4a', fg='white', font=('Segoe UI', 8), width=2).pack(side=tk.LEFT, padx=5)

            self.weapon_inventory_widgets.append({'row': row, 'weapon': weapon})

    def _remove_weapon(self, index: int):
        """Remove a weapon from the inventory."""
        if 0 <= index < len(self.weapon_config.inventory):
            weapon = self.weapon_config.inventory[index]
            if not weapon.is_equipped:
                self.weapon_config.inventory.pop(index)
                self._rebuild_weapon_inventory_list()
                self._update_weapon_displays()

    def _update_weapon_displays(self):
        """Update all weapon displays."""
        # Update summary
        equipped_atk = self.weapon_config.get_equipped_atk()
        inv_atk = self.weapon_config.get_total_inventory_atk()
        total_atk = self.weapon_config.get_total_atk_percent()

        self.weapon_summary_labels["equipped_atk"].config(text=f"+{equipped_atk:.1f}%")
        self.weapon_summary_labels["inventory_atk"].config(text=f"+{inv_atk:.1f}%")
        self.weapon_summary_labels["total_atk"].config(text=f"+{total_atk:.1f}%")

        # Rebuild inventory list
        self._rebuild_weapon_inventory_list()

    def _calculate_weapon_preview(self):
        """Calculate weapon stats for the calculator preview."""
        try:
            rarity = self.weapon_calc_rarity.get()
            tier = int(self.weapon_calc_tier.get())
            level = int(self.weapon_calc_level.get())
        except (ValueError, tk.TclError):
            return

        stats = calculate_weapon_atk(WeaponRarity(rarity.lower()), tier, level)
        self.weapon_calc_results["rate"].config(text=f"+{stats['rate_per_level']:.2f}%/level")
        self.weapon_calc_results["on_equip"].config(text=f"+{stats['on_equip_atk']:.1f}%")
        self.weapon_calc_results["inventory"].config(text=f"+{stats['inventory_atk']:.1f}%")
        self.weapon_calc_results["total"].config(text=f"+{stats['total_atk']:.1f}%")

    def get_weapon_stats_total(self) -> Dict[str, float]:
        """Get total stats contribution from weapons for damage calculation."""
        return self.weapon_config.get_all_stats()

    def save_weapons_to_csv(self, filepath: str = None):
        """Save weapon configuration to CSV."""
        if filepath is None:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="weapons_save.csv"
            )
            if not filepath:
                return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["rarity", "tier", "level", "weapon_class", "is_equipped"])

                for weapon in self.weapon_config.inventory:
                    writer.writerow([
                        weapon.definition.rarity.value,
                        weapon.definition.tier,
                        weapon.level,
                        weapon.definition.weapon_class,
                        weapon.is_equipped,
                    ])

            messagebox.showinfo("Success", f"Weapons saved to {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def load_weapons_from_csv(self, filepath: str = None, silent: bool = False):
        """Load weapon configuration from CSV."""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv")],
                initialfile="weapons_save.csv"
            )
            if not filepath:
                return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                self.weapon_config = WeaponConfig()

                for row in reader:
                    rarity = row.get("rarity", "legendary")
                    tier = int(row.get("tier", 1))
                    level = int(row.get("level", 1))
                    weapon_class = row.get("weapon_class", "bow")
                    is_equipped = row.get("is_equipped", "False").lower() == "true"

                    weapon = create_weapon_instance(rarity, tier, level, weapon_class, is_equipped)
                    self.weapon_config.inventory.append(weapon)

                    if is_equipped:
                        self.weapon_config.equipped = weapon

            # Update UI
            if self.weapon_config.equipped:
                eq = self.weapon_config.equipped
                self.weapon_equipped_rarity.set(eq.definition.rarity.value)
                self.weapon_equipped_tier.set(str(eq.definition.tier))
                self.weapon_equipped_level.delete(0, tk.END)
                self.weapon_equipped_level.insert(0, str(eq.level))
                self.weapon_equipped_class.set(eq.definition.weapon_class)

            self._on_weapon_equipped_change()

            if not silent:
                messagebox.showinfo("Success", f"Weapons loaded from {filepath}")

        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load: {e}")

    def auto_load_weapons(self):
        """Automatically load weapons from default save file on startup."""
        if os.path.exists(WEAPONS_SAVE_FILE):
            self.load_weapons_from_csv(WEAPONS_SAVE_FILE, silent=True)

    # =========================================================================
    # MAPLE RANK TAB
    # =========================================================================

    def build_maple_rank_tab(self):
        """Build the Maple Rank configuration tab."""
        # Create scrollable frame
        canvas = tk.Canvas(self.maple_rank_tab, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.maple_rank_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Main content area
        main_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        tk.Label(main_frame, text="Maple Rank Configuration",
                 font=('Segoe UI', 16, 'bold'), bg='#1a1a2e', fg='#ffd700').pack(pady=(0, 15))

        # Two column layout
        cols = tk.Frame(main_frame, bg='#1a1a2e')
        cols.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(cols, bg='#1a1a2e')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_col = tk.Frame(cols, bg='#1a1a2e')
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # =====================================================================
        # LEFT COLUMN: Main Stat Configuration
        # =====================================================================
        self._section_header(left_col, "Main Stat (Regular)")

        main_stat_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        main_stat_frame.pack(fill=tk.X, pady=5, padx=5)

        # Stage selector
        stage_row = tk.Frame(main_stat_frame, bg='#252545')
        stage_row.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(stage_row, text="Current Stage:", bg='#252545', fg='#aaa',
                 font=('Segoe UI', 10)).pack(side=tk.LEFT)

        self.maple_rank_stage_var = tk.StringVar(value="21")
        stage_combo = ttk.Combobox(stage_row, textvariable=self.maple_rank_stage_var,
                                   values=[str(i) for i in range(1, 26)], width=5, state='readonly')
        stage_combo.pack(side=tk.LEFT, padx=10)
        stage_combo.bind('<<ComboboxSelected>>', self._on_maple_rank_change)

        # Stage info label
        self.maple_rank_stage_info = tk.Label(stage_row, text="80 DEX per point",
                                              bg='#252545', fg='#7fff7f', font=('Segoe UI', 10))
        self.maple_rank_stage_info.pack(side=tk.LEFT, padx=10)

        # Level within stage
        level_row = tk.Frame(main_stat_frame, bg='#252545')
        level_row.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(level_row, text="Level in Stage:", bg='#252545', fg='#aaa',
                 font=('Segoe UI', 10)).pack(side=tk.LEFT)

        self.maple_rank_main_stat_level = tk.Entry(level_row, width=5, bg='#3a3a5a', fg='white',
                                                    insertbackground='white')
        self.maple_rank_main_stat_level.insert(0, "5")
        self.maple_rank_main_stat_level.pack(side=tk.LEFT, padx=10)
        self.maple_rank_main_stat_level.bind('<FocusOut>', self._on_maple_rank_change)
        self.maple_rank_main_stat_level.bind('<Return>', self._on_maple_rank_change)

        tk.Label(level_row, text="/ 10", bg='#252545', fg='#888').pack(side=tk.LEFT)

        # Regular main stat total
        self.maple_rank_regular_total = tk.Label(main_stat_frame, text="Total: 6,770 DEX",
                                                  bg='#252545', fg='#00ff88', font=('Segoe UI', 11, 'bold'))
        self.maple_rank_regular_total.pack(pady=10)

        # Special Main Stat
        self._section_header(left_col, "Main Stat (Special)")

        special_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        special_frame.pack(fill=tk.X, pady=5, padx=5)

        special_row = tk.Frame(special_frame, bg='#252545')
        special_row.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(special_row, text="Points:", bg='#252545', fg='#aaa',
                 font=('Segoe UI', 10)).pack(side=tk.LEFT)

        self.maple_rank_special_points = tk.Entry(special_row, width=5, bg='#3a3a5a', fg='white',
                                                   insertbackground='white')
        self.maple_rank_special_points.insert(0, "20")
        self.maple_rank_special_points.pack(side=tk.LEFT, padx=10)
        self.maple_rank_special_points.bind('<FocusOut>', self._on_maple_rank_change)
        self.maple_rank_special_points.bind('<Return>', self._on_maple_rank_change)

        tk.Label(special_row, text="/ 160  (20 DEX per point)", bg='#252545', fg='#888').pack(side=tk.LEFT)

        self.maple_rank_special_total = tk.Label(special_frame, text="Total: +400 DEX",
                                                  bg='#252545', fg='#00ff88', font=('Segoe UI', 11, 'bold'))
        self.maple_rank_special_total.pack(pady=10)

        # =====================================================================
        # RIGHT COLUMN: Other Stats
        # =====================================================================
        self._section_header(right_col, "Other Stats")

        stats_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        stats_frame.pack(fill=tk.X, pady=5, padx=5)

        self.maple_rank_stat_entries = {}

        # Create entries for each stat type
        stat_order = [
            (MapleRankStatType.DAMAGE_PERCENT, "Damage %", 50),
            (MapleRankStatType.BOSS_DAMAGE, "Boss Damage %", 30),
            (MapleRankStatType.NORMAL_DAMAGE, "Normal Damage %", 30),
            (MapleRankStatType.SKILL_DAMAGE, "Skill Damage %", 30),
            (MapleRankStatType.CRIT_DAMAGE, "Critical Damage %", 30),
            (MapleRankStatType.CRIT_RATE, "Critical Rate %", 10),
            (MapleRankStatType.MIN_DMG_MULT, "Min Dmg Mult %", 20),
            (MapleRankStatType.MAX_DMG_MULT, "Max Dmg Mult %", 20),
            (MapleRankStatType.ATTACK_SPEED, "Attack Speed %", 20),
            (MapleRankStatType.ACCURACY, "Accuracy", 20),
        ]

        for stat_type, display_name, max_level in stat_order:
            row = tk.Frame(stats_frame, bg='#252545')
            row.pack(fill=tk.X, padx=10, pady=3)

            tk.Label(row, text=f"{display_name}:", bg='#252545', fg='#aaa',
                     font=('Segoe UI', 10), width=18, anchor='w').pack(side=tk.LEFT)

            entry = tk.Entry(row, width=5, bg='#3a3a5a', fg='white', insertbackground='white')
            entry.insert(0, str(max_level))  # Default to max
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind('<FocusOut>', self._on_maple_rank_change)
            entry.bind('<Return>', self._on_maple_rank_change)

            tk.Label(row, text=f"/ {max_level}", bg='#252545', fg='#888').pack(side=tk.LEFT)

            # Value display
            per_level = MAPLE_RANK_STATS[stat_type]["per_level"]
            value_label = tk.Label(row, text=f"= {max_level * per_level:.1f}%",
                                   bg='#252545', fg='#7fff7f', font=('Segoe UI', 10))
            value_label.pack(side=tk.LEFT, padx=10)

            self.maple_rank_stat_entries[stat_type] = {
                "entry": entry,
                "max_level": max_level,
                "value_label": value_label,
                "per_level": per_level,
            }

        # =====================================================================
        # BOTTOM: Summary and Buttons
        # =====================================================================
        self._section_header(main_frame, "Maple Rank Summary")

        summary_frame = tk.Frame(main_frame, bg='#252545', relief='ridge', bd=1)
        summary_frame.pack(fill=tk.X, pady=5, padx=5)

        self.maple_rank_summary_labels = {}

        summary_stats = [
            ("Total Main Stat (DEX)", "total_main_stat"),
            ("Damage %", "damage_percent"),
            ("Boss Damage %", "boss_damage"),
            ("Normal Damage %", "normal_damage"),
            ("Skill Damage %", "skill_damage"),
            ("Crit Damage %", "crit_damage"),
            ("Crit Rate %", "crit_rate"),
            ("Min Dmg Mult %", "min_dmg_mult"),
            ("Max Dmg Mult %", "max_dmg_mult"),
            ("Attack Speed %", "attack_speed"),
            ("Accuracy", "accuracy"),
        ]

        # Create 2-column summary
        summary_cols = tk.Frame(summary_frame, bg='#252545')
        summary_cols.pack(fill=tk.X, padx=10, pady=10)

        left_summary = tk.Frame(summary_cols, bg='#252545')
        left_summary.pack(side=tk.LEFT, fill=tk.X, expand=True)

        right_summary = tk.Frame(summary_cols, bg='#252545')
        right_summary.pack(side=tk.LEFT, fill=tk.X, expand=True)

        for i, (label, key) in enumerate(summary_stats):
            parent = left_summary if i < 6 else right_summary
            row = tk.Frame(parent, bg='#252545')
            row.pack(fill=tk.X, pady=2)

            tk.Label(row, text=f"{label}:", bg='#252545', fg='#aaa',
                     font=('Segoe UI', 10), width=20, anchor='w').pack(side=tk.LEFT)

            lbl = tk.Label(row, text="0", bg='#252545', fg='#00ff88',
                          font=('Segoe UI', 10, 'bold'))
            lbl.pack(side=tk.LEFT)
            self.maple_rank_summary_labels[key] = lbl

        # Buttons
        btn_frame = tk.Frame(main_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=10)

        tk.Button(btn_frame, text="Set All to Max", command=self._set_maple_rank_max,
                  bg='#4a7a4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset to Zero", command=self._set_maple_rank_zero,
                  bg='#7a4a4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Save", command=self.save_maple_rank_to_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Load", command=self.load_maple_rank_from_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        # Initialize display
        self._update_maple_rank_display()

    def _on_maple_rank_change(self, event=None):
        """Called when any Maple Rank value changes."""
        self._update_maple_rank_config()
        self._update_maple_rank_display()
        self.update_damage()
        self.auto_save_maple_rank()

    def _update_maple_rank_config(self):
        """Update maple_rank_config from UI values."""
        try:
            self.maple_rank_config.current_stage = int(self.maple_rank_stage_var.get())
        except ValueError:
            self.maple_rank_config.current_stage = 1

        try:
            level = int(self.maple_rank_main_stat_level.get())
            self.maple_rank_config.main_stat_level = max(0, min(10, level))
        except ValueError:
            self.maple_rank_config.main_stat_level = 0

        try:
            points = int(self.maple_rank_special_points.get())
            self.maple_rank_config.special_main_stat_points = max(0, min(160, points))
        except ValueError:
            self.maple_rank_config.special_main_stat_points = 0

        for stat_type, data in self.maple_rank_stat_entries.items():
            try:
                level = int(data["entry"].get())
                self.maple_rank_config.set_stat_level(stat_type, level)
            except ValueError:
                self.maple_rank_config.set_stat_level(stat_type, 0)

    def _update_maple_rank_display(self):
        """Update all Maple Rank display labels."""
        # Update stage info
        stage = self.maple_rank_config.current_stage
        per_point = get_main_stat_per_point(stage)
        self.maple_rank_stage_info.config(text=f"{per_point} DEX per point")

        # Update totals
        regular = self.maple_rank_config.get_regular_main_stat()
        special = self.maple_rank_config.get_special_main_stat()
        total = regular + special

        self.maple_rank_regular_total.config(text=f"Total: {regular:,} DEX")
        self.maple_rank_special_total.config(text=f"Total: +{special:,} DEX")

        # Update stat value labels
        for stat_type, data in self.maple_rank_stat_entries.items():
            level = self.maple_rank_config.get_stat_level(stat_type)
            value = level * data["per_level"]
            if stat_type == MapleRankStatType.ACCURACY:
                data["value_label"].config(text=f"= {value:.1f}")
            else:
                data["value_label"].config(text=f"= {value:.1f}%")

        # Update summary
        stats = self.maple_rank_config.get_all_stats()
        self.maple_rank_summary_labels["total_main_stat"].config(text=f"{total:,}")
        self.maple_rank_summary_labels["damage_percent"].config(text=f"{stats['damage_percent']:.1f}%")
        self.maple_rank_summary_labels["boss_damage"].config(text=f"{stats['boss_damage']:.1f}%")
        self.maple_rank_summary_labels["normal_damage"].config(text=f"{stats['normal_damage']:.1f}%")
        self.maple_rank_summary_labels["skill_damage"].config(text=f"{stats['skill_damage']:.1f}%")
        self.maple_rank_summary_labels["crit_damage"].config(text=f"{stats['crit_damage']:.1f}%")
        self.maple_rank_summary_labels["crit_rate"].config(text=f"{stats['crit_rate']:.1f}%")
        self.maple_rank_summary_labels["min_dmg_mult"].config(text=f"{stats['min_dmg_mult']:.1f}%")
        self.maple_rank_summary_labels["max_dmg_mult"].config(text=f"{stats['max_dmg_mult']:.1f}%")
        self.maple_rank_summary_labels["attack_speed"].config(text=f"{stats['attack_speed']:.1f}%")
        self.maple_rank_summary_labels["accuracy"].config(text=f"{stats['accuracy']:.1f}")

    def _set_maple_rank_max(self):
        """Set all Maple Rank stats to max."""
        self.maple_rank_stage_var.set("21")
        self.maple_rank_main_stat_level.delete(0, tk.END)
        self.maple_rank_main_stat_level.insert(0, "10")
        self.maple_rank_special_points.delete(0, tk.END)
        self.maple_rank_special_points.insert(0, "160")

        for stat_type, data in self.maple_rank_stat_entries.items():
            data["entry"].delete(0, tk.END)
            data["entry"].insert(0, str(data["max_level"]))

        self._on_maple_rank_change()

    def _set_maple_rank_zero(self):
        """Reset all Maple Rank stats to zero."""
        self.maple_rank_stage_var.set("1")
        self.maple_rank_main_stat_level.delete(0, tk.END)
        self.maple_rank_main_stat_level.insert(0, "0")
        self.maple_rank_special_points.delete(0, tk.END)
        self.maple_rank_special_points.insert(0, "0")

        for stat_type, data in self.maple_rank_stat_entries.items():
            data["entry"].delete(0, tk.END)
            data["entry"].insert(0, "0")

        self._on_maple_rank_change()

    def save_maple_rank_to_csv(self, filepath=None, silent=False):
        """Save Maple Rank configuration to CSV."""
        if filepath is None:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="maple_rank_save.csv"
            )
            if not filepath:
                return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["stat", "value"])

                writer.writerow(["current_stage", self.maple_rank_config.current_stage])
                writer.writerow(["main_stat_level", self.maple_rank_config.main_stat_level])
                writer.writerow(["special_main_stat_points", self.maple_rank_config.special_main_stat_points])

                for stat_type in self.maple_rank_stat_entries:
                    level = self.maple_rank_config.get_stat_level(stat_type)
                    writer.writerow([stat_type.value, level])

            if not silent:
                messagebox.showinfo("Success", f"Maple Rank saved to {filepath}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save Maple Rank: {e}")

    def load_maple_rank_from_csv(self, filepath=None, silent=False):
        """Load Maple Rank configuration from CSV."""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv")],
                initialfile="maple_rank_save.csv"
            )
            if not filepath:
                return

        try:
            data = {}
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        data[row[0]] = row[1]

            # Apply values
            if "current_stage" in data:
                self.maple_rank_stage_var.set(data["current_stage"])
            if "main_stat_level" in data:
                self.maple_rank_main_stat_level.delete(0, tk.END)
                self.maple_rank_main_stat_level.insert(0, data["main_stat_level"])
            if "special_main_stat_points" in data:
                self.maple_rank_special_points.delete(0, tk.END)
                self.maple_rank_special_points.insert(0, data["special_main_stat_points"])

            for stat_type, entry_data in self.maple_rank_stat_entries.items():
                if stat_type.value in data:
                    entry_data["entry"].delete(0, tk.END)
                    entry_data["entry"].insert(0, data[stat_type.value])

            self._on_maple_rank_change()

            if not silent:
                messagebox.showinfo("Success", f"Maple Rank loaded from {filepath}")

        except FileNotFoundError:
            pass  # Silent fail for auto-load
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load Maple Rank: {e}")

    def auto_load_maple_rank(self):
        """Auto-load Maple Rank from default save file if it exists."""
        if os.path.exists(MAPLE_RANK_SAVE_FILE):
            try:
                self.load_maple_rank_from_csv(MAPLE_RANK_SAVE_FILE, silent=True)
            except Exception:
                pass  # Silent fail

    def auto_save_maple_rank(self):
        """Auto-save Maple Rank to default save file."""
        try:
            self.save_maple_rank_to_csv(MAPLE_RANK_SAVE_FILE, silent=True)
        except Exception:
            pass  # Silent fail

    def get_maple_rank_stats_total(self) -> Dict[str, float]:
        """Get total stats from Maple Rank for damage calculation."""
        return self.maple_rank_config.get_all_stats()

    def get_equipment_sets_stats_total(self) -> Dict[str, float]:
        """Get total stats from Equipment Sets (Medals & Costumes) for damage calculation."""
        return self.equipment_sets_config.get_all_stats()

    # =========================================================================
    # CHARACTER STATS TAB
    # =========================================================================

    def build_character_stats_tab(self):
        """Build the Character Stats tab showing aggregated stats from all sources."""
        main_frame = ttk.Frame(self.character_stats_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrollable canvas
        canvas = tk.Canvas(main_frame, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Title
        title = tk.Label(scrollable_frame, text="Character Stats Overview",
                        font=('Segoe UI', 16, 'bold'), fg='#00d4ff', bg='#1a1a2e')
        title.pack(pady=(10, 5))

        subtitle = tk.Label(scrollable_frame,
                           text="Compare calculated stats vs actual in-game values",
                           font=('Segoe UI', 10), fg='#888', bg='#1a1a2e')
        subtitle.pack(pady=(0, 15))

        # =====================================================================
        # CHARACTER SETTINGS SECTION (Level & Skill Levels)
        # =====================================================================
        settings_header = tk.Label(scrollable_frame, text="Character Settings",
                                   font=('Segoe UI', 14, 'bold'), fg='#00ff88', bg='#1a1a2e')
        settings_header.pack(pady=(10, 5))

        settings_frame = tk.Frame(scrollable_frame, bg='#2a2a4e', relief=tk.RIDGE, bd=1)
        settings_frame.pack(fill=tk.X, padx=20, pady=5)

        # Row 1: Character Level
        level_row = tk.Frame(settings_frame, bg='#2a2a4e')
        level_row.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(level_row, text="Character Level:", font=('Segoe UI', 10),
                fg='#fff', bg='#2a2a4e', width=15, anchor='w').pack(side=tk.LEFT)

        self.char_settings_level_var = tk.IntVar(value=self.character_level)
        level_entry = tk.Entry(level_row, textvariable=self.char_settings_level_var, width=6,
                              bg='#3a3a5e', fg='#00ff88', font=('Segoe UI', 10),
                              insertbackground='white', justify='center')
        level_entry.pack(side=tk.LEFT, padx=5)
        level_entry.bind('<FocusOut>', self._on_char_settings_change)
        level_entry.bind('<Return>', self._on_char_settings_change)

        tk.Label(level_row, text="(1-300)", font=('Segoe UI', 9),
                fg='#888', bg='#2a2a4e').pack(side=tk.LEFT, padx=5)

        # Row 2: Chapter/Stage selector (moved to top for visibility)
        chapter_row = tk.Frame(settings_frame, bg='#2a2a4e')
        chapter_row.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(chapter_row, text="Chapter/Stage:", font=('Segoe UI', 10),
                fg='#fff', bg='#2a2a4e', width=15, anchor='w').pack(side=tk.LEFT)

        # Create dropdown using the existing chapter_var (synced with DPS Calculator tab)
        self.char_stats_chapter_dropdown = ttk.Combobox(
            chapter_row, textvariable=self.chapter_var,
            values=list(ENEMY_DEFENSE_VALUES.keys()),
            state='readonly', width=18, font=('Segoe UI', 9)
        )
        self.char_stats_chapter_dropdown.pack(side=tk.LEFT, padx=5)
        self.char_stats_chapter_dropdown.bind('<<ComboboxSelected>>', self._on_chapter_change)

        # Show current defense value
        self.char_stats_def_label = tk.Label(
            chapter_row, text=f"(Def: {ENEMY_DEFENSE_VALUES.get(self.chapter_var.get(), 0.752):.3f})",
            font=('Segoe UI', 9), fg='#888', bg='#2a2a4e'
        )
        self.char_stats_def_label.pack(side=tk.LEFT, padx=5)

        # Row 3: All Skills (bonus from equipment/other sources)
        all_skills_row = tk.Frame(settings_frame, bg='#2a2a4e')
        all_skills_row.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(all_skills_row, text="All Skills Bonus:", font=('Segoe UI', 10),
                fg='#fff', bg='#2a2a4e', width=15, anchor='w').pack(side=tk.LEFT)

        self.char_settings_all_skills_var = tk.IntVar(value=self.current_all_skills)
        all_skills_entry = tk.Entry(all_skills_row, textvariable=self.char_settings_all_skills_var, width=6,
                                    bg='#3a3a5e', fg='#ffcc00', font=('Segoe UI', 10),
                                    insertbackground='white', justify='center')
        all_skills_entry.pack(side=tk.LEFT, padx=5)
        all_skills_entry.bind('<FocusOut>', self._on_char_settings_change)
        all_skills_entry.bind('<Return>', self._on_char_settings_change)

        tk.Label(all_skills_row, text="(adds to all job skill levels)", font=('Segoe UI', 9),
                fg='#888', bg='#2a2a4e').pack(side=tk.LEFT, padx=5)

        # Row 3: Individual Job Skill Levels
        skill_row = tk.Frame(settings_frame, bg='#2a2a4e')
        skill_row.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(skill_row, text="Job Skill Levels:", font=('Segoe UI', 10),
                fg='#fff', bg='#2a2a4e', width=15, anchor='w').pack(side=tk.LEFT)

        # Initialize skill level vars (base values before All Skills bonus)
        self.char_settings_skill_1st_var = tk.IntVar(value=0)
        self.char_settings_skill_2nd_var = tk.IntVar(value=0)
        self.char_settings_skill_3rd_var = tk.IntVar(value=0)
        self.char_settings_skill_4th_var = tk.IntVar(value=0)

        # 1st Job
        tk.Label(skill_row, text="1st:", font=('Segoe UI', 9),
                fg='#4a9eff', bg='#2a2a4e').pack(side=tk.LEFT, padx=(5, 2))
        skill_1st_entry = tk.Entry(skill_row, textvariable=self.char_settings_skill_1st_var, width=4,
                                   bg='#3a3a5e', fg='#4a9eff', font=('Segoe UI', 10),
                                   insertbackground='white', justify='center')
        skill_1st_entry.pack(side=tk.LEFT)
        skill_1st_entry.bind('<FocusOut>', self._on_char_settings_change)
        skill_1st_entry.bind('<Return>', self._on_char_settings_change)

        # 2nd Job
        tk.Label(skill_row, text="2nd:", font=('Segoe UI', 9),
                fg='#aa66ff', bg='#2a2a4e').pack(side=tk.LEFT, padx=(10, 2))
        skill_2nd_entry = tk.Entry(skill_row, textvariable=self.char_settings_skill_2nd_var, width=4,
                                   bg='#3a3a5e', fg='#aa66ff', font=('Segoe UI', 10),
                                   insertbackground='white', justify='center')
        skill_2nd_entry.pack(side=tk.LEFT)
        skill_2nd_entry.bind('<FocusOut>', self._on_char_settings_change)
        skill_2nd_entry.bind('<Return>', self._on_char_settings_change)

        # 3rd Job
        tk.Label(skill_row, text="3rd:", font=('Segoe UI', 9),
                fg='#ff8800', bg='#2a2a4e').pack(side=tk.LEFT, padx=(10, 2))
        skill_3rd_entry = tk.Entry(skill_row, textvariable=self.char_settings_skill_3rd_var, width=4,
                                   bg='#3a3a5e', fg='#ff8800', font=('Segoe UI', 10),
                                   insertbackground='white', justify='center')
        skill_3rd_entry.pack(side=tk.LEFT)
        skill_3rd_entry.bind('<FocusOut>', self._on_char_settings_change)
        skill_3rd_entry.bind('<Return>', self._on_char_settings_change)

        # 4th Job
        tk.Label(skill_row, text="4th:", font=('Segoe UI', 9),
                fg='#ff4444', bg='#2a2a4e').pack(side=tk.LEFT, padx=(10, 2))
        skill_4th_entry = tk.Entry(skill_row, textvariable=self.char_settings_skill_4th_var, width=4,
                                   bg='#3a3a5e', fg='#ff4444', font=('Segoe UI', 10),
                                   insertbackground='white', justify='center')
        skill_4th_entry.pack(side=tk.LEFT)
        skill_4th_entry.bind('<FocusOut>', self._on_char_settings_change)
        skill_4th_entry.bind('<Return>', self._on_char_settings_change)

        # Row 4: Combat Mode selector
        combat_row = tk.Frame(settings_frame, bg='#2a2a4e')
        combat_row.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(combat_row, text="Combat Mode:", font=('Segoe UI', 10),
                fg='#fff', bg='#2a2a4e', width=15, anchor='w').pack(side=tk.LEFT)

        self.combat_mode_var = tk.StringVar(value=self.combat_mode.value)
        combat_modes = [
            ("Stage (Mixed)", CombatMode.STAGE.value),
            ("Boss (Single)", CombatMode.BOSS.value),
            ("World Boss", CombatMode.WORLD_BOSS.value),
        ]

        for text, value in combat_modes:
            rb = tk.Radiobutton(
                combat_row, text=text, variable=self.combat_mode_var,
                value=value, bg='#2a2a4e', fg='#ccc', selectcolor='#3a3a5a',
                activebackground='#2a2a4e', activeforeground='#ffd700',
                command=self._on_combat_mode_change
            )
            rb.pack(side=tk.LEFT, padx=5)

        # Combat mode info label
        self.combat_mode_info = tk.Label(
            combat_row, text="", font=('Segoe UI', 8), fg='#888', bg='#2a2a4e'
        )
        self.combat_mode_info.pack(side=tk.LEFT, padx=10)
        self._update_combat_mode_info()

        # Row 6: Calculated Total Skill Levels (with All Skills bonus)
        total_row = tk.Frame(settings_frame, bg='#2a2a4e')
        total_row.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(total_row, text="Total (with bonus):", font=('Segoe UI', 10),
                fg='#888', bg='#2a2a4e', width=15, anchor='w').pack(side=tk.LEFT)

        self.char_settings_total_label = tk.Label(total_row, text="1st: 0  |  2nd: 0  |  3rd: 0  |  4th: 0",
                                                  font=('Segoe UI', 10), fg='#00ffcc', bg='#2a2a4e')
        self.char_settings_total_label.pack(side=tk.LEFT, padx=5)

        # Row 7: Medal & Costume Main Stat
        medal_costume_row = tk.Frame(settings_frame, bg='#2a2a4e')
        medal_costume_row.pack(fill=tk.X, padx=10, pady=8)

        tk.Label(medal_costume_row, text="Medal/Costume:", font=('Segoe UI', 10),
                fg='#fff', bg='#2a2a4e', width=15, anchor='w').pack(side=tk.LEFT)

        # Medal input
        tk.Label(medal_costume_row, text="Medal:", font=('Segoe UI', 9),
                fg='#ffaa00', bg='#2a2a4e').pack(side=tk.LEFT, padx=(5, 2))

        medal_dex = self.equipment_sets_config.medal_config.get_main_stat()
        self.char_stats_medal_var = tk.StringVar(value=str(int(medal_dex)))
        medal_entry = tk.Entry(medal_costume_row, textvariable=self.char_stats_medal_var, width=5,
                              bg='#3a3a5e', fg='#00ff88', font=('Segoe UI', 10),
                              insertbackground='white', justify='center')
        medal_entry.pack(side=tk.LEFT)
        medal_entry.bind('<FocusOut>', self._on_char_stats_medal_costume_change)
        medal_entry.bind('<Return>', self._on_char_stats_medal_costume_change)

        # Costume input
        tk.Label(medal_costume_row, text="Costume:", font=('Segoe UI', 9),
                fg='#ff66ff', bg='#2a2a4e').pack(side=tk.LEFT, padx=(15, 2))

        costume_dex = self.equipment_sets_config.costume_config.get_main_stat()
        self.char_stats_costume_var = tk.StringVar(value=str(int(costume_dex)))
        costume_entry = tk.Entry(medal_costume_row, textvariable=self.char_stats_costume_var, width=5,
                                bg='#3a3a5e', fg='#00ff88', font=('Segoe UI', 10),
                                insertbackground='white', justify='center')
        costume_entry.pack(side=tk.LEFT)
        costume_entry.bind('<FocusOut>', self._on_char_stats_medal_costume_change)
        costume_entry.bind('<Return>', self._on_char_stats_medal_costume_change)

        tk.Label(medal_costume_row, text="(max 1500 each)", font=('Segoe UI', 8),
                fg='#888', bg='#2a2a4e').pack(side=tk.LEFT, padx=10)

        # Separator before comparison section
        sep1 = tk.Frame(scrollable_frame, bg='#444', height=2)
        sep1.pack(fill=tk.X, padx=20, pady=15)

        # Load saved character settings
        self.load_character_settings()

        # =====================================================================
        # STAT COMPARISON SECTION (Calculated vs Actual)
        # =====================================================================
        comparison_header = tk.Label(scrollable_frame, text="Stat Comparison (Calculated vs Actual)",
                                    font=('Segoe UI', 14, 'bold'), fg='#ff8800', bg='#1a1a2e')
        comparison_header.pack(pady=(10, 5))

        comparison_note = tk.Label(scrollable_frame,
                                  text="Enter your actual in-game values to identify gaps in our model",
                                  font=('Segoe UI', 9), fg='#888', bg='#1a1a2e')
        comparison_note.pack(pady=(0, 10))

        # Comparison frame
        self.comparison_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
        self.comparison_frame.pack(fill=tk.X, padx=20, pady=5)

        # Initialize actual stat vars with default values from user's character
        self.actual_stat_vars = {}

        # Define stats to compare with their default actual values from screenshots
        # Format: (stat_key, display_name, default_actual, is_percentage, calc_key)
        self.comparison_stats = [
            # Main Stat breakdown
            ("dex", "DEX (Total)", 70456, False, "total_dex"),
            ("dex_flat", "DEX (Flat)", 27098, False, "dex_flat"),  # 70456 / 2.6 = ~27098
            ("dex_pct", "DEX %", 160, True, "dex_percent"),
            # Attack breakdown
            ("attack", "Attack (Total)", 48788000, False, "total_attack"),
            ("attack_flat", "Attack (Flat)", 0, False, "attack_flat"),  # Unknown breakdown
            ("attack_pct", "Attack %", 0, True, "attack_percent"),  # Unknown breakdown
            # Damage stats
            ("damage_pct", "Damage %", 1185.7, True, "damage_percent"),
            ("boss_damage", "Boss Damage %", 82.7, True, "boss_damage"),
            ("normal_damage", "Normal Dmg %", 143.4, True, "normal_damage"),
            ("crit_rate", "Crit Rate %", 128.9, True, "crit_rate"),
            ("crit_damage", "Crit Damage %", 246.5, True, "crit_damage"),
            ("def_pen", "Defense Pen %", 45.8, True, "defense_pen"),
            ("final_damage", "Final Damage %", 65.8, True, "final_damage"),
            ("skill_damage", "Skill Damage %", 61.0, True, "skill_damage"),
            ("min_dmg_mult", "Min Dmg Mult %", 264.3, True, "min_dmg_mult"),
            ("max_dmg_mult", "Max Dmg Mult %", 293.7, True, "max_dmg_mult"),
            ("attack_speed", "Attack Speed %", 103.5, True, "attack_speed"),
            ("accuracy", "Accuracy", 315, False, "accuracy"),
        ]

        # Build comparison table
        self._build_comparison_table()

        # Load saved actual stats after table is built
        self.load_actual_stats()

        # Separator
        sep = tk.Frame(scrollable_frame, bg='#444', height=2)
        sep.pack(fill=tk.X, padx=20, pady=15)

        # Stats display frame (detailed breakdown)
        breakdown_header = tk.Label(scrollable_frame, text="Detailed Stat Breakdown by Source",
                                   font=('Segoe UI', 14, 'bold'), fg='#00d4ff', bg='#1a1a2e')
        breakdown_header.pack(pady=(10, 10))

        self.char_stats_display = tk.Frame(scrollable_frame, bg='#1a1a2e')
        self.char_stats_display.pack(fill=tk.BOTH, expand=True, padx=20)

        # Build initial display
        self._build_character_stats_display()

    def _build_comparison_table(self):
        """Build the comparison table with actual vs calculated stats and manual adjustments."""
        # Clear existing
        for widget in self.comparison_frame.winfo_children():
            widget.destroy()

        # Header row
        header_frame = tk.Frame(self.comparison_frame, bg='#3a3a5e')
        header_frame.pack(fill=tk.X, pady=(0, 2))

        tk.Label(header_frame, text="Stat", font=('Segoe UI', 9, 'bold'),
                fg='#fff', bg='#3a3a5e', width=16, anchor='w').pack(side=tk.LEFT, padx=5)
        tk.Label(header_frame, text="Calculated", font=('Segoe UI', 9, 'bold'),
                fg='#00ff88', bg='#3a3a5e', width=11, anchor='e').pack(side=tk.LEFT, padx=3)
        tk.Label(header_frame, text="Adjustment", font=('Segoe UI', 9, 'bold'),
                fg='#4a9eff', bg='#3a3a5e', width=10, anchor='e').pack(side=tk.LEFT, padx=3)
        tk.Label(header_frame, text="Final", font=('Segoe UI', 9, 'bold'),
                fg='#00ffcc', bg='#3a3a5e', width=11, anchor='e').pack(side=tk.LEFT, padx=3)
        tk.Label(header_frame, text="Actual", font=('Segoe UI', 9, 'bold'),
                fg='#ffcc00', bg='#3a3a5e', width=11, anchor='e').pack(side=tk.LEFT, padx=3)
        tk.Label(header_frame, text="Gap", font=('Segoe UI', 9, 'bold'),
                fg='#ff6b6b', bg='#3a3a5e', width=10, anchor='e').pack(side=tk.LEFT, padx=3)

        # Mapping from comparison stat keys to manual adjustment keys
        self.stat_key_to_adjustment_key = {
            'dex': None,  # Total DEX is calculated, not directly adjustable
            'dex_flat': 'dex_flat',
            'dex_pct': 'dex_percent',
            'attack': None,  # Total attack is calculated
            'attack_flat': 'attack_flat',
            'attack_pct': None,  # Not in manual adjustments
            'damage_pct': 'damage_percent',
            'boss_damage': 'boss_damage',
            'normal_damage': 'normal_damage',
            'crit_rate': 'crit_rate',
            'crit_damage': 'crit_damage',
            'def_pen': 'defense_pen',
            'final_damage': 'final_damage',
            'skill_damage': 'skill_damage',
            'min_dmg_mult': 'min_dmg_mult',
            'max_dmg_mult': 'max_dmg_mult',
            'attack_speed': 'attack_speed',
            'accuracy': None,  # Not in manual adjustments yet
        }

        # Store references for updating
        self.comparison_rows = {}

        for stat_key, display_name, default_actual, is_pct, calc_key in self.comparison_stats:
            row_frame = tk.Frame(self.comparison_frame, bg='#2a2a4e')
            row_frame.pack(fill=tk.X, pady=1)

            # Stat name
            tk.Label(row_frame, text=display_name, font=('Segoe UI', 9),
                    fg='#ccc', bg='#2a2a4e', width=16, anchor='w').pack(side=tk.LEFT, padx=5)

            # Calculated value (before adjustments)
            calc_label = tk.Label(row_frame, text="0", font=('Segoe UI', 9),
                                 fg='#00ff88', bg='#2a2a4e', width=11, anchor='e')
            calc_label.pack(side=tk.LEFT, padx=3)

            # Manual adjustment input
            adj_key = self.stat_key_to_adjustment_key.get(stat_key)
            if adj_key and adj_key in self.manual_stat_adjustments:
                # Create StringVar for this adjustment
                if adj_key not in self.manual_stat_vars:
                    self.manual_stat_vars[adj_key] = tk.StringVar(value=str(self.manual_stat_adjustments[adj_key]))

                adj_entry = tk.Entry(row_frame, textvariable=self.manual_stat_vars[adj_key], width=10,
                                    font=('Segoe UI', 9), bg='#1a1a2e', fg='#4a9eff',
                                    insertbackground='#4a9eff', justify='right')
                adj_entry.pack(side=tk.LEFT, padx=3)
                adj_entry.bind('<Return>', lambda e, k=adj_key: self._on_adjustment_change(k))
                adj_entry.bind('<FocusOut>', lambda e, k=adj_key: self._on_adjustment_change(k))
            else:
                # No adjustment available for this stat
                tk.Label(row_frame, text="-", font=('Segoe UI', 9),
                        fg='#555', bg='#2a2a4e', width=10, anchor='e').pack(side=tk.LEFT, padx=3)

            # Final value (calculated + adjustment)
            final_label = tk.Label(row_frame, text="0", font=('Segoe UI', 9),
                                  fg='#00ffcc', bg='#2a2a4e', width=11, anchor='e')
            final_label.pack(side=tk.LEFT, padx=3)

            # Actual value input
            var = tk.DoubleVar(value=default_actual)
            self.actual_stat_vars[stat_key] = var

            actual_entry = tk.Entry(row_frame, textvariable=var, width=11,
                                   font=('Segoe UI', 9), bg='#1a1a2e', fg='#ffcc00',
                                   insertbackground='#ffcc00', justify='right')
            actual_entry.pack(side=tk.LEFT, padx=3)
            actual_entry.bind('<Return>', lambda e: self._on_actual_stat_change())
            actual_entry.bind('<FocusOut>', lambda e: self._on_actual_stat_change())

            # Gap label (Actual - Final)
            gap_label = tk.Label(row_frame, text="0", font=('Segoe UI', 9),
                                fg='#ff6b6b', bg='#2a2a4e', width=10, anchor='e')
            gap_label.pack(side=tk.LEFT, padx=3)

            self.comparison_rows[stat_key] = {
                'calc_label': calc_label,
                'final_label': final_label,
                'gap_label': gap_label,
                'is_pct': is_pct,
                'calc_key': calc_key,
                'adj_key': adj_key,
            }

        # Buttons row
        btn_frame = tk.Frame(self.comparison_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(btn_frame, text="Apply Adjustments", command=self._apply_all_adjustments,
                 bg='#4a9eff', fg='white', font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Auto-Fill from Gap", command=self._auto_fill_adjustments,
                 bg='#6a4a8a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset Adjustments", command=self._reset_adjustments,
                 bg='#8a4a4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        # Initial update
        self._update_comparison_display()

    def _on_actual_stat_change(self):
        """Handle when an actual stat value changes."""
        self._update_comparison_display()
        self.save_actual_stats()

    def _on_adjustment_change(self, adj_key: str):
        """Handle when a manual adjustment value changes."""
        try:
            val = float(self.manual_stat_vars[adj_key].get())
            self.manual_stat_adjustments[adj_key] = val
        except ValueError:
            pass
        self._update_comparison_display()

    def _apply_all_adjustments(self):
        """Apply all manual adjustments and save."""
        for adj_key in self.manual_stat_adjustments:
            if adj_key in self.manual_stat_vars:
                try:
                    val = float(self.manual_stat_vars[adj_key].get())
                    self.manual_stat_adjustments[adj_key] = val
                except ValueError:
                    pass
        self.save_manual_adjustments()
        self.update_damage()
        self._update_comparison_display()

    def _auto_fill_adjustments(self):
        """Auto-fill adjustments based on gap between calculated and actual."""
        for stat_key, row_data in self.comparison_rows.items():
            adj_key = row_data.get('adj_key')
            if not adj_key or adj_key not in self.manual_stat_adjustments:
                continue

            calc_key = row_data['calc_key']

            # Get current calculated value (without adjustments)
            stats = self._get_calculated_stats_for_priority()

            # Handle special cases
            if calc_key == 'total_dex':
                continue  # Can't auto-fill total, it's derived
            elif calc_key == 'total_attack':
                continue  # Can't auto-fill total, it's derived

            calculated = stats.get(calc_key, 0)

            try:
                actual = self.actual_stat_vars[stat_key].get()
            except:
                continue

            # Gap is what we need to add
            gap = actual - calculated

            # Update the adjustment
            self.manual_stat_adjustments[adj_key] = gap
            if adj_key in self.manual_stat_vars:
                self.manual_stat_vars[adj_key].set(str(gap))

        self.save_manual_adjustments()
        self.update_damage()
        self._update_comparison_display()

    def _reset_adjustments(self):
        """Reset all manual adjustments to zero."""
        for adj_key in self.manual_stat_adjustments:
            self.manual_stat_adjustments[adj_key] = 0.0
            if adj_key in self.manual_stat_vars:
                self.manual_stat_vars[adj_key].set("0")
        self.save_manual_adjustments()
        self.update_damage()
        self._update_comparison_display()

    def _update_comparison_display(self):
        """Update the comparison display with current calculated values.

        IMPORTANT: Uses _get_calculated_stats_for_priority() which pulls ONLY
        from modeled sources (equipment, artifacts, weapons, hero power, guild,
        companions, passives, maple rank) - NOT from damage calc sliders.
        """
        # Use calculated stats from modeled sources ONLY
        stats = self._get_calculated_stats_for_priority()

        # Get base calculated values
        dex_flat = stats['dex_flat']
        dex_percent = stats['dex_percent']
        attack_flat = stats.get('attack_flat', 0)
        attack_percent = stats.get('weapon_atk_pct', 0)

        # Calculate totals from base values (for "Calculated" column)
        total_dex_calc = dex_flat * (1 + dex_percent / 100)
        total_attack_calc = stats.get('base_atk', 0)

        # Get adjustments for component stats
        adj = self.manual_stat_adjustments
        dex_flat_adj = adj.get('dex_flat', 0)
        dex_pct_adj = adj.get('dex_percent', 0)
        attack_flat_adj = adj.get('attack_flat', 0)

        # Calculate adjusted totals (for "Final" column of derived stats)
        adjusted_dex_flat = dex_flat + dex_flat_adj
        adjusted_dex_pct = dex_percent + dex_pct_adj
        total_dex_final = adjusted_dex_flat * (1 + adjusted_dex_pct / 100)

        adjusted_attack_flat = attack_flat + attack_flat_adj
        # For total attack, we need to apply ATK% to adjusted flat attack
        total_attack_final = adjusted_attack_flat * (1 + attack_percent / 100) if attack_percent > 0 else total_attack_calc

        # Get final damage from stats
        total_fd_pct = stats.get('final_damage', 0)

        # Baseline values for stats that have them
        # These baselines are added to the bonus values to match in-game display
        BASE_MIN_DMG = 60.0   # Baseline min damage %
        BASE_MAX_DMG = 100.0  # Baseline max damage %
        BASE_CRIT_DMG = 30.0  # Baseline crit damage %

        # Map calc_key to actual calculated values (raw, before adjustments)
        # For min/max/crit damage, add baselines to match in-game totals
        calc_values = {
            'total_dex': total_dex_calc,
            'dex_flat': dex_flat,
            'dex_percent': dex_percent,
            'total_attack': total_attack_calc,
            'attack_flat': attack_flat,
            'attack_percent': attack_percent,
            'damage_percent': stats['damage_percent'],
            'boss_damage': stats['boss_damage'],
            'normal_damage': stats.get('normal_damage', 0),
            'crit_rate': stats.get('crit_rate', 0),
            'crit_damage': stats['crit_damage'] + BASE_CRIT_DMG,  # Add 30% baseline
            'defense_pen': stats['defense_pen'],
            'final_damage': total_fd_pct,
            'skill_damage': stats.get('skill_damage', 0),
            'min_dmg_mult': stats.get('min_dmg_mult', 0) + BASE_MIN_DMG,  # Add 60% baseline
            'max_dmg_mult': stats.get('max_dmg_mult', 0) + BASE_MAX_DMG,  # Add 100% baseline
            'attack_speed': stats.get('attack_speed', 0),
            'accuracy': stats.get('accuracy', 0),
        }

        # Map calc_key to final values (after adjustments, for derived stats)
        final_values = {
            'total_dex': total_dex_final,
            'total_attack': total_attack_final,
        }

        for stat_key, row_data in self.comparison_rows.items():
            calc_key = row_data['calc_key']
            is_pct = row_data['is_pct']
            adj_key = row_data.get('adj_key')

            calculated = calc_values.get(calc_key, 0)

            # For derived stats (total_dex, total_attack), use pre-computed final values
            if calc_key in final_values:
                final_value = final_values[calc_key]
                adjustment = final_value - calculated  # Show the effective adjustment
            else:
                # Get adjustment value for direct stats
                adjustment = 0
                if adj_key and adj_key in self.manual_stat_adjustments:
                    adjustment = self.manual_stat_adjustments[adj_key]
                # Final = calculated + adjustment
                final_value = calculated + adjustment

            try:
                actual = self.actual_stat_vars[stat_key].get()
            except:
                actual = 0

            # Gap is now Actual - Final (what's still missing after adjustments)
            gap = actual - final_value

            # Format values
            if is_pct:
                calc_str = f"{calculated:.1f}%"
                final_str = f"{final_value:.1f}%"
                gap_str = f"{gap:+.1f}%" if abs(gap) >= 0.05 else "0%"
            else:
                calc_str = f"{calculated:,.0f}"
                final_str = f"{final_value:,.0f}"
                gap_str = f"{gap:+,.0f}" if abs(gap) >= 0.5 else "0"

            # Update labels
            row_data['calc_label'].config(text=calc_str)
            if 'final_label' in row_data:
                row_data['final_label'].config(text=final_str)
            row_data['gap_label'].config(text=gap_str)

            # Color code the gap
            if abs(gap) < 0.5:
                gap_color = '#00ff88'  # Green - matched
            elif gap > 0:
                gap_color = '#ff6b6b'  # Red - we're missing stats
            else:
                gap_color = '#ffcc00'  # Yellow - we have more than actual (model error?)

            row_data['gap_label'].config(fg=gap_color)

    def _build_character_stats_display(self):
        """Build the character stats display panels.

        IMPORTANT: Uses _get_calculated_stats_for_priority() which pulls ONLY
        from modeled sources - NOT from damage calc sliders.
        """
        # Clear existing
        for widget in self.char_stats_display.winfo_children():
            widget.destroy()

        # Get all stats from MODELED SOURCES ONLY (not sliders!)
        stats = self._get_calculated_stats_for_priority()
        maple_rank = self.get_maple_rank_stats_total()
        companion = self.get_companion_stats_total()
        guild = self.get_guild_stats_total()
        passive = self.get_passive_stats_total()
        artifact = self.get_artifact_stats_total()
        hero_power = self.get_hero_power_stats_total()
        hero_power_passive = self.get_hero_power_passive_stats_total()
        equip_base = self.get_equipment_base_stats_total()
        pot = self.get_potential_stats_total()
        equip_sets = self.get_equipment_sets_stats_total()

        # Store labels for updating
        self.char_stat_labels = {}

        # =====================================================================
        # SECTION 1: Primary Combat Stats (CLICKABLE for breakdown)
        # =====================================================================
        self._char_stats_section_header("Primary Combat Stats  (click for breakdown)")

        primary_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        primary_frame.pack(fill=tk.X, pady=5)

        # Map display names to stat keys for breakdown
        primary_stats = [
            ("Base Attack", f"{stats['base_atk']:,.0f}", "#ffaa00", "base_atk"),
            ("Flat DEX", f"{stats['dex_flat']:,.0f}", "#00ff88", "dex_flat"),
            ("DEX %", f"{stats['dex_percent']:.1f}%", "#00ff88", "dex_percent"),
            ("Damage %", f"{stats['damage_percent']:.1f}%", "#ff6b6b", "damage_percent"),
            ("Boss Damage %", f"{stats['boss_damage']:.1f}%", "#ff4444", "boss_damage"),
            ("Crit Damage %", f"{stats['crit_damage']:.1f}%", "#ffcc00", "crit_damage"),
            ("Defense Pen %", f"{stats['defense_pen']:.1f}%", "#cc88ff", "defense_pen"),
            ("Final Damage %", f"{stats['final_damage']:.1f}%", "#ff88ff", "final_damage"),
        ]

        for name, value, color, stat_key in primary_stats:
            row = tk.Frame(primary_frame, bg='#2a2a4e', cursor='hand2')
            row.pack(fill=tk.X, padx=10, pady=2)

            name_lbl = tk.Label(row, text=f"▸ {name}", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                    width=22, anchor='w', cursor='hand2')
            name_lbl.pack(side=tk.LEFT)

            lbl = tk.Label(row, text=value, font=('Segoe UI', 10, 'bold'),
                          fg=color, bg='#2a2a4e', width=15, anchor='e', cursor='hand2')
            lbl.pack(side=tk.RIGHT)
            self.char_stat_labels[name] = lbl

            # Bind click event to show breakdown - use lambda with default arg to capture stat_key
            for widget in [row, name_lbl, lbl]:
                widget.bind('<Button-1>', lambda e, sk=stat_key: self._show_calculated_stat_breakdown(sk))
                # Hover effect
                widget.bind('<Enter>', lambda e, w=row: w.configure(bg='#3a3a5e'))
                widget.bind('<Leave>', lambda e, w=row: w.configure(bg='#2a2a4e'))

            # Also update child backgrounds on hover
            def on_enter(e, row=row, name_lbl=name_lbl, lbl=lbl):
                row.configure(bg='#3a3a5e')
                name_lbl.configure(bg='#3a3a5e')
                lbl.configure(bg='#3a3a5e')
            def on_leave(e, row=row, name_lbl=name_lbl, lbl=lbl):
                row.configure(bg='#2a2a4e')
                name_lbl.configure(bg='#2a2a4e')
                lbl.configure(bg='#2a2a4e')
            for widget in [row, name_lbl, lbl]:
                widget.bind('<Enter>', on_enter)
                widget.bind('<Leave>', on_leave)

        # =====================================================================
        # SECTION 2: Additional Combat Stats (CLICKABLE for breakdown)
        # =====================================================================
        self._char_stats_section_header("Additional Combat Stats  (click for breakdown)")

        new_stats_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        new_stats_frame.pack(fill=tk.X, pady=5)

        # Map display names to stat keys for breakdown
        new_stats = [
            ("Crit Rate %", f"{stats.get('crit_rate', 0):.1f}%", "#ffcc00", "crit_rate"),
            ("Normal Monster Dmg %", f"{stats.get('normal_damage', 0):.1f}%", "#88ff88", "normal_damage"),
            ("Skill Damage %", f"{stats.get('skill_damage', 0):.1f}%", "#ff88ff", "skill_damage"),
            ("Min Damage Mult %", f"{stats.get('min_dmg_mult', 0):.1f}%", "#88ccff", "min_dmg_mult"),
            ("Max Damage Mult %", f"{stats.get('max_dmg_mult', 0):.1f}%", "#88ccff", "max_dmg_mult"),
            ("Attack Speed %", f"{stats.get('attack_speed', 0):.1f}%", "#00ffcc", "attack_speed"),
            ("Accuracy", f"{stats.get('accuracy', 0):.0f}", "#aaaaaa", "accuracy"),
        ]

        for name, value, color, stat_key in new_stats:
            row = tk.Frame(new_stats_frame, bg='#2a2a4e', cursor='hand2')
            row.pack(fill=tk.X, padx=10, pady=2)

            name_lbl = tk.Label(row, text=f"▸ {name}", font=('Segoe UI', 10), fg='#ccc', bg='#2a2a4e',
                    width=22, anchor='w', cursor='hand2')
            name_lbl.pack(side=tk.LEFT)

            lbl = tk.Label(row, text=value, font=('Segoe UI', 10, 'bold'),
                          fg=color, bg='#2a2a4e', width=15, anchor='e', cursor='hand2')
            lbl.pack(side=tk.RIGHT)
            self.char_stat_labels[name] = lbl

            # Bind click event to show breakdown
            for widget in [row, name_lbl, lbl]:
                widget.bind('<Button-1>', lambda e, sk=stat_key: self._show_calculated_stat_breakdown(sk))

            # Hover effect
            def on_enter(e, row=row, name_lbl=name_lbl, lbl=lbl):
                row.configure(bg='#3a3a5e')
                name_lbl.configure(bg='#3a3a5e')
                lbl.configure(bg='#3a3a5e')
            def on_leave(e, row=row, name_lbl=name_lbl, lbl=lbl):
                row.configure(bg='#2a2a4e')
                name_lbl.configure(bg='#2a2a4e')
                lbl.configure(bg='#2a2a4e')
            for widget in [row, name_lbl, lbl]:
                widget.bind('<Enter>', on_enter)
                widget.bind('<Leave>', on_leave)

        # =====================================================================
        # SECTION 3: Maple Rank Breakdown
        # =====================================================================
        self._char_stats_section_header("Maple Rank Contribution")

        mr_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        mr_frame.pack(fill=tk.X, pady=5)

        mr_stats = [
            ("Main Stat (Regular)", f"+{maple_rank.get('main_stat_regular', 0):,.0f}", "#00ff88"),
            ("Main Stat (Special)", f"+{maple_rank.get('main_stat_special', 0):,.0f}", "#00ff88"),
            ("Damage %", f"+{maple_rank.get('damage_percent', 0):.1f}%", "#ff6b6b"),
            ("Boss Damage %", f"+{maple_rank.get('boss_damage', 0):.1f}%", "#ff4444"),
            ("Normal Damage %", f"+{maple_rank.get('normal_damage', 0):.1f}%", "#88ff88"),
            ("Crit Rate %", f"+{maple_rank.get('crit_rate', 0):.1f}%", "#ffcc00"),
            ("Crit Damage %", f"+{maple_rank.get('crit_damage', 0):.1f}%", "#ffcc00"),
            ("Skill Damage %", f"+{maple_rank.get('skill_damage', 0):.1f}%", "#ff88ff"),
            ("Min Dmg Mult %", f"+{maple_rank.get('min_dmg_mult', 0):.1f}%", "#88ccff"),
            ("Max Dmg Mult %", f"+{maple_rank.get('max_dmg_mult', 0):.1f}%", "#88ccff"),
            ("Attack Speed %", f"+{maple_rank.get('attack_speed', 0):.1f}%", "#00ffcc"),
            ("Accuracy", f"+{maple_rank.get('accuracy', 0):.0f}", "#aaaaaa"),
        ]

        for name, value, color in mr_stats:
            row = tk.Frame(mr_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 4: Companion Contribution
        # =====================================================================
        self._char_stats_section_header("Companion Contribution")

        comp_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        comp_frame.pack(fill=tk.X, pady=5)

        comp_stats = [
            ("Flat Main Stat (2nd Job Inv)", f"+{companion.get('flat_main_stat', 0):,.0f}", "#00ff88"),
            ("Flat Attack (Basic/1st Inv)", f"+{companion.get('flat_attack', 0):,.0f}", "#ffaa00"),
            ("Damage % (3rd+4th Job Inv)", f"+{companion.get('damage', 0):.1f}%", "#ff6b6b"),
            ("Boss Damage % (On-Equip)", f"+{companion.get('boss_damage', 0):.1f}%", "#ff4444"),
            ("Normal Damage % (On-Equip)", f"+{companion.get('normal_damage', 0):.1f}%", "#88ff88"),
            ("Crit Rate % (On-Equip)", f"+{companion.get('crit_rate', 0):.1f}%", "#ffcc00"),
            ("Min Dmg Mult % (On-Equip)", f"+{companion.get('min_dmg_mult', 0):.1f}%", "#88ccff"),
            ("Max Dmg Mult % (On-Equip)", f"+{companion.get('max_dmg_mult', 0):.1f}%", "#88ccff"),
            ("Attack Speed % (On-Equip)", f"+{companion.get('attack_speed', 0):.1f}%", "#00ffcc"),
        ]

        for name, value, color in comp_stats:
            row = tk.Frame(comp_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=28, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 5: Guild Contribution
        # =====================================================================
        self._char_stats_section_header("Guild Contribution")

        guild_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        guild_frame.pack(fill=tk.X, pady=5)

        guild_stats = [
            ("Damage %", f"+{guild.get('damage', 0):.1f}%", "#ff6b6b"),
            ("Boss Damage %", f"+{guild.get('boss_damage', 0):.1f}%", "#ff4444"),
            ("Crit Damage %", f"+{guild.get('crit_damage', 0):.1f}%", "#ffcc00"),
            ("Defense Pen %", f"+{guild.get('def_pen', 0):.1f}%", "#cc88ff"),
            ("Final Damage %", f"+{guild.get('final_damage', 0):.1f}%", "#ff88ff"),
            ("Main Stat %", f"+{guild.get('main_stat_pct', 0):.1f}%", "#00ff88"),
            ("Flat Attack", f"+{guild.get('attack_flat', 0):,.0f}", "#ffaa00"),
        ]

        for name, value, color in guild_stats:
            row = tk.Frame(guild_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 6: Hero Power Contribution
        # =====================================================================
        self._char_stats_section_header("Hero Power Contribution")

        hp_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        hp_frame.pack(fill=tk.X, pady=5)

        hp_stats = [
            ("Damage %", f"+{hero_power.get('damage', 0):.1f}%", "#ff6b6b"),
            ("Boss Damage %", f"+{hero_power.get('boss_damage', 0):.1f}%", "#ff4444"),
            ("Crit Damage %", f"+{hero_power.get('crit_damage', 0):.1f}%", "#ffcc00"),
            ("Defense Pen %", f"+{hero_power.get('def_pen', 0):.1f}%", "#cc88ff"),
            ("Main Stat (Flat)", f"+{hero_power.get('main_stat_pct', 0):,.0f}", "#00ff88"),  # This is FLAT main stat despite the key name
            ("Attack %", f"+{hero_power.get('attack_pct', 0):.1f}%", "#ffaa00"),
        ]

        for name, value, color in hp_stats:
            row = tk.Frame(hp_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 7: Artifact Contribution
        # =====================================================================
        self._char_stats_section_header("Artifact Contribution")

        art_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        art_frame.pack(fill=tk.X, pady=5)

        art_stats = [
            ("Damage %", f"+{artifact.get('damage', 0) * 100:.1f}%", "#ff6b6b"),
            ("Boss Damage %", f"+{artifact.get('boss_damage', 0) * 100:.1f}%", "#ff4444"),
            ("Normal Damage %", f"+{artifact.get('normal_damage', 0) * 100:.1f}%", "#88ff88"),
            ("Crit Damage %", f"+{artifact.get('crit_damage', 0) * 100:.1f}%", "#ffcc00"),
            ("Defense Pen %", f"+{artifact.get('def_pen', 0) * 100:.1f}%", "#cc88ff"),
            ("Basic Attack Damage %", f"+{artifact.get('basic_attack_damage', 0) * 100:.1f}%", "#ff88ff"),
            ("Max Damage Mult %", f"+{artifact.get('max_damage_mult', 0) * 100:.1f}%", "#88ccff"),
            ("Flat Main Stat", f"+{artifact.get('main_stat_flat', 0):,.0f}", "#00ff88"),
            ("Flat Attack", f"+{artifact.get('attack_flat', 0):,.0f}", "#ffaa00"),
        ]

        for name, value, color in art_stats:
            row = tk.Frame(art_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 8: Equipment Base/Sub Stats Contribution
        # =====================================================================
        self._char_stats_section_header("Equipment Base & Sub Stats")

        equip_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        equip_frame.pack(fill=tk.X, pady=5)

        equip_stats = [
            ("Attack (Main Stat)", f"+{equip_base.get('attack', 0):,.0f}", "#ffaa00"),
            ("Attack (Sub Stat)", f"+{equip_base.get('attack_flat', 0):,.0f}", "#ffaa00"),
            ("Boss Damage %", f"+{equip_base.get('boss_damage', 0):.1f}%", "#ff4444"),
            ("Normal Damage %", f"+{equip_base.get('normal_damage', 0):.1f}%", "#88ff88"),
            ("Crit Rate %", f"+{equip_base.get('crit_rate', 0):.1f}%", "#ffcc00"),
            ("Crit Damage %", f"+{equip_base.get('crit_damage', 0):.1f}%", "#ffcc00"),
            ("Damage % (Special)", f"+{equip_base.get('damage_pct', 0):.1f}%", "#ff6b6b"),
            ("Final Damage % (Special)", f"+{equip_base.get('final_damage', 0):.1f}%", "#ff88ff"),
            ("Main Stat (3rd Stat)", f"+{equip_base.get('main_stat', 0):,.0f}", "#00ff88"),
            ("All Skills (Special)", f"+{equip_base.get('all_skills', 0)}", "#00ffcc"),
            ("+1st Job Skills", f"+{equip_base.get('first_job', 0)}", "#aaddff"),
            ("+2nd Job Skills", f"+{equip_base.get('second_job', 0)}", "#aaddff"),
            ("+3rd Job Skills", f"+{equip_base.get('third_job', 0)}", "#aaddff"),
            ("+4th Job Skills", f"+{equip_base.get('fourth_job', 0)}", "#aaddff"),
        ]

        for name, value, color in equip_stats:
            row = tk.Frame(equip_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=26, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 9: Equipment Potentials Contribution
        # =====================================================================
        self._char_stats_section_header("Equipment Potentials")

        pot_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        pot_frame.pack(fill=tk.X, pady=5)

        pot_stats = [
            ("Damage %", f"+{pot.get('damage_percent', 0):.1f}%", "#ff6b6b"),
            ("Boss Damage %", f"+{pot.get('boss_damage', 0):.1f}%", "#ff4444"),
            ("Crit Damage %", f"+{pot.get('crit_damage', 0):.1f}%", "#ffcc00"),
            ("Crit Rate %", f"+{pot.get('crit_rate', 0):.1f}%", "#ffcc00"),
            ("Defense Pen %", f"+{pot.get('defense_pen', 0):.1f}%", "#cc88ff"),
            ("Final Damage %", f"+{pot.get('final_damage', 0):.1f}%", "#ff88ff"),
            ("Main Stat %", f"+{pot.get('dex_percent', 0):.1f}%", "#00ff88"),
            ("Flat Main Stat", f"+{pot.get('dex_flat', 0):,.0f}", "#00ff88"),
            ("All Skills", f"+{pot.get('all_skills', 0)}", "#00ffcc"),
        ]

        for name, value, color in pot_stats:
            row = tk.Frame(pot_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 10: Hero Power Passive Stats
        # =====================================================================
        self._char_stats_section_header("Hero Power Passive Stats (Leveled)")

        hpp_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        hpp_frame.pack(fill=tk.X, pady=5)

        hpp_stats = [
            ("Flat Main Stat", f"+{hero_power_passive.get('main_stat_flat', 0):,.0f}", "#00ff88"),
            ("Damage %", f"+{hero_power_passive.get('damage_percent', 0):.1f}%", "#ff6b6b"),
            ("Flat Attack", f"+{hero_power_passive.get('attack_flat', 0):,.0f}", "#ffaa00"),
            ("Accuracy", f"+{hero_power_passive.get('accuracy', 0):.0f}", "#aaaaaa"),
        ]

        for name, value, color in hpp_stats:
            row = tk.Frame(hpp_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 11: Passive Skills Contribution
        # =====================================================================
        self._char_stats_section_header("Passive Skills Contribution")

        passive_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        passive_frame.pack(fill=tk.X, pady=5)

        passive_stats = [
            ("Damage %", f"+{passive.get('damage', 0):.1f}%", "#ff6b6b"),
            ("Boss Damage %", f"+{passive.get('boss_damage', 0):.1f}%", "#ff4444"),
            ("Crit Rate %", f"+{passive.get('crit_rate', 0):.1f}%", "#ffcc00"),
            ("Crit Damage %", f"+{passive.get('crit_damage', 0):.1f}%", "#ffcc00"),
            ("Defense Pen %", f"+{passive.get('def_pen', 0):.1f}%", "#cc88ff"),
            ("Final Damage %", f"+{passive.get('final_damage', 0):.1f}%", "#ff88ff"),
            ("Main Stat %", f"+{passive.get('main_stat_pct', 0):.1f}%", "#00ff88"),
            ("Attack %", f"+{passive.get('attack_pct', 0):.1f}%", "#ffaa00"),
        ]

        for name, value, color in passive_stats:
            row = tk.Frame(passive_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # =====================================================================
        # SECTION 12: Medals & Costumes Contribution
        # =====================================================================
        self._char_stats_section_header("Medals & Costumes")

        medal_costume_frame = tk.Frame(self.char_stats_display, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        medal_costume_frame.pack(fill=tk.X, pady=5)

        medal_stat = self.equipment_sets_config.medal_config.get_main_stat()
        costume_stat = self.equipment_sets_config.costume_config.get_main_stat()

        medal_costume_stats = [
            ("Medal Main Stat", f"+{medal_stat:,.0f}", "#ffaa00"),
            ("Costume Main Stat", f"+{costume_stat:,.0f}", "#ff66ff"),
            ("Total Main Stat", f"+{medal_stat + costume_stat:,.0f}", "#00ff88"),
        ]

        for name, value, color in medal_costume_stats:
            row = tk.Frame(medal_costume_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=1)
            tk.Label(row, text=f"  {name}", font=('Segoe UI', 9), fg='#aaa', bg='#2a2a4e',
                    width=22, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=value, font=('Segoe UI', 9),
                    fg=color, bg='#2a2a4e', width=12, anchor='e').pack(side=tk.RIGHT)

        # Note about editing in Character Settings
        note_label = tk.Label(medal_costume_frame, text="  (Edit values in Character Settings above)",
                             font=('Segoe UI', 8), fg='#666', bg='#2a2a4e')
        note_label.pack(anchor='w', padx=10, pady=3)

        # Bottom padding
        tk.Frame(self.char_stats_display, bg='#1a1a2e', height=50).pack()

    def _char_stats_section_header(self, text: str):
        """Create a section header in the character stats display."""
        header = tk.Label(self.char_stats_display, text=text,
                         font=('Segoe UI', 11, 'bold'), fg='#00d4ff', bg='#1a1a2e')
        header.pack(anchor='w', pady=(15, 5))

    def _refresh_character_stats(self):
        """Refresh the character stats display."""
        self._update_comparison_display()
        self._build_character_stats_display()

    def _on_equipment_sets_change(self, event=None):
        """Called when medal or costume inventory values change."""
        try:
            medal_val = int(self.medal_inv_var.get())
            self.equipment_sets_config.medal_config.inventory_effect = max(0, min(1500, medal_val))
        except (ValueError, AttributeError):
            pass

        try:
            costume_val = int(self.costume_inv_var.get())
            self.equipment_sets_config.costume_config.inventory_effect = max(0, min(1500, costume_val))
        except (ValueError, AttributeError):
            pass

        # Save and refresh
        self.save_equipment_sets_to_csv(silent=True)
        self.update_damage()
        self._refresh_character_stats()

    def _on_char_stats_medal_costume_change(self, event=None):
        """Called when medal or costume values change in Character Stats tab."""
        try:
            medal_val = int(self.char_stats_medal_var.get())
            self.equipment_sets_config.medal_config.inventory_effect = max(0, min(1500, medal_val))
        except (ValueError, AttributeError):
            pass

        try:
            costume_val = int(self.char_stats_costume_var.get())
            self.equipment_sets_config.costume_config.inventory_effect = max(0, min(1500, costume_val))
        except (ValueError, AttributeError):
            pass

        # Update the other tab's inputs if they exist
        if hasattr(self, 'medal_inv_var'):
            self.medal_inv_var.set(str(self.equipment_sets_config.medal_config.inventory_effect))
        if hasattr(self, 'costume_inv_var'):
            self.costume_inv_var.set(str(self.equipment_sets_config.costume_config.inventory_effect))

        # Save and refresh
        self.save_equipment_sets_to_csv(silent=True)
        self.update_damage()
        self._refresh_character_stats()

    def save_equipment_sets_to_csv(self, filepath: str = None, silent: bool = False):
        """Save equipment sets configuration to CSV."""
        if filepath is None:
            filepath = EQUIPMENT_SETS_SAVE_FILE
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["type", "value"])
                writer.writerow(["medal", self.equipment_sets_config.medal_config.inventory_effect])
                writer.writerow(["costume", self.equipment_sets_config.costume_config.inventory_effect])
            if not silent:
                messagebox.showinfo("Saved", f"Equipment sets saved to {filepath}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save: {e}")

    def load_equipment_sets_from_csv(self, filepath: str = None, silent: bool = False):
        """Load equipment sets configuration from CSV."""
        if filepath is None:
            filepath = EQUIPMENT_SETS_SAVE_FILE
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        stat_type, value = row[0], int(row[1])
                        if stat_type == "medal":
                            self.equipment_sets_config.medal_config.inventory_effect = value
                        elif stat_type == "costume":
                            self.equipment_sets_config.costume_config.inventory_effect = value
            if not silent:
                messagebox.showinfo("Loaded", f"Equipment sets loaded from {filepath}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load: {e}")

    # =========================================================================
    # UPGRADE PATH OPTIMIZER TAB
    # =========================================================================

    def build_upgrade_optimizer_tab(self):
        """Build the Upgrade Path Optimizer tab."""
        main_frame = ttk.Frame(self.upgrade_optimizer_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Two-column layout
        cols = ttk.Frame(main_frame)
        cols.pack(fill=tk.BOTH, expand=True, pady=10)

        left_col = tk.Frame(cols, bg='#1a1a2e')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_col = tk.Frame(cols, bg='#1a1a2e')
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # =====================================================================
        # LEFT COLUMN - Current State & Budget
        # =====================================================================

        # Character stats section
        self._section_header(left_col, "Character Stats (for DPS calculation)")

        stats_frame = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        stats_frame.pack(fill=tk.X, pady=5)

        # Store optimizer stat vars
        self.optimizer_stat_vars = {}

        # Create stat input rows
        stat_configs = [
            ("base_atk", "Base ATK", 50000, 0, 200000),
            ("dex_flat", "Flat DEX Pool", 18700, 0, 100000),
            ("dex_percent", "DEX %", 126.5, 0, 500),
            ("damage_percent", "Damage %", 484.1, 0, 2000),
            ("crit_damage", "Crit Damage %", 184.5, 0, 500),
            ("defense_pen", "Defense Pen %", 60.0, 0, 100),
            ("boss_damage", "Boss Damage %", 64.5, 0, 500),
            ("enemy_def", "Enemy Defense", 0.752, 0, 2),
        ]

        for key, label, default, min_val, max_val in stat_configs:
            row = tk.Frame(stats_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=10, pady=2)

            tk.Label(row, text=f"{label}:", font=('Segoe UI', 9),
                     fg='#ccc', bg='#2a2a4e', width=15, anchor=tk.W).pack(side=tk.LEFT)

            var = tk.StringVar(value=str(default))
            self.optimizer_stat_vars[key] = var

            entry = tk.Entry(row, textvariable=var, width=12,
                           font=('Consolas', 9), bg='#3a3a5a', fg='#eee',
                           insertbackground='white')
            entry.pack(side=tk.LEFT, padx=5)

        # Sync from Damage Calculator button
        tk.Button(
            stats_frame, text="Sync from Damage Calculator",
            command=self._sync_optimizer_stats_from_damage_tab,
            bg='#4a9eff', fg='white', font=('Segoe UI', 9), width=25
        ).pack(pady=8)

        # Current DPS display
        self._section_header(left_col, "Current DPS Overview")

        dps_frame = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        dps_frame.pack(fill=tk.X, pady=5)

        self.optimizer_current_dps_label = tk.Label(
            dps_frame, text="Current DPS: ---",
            font=('Segoe UI', 14, 'bold'), fg='#00ff88', bg='#2a2a4e'
        )
        self.optimizer_current_dps_label.pack(anchor=tk.W, padx=10, pady=10)

        # Budget input
        self._section_header(left_col, "Budget (Diamonds)")

        budget_frame = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        budget_frame.pack(fill=tk.X, pady=5)

        budget_row = tk.Frame(budget_frame, bg='#2a2a4e')
        budget_row.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(budget_row, text="Budget:", font=('Segoe UI', 10),
                 fg='#ccc', bg='#2a2a4e').pack(side=tk.LEFT)

        self.optimizer_budget_var = tk.StringVar(value="100000")
        budget_entry = tk.Entry(budget_row, textvariable=self.optimizer_budget_var,
                               width=15, font=('Consolas', 11),
                               bg='#3a3a5a', fg='#eee', insertbackground='white')
        budget_entry.pack(side=tk.LEFT, padx=10)

        tk.Label(budget_row, text="diamonds", font=('Segoe UI', 10),
                 fg='#888', bg='#2a2a4e').pack(side=tk.LEFT)

        # Quick budget buttons
        quick_row = tk.Frame(budget_frame, bg='#2a2a4e')
        quick_row.pack(fill=tk.X, padx=10, pady=(0, 10))

        for amount, label in [(50000, "50K"), (100000, "100K"), (250000, "250K"), (500000, "500K")]:
            tk.Button(
                quick_row, text=label,
                command=lambda a=amount: self.optimizer_budget_var.set(str(a)),
                bg='#4a4a6a', fg='white', font=('Segoe UI', 9), width=6
            ).pack(side=tk.LEFT, padx=2)

        # Analyze button
        tk.Button(
            budget_frame, text="Analyze Upgrade Options",
            command=self.run_upgrade_analysis,
            bg='#ff9f43', fg='white', font=('Segoe UI', 12, 'bold'),
            width=25
        ).pack(pady=10)

        # Equipment Summary section
        self._section_header(left_col, "Equipment Status")

        # Scrollable equipment list
        equip_container = tk.Frame(left_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        equip_container.pack(fill=tk.BOTH, expand=True, pady=5)

        equip_canvas = tk.Canvas(equip_container, bg='#2a2a4e', height=300,
                                highlightthickness=0)
        scrollbar = ttk.Scrollbar(equip_container, orient="vertical",
                                 command=equip_canvas.yview)
        self.optimizer_equip_frame = tk.Frame(equip_canvas, bg='#2a2a4e')

        self.optimizer_equip_frame.bind(
            "<Configure>",
            lambda e: equip_canvas.configure(scrollregion=equip_canvas.bbox("all"))
        )

        equip_canvas.create_window((0, 0), window=self.optimizer_equip_frame, anchor="nw")
        equip_canvas.configure(yscrollcommand=scrollbar.set)

        equip_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Build equipment summary display
        self._build_optimizer_equipment_summary()

        # =====================================================================
        # RIGHT COLUMN - Recommendations
        # =====================================================================

        self._section_header(right_col, "Recommended Upgrade Path")

        path_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        path_frame.pack(fill=tk.X, pady=5)

        # Scrollable text widget for recommendations
        self.optimizer_path_text = tk.Text(
            path_frame, height=12, width=55, bg='#2a2a4e', fg='#aaa',
            font=('Consolas', 10), wrap=tk.WORD, state=tk.DISABLED,
            highlightthickness=0, borderwidth=0
        )
        path_scrollbar = ttk.Scrollbar(path_frame, orient="vertical",
                                        command=self.optimizer_path_text.yview)
        self.optimizer_path_text.configure(yscrollcommand=path_scrollbar.set)

        self.optimizer_path_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        path_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Set initial text
        self.optimizer_path_text.config(state=tk.NORMAL)
        self.optimizer_path_text.insert(tk.END, "Click 'Analyze Upgrade Options' to see recommendations")
        self.optimizer_path_text.config(state=tk.DISABLED)

        # Expected gains summary
        self._section_header(right_col, "Expected Gains")

        gains_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        gains_frame.pack(fill=tk.X, pady=5)

        self.optimizer_gains_label = tk.Label(
            gains_frame, text="---",
            font=('Segoe UI', 11), fg='#ccc', bg='#2a2a4e',
            justify=tk.LEFT
        )
        self.optimizer_gains_label.pack(anchor=tk.W, padx=10, pady=10)

        # All options ranked
        self._section_header(right_col, "All Upgrade Options (by Efficiency)")

        options_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        options_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollable options list
        options_canvas = tk.Canvas(options_frame, bg='#2a2a4e', height=250,
                                  highlightthickness=0)
        options_scrollbar = ttk.Scrollbar(options_frame, orient="vertical",
                                         command=options_canvas.yview)
        self.optimizer_options_frame = tk.Frame(options_canvas, bg='#2a2a4e')

        self.optimizer_options_frame.bind(
            "<Configure>",
            lambda e: options_canvas.configure(scrollregion=options_canvas.bbox("all"))
        )

        options_canvas.create_window((0, 0), window=self.optimizer_options_frame, anchor="nw")
        options_canvas.configure(yscrollcommand=options_scrollbar.set)

        options_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        options_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Efficiency explanation
        self._section_header(right_col, "Efficiency Guide")

        guide_frame = tk.Frame(right_col, bg='#2a2a4e', bd=1, relief=tk.RAISED)
        guide_frame.pack(fill=tk.X, pady=5)

        guide_text = (
            "Efficiency = DPS Gain % per 1000 diamonds\n\n"
            "Higher efficiency = better value\n"
            "Recommended path picks highest efficiency\n"
            "options that fit within your budget."
        )
        tk.Label(
            guide_frame, text=guide_text,
            font=('Consolas', 9), fg='#888', bg='#2a2a4e',
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=10, pady=10)

        # Initial update
        self._update_optimizer_dps_display()

    def _build_optimizer_equipment_summary(self):
        """Build the equipment summary display."""
        # Clear existing
        for widget in self.optimizer_equip_frame.winfo_children():
            widget.destroy()

        # Header
        header = tk.Frame(self.optimizer_equip_frame, bg='#3a3a5a')
        header.pack(fill=tk.X, padx=5, pady=(5, 2))

        tk.Label(header, text="Slot", font=('Segoe UI', 9, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=10).pack(side=tk.LEFT)
        tk.Label(header, text="Reg Tier", font=('Segoe UI', 9, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=10).pack(side=tk.LEFT)
        tk.Label(header, text="Bonus Tier", font=('Segoe UI', 9, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=10).pack(side=tk.LEFT)
        tk.Label(header, text="Status", font=('Segoe UI', 9, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=15).pack(side=tk.LEFT)

        # Equipment rows
        for slot in EQUIPMENT_SLOTS:
            equip = self.equipment.get(slot)
            if not equip:
                continue

            row = tk.Frame(self.optimizer_equip_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=5, pady=1)

            # Slot name
            tk.Label(row, text=slot.capitalize(), font=('Segoe UI', 9),
                     fg='#ccc', bg='#2a2a4e', width=10, anchor=tk.W).pack(side=tk.LEFT)

            # Regular tier with color
            reg_tier = equip.tier.value if hasattr(equip.tier, 'value') else str(equip.tier)
            tier_color = get_tier_color(equip.tier)
            tk.Label(row, text=reg_tier.capitalize(), font=('Segoe UI', 9),
                     fg=tier_color, bg='#2a2a4e', width=10).pack(side=tk.LEFT)

            # Bonus tier with color
            bonus_tier = equip.bonus_tier.value if hasattr(equip.bonus_tier, 'value') else str(equip.bonus_tier)
            bonus_color = get_tier_color(equip.bonus_tier)
            tk.Label(row, text=bonus_tier.capitalize(), font=('Segoe UI', 9),
                     fg=bonus_color, bg='#2a2a4e', width=10).pack(side=tk.LEFT)

            # Status (lines count)
            lines_count = len(equip.lines)
            bonus_count = len(equip.bonus_lines)
            status = f"{lines_count}/3 + {bonus_count}/3"
            tk.Label(row, text=status, font=('Consolas', 9),
                     fg='#888', bg='#2a2a4e', width=15).pack(side=tk.LEFT)

    def _sync_optimizer_stats_from_damage_tab(self):
        """Sync stats from the Damage Calculator tab to the optimizer."""
        try:
            stats = self._get_damage_stats()

            # Map to optimizer stat vars
            self.optimizer_stat_vars["base_atk"].set(str(int(stats.get("base_atk", 50000))))
            self.optimizer_stat_vars["dex_flat"].set(str(int(stats.get("dex_flat", 18700))))
            self.optimizer_stat_vars["dex_percent"].set(f"{stats.get('dex_percent', 126.5):.1f}")
            self.optimizer_stat_vars["damage_percent"].set(f"{stats.get('damage_percent', 484.1):.1f}")
            self.optimizer_stat_vars["crit_damage"].set(f"{stats.get('crit_damage', 184.5):.1f}")
            self.optimizer_stat_vars["defense_pen"].set(f"{stats.get('defense_pen', 60.0):.1f}")
            self.optimizer_stat_vars["boss_damage"].set(f"{stats.get('boss_damage', 64.5):.1f}")
            self.optimizer_stat_vars["enemy_def"].set(f"{stats.get('enemy_def', 0.752):.3f}")

            self._update_optimizer_dps_display()
            messagebox.showinfo("Success", "Stats synced from Damage Calculator")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to sync stats: {e}")

    def _get_optimizer_stats(self) -> Dict:
        """Get stats from the optimizer tab inputs."""
        try:
            return {
                "base_atk": float(self.optimizer_stat_vars["base_atk"].get()),
                "dex_flat": float(self.optimizer_stat_vars["dex_flat"].get()),
                "dex_percent": float(self.optimizer_stat_vars["dex_percent"].get()),
                "damage_percent": float(self.optimizer_stat_vars["damage_percent"].get()),
                "hex_stacks": 3,  # Default hex stacks
                "damage_amp": 23.2,  # Default damage amp
                "boss_damage": float(self.optimizer_stat_vars["boss_damage"].get()),
                "fd_sources": [13.0, 6.0],  # [Calculated FD, Guild FD]
                "crit_damage": float(self.optimizer_stat_vars["crit_damage"].get()),
                "defense_pen": float(self.optimizer_stat_vars["defense_pen"].get()),
                "enemy_def": float(self.optimizer_stat_vars["enemy_def"].get()),
            }
        except ValueError as e:
            raise ValueError(f"Invalid stat value: {e}")

    def _update_optimizer_dps_display(self):
        """Update the current DPS display in optimizer tab."""
        try:
            # Use full calculated stats for consistency with Cube Optimizer
            stats = self._get_damage_stats()
            dps = self._calc_damage(stats)
            self.optimizer_current_dps_label.config(
                text=f"Current DPS: {dps:,.0f}"
            )
        except:
            self.optimizer_current_dps_label.config(text="Current DPS: ---")

    def run_upgrade_analysis(self):
        """Run the upgrade path analysis."""
        try:
            budget = float(self.optimizer_budget_var.get().replace(",", ""))
        except ValueError:
            messagebox.showwarning("Warning", "Please enter a valid budget number")
            return

        try:
            # Get current DPS from full calculated stats (same as Cube Optimizer)
            # This includes all modeled sources: equipment, potentials, artifacts, hero power, etc.
            # plus any manual adjustments from Character Stats tab
            stats = self._get_damage_stats()
            current_dps = self._calc_damage(stats)

            # Create optimizer with callback to cube analyzer
            # Uses _get_damage_stats for consistency with Cube Optimizer
            optimizer = UpgradeOptimizer(
                calc_dps_func=self._calc_damage,
                get_stats_func=self._get_damage_stats,  # Use full calculated stats, not manual inputs
                equipment_state=self.equipment,
                equipment_items=self.equipment_items,
                hero_power_config=self.hero_power_config,
                current_dps=current_dps,
                artifact_config=self.artifact_config,
                analyze_potential_func=self._analyze_potential_for_slot,
                hero_power_level_config=self.hero_power_level_config,
                hero_power_presets=self.hero_power_presets,
                combat_mode=self.combat_mode.value,
            )

            # Analyze all options
            all_options = optimizer.analyze_all_upgrades()

            # Get optimal path within budget
            path = optimizer.get_optimal_path(budget)

            # Update displays
            self._display_upgrade_path(path, budget)
            self._display_all_options(all_options)
            self._update_optimizer_dps_display()
            self._build_optimizer_equipment_summary()

        except Exception as e:
            import traceback
            error_msg = f"Error during analysis:\n{str(e)}\n\n{traceback.format_exc()}"
            messagebox.showerror("Analysis Error", error_msg)
            print(error_msg)  # Also print to console for debugging

    def _display_upgrade_path(self, path: UpgradePath, budget: float):
        """Display the recommended upgrade path with detailed DPS breakdown."""
        if not path.upgrades:
            self.optimizer_path_text.config(state=tk.NORMAL)
            self.optimizer_path_text.delete(1.0, tk.END)
            self.optimizer_path_text.insert(tk.END,
                "No upgrades recommended within budget.\n"
                "Try increasing your budget or check if equipment is already maxed."
            )
            self.optimizer_path_text.config(state=tk.DISABLED)
            self.optimizer_gains_label.config(text="No upgrades selected")
            return

        # Build path description with detailed breakdown
        lines = ["═" * 50]
        lines.append("RECOMMENDED UPGRADE PATH")
        lines.append("═" * 50 + "\n")

        total_gain = 0.0
        for i, upgrade in enumerate(path.upgrades, 1):
            # Type icon and colors
            type_info = {
                UpgradeType.CUBE_REGULAR: ("🎲 CUBE-REG", "Regular Potential"),
                UpgradeType.CUBE_BONUS: ("🎲 CUBE-BON", "Bonus Potential"),
                UpgradeType.STARFORCE: ("⭐ STARFORCE", "Star Enhancement"),
                UpgradeType.HERO_POWER: ("🏅 HERO PWR", "Hero Power Line"),
                UpgradeType.ARTIFACT: ("🏺 ARTIFACT", "Artifact Upgrade"),
                UpgradeType.ARTIFACT_POTENTIAL: ("🔮 ART-POT", "Artifact Potential"),
                UpgradeType.HERO_POWER_POTENTIAL: ("⚡ HP-POT", "Hero Power Potential"),
            }
            icon, type_name = type_info.get(upgrade.upgrade_type, ("❓", "Unknown"))

            lines.append(f"#{i}. {icon}")
            lines.append(f"    Target: {upgrade.target.upper()}")
            lines.append(f"    Type: {type_name}")

            if upgrade.current_state:
                lines.append(f"    Change: {upgrade.current_state}")

            lines.append("")
            lines.append(f"    📈 DPS Impact:")
            lines.append(f"    ├─ Expected Gain: +{upgrade.expected_dps_gain_pct:.2f}% DPS")

            # Show details if available
            details = upgrade.details or {}
            if 'current_dps_pct' in details:
                lines.append(f"    ├─ Current: +{details['current_dps_pct']:.2f}% DPS")
            if 'expected_dps_pct' in details:
                lines.append(f"    ├─ After Upgrade: +{details['expected_dps_pct']:.2f}% DPS")
            if 'max_possible_pct' in details:
                lines.append(f"    └─ Max Possible: +{details['max_possible_pct']:.2f}% DPS")

            lines.append("")
            lines.append(f"    💎 Cost Analysis:")
            lines.append(f"    ├─ Cost: {upgrade.cost_diamonds:,.0f} diamonds")
            lines.append(f"    └─ Efficiency: {upgrade.efficiency:.4f} (DPS%/1K diamonds)")

            total_gain += upgrade.expected_dps_gain_pct
            lines.append("")
            lines.append("─" * 50)
            lines.append("")

        # Update the scrollable text widget
        self.optimizer_path_text.config(state=tk.NORMAL)
        self.optimizer_path_text.delete(1.0, tk.END)
        self.optimizer_path_text.insert(tk.END, "\n".join(lines))
        self.optimizer_path_text.config(state=tk.DISABLED)
        # Scroll to top
        self.optimizer_path_text.see("1.0")

        # Update gains summary
        gains_text = (
            f"Total Cost: {path.total_cost:,.0f} / {budget:,.0f} diamonds\n"
            f"Remaining: {path.remaining_budget:,.0f} diamonds\n\n"
            f"Expected DPS Gain: +{path.total_dps_gain:.2f}%\n"
            f"Average Efficiency: {path.average_efficiency:.3f} (DPS%/1K diamonds)"
        )
        self.optimizer_gains_label.config(text=gains_text)

    def _display_all_options(self, options: List[UpgradeOption]):
        """Display all upgrade options ranked by efficiency with detailed DPS info."""
        # Clear existing
        for widget in self.optimizer_options_frame.winfo_children():
            widget.destroy()

        if not options:
            tk.Label(
                self.optimizer_options_frame,
                text="No upgrade options available",
                font=('Segoe UI', 10), fg='#888', bg='#2a2a4e'
            ).pack(padx=10, pady=10)
            return

        # Header row
        header = tk.Frame(self.optimizer_options_frame, bg='#3a3a5a')
        header.pack(fill=tk.X, padx=5, pady=(5, 2))

        tk.Label(header, text="#", font=('Segoe UI', 8, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=3).pack(side=tk.LEFT)
        tk.Label(header, text="Type", font=('Segoe UI', 8, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=5).pack(side=tk.LEFT)
        tk.Label(header, text="Target", font=('Segoe UI', 8, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=30, anchor=tk.W).pack(side=tk.LEFT)
        tk.Label(header, text="DPS Gain", font=('Segoe UI', 8, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=10).pack(side=tk.LEFT)
        tk.Label(header, text="Efficiency", font=('Segoe UI', 8, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=10).pack(side=tk.LEFT)
        tk.Label(header, text="Cost", font=('Segoe UI', 8, 'bold'),
                 fg='#ffd700', bg='#3a3a5a', width=8).pack(side=tk.LEFT)

        # Type colors
        type_colors = {
            UpgradeType.CUBE_REGULAR: "#4a9eff",
            UpgradeType.CUBE_BONUS: "#9d65c9",
            UpgradeType.STARFORCE: "#ffd700",
            UpgradeType.HERO_POWER: "#ff6b6b",
            UpgradeType.ARTIFACT: "#ff9d4a",
            UpgradeType.ARTIFACT_POTENTIAL: "#c77dff",
            UpgradeType.HERO_POWER_POTENTIAL: "#00d4ff",
        }

        for i, option in enumerate(options[:25]):  # Show top 25
            # Main row
            row = tk.Frame(self.optimizer_options_frame, bg='#2a2a4e')
            row.pack(fill=tk.X, padx=5, pady=1)

            # Rank with color based on efficiency
            rank_color = "#00ff88" if i < 3 else "#ffd700" if i < 10 else "#888"
            tk.Label(row, text=f"{i+1}", font=('Consolas', 9, 'bold'),
                     fg=rank_color, bg='#2a2a4e', width=3).pack(side=tk.LEFT)

            # Type indicator
            type_color = type_colors.get(option.upgrade_type, "#ccc")
            type_short = {
                UpgradeType.CUBE_REGULAR: "REG",
                UpgradeType.CUBE_BONUS: "BON",
                UpgradeType.STARFORCE: "SF",
                UpgradeType.HERO_POWER: "HP",
                UpgradeType.ARTIFACT: "ART",
                UpgradeType.ARTIFACT_POTENTIAL: "APT",
                UpgradeType.HERO_POWER_POTENTIAL: "HPP",
            }.get(option.upgrade_type, "?")

            tk.Label(row, text=type_short, font=('Consolas', 8, 'bold'),
                     fg=type_color, bg='#2a2a4e', width=5).pack(side=tk.LEFT)

            # Target/Description
            desc = option.target.upper()
            if option.current_state:
                desc += f" ({option.current_state})"
            desc = desc[:28] + ".." if len(desc) > 30 else desc
            tk.Label(row, text=desc, font=('Segoe UI', 9),
                     fg='#ccc', bg='#2a2a4e', width=30, anchor=tk.W).pack(side=tk.LEFT)

            # DPS Gain with color
            dps_color = "#00ff88" if option.expected_dps_gain_pct > 1.0 else "#ffd700" if option.expected_dps_gain_pct > 0.5 else "#ff6b6b"
            tk.Label(row, text=f"+{option.expected_dps_gain_pct:.2f}%", font=('Consolas', 9),
                     fg=dps_color, bg='#2a2a4e', width=10).pack(side=tk.LEFT)

            # Efficiency with color
            eff_color = "#00ff88" if option.efficiency > 0.01 else "#ffd700" if option.efficiency > 0.005 else "#ff6b6b"
            tk.Label(row, text=f"{option.efficiency:.4f}", font=('Consolas', 9),
                     fg=eff_color, bg='#2a2a4e', width=10).pack(side=tk.LEFT)

            # Cost
            cost_str = f"{option.cost_diamonds/1000:.1f}K" if option.cost_diamonds >= 1000 else f"{option.cost_diamonds:.0f}"
            tk.Label(row, text=cost_str, font=('Consolas', 9),
                     fg='#888', bg='#2a2a4e', width=8).pack(side=tk.LEFT)

            # Details row (if available)
            details = option.details or {}
            if details.get('current_dps_pct') or details.get('max_possible_pct'):
                detail_row = tk.Frame(self.optimizer_options_frame, bg='#252545')
                detail_row.pack(fill=tk.X, padx=5, pady=0)

                detail_text = "    "
                if 'current_dps_pct' in details:
                    detail_text += f"Current: +{details['current_dps_pct']:.1f}%  "
                if 'max_possible_pct' in details:
                    detail_text += f"Max: +{details['max_possible_pct']:.1f}%  "
                if 'room_to_improve' in details:
                    detail_text += f"Room: +{details['room_to_improve']:.1f}%"

                tk.Label(detail_row, text=detail_text, font=('Consolas', 8),
                         fg='#666', bg='#252545', anchor=tk.W).pack(side=tk.LEFT, padx=25)


    # =========================================================================
    # COMPANIONS TAB
    # =========================================================================

    def build_companions_tab(self):
        """Build the Companions tab for tracking companion levels and bonuses."""
        main_frame = ttk.Frame(self.companions_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrollable canvas for the whole tab
        canvas = tk.Canvas(main_frame, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Three-column layout
        cols = tk.Frame(scrollable_frame, bg='#1a1a2e')
        cols.pack(fill=tk.BOTH, expand=True, pady=10)

        left_col = tk.Frame(cols, bg='#1a1a2e')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        mid_col = tk.Frame(cols, bg='#1a1a2e')
        mid_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        right_col = tk.Frame(cols, bg='#1a1a2e')
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # Store companion level entries
        self.companion_level_entries = {}

        # =====================================================================
        # LEFT COLUMN: 4th Job Companions (max level 10)
        # =====================================================================
        self._section_header(left_col, "4th Job Companions (max 10)")

        fourth_job_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        fourth_job_frame.pack(fill=tk.X, pady=5, padx=5)

        fourth_job_companions = [
            ("bowmaster_4th", "Bowmaster", "ATK SPD"),
            ("marksman_4th", "Marksman", "Status Effect"),
            ("night_lord_4th", "Night Lord", "Boss Dmg"),
            ("shadower_4th", "Shadower", "Min Dmg"),
            ("hero_4th", "Hero", "Max Dmg"),
            ("dark_knight_4th", "Dark Knight", "Boss Dmg"),
            ("arch_mage_fp_4th", "Arch Mage F/P", "Crit Rate"),
            ("arch_mage_il_4th", "Arch Mage I/L", "Normal Dmg"),
        ]

        for key, name, on_equip in fourth_job_companions:
            row = tk.Frame(fourth_job_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(row, text=f"{name}:", bg='#252545', fg='#aaa', width=14, anchor='w').pack(side=tk.LEFT)

            entry = tk.Entry(row, width=4, bg='#333', fg='#fff', insertbackground='#fff', justify='center')
            entry.insert(0, "0")
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind('<KeyRelease>', self._on_companion_level_change)
            self.companion_level_entries[key] = entry

            tk.Label(row, text=f"/10  ({on_equip})", bg='#252545', fg='#666', font=('Segoe UI', 8)).pack(side=tk.LEFT)

        # =====================================================================
        # LEFT COLUMN: 1st Job Companions (max level 50)
        # =====================================================================
        self._section_header(left_col, "1st Job Companions (max 50)")

        first_job_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        first_job_frame.pack(fill=tk.X, pady=5, padx=5)

        first_job_companions = [
            ("bowmaster_1st", "Bowmaster", "Flat ATK"),
            ("marksman_1st", "Marksman", "Flat ATK"),
            ("night_lord_1st", "Night Lord", "Flat ATK"),
            ("shadower_1st", "Shadower", "Flat ATK"),
            ("hero_1st", "Hero", "Flat ATK"),
            ("dark_knight_1st", "Dark Knight", "Flat ATK"),
            ("arch_mage_fp_1st", "Arch Mage F/P", "Flat ATK"),
            ("arch_mage_il_1st", "Arch Mage I/L", "Flat ATK"),
        ]

        for key, name, on_equip in first_job_companions:
            row = tk.Frame(first_job_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(row, text=f"{name}:", bg='#252545', fg='#aaa', width=14, anchor='w').pack(side=tk.LEFT)

            entry = tk.Entry(row, width=4, bg='#333', fg='#fff', insertbackground='#fff', justify='center')
            entry.insert(0, "0")
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind('<KeyRelease>', self._on_companion_level_change)
            self.companion_level_entries[key] = entry

            tk.Label(row, text=f"/50  ({on_equip})", bg='#252545', fg='#666', font=('Segoe UI', 8)).pack(side=tk.LEFT)

        # =====================================================================
        # LEFT COLUMN: Basic Companions (max level 100)
        # =====================================================================
        self._section_header(left_col, "Basic Companions (max 100)")

        basic_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        basic_frame.pack(fill=tk.X, pady=5, padx=5)

        basic_companions = [
            ("aspiring_warrior", "Aspiring Warrior", "Flat ATK"),
            ("aspiring_mage", "Aspiring Mage", "Flat ATK"),
            ("aspiring_bowman", "Aspiring Bowman", "Flat ATK"),
            ("aspiring_thief", "Aspiring Thief", "Flat ATK"),
        ]

        for key, name, on_equip in basic_companions:
            row = tk.Frame(basic_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(row, text=f"{name}:", bg='#252545', fg='#aaa', width=14, anchor='w').pack(side=tk.LEFT)

            entry = tk.Entry(row, width=4, bg='#333', fg='#fff', insertbackground='#fff', justify='center')
            entry.insert(0, "0")
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind('<KeyRelease>', self._on_companion_level_change)
            self.companion_level_entries[key] = entry

            tk.Label(row, text=f"/100  ({on_equip})", bg='#252545', fg='#666', font=('Segoe UI', 8)).pack(side=tk.LEFT)

        # =====================================================================
        # MIDDLE COLUMN: 3rd Job Companions (max level 10)
        # =====================================================================
        self._section_header(mid_col, "3rd Job Companions (max 10)")

        third_job_frame = tk.Frame(mid_col, bg='#252545', relief='ridge', bd=1)
        third_job_frame.pack(fill=tk.X, pady=5, padx=5)

        third_job_companions = [
            ("bowmaster_3rd", "Bowmaster", "ATK SPD"),
            ("marksman_3rd", "Marksman", "Status Effect"),
            ("night_lord_3rd", "Night Lord", "Boss Dmg"),
            ("shadower_3rd", "Shadower", "Min Dmg"),
            ("hero_3rd", "Hero", "Max Dmg"),
            ("dark_knight_3rd", "Dark Knight", "Accuracy"),
            ("arch_mage_fp_3rd", "Arch Mage F/P", "Crit Rate"),
            ("arch_mage_il_3rd", "Arch Mage I/L", "Normal Dmg"),
        ]

        for key, name, on_equip in third_job_companions:
            row = tk.Frame(third_job_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(row, text=f"{name}:", bg='#252545', fg='#aaa', width=14, anchor='w').pack(side=tk.LEFT)

            entry = tk.Entry(row, width=4, bg='#333', fg='#fff', insertbackground='#fff', justify='center')
            entry.insert(0, "0")
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind('<KeyRelease>', self._on_companion_level_change)
            self.companion_level_entries[key] = entry

            tk.Label(row, text=f"/10  ({on_equip})", bg='#252545', fg='#666', font=('Segoe UI', 8)).pack(side=tk.LEFT)

        # =====================================================================
        # RIGHT COLUMN: 2nd Job Companions (max level 30)
        # =====================================================================
        self._section_header(right_col, "2nd Job Companions (max 30)")

        second_job_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        second_job_frame.pack(fill=tk.X, pady=5, padx=5)

        second_job_companions = [
            ("bowmaster_2nd", "Bowmaster", "ATK SPD"),
            ("marksman_2nd", "Marksman", "Status Effect"),
            ("night_lord_2nd", "Night Lord", "Boss Dmg"),
            ("shadower_2nd", "Shadower", "Min Dmg"),
            ("hero_2nd", "Hero", "Max Dmg"),
            ("dark_knight_2nd", "Dark Knight", "Accuracy"),
            ("arch_mage_fp_2nd", "Arch Mage F/P", "Crit Rate"),
            ("arch_mage_il_2nd", "Arch Mage I/L", "Normal Dmg"),
        ]

        for key, name, on_equip in second_job_companions:
            row = tk.Frame(second_job_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(row, text=f"{name}:", bg='#252545', fg='#aaa', width=14, anchor='w').pack(side=tk.LEFT)

            entry = tk.Entry(row, width=4, bg='#333', fg='#fff', insertbackground='#fff', justify='center')
            entry.insert(0, "0")
            entry.pack(side=tk.LEFT, padx=5)
            entry.bind('<KeyRelease>', self._on_companion_level_change)
            self.companion_level_entries[key] = entry

            tk.Label(row, text=f"/30  ({on_equip})", bg='#252545', fg='#666', font=('Segoe UI', 8)).pack(side=tk.LEFT)

        # =====================================================================
        # LEFT COLUMN: Equipped Companions (7 slots)
        # =====================================================================
        self._section_header(left_col, "Equipped Companions (7 Slots)")

        equipped_frame = tk.Frame(left_col, bg='#252545', relief='ridge', bd=1)
        equipped_frame.pack(fill=tk.X, pady=5, padx=5)

        self.equipped_companion_combos = []
        slot_names = ["Main", "Sub 1", "Sub 2", "Sub 3", "Sub 4", "Sub 5", "Sub 6"]

        # Get all companion names for dropdown
        all_companion_options = ["None"] + [COMPANIONS[key].name for key in COMPANIONS.keys()]

        for i, slot_name in enumerate(slot_names):
            row = tk.Frame(equipped_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=2)

            tk.Label(row, text=f"{slot_name}:", bg='#252545', fg='#aaa', width=6, anchor='w').pack(side=tk.LEFT)

            combo = ttk.Combobox(row, values=all_companion_options, width=20, state='readonly')
            combo.set("None")
            combo.pack(side=tk.LEFT, padx=5)
            combo.bind('<<ComboboxSelected>>', self._on_equipped_companion_change)
            self.equipped_companion_combos.append(combo)

        # =====================================================================
        # MIDDLE COLUMN: Stats Summary
        # =====================================================================
        self._section_header(mid_col, "Companion Stats Summary")

        summary_frame = tk.Frame(mid_col, bg='#252545', relief='ridge', bd=1)
        summary_frame.pack(fill=tk.X, pady=5, padx=5)

        self.companion_summary_labels = {}

        # Inventory stats (always active)
        tk.Label(summary_frame, text="--- Inventory Effects (Always Active) ---",
                 bg='#252545', fg='#ffd700', font=('Segoe UI', 9, 'bold')).pack(pady=(5, 2))

        inv_stats = [
            ("Basic + 1st: Attack", "total_attack"),
            ("All Tiers: Max HP", "total_max_hp"),
            ("2nd Job: Main Stat", "second_job_main_stat"),
            ("3rd Job: Damage %", "third_job_damage"),
            ("4th Job: Damage %", "fourth_job_damage"),
            ("Total Damage %", "total_damage"),
        ]

        for label, key in inv_stats:
            row = tk.Frame(summary_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=1)
            tk.Label(row, text=f"{label}:", bg='#252545', fg='#aaa', width=20, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="0", bg='#252545', fg='#7fff7f', font=('Segoe UI', 10, 'bold'))
            lbl.pack(side=tk.LEFT)
            self.companion_summary_labels[key] = lbl

        # On-equip stats
        tk.Label(summary_frame, text="--- On-Equip Effects (Equipped Only) ---",
                 bg='#252545', fg='#ffd700', font=('Segoe UI', 9, 'bold')).pack(pady=(10, 2))

        equip_stats = [
            ("Attack Speed %", "on_equip_attack_speed"),
            ("Boss Damage %", "on_equip_boss_damage"),
            ("Normal Damage %", "on_equip_normal_damage"),
            ("Min Dmg Mult %", "on_equip_min_dmg_mult"),
            ("Max Dmg Mult %", "on_equip_max_dmg_mult"),
            ("Crit Rate %", "on_equip_crit_rate"),
            ("Flat Attack", "on_equip_flat_attack"),
        ]

        for label, key in equip_stats:
            row = tk.Frame(summary_frame, bg='#252545')
            row.pack(fill=tk.X, padx=5, pady=1)
            tk.Label(row, text=f"{label}:", bg='#252545', fg='#aaa', width=20, anchor='w').pack(side=tk.LEFT)
            lbl = tk.Label(row, text="0", bg='#252545', fg='#7fff7f', font=('Segoe UI', 10, 'bold'))
            lbl.pack(side=tk.LEFT)
            self.companion_summary_labels[key] = lbl

        # =====================================================================
        # RIGHT COLUMN: Info and Tips
        # =====================================================================
        self._section_header(right_col, "Companion System Info")

        info_frame = tk.Frame(right_col, bg='#252545', relief='ridge', bd=1)
        info_frame.pack(fill=tk.X, pady=5, padx=5)

        info_text = """
How Companions Work:

INVENTORY EFFECTS (Always Active):
• Basic: Attack + Max HP
• 1st Job: Attack + Max HP
• 2nd Job: Main Stat + Max HP
• 3rd Job: Damage %
• 4th Job: Damage %

ON-EQUIP EFFECTS (Equipped Only):
• Only 7 companions can be equipped
• 1 Main slot + 6 Sub slots
• Basic/1st Job: Flat Attack
• 2nd/3rd/4th Job: Varies by class

MAX LEVELS:
• Basic: 100
• 1st Job: 50
• 2nd Job: 30
• 3rd Job: 10
• 4th Job: 10

TIP: For stages, equip ATK SPD companions
(Bowmaster at each job tier)
        """

        tk.Label(info_frame, text=info_text, bg='#252545', fg='#888',
                 font=('Segoe UI', 9), justify='left').pack(anchor='w', padx=5, pady=5)

        # =====================================================================
        # BOTTOM: Save/Load/Update buttons
        # =====================================================================
        btn_frame = tk.Frame(scrollable_frame, bg='#1a1a2e')
        btn_frame.pack(fill=tk.X, pady=10, padx=5)

        tk.Button(btn_frame, text="Save Companions", command=self.save_companions_to_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Load Companions", command=self.load_companions_from_csv,
                  bg='#4a4a7a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Update Stats", command=self._update_companion_stats,
                  bg='#7a4a4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Set All to Max", command=self._set_all_companions_max,
                  bg='#4a7a4a', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)

        # Initialize displays
        self._update_companion_stats()

    def _on_companion_level_change(self, event=None):
        """Called when a companion level entry changes."""
        self._update_companion_config()
        self._update_companion_stats()
        self.update_damage()
        self.auto_save_companions()

    def _on_equipped_companion_change(self, event=None):
        """Called when an equipped companion slot changes."""
        self._update_companion_config()
        self._update_companion_stats()
        self.update_damage()
        self.auto_save_companions()

    def _update_companion_config(self):
        """Update companion_config from UI values."""
        # Build inventory from level entries
        inventory = []
        for key, entry in self.companion_level_entries.items():
            try:
                level = int(entry.get())
                if level > 0 and key in COMPANIONS:
                    instance = create_companion_instance(key, level)
                    if instance:
                        inventory.append(instance)
            except ValueError:
                pass

        self.companion_config.inventory = inventory

        # Update equipped companions
        for i, combo in enumerate(self.equipped_companion_combos):
            selected = combo.get()
            if selected == "None":
                self.companion_config.equipped[i] = None
            else:
                # Find the companion key by name
                for key, definition in COMPANIONS.items():
                    if definition.name == selected:
                        # Get level from entry
                        level = 1
                        if key in self.companion_level_entries:
                            try:
                                level = int(self.companion_level_entries[key].get())
                            except ValueError:
                                level = 1
                        self.companion_config.equipped[i] = create_companion_instance(key, max(1, level))
                        break

    def _update_companion_stats(self):
        """Update the companion stats display."""
        # Get inventory summary
        summary = self.companion_config.get_inventory_summary()

        # Update inventory stat labels
        self.companion_summary_labels["total_attack"].config(text=f"{summary.get('total_attack', 0):.0f}")
        total_hp = summary.get('basic_max_hp', 0) + summary.get('1st_job_max_hp', 0) + summary.get('2nd_job_max_hp', 0)
        self.companion_summary_labels["total_max_hp"].config(text=f"{total_hp:.0f}")
        self.companion_summary_labels["second_job_main_stat"].config(text=f"{summary['2nd_job_main_stat']:.0f}")
        self.companion_summary_labels["third_job_damage"].config(text=f"{summary.get('3rd_job_damage', 0):.1f}%")
        self.companion_summary_labels["fourth_job_damage"].config(text=f"{summary.get('4th_job_damage', 0):.1f}%")
        self.companion_summary_labels["total_damage"].config(text=f"{summary.get('total_damage', 0):.1f}%")

        # Get on-equip stats
        on_equip = self.companion_config.get_on_equip_stats()

        self.companion_summary_labels["on_equip_attack_speed"].config(text=f"{on_equip.get('attack_speed', 0):.1f}%")
        self.companion_summary_labels["on_equip_boss_damage"].config(text=f"{on_equip.get('boss_damage', 0):.1f}%")
        self.companion_summary_labels["on_equip_normal_damage"].config(text=f"{on_equip.get('normal_damage', 0):.1f}%")
        self.companion_summary_labels["on_equip_min_dmg_mult"].config(text=f"{on_equip.get('min_dmg_mult', 0):.1f}%")
        self.companion_summary_labels["on_equip_max_dmg_mult"].config(text=f"{on_equip.get('max_dmg_mult', 0):.1f}%")
        self.companion_summary_labels["on_equip_crit_rate"].config(text=f"{on_equip.get('crit_rate', 0):.1f}%")
        self.companion_summary_labels["on_equip_flat_attack"].config(text=f"{on_equip.get('flat_attack', 0):.0f}")

    def _set_all_companions_max(self):
        """Set all companion levels to their respective max levels."""
        max_levels = {
            "_4th": 10,
            "_3rd": 10,
            "_2nd": 30,
            "_1st": 50,
            "aspiring_": 100,  # Basic tier
        }
        for key, entry in self.companion_level_entries.items():
            max_level = 10  # default
            if key.startswith("aspiring_"):
                max_level = 100
            else:
                for suffix, level in max_levels.items():
                    if key.endswith(suffix):
                        max_level = level
                        break
            entry.delete(0, tk.END)
            entry.insert(0, str(max_level))
        self._on_companion_level_change()

    def save_companions_to_csv(self, filepath=None, silent=False):
        """Save companion configuration to CSV."""
        if filepath is None:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                initialfile="companions_save.csv"
            )
            if not filepath:
                return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["type", "key", "name", "tier", "level", "max_level", "slot"])

                # Save all companion levels grouped by tier
                tier_order = ["aspiring_", "_4th", "_3rd", "_2nd", "_1st"]
                tier_names = {
                    "aspiring_": "Basic",
                    "_4th": "4th Job",
                    "_3rd": "3rd Job",
                    "_2nd": "2nd Job",
                    "_1st": "1st Job"
                }
                max_levels = {
                    "aspiring_": 100,
                    "_4th": 10,
                    "_3rd": 10,
                    "_2nd": 30,
                    "_1st": 50
                }

                for tier_key in tier_order:
                    for key, entry in self.companion_level_entries.items():
                        # Check if key matches this tier
                        is_match = (tier_key == "aspiring_" and key.startswith(tier_key)) or \
                                   (tier_key != "aspiring_" and key.endswith(tier_key))
                        if is_match:
                            try:
                                level = int(entry.get())
                            except ValueError:
                                level = 0

                            name = COMPANIONS[key].name if key in COMPANIONS else key
                            tier = tier_names.get(tier_key, "Unknown")
                            max_lvl = max_levels.get(tier_key, 10)
                            writer.writerow(["inventory", key, name, tier, level, max_lvl, ""])

                # Save equipped companions
                slot_names = ["Main", "Sub 1", "Sub 2", "Sub 3", "Sub 4", "Sub 5", "Sub 6"]
                for i, combo in enumerate(self.equipped_companion_combos):
                    selected = combo.get()
                    if selected != "None":
                        # Find key by name
                        for key, definition in COMPANIONS.items():
                            if definition.name == selected:
                                writer.writerow(["equipped", key, selected, "", "", "", slot_names[i]])
                                break

            if not silent:
                messagebox.showinfo("Success", f"Companions saved to {filepath}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to save companions: {e}")

    def load_companions_from_csv(self, filepath=None, silent=False):
        """Load companion configuration from CSV."""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                filetypes=[("CSV files", "*.csv")],
                initialfile="companions_save.csv"
            )
            if not filepath:
                return

        try:
            # Reset all entries to 0
            for entry in self.companion_level_entries.values():
                entry.delete(0, tk.END)
                entry.insert(0, "0")

            # Reset equipped to None
            for combo in self.equipped_companion_combos:
                combo.set("None")

            equipped_data = {}
            slot_name_to_idx = {"Main": 0, "Sub 1": 1, "Sub 2": 2, "Sub 3": 3, "Sub 4": 4, "Sub 5": 5, "Sub 6": 6}

            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)  # Read header

                # Detect format: new format has 7 columns, old has 4
                is_new_format = len(header) >= 7

                for row in reader:
                    if len(row) < 2:
                        continue

                    row_type = row[0]
                    key = row[1]

                    if row_type == "inventory" and key in self.companion_level_entries:
                        # New format: type, key, name, tier, level, max_level, slot
                        # Old format: type, key, level, slot
                        if is_new_format and len(row) >= 5:
                            level = row[4]  # level is in column 5
                        elif len(row) >= 3:
                            level = row[2]  # level is in column 3 (old format)
                        else:
                            level = "0"

                        self.companion_level_entries[key].delete(0, tk.END)
                        self.companion_level_entries[key].insert(0, str(level))

                    elif row_type == "equipped":
                        # New format: slot name in column 7
                        # Old format: slot index in column 4
                        if is_new_format and len(row) >= 7:
                            slot_name = row[6]
                            slot = slot_name_to_idx.get(slot_name, -1)
                        elif len(row) >= 4:
                            try:
                                slot = int(row[3])
                            except (ValueError, IndexError):
                                slot = -1
                        else:
                            slot = -1

                        if slot >= 0 and key in COMPANIONS:
                            equipped_data[slot] = COMPANIONS[key].name

            # Apply equipped data
            for slot, name in equipped_data.items():
                if slot < len(self.equipped_companion_combos):
                    self.equipped_companion_combos[slot].set(name)

            self._on_companion_level_change()
            if not silent:
                messagebox.showinfo("Success", f"Companions loaded from {filepath}")

        except FileNotFoundError:
            pass  # Silent fail for auto-load
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to load companions: {e}")

    def auto_load_companions(self):
        """Auto-load companions from default save file if it exists."""
        if os.path.exists(COMPANIONS_SAVE_FILE):
            try:
                self.load_companions_from_csv(COMPANIONS_SAVE_FILE, silent=True)
            except Exception:
                pass  # Silent fail

    def auto_save_companions(self):
        """Auto-save companions to default save file."""
        try:
            self.save_companions_to_csv(COMPANIONS_SAVE_FILE, silent=True)
        except Exception:
            pass  # Silent fail

    # =========================================================================
    # STAT EFFICIENCY GUIDE TAB
    # =========================================================================

    def build_stat_efficiency_tab(self):
        """Build the Stat Efficiency Guide tab."""
        main_frame = tk.Frame(self.stat_efficiency_tab, bg='#1a1a2e')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create scrollable canvas
        canvas = tk.Canvas(main_frame, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#1a1a2e')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Title
        title = tk.Label(scrollable_frame, text="Stat Efficiency Guide",
                         font=('Segoe UI', 18, 'bold'), fg='#00d4ff', bg='#1a1a2e')
        title.pack(pady=(15, 5))

        subtitle = tk.Label(scrollable_frame,
                            text="Long-term stat distribution strategy for optimal end-game builds",
                            font=('Segoe UI', 10), fg='#888', bg='#1a1a2e')
        subtitle.pack(pady=(0, 15))

        # Section 1: Where to Get Each Stat
        self._build_stat_distribution_section(scrollable_frame)

        # Separator
        sep1 = tk.Frame(scrollable_frame, bg='#444', height=2)
        sep1.pack(fill=tk.X, padx=20, pady=15)

        # Section 2: Equipment Slot Quick Reference
        self._build_equipment_slot_section(scrollable_frame)

        # Separator
        sep2 = tk.Frame(scrollable_frame, bg='#444', height=2)
        sep2.pack(fill=tk.X, padx=20, pady=15)

        # Section 3: Per-System Stat Priorities
        self._build_system_priorities_section(scrollable_frame)

    def _build_stat_distribution_section(self, parent):
        """Section 1: Where to get each stat."""
        # Section header
        header = tk.Label(parent, text="WHERE TO GET EACH STAT",
                          font=('Segoe UI', 14, 'bold'), fg='#ffd700', bg='#1a1a2e')
        header.pack(pady=(10, 10), anchor=tk.W, padx=20)

        desc = tk.Label(parent,
                        text="Rankings show which system provides the most of each stat (best first)",
                        font=('Segoe UI', 9), fg='#888', bg='#1a1a2e')
        desc.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Stats to display with their rankings
        key_stats = [
            StatCategory.DAMAGE_PCT,
            StatCategory.BOSS_DAMAGE,
            StatCategory.CRIT_DAMAGE,
            StatCategory.DEF_PEN,
            StatCategory.FINAL_DAMAGE,
            StatCategory.MIN_DMG_MULT,
            StatCategory.MAX_DMG_MULT,
            StatCategory.NORMAL_DAMAGE,
        ]

        for stat in key_stats:
            stat_frame = tk.Frame(parent, bg='#2a2a4e')
            stat_frame.pack(fill=tk.X, padx=20, pady=3)

            # Stat name
            stat_label = tk.Label(stat_frame, text=f"{stat.value}:",
                                  font=('Segoe UI', 10, 'bold'),
                                  fg='#00d4ff', bg='#2a2a4e', width=18, anchor=tk.W)
            stat_label.pack(side=tk.LEFT, padx=5, pady=5)

            # Get rankings
            rankings = get_stat_rankings(stat)

            if rankings:
                # Build ranking string
                rank_parts = []
                for i, eff in enumerate(rankings[:4]):  # Top 4 sources
                    # Color based on efficiency
                    if eff.is_best_source:
                        color = '#00ff88'
                    elif eff.efficiency_pct >= 50:
                        color = '#ffd700'
                    else:
                        color = '#888'

                    # Special slot indicator
                    sys_name = eff.system.value
                    if eff.system == SystemType.EQUIPMENT:
                        # Check for special slots
                        sys_data = MAX_STAT_VALUES.get(eff.system, {}).get(stat)
                        if sys_data and sys_data.special_slot:
                            sys_name = f"Equip ({sys_data.special_slot})"

                    rank_label = tk.Label(stat_frame,
                                          text=f"{sys_name} {eff.star_rating} ({eff.max_value:.0f}%)",
                                          font=('Consolas', 9),
                                          fg=color, bg='#2a2a4e')
                    rank_label.pack(side=tk.LEFT, padx=2)

                    if i < len(rankings) - 1 and i < 3:
                        sep = tk.Label(stat_frame, text=">",
                                       font=('Consolas', 9), fg='#666', bg='#2a2a4e')
                        sep.pack(side=tk.LEFT)

            # Show insight/warning if available
            insight = STAT_INSIGHTS.get(stat, {})
            warning = insight.get("warning")
            if warning:
                warn_label = tk.Label(stat_frame, text=f" ({warning})",
                                      font=('Segoe UI', 8, 'italic'),
                                      fg='#ff6b6b', bg='#2a2a4e')
                warn_label.pack(side=tk.LEFT, padx=5)

    def _build_equipment_slot_section(self, parent):
        """Section 2: Equipment slot quick reference."""
        # Section header
        header = tk.Label(parent, text="EQUIPMENT SLOT RECOMMENDATIONS",
                          font=('Segoe UI', 14, 'bold'), fg='#ffd700', bg='#1a1a2e')
        header.pack(pady=(10, 10), anchor=tk.W, padx=20)

        desc = tk.Label(parent,
                        text="What stats to roll for on each equipment slot",
                        font=('Segoe UI', 9), fg='#888', bg='#1a1a2e')
        desc.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Get priority sorted slots
        priority_slots = get_priority_slots()

        # Group by priority tier
        tier_labels = {1: "PRIORITY SLOTS (Special Potentials)", 2: "SECONDARY (Good Specials)", 3: "STANDARD (No Special)"}

        current_tier = None
        for slot_rec in priority_slots:
            # Add tier header if changed
            if slot_rec.priority_tier != current_tier:
                current_tier = slot_rec.priority_tier
                tier_header = tk.Label(parent, text=tier_labels.get(current_tier, "OTHER"),
                                       font=('Segoe UI', 10, 'bold'),
                                       fg='#ff9500' if current_tier == 1 else '#888',
                                       bg='#1a1a2e')
                tier_header.pack(pady=(10, 5), anchor=tk.W, padx=30)

            # Slot frame
            slot_frame = tk.Frame(parent, bg='#2a2a4e')
            slot_frame.pack(fill=tk.X, padx=30, pady=2)

            # Slot name with bracket
            slot_color = '#00ff88' if current_tier == 1 else '#ffd700' if current_tier == 2 else '#ccc'
            slot_label = tk.Label(slot_frame, text=f"[{slot_rec.slot.upper()}]",
                                  font=('Consolas', 10, 'bold'),
                                  fg=slot_color, bg='#2a2a4e', width=12, anchor=tk.W)
            slot_label.pack(side=tk.LEFT, padx=5, pady=5)

            # Special stat if any
            if slot_rec.special_stat:
                special_text = f"Special: {slot_rec.special_stat} ({slot_rec.special_value_mystic}% Mystic)"
                special_label = tk.Label(slot_frame, text=special_text,
                                         font=('Segoe UI', 9),
                                         fg='#00d4ff', bg='#2a2a4e')
                special_label.pack(side=tk.LEFT, padx=5)

            # Recommendation
            rec_label = tk.Label(slot_frame, text=slot_rec.primary_recommendation,
                                 font=('Segoe UI', 9),
                                 fg='#ccc', bg='#2a2a4e')
            rec_label.pack(side=tk.LEFT, padx=10)

    def _build_system_priorities_section(self, parent):
        """Section 3: Per-system stat priorities."""
        # Section header
        header = tk.Label(parent, text="WHAT TO ROLL FOR IN EACH SYSTEM",
                          font=('Segoe UI', 14, 'bold'), fg='#ffd700', bg='#1a1a2e')
        header.pack(pady=(10, 10), anchor=tk.W, padx=20)

        desc = tk.Label(parent,
                        text="Stats ranked by relative efficiency within each system",
                        font=('Segoe UI', 9), fg='#888', bg='#1a1a2e')
        desc.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Systems to show
        systems_to_show = [
            (SystemType.EQUIPMENT, "Equipment Potentials - What to cube for"),
            (SystemType.ARTIFACTS, "Artifacts - What to roll for"),
            (SystemType.HERO_POWER, "Hero Power - What lines to keep"),
        ]

        for system, title in systems_to_show:
            # System header
            sys_frame = tk.Frame(parent, bg='#2a2a4e')
            sys_frame.pack(fill=tk.X, padx=20, pady=5)

            sys_header = tk.Label(sys_frame, text=title,
                                  font=('Segoe UI', 11, 'bold'),
                                  fg='#00d4ff', bg='#2a2a4e')
            sys_header.pack(anchor=tk.W, padx=10, pady=5)

            # Get priorities for this system
            priorities = get_system_priorities(system)

            for i, eff in enumerate(priorities[:6]):  # Top 6 stats
                row = tk.Frame(sys_frame, bg='#2a2a4e')
                row.pack(fill=tk.X, padx=20)

                # Rank
                rank_label = tk.Label(row, text=f"{i+1}.",
                                      font=('Consolas', 9),
                                      fg='#888', bg='#2a2a4e', width=3)
                rank_label.pack(side=tk.LEFT)

                # Stat name
                stat_label = tk.Label(row, text=eff.stat.value,
                                      font=('Segoe UI', 9),
                                      fg='#ccc', bg='#2a2a4e', width=16, anchor=tk.W)
                stat_label.pack(side=tk.LEFT)

                # Star rating with color
                star_color = '#00ff88' if eff.is_best_source else '#ffd700' if eff.efficiency_pct >= 50 else '#888'
                stars = tk.Label(row, text=eff.star_rating,
                                 font=('Consolas', 9),
                                 fg=star_color, bg='#2a2a4e', width=8)
                stars.pack(side=tk.LEFT)

                # Recommendation
                if eff.is_best_source:
                    rec = "BEST SOURCE - Prioritize!"
                    rec_color = '#00ff88'
                elif eff.efficiency_pct >= 50:
                    rec = "Good source"
                    rec_color = '#ffd700'
                else:
                    rec = "Get elsewhere"
                    rec_color = '#888'

                rec_label = tk.Label(row, text=rec,
                                     font=('Segoe UI', 9),
                                     fg=rec_color, bg='#2a2a4e')
                rec_label.pack(side=tk.LEFT, padx=10)

        # Footer with key insight
        footer_frame = tk.Frame(parent, bg='#1a1a2e')
        footer_frame.pack(fill=tk.X, padx=20, pady=20)

        key_insight = tk.Label(footer_frame,
                               text="KEY INSIGHT: Boss Damage% and Normal Damage% are NOT available in Equipment potentials!",
                               font=('Segoe UI', 10, 'bold'),
                               fg='#ff6b6b', bg='#1a1a2e')
        key_insight.pack()

        key_insight2 = tk.Label(footer_frame,
                                text="Use Artifacts for Boss/Normal Damage. Use Equipment for Damage%, Crit Damage (Gloves), Def Pen (Shoulder).",
                                font=('Segoe UI', 9),
                                fg='#888', bg='#1a1a2e')
        key_insight2.pack(pady=(5, 0))


# =============================================================================
# MAIN
# =============================================================================

def main():
    root = tk.Tk()
    app = MapleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
