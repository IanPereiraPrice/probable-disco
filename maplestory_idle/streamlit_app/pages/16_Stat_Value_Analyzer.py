"""
Stat Value Analyzer
Visualize how much each stat contributes to DPS and see diminishing returns.
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any, List
import copy
import hashlib

from utils.data_manager import save_user_data
from utils.dps_calculator import (
    aggregate_stats,
    calculate_dps,
    calculate_effective_defense_pen_with_sources,
    calculate_effective_attack_speed_with_sources,
)
from game.job_classes import JobClass, get_main_stat_name

st.set_page_config(page_title="Stat Value", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

st.title("📈 Stat Value Analyzer")
st.markdown("""
See how much DPS you gain from adding stats based on your current character.
Higher current stats = more diminishing returns on that stat type.
""")

# Get current stats and DPS
job_class = JobClass(getattr(data, 'job_class', 'bowmaster'))
combat_mode = getattr(data, 'combat_mode', 'stage')

# Get base stats
base_stats = aggregate_stats(data)
base_dps_result = calculate_dps(base_stats, combat_mode, job_class=job_class)
base_dps = base_dps_result['total']

# Display current DPS
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Current DPS", f"{base_dps:,.0f}")
with col2:
    st.metric("Combat Mode", combat_mode.replace('_', ' ').title())
with col3:
    st.metric("Job Class", job_class.name.replace('_', ' ').title())

st.divider()

# Define stat types to analyze
main_stat_name = get_main_stat_name(job_class)

STAT_CONFIGS = [
    {
        'name': 'Main Stat',
        'key': f'{main_stat_name}_flat',
        'default_amount': 1000,
        'max_amount': 10000,
        'step': 100,
        'display_unit': '',
        'description': f'+{main_stat_name.upper()} flat stat',
    },
    {
        'name': 'Main Stat %',
        'key': f'{main_stat_name}_pct',
        'default_amount': 10,
        'max_amount': 200,
        'step': 5,
        'display_unit': '%',
        'description': f'+{main_stat_name.upper()}% percentage',
    },
    {
        'name': 'Attack',
        'key': 'attack_flat',
        'default_amount': 1000,
        'max_amount': 10000,
        'step': 100,
        'display_unit': '',
        'description': '+ATK flat stat',
    },
    {
        'name': 'Attack %',
        'key': 'attack_pct',
        'default_amount': 10,
        'max_amount': 100,
        'step': 5,
        'display_unit': '%',
        'description': '+ATK% percentage',
    },
    {
        'name': 'Boss Damage',
        'key': 'boss_damage',
        'default_amount': 20,
        'max_amount': 200,
        'step': 5,
        'display_unit': '%',
        'description': '+Boss Damage %',
    },
    {
        'name': 'Damage %',
        'key': 'damage_pct',
        'default_amount': 20,
        'max_amount': 200,
        'step': 5,
        'display_unit': '%',
        'description': '+Damage % (all targets)',
    },
    {
        'name': 'Damage Amp',
        'key': 'damage_amp',
        'default_amount': 10,
        'max_amount': 200,
        'step': 5,
        'display_unit': '%',
        'description': '+Damage Amplification %',
    },
    {
        'name': 'Skill Damage',
        'key': 'skill_damage',
        'default_amount': 10,
        'max_amount': 200,
        'step': 5,
        'display_unit': '%',
        'description': '+Skill Damage % (active skills only)',
    },
    {
        'name': 'Basic Atk Dmg',
        'key': 'basic_attack_damage',
        'default_amount': 10,
        'max_amount': 200,
        'step': 5,
        'display_unit': '%',
        'description': '+Basic Attack Damage % (basic attacks only)',
    },
    {
        'name': 'Crit Damage',
        'key': 'crit_damage',
        'default_amount': 20,
        'max_amount': 200,
        'step': 5,
        'display_unit': '%',
        'description': '+Crit Damage %',
    },
    {
        'name': 'Crit Rate',
        'key': 'crit_rate',
        'default_amount': 10,
        'max_amount': 50,
        'step': 5,
        'display_unit': '%',
        'description': '+Crit Rate %',
    },
    {
        'name': 'All Skills',
        'key': 'all_skills_bonus',
        'default_amount': 20,
        'max_amount': 200,
        'step': 10,
        'display_unit': '',
        'description': '+All Skills level bonus',
    },
    {
        'name': '1st Job Skills',
        'key': 'skill_1st_bonus',
        'default_amount': 10,
        'max_amount': 200,
        'step': 10,
        'display_unit': '',
        'description': '+1st Job Skill levels',
    },
    {
        'name': '2nd Job Skills',
        'key': 'skill_2nd_bonus',
        'default_amount': 10,
        'max_amount': 200,
        'step': 10,
        'display_unit': '',
        'description': '+2nd Job Skill levels',
    },
    {
        'name': '3rd Job Skills',
        'key': 'skill_3rd_bonus',
        'default_amount': 10,
        'max_amount': 200,
        'step': 10,
        'display_unit': '',
        'description': '+3rd Job Skill levels',
    },
    {
        'name': '4th Job Skills',
        'key': 'skill_4th_bonus',
        'default_amount': 10,
        'max_amount': 200,
        'step': 10,
        'display_unit': '',
        'description': '+4th Job Skill levels',
    },
    {
        'name': 'Min DMG',
        'key': 'min_dmg_mult',
        'default_amount': 10,
        'max_amount': 100,
        'step': 5,
        'display_unit': '%',
        'description': '+Min Damage %',
    },
    {
        'name': 'Max DMG',
        'key': 'max_dmg_mult',
        'default_amount': 10,
        'max_amount': 100,
        'step': 5,
        'display_unit': '%',
        'description': '+Max Damage %',
    },
    {
        'name': 'Def Pen',
        'key': 'def_pen',
        'source_type': 'def_pen',
        'default_amount': 5,
        'max_amount': 50,
        'step': 5,
        'display_unit': '%',
        'description': '+Defense Penetration %',
    },
    {
        'name': 'Att Speed',
        'key': 'attack_speed',
        'source_type': 'attack_speed',
        'default_amount': 10,
        'max_amount': 100,
        'step': 10,
        'display_unit': '%',
        'description': '+Attack Speed %',
    },
    {
        'name': 'Skill CD',
        'key': 'skill_cd_reduction',
        'default_amount': 2,
        'max_amount': 10,
        'step': 2,
        'display_unit': 's',
        'description': '+Skill Cooldown Reduction (seconds)',
    },
]


def _make_stats_key(stats: Dict) -> str:
    """Create a stable hash key from a stats dict for caching."""
    s = str(sorted((k, str(v)) for k, v in stats.items()))
    return hashlib.sha1(s.encode()).hexdigest()[:20]


@st.cache_data(ttl=300, show_spinner=False)
def _cached_dps_with_change(stats_key: str, stat_key: str, amount: float, source_type: str,
                             combat_mode_str: str, job_class_str: str, _base_stats: Dict) -> float:
    """Cached DPS calculation with one stat changed. stats_key is the cache key, _base_stats is the actual data."""
    modified_stats = copy.deepcopy(_base_stats)
    if source_type == 'def_pen':
        modified_stats['def_pen_sources'].append(('Stat Compare', amount / 100, 999))
    elif source_type == 'attack_speed':
        modified_stats['attack_speed_sources'].append(('Stat Compare', amount))
    else:
        current_value = modified_stats.get(stat_key, 0)
        modified_stats[stat_key] = current_value + amount
    result = calculate_dps(modified_stats, combat_mode_str, job_class=JobClass(job_class_str))
    return result['total']


def calculate_dps_with_stat_change(base_stats: Dict, stat_key: str, amount: float, source_type: str = 'additive') -> float:
    stats_key = _make_stats_key(base_stats)
    return _cached_dps_with_change(stats_key, stat_key, amount, source_type,
                                   combat_mode, job_class.value, base_stats)


def calculate_stat_value(base_stats: Dict, base_dps: float, stat_key: str, amount: float, source_type: str = 'additive') -> Dict:
    """Calculate the DPS gain and efficiency for a stat increase."""
    new_dps = calculate_dps_with_stat_change(base_stats, stat_key, amount, source_type)
    dps_gain = new_dps - base_dps
    pct_gain = (dps_gain / base_dps * 100) if base_dps > 0 else 0

    return {
        'new_dps': new_dps,
        'dps_gain': dps_gain,
        'pct_gain': pct_gain,
    }


# =============================================================================
# Main Stat Value Table
# =============================================================================
st.subheader("Stat Value Comparison")
st.markdown("How much DPS each stat gives based on your current character:")

# Create adjustable sliders in an expander
with st.expander("Adjust Stat Amounts", expanded=True):
    st.markdown("Adjust how much of each stat to add for the comparison:")

    slider_cols = st.columns(4)
    stat_amounts = {}

    for i, config in enumerate(STAT_CONFIGS):
        col_idx = i % 4
        with slider_cols[col_idx]:
            stat_amounts[config['key']] = st.slider(
                f"+{config['name']}",
                min_value=config['step'],
                max_value=config['max_amount'],
                value=config['default_amount'],
                step=config['step'],
                key=f"stat_slider_{config['key']}",
                help=config['description'],
            )

# Calculate values for each stat
results = []
for config in STAT_CONFIGS:
    source_type = config.get('source_type', 'additive')
    amount = stat_amounts[config['key']]
    value = calculate_stat_value(base_stats, base_dps, config['key'], amount, source_type)

    # Get current value for display
    if source_type == 'def_pen':
        eff, _ = calculate_effective_defense_pen_with_sources(base_stats.get('def_pen_sources', []))
        current_value = eff * 100
    elif source_type == 'attack_speed':
        eff, _ = calculate_effective_attack_speed_with_sources(base_stats.get('attack_speed_sources', []))
        current_value = eff - 100  # excess over base 100%
    else:
        current_value = base_stats.get(config['key'], 0)

    results.append({
        'Stat': config['name'],
        'Current': f"{current_value:,.1f}{config['display_unit']}",
        'Added': f"+{amount:,.0f}{config['display_unit']}",
        'DPS Gain': f"+{value['dps_gain']:,.0f}",
        'DPS %': f"+{value['pct_gain']:.2f}%",
        'Per Unit': f"+{value['dps_gain']/amount:,.1f}" if amount > 0 else "0",
        '_dps_gain': value['dps_gain'],  # For sorting
        '_pct_gain': value['pct_gain'],
    })

# Sort by DPS gain (highest first)
results.sort(key=lambda x: x['_dps_gain'], reverse=True)

# Display as dataframe
df = pd.DataFrame(results)
display_df = df[['Stat', 'Current', 'Added', 'DPS Gain', 'DPS %', 'Per Unit']]
st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

# =============================================================================
# Diminishing Returns Visualization
# =============================================================================
st.subheader("Diminishing Returns Chart")
st.markdown("See how stat efficiency decreases as you add more of a stat:")

# Stat selector for chart
chart_stat = st.selectbox(
    "Select stat to analyze",
    options=[c['name'] for c in STAT_CONFIGS],
    index=0,
    key="chart_stat_select"
)

selected_config = next(c for c in STAT_CONFIGS if c['name'] == chart_stat)
stat_key = selected_config['key']
chart_source_type = selected_config.get('source_type', 'additive')
current_stat_value = base_stats.get(stat_key, 0)

# Generate data points for the chart
chart_data = []
step_size = selected_config['default_amount']
num_points = 20

for i in range(num_points + 1):
    added_amount = i * step_size

    if added_amount == 0:
        # Baseline
        chart_data.append({
            'Added': 0,
            'Total': current_stat_value,
            'DPS': base_dps,
            'DPS Gain': 0,
            'Marginal DPS': 0,
        })
    else:
        new_dps = calculate_dps_with_stat_change(base_stats, stat_key, added_amount, chart_source_type)
        prev_dps = chart_data[-1]['DPS']
        marginal_gain = (new_dps - prev_dps) / step_size  # DPS per unit of stat

        chart_data.append({
            'Added': added_amount,
            'Total': current_stat_value + added_amount,
            'DPS': new_dps,
            'DPS Gain': new_dps - base_dps,
            'Marginal DPS': marginal_gain,
        })

chart_df = pd.DataFrame(chart_data)

# Show two charts side by side
col1, col2 = st.columns(2)

with col1:
    st.markdown(f"**Total DPS vs Added {chart_stat}**")
    st.line_chart(
        chart_df.set_index('Added')['DPS'],
        use_container_width=True,
    )

with col2:
    st.markdown(f"**DPS per Unit (Marginal Value)**")
    # Skip first point (0) for marginal chart
    marginal_df = chart_df[chart_df['Added'] > 0]
    st.line_chart(
        marginal_df.set_index('Added')['Marginal DPS'],
        use_container_width=True,
    )

# Show data table
with st.expander("View Chart Data"):
    display_chart_df = chart_df.copy()
    display_chart_df['DPS'] = display_chart_df['DPS'].apply(lambda x: f"{x:,.0f}")
    display_chart_df['DPS Gain'] = display_chart_df['DPS Gain'].apply(lambda x: f"+{x:,.0f}")
    display_chart_df['Marginal DPS'] = display_chart_df['Marginal DPS'].apply(lambda x: f"{x:,.2f}")
    st.dataframe(display_chart_df, use_container_width=True, hide_index=True)

st.divider()

# =============================================================================
# Stat Comparison Tool
# =============================================================================
st.subheader("Compare Two Stats")
st.markdown("Compare the value of two different stats side by side:")

comp_cols = st.columns(2)

with comp_cols[0]:
    stat1_name = st.selectbox(
        "First Stat",
        options=[c['name'] for c in STAT_CONFIGS],
        index=0,
        key="compare_stat1"
    )
    stat1_config = next(c for c in STAT_CONFIGS if c['name'] == stat1_name)
    stat1_amount = st.number_input(
        f"Amount of {stat1_name}",
        min_value=1,
        max_value=stat1_config['max_amount'] * 2,
        value=stat1_config['default_amount'],
        step=stat1_config['step'],
        key="compare_amount1"
    )

with comp_cols[1]:
    stat2_name = st.selectbox(
        "Second Stat",
        options=[c['name'] for c in STAT_CONFIGS],
        index=3,  # Default to Boss Damage
        key="compare_stat2"
    )
    stat2_config = next(c for c in STAT_CONFIGS if c['name'] == stat2_name)
    stat2_amount = st.number_input(
        f"Amount of {stat2_name}",
        min_value=1,
        max_value=stat2_config['max_amount'] * 2,
        value=stat2_config['default_amount'],
        step=stat2_config['step'],
        key="compare_amount2"
    )

# Calculate comparison
stat1_value = calculate_stat_value(base_stats, base_dps, stat1_config['key'], stat1_amount)
stat2_value = calculate_stat_value(base_stats, base_dps, stat2_config['key'], stat2_amount)

# Display comparison
result_cols = st.columns(2)

with result_cols[0]:
    st.metric(
        f"+{stat1_amount:,}{stat1_config['display_unit']} {stat1_name}",
        f"+{stat1_value['dps_gain']:,.0f} DPS",
        f"+{stat1_value['pct_gain']:.2f}%"
    )

with result_cols[1]:
    st.metric(
        f"+{stat2_amount:,}{stat2_config['display_unit']} {stat2_name}",
        f"+{stat2_value['dps_gain']:,.0f} DPS",
        f"+{stat2_value['pct_gain']:.2f}%"
    )

# Show which is better
if stat1_value['dps_gain'] > stat2_value['dps_gain']:
    diff = stat1_value['dps_gain'] - stat2_value['dps_gain']
    st.success(f"**{stat1_name}** gives **+{diff:,.0f}** more DPS ({diff/stat2_value['dps_gain']*100:.1f}% better)" if stat2_value['dps_gain'] > 0 else f"**{stat1_name}** is better")
elif stat2_value['dps_gain'] > stat1_value['dps_gain']:
    diff = stat2_value['dps_gain'] - stat1_value['dps_gain']
    st.success(f"**{stat2_name}** gives **+{diff:,.0f}** more DPS ({diff/stat1_value['dps_gain']*100:.1f}% better)" if stat1_value['dps_gain'] > 0 else f"**{stat2_name}** is better")
else:
    st.info("Both stats give equal DPS gain")

st.divider()

# =============================================================================
# Explanation
# =============================================================================
with st.expander("How Stat Values Work"):
    st.markdown("""
    ### Diminishing Returns Explained

    Most stats in MapleStory Idle have **diminishing returns** - the more you have of a stat,
    the less value each additional point provides.

    **Example with Damage %:**
    - Going from 0% to 20% damage is a 20% DPS increase
    - Going from 100% to 120% damage is only a 10% DPS increase (120/100 = 1.10x)
    - Going from 200% to 220% damage is only a 6.7% DPS increase (320/300 = 1.067x)

    ### Stat Priority Changes

    Because of diminishing returns, your **stat priority changes** based on what you already have:
    - If you have very low Boss Damage, it might be your best stat
    - If you already have 300% Boss Damage, Main Stat or Attack might be better

    ### Using This Tool

    1. **Stat Value Table**: See which stats currently give the most DPS per point
    2. **Diminishing Returns Chart**: Visualize how efficiency drops as you add more
    3. **Compare Stats**: Directly compare two stat options (e.g., "Should I get +1000 DEX or +20% Boss?")

    ### Notes
    - Values are based on your current character configuration
    - Combat mode affects which stats are valuable (Boss Damage only helps vs bosses)
    - This uses the full DPS simulation including skill rotations
    """)
