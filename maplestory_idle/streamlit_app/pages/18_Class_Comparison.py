"""
Class Comparison
Compare all job classes on equal footing using standardized stats.
Shows absolute DPS comparison, skill-type composition, and per-stat sensitivity curves.
"""
import streamlit as st
import pandas as pd
import altair as alt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from game.skills import DPSCalculator, create_default_character, SKILLS_BY_JOB
from game.job_classes import JobClass, JOB_DISPLAY_NAMES
from game.stage_settings import COMBAT_SCENARIO_PARAMS, CombatMode

st.set_page_config(page_title="Class Comparison", page_icon="⚖️", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data

AVAILABLE_JOBS = list(SKILLS_BY_JOB.keys())

JOB_COLORS = {
    JobClass.BOWMASTER:             "#22c55e",
    JobClass.MARKSMAN:              "#3b82f6",
    JobClass.NIGHT_LORD:            "#a855f7",
    JobClass.SHADOWER:              "#f97316",
    JobClass.ARCHMAGE_FIRE_POISON:  "#dc2626",
    JobClass.ARCHMAGE_ICE_LIGHTNING:"#06b6d4",
    JobClass.HERO:                  "#facc15",
    JobClass.DARK_KNIGHT:           "#ef4444",
    JobClass.BUCCANEER:             "#0d9488",
    JobClass.CORSAIR:               "#d97706",
}

FIGHT_DURATION = 3600.0  # Long fight to eliminate cast-count edge effects

# =============================================================================
# Cached computation functions (module-level so Streamlit can cache them)
# =============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def _single_dps(
    char_level: int,
    job_class_name: str,
    all_skills_bonus: int,
    cd: float,
    as_pct: float,
    n_enemies: int,
    mob_frac: float,
    buff_dur_pct: float = 0.0,
) -> float:
    job_class = JobClass[job_class_name]
    char = create_default_character(char_level, job_class, all_skills_bonus)
    char.skill_cd_reduction = cd
    char.attack_speed_pct = as_pct
    char.buff_duration_pct = buff_dur_pct
    calc = DPSCalculator(char, enemy_def=0.752)
    bd = calc.get_skill_damage_breakdown(FIGHT_DURATION, n_enemies, mob_frac)
    return sum(info['dps'] for info in bd.values())


@st.cache_data(ttl=300, show_spinner=False)
def _breakdown_dps(
    char_level: int,
    job_class_name: str,
    all_skills_bonus: int,
    cd: float,
    as_pct: float,
    n_enemies: int,
    mob_frac: float,
) -> dict:
    """Return skill-type DPS totals and mob/boss phase DPS for one class."""
    job_class = JobClass[job_class_name]
    char = create_default_character(char_level, job_class, all_skills_bonus)
    char.skill_cd_reduction = cd
    char.attack_speed_pct = as_pct
    calc = DPSCalculator(char, enemy_def=0.752)
    bd = calc.get_skill_damage_breakdown(FIGHT_DURATION, n_enemies, mob_frac)

    type_totals = {"Basic Attack": 0.0, "Active Skills": 0.0, "Summons": 0.0, "Procs": 0.0}
    mob_dps_total  = 0.0
    boss_dps_total = 0.0

    for info in bd.values():
        stype = info.get('skill_type', '')
        if stype == 'basic':
            type_totals["Basic Attack"] += info['dps']
        elif stype == 'active':
            type_totals["Active Skills"] += info['dps']
        elif stype == 'summon':
            type_totals["Summons"] += info['dps']
        else:
            type_totals["Procs"] += info['dps']

        # mob_damage / boss_damage are total damage values over the full fight
        mob_dps_total  += info.get('mob_damage', 0.0) / FIGHT_DURATION
        boss_dps_total += info.get('boss_damage', 0.0) / FIGHT_DURATION

    return {
        "types": type_totals,
        "mob_dps":  mob_dps_total,
        "boss_dps": boss_dps_total,
    }


