"""
Equipment Page - Compact Layout with Cube Priority Recommendations
Matches original Tkinter app design with all potentials visible + DPS-based recommendations.
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core import ENEMY_DEFENSE_VALUES, get_enemy_defense
from utils.data_manager import save_user_data, EQUIPMENT_SLOTS
from utils.cube_analyzer import analyze_all_cube_priorities, format_stat_display, CubeRecommendation, get_distribution_data_for_slot
from utils.dps_calculator import aggregate_stats, calculate_dps
from utils.distribution_chart import (
    create_dps_distribution_chart,
    create_expanded_distribution_chart,
    get_percentile_breakdown_data,
    get_percentile_label,
    get_percentile_color,
)
from typing import Dict, Any, List

st.set_page_config(page_title="Equipment", page_icon="🛡️", layout="wide")

# Compact CSS styling
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    .equip-row {
        font-family: monospace;
        font-size: 12px;
        padding: 4px 8px;
        margin: 2px 0;
        border-radius: 4px;
        background: #1e1e1e;
        border-left: 3px solid #444;
    }
    .equip-row:hover { background: #2a2a2a; }
    .equip-row.selected { border-left-color: #ff6b6b; background: #2a2020; }
    .yellow-line { color: #ffdd44; }
    .grey-line { color: #888888; }
    .rating-low { color: #ff6666; }
    .rating-mid { color: #ffcc00; }
    .rating-high { color: #66ff66; }
    .section-header {
        font-size: 14px;
        font-weight: bold;
        color: #aaa;
        border-bottom: 1px solid #444;
        padding-bottom: 4px;
        margin-bottom: 8px;
    }
    .pot-summary {
        font-family: monospace;
        font-size: 11px;
        background: #1a1a2e;
        padding: 6px 10px;
        border-radius: 4px;
        margin: 2px 0;
    }
    .stat-box {
        background: #1e1e1e;
        padding: 8px;
        border-radius: 4px;
        text-align: center;
        margin: 4px 0;
    }
    .stat-value { font-size: 16px; font-weight: bold; color: #66ff66; }
    .stat-label { font-size: 10px; color: #888; }
    .priority-bar {
        height: 20px;
        border-radius: 4px;
        margin: 2px 0;
    }
</style>
""", unsafe_allow_html=True)

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# ============================================================================
# CONSTANTS
# ============================================================================

POTENTIAL_TIERS = ["Rare", "Epic", "Unique", "Legendary", "Mystic"]
TIER_ABBREV = {"Rare": "RAR", "Epic": "EPC", "Unique": "UNI", "Legendary": "LEG", "Mystic": "MYS"}
TIER_COLORS = {"Rare": "#5599ff", "Epic": "#cc77ff", "Unique": "#ffcc00", "Legendary": "#66ff66", "Mystic": "#ff6666"}

