"""
Guild Skills Page
Configure your guild skill bonuses.

Guild skills provide various stat bonuses that stack with other sources.
Defense Penetration from guild is applied first (highest priority) in multiplicative calculations.
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from guild import (
    GuildSkillType, GUILD_SKILL_DATA, SKILL_DISPLAY_NAMES,
    GuildConfig
)
from utils.data_manager import save_user_data

st.set_page_config(page_title="Guild Skills", page_icon="⚔️", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def auto_save():
    save_user_data(st.session_state.username, data)


# Initialize guild_skills if needed
if not hasattr(data, 'guild_skills') or data.guild_skills is None:
    data.guild_skills = {}


st.title("⚔️ Guild Skills")
st.markdown("Configure your guild skill bonuses. These provide valuable stat boosts that stack with other sources.")

st.info("""
**Priority Note:** Defense Penetration from guild skills is applied **first** in the multiplicative
stacking calculation, meaning it gets full value before other sources reduce the remaining defense.
""")

st.divider()

# Two columns for guild skills
col1, col2 = st.columns(2)

# Track if any changes were made
changes_made = False

# Combat-relevant skills
combat_skills = [
    GuildSkillType.FINAL_DAMAGE,
    GuildSkillType.DAMAGE,
    GuildSkillType.BOSS_DAMAGE,
    GuildSkillType.DEF_PEN,
    GuildSkillType.CRIT_DAMAGE,
    GuildSkillType.MAIN_STAT,
    GuildSkillType.ATTACK,
]

# Non-combat skills
other_skills = [
    GuildSkillType.MAX_HP,
]

with col1:
    st.subheader("Combat Skills")

    for skill in combat_skills:
        skill_data = GUILD_SKILL_DATA[skill]
        skill_key = skill.value
        display_name = SKILL_DISPLAY_NAMES[skill]
        max_level = skill_data["max_level"]
        per_level = skill_data["per_level"]

        # Get current value
        current_level = int(data.guild_skills.get(skill_key, 0))
        current_value = current_level * per_level

        # Create input with help text
        new_level = st.number_input(
            f"{display_name}",
            min_value=0,
            max_value=max_level,
            value=current_level,
            step=1,
            help=f"{skill_data['description']} (Max: {max_level})",
            key=f"guild_{skill_key}"
        )

        # Show current value
        if skill_key in ("attack", "max_hp"):
            st.caption(f"Current bonus: +{new_level * per_level:.0f}")
        else:
            st.caption(f"Current bonus: +{new_level * per_level:.1f}%")

        if new_level != current_level:
            data.guild_skills[skill_key] = new_level
            changes_made = True

with col2:
    st.subheader("Other Skills")

    for skill in other_skills:
        skill_data = GUILD_SKILL_DATA[skill]
        skill_key = skill.value
        display_name = SKILL_DISPLAY_NAMES[skill]
        max_level = skill_data["max_level"]
        per_level = skill_data["per_level"]

        # Get current value
        current_level = int(data.guild_skills.get(skill_key, 0))

        # Create input
        new_level = st.number_input(
            f"{display_name}",
            min_value=0,
            max_value=max_level,
            value=current_level,
            step=1,
            help=f"{skill_data['description']} (Max: {max_level})",
            key=f"guild_{skill_key}"
        )

        # Show current value
        st.caption(f"Current bonus: +{new_level * per_level:.0f}")

        if new_level != current_level:
            data.guild_skills[skill_key] = new_level
            changes_made = True

    st.divider()

    # Quick actions
    st.subheader("Quick Actions")

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Max All Skills", key="max_all"):
            for skill in GuildSkillType:
                skill_key = skill.value
                max_level = GUILD_SKILL_DATA[skill]["max_level"]
                data.guild_skills[skill_key] = max_level
            auto_save()
            st.rerun()

    with col_b:
        if st.button("Reset All Skills", key="reset_all"):
            for skill in GuildSkillType:
                skill_key = skill.value
                data.guild_skills[skill_key] = 0
            auto_save()
            st.rerun()

# Auto-save if changes were made
if changes_made:
    auto_save()
    st.success("Guild skills saved!")

st.divider()

# Summary section
st.subheader("Guild Stats Summary")

# Calculate total stats
summary_data = []
for skill in GuildSkillType:
    skill_data = GUILD_SKILL_DATA[skill]
    skill_key = skill.value
    display_name = SKILL_DISPLAY_NAMES[skill]
    per_level = skill_data["per_level"]
    max_level = skill_data["max_level"]

    current_level = int(data.guild_skills.get(skill_key, 0))
    current_value = current_level * per_level
    max_value = max_level * per_level

    if skill_key in ("attack", "max_hp"):
        current_str = f"+{current_value:.0f}"
        max_str = f"+{max_value:.0f}"
    else:
        current_str = f"+{current_value:.1f}%"
        max_str = f"+{max_value:.1f}%"

    summary_data.append({
        "Stat": display_name,
        "Level": f"{current_level}/{max_level}",
        "Current Value": current_str,
        "Max Value": max_str,
    })

st.dataframe(summary_data, use_container_width=True, hide_index=True)

# Notes
st.divider()
with st.expander("📝 Notes on Guild Skills"):
    st.markdown("""
    ### Guild Skill Mechanics

    - **Final Damage**: Multiplicative with other FD sources. Very valuable!
    - **Damage %**: Additive with other damage % sources
    - **Boss Damage %**: Only applies to boss monsters
    - **Defense Penetration %**: Applied FIRST in multiplicative stacking (gets full value)
    - **Crit Damage %**: Additive with other crit damage sources
    - **Main Stat %**: Increases your DEX/STR/INT/LUK by percentage
    - **Attack**: Flat attack bonus
    - **Max HP**: Increases survivability

    ### Priority

    Guild Defense Penetration has the **highest priority** in the calculation order:
    1. Guild Skill (Priority 1)
    2. Shoulder Potentials (Priority 2)
    3. Hero Power (Priority 3)
    4. Other sources (Priority 100)

    This means guild def pen gets applied when defense reduction is at maximum,
    giving it full effective value.
    """)