@st.cache_data(ttl=300, show_spinner="Calculating stat sensitivity...")
def _sweep(
    char_level: int,
    base_all_skills: int,
    base_cd: float,
    base_as_pct: float,
    base_buff_dur_pct: float,
    sweep_stat: str,
    sweep_values: tuple,
    n_enemies: int,
    mob_frac: float,
    job_class_names: tuple,
) -> pd.DataFrame:
    rows = []
    for job_name in job_class_names:
        baseline = None
        for val in sweep_values:
            if sweep_stat == "all_skills":
                dps = _single_dps(char_level, job_name, val, base_cd, base_as_pct, n_enemies, mob_frac, float(base_buff_dur_pct))
            elif sweep_stat == "cd_reduction":
                dps = _single_dps(char_level, job_name, base_all_skills, val, base_as_pct, n_enemies, mob_frac, float(base_buff_dur_pct))
            elif sweep_stat == "attack_speed":
                dps = _single_dps(char_level, job_name, base_all_skills, base_cd, float(val), n_enemies, mob_frac, float(base_buff_dur_pct))
            else:  # buff_duration
                dps = _single_dps(char_level, job_name, base_all_skills, base_cd, base_as_pct, n_enemies, mob_frac, float(val))
            if baseline is None:
                baseline = dps if dps > 0 else 1.0
            rows.append({
                'Stat Value': val,
                'Class': JOB_DISPLAY_NAMES[JobClass[job_name]],
                'DPS Gain %': round((dps / baseline - 1) * 100, 2),
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=300, show_spinner=False)
def _level_sweep(
    all_skills_bonus: int,
    cd: float,
    as_pct: float,
    buff_dur_pct: float,
    n_enemies: int,
    mob_frac: float,
    levels: tuple,
    job_class_names: tuple,
) -> pd.DataFrame:
    """Compute DPS for every (level, job) combination with the given stats."""
    rows = []
    for job_name in job_class_names:
        for lvl in levels:
            dps = _single_dps(lvl, job_name, all_skills_bonus, cd, float(as_pct),
                               n_enemies, mob_frac, float(buff_dur_pct))
            rows.append({
                'Level': lvl,
                'Class': JOB_DISPLAY_NAMES[JobClass[job_name]],
                'DPS': dps,
            })
    return pd.DataFrame(rows)


# =============================================================================
# Sidebar
# =============================================================================
st.sidebar.header("Configuration")

level = st.sidebar.slider("Character Level", 10, 200, min(data.character_level, 200), step=5)

combat_modes = {
    CombatMode.STAGE:        "Stage (60% mob, 40% boss)",
    CombatMode.BOSS:         "Boss (100% boss)",
    CombatMode.CHAPTER_HUNT: "Chapter Hunt (100% mob)",
    CombatMode.WORLD_BOSS:   "World Boss (100% boss)",
}
selected_mode = st.sidebar.selectbox(
    "Combat Mode", list(combat_modes.keys()), format_func=lambda x: combat_modes[x]
)
scenario = COMBAT_SCENARIO_PARAMS.get(selected_mode)
num_enemies  = scenario.num_enemies if scenario else 12
mob_fraction = scenario.mob_time_fraction if scenario else 0.6

all_skills = st.sidebar.slider("+All Skills", 0, 200, min(data.all_skills, 200), step=5)
cd_reduction = st.sidebar.slider("CD Reduction (s)", 0.0, 10.0, 0.0, step=0.5)
attack_speed_pct = st.sidebar.slider("Attack Speed %", 0, 150, 0, step=5)

st.sidebar.info(
    "Standardized stats used for all classes: "
    "50K ATK · 30K main stat · 150% damage · 100% boss · 50% normal · "
    "80% crit rate · 150% crit damage · 50% final damage · 30% def pen"
)

# =============================================================================
# Page title
# =============================================================================
st.title("⚖️ Class Comparison")
st.markdown(
    "All classes use identical standardized stats — differences reflect skill rotations, "
    "masteries, and class mechanics rather than user gear."
)

# =============================================================================
# Section 1: DPS Snapshot
# =============================================================================
st.subheader("DPS Snapshot")

with st.spinner("Computing DPS for all classes..."):
    dps_map = {
        job: _single_dps(level, job.name, all_skills, cd_reduction, float(attack_speed_pct),
                         num_enemies, mob_fraction)
        for job in AVAILABLE_JOBS
    }

top_dps = max(dps_map.values()) if dps_map else 1.0
snap_rows = sorted(
    [
        {
            'Class': JOB_DISPLAY_NAMES[job],
            'DPS': dps_map[job],
            'vs Top': round(dps_map[job] / top_dps * 100, 1),
        }
        for job in AVAILABLE_JOBS
    ],
    key=lambda r: -r['DPS'],
)
snap_df = pd.DataFrame(snap_rows)

col_bar, col_tbl = st.columns([2, 1])
with col_bar:
    bar_chart = alt.Chart(snap_df).mark_bar().encode(
        x=alt.X('DPS:Q', title='DPS (standardized stats)', axis=alt.Axis(format='~s')),
        y=alt.Y('Class:N', sort='-x', title=''),
        color=alt.Color('Class:N',
            scale=alt.Scale(
                domain=[JOB_DISPLAY_NAMES[j] for j in AVAILABLE_JOBS],
                range=[JOB_COLORS[j] for j in AVAILABLE_JOBS],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip('Class:N'),
            alt.Tooltip('DPS:Q', format=',.0f', title='DPS'),
            alt.Tooltip('vs Top:Q', title='% of Top', format='.1f'),
        ],
    ).properties(height=260).interactive()
    st.altair_chart(bar_chart, use_container_width=True)

with col_tbl:
    display_snap = snap_df.copy()
    display_snap['DPS'] = display_snap['DPS'].apply(lambda x: f"{x:,.0f}")
    display_snap['vs Top'] = display_snap['vs Top'].apply(lambda x: f"{x:.1f}%")
    st.dataframe(display_snap, hide_index=True, use_container_width=True)

st.divider()

# =============================================================================
# Section 2: Boss vs Mob Performance (separate graphs)
# =============================================================================
st.subheader("Mob vs Boss Performance")
st.markdown(
    "Pure mob performance uses Chapter Hunt settings (12 enemies, 100% mob). "
    "Pure boss performance uses Boss settings (1 enemy, 100% boss). "
    "These are independent of the combat mode selected in the sidebar."
)

with st.spinner("Computing mob and boss performance..."):
    mob_dps_map  = {
        job: _single_dps(level, job.name, all_skills, cd_reduction, float(attack_speed_pct),
                         12, 1.0)
        for job in AVAILABLE_JOBS
    }
    boss_dps_map = {
        job: _single_dps(level, job.name, all_skills, cd_reduction, float(attack_speed_pct),
                         1, 0.0)
        for job in AVAILABLE_JOBS
    }

mob_rows  = [{'Class': JOB_DISPLAY_NAMES[j], 'DPS': mob_dps_map[j]}  for j in AVAILABLE_JOBS]
boss_rows = [{'Class': JOB_DISPLAY_NAMES[j], 'DPS': boss_dps_map[j]} for j in AVAILABLE_JOBS]
mob_df    = pd.DataFrame(mob_rows)
boss_df   = pd.DataFrame(boss_rows)

col_mob, col_boss = st.columns(2)

with col_mob:
    st.markdown("**Mob Grinding** (Chapter Hunt — 12 enemies)")
    mob_order = [JOB_DISPLAY_NAMES[j] for j in sorted(AVAILABLE_JOBS, key=lambda j: -mob_dps_map[j])]
    mob_chart = alt.Chart(mob_df).mark_bar().encode(
        x=alt.X('DPS:Q', title='DPS', axis=alt.Axis(format='~s')),
        y=alt.Y('Class:N', sort=mob_order, title=''),
        color=alt.Color('Class:N',
            scale=alt.Scale(
                domain=[JOB_DISPLAY_NAMES[j] for j in AVAILABLE_JOBS],
                range=[JOB_COLORS[j] for j in AVAILABLE_JOBS],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip('Class:N'),
            alt.Tooltip('DPS:Q', format=',.0f', title='Mob DPS'),
        ],
    ).properties(height=260).interactive()
    st.altair_chart(mob_chart, use_container_width=True)

with col_boss:
    st.markdown("**Single Target Boss**")
    boss_order = [JOB_DISPLAY_NAMES[j] for j in sorted(AVAILABLE_JOBS, key=lambda j: -boss_dps_map[j])]
    boss_chart = alt.Chart(boss_df).mark_bar().encode(
        x=alt.X('DPS:Q', title='DPS', axis=alt.Axis(format='~s')),
        y=alt.Y('Class:N', sort=boss_order, title=''),
        color=alt.Color('Class:N',
            scale=alt.Scale(
                domain=[JOB_DISPLAY_NAMES[j] for j in AVAILABLE_JOBS],
                range=[JOB_COLORS[j] for j in AVAILABLE_JOBS],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip('Class:N'),
            alt.Tooltip('DPS:Q', format=',.0f', title='Boss DPS'),
        ],
    ).properties(height=260).interactive()
    st.altair_chart(boss_chart, use_container_width=True)

# Summary table comparing mob vs boss ranking
ratio_rows = []
top_mob  = max(mob_dps_map.values())  if mob_dps_map  else 1.0
top_boss = max(boss_dps_map.values()) if boss_dps_map else 1.0
for job in sorted(AVAILABLE_JOBS, key=lambda j: -mob_dps_map[j]):
    jname = JOB_DISPLAY_NAMES[job]
    ratio_rows.append({
        'Class':        jname,
        'Mob DPS':      f"{mob_dps_map[job]:,.0f}",
        'Mob vs Top':   f"{mob_dps_map[job] / top_mob * 100:.1f}%",
        'Boss DPS':     f"{boss_dps_map[job]:,.0f}",
        'Boss vs Top':  f"{boss_dps_map[job] / top_boss * 100:.1f}%",
    })

st.dataframe(pd.DataFrame(ratio_rows), hide_index=True, use_container_width=True)
st.caption("Rankings may differ between mob and boss modes — some classes excel at AoE while others specialise in single-target.")

st.divider()

# =============================================================================
# Section 3: Damage Source Composition
# =============================================================================
st.subheader("Damage Source Composition")
st.markdown("What proportion of each class's DPS comes from basic attacks, active skills, summons, and procs?")

with st.spinner("Computing skill breakdowns..."):
    comp_rows = []
    for job in AVAILABLE_JOBS:
        bd_result = _breakdown_dps(
            level, job.name, all_skills, cd_reduction, float(attack_speed_pct),
            num_enemies, mob_fraction,
        )
        type_totals = bd_result["types"]
        total = sum(type_totals.values()) or 1.0
        for stype, val in type_totals.items():
            comp_rows.append({
                'Class': JOB_DISPLAY_NAMES[job],
                'Source': stype,
                'DPS': val,
                'Pct': round(val / total * 100, 1),
            })

comp_df = pd.DataFrame(comp_rows)

SOURCE_COLORS = {
    "Basic Attack":  "#94a3b8",
    "Active Skills": "#22c55e",
    "Summons":       "#f59e0b",
    "Procs":         "#a855f7",
}

# Sort classes by their total DPS (matches snapshot order)
class_order = [JOB_DISPLAY_NAMES[j] for j in sorted(AVAILABLE_JOBS, key=lambda j: -dps_map[j])]

comp_chart = alt.Chart(comp_df).mark_bar().encode(
    x=alt.X('Pct:Q', title='% of Total DPS', stack='zero'),
    y=alt.Y('Class:N', sort=class_order, title=''),
    color=alt.Color('Source:N',
        scale=alt.Scale(
            domain=list(SOURCE_COLORS.keys()),
            range=list(SOURCE_COLORS.values()),
        ),
        legend=alt.Legend(title='Damage Source', orient='top'),
    ),
    tooltip=[
        alt.Tooltip('Class:N'),
        alt.Tooltip('Source:N'),
        alt.Tooltip('Pct:Q', format='.1f', title='%'),
        alt.Tooltip('DPS:Q', format=',.0f'),
    ],
).properties(height=260).interactive()

st.altair_chart(comp_chart, use_container_width=True)

st.divider()

# =============================================================================
# Section 3: Stat Sensitivity
# =============================================================================
st.subheader("Stat Sensitivity by Class")
st.markdown(
    "Each line shows cumulative DPS gain (%) from zero of the swept stat. "
    "Other stats are held at sidebar values. "
    "A steeper curve = that class gets more value from this stat."
)

stat_choice = st.radio(
    "Sweep stat",
    ["All Skills +", "CD Reduction (s)", "Attack Speed (%)", "Buff Duration (%)"],
    horizontal=True,
)

if stat_choice == "All Skills +":
    sweep_key  = "all_skills"
    sweep_vals = tuple(range(0, 201, 5))
    x_title    = "+All Skills Bonus"
    s_as       = float(attack_speed_pct)
    s_cd       = cd_reduction
    s_buff_dur = 0.0
elif stat_choice == "CD Reduction (s)":
    sweep_key  = "cd_reduction"
    sweep_vals = tuple(round(i * 0.5, 1) for i in range(21))  # 0.0 → 10.0
    x_title    = "CD Reduction (s)"
    s_as       = float(attack_speed_pct)
    s_cd       = 0.0  # not used when sweeping
    s_buff_dur = 0.0
elif stat_choice == "Attack Speed (%)":
    sweep_key  = "attack_speed"
    sweep_vals = tuple(range(0, 156, 5))  # 0 → 150
    x_title    = "Attack Speed %"
    s_as       = 0.0   # not used when sweeping
    s_cd       = cd_reduction
    s_buff_dur = 0.0
else:
    sweep_key  = "buff_duration"
    sweep_vals = tuple(range(0, 105, 5))  # 0 → 100
    x_title    = "Buff Duration %"
    s_as       = float(attack_speed_pct)
    s_cd       = cd_reduction
    s_buff_dur = 0.0  # not used when sweeping

sweep_df = _sweep(
    char_level=level,
    base_all_skills=all_skills if sweep_key != "all_skills" else 0,
    base_cd=s_cd,
    base_as_pct=s_as,
    base_buff_dur_pct=s_buff_dur,
    sweep_stat=sweep_key,
    sweep_values=sweep_vals,
    n_enemies=num_enemies,
    mob_frac=mob_fraction,
    job_class_names=tuple(j.name for j in AVAILABLE_JOBS),
)

if not sweep_df.empty:
    job_display_order = [JOB_DISPLAY_NAMES[j] for j in AVAILABLE_JOBS]
    job_color_range   = [JOB_COLORS[j] for j in AVAILABLE_JOBS]

    sweep_chart = alt.Chart(sweep_df).mark_line(strokeWidth=2.5).encode(
        x=alt.X('Stat Value:Q', title=x_title),
        y=alt.Y('DPS Gain %:Q', title='Cumulative DPS Gain %'),
        color=alt.Color('Class:N',
            scale=alt.Scale(domain=job_display_order, range=job_color_range),
            legend=alt.Legend(title='Class', orient='right'),
        ),
        tooltip=[
            alt.Tooltip('Stat Value:Q', title=x_title),
            alt.Tooltip('Class:N'),
            alt.Tooltip('DPS Gain %:Q', format='.1f', title='Total Gain %'),
        ],
    ).properties(height=400).interactive()

    st.altair_chart(sweep_chart, use_container_width=True)

    # Summary table: total gain and marginal at last point
    last_val   = sweep_vals[-1]
    prev_val   = sweep_vals[-2] if len(sweep_vals) > 1 else sweep_vals[-1]
    step_size  = (last_val - prev_val) or 1

    summary_rows = []
    for job in sorted(AVAILABLE_JOBS, key=lambda j: -dps_map[j]):
        jname = JOB_DISPLAY_NAMES[job]
        sub = sweep_df[sweep_df['Class'] == jname]
        at_last = sub[sub['Stat Value'] == last_val]['DPS Gain %'].values
        at_prev = sub[sub['Stat Value'] == prev_val]['DPS Gain %'].values
        if len(at_last) and len(at_prev):
            total_gain = at_last[0]
            marginal   = (at_last[0] - at_prev[0]) / step_size
            summary_rows.append({
                'Class': jname,
                f'Total gain at {x_title}={last_val}': f'{total_gain:.1f}%',
                'Last marginal gain/unit': f'{marginal:.3f}%',
            })

    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)

    if sweep_key == "cd_reduction":
        st.info(
            "**CD Reduction note:** The gain curve can appear non-linear because CD reduction affects "
            "ALL skills simultaneously, including buffs like Sharp Eyes. At certain CD values, "
            "a high-damage skill may shift into — or out of — a buff's active window, producing "
            "jumps or plateaus. Total DPS gain at 8s flat CD is typically 8–15% for most classes."
        )
    elif sweep_key == "buff_duration":
        st.info(
            "**Buff Duration note:** Classes with high-value timed FD buffs (Shadower's Into Darkness "
            "and Smokescreen, Bowmaster's Sharp Eyes) gain the most from buff duration. "
            "The effect grows non-linearly as buff uptime approaches 100% of the cooldown cycle."
        )
    else:
        st.caption(
            "Baseline for each class is its DPS at the swept stat = 0, "
            "with other stats fixed at sidebar values."
        )

st.divider()

# =============================================================================
# Section 5: DPS by Character Level
# =============================================================================
st.subheader("DPS by Character Level")
st.markdown(
    "Absolute DPS for each class at every level. "
    "Mob and boss charts are always in sync — adjust the controls below to see "
    "how different builds shift the level scaling curves."
)

lv_col1, lv_col2, lv_col3, lv_col4 = st.columns(4)
with lv_col1:
    lv_all_skills = st.slider("All Skills +", 0, 200, 0, step=5, key="lv_all_skills")
with lv_col2:
    lv_cd = st.slider("CD Reduction (s)", 0.0, 10.0, 0.0, step=0.5, key="lv_cd")
with lv_col3:
    lv_as_pct = st.slider("Attack Speed %", 0, 150, 0, step=5, key="lv_as_pct")
with lv_col4:
    lv_buff_dur = st.slider("Buff Duration %", 0, 100, 0, step=5, key="lv_buff_dur")

LEVEL_POINTS = tuple(range(100, 145, 5))  # 100, 105, 110, ... 140
job_names_tuple = tuple(j.name for j in AVAILABLE_JOBS)

with st.spinner("Computing DPS by level..."):
    mob_lv_df  = _level_sweep(lv_all_skills, lv_cd, lv_as_pct, lv_buff_dur,
                               12, 1.0, LEVEL_POINTS, job_names_tuple)
    boss_lv_df = _level_sweep(lv_all_skills, lv_cd, lv_as_pct, lv_buff_dur,
                               1, 0.0, LEVEL_POINTS, job_names_tuple)

job_display_order = [JOB_DISPLAY_NAMES[j] for j in AVAILABLE_JOBS]
job_color_range   = [JOB_COLORS[j] for j in AVAILABLE_JOBS]

color_enc = alt.Color('Class:N',
    scale=alt.Scale(domain=job_display_order, range=job_color_range),
    legend=alt.Legend(title='Class', orient='bottom', columns=3),
)

lv_mob_chart = (
    alt.Chart(mob_lv_df)
    .mark_line(strokeWidth=2)
    .encode(
        x=alt.X('Level:Q', title='Character Level', scale=alt.Scale(domain=[100, 140])),
        y=alt.Y('DPS:Q', title='Mob DPS', axis=alt.Axis(format='~s')),
        color=color_enc,
        tooltip=[
            alt.Tooltip('Level:Q'),
            alt.Tooltip('Class:N'),
            alt.Tooltip('DPS:Q', format=',.0f', title='Mob DPS'),
        ],
    )
    .properties(title='Mob DPS by Level  (12 enemies, 100% mob)', height=380)
    .interactive()
)

lv_boss_chart = (
    alt.Chart(boss_lv_df)
    .mark_line(strokeWidth=2)
    .encode(
        x=alt.X('Level:Q', title='Character Level', scale=alt.Scale(domain=[100, 140])),
        y=alt.Y('DPS:Q', title='Boss DPS', axis=alt.Axis(format='~s')),
        color=color_enc,
        tooltip=[
            alt.Tooltip('Level:Q'),
            alt.Tooltip('Class:N'),
            alt.Tooltip('DPS:Q', format=',.0f', title='Boss DPS'),
        ],
    )
    .properties(title='Boss DPS by Level  (1 enemy, 100% boss)', height=380)
    .interactive()
)

lv_chart_col1, lv_chart_col2 = st.columns(2)
with lv_chart_col1:
    st.altair_chart(lv_mob_chart, use_container_width=True)
with lv_chart_col2:
    st.altair_chart(lv_boss_chart, use_container_width=True)

st.caption(
    "Both charts use the same four controls above. "
    "Jumps in the curves correspond to skill unlock thresholds and mastery nodes."
)