POTENTIAL_VALUES = {
    "dex_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "str_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "int_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "luk_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "dex_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    "str_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    "int_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    "luk_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    "damage": {"Rare": 8.0, "Epic": 12.0, "Unique": 18.0, "Legendary": 25.0, "Mystic": 35.0},
    "crit_rate": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "min_dmg_mult": {"Rare": 6.0, "Epic": 8.0, "Unique": 10.0, "Legendary": 15.0, "Mystic": 25.0},
    "max_dmg_mult": {"Rare": 6.0, "Epic": 8.0, "Unique": 10.0, "Legendary": 15.0, "Mystic": 25.0},
    "attack_speed": {"Rare": 3.5, "Epic": 4.0, "Unique": 5.0, "Legendary": 7.0, "Mystic": 10.0},
    "defense": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "max_hp": {"Epic": 12.0, "Unique": 15.0, "Legendary": 20.0, "Mystic": 25.0},
    "max_mp": {"Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
}

SPECIAL_POTENTIAL_VALUES = {
    "skill_cd": {"Epic": 0.5, "Unique": 1.0, "Legendary": 1.5, "Mystic": 2.0},
    "crit_damage": {"Unique": 20.0, "Legendary": 30.0, "Mystic": 50.0},
    "def_pen": {"Unique": 8.0, "Legendary": 12.0, "Mystic": 20.0},
    "all_skills": {"Epic": 5, "Unique": 8, "Legendary": 12, "Mystic": 16},
    "final_damage": {"Epic": 3.0, "Unique": 5.0, "Legendary": 8.0, "Mystic": 12.0},
    "buff_duration": {"Epic": 5.0, "Unique": 8.0, "Legendary": 12.0, "Mystic": 20.0},
    "stat_per_level": {"Epic": 3, "Unique": 5, "Legendary": 8, "Mystic": 12},
    "ba_targets": {"Unique": 1, "Legendary": 2, "Mystic": 3},
}

TIER_PREV = {"Rare": None, "Epic": "Rare", "Unique": "Epic", "Legendary": "Unique", "Mystic": "Legendary"}

BASE_POTENTIAL_STATS = [
    "", "dex_pct", "str_pct", "int_pct", "luk_pct",
    "dex_flat", "str_flat", "int_flat", "luk_flat",
    "damage", "crit_rate", "min_dmg_mult", "max_dmg_mult", "attack_speed",
    "defense", "max_hp", "max_mp",
]

SPECIAL_POTENTIALS = {
    "hat": {"stat": "skill_cd", "name": "Skill Cooldown"},
    "gloves": {"stat": "crit_damage", "name": "Crit Damage"},
    "shoulder": {"stat": "def_pen", "name": "Defense Pen"},
    "ring": {"stat": "all_skills", "name": "All Skills"},
    "necklace": {"stat": "all_skills", "name": "All Skills"},
    "cape": {"stat": "final_damage", "name": "Final Damage"},
    "bottom": {"stat": "final_damage", "name": "Final Damage"},
    "belt": {"stat": "buff_duration", "name": "Buff Duration"},
    "face": {"stat": "stat_per_level", "name": "Stat/Level"},
    "top": {"stat": "ba_targets", "name": "BA Targets"},
    "shoes": None,
}

MAX_POT_VALUES = {
    "damage": 25.0, "crit_rate": 12.0, "crit_damage": 30.0, "def_pen": 12.0,
    "final_damage": 8.0, "all_skills": 12, "dex_pct": 12.0, "str_pct": 12.0,
    "int_pct": 12.0, "luk_pct": 12.0, "min_dmg_mult": 15.0, "max_dmg_mult": 15.0,
}

STAT_DISPLAY = {
    "dex_pct": "DEX%", "str_pct": "STR%", "int_pct": "INT%", "luk_pct": "LUK%",
    "dex_flat": "DEX", "str_flat": "STR", "int_flat": "INT", "luk_flat": "LUK",
    "damage": "DMG%", "crit_rate": "CR%", "crit_damage": "CD%", "def_pen": "DP%",
    "final_damage": "FD%", "all_skills": "AS", "min_dmg_mult": "MinD%", "max_dmg_mult": "MaxD%",
    "attack_speed": "AS%", "defense": "DEF%", "max_hp": "HP%", "max_mp": "MP%",
    "skill_cd": "CDR", "buff_duration": "Buff%", "stat_per_level": "S/Lv", "ba_targets": "BA+",
}

# Typical cube roll values for priority calculation
TYPICAL_ROLL_VALUES = {
    "damage": 30,           # Mystic Damage % line
    "dex_pct": 15,          # Mystic Main Stat % line
    "crit_damage": 30,      # Mystic Crit Damage (special)
    "def_pen": 12,          # Defense Pen (special)
    "final_damage": 8,      # Final Damage (special)
    "min_dmg_mult": 15,     # Min Damage %
    "max_dmg_mult": 15,     # Max Damage %
    "all_skills": 12,       # All Skills (special)
}


def get_stat_value(stat: str, tier: str, is_yellow: bool, slot: str) -> float:
    """Get auto-calculated value for a stat."""
    if not stat:
        return 0.0

    if slot in SPECIAL_POTENTIALS and SPECIAL_POTENTIALS[slot]:
        special_stat = SPECIAL_POTENTIALS[slot]["stat"]
        if stat == special_stat or stat == SPECIAL_POTENTIALS[slot]["name"]:
            values = SPECIAL_POTENTIAL_VALUES.get(special_stat, {})
            if is_yellow:
                return values.get(tier, 0.0)
            else:
                prev = TIER_PREV.get(tier)
                return values.get(prev, 0.0) if prev else 0.0

    values = POTENTIAL_VALUES.get(stat, {})
    if is_yellow:
        return values.get(tier, 0.0)
    else:
        prev = TIER_PREV.get(tier)
        return values.get(prev, 0.0) if prev else 0.0


def get_stat_options(slot: str) -> list:
    """Get stat options for a slot."""
    options = BASE_POTENTIAL_STATS.copy()
    if slot in SPECIAL_POTENTIALS and SPECIAL_POTENTIALS[slot]:
        special = SPECIAL_POTENTIALS[slot]["stat"]
        options = [special] + options
    return options


def format_stat(stat: str) -> str:
    """Format stat for display."""
    if not stat:
        return "---"
    return STAT_DISPLAY.get(stat, stat.replace("_", " ").title())


def ensure_pot_fields(pots: dict) -> dict:
    """Ensure all fields exist."""
    defaults = {
        'tier': 'Legendary', 'line1_stat': '', 'line1_value': 0,
        'line2_stat': '', 'line2_value': 0, 'line3_stat': '', 'line3_value': 0,
        'line2_yellow': True, 'line3_yellow': True, 'regular_pity': 0,
        'bonus_tier': 'Legendary',
        'bonus_line1_stat': '', 'bonus_line1_value': 0,
        'bonus_line2_stat': '', 'bonus_line2_value': 0,
        'bonus_line3_stat': '', 'bonus_line3_value': 0,
        'bonus_line2_yellow': True, 'bonus_line3_yellow': True, 'bonus_pity': 0,
    }
    for k, v in defaults.items():
        if k not in pots:
            pots[k] = v
    return pots


def calculate_rating(slot: str, pots: dict, pot_type: str = "regular") -> float:
    """Calculate rating % for a potential set (0-100)."""
    prefix = "" if pot_type == "regular" else "bonus_"

    total_value = 0
    for i in range(1, 4):
        stat = pots.get(f"{prefix}line{i}_stat", "")
        val = pots.get(f"{prefix}line{i}_value", 0)
        if stat and val > 0:
            max_stat_val = MAX_POT_VALUES.get(stat, 15.0)
            total_value += min(val / max_stat_val, 1.0) * 33.33

    return min(total_value, 100)


def format_pot_line(stat: str, val: float, is_yellow: bool) -> str:
    """Format a single potential line for display."""
    if not stat or val == 0:
        return ""

    line_marker = "<span class='yellow-line'>[Y]</span>" if is_yellow else "<span class='grey-line'>[G]</span>"
    stat_name = format_stat(stat)

    if "flat" in stat or stat in ["all_skills", "ba_targets"]:
        val_str = f"+{int(val)}"
    elif stat == "skill_cd":
        val_str = f"-{val:.1f}s"
    else:
        val_str = f"+{val:.1f}%"

    return f"{line_marker} {stat_name}: {val_str}"


def build_pot_summary(slot: str, pots: dict, pot_type: str = "regular") -> str:
    """Build compact potential summary string."""
    prefix = "" if pot_type == "regular" else "bonus_"
    tier_key = "tier" if pot_type == "regular" else "bonus_tier"
    tier = pots.get(tier_key, "Legendary")
    tier_abbr = TIER_ABBREV.get(tier, "???")
    tier_color = TIER_COLORS.get(tier, "#fff")

    parts = []
    for i in range(1, 4):
        stat = pots.get(f"{prefix}line{i}_stat", "")
        val = pots.get(f"{prefix}line{i}_value", 0)
        is_yellow = True if i == 1 else pots.get(f"{prefix}line{i}_yellow", True)
        line_str = format_pot_line(stat, val, is_yellow)
        if line_str:
            parts.append(line_str)

    type_label = "Reg" if pot_type == "regular" else "Bon"
    tier_html = f"<span style='color:{tier_color}'>[{tier_abbr}]</span>"

    if parts:
        return f"{type_label}: {tier_html} {' | '.join(parts)}"
    else:
        return f"{type_label}: {tier_html} <span style='color:#666'>(empty)</span>"


def calculate_stat_priorities(pot_totals: dict) -> list:
    """
    Calculate DPS priority for each stat based on typical cube roll values.
    Returns list of (stat_name, gain_percent, color) sorted by gain.
    """
    # Base stats for calculation (reasonable defaults if not configured)
    base_damage_pct = pot_totals.get("damage", 0) + 300  # Base ~300% damage
    base_main_stat_pct = pot_totals.get("dex_pct", 0) + pot_totals.get("str_pct", 0) + pot_totals.get("int_pct", 0) + pot_totals.get("luk_pct", 0) + 100
    base_crit_damage = pot_totals.get("crit_damage", 0) + 150  # Base ~150% crit dmg
    base_def_pen = 50  # Assume 50% base def pen
    base_final_damage = pot_totals.get("final_damage", 0) + 20  # Base ~20% FD
    base_min_dmg = pot_totals.get("min_dmg_mult", 0) + 100
    base_max_dmg = pot_totals.get("max_dmg_mult", 0) + 100

    results = []

    # Test each stat with typical roll value
    tests = [
        ("Damage % (+30)", "damage", base_damage_pct, 30, "#4a9eff"),
        ("Main Stat % (+15)", "main_stat", base_main_stat_pct, 15, "#ff9f43"),
        ("Crit Damage (+30)", "crit_damage", base_crit_damage, 30, "#ffd93d"),
        ("Defense Pen (+12)", "def_pen", 100 - base_def_pen, 12, "#9d65c9"),  # Special calc
        ("Final Damage (+8)", "final_damage", 100 + base_final_damage, 8, "#ff69b4"),  # Multiplicative
        ("Min Dmg Mult (+15)", "min_dmg", base_min_dmg, 15, "#66ff66"),
        ("Max Dmg Mult (+15)", "max_dmg", base_max_dmg, 15, "#00ff88"),
    ]

    for label, stat_type, base_val, roll_val, color in tests:
        if stat_type == "def_pen":
            # Defense pen is multiplicative: remaining = remaining * (1 - new%)
            old_remaining = base_val / 100
            new_remaining = old_remaining * (1 - roll_val / 100)
            # Against high def enemy, this means more damage
            gain = ((old_remaining / new_remaining) - 1) * 100
        elif stat_type == "final_damage":
            # FD is multiplicative
            gain = (roll_val / base_val) * 100
        else:
            # Additive stats
            gain = (roll_val / base_val) * 100

        results.append((label, gain, color))

    # Sort by gain descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def auto_save():
    """Save data and update last save timestamp."""
    save_user_data(st.session_state.username, data)
    st.session_state.last_equip_save_time = datetime.now()


# ============================================================================
# DPS CALCULATION FUNCTIONS (using shared module)
# ============================================================================

def aggregate_stats_for_dps() -> Dict[str, Any]:
    """Wrapper that calls shared aggregate_stats with user data."""
    return aggregate_stats(data)


def calculate_dps_from_stats(stats: Dict[str, Any], combat_mode: str = 'stage', enemy_def: float = None) -> Dict[str, Any]:
    """Wrapper that calls shared calculate_dps with correct enemy defense."""
    # Determine enemy defense based on combat mode if not explicitly provided
    if enemy_def is None:
        if combat_mode == 'world_boss':
            enemy_def = ENEMY_DEFENSE_VALUES.get('World Boss', 6.527)
        else:
            # Get chapter number from user data
            chapter_str = getattr(data, 'chapter', 'Chapter 27')
            try:
                chapter_num = int(chapter_str.replace('Chapter ', '').strip())
            except (ValueError, AttributeError):
                chapter_num = 27
            enemy_def = get_enemy_defense(chapter_num)
    return calculate_dps(stats, combat_mode, enemy_def)


@st.cache_data(ttl=30)
def get_cube_recommendations_cached(user_data_hash: str) -> List[CubeRecommendation]:
    """Get cube recommendations with caching to avoid recalculation on every rerun."""
    return analyze_all_cube_priorities(
        user_data=data,
        aggregate_stats_func=aggregate_stats_for_dps,
        calculate_dps_func=calculate_dps_from_stats,
    )


# ============================================================================
# PAGE LAYOUT
# ============================================================================

st.title("🛡️ Equipment Potentials")

# Initialize session state
if 'selected_equip_slot' not in st.session_state:
    st.session_state.selected_equip_slot = EQUIPMENT_SLOTS[0]

# Ensure all slots have data
for slot in EQUIPMENT_SLOTS:
    if slot not in data.equipment_potentials:
        data.equipment_potentials[slot] = {}
    data.equipment_potentials[slot] = ensure_pot_fields(data.equipment_potentials[slot])

# ============================================================================
# EDITOR SECTION (Process first to update data before rendering list)
# ============================================================================

selected_slot = st.session_state.selected_equip_slot
pots = data.equipment_potentials[selected_slot]

# Track if we need to save
needs_save = False

# We'll render this later, but process the logic now
pot_type_key = st.session_state.get('pot_type_select', 'Regular')

# Main layout
col_list, col_editor = st.columns([3, 2])

# ============================================================================
# RIGHT COLUMN: Quick Set Potential Panel
# ============================================================================
with col_editor:
    st.markdown(f"<div class='section-header'>Edit: {selected_slot.upper()}</div>", unsafe_allow_html=True)

    # Slot selector
    new_slot = st.selectbox(
        "Slot", EQUIPMENT_SLOTS,
        index=EQUIPMENT_SLOTS.index(selected_slot),
        format_func=lambda x: x.upper(),
        key="slot_select"
    )
    if new_slot != selected_slot:
        st.session_state.selected_equip_slot = new_slot
        st.rerun()

    # Potential type toggle
    pot_type = st.radio("Type", ["Regular", "Bonus"], horizontal=True, key="pot_type_select")

    prefix = "" if pot_type == "Regular" else "bonus_"
    tier_key = "tier" if pot_type == "Regular" else "bonus_tier"
    pity_key = "regular_pity" if pot_type == "Regular" else "bonus_pity"

    # Tier + Pity row
    t_col, p_col = st.columns([2, 1])
    with t_col:
        current_tier_val = pots.get(tier_key, "Legendary")
        tier_idx = POTENTIAL_TIERS.index(current_tier_val) if current_tier_val in POTENTIAL_TIERS else 3
        new_tier = st.selectbox("Tier", POTENTIAL_TIERS, index=tier_idx, key="tier_select")
        if new_tier != pots.get(tier_key):
            pots[tier_key] = new_tier
            for i in range(1, 4):
                stat = pots.get(f"{prefix}line{i}_stat", "")
                if stat:
                    is_yellow = True if i == 1 else pots.get(f"{prefix}line{i}_yellow", True)
                    pots[f"{prefix}line{i}_value"] = get_stat_value(stat, new_tier, is_yellow, selected_slot)
            auto_save()
            st.rerun()

    with p_col:
        new_pity = st.number_input("Pity", 0, 999, int(pots.get(pity_key, 0)), key="pity_input")
        if new_pity != pots.get(pity_key):
            pots[pity_key] = new_pity
            auto_save()

    st.markdown("---")

    # Get stat options
    stat_options = get_stat_options(selected_slot)
    current_tier = pots.get(tier_key, "Legendary")

    # Lines 1-3
    for i in range(1, 4):
        stat_key = f"{prefix}line{i}_stat"
        val_key = f"{prefix}line{i}_value"
        yellow_key = f"{prefix}line{i}_yellow"

        is_yellow = True if i == 1 else pots.get(yellow_key, True)
        current_stat = pots.get(stat_key, "")

        yg_col, stat_col, val_col = st.columns([1, 3, 1])

        with yg_col:
            if i == 1:
                st.markdown(f"**L{i}** 🟡")
            else:
                yg_label = "🟡" if is_yellow else "⚫"
                if st.button(yg_label, key=f"yg_{prefix}{i}", help="Toggle Yellow/Grey"):
                    pots[yellow_key] = not is_yellow
                    if current_stat:
                        pots[val_key] = get_stat_value(current_stat, current_tier, not is_yellow, selected_slot)
                    auto_save()
                    st.rerun()

        with stat_col:
            try:
                stat_idx = stat_options.index(current_stat) if current_stat in stat_options else 0
            except ValueError:
                stat_idx = 0

            new_stat = st.selectbox(
                f"L{i}", stat_options, index=stat_idx,
                format_func=format_stat,
                key=f"stat_{prefix}{i}",
                label_visibility="collapsed"
            )
            if new_stat != current_stat:
                pots[stat_key] = new_stat
                pots[val_key] = get_stat_value(new_stat, current_tier, is_yellow, selected_slot)
                auto_save()
                st.rerun()

        with val_col:
            val = pots.get(val_key, 0)
            if current_stat and val > 0:
                if "flat" in current_stat or current_stat in ["all_skills", "ba_targets"]:
                    st.markdown(f"**+{int(val)}**")
                elif current_stat == "skill_cd":
                    st.markdown(f"**-{val:.1f}s**")
                else:
                    st.markdown(f"**{val:.1f}%**")
            else:
                st.markdown("—")

    # Rating display (uses fresh data)
    rating = calculate_rating(selected_slot, pots, "regular" if pot_type == "Regular" else "bonus")
    rating_color = "#66ff66" if rating >= 70 else ("#ffcc00" if rating >= 40 else "#ff6666")
    st.markdown(f"<div style='text-align:center; font-size:18px; color:{rating_color}; margin-top:10px;'>Rating: {rating:.0f}%</div>", unsafe_allow_html=True)

    # Save indicator
    if 'last_equip_save_time' in st.session_state:
        save_time = st.session_state.last_equip_save_time
        st.caption(f"Last saved: {save_time.strftime('%H:%M:%S')}")

# ============================================================================
# LEFT COLUMN: Equipment Potentials List
# ============================================================================
with col_list:
    st.markdown("<div class='section-header'>All Equipment Potentials</div>", unsafe_allow_html=True)

    for slot in EQUIPMENT_SLOTS:
        slot_pots = data.equipment_potentials.get(slot, {})

        # Calculate ratings (using current data)
        reg_rating = calculate_rating(slot, slot_pots, "regular")
        bon_rating = calculate_rating(slot, slot_pots, "bonus")

        def rating_class(r):
            if r >= 70: return "rating-high"
            elif r >= 40: return "rating-mid"
            else: return "rating-low"

        # Build summary strings
        reg_summary = build_pot_summary(slot, slot_pots, "regular")
        bon_summary = build_pot_summary(slot, slot_pots, "bonus")

        is_selected = slot == st.session_state.selected_equip_slot
        selected_class = "selected" if is_selected else ""
        slot_display = slot.upper()

        html = f"""
        <div class='equip-row {selected_class}'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <span style='font-weight:bold; width:80px;'>{slot_display}</span>
                <span class='{rating_class(reg_rating)}' style='width:50px;'>R:{reg_rating:.0f}%</span>
                <span class='{rating_class(bon_rating)}' style='width:50px;'>B:{bon_rating:.0f}%</span>
            </div>
            <div class='pot-summary'>{reg_summary}</div>
            <div class='pot-summary'>{bon_summary}</div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

        if st.button(f"Edit", key=f"edit_{slot}"):
            st.session_state.selected_equip_slot = slot
            st.rerun()

st.divider()

# ============================================================================
# BOTTOM SECTION: Stats Summary + Priority Chart
# ============================================================================

bottom_left, bottom_right = st.columns(2)

# ============================================================================
# TOTAL STATS FROM POTENTIALS
# ============================================================================
with bottom_left:
    st.markdown("<div class='section-header'>Total Stats from Potentials</div>", unsafe_allow_html=True)

    totals = {}
    for slot in EQUIPMENT_SLOTS:
        slot_pots = data.equipment_potentials.get(slot, {})

        for i in range(1, 4):
            stat = slot_pots.get(f"line{i}_stat", "")
            val = slot_pots.get(f"line{i}_value", 0)
            if stat and val > 0:
                totals[stat] = totals.get(stat, 0) + val

        for i in range(1, 4):
            stat = slot_pots.get(f"bonus_line{i}_stat", "")
            val = slot_pots.get(f"bonus_line{i}_value", 0)
            if stat and val > 0:
                totals[stat] = totals.get(stat, 0) + val

    if totals:
        sorted_stats = sorted(totals.items(), key=lambda x: x[1], reverse=True)

        cols = st.columns(3)
        for idx, (stat, val) in enumerate(sorted_stats[:9]):
            with cols[idx % 3]:
                stat_name = format_stat(stat)
                if "flat" in stat or stat in ["all_skills", "ba_targets"]:
                    val_str = f"+{int(val)}"
                elif stat == "skill_cd":
                    val_str = f"-{val:.1f}s"
                else:
                    val_str = f"{val:.1f}%"

                st.markdown(f"""
                <div class='stat-box'>
                    <div class='stat-value'>{val_str}</div>
                    <div class='stat-label'>{stat_name}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No potentials configured yet.")

# ============================================================================
# CUBE PRIORITY RECOMMENDATIONS (Which Item to Cube?)
# ============================================================================
with bottom_right:
    st.markdown("<div class='section-header'>Which Item to Cube?</div>", unsafe_allow_html=True)

    # Button to analyze cube priorities
    if st.button("Analyze Cube Priorities", type="primary"):
        with st.spinner("Analyzing all equipment..."):
            try:
                recommendations = analyze_all_cube_priorities(
                    user_data=data,
                    aggregate_stats_func=aggregate_stats_for_dps,
                    calculate_dps_func=calculate_dps_from_stats,
                )
                st.session_state.cube_recommendations = recommendations
                st.session_state.cube_analysis_time = datetime.now()
                st.success(f"Analysis complete! Found {len(recommendations)} recommendations.")
            except Exception as e:
                st.error(f"Error analyzing: {e}")
                import traceback
                st.code(traceback.format_exc())
                st.session_state.cube_recommendations = []

    # Show when analysis was last run
    if 'cube_analysis_time' in st.session_state:
        analysis_time = st.session_state.cube_analysis_time
        st.caption(f"Last analyzed: {analysis_time.strftime('%H:%M:%S')}")

    # Show recommendations if available
    if 'cube_recommendations' in st.session_state and st.session_state.cube_recommendations:
        recommendations = st.session_state.cube_recommendations

        # Number selector for how many to show
        num_to_show = st.slider("Show top N recommendations", 1, 10, 5, key="num_recs")

        for rec in recommendations[:num_to_show]:
            slot_display = rec.slot.upper()
            pot_type = "BON" if rec.is_bonus else "REG"
            tier_color = TIER_COLORS.get(rec.tier, "#fff")
            tier_upper = rec.tier.upper()

            # Efficiency indicator emoji
            if rec.dps_efficiency < 30:
                score_emoji = "🔴"
            elif rec.dps_efficiency < 60:
                score_emoji = "🟡"
            else:
                score_emoji = "🟢"

            # Room to improve
            room_to_improve = rec.best_possible_dps_gain - rec.current_dps_gain

            # Build detailed recommendation display
            with st.expander(f"#{rec.priority_rank}. {slot_display} [{tier_upper[:3]}] {pot_type}", expanded=(rec.priority_rank <= 3)):
                # DPS Impact section
                st.markdown("**📈 DPS Impact:**")
                st.markdown(f"""
                <div style='font-family:monospace; font-size:12px; color:#ccc; margin-left:16px;'>
                ├─ Current Roll: <span style='color:#66ff66'>+{rec.current_dps_gain:.2f}%</span> DPS<br>
                ├─ Best Possible: <span style='color:#ffcc00'>+{rec.best_possible_dps_gain:.2f}%</span> DPS<br>
                ├─ Room to Improve: <span style='color:#ff9999'>+{room_to_improve:.2f}%</span> DPS<br>
                └─ Efficiency: {rec.dps_efficiency:.0f}% of max {score_emoji}
                </div>
                """, unsafe_allow_html=True)

                # Current Lines section
                st.markdown("**📋 Current Lines:**")
                lines_html = "<div style='font-family:monospace; font-size:12px; color:#ccc; margin-left:16px;'>"

                for i, (stat, val, dps_gain, is_yellow) in enumerate([
                    (rec.line1_stat, rec.line1_value, rec.line1_dps_gain, rec.line1_yellow),
                    (rec.line2_stat, rec.line2_value, rec.line2_dps_gain, rec.line2_yellow),
                    (rec.line3_stat, rec.line3_value, rec.line3_dps_gain, rec.line3_yellow),
                ], 1):
                    y_marker = "Y" if is_yellow else "G"
                    y_color = "#ffdd44" if is_yellow else "#888888"
                    prefix_char = "├─" if i < 3 else "└─"

                    if stat:
                        stat_display = format_stat(stat)
                        if "flat" in stat or stat in ["all_skills", "ba_targets"]:
                            val_str = f"+{int(val)}"
                        elif stat == "skill_cd":
                            val_str = f"-{val:.1f}s"
                        else:
                            val_str = f"+{val:.1f}%"
                        lines_html += f"{prefix_char} L{i} [<span style='color:{y_color}'>{y_marker}</span>]: {stat_display} {val_str} <span style='color:#66ff66'>(+{dps_gain:.2f}% DPS)</span><br>"
                    else:
                        lines_html += f"{prefix_char} L{i} [<span style='color:{y_color}'>{y_marker}</span>]: <span style='color:#666'>Empty</span><br>"

                lines_html += "</div>"
                st.markdown(lines_html, unsafe_allow_html=True)

                # Expected Cubes section
                st.markdown("**📊 Expected Cubes:**")
                cubes_html = "<div style='font-family:monospace; font-size:12px; color:#ccc; margin-left:16px;'>"
                if rec.expected_cubes_to_improve < 500:
                    cubes_html += f"├─ Any improvement: ~{rec.expected_cubes_to_improve:.0f} cubes<br>"
                else:
                    cubes_html += f"├─ Any improvement: <span style='color:#ff6666'>Very difficult (500+ cubes)</span><br>"
                cubes_html += f"└─ {rec.prob_improve_10_cubes*100:.0f}% chance to improve in 10 cubes"
                cubes_html += "</div>"
                st.markdown(cubes_html, unsafe_allow_html=True)

                # Pity / Tier-Up section (only if not Mystic)
                if rec.tier != "Mystic" and rec.pity_threshold < 999999:
                    st.markdown("**🎲 Tier-Up Progress:**")
                    pity_pct = (rec.current_pity / rec.pity_threshold) * 100 if rec.pity_threshold > 0 else 0
                    pity_bar_len = int(pity_pct / 10)
                    pity_bar = "█" * pity_bar_len + "░" * (10 - pity_bar_len)

                    pity_html = "<div style='font-family:monospace; font-size:12px; color:#ccc; margin-left:16px;'>"
                    pity_html += f"├─ Pity: {rec.current_pity}/{rec.pity_threshold} [{pity_bar}] {pity_pct:.0f}%<br>"
                    if rec.cubes_to_tier_up < float('inf'):
                        pity_html += f"├─ Expected tier-up: ~{rec.cubes_to_tier_up:.0f} cubes<br>"
                    if rec.tier_up_score_gain > 0:
                        pity_html += f"└─ Tier-up score boost: +{rec.tier_up_score_gain:.0f} pts potential"
                    pity_html += "</div>"
                    st.markdown(pity_html, unsafe_allow_html=True)

                # Diminishing returns warning
                if rec.improvement_difficulty in ("Hard", "Very Hard"):
                    st.markdown(f"**⚠️ DIMINISHING RETURNS:** {rec.diminishing_returns_warning}")

                # Difficulty and Efficiency
                diff_color = {"Easy": "#66ff66", "Medium": "#ffcc00", "Hard": "#ff9999", "Very Hard": "#ff6666"}.get(rec.improvement_difficulty, "#ccc")
                st.markdown(f"""
                <div style='font-family:monospace; font-size:12px; margin-top:8px;'>
                <span style='color:#66ccff'>⚡ Difficulty:</span> <span style='color:{diff_color}'>{rec.improvement_difficulty.upper()}</span><br>
                <span style='color:#ffcc00'>💎 Efficiency:</span> {rec.efficiency_score:.2f}{' (BEST)' if rec.priority_rank == 1 else ''}
                </div>
                """, unsafe_allow_html=True)

                # Top stats to target
                if rec.top_stats:
                    st.markdown("**🎯 Stats to Target:**")
                    stats_html = "<div style='font-family:monospace; font-size:12px; color:#ccc; margin-left:16px;'>"
                    for j, (stat_name, dps_gain, prob) in enumerate(rec.top_stats[:5], 1):
                        stats_html += f"{j}. {stat_name}: <span style='color:#66ff66'>+{dps_gain:.2f}%</span> DPS ({prob:.1f}% chance)<br>"
                    stats_html += "</div>"
                    st.markdown(stats_html, unsafe_allow_html=True)

                # DPS Distribution Chart
                if st.checkbox(f"Show DPS Distribution", key=f"dist_{rec.slot}_{rec.is_bonus}"):
                    with st.spinner("Generating distribution..."):
                        try:
                            dist_data = get_distribution_data_for_slot(
                                user_data=data,
                                slot=rec.slot,
                                is_bonus=rec.is_bonus,
                                aggregate_stats_func=aggregate_stats_for_dps,
                                calculate_dps_func=calculate_dps_from_stats,
                            )
                            if dist_data:
                                fig = create_dps_distribution_chart(
                                    distribution_data=dist_data,
                                    current_dps_gain=dist_data["current_dps_gain"],
                                    slot_name=rec.slot,
                                    is_bonus=rec.is_bonus,
                                    height=250,
                                )
                                st.plotly_chart(fig, use_container_width=True)

                                # Add percentile interpretation
                                current_pct = rec.percentile_score
                                label = get_percentile_label(current_pct)
                                color = get_percentile_color(current_pct)
                                st.markdown(f"""
                                <div style='font-family:monospace; font-size:11px; text-align:center;'>
                                Your roll is <span style='color:{color}; font-weight:bold'>{label}</span>
                                (beats {current_pct:.0f}% of possible rolls)
                                </div>
                                """, unsafe_allow_html=True)

                                # Expanded view dialog
                                pot_type = "Bonus" if rec.is_bonus else "Regular"
                                with st.expander(f"View Detailed Breakdown"):
                                    # Larger chart
                                    expanded_fig = create_expanded_distribution_chart(
                                        distribution_data=dist_data,
                                        current_dps_gain=dist_data["current_dps_gain"],
                                        slot_name=rec.slot,
                                        is_bonus=rec.is_bonus,
                                    )
                                    st.plotly_chart(expanded_fig, use_container_width=True)

                                    # Percentile breakdown table
                                    st.markdown("#### Improvement Targets")
                                    breakdown = get_percentile_breakdown_data(
                                        dist_data,
                                        dist_data["current_dps_gain"]
                                    )

                                    if breakdown:
                                        # Create table header
                                        st.markdown("""
                                        <style>
                                        .pct-table { width: 100%; border-collapse: collapse; font-family: monospace; font-size: 12px; }
                                        .pct-table th { background: #2a2a4e; padding: 8px; text-align: left; border-bottom: 1px solid #444; }
                                        .pct-table td { padding: 6px 8px; border-bottom: 1px solid #333; }
                                        .pct-table tr:hover { background: rgba(255,255,255,0.05); }
                                        .pct-gold { color: #ffd700; }
                                        .pct-purple { color: #9370db; }
                                        .pct-green { color: #4caf50; }
                                        </style>
                                        """, unsafe_allow_html=True)

                                        table_html = """
                                        <table class='pct-table'>
                                        <tr>
                                            <th>Percentile</th>
                                            <th>DPS Gain</th>
                                            <th>Improvement</th>
                                            <th>Probability</th>
                                            <th>Expected Cubes</th>
                                        </tr>
                                        """

                                        for row in breakdown:
                                            pct = row['percentile']
                                            if pct == 100:
                                                pct_class = "pct-gold"
                                                pct_label = "Best"
                                            elif pct >= 99:
                                                pct_class = "pct-purple"
                                                pct_label = f"P{pct}"
                                            else:
                                                pct_class = "pct-green"
                                                pct_label = f"P{pct}"

                                            cubes_str = f"~{row['expected_cubes']:.0f}" if row['expected_cubes'] < 100000 else "Very Rare"

                                            table_html += f"""
                                            <tr>
                                                <td class='{pct_class}'>{pct_label}</td>
                                                <td>+{row['dps_gain']:.2f}%</td>
                                                <td>+{row['improvement']:.2f}%</td>
                                                <td>{row['prob_pct']:.2f}%</td>
                                                <td>{cubes_str}</td>
                                            </tr>
                                            """

                                        table_html += "</table>"
                                        st.markdown(table_html, unsafe_allow_html=True)
                                    else:
                                        st.info("You're at the maximum roll!")

                            else:
                                st.warning("Could not generate distribution for this slot.")
                        except Exception as e:
                            st.error(f"Error generating distribution: {e}")

    else:
        st.info("Click 'Analyze Cube Priorities' to see which item to cube next based on actual DPS calculations.")
