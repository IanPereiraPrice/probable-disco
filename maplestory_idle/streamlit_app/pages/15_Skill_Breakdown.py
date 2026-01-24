"""
Skill Damage Breakdown Page
Visualize what percentage of damage comes from each skill across levels.

Uses default character stats for consistent comparison across levels and masteries.
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from skills import (
    DPSCalculator,
    create_default_character,
    get_skills_for_job,
    get_masteries_for_job,
    get_level_breakpoints,
)
from job_classes import JobClass, JOB_DISPLAY_NAMES
from stage_settings import COMBAT_SCENARIO_PARAMS, CombatMode

st.set_page_config(page_title="Skill Breakdown", page_icon="📊", layout="wide")

# Check login
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

st.title("📊 Skill Damage Breakdown")
st.markdown("Visualize how damage is distributed across skills at different levels.")

# Get job class from character settings
from skills import SKILLS_BY_JOB

job_class_str = getattr(data, 'job_class', 'bowmaster')
try:
    selected_job = JobClass(job_class_str)
except (ValueError, KeyError):
    selected_job = JobClass.BOWMASTER

# Check if skill data is available for this job class
if selected_job not in SKILLS_BY_JOB:
    st.error(f"Skill data not available for **{JOB_DISPLAY_NAMES.get(selected_job, selected_job.value)}**.")
    st.info("Skill breakdown is currently available for: " + ", ".join(
        JOB_DISPLAY_NAMES[job] for job in SKILLS_BY_JOB.keys()
    ))
    st.stop()

# Show current job class
st.info(f"**Job Class:** {JOB_DISPLAY_NAMES[selected_job]} (set in Character Settings)")

# Sidebar controls
st.sidebar.header("Configuration")

# Character level slider
level = st.sidebar.slider(
    "Character Level",
    min_value=10,
    max_value=200,
    value=140,
    step=5,
    help="Higher levels unlock more skills and masteries"
)

# Combat mode selection
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

# All Skills bonus
all_skills = st.sidebar.slider(
    "+All Skills Bonus",
    min_value=0,
    max_value=400,
    value=100,
    step=10,
    help="From equipment, hyper stats, etc."
)

# Job-specific skill bonuses
st.sidebar.subheader("Job-Specific Bonuses")
skill_1st = st.sidebar.slider("+1st Job Skill", min_value=0, max_value=200, value=0, step=10)
skill_2nd = st.sidebar.slider("+2nd Job Skill", min_value=0, max_value=200, value=0, step=10)
skill_3rd = st.sidebar.slider("+3rd Job Skill", min_value=0, max_value=200, value=0, step=10)
skill_4th = st.sidebar.slider("+4th Job Skill", min_value=0, max_value=200, value=0, step=10)

# Get scenario params
scenario_params = COMBAT_SCENARIO_PARAMS.get(selected_mode)
fight_duration = scenario_params.fight_duration if scenario_params else 60.0
num_enemies = scenario_params.num_enemies if scenario_params else 12
mob_fraction = scenario_params.mob_time_fraction if scenario_params else 0.6

# Create character and calculate breakdown
char = create_default_character(
    level, selected_job, all_skills,
    skill_1st_bonus=skill_1st,
    skill_2nd_bonus=skill_2nd,
    skill_3rd_bonus=skill_3rd,
    skill_4th_bonus=skill_4th,
)
calc = DPSCalculator(char, enemy_def=0.752)

# Handle infinite duration for chapter hunt
if fight_duration == float('inf'):
    fight_duration = 60.0  # Use 60s for visualization

breakdown = calc.get_skill_damage_breakdown(
    fight_duration=fight_duration,
    num_enemies=num_enemies,
    mob_time_fraction=mob_fraction,
)

# Display results
if not breakdown:
    st.warning("No damage-dealing skills unlocked at this level.")
    st.stop()

# Convert to DataFrame for display
data = []
for skill_name, info in breakdown.items():
    data.append({
        'Skill': info['display_name'],
        'Type': info['skill_type'].title(),
        'DPS': info['dps'],
        'Total Damage': info['total_damage'],
        '% of Total': info['pct_of_total'],
        'Mob Damage': info['mob_damage'],
        'Boss Damage': info['boss_damage'],
    })

df = pd.DataFrame(data)
df = df.sort_values('% of Total', ascending=False)

# Summary metrics
total_dps = df['DPS'].sum()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total DPS", f"{total_dps:,.0f}")
with col2:
    st.metric("Level", level)
with col3:
    st.metric("Skills Active", len(breakdown))

st.divider()

# Main breakdown table
st.subheader("Damage Distribution by Skill")

# Format for display
display_df = df.copy()
display_df['DPS'] = display_df['DPS'].apply(lambda x: f"{x:,.0f}")
display_df['Total Damage'] = display_df['Total Damage'].apply(lambda x: f"{x:,.0f}")
display_df['% of Total'] = display_df['% of Total'].apply(lambda x: f"{x:.1f}%")
display_df['Mob Damage'] = display_df['Mob Damage'].apply(lambda x: f"{x:,.0f}")
display_df['Boss Damage'] = display_df['Boss Damage'].apply(lambda x: f"{x:,.0f}")

st.dataframe(display_df, hide_index=True, use_container_width=True)

# Bar chart visualization
st.subheader("Visual Breakdown")

chart_df = df[['Skill', '% of Total']].copy()
chart_df = chart_df.set_index('Skill')
st.bar_chart(chart_df)

st.divider()

# Level progression charts - Stacked Area (Boss vs Mob)
st.subheader("Skill Contribution by Level")
st.markdown("See how damage distribution changes as you level up. Left: Boss fights (single target). Right: Mob grinding (multi-target).")

import altair as alt

# Calculate progression data for both scenarios
steady_state_duration = 300.0  # 5 minutes for steady state simulation

# Output levels for charts (every level from 10-200)
ALL_LEVELS = list(range(10, 201, 1))

@st.cache_data(ttl=300, show_spinner="Calculating level progression...")
def calculate_progression_data_cached(
    job_class_name: str,
    all_skills_bonus: int,
    skill_1st_bonus: int,
    skill_2nd_bonus: int,
    skill_3rd_bonus: int,
    skill_4th_bonus: int,
    mob_time_fraction: float,
    num_enemies: int,
) -> pd.DataFrame:
    """Calculate skill contribution data across levels for a specific scenario.

    Uses breakpoint optimization: only runs full simulation at levels where
    skills/masteries unlock, then interpolates between breakpoints.
    This reduces ~191 simulations to ~30-40 simulations.

    All parameters must be hashable for caching to work.
    """
    # Convert job class name back to enum
    job_class = JobClass[job_class_name]

    # Get breakpoint levels (where skills/masteries unlock)
    breakpoints = get_level_breakpoints(job_class, min_level=10, max_level=200)

    # Run full simulation only at breakpoint levels
    breakpoint_data = {}  # level -> {skill_name: pct}
    breakpoint_skills = {}  # level -> set of skill names

    for bp_level in breakpoints:
        prog_char = create_default_character(
            bp_level, job_class, all_skills_bonus,
            skill_1st_bonus=skill_1st_bonus,
            skill_2nd_bonus=skill_2nd_bonus,
            skill_3rd_bonus=skill_3rd_bonus,
            skill_4th_bonus=skill_4th_bonus,
        )
        prog_calc = DPSCalculator(prog_char, enemy_def=0.752)
        prog_breakdown = prog_calc.get_skill_damage_breakdown(
            fight_duration=steady_state_duration,
            num_enemies=num_enemies,
            mob_time_fraction=mob_time_fraction,
        )

        level_data = {}
        for skill_name, info in prog_breakdown.items():
            # Consolidate all basic attacks into one "Basic Attack" segment
            if info['skill_type'] == 'basic':
                display_name = 'Basic Attack'
            else:
                display_name = info['display_name']

            if display_name not in level_data:
                level_data[display_name] = 0.0
            level_data[display_name] += info['pct_of_total']

        breakpoint_data[bp_level] = level_data
        breakpoint_skills[bp_level] = set(level_data.keys())

    # Interpolate between breakpoints for smooth visualization
    progression_data = []

    for level in ALL_LEVELS:
        if level in breakpoint_data:
            # Exact breakpoint - use calculated values
            for skill, pct in breakpoint_data[level].items():
                progression_data.append({
                    'Level': level,
                    'Skill': skill,
                    'pct': pct,
                })
        else:
            # Find surrounding breakpoints
            lower_bp = max(bp for bp in breakpoints if bp < level)
            upper_bp = min(bp for bp in breakpoints if bp > level)

            # Linear interpolation factor
            t = (level - lower_bp) / (upper_bp - lower_bp)

            # Get union of skills from both breakpoints
            all_skills = breakpoint_skills[lower_bp] | breakpoint_skills[upper_bp]

            for skill in all_skills:
                lower_pct = breakpoint_data[lower_bp].get(skill, 0.0)
                upper_pct = breakpoint_data[upper_bp].get(skill, 0.0)

                # Linear interpolation
                interpolated_pct = lower_pct + t * (upper_pct - lower_pct)

                if interpolated_pct > 0.01:  # Skip near-zero values
                    progression_data.append({
                        'Level': level,
                        'Skill': skill,
                        'pct': interpolated_pct,
                    })

    if not progression_data:
        return pd.DataFrame()

    df = pd.DataFrame(progression_data)
    # Aggregate in case multiple skills map to same name
    df = df.groupby(['Level', 'Skill'], as_index=False)['pct'].sum()
    return df


def calculate_progression_data(mob_time_fraction: float, num_enemies: int) -> pd.DataFrame:
    """Wrapper that calls cached function with current slider values."""
    return calculate_progression_data_cached(
        job_class_name=selected_job.name,
        all_skills_bonus=all_skills,
        skill_1st_bonus=skill_1st,
        skill_2nd_bonus=skill_2nd,
        skill_3rd_bonus=skill_3rd,
        skill_4th_bonus=skill_4th,
        mob_time_fraction=mob_time_fraction,
        num_enemies=num_enemies,
    )

def create_stacked_area_chart(df: pd.DataFrame, title: str) -> alt.Chart:
    """Create a stacked area chart from progression data."""
    pivot_df = df.pivot(index='Level', columns='Skill', values='pct')
    pivot_df = pivot_df.fillna(0)

    chart_df = pivot_df.reset_index().melt(
        id_vars=['Level'],
        var_name='Skill',
        value_name='Contribution %'
    )

    chart = alt.Chart(chart_df).mark_area().encode(
        x=alt.X('Level:Q', title='Character Level'),
        y=alt.Y('Contribution %:Q', stack='normalize', title='% of Total DPS', axis=alt.Axis(format='%')),
        color=alt.Color('Skill:N', legend=alt.Legend(title='Skill')),
        tooltip=['Level', 'Skill', alt.Tooltip('Contribution %:Q', format='.1f')]
    ).properties(
        title=title,
        height=350
    ).interactive()

    return chart

# Calculate data for both scenarios
boss_df = calculate_progression_data(mob_time_fraction=0.0, num_enemies=1)  # Pure boss, single target
mob_df = calculate_progression_data(mob_time_fraction=1.0, num_enemies=12)  # Pure mob, 12 enemies

# Display vertically for better visibility
if not boss_df.empty:
    boss_chart = create_stacked_area_chart(boss_df, "Boss (Single Target)")
    st.altair_chart(boss_chart, use_container_width=True)
else:
    st.warning("No data for boss scenario")

if not mob_df.empty:
    mob_chart = create_stacked_area_chart(mob_df, "Mob Grinding (12 Enemies)")
    st.altair_chart(mob_chart, use_container_width=True)
else:
    st.warning("No data for mob scenario")

# Show key mastery unlock levels
with st.expander("Mastery Unlock Levels"):
    masteries = get_masteries_for_job(selected_job)
    mastery_data = []
    for m in masteries:
        if m.unlock_level > 0:
            mastery_data.append({
                'Level': m.unlock_level,
                'Mastery': m.name,
                'Effect': m.description or f"{m.effect_type}: {m.effect_value}",
            })

    if mastery_data:
        mastery_df = pd.DataFrame(mastery_data)
        mastery_df = mastery_df.sort_values('Level')
        st.dataframe(mastery_df, hide_index=True, use_container_width=True)
    else:
        st.info("No mastery data available for this job class.")

st.divider()

# =============================================================================
# Skill Scaling by +All Skills
# =============================================================================
st.subheader("Skill Scaling by +All Skills")
st.markdown("See which skills scale best with +All Skills investment. Steeper curves = better scaling.")

@st.cache_data(ttl=300, show_spinner="Calculating skill scaling...")
def calculate_scaling_data_cached(
    char_level: int,
    job_class_name: str,
    skill_1st_bonus: int,
    skill_2nd_bonus: int,
    skill_3rd_bonus: int,
    skill_4th_bonus: int,
    num_enemies: int,
    mob_time_fraction: float,
    all_skills_range: tuple,  # Must be tuple for hashability
) -> pd.DataFrame:
    """Calculate skill contribution as +All Skills changes."""
    job_class = JobClass[job_class_name]
    scaling_data = []

    for bonus in all_skills_range:
        scaling_char = create_default_character(
            char_level, job_class, bonus,
            skill_1st_bonus=skill_1st_bonus,
            skill_2nd_bonus=skill_2nd_bonus,
            skill_3rd_bonus=skill_3rd_bonus,
            skill_4th_bonus=skill_4th_bonus,
        )
        scaling_calc = DPSCalculator(scaling_char, enemy_def=0.752)
        scaling_breakdown = scaling_calc.get_skill_damage_breakdown(
            fight_duration=60.0,
            num_enemies=num_enemies,
            mob_time_fraction=mob_time_fraction,
        )

        for skill_name, info in scaling_breakdown.items():
            if info['skill_type'] == 'basic':
                display_name = 'Basic Attack'
            else:
                display_name = info['display_name']

            scaling_data.append({
                '+All Skills': bonus,
                'Skill': display_name,
                'pct': info['pct_of_total'],
                'DPS': info['dps'],
            })

    if not scaling_data:
        return pd.DataFrame()

    df = pd.DataFrame(scaling_data)
    df = df.groupby(['+All Skills', 'Skill'], as_index=False).agg({
        'pct': 'sum',
        'DPS': 'sum',
    })
    return df

# Calculate for range of +All Skills values (0 to 400, step 20)
all_skills_range = tuple(range(0, 401, 20))  # Tuple for hashability
scaling_df = calculate_scaling_data_cached(
    char_level=level,
    job_class_name=selected_job.name,
    skill_1st_bonus=skill_1st,
    skill_2nd_bonus=skill_2nd,
    skill_3rd_bonus=skill_3rd,
    skill_4th_bonus=skill_4th,
    num_enemies=num_enemies,
    mob_time_fraction=mob_fraction,
    all_skills_range=all_skills_range,
)

if not scaling_df.empty:
    # Stacked area chart showing % contribution
    scaling_chart = alt.Chart(scaling_df).mark_area().encode(
        x=alt.X('+All Skills:Q', title='+All Skills Bonus'),
        y=alt.Y('pct:Q', stack='normalize', title='% of Total DPS', axis=alt.Axis(format='%')),
        color=alt.Color('Skill:N', legend=alt.Legend(title='Skill')),
        tooltip=['+All Skills', 'Skill', alt.Tooltip('pct:Q', format='.1f')]
    ).properties(
        title="Skill Contribution by +All Skills",
        height=350
    ).interactive()

    st.altair_chart(scaling_chart, use_container_width=True)

    # DPS Growth line chart
    st.subheader("DPS Growth by +All Skills")
    st.markdown("Raw DPS growth per skill (relative to +0 All Skills baseline).")

    # Calculate growth relative to baseline
    baseline_dps = scaling_df[scaling_df['+All Skills'] == 0].set_index('Skill')['DPS'].to_dict()
    growth_data = []

    for _, row in scaling_df.iterrows():
        baseline = baseline_dps.get(row['Skill'], row['DPS'])
        growth_pct = ((row['DPS'] / baseline) - 1) * 100 if baseline > 0 else 0
        growth_data.append({
            '+All Skills': row['+All Skills'],
            'Skill': row['Skill'],
            'Growth %': growth_pct,
        })

    growth_df = pd.DataFrame(growth_data)

    growth_chart = alt.Chart(growth_df).mark_line(point=True).encode(
        x=alt.X('+All Skills:Q', title='+All Skills Bonus'),
        y=alt.Y('Growth %:Q', title='DPS Growth (% vs baseline)'),
        color=alt.Color('Skill:N'),
        tooltip=['+All Skills', 'Skill', alt.Tooltip('Growth %:Q', format='.1f')]
    ).properties(
        title="DPS Growth per Skill (relative to +0 All Skills)",
        height=350
    ).interactive()

    st.altair_chart(growth_chart, use_container_width=True)
else:
    st.warning("No data for skill scaling analysis")

st.divider()

# Passive effects section
passive_effects = calc.get_active_passive_effects()

if passive_effects:
    st.subheader("Active Passive Effects")
    st.markdown("These passives (like Maple Hero) enhance specific skills:")

    effects_data = []
    for target_skill, effects_list in passive_effects.items():
        skill = get_skills_for_job(selected_job).get(target_skill)
        if not skill:
            continue

        for effect in effects_list:
            effects_data.append({
                'Target Skill': skill.name,
                'Source': effect['source'],
                'Effect': effect['effect_type'].replace('_', ' ').title(),
                'Value': f"+{effect['value']:.0f}%",
            })

    if effects_data:
        effects_df = pd.DataFrame(effects_data)
        st.dataframe(effects_df, hide_index=True, use_container_width=True)

st.divider()

# Skill details
with st.expander("Skill Details"):
    skills = get_skills_for_job(selected_job)

    st.markdown("**Damage-Dealing Skills:**")
    for skill_name, skill in skills.items():
        if skill_name not in breakdown:
            continue

        info = breakdown[skill_name]
        dmg_pct = calc.get_skill_damage_pct(skill_name)
        hits = calc.get_skill_hits(skill_name)
        targets = calc.get_skill_targets(skill_name)

        st.markdown(f"**{skill.name}** (Unlocks at level {skill.unlock_level})")
        st.markdown(f"- Damage: {dmg_pct:.0f}% x {hits} hits x {targets} targets")
        st.markdown(f"- Cooldown: {skill.cooldown:.1f}s" if skill.cooldown > 0 else "- No cooldown")
        st.markdown(f"- Contribution: {info['pct_of_total']:.1f}% of total DPS")

        # Show passive effects on this skill
        if skill_name in passive_effects:
            for effect in passive_effects[skill_name]:
                st.markdown(f"  - *{effect['source']}: +{effect['value']:.0f}% {effect['effect_type'].replace('_', ' ')}*")

        st.markdown("---")
