"""
Maple Rank Page
Track Maple Rank progression, main stat accumulation, and stat bonuses.
Uses verified main stat scaling formulas from maple_rank.py.
"""
import streamlit as st
from utils.data_manager import save_user_data
from maple_rank import (
    MapleRankStatType, MapleRankConfig, MAPLE_RANK_STATS,
    STAT_DISPLAY_NAMES, MAIN_STAT_SPECIAL,
    get_main_stat_per_point, get_cumulative_main_stat, get_stage_main_stat_table
)

st.set_page_config(page_title="Maple Rank", page_icon="M", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def auto_save():
    save_user_data(st.session_state.username, data)


def build_maple_rank_config() -> MapleRankConfig:
    """Build MapleRankConfig from user data."""
    config = MapleRankConfig(
        current_stage=data.maple_rank.get('current_stage', 1),
        main_stat_level=data.maple_rank.get('main_stat_level', 0),
        special_main_stat_points=data.maple_rank.get('special_main_stat', 0),
    )
    # Load stat levels
    stat_levels = data.maple_rank.get('stat_levels', {})
    for stat_type in MapleRankStatType:
        if stat_type in MAPLE_RANK_STATS:
            level = stat_levels.get(stat_type.value, 0)
            config.stat_levels[stat_type] = level
    return config


st.title("Maple Rank")
st.markdown("Track your Maple Rank progression and stat bonuses using verified formulas.")

# Initialize if needed
if not data.maple_rank:
    data.maple_rank = {
        'current_stage': 1,
        'main_stat_level': 0,
        'special_main_stat': 0,
        'stat_levels': {},
    }

tab1, tab2, tab3 = st.tabs(["Stage Progress", "Stat Bonuses", "Summary"])

# ============================================================================
# TAB 1: STAGE PROGRESS
# ============================================================================
with tab1:
    st.markdown("**Main Stat Progression** - Track your stage and level progress")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Current Progress")

        # Current Stage
        new_stage = st.number_input(
            "Current Stage",
            min_value=1,
            max_value=25,
            value=data.maple_rank.get('current_stage', 1),
            help="Your highest unlocked Maple Rank stage (1-25)"
        )
        if new_stage != data.maple_rank.get('current_stage'):
            data.maple_rank['current_stage'] = new_stage
            auto_save()

        # Main Stat Level within stage
        new_ms_level = st.number_input(
            "Level in Current Stage",
            min_value=0,
            max_value=10,
            value=data.maple_rank.get('main_stat_level', 0),
            help="Progress within current stage (0-10 points)"
        )
        if new_ms_level != data.maple_rank.get('main_stat_level'):
            data.maple_rank['main_stat_level'] = new_ms_level
            auto_save()

        # Special Main Stat Points
        new_special = st.number_input(
            "Special Main Stat Points",
            min_value=0,
            max_value=MAIN_STAT_SPECIAL["max_points"],
            value=data.maple_rank.get('special_main_stat', 0),
            help=f"Additional main stat from special rewards (0-{MAIN_STAT_SPECIAL['max_points']})"
        )
        if new_special != data.maple_rank.get('special_main_stat'):
            data.maple_rank['special_main_stat'] = new_special
            auto_save()

        st.divider()

        # Build config and show current values
        config = build_maple_rank_config()

        # Main stat breakdown
        st.markdown("### Main Stat Breakdown")

        regular_ms = config.get_regular_main_stat()
        special_ms = config.get_special_main_stat()
        total_ms = config.get_total_main_stat()

        col_r, col_s = st.columns(2)
        with col_r:
            st.metric("Regular Main Stat", f"+{regular_ms:,}",
                      help="From stage progression (cumulative)")
        with col_s:
            st.metric("Special Main Stat", f"+{special_ms:,}",
                      help=f"Base {MAIN_STAT_SPECIAL['base_value']} + {new_special} pts x {MAIN_STAT_SPECIAL['per_point']}/pt")

        st.metric("Total Main Stat from Maple Rank", f"+{total_ms:,}")

        # Show current stage info
        per_point = get_main_stat_per_point(new_stage)
        st.caption(f"Stage {new_stage}: +{per_point} main stat per point | {new_ms_level}/10 points invested")

    with col2:
        st.markdown("### Main Stat Scaling Reference")
        st.caption("Verified formula showing main stat per point at each stage")

        # Generate scaling table
        stage_table = get_stage_main_stat_table()

        table_data = []
        for stage in range(1, 22):
            info = stage_table[stage]
            is_current = stage == new_stage
            marker = " <--" if is_current else ""
            table_data.append({
                "Stage": stage,
                "Per Point": f"+{info['per_point']}",
                "Max @ Stage": f"+{info['max_at_stage']}",
                "Cumulative": f"+{info['cumulative_max']:,}",
                "Current": marker,
            })

        st.dataframe(table_data, use_container_width=True, hide_index=True, height=400)

        st.caption("""
**Formula:**
- Stages 1-7: +2/stage increment (1, 3, 5, 7, 9, 11, 13 per point)
- Stages 8-10: +4/stage increment (17, 21, 25 per point)
- Stages 11+: +5/stage increment (30, 35, 40, ... per point)
        """)

# ============================================================================
# TAB 2: STAT BONUSES
# ============================================================================
with tab2:
    st.markdown("**Stat Bonuses** - Level up stats to unlock bonuses")

    # Initialize stat levels if not present
    if 'stat_levels' not in data.maple_rank:
        data.maple_rank['stat_levels'] = {}

    # Group stats into columns
    col1, col2 = st.columns(2)

    # Define stat groups for better organization
    stat_groups = [
        (MapleRankStatType.DAMAGE_PERCENT, "Damage %"),
        (MapleRankStatType.BOSS_DAMAGE, "Boss Damage %"),
        (MapleRankStatType.NORMAL_DAMAGE, "Normal Damage %"),
        (MapleRankStatType.CRIT_DAMAGE, "Crit Damage %"),
        (MapleRankStatType.SKILL_DAMAGE, "Skill Damage %"),
        (MapleRankStatType.ATTACK_SPEED, "Attack Speed %"),
        (MapleRankStatType.CRIT_RATE, "Crit Rate %"),
        (MapleRankStatType.MIN_DMG_MULT, "Min Damage Mult %"),
        (MapleRankStatType.MAX_DMG_MULT, "Max Damage Mult %"),
        (MapleRankStatType.ACCURACY, "Accuracy"),
    ]

    for idx, (stat_type, display_name) in enumerate(stat_groups):
        stat_info = MAPLE_RANK_STATS.get(stat_type, {})
        max_level = stat_info.get("max_level", 20)
        per_level = stat_info.get("per_level", 1.0)

        current_level = data.maple_rank.get('stat_levels', {}).get(stat_type.value, 0)
        current_value = current_level * per_level

        with col1 if idx < 5 else col2:
            # Show stat name and current value
            if stat_type == MapleRankStatType.ACCURACY:
                value_str = f"+{current_value:.1f}"
            else:
                value_str = f"+{current_value:.2f}%"

            st.markdown(f"**{display_name}**: {value_str}")

            new_level = st.slider(
                f"{stat_type.value}",
                min_value=0,
                max_value=max_level,
                value=current_level,
                key=f"mr_stat_{stat_type.value}",
                label_visibility="collapsed"
            )

            if new_level != current_level:
                if 'stat_levels' not in data.maple_rank:
                    data.maple_rank['stat_levels'] = {}
                data.maple_rank['stat_levels'][stat_type.value] = new_level
                auto_save()

            max_value = max_level * per_level
            if stat_type == MapleRankStatType.ACCURACY:
                st.caption(f"Lv {new_level}/{max_level} | +{per_level:.2f}/lv (max +{max_value:.0f})")
            else:
                st.caption(f"Lv {new_level}/{max_level} | +{per_level:.2f}%/lv (max +{max_value:.1f}%)")

    st.divider()

    # Quick max/reset buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Max All Stats", key="max_all_stats"):
            for stat_type in MAPLE_RANK_STATS:
                max_level = MAPLE_RANK_STATS[stat_type]["max_level"]
                data.maple_rank['stat_levels'][stat_type.value] = max_level
            auto_save()
            st.rerun()
    with col2:
        if st.button("Reset All Stats", key="reset_all_stats"):
            data.maple_rank['stat_levels'] = {}
            auto_save()
            st.rerun()

# ============================================================================
# TAB 3: SUMMARY
# ============================================================================
with tab3:
    st.markdown("**Maple Rank Summary** - All stats from Maple Rank")

    config = build_maple_rank_config()
    all_stats = config.get_all_stats()

    # Main Stat Section
    st.markdown("### Main Stat")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Regular", f"+{all_stats['main_stat_regular']:,.0f}")
    with col2:
        st.metric("Special", f"+{all_stats['main_stat_special']:,.0f}")
    with col3:
        st.metric("Total", f"+{all_stats['main_stat_flat']:,.0f}")

    st.divider()

    # Damage Stats
    st.markdown("### Damage Stats")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Damage %", f"+{all_stats['damage_percent']:.2f}%")
        st.metric("Boss Damage %", f"+{all_stats['boss_damage']:.2f}%")
    with col2:
        st.metric("Normal Damage %", f"+{all_stats['normal_damage']:.2f}%")
        st.metric("Skill Damage %", f"+{all_stats['skill_damage']:.2f}%")
    with col3:
        st.metric("Crit Damage %", f"+{all_stats['crit_damage']:.2f}%")

    st.divider()

    # Other Stats
    st.markdown("### Other Stats")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Attack Speed %", f"+{all_stats['attack_speed']:.2f}%")
        st.metric("Crit Rate %", f"+{all_stats['crit_rate']:.2f}%")
    with col2:
        st.metric("Min Damage Mult %", f"+{all_stats['min_dmg_mult']:.2f}%")
        st.metric("Max Damage Mult %", f"+{all_stats['max_dmg_mult']:.2f}%")
    with col3:
        st.metric("Accuracy", f"+{all_stats['accuracy']:.1f}")

    st.divider()

    # Stats table
    st.markdown("### All Stats Table")
    stats_table = []

    # Main stats
    stats_table.append({
        "Category": "Main Stat",
        "Stat": "Regular Main Stat",
        "Value": f"+{all_stats['main_stat_regular']:,.0f}",
        "Max Possible": f"+{get_cumulative_main_stat(21, 10):,}",
    })
    stats_table.append({
        "Category": "Main Stat",
        "Stat": "Special Main Stat",
        "Value": f"+{all_stats['main_stat_special']:,.0f}",
        "Max Possible": f"+{MAIN_STAT_SPECIAL['base_value'] + MAIN_STAT_SPECIAL['max_points'] * MAIN_STAT_SPECIAL['per_point']:,}",
    })

    # Other stats
    for stat_type in MAPLE_RANK_STATS:
        stat_info = MAPLE_RANK_STATS[stat_type]
        max_level = stat_info["max_level"]
        per_level = stat_info["per_level"]
        max_value = max_level * per_level

        current_value = config.get_stat_value(stat_type)
        display_name = STAT_DISPLAY_NAMES.get(stat_type, stat_type.value)

        if stat_type == MapleRankStatType.ACCURACY:
            val_str = f"+{current_value:.1f}"
            max_str = f"+{max_value:.0f}"
        else:
            val_str = f"+{current_value:.2f}%"
            max_str = f"+{max_value:.1f}%"

        stats_table.append({
            "Category": "Bonus Stat",
            "Stat": display_name,
            "Value": val_str,
            "Max Possible": max_str,
        })

    st.dataframe(stats_table, use_container_width=True, hide_index=True)

    # Progress indicator
    st.divider()
    st.markdown("### Progress")

    # Calculate overall progress
    current_stage = data.maple_rank.get('current_stage', 1)
    current_level = data.maple_rank.get('main_stat_level', 0)
    special_points = data.maple_rank.get('special_main_stat', 0)

    # Stage progress (21 stages max, 10 levels each = 210 points)
    total_stage_points = (current_stage - 1) * 10 + current_level
    max_stage_points = 21 * 10
    stage_progress = total_stage_points / max_stage_points

    # Special progress
    special_progress = special_points / MAIN_STAT_SPECIAL["max_points"]

    # Stat levels progress
    total_stat_levels = sum(data.maple_rank.get('stat_levels', {}).values())
    max_stat_levels = sum(info["max_level"] for info in MAPLE_RANK_STATS.values())
    stat_progress = total_stat_levels / max_stat_levels if max_stat_levels > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Stage Progress**")
        st.progress(stage_progress)
        st.caption(f"Stage {current_stage} @ {current_level}/10 ({stage_progress:.1%})")
    with col2:
        st.markdown("**Special MS Progress**")
        st.progress(special_progress)
        st.caption(f"{special_points}/{MAIN_STAT_SPECIAL['max_points']} pts ({special_progress:.1%})")
    with col3:
        st.markdown("**Stat Levels Progress**")
        st.progress(stat_progress)
        st.caption(f"{total_stat_levels}/{max_stat_levels} levels ({stat_progress:.1%})")
