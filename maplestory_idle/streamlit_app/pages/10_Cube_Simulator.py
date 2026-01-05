"""
Cube Simulator Page
Simulate potential rolling with pity system.
"""
import streamlit as st
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

st.set_page_config(page_title="Cube Simulator", page_icon="🎲", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()


# Tier definitions
class PotentialTier(Enum):
    RARE = "Rare"
    EPIC = "Epic"
    UNIQUE = "Unique"
    LEGENDARY = "Legendary"
    MYSTIC = "Mystic"


TIER_ORDER = [PotentialTier.RARE, PotentialTier.EPIC, PotentialTier.UNIQUE,
              PotentialTier.LEGENDARY, PotentialTier.MYSTIC]

# Tier up rates
TIER_UP_RATES = {
    PotentialTier.RARE: 0.03333,      # 3.333% to Epic
    PotentialTier.EPIC: 0.006,        # 0.6% to Unique
    PotentialTier.UNIQUE: 0.0021,     # 0.21% to Legendary
    PotentialTier.LEGENDARY: 0.0014,  # 0.14% to Mystic
    PotentialTier.MYSTIC: 0.0,        # Can't tier up
}

# Pity thresholds (regular cubes)
PITY_THRESHOLDS = {
    PotentialTier.RARE: 60,
    PotentialTier.EPIC: 150,
    PotentialTier.UNIQUE: 333,
    PotentialTier.LEGENDARY: 714,
    PotentialTier.MYSTIC: 999999,
}

# Potential stats by tier
POTENTIAL_STATS = {
    PotentialTier.RARE: [
        ("Damage %", 8.0), ("Main Stat %", 4.5), ("Crit Rate %", 4.5),
        ("Min Dmg %", 6.0), ("Max Dmg %", 6.0), ("Defense %", 4.5),
    ],
    PotentialTier.EPIC: [
        ("Damage %", 12.0), ("Main Stat %", 6.0), ("Crit Rate %", 6.0),
        ("Min Dmg %", 8.0), ("Max Dmg %", 8.0), ("Defense %", 6.0),
    ],
    PotentialTier.UNIQUE: [
        ("Damage %", 18.0), ("Main Stat %", 9.0), ("Crit Rate %", 9.0),
        ("Min Dmg %", 10.0), ("Max Dmg %", 10.0), ("Defense %", 9.0),
    ],
    PotentialTier.LEGENDARY: [
        ("Damage %", 25.0), ("Main Stat %", 12.0), ("Crit Rate %", 12.0),
        ("Min Dmg %", 15.0), ("Max Dmg %", 15.0), ("Defense %", 12.0),
    ],
    PotentialTier.MYSTIC: [
        ("Damage %", 35.0), ("Main Stat %", 15.0), ("Crit Rate %", 15.0),
        ("Min Dmg %", 25.0), ("Max Dmg %", 25.0), ("Defense %", 15.0),
    ],
}


def roll_potential(tier: PotentialTier, slot: int) -> tuple:
    """Roll a potential line for given tier and slot (1-3)."""
    stats = POTENTIAL_STATS[tier]
    # Slot 1 always current tier, slots 2-3 can be grey (lower tier)
    if slot == 1:
        use_tier = tier
    else:
        # 24% chance for slot 2, 8% chance for slot 3 to be current tier
        yellow_chance = 0.24 if slot == 2 else 0.08
        if random.random() < yellow_chance:
            use_tier = tier
        else:
            # Use previous tier (grey line)
            tier_idx = TIER_ORDER.index(tier)
            if tier_idx > 0:
                use_tier = TIER_ORDER[tier_idx - 1]
            else:
                use_tier = tier

    stats = POTENTIAL_STATS[use_tier]
    stat_name, value = random.choice(stats)
    return (stat_name, value, use_tier == tier)


def simulate_cube(current_tier: PotentialTier, pity_count: int):
    """Simulate using one cube. Returns (new_tier, new_pity, tier_upped, lines)."""
    rate = TIER_UP_RATES[current_tier]
    pity_threshold = PITY_THRESHOLDS[current_tier]

    # Check for tier up
    tier_upped = False
    new_tier = current_tier

    if current_tier != PotentialTier.MYSTIC:
        pity_count += 1
        if pity_count >= pity_threshold:
            tier_upped = True
        elif random.random() < rate:
            tier_upped = True

        if tier_upped:
            tier_idx = TIER_ORDER.index(current_tier)
            new_tier = TIER_ORDER[tier_idx + 1]
            pity_count = 0

    # Roll new lines
    lines = [
        roll_potential(new_tier, 1),
        roll_potential(new_tier, 2),
        roll_potential(new_tier, 3),
    ]

    return new_tier, pity_count if not tier_upped else 0, tier_upped, lines


# Initialize session state for simulator
if 'sim_tier' not in st.session_state:
    st.session_state.sim_tier = PotentialTier.RARE
if 'sim_pity' not in st.session_state:
    st.session_state.sim_pity = 0
if 'sim_cubes_used' not in st.session_state:
    st.session_state.sim_cubes_used = 0
if 'sim_lines' not in st.session_state:
    st.session_state.sim_lines = []
if 'sim_history' not in st.session_state:
    st.session_state.sim_history = []


st.title("🎲 Cube Simulator")
st.markdown("Simulate rolling potentials with the pity system.")

# Controls
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    if st.button("🎲 Use Cube", type="primary"):
        new_tier, new_pity, tier_upped, lines = simulate_cube(
            st.session_state.sim_tier,
            st.session_state.sim_pity
        )
        st.session_state.sim_tier = new_tier
        st.session_state.sim_pity = new_pity
        st.session_state.sim_cubes_used += 1
        st.session_state.sim_lines = lines

        if tier_upped:
            st.session_state.sim_history.append(
                f"🎉 TIER UP to {new_tier.value} after {st.session_state.sim_cubes_used} cubes!"
            )

with col2:
    if st.button("🔄 Reset"):
        st.session_state.sim_tier = PotentialTier.RARE
        st.session_state.sim_pity = 0
        st.session_state.sim_cubes_used = 0
        st.session_state.sim_lines = []
        st.session_state.sim_history = []
        st.rerun()

with col3:
    new_start_tier = st.selectbox(
        "Starting Tier",
        options=[t for t in TIER_ORDER if t != PotentialTier.MYSTIC],
        format_func=lambda x: x.value,
        index=TIER_ORDER.index(st.session_state.sim_tier) if st.session_state.sim_tier in TIER_ORDER[:-1] else 0
    )
    if new_start_tier != st.session_state.sim_tier and st.session_state.sim_cubes_used == 0:
        st.session_state.sim_tier = new_start_tier

st.divider()

# Current status
status_cols = st.columns(4)

with status_cols[0]:
    tier_colors = {
        PotentialTier.RARE: "🔵",
        PotentialTier.EPIC: "🟣",
        PotentialTier.UNIQUE: "🟡",
        PotentialTier.LEGENDARY: "🟢",
        PotentialTier.MYSTIC: "🔴",
    }
    st.metric("Current Tier", f"{tier_colors[st.session_state.sim_tier]} {st.session_state.sim_tier.value}")

with status_cols[1]:
    st.metric("Cubes Used", st.session_state.sim_cubes_used)

with status_cols[2]:
    pity_threshold = PITY_THRESHOLDS[st.session_state.sim_tier]
    if st.session_state.sim_tier != PotentialTier.MYSTIC:
        st.metric("Pity Progress", f"{st.session_state.sim_pity} / {pity_threshold}")
    else:
        st.metric("Pity Progress", "MAX TIER")

with status_cols[3]:
    rate = TIER_UP_RATES[st.session_state.sim_tier]
    if rate > 0:
        st.metric("Tier Up Rate", f"{rate * 100:.2f}%")
    else:
        st.metric("Tier Up Rate", "N/A")

st.divider()

# Current potentials
st.subheader("Current Potentials")

if st.session_state.sim_lines:
    for i, (stat_name, value, is_yellow) in enumerate(st.session_state.sim_lines, 1):
        color = "🟡" if is_yellow else "⚪"
        st.write(f"**Line {i}:** {color} {stat_name}: +{value:.1f}%")
else:
    st.info("Use a cube to roll potentials!")

st.divider()

# History
if st.session_state.sim_history:
    st.subheader("Tier Up History")
    for entry in reversed(st.session_state.sim_history[-10:]):
        st.success(entry)

st.divider()

# Info
st.subheader("Cube Mechanics")
st.info("""
**Tier Up Rates:**
- Rare → Epic: 3.333% (Pity: 60)
- Epic → Unique: 0.6% (Pity: 150)
- Unique → Legendary: 0.21% (Pity: 333)
- Legendary → Mystic: 0.14% (Pity: 714)

**Slot Colors:**
- Line 1: Always yellow (current tier)
- Line 2: 24% yellow, 76% grey (previous tier)
- Line 3: 8% yellow, 92% grey (previous tier)
""")
