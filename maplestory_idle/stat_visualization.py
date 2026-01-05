"""
MapleStory Idle - Stat Effectiveness & Diminishing Returns Visualization
=========================================================================
Demonstrates why balanced stat allocation is more efficient than stacking
a single stat type.

Based on the verified Master Damage Formula:
    Damage = ATK × (1 + Stat%) × (1 + Damage%) × (1 + DamageAmp%) ×
             (1 + FinalDamage%) × (1 + CritDamage%) × DefenseMultiplier
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Tuple


# =============================================================================
# BASELINE CHARACTER STATS (from your Bowmaster)
# =============================================================================

BASELINE_STATS = {
    "damage_percent": 4.841,      # 484.1% base (before Hex)
    "final_damage": 0.518,        # 51.8% (base without Mortal/Flower)
    "crit_damage": 1.845,         # 184.5%
    "defense_pen": 0.609,         # 60.9%
    "dex_percent": 1.265,         # 126.5%
    "boss_damage": 0.645,         # 64.5%
}

# Enemy defense for calculations
ENEMY_DEF = 0.752  # Mu Lung 27-1


# =============================================================================
# DAMAGE CALCULATION
# =============================================================================

def calculate_damage_multiplier(
    damage_percent: float,
    final_damage: float,
    crit_damage: float,
    defense_pen: float,
    enemy_def: float = ENEMY_DEF,
    boss_damage: float = 0.0
) -> float:
    """
    Calculate the total damage multiplier from all stats.

    Returns relative damage (normalized so baseline = 1.0)
    """
    dmg_mult = 1 + damage_percent + boss_damage
    fd_mult = 1 + final_damage
    crit_mult = 1 + crit_damage
    def_mult = 1 / (1 + enemy_def * (1 - defense_pen))

    return dmg_mult * fd_mult * crit_mult * def_mult


def get_baseline_damage() -> float:
    """Get damage multiplier with baseline stats."""
    return calculate_damage_multiplier(
        damage_percent=BASELINE_STATS["damage_percent"],
        final_damage=BASELINE_STATS["final_damage"],
        crit_damage=BASELINE_STATS["crit_damage"],
        defense_pen=BASELINE_STATS["defense_pen"],
        boss_damage=BASELINE_STATS["boss_damage"]
    )


# =============================================================================
# PLOT 1: DIMINISHING RETURNS - DPS GAIN PER ADDITIONAL POINT
# =============================================================================

def plot_diminishing_returns():
    """
    Show how adding the same amount of a stat gives less DPS% as you stack more.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Diminishing Returns: DPS Gain per +10% Stat Increase", fontsize=14, fontweight='bold')

    baseline = get_baseline_damage()

    # Stat configurations: (name, baseline, x_range, increment)
    stats_config = [
        ("Damage %", "damage_percent", np.arange(1.0, 10.0, 0.1), 0.10),
        ("Final Damage %", "final_damage", np.arange(0.0, 2.0, 0.05), 0.10),
        ("Crit Damage %", "crit_damage", np.arange(0.5, 4.0, 0.1), 0.10),
        ("Defense Penetration %", "defense_pen", np.arange(0.0, 0.95, 0.05), 0.05),
    ]

    for ax, (name, stat_key, x_range, increment) in zip(axes.flatten(), stats_config):
        dps_gains = []
        x_values = []

        for current_value in x_range:
            # Create modified stats
            stats = dict(BASELINE_STATS)
            stats[stat_key] = current_value

            # Calculate DPS at current value
            dmg_before = calculate_damage_multiplier(
                damage_percent=stats["damage_percent"],
                final_damage=stats["final_damage"],
                crit_damage=stats["crit_damage"],
                defense_pen=stats["defense_pen"],
                boss_damage=stats["boss_damage"]
            )

            # Calculate DPS after adding increment
            stats[stat_key] = current_value + increment
            dmg_after = calculate_damage_multiplier(
                damage_percent=stats["damage_percent"],
                final_damage=stats["final_damage"],
                crit_damage=stats["crit_damage"],
                defense_pen=stats["defense_pen"],
                boss_damage=stats["boss_damage"]
            )

            # Calculate % DPS gain
            dps_gain = ((dmg_after / dmg_before) - 1) * 100
            dps_gains.append(dps_gain)
            x_values.append(current_value * 100)

        ax.plot(x_values, dps_gains, 'b-', linewidth=2)
        ax.axvline(x=BASELINE_STATS[stat_key] * 100, color='r', linestyle='--',
                   label=f'Your current: {BASELINE_STATS[stat_key]*100:.1f}%')
        ax.set_xlabel(f"Current {name}")
        ax.set_ylabel(f"DPS Gain from +{increment*100:.0f}%")
        ax.set_title(name)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Highlight diminishing returns
        ax.fill_between(x_values, dps_gains, alpha=0.3)

    plt.tight_layout()
    plt.savefig("diminishing_returns.png", dpi=150, bbox_inches='tight')
    plt.show()
    print("Saved: diminishing_returns.png")


