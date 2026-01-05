"""
Cube Cost Calculator Page
Estimate cube costs for tier upgrades.
"""
import streamlit as st
from enum import Enum

st.set_page_config(page_title="Cube Cost Calculator", page_icon="💎", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()


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
    PotentialTier.RARE: 0.03333,
    PotentialTier.EPIC: 0.006,
    PotentialTier.UNIQUE: 0.0021,
    PotentialTier.LEGENDARY: 0.0014,
}

# Pity thresholds
PITY_THRESHOLDS = {
    PotentialTier.RARE: 60,
    PotentialTier.EPIC: 150,
    PotentialTier.UNIQUE: 333,
    PotentialTier.LEGENDARY: 714,
}

# Cube prices
CUBE_COST_DIAMOND = 3000  # blue diamonds per regular cube


def expected_cubes_with_pity(p: float, pity: int) -> float:
    """Calculate expected cubes using truncated geometric distribution."""
    if p <= 0:
        return float(pity)
    if p >= 1:
        return 1.0
    q = 1 - p
    return (1 - q**pity) / p


def calculate_expected_cubes(from_tier: PotentialTier, to_tier: PotentialTier) -> float:
    """Calculate expected cubes to go from one tier to another."""
    from_idx = TIER_ORDER.index(from_tier)
    to_idx = TIER_ORDER.index(to_tier)

    if from_idx >= to_idx:
        return 0

    total_cubes = 0
    for i in range(from_idx, to_idx):
        tier = TIER_ORDER[i]
        rate = TIER_UP_RATES[tier]
        pity = PITY_THRESHOLDS[tier]
        total_cubes += expected_cubes_with_pity(rate, pity)

    return total_cubes


st.title("💎 Cube Cost Calculator")
st.markdown("Estimate the number of cubes and costs needed for tier upgrades.")

# Input
col1, col2 = st.columns(2)

with col1:
    from_tier = st.selectbox(
        "Current Tier",
        options=TIER_ORDER[:-1],  # Can't start from Mystic
        format_func=lambda x: x.value
    )

with col2:
    from_idx = TIER_ORDER.index(from_tier)
    valid_targets = TIER_ORDER[from_idx + 1:]
    to_tier = st.selectbox(
        "Target Tier",
        options=valid_targets,
        format_func=lambda x: x.value
    )

st.divider()

# Calculate
expected_cubes = calculate_expected_cubes(from_tier, to_tier)
expected_cost = expected_cubes * CUBE_COST_DIAMOND

# Results
st.subheader("Expected Results")

result_cols = st.columns(3)

with result_cols[0]:
    st.metric("Expected Cubes", f"{expected_cubes:.1f}")

with result_cols[1]:
    st.metric("Cost (Blue Diamonds)", f"{expected_cost:,.0f}")

with result_cols[2]:
    # Approximate USD (rough estimate: $100 = ~50k diamonds)
    usd_estimate = expected_cost / 500
    st.metric("Approx. USD", f"${usd_estimate:.2f}")

st.divider()

# Breakdown by tier
st.subheader("Tier-by-Tier Breakdown")

from_idx = TIER_ORDER.index(from_tier)
to_idx = TIER_ORDER.index(to_tier)

breakdown_data = []
for i in range(from_idx, to_idx):
    tier = TIER_ORDER[i]
    next_tier = TIER_ORDER[i + 1]
    rate = TIER_UP_RATES[tier]
    pity = PITY_THRESHOLDS[tier]
    expected = expected_cubes_with_pity(rate, pity)

    breakdown_data.append({
        "Upgrade": f"{tier.value} → {next_tier.value}",
        "Rate": f"{rate * 100:.3f}%",
        "Pity": pity,
        "Expected Cubes": f"{expected:.1f}",
        "Cost": f"{expected * CUBE_COST_DIAMOND:,.0f}",
    })

if breakdown_data:
    st.dataframe(breakdown_data, width='stretch', hide_index=True)

st.divider()

# Reference table
st.subheader("Quick Reference")

ref_data = []
for tier in TIER_ORDER[:-1]:
    next_tier = TIER_ORDER[TIER_ORDER.index(tier) + 1]
    rate = TIER_UP_RATES[tier]
    pity = PITY_THRESHOLDS[tier]
    expected = expected_cubes_with_pity(rate, pity)
    naive = 1 / rate if rate > 0 else float('inf')

    ref_data.append({
        "Upgrade": f"{tier.value} → {next_tier.value}",
        "Rate": f"{rate * 100:.3f}%",
        "Pity": pity,
        "Naive (1/rate)": f"{naive:.0f}",
        "With Pity": f"{expected:.1f}",
        "Pity Savings": f"{((naive - expected) / naive * 100):.1f}%",
    })

st.dataframe(ref_data, width='stretch', hide_index=True)

st.info("""
**Notes:**
- Expected cubes calculated using truncated geometric distribution
- Pity system guarantees tier-up at threshold (not just increases rate)
- Actual costs may vary based on RNG and cube source
""")
