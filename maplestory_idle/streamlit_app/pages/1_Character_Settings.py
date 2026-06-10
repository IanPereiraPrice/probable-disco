"""
Character Settings Page
Configure character level, combat mode, and chapter.
All Skills bonus is auto-calculated from equipment sources.
"""
import streamlit as st
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.data_manager import save_user_data, export_user_data_csv, import_user_data_csv, EQUIPMENT_SLOTS
from utils.dps_calculator import (
    aggregate_stats as shared_aggregate_stats,
    calculate_dps as shared_calculate_dps,
)
from constants import ENEMY_DEFENSE_VALUES
from game.equipment import get_amplify_multiplier
from game.job_classes import JobClass, JOB_DISPLAY_NAMES, get_job_stats, get_main_stat_name, get_secondary_stat_name
from game.skills import get_skill_points_for_job, Job
from game.unique_stats import (
    UNIQUE_STAT_OPTIONS,
    SKIP_FOR_DPS,
    available_unique_stat_points,
    auto_allocate,
    points_spent,
)

st.set_page_config(page_title="Character Settings", page_icon="⚔️", layout="wide")

# Check if logged in
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def auto_save():
    """Save data after changes."""
    save_user_data(st.session_state.username, data)


def calculate_all_skills() -> int:
    """
    Calculate total All Skills bonus from all equipment sources.

    Sources:
    1. Equipment potentials (regular and bonus) with 'all_skills' stat
       - Potentials are NOT affected by starforce
    2. Equipment special stats (sub stats) where special_stat_type == 'all_skills'
       - Sub stats ARE affected by starforce sub amplify multiplier

    Returns:
        Total All Skills bonus as an integer
    """
    total = 0

    for slot in EQUIPMENT_SLOTS:
        # Get equipment item for starforce multiplier (sub stats only)
        item = data.equipment_items.get(slot, {})
        stars = int(item.get('stars', 0))
        sub_mult = get_amplify_multiplier(stars, is_sub=True)

        # Check potentials (regular and bonus) - NOT affected by starforce
        pots = data.equipment_potentials.get(slot, {})
        for prefix in ['', 'bonus_']:
            for i in range(1, 4):
                stat = pots.get(f'{prefix}line{i}_stat', '')
                value = pots.get(f'{prefix}line{i}_value', 0)
                if stat == 'all_skills' and value > 0:
                    total += int(value)

        # Check special sub stats (only if item is marked as special)
        # Sub stats ARE affected by starforce sub amplify multiplier
        if item.get('is_special', False):
            special_type = item.get('special_stat_type', '')
            special_value = item.get('special_stat_value', 0)
            if special_type == 'all_skills' and special_value > 0:
                total += int(special_value * sub_mult)

    return total


def calculate_skill_bonuses() -> dict:
    """Sum equipment sub-stat skill bonuses (skill_1st–skill_4th) across all slots."""
    totals = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    for slot in EQUIPMENT_SLOTS:
        item = data.equipment_items.get(slot, {})
        stars = int(item.get('stars', 0))
        sub_mult = get_amplify_multiplier(stars, is_sub=True)
        totals[1] += item.get('sub_skill_1st', 0) * sub_mult
        totals[2] += item.get('sub_skill_2nd', 0) * sub_mult
        totals[3] += item.get('sub_skill_3rd', 0) * sub_mult
        totals[4] += item.get('sub_skill_4th', 0) * sub_mult
    return {k: int(v) for k, v in totals.items()}


