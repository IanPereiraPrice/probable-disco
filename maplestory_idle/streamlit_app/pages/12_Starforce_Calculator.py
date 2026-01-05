"""
Starforce Calculator Page
Calculate starforce enhancement costs and success rates.
"""
import streamlit as st

st.set_page_config(page_title="Starforce Calculator", page_icon="⭐", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()


# Starforce success rates
SUCCESS_RATES = {
    0: 0.95, 1: 0.90, 2: 0.85, 3: 0.85, 4: 0.80,
    5: 0.75, 6: 0.70, 7: 0.65, 8: 0.60, 9: 0.55,
    10: 0.50, 11: 0.45, 12: 0.40, 13: 0.35, 14: 0.30,
    15: 0.30, 16: 0.30, 17: 0.30, 18: 0.30, 19: 0.30,
    20: 0.30, 21: 0.30, 22: 0.03, 23: 0.02, 24: 0.01,
}

# Destroy rates (above 12 stars)
DESTROY_RATES = {
    12: 0.01, 13: 0.02, 14: 0.02, 15: 0.03, 16: 0.03,
    17: 0.03, 18: 0.04, 19: 0.04, 20: 0.10, 21: 0.10,
    22: 0.20, 23: 0.30, 24: 0.40,
}

# Base meso costs per star (approximate, tier 4 equipment)
BASE_COSTS = {
    0: 10000, 1: 15000, 2: 20000, 3: 25000, 4: 30000,
    5: 40000, 6: 50000, 7: 60000, 8: 80000, 9: 100000,
    10: 150000, 11: 200000, 12: 300000, 13: 400000, 14: 500000,
    15: 800000, 16: 1000000, 17: 1500000, 18: 2000000, 19: 3000000,
    20: 5000000, 21: 8000000, 22: 12000000, 23: 18000000, 24: 25000000,
}


def calculate_expected_attempts(from_star: int, to_star: int) -> float:
    """Calculate expected attempts to go from one star to another."""
    if from_star >= to_star:
        return 0

    total_attempts = 0
    for star in range(from_star, to_star):
        rate = SUCCESS_RATES.get(star, 0.30)
        if rate > 0:
            total_attempts += 1 / rate
        else:
            total_attempts += float('inf')

    return total_attempts


def calculate_expected_cost(from_star: int, to_star: int) -> float:
    """Calculate expected meso cost."""
    if from_star >= to_star:
        return 0

    total_cost = 0
    for star in range(from_star, to_star):
        rate = SUCCESS_RATES.get(star, 0.30)
        base_cost = BASE_COSTS.get(star, 25000000)
        if rate > 0:
            expected_attempts = 1 / rate
            total_cost += base_cost * expected_attempts
        else:
            total_cost += float('inf')

    return total_cost


st.title("⭐ Starforce Calculator")
st.markdown("Calculate enhancement costs and success rates.")

# Input
col1, col2 = st.columns(2)

with col1:
    from_star = st.number_input("Current Stars", min_value=0, max_value=24, value=0)

with col2:
    to_star = st.number_input("Target Stars", min_value=0, max_value=25, value=15)

st.divider()

# Calculate
if to_star > from_star:
    expected_attempts = calculate_expected_attempts(from_star, to_star)
    expected_cost = calculate_expected_cost(from_star, to_star)

    # Results
    st.subheader("Expected Results")

    result_cols = st.columns(3)

    with result_cols[0]:
        st.metric("Expected Attempts", f"{expected_attempts:.1f}")

    with result_cols[1]:
        if expected_cost < 1000000:
            cost_str = f"{expected_cost:,.0f}"
        else:
            cost_str = f"{expected_cost / 1000000:.2f}M"
        st.metric("Expected Cost (Mesos)", cost_str)

    with result_cols[2]:
        success_next = SUCCESS_RATES.get(from_star, 0.30)
        st.metric("Next Success Rate", f"{success_next * 100:.1f}%")

    st.divider()

    # Step by step breakdown
    st.subheader("Step-by-Step Breakdown")

    breakdown_data = []
    for star in range(from_star, to_star):
        rate = SUCCESS_RATES.get(star, 0.30)
        destroy = DESTROY_RATES.get(star, 0)
        cost = BASE_COSTS.get(star, 25000000)
        expected = 1 / rate if rate > 0 else float('inf')

        breakdown_data.append({
            "Star": f"{star} → {star + 1}",
            "Success": f"{rate * 100:.1f}%",
            "Destroy": f"{destroy * 100:.1f}%" if destroy > 0 else "-",
            "Cost/Try": f"{cost:,}",
            "Expected Tries": f"{expected:.2f}",
            "Expected Cost": f"{cost * expected:,.0f}",
        })

    st.dataframe(breakdown_data, width='stretch', hide_index=True)

else:
    st.info("Target stars must be higher than current stars.")

st.divider()

# Reference tables
st.subheader("Success Rate Reference")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Stars 0-12 (Safe Zone)**")
    safe_data = []
    for star in range(0, 13):
        rate = SUCCESS_RATES.get(star, 0)
        safe_data.append({
            "Star": f"{star}→{star+1}",
            "Rate": f"{rate * 100:.0f}%",
        })
    st.dataframe(safe_data, width='stretch', hide_index=True)

with col2:
    st.markdown("**Stars 13-24 (Danger Zone)**")
    danger_data = []
    for star in range(13, 25):
        rate = SUCCESS_RATES.get(star, 0)
        destroy = DESTROY_RATES.get(star, 0)
        danger_data.append({
            "Star": f"{star}→{star+1}",
            "Rate": f"{rate * 100:.0f}%",
            "Destroy": f"{destroy * 100:.0f}%",
        })
    st.dataframe(danger_data, width='stretch', hide_index=True)

st.warning("""
**Warning:** Stars 22+ have very low success rates and high destroy chances!
- 22→23: 3% success, 20% destroy
- 23→24: 2% success, 30% destroy
- 24→25: 1% success, 40% destroy
""")
