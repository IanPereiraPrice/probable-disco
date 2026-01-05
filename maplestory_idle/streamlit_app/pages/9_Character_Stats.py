"""
Character Stats Page
View aggregated stats from all sources with breakdown.
"""
import streamlit as st
from utils.data_manager import EQUIPMENT_SLOTS

st.set_page_config(page_title="Character Stats", page_icon="📊", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Baselines
BASE_MIN_DMG = 60.0
BASE_MAX_DMG = 100.0
BASE_CRIT_DMG = 30.0


def get_stats_by_source():
    """Get stats broken down by source."""
    sources = {
        'Equipment Potentials': {},
        'Hero Power Lines': {},
        'Hero Power Passives': {},
        'Maple Rank': {},
        'Equipment Sets': {},
        'Weapons': {},
        'Artifacts': {},
    }

    # Equipment potentials
    pot_stats = {}
    for slot in EQUIPMENT_SLOTS:
        pots = data.equipment_potentials.get(slot, {})
        for i in range(1, 4):
            stat = pots.get(f'line{i}_stat', '')
            value = float(pots.get(f'line{i}_value', 0))
            if stat and value > 0:
                pot_stats[stat] = pot_stats.get(stat, 0) + value
    sources['Equipment Potentials'] = pot_stats

    # Hero Power lines
    hp_stats = {}
    for line_key, line in data.hero_power_lines.items():
        stat = line.get('stat', '')
        value = float(line.get('value', 0))
        if stat and value > 0:
            hp_stats[stat] = hp_stats.get(stat, 0) + value
    sources['Hero Power Lines'] = hp_stats

    # Hero Power passives
    hpp_stats = {}
    passives = data.hero_power_passives
    if passives.get('main_stat', 0) > 0:
        hpp_stats['main_stat'] = passives['main_stat'] * 100
    if passives.get('damage', 0) > 0:
        hpp_stats['damage'] = passives['damage'] * 2
    sources['Hero Power Passives'] = hpp_stats

    # Maple Rank
    mr_stats = {}
    mr = data.maple_rank
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)
    special = mr.get('special_main_stat', 0)
    main_stat_total = (stage - 1) * 100 + ms_level * 10 + special
    if main_stat_total > 0:
        mr_stats['main_stat'] = main_stat_total

    stat_levels = mr.get('stat_levels', {})
    if isinstance(stat_levels, dict):
        for stat_key, level in stat_levels.items():
            if isinstance(level, (int, float)) and level > 0:
                mr_stats[stat_key] = level * 2  # Approximate value per level
    sources['Maple Rank'] = mr_stats

    # Equipment Sets
    sets_stats = {}
    if data.equipment_sets.get('medal', 0) > 0:
        sets_stats['medal_main_stat'] = data.equipment_sets['medal']
    if data.equipment_sets.get('costume', 0) > 0:
        sets_stats['costume_main_stat'] = data.equipment_sets['costume']
    sources['Equipment Sets'] = sets_stats

    # Weapons
    weapon_stats = {}
    total_atk_pct = sum(w.get('atk_pct', 0) for w in data.weapons.values())
    if total_atk_pct > 0:
        weapon_stats['attack_pct'] = total_atk_pct
    sources['Weapons'] = weapon_stats

    # Artifacts
    art_stats = {}
    for slot_key, artifact in data.artifacts_equipped.items():
        for i in range(1, 4):
            stat = artifact.get(f'pot{i}', '')
            value = float(artifact.get(f'pot{i}_val', 0))
            if stat and value > 0:
                art_stats[stat] = art_stats.get(stat, 0) + value
    sources['Artifacts'] = art_stats

    return sources


st.title("📊 Character Stats Overview")
st.markdown("View your aggregated stats from all sources.")

# Quick summary
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Character Level", data.character_level)
with col2:
    st.metric("All Skills", f"+{data.all_skills}")
with col3:
    st.metric("Combat Mode", data.combat_mode.replace("_", " ").title())
with col4:
    st.metric("Chapter", data.chapter.replace("Chapter ", "Ch. "))

st.divider()

# Stats by source
sources = get_stats_by_source()

st.subheader("Stats by Source")

for source_name, stats in sources.items():
    if stats:
        with st.expander(f"**{source_name}**", expanded=True):
            cols = st.columns(3)
            stat_items = list(stats.items())
            for idx, (stat, value) in enumerate(stat_items):
                with cols[idx % 3]:
                    display_name = stat.replace("_", " ").title()
                    st.write(f"{display_name}: **+{value:.1f}**")

st.divider()

# Total stats
st.subheader("Total Aggregated Stats")

totals = {}
for source_stats in sources.values():
    for stat, value in source_stats.items():
        # Normalize stat names
        if stat in ['medal_main_stat', 'costume_main_stat']:
            stat = 'main_stat'
        totals[stat] = totals.get(stat, 0) + value

# Add baselines
display_totals = totals.copy()
display_totals['min_dmg_mult'] = display_totals.get('min_dmg_mult', 0) + BASE_MIN_DMG
display_totals['max_dmg_mult'] = display_totals.get('max_dmg_mult', 0) + BASE_MAX_DMG
display_totals['crit_damage'] = display_totals.get('crit_damage', 0) + BASE_CRIT_DMG

# Display totals in table
total_data = [
    {"Stat": stat.replace("_", " ").title(), "Total": f"+{value:.1f}"}
    for stat, value in sorted(display_totals.items())
]

if total_data:
    st.dataframe(total_data, width='stretch', hide_index=True)

st.divider()

# Notes
st.subheader("Notes")
st.info("""
**Baseline Values Included:**
- Min Damage: +60% baseline
- Max Damage: +100% baseline
- Crit Damage: +30% baseline

**Missing Sources:**
Some stats may not be fully tracked yet. The Damage Calculator page uses
these aggregated values to calculate your DPS.
""")