st.title("⚔️ Character Settings")
st.markdown("Configure your character's basic information.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Basic Info")

    # Character Level
    new_level = st.number_input(
        "Character Level",
        min_value=1,
        max_value=300,
        value=data.character_level,
        step=1,
        help="Your character's current level (1-300)"
    )
    if new_level != data.character_level:
        data.character_level = new_level
        auto_save()

    # Job Class Selector
    job_options = list(JobClass)
    job_display_options = [JOB_DISPLAY_NAMES[j] for j in job_options]

    current_job = JobClass(data.job_class)
    current_idx = job_options.index(current_job)

    selected_job_display = st.selectbox(
        "Job Class",
        options=job_display_options,
        index=current_idx,
        help="Your character's job class. Determines main and secondary stats."
    )

    # Find selected job enum
    selected_idx = job_display_options.index(selected_job_display)
    selected_job = job_options[selected_idx]

    if selected_job != current_job:
        data.job_class = selected_job.value
        auto_save()

    # Show main/secondary stat info
    main_stat = get_main_stat_name(selected_job).upper()
    secondary_stat = get_secondary_stat_name(selected_job).upper()
    st.caption(f"Main Stat: **{main_stat}** | Secondary: **{secondary_stat}**")

    # All Skills (calculated automatically)
    calculated_all_skills = calculate_all_skills()
    st.metric(
        "All Skills Bonus",
        f"+{calculated_all_skills}",
        help="Auto-calculated from equipment potentials and special sub stats"
    )
    st.caption("*From ring/necklace potentials + special sub stats*")

    # Update stored value if different
    if calculated_all_skills != data.all_skills:
        data.all_skills = calculated_all_skills
        auto_save()

    # Skill Level Breakdown
    st.subheader("Skill Levels")
    st.caption("Base (from leveling, capped at L140) + equipment bonus + All Skills")

    equip_bonuses = calculate_skill_bonuses()
    all_sk = calculated_all_skills
    level_for_pts = min(data.character_level, 140)

    skill_jobs = [
        ("1st Job", Job.FIRST, equip_bonuses[1]),
        ("2nd Job", Job.SECOND, equip_bonuses[2]),
        ("3rd Job", Job.THIRD, equip_bonuses[3]),
        ("4th Job", Job.FOURTH, equip_bonuses[4]),
    ]
    for label, job, equip in skill_jobs:
        base_pts = get_skill_points_for_job(level_for_pts, job)
        total = 1 + base_pts + all_sk + equip
        parts = f"1 base + {base_pts} leveling"
        if all_sk:
            parts += f" + {all_sk} all skills"
        if equip:
            parts += f" + {equip} equip"
        st.metric(f"{label} Skill Level", total, help=parts)

    st.divider()

    # Medal/Costume Main Stat
    st.subheader("Equipment Sets")

    medal_val = data.equipment_sets.get('medal', 0)
    costume_val = data.equipment_sets.get('costume', 0)

    new_medal = st.number_input(
        "Medal Main Stat",
        min_value=0,
        max_value=1500,
        value=medal_val,
        step=10,
        help="Main stat from medal inventory effect (0-1500)"
    )
    if new_medal != medal_val:
        data.equipment_sets['medal'] = new_medal
        auto_save()

    new_costume = st.number_input(
        "Costume Main Stat",
        min_value=0,
        max_value=3000,
        value=costume_val,
        step=10,
        help="Main stat from costume inventory effect (0-3000)"
    )
    if new_costume != costume_val:
        data.equipment_sets['costume'] = new_costume
        auto_save()

    total_set_stat = new_medal + new_costume
    st.metric("Total from Sets", f"+{total_set_stat:,}")

    st.divider()

    # Unique Stats (HeroUniqueStatOption)
    # Auto-allocated greedily in unlock order from the points the character has
    # earned per HeroStatStepTable. No manual editing — levels are derived from
    # character level so users don't have to think about distribution.
    st.subheader("Unique Stats")

    earned_points = available_unique_stat_points(int(data.character_level))
    allocation = auto_allocate(int(data.character_level))
    spent = points_spent(allocation)

    # Persist the auto-allocation so downstream DPS aggregation picks it up via
    # the existing data.unique_stats path. Save only when it actually changes.
    if not hasattr(data, 'unique_stats') or data.unique_stats != allocation:
        data.unique_stats = allocation
        auto_save()

    pt_col1, pt_col2 = st.columns(2)
    pt_col1.metric(
        "Points Earned", earned_points,
        help="From HeroStatStepTable: +10/step from StatStep 3-10, +20/step from 11-26. StatStep = level // 5."
    )
    pt_col2.metric("Points Spent (auto)", spent)

    # Read-only display of each option's allocated level + bonus.
    ucol1, ucol2 = st.columns(2)
    for i, opt in enumerate(UNIQUE_STAT_OPTIONS):
        lv = allocation[opt.key]
        bonus = opt.bonus_at(lv)
        suffix = '' if opt.is_flat else '%'
        col = ucol1 if i % 2 == 0 else ucol2
        with col:
            if opt.key in SKIP_FOR_DPS:
                st.caption(f"⏭ **{opt.display_name}** — skipped (no effect on DPS in our model)")
            elif data.character_level < opt.unlock_level:
                st.caption(f"🔒 **{opt.display_name}** — unlocks at L{opt.unlock_level}")
            elif lv == 0:
                st.caption(f"⏸ **{opt.display_name}** — no points reached this option yet")
            else:
                cost_note = f" [{opt.point_cost} pts/lv]" if opt.point_cost > 1 else ""
                st.markdown(
                    f"**{opt.display_name}** Lv {lv}/{opt.max_level} → **+{bonus:.1f}{suffix}**{cost_note}"
                )

