"""
Upgrade Path Optimizer Page
Recommendations for optimal upgrade paths.
"""
import streamlit as st
from utils.data_manager import EQUIPMENT_SLOTS

st.set_page_config(page_title="Upgrade Optimizer", page_icon="📈", layout="wide")

if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.warning("Please login first!")
    st.stop()

data = st.session_state.user_data


def analyze_equipment():
    """Analyze equipment for upgrade opportunities."""
    opportunities = []

    for slot in EQUIPMENT_SLOTS:
        item = data.equipment_items.get(slot, {})
        pots = data.equipment_potentials.get(slot, {})

        stars = item.get('stars', 0)
        tier = item.get('tier', 1)
        pot_tier = pots.get('tier', 'Rare')

        # Check starforce
        if stars < 15:
            priority = "High" if stars < 10 else "Medium"
            opportunities.append({
                "Slot": slot.title(),
                "Type": "Starforce",
                "Current": f"{stars} stars",
                "Recommended": "15+ stars",
                "Priority": priority,
                "Notes": "Starforce provides main stat scaling"
            })

        # Check potential tier
        tier_priority = {
            "Rare": ("High", "Epic+"),
            "Epic": ("Medium", "Unique+"),
            "Unique": ("Low", "Legendary"),
            "Legendary": ("Very Low", "Mystic"),
        }
        if pot_tier in tier_priority:
            prio, rec = tier_priority[pot_tier]
            opportunities.append({
                "Slot": slot.title(),
                "Type": "Potential Tier",
                "Current": pot_tier,
                "Recommended": rec,
                "Priority": prio,
                "Notes": "Higher tiers = better stat values"
            })

        # Check for empty potential lines
        empty_lines = 0
        for i in range(1, 4):
            if not pots.get(f'line{i}_stat'):
                empty_lines += 1
        if empty_lines > 0:
            opportunities.append({
                "Slot": slot.title(),
                "Type": "Fill Potentials",
                "Current": f"{3 - empty_lines}/3 lines",
                "Recommended": "3/3 lines",
                "Priority": "High",
                "Notes": "Empty lines are wasted potential"
            })

    return opportunities


def analyze_hero_power():
    """Analyze hero power for improvements."""
    opportunities = []

    # Check passive levels
    passives = data.hero_power_passives
    if passives.get('main_stat', 0) < 10:
        opportunities.append({
            "Area": "Hero Power Passives",
            "Current": f"Main Stat Level {passives.get('main_stat', 0)}",
            "Recommended": "Max main stat passive",
            "Priority": "High",
        })
    if passives.get('damage', 0) < 10:
        opportunities.append({
            "Area": "Hero Power Passives",
            "Current": f"Damage Level {passives.get('damage', 0)}",
            "Recommended": "Max damage passive",
            "Priority": "High",
        })

    # Check hero power lines
    good_stats = ['damage', 'boss_damage', 'crit_damage', 'def_pen']
    weak_lines = []
    for line_key, line in data.hero_power_lines.items():
        stat = line.get('stat', '')
        if stat and stat not in good_stats:
            weak_lines.append(f"{line_key}: {stat}")

    if weak_lines:
        opportunities.append({
            "Area": "Hero Power Lines",
            "Current": f"{len(weak_lines)} weak lines",
            "Recommended": "Roll for Damage%/Boss%/Crit%",
            "Priority": "Medium",
        })

    return opportunities


def analyze_maple_rank():
    """Analyze maple rank progression."""
    opportunities = []

    mr = data.maple_rank
    stage = mr.get('current_stage', 1)
    ms_level = mr.get('main_stat_level', 0)

    if stage < 30:
        opportunities.append({
            "Area": "Maple Rank Stage",
            "Current": f"Stage {stage}",
            "Recommended": "Push to higher stages",
            "Priority": "High" if stage < 20 else "Medium",
        })

    if ms_level < 100:
        opportunities.append({
            "Area": "Main Stat Level",
            "Current": f"Level {ms_level}",
            "Recommended": "Max main stat upgrades",
            "Priority": "Medium",
        })

    return opportunities


st.title("📈 Upgrade Path Optimizer")
st.markdown("Get recommendations for the most impactful upgrades.")

st.info("""
**How to Use:**
This page analyzes your current stats and identifies the highest-impact upgrades.
Recommendations are based on general optimization principles.
""")

st.divider()

# Equipment Analysis
st.subheader("Equipment Recommendations")
eq_opps = analyze_equipment()

if eq_opps:
    # Sort by priority
    priority_order = {"High": 0, "Medium": 1, "Low": 2, "Very Low": 3}
    eq_opps.sort(key=lambda x: priority_order.get(x.get("Priority", "Low"), 99))
    st.dataframe(eq_opps, width='stretch', hide_index=True)
else:
    st.success("Equipment is well optimized!")

st.divider()

# Hero Power Analysis
st.subheader("Hero Power Recommendations")
hp_opps = analyze_hero_power()

if hp_opps:
    st.dataframe(hp_opps, width='stretch', hide_index=True)
else:
    st.success("Hero Power is well optimized!")

st.divider()

# Maple Rank Analysis
st.subheader("Maple Rank Recommendations")
mr_opps = analyze_maple_rank()

if mr_opps:
    st.dataframe(mr_opps, width='stretch', hide_index=True)
else:
    st.success("Maple Rank is well optimized!")

st.divider()

# General tips
st.subheader("General Optimization Tips")

st.markdown("""
### Priority Order (Early/Mid Game)
1. **Starforce to 15+** on all equipment
2. **Potential tier to Unique+** on all equipment
3. **Fill all potential lines** with good stats (Damage%, Boss%, etc.)
4. **Max Hero Power passives** (Main Stat and Damage)
5. **Push Maple Rank stages** for main stat bonuses

### Stat Priority (Stage Mode)
1. **Damage %** - Multiplicative with everything
2. **Main Stat %** - Strong scaling
3. **Crit Damage %** - Great if 100% crit rate
4. **Defense Penetration %** - Important for higher chapters
5. **Boss/Normal Damage %** - Weighted by combat mode

### Special Potential Priorities
- **Gloves**: Crit Damage (30% at Legendary)
- **Cape/Bottom**: Final Damage (8% at Legendary)
- **Shoulder**: Defense Pen (12% at Legendary)
- **Ring/Necklace**: All Skills (+12 at Legendary)
""")
