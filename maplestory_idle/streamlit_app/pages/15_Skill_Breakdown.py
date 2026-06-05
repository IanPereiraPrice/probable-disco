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

from game.skills import (
    DPSCalculator,
    SkillType,
    create_default_character,
    get_skills_for_job,
    get_masteries_for_job,
    get_level_breakpoints,
    calculate_effective_cooldown,
)
from libs.cooldown_calc import calculate_buff_uptime
from game.job_classes import JobClass, JOB_DISPLAY_NAMES
from game.stage_settings import COMBAT_SCENARIO_PARAMS, CombatMode

st.set_page_config(page_title="Skill Breakdown", page_icon="📊", layout="wide")

# Check login
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

st.title("📊 Skill Damage Breakdown")
st.markdown("Visualize how damage is distributed across skills at different levels.")

# Get job class from character settings
from game.skills import SKILLS_BY_JOB

selected_job = JobClass(data.job_class)

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

# Attack speed
attack_speed = st.sidebar.slider(
    "Attack Speed %",
    min_value=0,
    max_value=150,
    value=0,
    step=5,
    help="Total attack speed % from equipment, potentials, companions, etc."
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
char.attack_speed_pct = attack_speed
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
st.markdown("See how damage distribution changes as you level up and with cooldown reduction.")

import altair as alt

# CD Reduction + All Skills override sliders
cd_options = [x * 0.5 for x in range(0, 21)]  # 0.0 to 10.0
col_cd, col_as = st.columns(2)
with col_cd:
    selected_cd = st.select_slider(
        "Cooldown Reduction (seconds)",
        options=cd_options,
        value=0.0,
        format_func=lambda x: f"{x:.1f}s",
    )
with col_as:
    selected_all_skills = st.slider(
        "+All Skills Override",
        min_value=0,
        max_value=400,
        value=all_skills,
        step=10,
        help="Override +All Skills for comparison. Affects skill damage scaling via level factors."
    )

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
    skill_cd_reduction: float = 0.0,
    attack_speed_pct: float = 0.0,
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
        prog_char.skill_cd_reduction = skill_cd_reduction
        prog_char.attack_speed_pct = attack_speed_pct
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
        all_skills_bonus=selected_all_skills,
        skill_1st_bonus=skill_1st,
        skill_2nd_bonus=skill_2nd,
        skill_3rd_bonus=skill_3rd,
        skill_4th_bonus=skill_4th,
        mob_time_fraction=mob_time_fraction,
        num_enemies=num_enemies,
        skill_cd_reduction=selected_cd,
        attack_speed_pct=float(attack_speed),
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

# =============================================================================
# Skill Damage Proportion at selected CD reduction
# =============================================================================
st.subheader("Skill Damage Proportion")

# Build characters at current level: one at 0s CD (baseline), one at selected CD
cd_char_base = create_default_character(
    level, selected_job, all_skills,
    skill_1st_bonus=skill_1st, skill_2nd_bonus=skill_2nd,
    skill_3rd_bonus=skill_3rd, skill_4th_bonus=skill_4th,
)
cd_char_base.skill_cd_reduction = 0.0
cd_char_base.attack_speed_pct = attack_speed
cd_calc_base = DPSCalculator(cd_char_base, enemy_def=0.752)
cd_breakdown_base = cd_calc_base.get_skill_damage_breakdown(
    fight_duration=60.0, num_enemies=num_enemies, mob_time_fraction=mob_fraction,
)

cd_char_curr = create_default_character(
    level, selected_job, selected_all_skills,
    skill_1st_bonus=skill_1st, skill_2nd_bonus=skill_2nd,
    skill_3rd_bonus=skill_3rd, skill_4th_bonus=skill_4th,
)
cd_char_curr.skill_cd_reduction = selected_cd
cd_char_curr.attack_speed_pct = attack_speed
cd_calc_curr = DPSCalculator(cd_char_curr, enemy_def=0.752)
cd_breakdown_curr = cd_calc_curr.get_skill_damage_breakdown(
    fight_duration=60.0, num_enemies=num_enemies, mob_time_fraction=mob_fraction,
)

# Aggregate into display-friendly maps
def _aggregate_breakdown(bd):
    skill_map = {}
    for skill_name, info in bd.items():
        display_name = 'Basic Attack' if info['skill_type'] == 'basic' else info['display_name']
        if display_name not in skill_map:
            skill_map[display_name] = {'dps': 0.0, 'pct': 0.0}
        skill_map[display_name]['dps'] += info['dps']
        skill_map[display_name]['pct'] += info['pct_of_total']
    return skill_map

base_map = _aggregate_breakdown(cd_breakdown_base)
curr_map = _aggregate_breakdown(cd_breakdown_curr)

# Stacked horizontal bar chart for current CD value
curr_bar_data = pd.DataFrame([
    {'skill': name, 'pct': vals['pct'], 'dps': vals['dps']}
    for name, vals in curr_map.items()
]).sort_values('pct', ascending=False)

proportion_chart = alt.Chart(curr_bar_data).mark_bar().encode(
    x=alt.X('pct:Q', title='% of Total DPS', stack='zero'),
    color=alt.Color('skill:N', legend=alt.Legend(title='Skill')),
    tooltip=[
        alt.Tooltip('skill:N', title='Skill'),
        alt.Tooltip('pct:Q', title='% of Total', format='.1f'),
        alt.Tooltip('dps:Q', title='DPS', format=',.0f'),
    ],
).properties(height=60)

st.altair_chart(proportion_chart, use_container_width=True)

# Build comparison table with effective cooldowns
# Map display_name -> (skill_name, skill_data) for cooldown lookup
skills_for_job = get_skills_for_job(selected_job)
display_to_skill = {}
for sname, sdata in skills_for_job.items():
    display_to_skill[sdata.name] = (sname, sdata)

comparison_rows = []
all_skill_names = set(base_map.keys()) | set(curr_map.keys())
for skill_display in all_skill_names:
    base_pct = base_map.get(skill_display, {}).get('pct', 0)
    base_dps_val = base_map.get(skill_display, {}).get('dps', 0)
    curr_pct = curr_map.get(skill_display, {}).get('pct', 0)
    curr_dps_val = curr_map.get(skill_display, {}).get('dps', 0)
    dps_change = curr_dps_val - base_dps_val

    # Compute effective cooldown for this skill
    base_cd_str = "-"
    eff_cd_str = "-"
    if skill_display in display_to_skill:
        sname, sdata = display_to_skill[skill_display]
        if sdata.cooldown > 0:
            mastery_pct = cd_calc_curr.get_mastery_bonus(sname, "skill_cooldown_reduction") * 100
            base_cd_val = calculate_effective_cooldown(sdata.cooldown, mastery_pct, 0)
            eff_cd_val = calculate_effective_cooldown(sdata.cooldown, mastery_pct, selected_cd)
            base_cd_str = f"{base_cd_val:.1f}s"
            eff_cd_str = f"{eff_cd_val:.1f}s"

    # Build column label for the "current" state
    has_changes = selected_cd > 0 or selected_all_skills != all_skills
    curr_label_parts = []
    if selected_cd > 0:
        curr_label_parts.append(f"{selected_cd:.1f}s CD")
    if selected_all_skills != all_skills:
        diff = selected_all_skills - all_skills
        curr_label_parts.append(f"{diff:+d} AS")
    curr_label = ", ".join(curr_label_parts) if curr_label_parts else ""

    row = {
        'Skill': skill_display,
        'Base CD': base_cd_str,
        'Eff. CD': eff_cd_str,
        f'DPS (base)': f"{base_dps_val:,.0f}",
        'DPS Change': f"+{dps_change:,.0f}" if dps_change >= 0 else f"{dps_change:,.0f}",
        f'% (base)': f"{base_pct:.1f}%",
    }
    if has_changes:
        row[f'DPS ({curr_label})'] = f"{curr_dps_val:,.0f}"
        row[f'% ({curr_label})'] = f"{curr_pct:.1f}%"

    comparison_rows.append(row)

comparison_df = pd.DataFrame(comparison_rows)
# Sort by current DPS (or base DPS if no changes)
has_changes = selected_cd > 0 or selected_all_skills != all_skills
curr_label_parts = []
if selected_cd > 0:
    curr_label_parts.append(f"{selected_cd:.1f}s CD")
if selected_all_skills != all_skills:
    diff = selected_all_skills - all_skills
    curr_label_parts.append(f"{diff:+d} AS")
curr_label = ", ".join(curr_label_parts) if curr_label_parts else ""
sort_col = f'DPS ({curr_label})' if has_changes else 'DPS (base)'
comparison_df = comparison_df.sort_values(
    sort_col, ascending=False,
    key=lambda x: x.str.replace(',', '').str.replace('+', '').astype(float)
)
st.dataframe(comparison_df, hide_index=True, use_container_width=True)

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

# =============================================================================
# DPS Gain Visualization — CD Reduction × +All Skills
# =============================================================================
st.divider()
st.subheader("DPS Gain: CD Reduction × All Skills")
st.markdown("See how total DPS scales with different combinations of cooldown reduction and +All Skills.")

@st.cache_data(ttl=300, show_spinner="Calculating DPS gain surface...")
def calculate_dps_gain_surface(
    char_level: int,
    job_class_name: str,
    base_all_skills: int,
    skill_1st_bonus: int,
    skill_2nd_bonus: int,
    skill_3rd_bonus: int,
    skill_4th_bonus: int,
    num_enemies: int,
    mob_time_fraction: float,
    cd_steps: tuple,
    as_steps: tuple,
    attack_speed_pct: float = 0.0,
) -> pd.DataFrame:
    """Calculate total DPS for each (CD reduction, +All Skills) combination."""
    job_class = JobClass[job_class_name]
    results = []

    # Baseline DPS: 0s CD, base all_skills
    base_char = create_default_character(
        char_level, job_class, base_all_skills,
        skill_1st_bonus=skill_1st_bonus,
        skill_2nd_bonus=skill_2nd_bonus,
        skill_3rd_bonus=skill_3rd_bonus,
        skill_4th_bonus=skill_4th_bonus,
    )
    base_char.skill_cd_reduction = 0.0
    base_char.attack_speed_pct = attack_speed_pct
    base_calc = DPSCalculator(base_char, enemy_def=0.752)
    base_breakdown = base_calc.get_skill_damage_breakdown(
        fight_duration=60.0, num_enemies=num_enemies, mob_time_fraction=mob_time_fraction,
    )
    base_dps = sum(info['dps'] for info in base_breakdown.values())

    for as_val in as_steps:
        for cd_val in cd_steps:
            sim_char = create_default_character(
                char_level, job_class, as_val,
                skill_1st_bonus=skill_1st_bonus,
                skill_2nd_bonus=skill_2nd_bonus,
                skill_3rd_bonus=skill_3rd_bonus,
                skill_4th_bonus=skill_4th_bonus,
            )
            sim_char.skill_cd_reduction = cd_val
            sim_char.attack_speed_pct = attack_speed_pct
            sim_calc = DPSCalculator(sim_char, enemy_def=0.752)
            sim_breakdown = sim_calc.get_skill_damage_breakdown(
                fight_duration=60.0, num_enemies=num_enemies, mob_time_fraction=mob_time_fraction,
            )
            total_dps = sum(info['dps'] for info in sim_breakdown.values())
            gain_pct = ((total_dps / base_dps) - 1) * 100 if base_dps > 0 else 0

            results.append({
                'CD Reduction': cd_val,
                '+All Skills': as_val,
                'Total DPS': total_dps,
                'DPS Gain %': gain_pct,
            })

    return pd.DataFrame(results)

# All Skills steps: 0, 50, 100, ..., 400
as_steps = tuple(range(0, 401, 50))
cd_steps = tuple(x * 0.5 for x in range(0, 21))  # 0.0 to 10.0

gain_df = calculate_dps_gain_surface(
    char_level=level,
    job_class_name=selected_job.name,
    base_all_skills=all_skills,
    skill_1st_bonus=skill_1st,
    skill_2nd_bonus=skill_2nd,
    skill_3rd_bonus=skill_3rd,
    skill_4th_bonus=skill_4th,
    num_enemies=num_enemies,
    mob_time_fraction=mob_fraction,
    cd_steps=cd_steps,
    as_steps=as_steps,
    attack_speed_pct=float(attack_speed),
)

if not gain_df.empty:
    # Convert +All Skills to ordered categorical string for correct legend order
    as_order = [str(x) for x in range(0, 401, 50)]
    gain_df['AS Label'] = gain_df['+All Skills'].astype(str)

    gain_chart = alt.Chart(gain_df).mark_line(point=True).encode(
        x=alt.X('CD Reduction:Q', title='CD Reduction (seconds)'),
        y=alt.Y('DPS Gain %:Q', title=f'DPS Gain % (vs {all_skills} AS, 0s CD baseline)'),
        color=alt.Color('AS Label:N', title='+All Skills',
                        sort=as_order,
                        legend=alt.Legend(symbolType='stroke')),
        tooltip=[
            alt.Tooltip('CD Reduction:Q', title='CD Reduction', format='.1f'),
            alt.Tooltip('AS Label:N', title='+All Skills'),
            alt.Tooltip('Total DPS:Q', title='Total DPS', format=',.0f'),
            alt.Tooltip('DPS Gain %:Q', title='DPS Gain %', format='.1f'),
        ],
    ).properties(
        title=f"Total DPS Gain by CD Reduction at Different +All Skills (baseline: {all_skills} AS, 0s CD)",
        height=400,
    ).interactive()

    st.altair_chart(gain_chart, use_container_width=True)

    # Show a summary table: DPS gain at specific CD values for each AS level
    st.markdown("**DPS Gain Summary (% vs baseline)**")
    pivot_df = gain_df.pivot_table(
        index='+All Skills', columns='CD Reduction', values='DPS Gain %',
    )
    # Show only key CD values for readability
    key_cds = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    available_cds = [c for c in key_cds if c in pivot_df.columns]
    summary_df = pivot_df[available_cds].copy()
    summary_df.columns = [f"{c:.0f}s CD" for c in available_cds]
    summary_df.index.name = '+All Skills'
    summary_df = summary_df.map(lambda x: f"+{x:.1f}%")
    st.dataframe(summary_df, use_container_width=True)
else:
    st.warning("No data for DPS gain visualization")

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
    attack_speed_pct: float = 0.0,
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
        scaling_char.attack_speed_pct = attack_speed_pct
        scaling_calc = DPSCalculator(scaling_char, enemy_def=0.752)
        # Use long fight duration to eliminate simulation edge effects
        # (short fights cause DPS dips when skill priority reordering
        # pushes casts near the fight boundary)
        scaling_breakdown = scaling_calc.get_skill_damage_breakdown(
            fight_duration=1200.0,
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
    attack_speed_pct=float(attack_speed),
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

# =============================================================================
# Final Damage Buff Impact
# =============================================================================
st.subheader("Final Damage Buff Impact")
st.markdown("Uptime-weighted FD contribution from each buff skill and its effect on total DPS.")

_skills_dict = get_skills_for_job(selected_job)
_buff_data = []

for _sname, _skill in _skills_dict.items():
    if not _skill.skill_bonuses or 'final_damage' not in _skill.skill_bonuses:
        continue
    if not char.is_skill_unlocked(_sname):
        continue

    _fd = calc.get_skill_bonus_value(_sname, 'final_damage')
    _fd += calc.get_mastery_bonus(_sname, 'skill_final_damage')
    if _fd <= 0:
        continue

    if _skill.skill_type == SkillType.PASSIVE_STAT:
        _uptime = 1.0
    elif _skill.skill_type == SkillType.PASSIVE_PROC and getattr(_skill, 'buff_downtime', 0):
        _uptime = (_skill.cooldown - _skill.buff_downtime) / _skill.cooldown
    elif _skill.skill_type in (SkillType.BUFF, SkillType.PASSIVE_BUFF) and _skill.cooldown and _skill.duration:
        _eff_cd = char.get_effective_skill_cooldown(_skill.cooldown, 0)
        _uptime = calculate_buff_uptime(_eff_cd, _skill.duration, 60.0)
    else:
        _uptime = 1.0

    _avg_fd = _fd * _uptime
    _dps_impact = (1 - 1 / (1 + _avg_fd / 100)) * 100

    _buff_data.append({
        'Skill': _skill.name,
        'FD at Current Level': f"+{_fd:.1f}%",
        'Uptime': f"{_uptime * 100:.0f}%",
        'Avg FD': f"+{_avg_fd:.1f}%",
        'DPS Impact': f"+{_dps_impact:.1f}%",
    })

if _buff_data:
    st.dataframe(pd.DataFrame(_buff_data), hide_index=True, use_container_width=True)
    st.caption(
        "DPS Impact is the multiplicative contribution of that buff alone. "
        "Actual impact is slightly lower when stacked with other FD sources (diminishing returns)."
    )
else:
    st.info("No FD buff skills unlocked for this job at the current level.")

st.divider()

# =============================================================================
# Maple Hero Compounding Growth
# =============================================================================
st.subheader("Maple Hero Compounding Growth")
st.markdown(
    "Skills enhanced by Maple Hero gain FD *on top of* their own damage scaling — "
    "both values grow with +All Skills, compounding multiplicatively and producing a steeper growth curve."
)

_mh_skill = _skills_dict.get('maple_hero') or _skills_dict.get('maple_hero_mage')
if _mh_skill and _mh_skill.skill_bonuses and not scaling_df.empty:
    _enhanced_names = set(_mh_skill.skill_bonuses.keys())

    # Map internal skill names → display names used in scaling_df
    _name_map = {s.name: True for n, s in _skills_dict.items() if n in _enhanced_names}
    _enhanced_display = {
        _skills_dict[n].name for n in _enhanced_names if n in _skills_dict
    }

    # Tag each row
    _growth_tagged = growth_df.copy()
    _growth_tagged['Category'] = _growth_tagged['Skill'].apply(
        lambda s: 'Maple Hero Enhanced' if s in _enhanced_display else 'Standard'
    )

    # Mean growth per category
    _mean_growth = (
        _growth_tagged.groupby(['+All Skills', 'Category'], as_index=False)['Growth %'].mean()
    )

    _mh_chart = alt.Chart(_mean_growth).mark_line(point=True).encode(
        x=alt.X('+All Skills:Q', title='+All Skills Bonus'),
        y=alt.Y('Growth %:Q', title='Avg DPS Growth (% vs +0 baseline)'),
        color=alt.Color(
            'Category:N',
            scale=alt.Scale(
                domain=['Maple Hero Enhanced', 'Standard'],
                range=['#f97316', '#64748b'],
            ),
        ),
        tooltip=['+All Skills', 'Category', alt.Tooltip('Growth %:Q', format='.1f')],
    ).properties(
        title="Maple Hero Enhanced vs Standard Skills — Growth Rate Comparison",
        height=320,
    ).interactive()

    st.altair_chart(_mh_chart, use_container_width=True)

    # Show which skills are enhanced
    _enhanced_list = ', '.join(sorted(_enhanced_display))
    st.caption(f"Enhanced skills: {_enhanced_list}")
    st.caption(
        "Enhanced skills grow faster because each +1 to All Skills raises both the skill's own "
        "base damage AND Maple Hero's FD multiplier — two linear gains that multiply together."
    )
else:
    st.info("Maple Hero not available or no scaling data for this job.")

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

# =============================================================================
# Skill Point Returns — All Skills vs Job Skill Levels
# =============================================================================
st.subheader("Skill Point Returns: Equipment Bonuses")
st.markdown(
    "Starting from **0 bonus points**, how does total DPS grow as you invest in each stat? "
    "The left chart shows cumulative DPS gain — a bending curve means diminishing relative returns. "
    "The right chart shows how much each additional point is worth (as % of your DPS at that moment)."
)

@st.cache_data(ttl=300, show_spinner="Calculating skill point returns...")
def calculate_skill_point_returns_v2(
    char_level: int,
    job_class_name: str,
    all_skills_bonus: int,
    skill_1st_bonus: int,
    skill_2nd_bonus: int,
    skill_3rd_bonus: int,
    skill_4th_bonus: int,
    num_enemies: int,
    mob_time_fraction: float,
    max_points: int,
    step: int,
    skill_cd_reduction: float,
    attack_speed_pct: float,
) -> pd.DataFrame:
    job_class = JobClass[job_class_name]

    def _dps(as_val, s1, s2, s3, s4):
        c = create_default_character(char_level, job_class, as_val,
            skill_1st_bonus=s1, skill_2nd_bonus=s2,
            skill_3rd_bonus=s3, skill_4th_bonus=s4,
        )
        c.skill_cd_reduction = skill_cd_reduction
        c.attack_speed_pct = attack_speed_pct
        bd = DPSCalculator(c, enemy_def=0.752).get_skill_damage_breakdown(
            fight_duration=3600.0, num_enemies=num_enemies, mob_time_fraction=mob_time_fraction,
        )
        return sum(info['dps'] for info in bd.values())

    points = list(range(0, max_points + 1, step))
    stat_configs = [
        ('All Skills',    lambda n: _dps(n,               skill_1st_bonus, skill_2nd_bonus, skill_3rd_bonus, skill_4th_bonus)),
        ('1st Job Skill', lambda n: _dps(all_skills_bonus, n,              skill_2nd_bonus, skill_3rd_bonus, skill_4th_bonus)),
        ('2nd Job Skill', lambda n: _dps(all_skills_bonus, skill_1st_bonus, n,              skill_3rd_bonus, skill_4th_bonus)),
        ('3rd Job Skill', lambda n: _dps(all_skills_bonus, skill_1st_bonus, skill_2nd_bonus, n,              skill_4th_bonus)),
        ('4th Job Skill', lambda n: _dps(all_skills_bonus, skill_1st_bonus, skill_2nd_bonus, skill_3rd_bonus, n)),
    ]

    rows = []
    for stat_name, dps_fn in stat_configs:
        dps_at = {n: dps_fn(n) for n in points}
        baseline = dps_at[0] if dps_at[0] > 0 else 1.0
        for i, n in enumerate(points[1:], 1):
            prev_n = points[i - 1]
            cumulative_pct = (dps_at[n] / baseline - 1) * 100
            prev_dps = dps_at[prev_n] if dps_at[prev_n] > 0 else 1.0
            marginal_pct = (dps_at[n] - dps_at[prev_n]) / prev_dps / step * 100
            rows.append({
                'Points Added': n,
                'Stat': stat_name,
                'Cumulative DPS Gain %': round(cumulative_pct, 3),
                'Marginal DPS %/pt': round(marginal_pct, 4),
            })

    return pd.DataFrame(rows)


_returns_df = calculate_skill_point_returns_v2(
    char_level=level,
    job_class_name=selected_job.name,
    all_skills_bonus=all_skills,
    skill_1st_bonus=skill_1st,
    skill_2nd_bonus=skill_2nd,
    skill_3rd_bonus=skill_3rd,
    skill_4th_bonus=skill_4th,
    num_enemies=num_enemies,
    mob_time_fraction=mob_fraction,
    max_points=200,
    step=5,
    skill_cd_reduction=selected_cd,
    attack_speed_pct=float(attack_speed),
)

if not _returns_df.empty:
    _cum_chart = alt.Chart(_returns_df).mark_line().encode(
        x=alt.X('Points Added:Q', title='Bonus Points Added'),
        y=alt.Y('Cumulative DPS Gain %:Q', title='Total DPS Gain %'),
        color=alt.Color('Stat:N', legend=alt.Legend(title='Stat')),
        tooltip=[
            alt.Tooltip('Points Added:Q', title='Points'),
            alt.Tooltip('Stat:N'),
            alt.Tooltip('Cumulative DPS Gain %:Q', format='.1f', title='Total Gain %'),
        ],
    ).properties(title="Cumulative DPS Gain", height=320).interactive()

    # Marginal: raw scatter + LOESS trend per stat
    _scatter = alt.Chart(_returns_df).mark_point(opacity=0.25, size=20).encode(
        x=alt.X('Points Added:Q', title='Bonus Points Added'),
        y=alt.Y('Marginal DPS %/pt:Q', title='DPS % gained per point'),
        color=alt.Color('Stat:N', legend=None),
    )
    _trend = alt.Chart(_returns_df).transform_loess(
        'Points Added', 'Marginal DPS %/pt', groupby=['Stat'], bandwidth=0.4,
    ).mark_line(strokeWidth=2).encode(
        x='Points Added:Q',
        y='Marginal DPS %/pt:Q',
        color=alt.Color('Stat:N', legend=alt.Legend(title='Stat')),
        tooltip=[
            alt.Tooltip('Points Added:Q', title='Points'),
            alt.Tooltip('Stat:N'),
            alt.Tooltip('Marginal DPS %/pt:Q', format='.4f', title='DPS %/pt (trend)'),
        ],
    )
    _marg_chart = (_scatter + _trend).properties(
        title="Marginal DPS per Point (faint dots = raw, solid = trend)",
        height=320,
    ).interactive()

    col_cum, col_marg = st.columns(2)
    with col_cum:
        st.altair_chart(_cum_chart, use_container_width=True)
    with col_marg:
        st.altair_chart(_marg_chart, use_container_width=True)
    st.caption(
        "Cumulative curve bending = diminishing relative returns (same absolute gain, growing DPS base). "
        "Marginal trend declining = each point is worth a smaller % of your current DPS. "
        "All Skills is worth more than a single job bonus because it boosts all tiers simultaneously."
    )
else:
    st.warning("No data for skill point returns analysis")

st.subheader("DPS Gained per Level (Leveling from Scratch)")
st.markdown(
    "Starting from level 10 with no equipment bonuses — how much does each character level's "
    "3 skill points add, as **% of your DPS at that moment**? "
    "The INC50 kink in Maple Hero shows as a drop in the 4th job line."
)

@st.cache_data(ttl=300, show_spinner="Calculating leveling curve...")
def calculate_leveling_curve(
    job_class_name: str,
    all_skills_bonus: int,
    num_enemies: int,
    mob_time_fraction: float,
    skill_cd_reduction: float,
    attack_speed_pct: float,
) -> pd.DataFrame:
    job_class = JobClass[job_class_name]
    levels = list(range(10, 141))

    def _dps(lv):
        c = create_default_character(lv, job_class, all_skills_bonus)
        c.skill_cd_reduction = skill_cd_reduction
        c.attack_speed_pct = attack_speed_pct
        bd = DPSCalculator(c, enemy_def=0.752).get_skill_damage_breakdown(
            fight_duration=3600.0, num_enemies=num_enemies, mob_time_fraction=mob_time_fraction,
        )
        return sum(info['dps'] for info in bd.values())

    dps_at = {lv: _dps(lv) for lv in levels}
    baseline = dps_at[10] if dps_at[10] > 0 else 1.0

    def _job_label(lv):
        if lv < 30:  return '1st Job'
        if lv < 60:  return '2nd Job'
        if lv < 100: return '3rd Job'
        return '4th Job'

    rows = []
    for i in range(1, len(levels)):
        prev_lv, curr_lv = levels[i - 1], levels[i]
        prev_dps = dps_at[prev_lv] if dps_at[prev_lv] > 0 else 1.0
        marginal_per_pt = (dps_at[curr_lv] - prev_dps) / prev_dps / 3 * 100
        cumulative_pct  = (dps_at[curr_lv] / baseline - 1) * 100
        rows.append({
            'Character Level': curr_lv,
            'Job Tier': _job_label(curr_lv),
            'Marginal DPS %/pt': round(marginal_per_pt, 4),
            'Cumulative DPS Gain %': round(cumulative_pct, 1),
        })

    return pd.DataFrame(rows)


_lv_df = calculate_leveling_curve(
    job_class_name=selected_job.name,
    all_skills_bonus=all_skills,
    num_enemies=num_enemies,
    mob_time_fraction=mob_fraction,
    skill_cd_reduction=selected_cd,
    attack_speed_pct=float(attack_speed),
)

if not _lv_df.empty:
    _kink_lv = 100 + (120 - all_skills) / 3
    _job_sort = ['1st Job', '2nd Job', '3rd Job', '4th Job']

    # Left: cumulative DPS gain coloured by job tier
    _lv_cum = alt.Chart(_lv_df).mark_area(opacity=0.15).encode(
        x=alt.X('Character Level:Q'),
        y=alt.Y('Cumulative DPS Gain %:Q', title='Total DPS Gain % (vs L10)'),
        color=alt.Color('Job Tier:N', sort=_job_sort),
    ) + alt.Chart(_lv_df).mark_line(strokeWidth=2).encode(
        x='Character Level:Q',
        y='Cumulative DPS Gain %:Q',
        color=alt.Color('Job Tier:N', sort=_job_sort,
                        legend=alt.Legend(title='Job Tier')),
        tooltip=['Character Level:Q', 'Job Tier:N',
                 alt.Tooltip('Cumulative DPS Gain %:Q', format='.1f')],
    )

    # Right: marginal per point — raw + LOESS trend
    _lv_scatter = alt.Chart(_lv_df).mark_point(opacity=0.2, size=18).encode(
        x=alt.X('Character Level:Q'),
        y=alt.Y('Marginal DPS %/pt:Q', title='DPS % per skill point'),
        color=alt.Color('Job Tier:N', sort=_job_sort, legend=None),
    )
    _lv_trend = alt.Chart(_lv_df).transform_loess(
        'Character Level', 'Marginal DPS %/pt', groupby=['Job Tier'], bandwidth=0.35,
    ).mark_line(strokeWidth=2).encode(
        x='Character Level:Q',
        y='Marginal DPS %/pt:Q',
        color=alt.Color('Job Tier:N', sort=_job_sort,
                        legend=alt.Legend(title='Job Tier')),
        tooltip=['Character Level:Q', 'Job Tier:N',
                 alt.Tooltip('Marginal DPS %/pt:Q', format='.4f')],
    )

    # Orange kink line on marginal chart if it falls in the 4th job range
    _kink_layer = alt.layer(_lv_scatter, _lv_trend)
    if 100 <= _kink_lv <= 140:
        _kink_rule = alt.Chart(pd.DataFrame({'x': [int(_kink_lv)]})).mark_rule(
            strokeDash=[4, 4], color='orange', strokeWidth=1.5,
        ).encode(x='x:Q')
        _kink_layer = alt.layer(_lv_scatter, _lv_trend, _kink_rule)

    _lv_marg = _kink_layer.properties(
        title="Marginal DPS per Skill Point (faint = raw, solid = trend)",
        height=320,
    ).interactive()

    _lv_cum_chart = _lv_cum.properties(
        title="Cumulative DPS Growth While Leveling",
        height=320,
    ).interactive()

    col_lv1, col_lv2 = st.columns(2)
    with col_lv1:
        st.altair_chart(_lv_cum_chart, use_container_width=True)
    with col_lv2:
        st.altair_chart(_lv_marg, use_container_width=True)

    if 100 <= _kink_lv <= 140:
        st.caption(
            f"Orange line (~L{int(_kink_lv)}): Maple Hero's INC50 growth slows 5× here. "
            f"With +{all_skills} All Skills this kink falls at character level ~{int(_kink_lv)}. "
            "Raise +All Skills in the sidebar to pull the kink earlier."
        )
    else:
        st.caption(
            f"With +{all_skills} All Skills, Maple Hero's INC50 kink is outside L10–140 "
            f"(falls at ~L{int(_kink_lv):.0f}). "
            "Lower +All Skills to bring it into view."
        )
else:
    st.warning("No leveling curve data available")

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