with col2:
    st.subheader("Combat Settings")

    # Combat Mode
    combat_modes = {
        "stage": "Stage (Mixed) - 60% normal, 40% boss",
        "chapter_hunt": "Chapter Hunt - 100% normal, infinite duration",
        "boss": "Boss (Single) - 100% boss damage",
        "world_boss": "World Boss - 100% boss damage"
    }

    current_mode = data.combat_mode
    mode_index = list(combat_modes.keys()).index(current_mode) if current_mode in combat_modes else 0

    new_mode = st.radio(
        "Combat Mode",
        options=list(combat_modes.keys()),
        format_func=lambda x: combat_modes[x],
        index=mode_index,
        help="Affects how normal% and boss% damage bonuses are weighted"
    )
    if new_mode != data.combat_mode:
        data.combat_mode = new_mode
        auto_save()

    # Realistic DPS toggle
    if not hasattr(data, 'use_realistic_dps'):
        data.use_realistic_dps = False

    use_realistic = st.checkbox(
        "Use Realistic DPS",
        value=data.use_realistic_dps,
        help="Phase-aware simulation: applies boss damage only during boss phase, "
             "normal damage only during mob phase, and optimizes skill usage per phase "
             "(e.g., saves Hurricane for boss when multi-target BA is better during mobs)"
    )
    if use_realistic != data.use_realistic_dps:
        data.use_realistic_dps = use_realistic
        auto_save()

    # Boss Importance slider (only visible when realistic DPS is enabled and in stage mode)
    if use_realistic and new_mode == "stage":
        if not hasattr(data, 'boss_importance'):
            data.boss_importance = 70  # Default: boss has ~70% of total HP

        # TODO: Re-enable after testing boss_damage_multiplier
        # boss_importance = st.slider(
        #     "Boss Importance",
        #     min_value=0,
        #     max_value=100,
        #     value=data.boss_importance,
        #     step=5,
        #     help="How much to weight boss damage vs normal damage. "
        #          "Higher = boss is your bottleneck (struggle to kill boss). "
        #          "Lower = mobs are your bottleneck (struggle to clear waves). "
        #          "Default 70% reflects boss having ~70% of total stage HP."
        # )
        # if boss_importance != data.boss_importance:
        #     data.boss_importance = boss_importance
        #     auto_save()
        #
        # # Show what this means
        # mob_weight = 100 - boss_importance
        # st.caption(f"Mob damage valued at {mob_weight}%, Boss damage valued at {boss_importance}%")

        # Boss damage display multiplier
        if not hasattr(data, 'boss_damage_multiplier'):
            data.boss_damage_multiplier = 1.0  # Default: no scaling

        boss_multiplier = st.number_input(
            "Boss Damage Display Multiplier",
            min_value=0.1,
            max_value=20.0,
            value=float(data.boss_damage_multiplier),
            step=0.5,
            format="%.1f",
            help="Scales boss phase damage for display purposes. "
                 "Set to ~5 (number of mobs) to make boss/mob damage numbers comparable. "
                 "This doesn't affect the actual DPS weighting, just how the numbers are displayed."
        )
        if boss_multiplier != data.boss_damage_multiplier:
            data.boss_damage_multiplier = boss_multiplier
            auto_save()

        if boss_multiplier != 1.0:
            st.caption(f"Boss damage display scaled by {boss_multiplier}x (for comparison only)")

    st.divider()

    # Chapter Selection
    st.subheader("Chapter/Stage")

    chapters = list(ENEMY_DEFENSE_VALUES.keys())
    current_chapter = data.chapter if data.chapter in chapters else "Chapter 27"
    chapter_index = chapters.index(current_chapter) if current_chapter in chapters else 0

    new_chapter = st.selectbox(
        "Current Chapter",
        options=chapters,
        index=chapter_index,
        help="Select your current chapter for enemy defense calculations"
    )
    if new_chapter != data.chapter:
        data.chapter = new_chapter
        auto_save()

    # Show enemy defense
    enemy_def = ENEMY_DEFENSE_VALUES.get(new_chapter, 0.752)
    st.metric("Enemy Defense", f"{enemy_def:.3f}")

    st.info("""
    **Combat Mode Effects:**
    - **Stage**: Normal% affects 60% of damage, Boss% affects 40%
    - **Boss**: Only Boss% applies (100%)
    - **World Boss**: Only Boss% applies (100%)
    """)

