"""
Damage Calculator Page
Calculate DPS based on all configured stats.

Uses utils/dps_calculator.py for all calculations - single source of truth.
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core import (
    calculate_total_dex,
    calculate_final_damage_mult,
    calculate_effective_crit_multiplier,
    BASE_CRIT_DMG,
    BASE_MIN_DMG,
    BASE_MAX_DMG,
    EQUIPMENT_SLOTS,
    ENEMY_DEFENSE_VALUES,
    get_enemy_defense,
)
from utils.data_manager import save_user_data
from utils.dps_calculator import (
    aggregate_stats as shared_aggregate_stats,
    calculate_dps as shared_calculate_dps,
)
from job_classes import JobClass

st.set_page_config(page_title="Damage Calculator", page_icon="💥", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def aggregate_stats():
    """Wrapper that calls shared aggregate_stats with user data."""
    return shared_aggregate_stats(data)


def calculate_dps(stats, combat_mode='stage', enemy_def=None, log_actions=False):
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

    # Check if user has enabled realistic DPS calculation
    use_realistic_dps = getattr(data, 'use_realistic_dps', False)
    boss_importance = getattr(data, 'boss_importance', 70) / 100.0
    boss_damage_multiplier = getattr(data, 'boss_damage_multiplier', 1.0)
    job_class = JobClass(data.job_class)

    return shared_calculate_dps(
        stats, combat_mode, enemy_def,
        job_class=job_class,
        use_realistic_dps=use_realistic_dps,
        boss_importance=boss_importance,
        log_actions=log_actions,
        boss_damage_multiplier=boss_damage_multiplier,
    )


st.title("💥 Damage Calculator")
st.markdown("Calculate your DPS based on all configured stats.")

# Aggregate stats
stats = aggregate_stats()

# Get enemy defense based on combat mode
combat_mode = data.combat_mode
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

# Calculate DPS (request fight log if realistic DPS is enabled)
use_realistic_dps = getattr(data, 'use_realistic_dps', False)
result = calculate_dps(stats, combat_mode, enemy_def, log_actions=use_realistic_dps)

# Display DPS
col1, col2 = st.columns([2, 1])

with col1:
    st.metric("Total DPS", f"{result['total']:,.0f}")

with col2:
    st.metric("Combat Mode", combat_mode.replace("_", " ").title())

# Phase DPS breakdown (only shown in realistic DPS mode)
if use_realistic_dps and result.get('mob_phase_dps', 0) > 0:
    st.divider()
    st.subheader("Phase DPS Breakdown")

    boss_multiplier = result.get('boss_damage_multiplier', 1.0)
    phase_cols = st.columns(3)

    with phase_cols[0]:
        st.metric("Mob Phase DPS", f"{result['mob_phase_dps']:,.0f}")

    with phase_cols[1]:
        if boss_multiplier != 1.0:
            st.metric(
                f"Boss Phase DPS (×{boss_multiplier:.1f})",
                f"{result['boss_phase_dps_display']:,.0f}",
                help=f"Actual: {result['boss_phase_dps']:,.0f} | Display scaled by {boss_multiplier}x for comparison"
            )
        else:
            st.metric("Boss Phase DPS", f"{result['boss_phase_dps']:,.0f}")

    with phase_cols[2]:
        boss_importance = getattr(data, 'boss_importance', 70)
        mob_importance = 100 - boss_importance
        st.metric("Weighting", f"Mob {mob_importance}% / Boss {boss_importance}%")

    if boss_multiplier != 1.0:
        st.caption(f"💡 Boss damage display scaled by {boss_multiplier}x to compare with multi-target mob damage")

st.divider()

# Multiplier breakdown
st.subheader("Damage Multipliers")

mult_cols = st.columns(4)

with mult_cols[0]:
    st.metric("Stat (DEX)", f"x{result['stat_mult']:.4f}")
    st.metric("Damage %", f"x{result['damage_mult']:.4f}")

with mult_cols[1]:
    st.metric("Damage Amp", f"x{result['amp_mult']:.4f}")
    st.metric("Final Damage", f"x{result['fd_mult']:.4f}")

with mult_cols[2]:
    st.metric("Crit Damage", f"x{result['crit_mult']:.4f}")
    st.metric("Defense", f"x{result['def_mult']:.4f}")

with mult_cols[3]:
    st.metric("Dmg Range", f"x{result['range_mult']:.2f}")
    st.metric("Attack Speed", f"x{result['speed_mult']:.2f}")

st.divider()

# Stat summary
st.subheader("Aggregated Stats")

stat_col1, stat_col2, stat_col3 = st.columns(3)

with stat_col1:
    st.markdown("**Main Stats**")
    st.write(f"Flat DEX: {stats.get('dex_flat', 0):,.0f}")
    st.write(f"DEX %: {stats.get('dex_pct', 0):.1f}%")
    st.write(f"Total DEX: {result['total_dex']:,.0f}")
    st.write(f"Base Attack: {stats.get('attack_flat', 0):,.0f}")

with stat_col2:
    st.markdown("**Damage Stats**")
    st.write(f"Damage %: {stats.get('damage_pct', 0):.1f}%")
    st.write(f"Damage Amp %: {stats.get('damage_amp', 0):.1f}%")
    st.write(f"Boss Damage %: {stats['boss_damage']:.1f}%")
    st.write(f"Normal Damage %: {stats['normal_damage']:.1f}%")
    st.write(f"Crit Rate %: {stats['crit_rate']:.1f}%")
    st.write(f"Crit Damage %: {stats['crit_damage']:.1f}%")
    fd_total = (result['fd_mult'] - 1) * 100
    st.write(f"Final Damage % (total): {fd_total:.1f}%")

with stat_col3:
    st.markdown("**Other Stats**")
    st.write(f"Defense Pen % (total): {result['defense_pen'] * 100:.1f}%")
    st.write(f"Attack Speed % (total): {result['attack_speed']:.1f}%")
    st.write(f"Min Dmg Mult %: {stats['min_dmg_mult']:.1f}%")
    st.write(f"Max Dmg Mult %: {stats['max_dmg_mult']:.1f}%")

    # Show individual sources with effective gains
    if result.get('defense_pen_breakdown'):
        st.markdown("*Defense Pen Sources (priority order):*")
        for source_name, raw_value, effective_gain in result['defense_pen_breakdown']:
            # Clean up source name for display
            display_name = source_name.replace('_', ' ').title()
            st.write(f"  - {display_name}: {raw_value*100:.1f}% (eff: +{effective_gain*100:.1f}%)")

    if result.get('attack_speed_breakdown'):
        st.markdown("*Attack Speed Sources (highest first):*")
        for source_name, raw_value, effective_gain in result['attack_speed_breakdown']:
            # Clean up source name for display
            display_name = source_name.replace('_', ' ').title()
            st.write(f"  - {display_name}: {raw_value:.1f}% (eff: +{effective_gain:.1f}%)")

    if stats['final_damage_sources']:
        st.markdown("*Final Damage Sources:*")
        for i, src in enumerate(stats['final_damage_sources']):
            st.write(f"  - Source {i+1}: {src*100:.1f}%")

st.divider()

# Formula explanation
with st.expander("📊 Damage Formula Explanation"):
    st.markdown("""
    ### Master Damage Formula

    ```
    Damage = Base_ATK × Stat_Mult × Damage_Mult × Amp_Mult × FD_Mult × Crit_Mult × Def_Mult
    ```

    **Where:**
    - **Stat_Mult** = 1 + (Total_DEX × 0.01) + (Total_STR × 0.0025)
    - **Damage_Mult** = 1 + (Damage% / 100) + (Boss% / 100)
    - **Amp_Mult** = 1 + (Damage_Amp / 100)
    - **FD_Mult** = (1 + FD₁) × (1 + FD₂) × ... *(multiplicative)*
    - **Crit_Mult** = 1 + (Crit_Rate/100) × (Crit_Damage/100)
    - **Def_Mult** = 1 / (1 + Enemy_Def × (1 - Def_Pen))

    ### Defense Penetration (Multiplicative)

    ```
    Remaining = (1 - IED₁) × (1 - IED₂) × ...
    Total_Def_Pen = 1 - Remaining
    ```

    Each source reduces the *remaining* defense, not the original.

    ### Attack Speed (Diminishing Returns)

    ```
    For each source: gain = (150 - current) × (source / 150)
    ```

    Each source gives diminishing returns as you approach the 150% cap.
    """)

# Stat priority recommendations
st.subheader("Stat Priority Recommendations")
st.info("""
Based on your current stats, here are general recommendations:
- **Low on Damage %?** Focus on Damage % potentials and Hero Power lines
- **Low on Boss/Normal %?** Prioritize based on your combat mode
- **Low on Crit Damage?** Great value if you have high crit rate
- **Low on Final Damage?** Very valuable as it's multiplicative (each source multiplies separately)
- **Low on Defense Pen?** Important for higher chapter progression (also multiplicative stacking)
""")

# Fight Simulation Log (only when realistic DPS is enabled)
fight_log = result.get('fight_log')
if fight_log:
    st.divider()
    st.subheader("Fight Simulation Log")

    # Determine mob duration from actual fight log timestamps
    mob_actions = [e for e in fight_log if e.phase == 'mob']
    boss_actions = [e for e in fight_log if e.phase == 'boss']

    mob_duration = max(e.time + e.cast_time for e in mob_actions) if mob_actions else 0.0
    fight_duration = max(e.time + e.cast_time for e in fight_log)

    # Summary stats
    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("Total Actions", len(fight_log))
    with summary_cols[1]:
        st.metric("Mob Phase Actions", len(mob_actions))
    with summary_cols[2]:
        st.metric("Boss Phase Actions", len(boss_actions))
    with summary_cols[3]:
        total_damage = sum(e.damage for e in fight_log)
        st.metric("Total Damage", f"{total_damage:,.0f}")

    # Skill usage breakdown
    from collections import Counter
    skill_counter = Counter(e.skill_name for e in fight_log)
    skill_damage = {}
    for entry in fight_log:
        skill_damage[entry.skill_name] = skill_damage.get(entry.skill_name, 0) + entry.damage

    st.markdown("**Skill Usage Summary:**")
    skill_data = []
    for skill_name, count in skill_counter.most_common():
        display_name = skill_name.replace('_', ' ').title()
        damage = skill_damage.get(skill_name, 0)
        pct = (damage / total_damage * 100) if total_damage > 0 else 0
        skill_data.append({
            'Skill': display_name,
            'Uses': count,
            'Total Damage': f"{damage:,.0f}",
            '% of Damage': f"{pct:.1f}%",
        })

    import pandas as pd
    st.dataframe(pd.DataFrame(skill_data), hide_index=True, use_container_width=True)

    # Detailed log in expander
    with st.expander("Detailed Action Log", expanded=False):
        st.markdown(f"*Mob Phase: 0.0s - {mob_duration:.1f}s | Boss Phase: {mob_duration:.1f}s - {fight_duration:.1f}s*")

        # Group consecutive same-skill actions
        log_entries = []
        i = 0
        while i < len(fight_log):
            entry = fight_log[i]
            count = 1
            total_dmg = entry.damage
            end_time = entry.time + entry.cast_time

            # Look ahead for same skill in same phase
            j = i + 1
            while j < len(fight_log) and fight_log[j].skill_name == entry.skill_name and fight_log[j].phase == entry.phase:
                count += 1
                total_dmg += fight_log[j].damage
                end_time = fight_log[j].time + fight_log[j].cast_time
                j += 1

            display_name = entry.skill_name.replace('_', ' ').title()
            phase_emoji = "M" if entry.phase == 'mob' else "B"

            if count > 1:
                log_entries.append({
                    'Time': f"{entry.time:.1f}s - {end_time:.1f}s",
                    'Phase': phase_emoji,
                    'Skill': f"{display_name} x{count}",
                    'Damage': f"{total_dmg:,.0f}",
                    'Reason': entry.reason,
                })
            else:
                log_entries.append({
                    'Time': f"{entry.time:.1f}s",
                    'Phase': phase_emoji,
                    'Skill': display_name,
                    'Damage': f"{entry.damage:,.0f}",
                    'Reason': entry.reason,
                })

            i = j

        st.dataframe(pd.DataFrame(log_entries), hide_index=True, use_container_width=True)

    # Skill Action Values debug section
    with st.expander("🔧 Skill Action Values (Debug)", expanded=False):
        st.markdown("**Precalculated skill values used by the simulator:**")
        st.caption("These are the damage values and DPS for each skill in mob vs boss phase")

        # Re-create the DPS calculator to get skill values
        from skills import DPSCalculator, create_character_at_level
        from stage_settings import COMBAT_SCENARIO_PARAMS, get_combat_mode_from_string

        # Get scenario params
        combat_mode_enum = get_combat_mode_from_string(combat_mode)
        scenario_params = COMBAT_SCENARIO_PARAMS.get(combat_mode_enum)
        num_enemies = scenario_params.num_enemies if scenario_params else 5

        # Create character and calculator
        level = stats.get('character_level', 140)
        all_skills = int(stats.get('all_skills', 0))

        from skills import create_character_at_level
        char = create_character_at_level(level, all_skills)

        # Set character stats from aggregated stats
        char.attack = stats.get('attack_flat', 10000) * (1 + stats.get('attack_pct', 0) / 100)
        char.main_stat_flat = stats.get('dex_flat', 0)
        char.main_stat_pct = stats.get('dex_pct', 0)
        char.damage_pct = stats.get('damage_pct', 0)
        char.boss_damage_pct = stats.get('boss_damage', 0)
        char.normal_damage_pct = stats.get('normal_damage', 0)
        char.crit_rate = stats.get('crit_rate', 0)
        char.crit_damage = stats.get('crit_damage', 0)
        char.final_damage_pct = (result.get('fd_mult', 1.0) - 1) * 100
        char.ba_targets = int(stats.get('ba_targets', 0))

        calc = DPSCalculator(char, enemy_def=enemy_def)

        # Calculate attack speed multiplier from result
        total_attack_speed = result.get('attack_speed', 0)
        attack_speed_mult = min(1 + total_attack_speed / 100, 2.5)

        skill_values = calc._precalculate_skill_values(num_enemies, attack_speed_mult)

        skill_value_data = []
        for skill_name, sv in skill_values.items():
            skill_value_data.append({
                'Skill': skill_name.replace('_', ' ').title(),
                'Cast Time': f"{sv.cast_time:.2f}s",
                'Cooldown': f"{sv.cooldown:.1f}s" if sv.cooldown > 0 else "-",
                'Mob Dmg': f"{sv.damage_per_use_mob:,.0f}",
                'Boss Dmg': f"{sv.damage_per_use_boss:,.0f}",
                'Mob DPS': f"{sv.dps_value_mob:,.0f}",
                'Boss DPS': f"{sv.dps_value_boss:,.0f}",
            })

        st.dataframe(pd.DataFrame(skill_value_data), hide_index=True, use_container_width=True)

        # Show detailed breakdown for active skills
        st.markdown("**Skill Calculation Breakdown:**")
        from skills import BOWMASTER_SKILLS
        for skill_name in ["arrow_stream", "hurricane", "covering_fire"]:
            if skill_name not in skill_values:
                continue
            skill = BOWMASTER_SKILLS.get(skill_name)
            if not skill:
                continue

            sv = skill_values[skill_name]
            hits = calc.get_skill_hits(skill_name)
            targets = calc.get_skill_targets(skill_name)
            dmg_pct = calc.get_skill_damage_pct(skill_name)

            # Calculate per-hit damage
            dmg_per_hit_boss = sv.damage_per_use_boss / hits if hits > 0 else 0

            # Check for Maple Hero FD bonus
            # Formula: floor(base + per_level * level)
            maple_hero_note = ""
            if char.is_skill_unlocked("maple_hero"):
                from skills import BOWMASTER_SKILLS
                mh_skill = BOWMASTER_SKILLS["maple_hero"]
                if mh_skill.skill_bonuses and skill_name in mh_skill.skill_bonuses:
                    mh_level = char.get_effective_skill_level("maple_hero")
                    base, per_level = mh_skill.skill_bonuses[skill_name]
                    mh_fd = int(base + per_level * mh_level)
                    maple_hero_note = f" (Maple Hero +{mh_fd}% FD)"

            st.markdown(f"**{skill_name.replace('_', ' ').title()}**: "
                       f"{dmg_pct:.0f}% dmg × {hits} hits × 1 target = {sv.damage_per_use_boss:,.0f} total | "
                       f"Cast: {sv.cast_time:.2f}s | "
                       f"Per hit: {dmg_per_hit_boss:,.0f}{maple_hero_note}")

        st.markdown("**Summons & Procs (calculated separately):**")
        st.caption("These run in parallel with player actions")

        # Show summon/proc info
        summon_info = []
        for skill_name in ["phoenix", "arrow_platter", "quiver_cartridge", "final_attack"]:
            if char.is_skill_unlocked(skill_name):
                summon_info.append(skill_name.replace('_', ' ').title())

        if summon_info:
            st.write(f"Active summons/procs: {', '.join(summon_info)}")
        else:
            st.write("No summons/procs unlocked")
