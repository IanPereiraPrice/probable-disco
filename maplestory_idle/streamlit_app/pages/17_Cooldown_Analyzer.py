"""
Cooldown Reduction Analyzer
Visualize DPS gain from skill cooldown reduction and how it shifts damage proportions.
"""
import streamlit as st
import pandas as pd
import altair as alt
import sys
import math
from pathlib import Path

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from game.skills import DPSCalculator, create_character_at_level, SKILLS_BY_JOB
from core import BASE_MIN_DMG, BASE_MAX_DMG
from constants import ENEMY_DEFENSE_VALUES
from game.artifacts import calculate_book_of_ancient_bonus
from utils.dps_calculator import (
    aggregate_stats as shared_aggregate_stats,
    build_character_model_from_stats,
)
from game.job_classes import JobClass, JOB_DISPLAY_NAMES
from game.stage_settings import COMBAT_SCENARIO_PARAMS, CombatMode

st.set_page_config(page_title="Cooldown Analyzer", page_icon="⏱️", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

# Get job class from character settings
selected_job = JobClass(data.job_class)

st.title("⏱️ Cooldown Reduction Analyzer")
st.markdown("See how skill cooldown reduction (from hat potential) affects your DPS and rotation.")

# Check if skill data is available for this job class
if selected_job not in SKILLS_BY_JOB:
    st.error(f"Skill data not available for **{JOB_DISPLAY_NAMES.get(selected_job, selected_job.value)}**.")
    st.info("Cooldown analysis is currently available for: " + ", ".join(
        JOB_DISPLAY_NAMES[job] for job in SKILLS_BY_JOB.keys()
    ))
    st.stop()

st.info(f"**Job Class:** {JOB_DISPLAY_NAMES[selected_job]} (set in Character Settings)")

# Sidebar: Combat Mode
st.sidebar.header("Configuration")
combat_modes = {
    CombatMode.STAGE: "Stage (60% mob, 40% boss)",
    CombatMode.BOSS: "Boss (100% boss)",
    CombatMode.CHAPTER_HUNT: "Chapter Hunt (100% mob)",
    CombatMode.WORLD_BOSS: "World Boss (100% boss)",
}
selected_mode = st.sidebar.selectbox(
    "Combat Mode",
    options=list(combat_modes.keys()),
    format_func=lambda x: combat_modes[x],
    index=0,
)

scenario_params = COMBAT_SCENARIO_PARAMS.get(selected_mode)
fight_duration = scenario_params.fight_duration if scenario_params else 60.0
num_enemies = scenario_params.num_enemies if scenario_params else 12
mob_fraction = scenario_params.mob_time_fraction if scenario_params else 0.6

# Handle infinite duration
if math.isinf(fight_duration):
    fight_duration = 60.0

# Get enemy defense
combat_mode_str = selected_mode.value if hasattr(selected_mode, 'value') else 'stage'
enemy_def = ENEMY_DEFENSE_VALUES.get(getattr(data, 'chapter', 'Chapter 27'), 0.752)


def build_character_from_stats(stats, cd_reduction_override=0.0):
    """Build a CharacterState from aggregated stats with a specific CD reduction value."""
    job_class = JobClass(data.job_class)
    char_model = build_character_model_from_stats(stats, job_class)

    # Override: use provided CD reduction instead of what was aggregated from equipment
    char_model = char_model.model_copy(update={'skill_cd_reduction': cd_reduction_override})

    # Book of Ancient: convert portion of Crit Rate to Crit Damage
    _, cd_from_book = calculate_book_of_ancient_bonus(
        char_model.book_of_ancient_stars, char_model.crit_rate / 100
    )
    total_crit_damage = char_model.crit_damage + cd_from_book * 100

    # Create CharacterState and apply all stats from the typed model
    char = create_character_at_level(char_model.level, char_model.all_skills_bonus, job_class=job_class)
    for k, v in char_model.to_character_state_kwargs().items():
        setattr(char, k, v)

    # Override: attack uses floor(10000) + pct bonus + manual adjustment
    attack_flat_eff = max(char_model.attack_flat, 10000)
    char.attack = attack_flat_eff * (1 + char_model.attack_pct / 100) + char_model.total_attack_adjustment

    # Override: crit_damage with Book of Ancient bonus applied
    char.crit_damage = total_crit_damage

    # Override: pre-weight boss/normal into damage_pct (legacy mode)
    char.damage_pct = char_model.damage_pct + char_model.normal_damage * mob_fraction + char_model.boss_damage * (1 - mob_fraction)
    char.boss_damage = char_model.boss_damage
    char.normal_damage = 0

    return char


# Aggregate stats once
stats = shared_aggregate_stats(data)

# Damage range multiplier (not handled by DPSCalculator)
final_min = BASE_MIN_DMG + stats['min_dmg_mult']
final_max = BASE_MAX_DMG + stats['max_dmg_mult']
dmg_range_mult = (final_min + final_max) / 2 / 100
hex_mult = stats.get('hex_multiplier', 1.0)


@st.cache_data(ttl=300, show_spinner="Calculating cooldown impact...")
def calculate_cd_sweep(
    stats_keys: tuple,  # hashable cache key derived from stats
    combat_mode_name: str,
):
    """Sweep CD reduction from 0 to 6s in 0.5s steps.

    Returns tuple of (summary_df, breakdowns_dict).
    summary_df: columns [cd_reduction, total_dps]
    breakdowns_dict: {cd_value: [{skill, dps, pct, skill_type}, ...]}
    """
    cd_values = [x * 0.5 for x in range(0, 21)]  # 0.0 to 10.0
    summary_rows = []
    breakdowns = {}

    for cd_val in cd_values:
        char = build_character_from_stats(stats, cd_reduction_override=cd_val)
        calc = DPSCalculator(char, enemy_def=enemy_def)

        breakdown = calc.get_skill_damage_breakdown(
            fight_duration=fight_duration,
            num_enemies=num_enemies,
            mob_time_fraction=mob_fraction,
        )

        total_dps = sum(info['dps'] for info in breakdown.values())
        # Apply damage range and hex multiplier for display
        total_dps *= dmg_range_mult * hex_mult

        summary_rows.append({
            'cd_reduction': cd_val,
            'total_dps': total_dps,
        })

        skill_rows = []
        for skill_name, info in breakdown.items():
            display_name = 'Basic Attack' if info['skill_type'] == 'basic' else info['display_name']
            skill_rows.append({
                'skill': display_name,
                'dps': info['dps'] * dmg_range_mult * hex_mult,
                'pct': info['pct_of_total'],
                'skill_type': info['skill_type'],
            })
        breakdowns[cd_val] = skill_rows

    summary_df = pd.DataFrame(summary_rows)
    return summary_df, breakdowns


# Build a hashable cache key from stats that affect DPS
cache_key = (
    stats.get('level', 140),
    round(stats.get('attack_flat', 0), 1),
    round(stats.get('attack_pct', 0), 1),
    round(stats['crit_rate'], 1),
    round(stats['crit_damage'], 1),
    round(stats['damage_pct'], 1),
    round(stats['boss_damage'], 1),
    round(stats.get('all_skills_bonus', 0), 1),
    round(stats.get('skill_damage', 0), 1),
    round(enemy_def, 4),
)

def calculate_skill_tier_values(
    skill_1st_base: int,
    skill_2nd_base: int,
    skill_3rd_base: int,
    skill_4th_base: int,
    current_cd: float,
) -> pd.DataFrame:
    """For each skill tier, compute DPS gain from +10 bonus, holding others constant."""
    baseline_char = build_character_from_stats(stats, cd_reduction_override=current_cd)
    baseline_calc = DPSCalculator(baseline_char, enemy_def=enemy_def)
    baseline_dps = sum(
        info['dps'] for info in baseline_calc.get_skill_damage_breakdown(
            fight_duration=fight_duration, num_enemies=num_enemies, mob_time_fraction=mob_fraction
        ).values()
    ) * dmg_range_mult * hex_mult

    tiers = [
        ("1st Job", "skill_1st", skill_1st_base),
        ("2nd Job", "skill_2nd", skill_2nd_base),
        ("3rd Job", "skill_3rd", skill_3rd_base),
        ("4th Job", "skill_4th", skill_4th_base),
    ]

    rows = []
    for label, key, base_val in tiers:
        modified_stats = dict(stats)
        modified_stats[key] = base_val + 10
        char = build_character_from_stats(modified_stats, cd_reduction_override=current_cd)
        calc = DPSCalculator(char, enemy_def=enemy_def)
        new_dps = sum(
            info['dps'] for info in calc.get_skill_damage_breakdown(
                fight_duration=fight_duration, num_enemies=num_enemies, mob_time_fraction=mob_fraction
            ).values()
        ) * dmg_range_mult * hex_mult

        dps_gain = new_dps - baseline_dps
        pct_gain = (dps_gain / baseline_dps * 100) if baseline_dps > 0 else 0
        rows.append({
            'tier': label,
            'current_bonus': base_val,
            'after_bonus': base_val + 10,
            'dps_gain': dps_gain,
            'pct_gain': pct_gain,
        })

    return pd.DataFrame(rows)


summary_df, breakdowns = calculate_cd_sweep(cache_key, selected_mode.name)

if summary_df.empty:
    st.warning("No data generated. Check your character settings.")
    st.stop()

# Current CD reduction from equipment
current_cd = stats.get('skill_cd_reduction', 0)

# =============================================================================
# Section 1: Total DPS vs CD Reduction
# =============================================================================
st.subheader("Total DPS vs Cooldown Reduction")

base_dps = summary_df.iloc[0]['total_dps']
max_dps = summary_df.iloc[-1]['total_dps']

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("DPS at 0s CD Reduction", f"{base_dps:,.0f}")
with col2:
    st.metric("DPS at 10s CD Reduction", f"{max_dps:,.0f}", delta=f"+{(max_dps/base_dps - 1)*100:.1f}%")
with col3:
    st.metric("Current CD Reduction", f"{current_cd:.1f}s")

dps_chart = alt.Chart(summary_df).mark_line(point=True, color='#4c78a8').encode(
    x=alt.X('cd_reduction:Q', title='Cooldown Reduction (seconds)', scale=alt.Scale(domain=[0, 10])),
    y=alt.Y('total_dps:Q', title='Total DPS', scale=alt.Scale(zero=False)),
    tooltip=[
        alt.Tooltip('cd_reduction:Q', title='CD Reduction', format='.1f'),
        alt.Tooltip('total_dps:Q', title='Total DPS', format=',.0f'),
    ],
).properties(height=300)

# Add vertical rule at current CD reduction
if current_cd > 0:
    current_rule = alt.Chart(pd.DataFrame({'x': [current_cd]})).mark_rule(
        color='orange', strokeDash=[4, 4], strokeWidth=2
    ).encode(x='x:Q')
    dps_chart = dps_chart + current_rule

st.altair_chart(dps_chart, use_container_width=True)

# =============================================================================
# Section 2: Marginal DPS Gain per 0.5s Step
# =============================================================================
st.subheader("Marginal DPS Gain per 0.5s")
st.markdown("How much DPS each additional 0.5 seconds of cooldown reduction adds.")

marginal_rows = []
for i in range(1, len(summary_df)):
    prev_dps = summary_df.iloc[i - 1]['total_dps']
    curr_dps = summary_df.iloc[i]['total_dps']
    cd_val = summary_df.iloc[i]['cd_reduction']
    gain = curr_dps - prev_dps
    pct_gain = (gain / prev_dps * 100) if prev_dps > 0 else 0
    marginal_rows.append({
        'step': f"{cd_val - 0.5:.1f}s → {cd_val:.1f}s",
        'cd_reduction': cd_val,
        'dps_gain': gain,
        'pct_gain': pct_gain,
    })

marginal_df = pd.DataFrame(marginal_rows)

marginal_chart = alt.Chart(marginal_df).mark_bar(color='#4c78a8').encode(
    x=alt.X('step:N', title='CD Reduction Step', sort=None),
    y=alt.Y('dps_gain:Q', title='DPS Gained'),
    tooltip=[
        alt.Tooltip('step:N', title='Step'),
        alt.Tooltip('dps_gain:Q', title='DPS Gained', format=',.0f'),
        alt.Tooltip('pct_gain:Q', title='% Gain', format='.2f'),
    ],
).properties(height=250)

st.altair_chart(marginal_chart, use_container_width=True)

# Show marginal table
display_marginal = marginal_df[['step', 'dps_gain', 'pct_gain']].copy()
display_marginal.columns = ['Step', 'DPS Gained', '% Gain']
display_marginal['DPS Gained'] = display_marginal['DPS Gained'].apply(lambda x: f"{x:,.0f}")
display_marginal['% Gain'] = display_marginal['% Gain'].apply(lambda x: f"{x:.2f}%")
st.dataframe(display_marginal, hide_index=True, use_container_width=True)

# =============================================================================
# Section 3: Skill Tier Value (+10 each tier)
# =============================================================================
st.subheader("Skill Tier Value (+10 Levels)")
st.markdown("DPS gain from adding +10 bonus levels to each skill tier, holding all others constant.")

skill_tier_df = calculate_skill_tier_values(
    int(stats.get('skill_1st_bonus', 0)),
    int(stats.get('skill_2nd_bonus', 0)),
    int(stats.get('skill_3rd_bonus', 0)),
    int(stats.get('skill_4th_bonus', 0)),
    current_cd,
)

tier_chart = alt.Chart(skill_tier_df).mark_bar().encode(
    x=alt.X('tier:N', title='Skill Tier', sort=None),
    y=alt.Y('pct_gain:Q', title='% DPS Gain'),
    color=alt.Color('tier:N', legend=None),
    tooltip=[
        alt.Tooltip('tier:N', title='Tier'),
        alt.Tooltip('current_bonus:Q', title='Current Bonus'),
        alt.Tooltip('after_bonus:Q', title='After +10'),
        alt.Tooltip('dps_gain:Q', title='DPS Gained', format=',.0f'),
        alt.Tooltip('pct_gain:Q', title='% DPS Gain', format='.3f'),
    ],
).properties(height=250)

st.altair_chart(tier_chart, use_container_width=True)

display_tier = skill_tier_df[['tier', 'current_bonus', 'after_bonus', 'dps_gain', 'pct_gain']].copy()
display_tier.columns = ['Tier', 'Current Bonus', 'After +10', 'DPS Gained', '% DPS Gain']
display_tier['DPS Gained'] = display_tier['DPS Gained'].apply(lambda x: f"{x:,.0f}")
display_tier['% DPS Gain'] = display_tier['% DPS Gain'].apply(lambda x: f"{x:.3f}%")
st.dataframe(display_tier, hide_index=True, use_container_width=True)
