"""
Stat Efficiency Guide Page
Educational reference for stat values and efficiency.
"""
import streamlit as st

st.set_page_config(page_title="Stat Guide", page_icon="📚", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()


st.title("📚 Stat Efficiency Guide")
st.markdown("Learn about stat values, efficiency, and optimization strategies.")

# Stat overview
st.header("Stat Overview")

tab1, tab2, tab3, tab4 = st.tabs(["Damage Stats", "Defensive Stats", "Special Stats", "Formulas"])

with tab1:
    st.subheader("Damage Stats")

    st.markdown("""
    ### Damage % (Additive)
    - Primary damage multiplier
    - Stacks additively with itself
    - Affected by Hex multiplier (1.24^stacks)
    - **Value:** S-Tier, always valuable

    ### Boss Damage %
    - Only applies to boss enemies
    - In Stage mode: Affects 40% of enemies
    - In Boss mode: Affects 100% of enemies
    - **Value:** S-Tier for bossing, A-Tier for stages

    ### Normal Damage %
    - Only applies to normal monsters
    - In Stage mode: Affects 60% of enemies
    - Useless in Boss/World Boss mode
    - **Value:** A-Tier for stages only

    ### Critical Damage %
    - Bonus damage on critical hits
    - Base: 30% crit damage
    - Requires 100% crit rate for full value
    - **Value:** S-Tier if crit capped, B-Tier otherwise

    ### Final Damage %
    - Multiplicative with everything
    - Extremely valuable as a separate multiplier
    - Only available on Cape/Bottom specials
    - **Value:** S-Tier, always valuable
    """)

with tab2:
    st.subheader("Defensive & Utility Stats")

    st.markdown("""
    ### Defense Penetration %
    - Reduces enemy defense effectiveness
    - Formula: 1 / (1 + enemy_def × (1 - def_pen))
    - More valuable in higher chapters (higher enemy defense)
    - **Value:** S-Tier in high chapters, A-Tier otherwise

    ### Critical Rate %
    - Chance to deal critical hits
    - Cap: 100% (excess is wasted)
    - Required to make Crit Damage valuable
    - **Value:** A-Tier until capped, then worthless

    ### Attack Speed %
    - Increases attack frequency
    - Diminishing returns at high values
    - **Value:** B-Tier, situational

    ### Main Stat % (DEX/STR/INT/LUK)
    - Scales your flat main stat
    - Formula: 1 + (total_stat / 10000)
    - **Value:** S-Tier early game, A-Tier late game
    """)

with tab3:
    st.subheader("Special Stats")

    st.markdown("""
    ### All Skills
    - Increases all skill levels
    - Very powerful for skill damage scaling
    - Available on Ring/Necklace specials
    - **Value:** S-Tier for most classes

    ### Skill Cooldown
    - Reduces skill cooldowns (seconds)
    - Available on Hat specials
    - Minimum 4 second cooldown
    - **Value:** B-Tier, class dependent

    ### Buff Duration
    - Extends buff timers
    - Available on Belt specials
    - **Value:** B-Tier, situational

    ### Basic Attack Targets
    - Adds extra basic attack hits
    - Only valuable in Stage mode (mob clearing)
    - Useless for single-target bosses
    - Available on Top specials
    - **Value:** A-Tier for stages, F-Tier for bosses

    ### Main Stat per Level
    - Flat stat based on character level
    - Available on Face specials
    - **Value:** A-Tier at high levels
    """)

with tab4:
    st.subheader("Damage Formula")

    st.code("""
    Total DPS = Base_Attack
              × Stat_Multiplier        (1 + total_stat / 10000)
              × Damage_Multiplier      (1 + damage% × hex_mult)
              × Combat_Multiplier      (boss% or normal% weighted)
              × Final_Damage           (1 + final%)
              × Crit_Multiplier        (1 + crit_dmg%)
              × Defense_Multiplier     (1 / (1 + def × (1 - def_pen)))
              × Range_Multiplier       ((min% + max%) / 2 / 100)
              × Speed_Multiplier       (1 + atk_speed%)
    """, language="text")

    st.markdown("""
    ### Key Insights

    1. **Multiplicative vs Additive**
       - Stats within the same category are additive
       - Different categories multiply together
       - Final Damage is its own multiplier = very valuable

    2. **Hex Multiplier**
       - Damage% is multiplied by 1.24^stacks (max 3 stacks)
       - At 3 stacks: 1.24³ = 1.91x multiplier on Damage%
       - Makes Damage% the most valuable stat

    3. **Combat Mode Weighting**
       - Stage: 60% normal, 40% boss
       - Boss/World Boss: 100% boss
       - Choose stats based on your focus

    4. **Diminishing Returns**
       - As you stack more of one stat, marginal value decreases
       - Balance stats across multiplier categories
       - Exception: Damage% always valuable due to Hex
    """)

st.divider()

# Stat tier list
st.header("Stat Tier List")

tier_data = {
    "S-Tier": [
        ("Damage %", "Always valuable, amplified by Hex"),
        ("Main Stat %", "Strong stat multiplier"),
        ("Crit Damage %", "Huge multiplier if crit capped"),
        ("Final Damage %", "Separate multiplier, always valuable"),
        ("Defense Pen %", "Critical for high chapters"),
        ("All Skills", "Massive skill damage boost"),
    ],
    "A-Tier": [
        ("Boss Damage %", "Great for bossing content"),
        ("Normal Damage %", "Great for stage farming"),
        ("Min/Max Dmg %", "Solid damage range increase"),
        ("Crit Rate %", "Required until capped"),
        ("Stat per Level", "Good flat stat scaling"),
    ],
    "B-Tier": [
        ("Attack Speed %", "Situational, diminishing returns"),
        ("Skill Cooldown", "Class dependent"),
        ("Buff Duration", "Situational"),
        ("BA Targets", "Good for stages, useless for bosses"),
    ],
    "F-Tier": [
        ("Defense %", "Useless for damage"),
        ("Max HP/MP", "Useless for damage"),
        ("Flat Main Stat", "Poor scaling late game"),
    ],
}

cols = st.columns(len(tier_data))
for col, (tier, stats) in zip(cols, tier_data.items()):
    with col:
        if tier == "S-Tier":
            st.markdown(f"### 🥇 {tier}")
        elif tier == "A-Tier":
            st.markdown(f"### 🥈 {tier}")
        elif tier == "B-Tier":
            st.markdown(f"### 🥉 {tier}")
        else:
            st.markdown(f"### ⚫ {tier}")

        for stat, desc in stats:
            st.markdown(f"**{stat}**")
            st.caption(desc)
            st.markdown("---")

st.divider()

# Equipment special potentials
st.header("Special Potential Reference")

special_data = [
    {"Slot": "Hat", "Special": "Skill Cooldown", "Legendary": "-1.5s", "Mystic": "-2.0s"},
    {"Slot": "Gloves", "Special": "Crit Damage", "Legendary": "+30%", "Mystic": "+50%"},
    {"Slot": "Shoulder", "Special": "Defense Pen", "Legendary": "+12%", "Mystic": "+20%"},
    {"Slot": "Cape", "Special": "Final Damage", "Legendary": "+8%", "Mystic": "+12%"},
    {"Slot": "Bottom", "Special": "Final Damage", "Legendary": "+8%", "Mystic": "+12%"},
    {"Slot": "Ring", "Special": "All Skills", "Legendary": "+12", "Mystic": "+16"},
    {"Slot": "Necklace", "Special": "All Skills", "Legendary": "+12", "Mystic": "+16"},
    {"Slot": "Belt", "Special": "Buff Duration", "Legendary": "+12%", "Mystic": "+20%"},
    {"Slot": "Face", "Special": "Stat/Level", "Legendary": "+8/lvl", "Mystic": "+12/lvl"},
    {"Slot": "Top", "Special": "BA Targets", "Legendary": "+2", "Mystic": "+3"},
]

st.dataframe(special_data, width='stretch', hide_index=True)

st.info("""
**Tip:** Special potentials have a 1% base chance per line.
Priority special potentials for your class:
- **All Classes:** Gloves (Crit Dmg), Cape (Final Dmg), Bottom (Final Dmg)
- **Skill Classes:** Ring (All Skills), Necklace (All Skills)
- **High Chapter:** Shoulder (Def Pen)
""")