# =============================================================================
# PLOT 2: STAT EFFICIENCY COMPARISON
# =============================================================================

def plot_stat_efficiency():
    """
    Compare the DPS value of investing in different stats at current levels.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    baseline = get_baseline_damage()

    # Test adding equivalent amounts to each stat
    investment_amounts = [0.05, 0.10, 0.15, 0.20, 0.25]  # 5% to 25%

    stats_to_test = [
        ("Damage %", "damage_percent"),
        ("Final Damage %", "final_damage"),
        ("Crit Damage %", "crit_damage"),
        ("Boss Damage %", "boss_damage"),
    ]

    x = np.arange(len(investment_amounts))
    width = 0.2

    for i, (name, stat_key) in enumerate(stats_to_test):
        dps_gains = []

        for amount in investment_amounts:
            stats = dict(BASELINE_STATS)
            stats[stat_key] = BASELINE_STATS[stat_key] + amount

            new_dmg = calculate_damage_multiplier(
                damage_percent=stats["damage_percent"],
                final_damage=stats["final_damage"],
                crit_damage=stats["crit_damage"],
                defense_pen=stats["defense_pen"],
                boss_damage=stats["boss_damage"]
            )

            dps_gain = ((new_dmg / baseline) - 1) * 100
            dps_gains.append(dps_gain)

        bars = ax.bar(x + i * width, dps_gains, width, label=name)

    ax.set_xlabel("Stat Investment Amount")
    ax.set_ylabel("DPS Increase (%)")
    ax.set_title("DPS Gain from Equal Investment in Different Stats\n(Based on YOUR current stat levels)")
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels([f"+{int(a*100)}%" for a in investment_amounts])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig("stat_efficiency.png", dpi=150, bbox_inches='tight')
    plt.show()
    print("Saved: stat_efficiency.png")


# =============================================================================
# PLOT 3: BALANCED VS STACKED - THE KEY INSIGHT
# =============================================================================

def plot_balanced_vs_stacked():
    """
    The key visualization: Show that spreading stats is better than stacking.

    Example: You have 60% worth of stats to allocate.
    Option A: Put all 60% into Damage %
    Option B: Put 20% into Damage%, 20% into FD, 20% into CD
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    baseline = get_baseline_damage()

    # Total "budget" to allocate (in equivalent % points)
    budgets = np.arange(0, 1.01, 0.05)  # 0% to 100%

    # Strategy 1: All into Damage %
    all_damage = []
    # Strategy 2: All into Final Damage
    all_fd = []
    # Strategy 3: All into Crit Damage
    all_cd = []
    # Strategy 4: Split evenly across all three
    balanced = []

    for budget in budgets:
        # All Damage %
        stats = dict(BASELINE_STATS)
        stats["damage_percent"] += budget
        all_damage.append(calculate_damage_multiplier(
            stats["damage_percent"], stats["final_damage"],
            stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
        ) / baseline * 100 - 100)

        # All Final Damage
        stats = dict(BASELINE_STATS)
        stats["final_damage"] += budget
        all_fd.append(calculate_damage_multiplier(
            stats["damage_percent"], stats["final_damage"],
            stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
        ) / baseline * 100 - 100)

        # All Crit Damage
        stats = dict(BASELINE_STATS)
        stats["crit_damage"] += budget
        all_cd.append(calculate_damage_multiplier(
            stats["damage_percent"], stats["final_damage"],
            stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
        ) / baseline * 100 - 100)

        # Balanced (split into thirds)
        stats = dict(BASELINE_STATS)
        stats["damage_percent"] += budget / 3
        stats["final_damage"] += budget / 3
        stats["crit_damage"] += budget / 3
        balanced.append(calculate_damage_multiplier(
            stats["damage_percent"], stats["final_damage"],
            stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
        ) / baseline * 100 - 100)

    # Left plot: Compare strategies
    ax1 = axes[0]
    ax1.plot(budgets * 100, all_damage, 'b-', linewidth=2, label='All → Damage %')
    ax1.plot(budgets * 100, all_fd, 'g-', linewidth=2, label='All → Final Damage')
    ax1.plot(budgets * 100, all_cd, 'orange', linewidth=2, label='All → Crit Damage')
    ax1.plot(budgets * 100, balanced, 'r-', linewidth=3, label='Balanced (1/3 each)')

    ax1.set_xlabel("Total Stat Budget (%)")
    ax1.set_ylabel("DPS Increase (%)")
    ax1.set_title("Stacking One Stat vs Balanced Distribution")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Add annotation showing the gap
    idx_50 = 10  # At 50% budget
    ax1.annotate(f'+{balanced[idx_50] - all_damage[idx_50]:.1f}% more DPS\nfrom balancing!',
                xy=(50, balanced[idx_50]), xytext=(60, balanced[idx_50] + 5),
                arrowprops=dict(arrowstyle='->', color='red'),
                fontsize=10, color='red')

    # Right plot: Advantage of balanced approach
    ax2 = axes[1]
    advantage_vs_damage = [b - d for b, d in zip(balanced, all_damage)]
    advantage_vs_fd = [b - f for b, f in zip(balanced, all_fd)]
    advantage_vs_cd = [b - c for b, c in zip(balanced, all_cd)]

    ax2.fill_between(budgets * 100, advantage_vs_damage, alpha=0.3, color='blue', label='vs All Damage %')
    ax2.fill_between(budgets * 100, advantage_vs_fd, alpha=0.3, color='green', label='vs All Final Damage')
    ax2.fill_between(budgets * 100, advantage_vs_cd, alpha=0.3, color='orange', label='vs All Crit Damage')
    ax2.plot(budgets * 100, advantage_vs_damage, 'b-', linewidth=2)
    ax2.plot(budgets * 100, advantage_vs_fd, 'g-', linewidth=2)
    ax2.plot(budgets * 100, advantage_vs_cd, 'orange', linewidth=2)

    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_xlabel("Total Stat Budget (%)")
    ax2.set_ylabel("Extra DPS from Balanced Approach (%)")
    ax2.set_title("Advantage of Balanced Stats Over Single-Stat Stacking")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("balanced_vs_stacked.png", dpi=150, bbox_inches='tight')
    plt.show()
    print("Saved: balanced_vs_stacked.png")