st.divider()

# Summary
st.subheader("Current Settings Summary")
summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)

with summary_col1:
    st.metric("Level", data.character_level)
with summary_col2:
    st.metric("All Skills", f"+{data.all_skills}")
with summary_col3:
    st.metric("Combat Mode", data.combat_mode.replace("_", " ").title())
with summary_col4:
    st.metric("Chapter", data.chapter.replace("Chapter ", ""))

st.divider()

# ============================================================================
# FIGHT ACTION SUMMARY
# ============================================================================
# Surfaces the simulator's action log on this page so the user can see at a
# glance what the scheduler does with their build — when companion summon
# fires, when buffs go up, which skills dominate damage. Full per-action log
# remains on the Damage Calculator page; here we keep it short.

st.subheader("Fight Action Summary")

_use_realistic = getattr(data, 'use_realistic_dps', False)
if not _use_realistic:
    st.info(
        "Enable **Realistic DPS** in the Damage Calculator page to populate "
        "this section. The summary reflects how the scheduler sequences your "
        "skills, buffs, and companion summon during a simulated fight."
    )
else:
    _stats = shared_aggregate_stats(data)
    _enemy_def = ENEMY_DEFENSE_VALUES.get(getattr(data, 'chapter', 'Chapter 27'), 0.752)
    _boss_importance = getattr(data, 'boss_importance', 70) / 100.0
    _boss_dmg_mult = getattr(data, 'boss_damage_multiplier', 1.0)
    _job_class = JobClass(data.job_class)

    _result = shared_calculate_dps(
        _stats, data.combat_mode, _enemy_def,
        job_class=_job_class,
        use_realistic_dps=True,
        boss_importance=_boss_importance,
        log_actions=True,
        boss_damage_multiplier=_boss_dmg_mult,
    )
    _fight_log = _result.get('fight_log') or []

    if not _fight_log:
        st.caption("Simulator produced no action log (fight had no available skills).")
    else:
        _total_damage = sum(e.damage for e in _fight_log)
        _mob_actions = [e for e in _fight_log if e.phase == 'mob']
        _boss_actions = [e for e in _fight_log if e.phase == 'boss']

        _hi_cols = st.columns(4)
        with _hi_cols[0]:
            st.metric("Total Actions", len(_fight_log))
        with _hi_cols[1]:
            st.metric("Mob / Boss", f"{len(_mob_actions)} / {len(_boss_actions)}")
        with _hi_cols[2]:
            _fight_duration = max(e.time + e.cast_time for e in _fight_log)
            st.metric("Sim Duration", f"{_fight_duration:.1f}s")
        with _hi_cols[3]:
            st.metric("Total Damage", f"{_total_damage:,.0f}")

        # Skill usage table: how many casts, total damage, % of total.
        from collections import Counter
        _usage = Counter(e.skill_name for e in _fight_log)
        _damage_by_skill: dict = {}
        for _e in _fight_log:
            _damage_by_skill[_e.skill_name] = _damage_by_skill.get(_e.skill_name, 0) + _e.damage

        _rows = []
        for _skill, _count in _usage.most_common():
            _dmg = _damage_by_skill.get(_skill, 0)
            _pct = (_dmg / _total_damage * 100.0) if _total_damage > 0 else 0.0
            _rows.append({
                'Skill': _skill.replace('_', ' ').title(),
                'Uses': _count,
                'Total Damage': f"{_dmg:,.0f}",
                '% of Damage': f"{_pct:.1f}%",
            })

        import pandas as pd
        st.dataframe(pd.DataFrame(_rows), hide_index=True, use_container_width=True)

        # First-cast highlights — answers "when do my buffs / summon fire?"
        # at a glance without scrolling the full per-action log.
        _firsts = {}
        for _e in _fight_log:
            if _e.skill_name not in _firsts:
                _firsts[_e.skill_name] = _e.time
        # Only surface the non-trivial events: buffs, summons, anything cast
        # less than once-per-second (basic attacks would dominate otherwise).
        _highlights = [
            (name, t) for name, t in _firsts.items()
            if _usage[name] <= max(1, len(_fight_log) // 10)
        ]
        if _highlights:
            st.markdown("**First Cast Timeline:**")
            _highlights.sort(key=lambda nt: nt[1])
            _timeline_rows = [
                {'Time': f"{t:.1f}s", 'Skill': name.replace('_', ' ').title()}
                for name, t in _highlights
            ]
            st.dataframe(pd.DataFrame(_timeline_rows), hide_index=True, use_container_width=True)

        st.caption("Full per-action log is on the Damage Calculator page.")

st.divider()

# ============================================================================
# DATA IMPORT/EXPORT
# ============================================================================

st.subheader("Data Management")
st.markdown("Export your build to share with others, or import someone else's build.")

exp_col, imp_col = st.columns(2)

with exp_col:
    st.markdown("**Export Build**")
    st.caption("Download your current build as a CSV file to share with others.")

    # Generate CSV content
    csv_content = export_user_data_csv(data)
    filename = f"{st.session_state.username}_build.csv"

    st.download_button(
        label="Download Build CSV",
        data=csv_content,
        file_name=filename,
        mime="text/csv",
        help="Download your complete build data as a CSV file"
    )

with imp_col:
    st.markdown("**Import Build**")
    st.caption("Upload a CSV file to load someone else's build (overwrites your current data).")

    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload a build CSV file to import",
        key="import_csv"
    )

    if uploaded_file is not None:
        # Read the file content
        csv_text = uploaded_file.getvalue().decode('utf-8')

        # Show preview
        with st.expander("Preview imported data", expanded=False):
            st.text(csv_text[:1000] + "..." if len(csv_text) > 1000 else csv_text)

        if st.button("Import Build", type="primary"):
            imported_data = import_user_data_csv(csv_text, st.session_state.username,
                                                  current_job_class=getattr(data, 'job_class', None))
            if imported_data:
                # Update session state
                st.session_state.user_data = imported_data
                # Save to file
                save_user_data(st.session_state.username, imported_data)
                st.success("Build imported successfully! Refresh the page to see changes.")
                st.rerun()
            else:
                st.error("Failed to import build. Please check the CSV format.")

st.info("""
**Sharing Builds:**
1. Click "Download Build CSV" to export your current build
2. Share the CSV file with friends
3. They can upload it using "Import Build" to load your stats
""")