# =============================================================================
# PLOT 4: MARGINAL DPS VALUE HEATMAP
# =============================================================================

def plot_marginal_value_comparison():
    """
    Show the marginal DPS value of each stat at various levels.
    This creates a "priority guide" for which stat to upgrade next.
    """
    fig, ax = plt.subplots(figsize=(12, 8))

    # Stats and their test ranges
    stats_ranges = {
        "Damage %": np.arange(2.0, 8.0, 0.5),
        "Final Damage %": np.arange(0.2, 1.2, 0.1),
        "Crit Damage %": np.arange(1.0, 3.0, 0.2),
        "Boss Damage %": np.arange(0.2, 1.2, 0.1),
    }

    stat_keys = ["damage_percent", "final_damage", "crit_damage", "boss_damage"]
    stat_names = list(stats_ranges.keys())

    # For each stat level, calculate the marginal value of +10%
    increment = 0.10

    data = []
    labels_y = []

    for stat_name, stat_key, values in zip(stat_names, stat_keys, stats_ranges.values()):
        row = []
        for val in values:
            stats = dict(BASELINE_STATS)
            stats[stat_key] = val

            dmg_before = calculate_damage_multiplier(
                stats["damage_percent"], stats["final_damage"],
                stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
            )

            stats[stat_key] = val + increment
            dmg_after = calculate_damage_multiplier(
                stats["damage_percent"], stats["final_damage"],
                stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
            )

            dps_gain = ((dmg_after / dmg_before) - 1) * 100
            row.append(dps_gain)

        data.append(row)
        labels_y.append(stat_name)

    # Normalize row lengths (pad with NaN if needed)
    max_len = max(len(row) for row in data)
    for row in data:
        while len(row) < max_len:
            row.append(np.nan)

    data_array = np.array(data)

    im = ax.imshow(data_array, cmap='RdYlGn', aspect='auto')

    ax.set_yticks(range(len(stat_names)))
    ax.set_yticklabels(stat_names)
    ax.set_xlabel("Stat Level (Low → High)")
    ax.set_title("Marginal DPS Value of +10% (Green = High Value, Red = Low Value)\nPrioritize GREEN cells!")

    cbar = plt.colorbar(im)
    cbar.set_label("DPS Gain from +10%")

    # Add current position markers
    for i, (stat_key, values) in enumerate(zip(stat_keys, stats_ranges.values())):
        current = BASELINE_STATS[stat_key]
        if values[0] <= current <= values[-1]:
            pos = np.searchsorted(values, current)
            ax.plot(pos, i, 'ko', markersize=15, markerfacecolor='white', markeredgewidth=2)
            ax.annotate('YOU', (pos, i), ha='center', va='center', fontsize=8, fontweight='bold')

    plt.tight_layout()
    plt.savefig("marginal_value_heatmap.png", dpi=150, bbox_inches='tight')
    plt.show()
    print("Saved: marginal_value_heatmap.png")


# =============================================================================
# PLOT 5: INVESTMENT OPTIMIZER - WHAT TO UPGRADE NEXT
# =============================================================================

def plot_next_upgrade_priority():
    """
    Bar chart showing which stat gives the most DPS per % invested RIGHT NOW.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    baseline = get_baseline_damage()
    increment = 0.10  # 10% investment

    stats_to_test = [
        ("Damage %", "damage_percent"),
        ("Final Damage %", "final_damage"),
        ("Crit Damage %", "crit_damage"),
        ("Boss Damage %", "boss_damage"),
        ("Defense Pen %", "defense_pen"),
    ]

    names = []
    gains = []
    current_values = []

    for name, stat_key in stats_to_test:
        stats = dict(BASELINE_STATS)

        dmg_before = calculate_damage_multiplier(
            stats["damage_percent"], stats["final_damage"],
            stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
        )

        # Add increment
        if stat_key == "defense_pen":
            # Defense pen is multiplicative, so adding 10% works differently
            remaining = 1 - stats[stat_key]
            stats[stat_key] = 1 - (remaining * (1 - increment))
        else:
            stats[stat_key] += increment

        dmg_after = calculate_damage_multiplier(
            stats["damage_percent"], stats["final_damage"],
            stats["crit_damage"], stats["defense_pen"], boss_damage=stats["boss_damage"]
        )

        dps_gain = ((dmg_after / dmg_before) - 1) * 100

        names.append(name)
        gains.append(dps_gain)
        current_values.append(BASELINE_STATS[stat_key] * 100)

    # Sort by gain
    sorted_data = sorted(zip(gains, names, current_values), reverse=True)
    gains, names, current_values = zip(*sorted_data)

    colors = plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(names)))[::-1]
    bars = ax.barh(names, gains, color=colors)

    ax.set_xlabel("DPS Gain from +10%")
    ax.set_title("Which Stat to Upgrade Next?\n(Based on YOUR current stats - Higher = Better Value)")

    # Add value labels
    for bar, gain, current in zip(bars, gains, current_values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                f'+{gain:.2f}% DPS (current: {current:.1f}%)',
                va='center', fontsize=9)

    ax.set_xlim(0, max(gains) * 1.4)
    ax.grid(True, alpha=0.3, axis='x')

    plt.tight_layout()
    plt.savefig("upgrade_priority.png", dpi=150, bbox_inches='tight')
    plt.show()
    print("Saved: upgrade_priority.png")


# =============================================================================
# MAIN - GENERATE ALL PLOTS
# =============================================================================

def generate_all_plots():
    """Generate all visualization plots."""
    print("=" * 60)
    print("MapleStory Idle - Stat Effectiveness Visualization")
    print("=" * 60)
    print()
    print("Your current stats:")
    for name, value in BASELINE_STATS.items():
        print(f"  {name}: {value*100:.1f}%")
    print()

    print("Generating plots...")
    print()

    print("1. Diminishing Returns Plot")
    plot_diminishing_returns()
    print()

    print("2. Stat Efficiency Comparison")
    plot_stat_efficiency()
    print()

    print("3. Balanced vs Stacked Comparison")
    plot_balanced_vs_stacked()
    print()

    print("4. Marginal Value Heatmap")
    plot_marginal_value_comparison()
    print()

    print("5. Upgrade Priority Chart")
    plot_next_upgrade_priority()
    print()

    print("=" * 60)
    print("All plots generated!")
    print("=" * 60)


if __name__ == "__main__":
    generate_all_plots()
