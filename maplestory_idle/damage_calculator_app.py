"""
MapleStory Idle - Interactive Damage Calculator
================================================
Adjust sliders to see real-time impact on DPS.
Includes live visualization of stat priority and diminishing returns.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple


# =============================================================================
# DAMAGE CALCULATION (from your verified formulas)
# =============================================================================

DAMAGE_AMP_DIVISOR = 396.5
HEX_MULTIPLIER = 1.24


def calculate_damage(
    base_atk: float,
    dex_flat: float,
    dex_percent: float,
    damage_percent: float,
    hex_stacks: int,
    damage_amp: float,
    final_damage_sources: list,
    crit_damage: float,
    defense_pen: float,
    enemy_def: float,
    boss_damage: float,
) -> Dict[str, float]:
    """Calculate damage with full breakdown."""

    # DEX calculation
    total_dex = dex_flat * (1 + dex_percent / 100)
    stat_multiplier = 1 + (total_dex * 0.01)

    # Damage % with Hex stacks
    hex_mult = HEX_MULTIPLIER ** min(hex_stacks, 3)
    total_damage_percent = (damage_percent / 100) * hex_mult
    damage_multiplier = 1 + total_damage_percent + (boss_damage / 100)

    # Damage Amplification
    amp_multiplier = 1 + (damage_amp / DAMAGE_AMP_DIVISOR)

    # Final Damage (multiplicative)
    fd_multiplier = 1.0
    for fd in final_damage_sources:
        fd_multiplier *= (1 + fd / 100)

    # Crit Damage
    crit_multiplier = 1 + (crit_damage / 100)

    # Defense
    def_pen_decimal = defense_pen / 100
    defense_multiplier = 1 / (1 + enemy_def * (1 - def_pen_decimal))

    # Total damage
    total = (base_atk * stat_multiplier * damage_multiplier *
             amp_multiplier * fd_multiplier * crit_multiplier * defense_multiplier)

    return {
        "total": total,
        "stat_mult": stat_multiplier,
        "damage_mult": damage_multiplier,
        "amp_mult": amp_multiplier,
        "fd_mult": fd_multiplier,
        "crit_mult": crit_multiplier,
        "def_mult": defense_multiplier,
        "total_dex": total_dex,
        "effective_damage_pct": total_damage_percent * 100,
    }


# =============================================================================
# CANVAS BAR CHART (no matplotlib needed)
# =============================================================================

class BarChart:
    """Simple horizontal bar chart using tkinter Canvas."""

    def __init__(self, parent, width=380, height=200):
        self.width = width
        self.height = height
        self.bar_height = 28
        self.padding = 10
        self.label_width = 100

        self.canvas = tk.Canvas(parent, width=width, height=height,
                                bg='#1a1a2e', highlightthickness=0)
        self.canvas.pack(pady=5)

    def update(self, data: List[Tuple[str, float, str]]):
        """
        Update chart with new data.
        data: List of (label, value, color) tuples
        """
        self.canvas.delete("all")

        if not data:
            return

        max_val = max(d[1] for d in data) if data else 1
        bar_area_width = self.width - self.label_width - self.padding * 2

        # Sort by value (highest first)
        data = sorted(data, key=lambda x: x[1], reverse=True)

        for i, (label, value, color) in enumerate(data):
            y = self.padding + i * (self.bar_height + 5)

            # Label
            self.canvas.create_text(
                self.label_width - 5, y + self.bar_height // 2,
                text=label, anchor=tk.E, fill='#ccc',
                font=('Segoe UI', 9)
            )

            # Bar background
            self.canvas.create_rectangle(
                self.label_width, y,
                self.label_width + bar_area_width, y + self.bar_height,
                fill='#2a2a4e', outline=''
            )

            # Bar fill
            bar_width = (value / max_val) * bar_area_width if max_val > 0 else 0
            self.canvas.create_rectangle(
                self.label_width, y,
                self.label_width + bar_width, y + self.bar_height,
                fill=color, outline=''
            )

            # Value text
            self.canvas.create_text(
                self.label_width + bar_width + 5, y + self.bar_height // 2,
                text=f"+{value:.2f}%", anchor=tk.W, fill='white',
                font=('Consolas', 9, 'bold')
            )


class DiminishingReturnsChart:
    """Line chart showing diminishing returns as you stack a stat."""

    def __init__(self, parent, width=380, height=150):
        self.width = width
        self.height = height
        self.padding = 40

        self.canvas = tk.Canvas(parent, width=width, height=height,
                                bg='#1a1a2e', highlightthickness=0)
        self.canvas.pack(pady=5)

    def update(self, stat_name: str, current_val: float, data_points: List[Tuple[float, float]], color: str):
        """
        Update chart with diminishing returns curve.
        data_points: List of (stat_value, dps_gain_per_10pct) tuples
        """
        self.canvas.delete("all")

        if not data_points:
            return

        # Chart area
        chart_left = self.padding + 20
        chart_right = self.width - self.padding
        chart_top = self.padding
        chart_bottom = self.height - self.padding

        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top

        # Axis
        self.canvas.create_line(chart_left, chart_bottom, chart_right, chart_bottom, fill='#555')
        self.canvas.create_line(chart_left, chart_bottom, chart_left, chart_top, fill='#555')

        # Labels
        self.canvas.create_text(
            self.width // 2, self.height - 5,
            text=f"{stat_name} Value", fill='#888', font=('Segoe UI', 8)
        )
        self.canvas.create_text(
            10, self.height // 2,
            text="DPS\nGain", fill='#888', font=('Segoe UI', 8), justify=tk.CENTER
        )

        # Scale
        x_vals = [d[0] for d in data_points]
        y_vals = [d[1] for d in data_points]
        x_min, x_max = min(x_vals), max(x_vals)
        y_min, y_max = 0, max(y_vals) * 1.1

        def scale_x(val):
            return chart_left + (val - x_min) / (x_max - x_min) * chart_width if x_max != x_min else chart_left

        def scale_y(val):
            return chart_bottom - (val - y_min) / (y_max - y_min) * chart_height if y_max != y_min else chart_bottom

        # Draw curve
        points = []
        for x, y in data_points:
            points.append((scale_x(x), scale_y(y)))

        for i in range(len(points) - 1):
            self.canvas.create_line(
                points[i][0], points[i][1],
                points[i + 1][0], points[i + 1][1],
                fill=color, width=2
            )

        # Mark current position
        if x_min <= current_val <= x_max:
            # Find closest data point
            closest_idx = min(range(len(data_points)), key=lambda i: abs(data_points[i][0] - current_val))
            cx, cy = points[closest_idx]

            self.canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill='white', outline=color, width=2)
            self.canvas.create_text(cx, cy - 15, text="YOU", fill='white', font=('Segoe UI', 8, 'bold'))


# =============================================================================
# APP CLASS
# =============================================================================

class DamageCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MapleStory Idle - Damage Calculator")
        self.root.geometry("1250x800")
        self.root.configure(bg='#1a1a2e')

        # Store baseline for comparison
        self.baseline_damage = None

        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TScale', background='#1a1a2e')
        style.configure('TFrame', background='#1a1a2e')
        style.configure('TLabel', background='#1a1a2e', foreground='#eee')
        style.configure('TButton', background='#4a4a6a')

        # Main container with 3 columns
        main_frame = ttk.Frame(root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = tk.Label(main_frame, text="MapleStory Idle - Damage Calculator",
                         font=('Segoe UI', 16, 'bold'), bg='#1a1a2e', fg='#ffd700')
        title.pack(pady=(0, 10))

        # Create three columns
        columns_frame = ttk.Frame(main_frame)
        columns_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(columns_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        middle_frame = ttk.Frame(columns_frame)
        middle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_frame = ttk.Frame(columns_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Sliders storage
        self.sliders = {}
        self.value_labels = {}

        # === LEFT COLUMN: Main Stats ===
        self.create_section_header(left_frame, "Base Stats")

        self.create_slider(left_frame, "base_atk", "Base ATK",
                           0, 200000, 50000, resolution=1000)
        self.create_slider(left_frame, "dex_flat", "Flat DEX Pool",
                           0, 50000, 18700, resolution=100)
        self.create_slider(left_frame, "dex_percent", "DEX %",
                           0, 300, 126.5, resolution=0.5)

        self.create_section_header(left_frame, "Damage Multipliers")

        self.create_slider(left_frame, "damage_percent", "Damage %",
                           0, 1000, 484.1, resolution=1)
        self.create_slider(left_frame, "hex_stacks", "Hex Necklace Stacks",
                           0, 3, 3, resolution=1)
        self.create_slider(left_frame, "damage_amp", "Damage Amp %",
                           0, 100, 23.2, resolution=0.1)
        self.create_slider(left_frame, "boss_damage", "Boss Damage %",
                           0, 200, 64.5, resolution=0.5)

        # === MIDDLE COLUMN: More Stats ===
        self.create_section_header(middle_frame, "Final Damage Sources")

        self.create_slider(middle_frame, "fd_equipment", "Equipment FD %",
                           0, 50, 13, resolution=0.5)
        self.create_slider(middle_frame, "fd_guild", "Guild FD %",
                           0, 20, 10, resolution=0.5)
        self.create_slider(middle_frame, "fd_skill", "Skill FD % (Extreme Archery)",
                           0, 50, 21.7, resolution=0.1)
        self.create_slider(middle_frame, "fd_mortal", "Mortal Blow FD %",
                           0, 20, 0, resolution=0.1)
        self.create_slider(middle_frame, "fd_flower", "Fire Flower FD %",
                           0, 12, 0, resolution=0.1)

        self.create_section_header(middle_frame, "Critical & Defense")

        self.create_slider(middle_frame, "crit_damage", "Crit Damage %",
                           0, 400, 184.5, resolution=0.5)
        self.create_slider(middle_frame, "defense_pen", "Defense Pen %",
                           0, 100, 60.9, resolution=0.5)
        self.create_slider(middle_frame, "enemy_def", "Enemy Defense",
                           0, 10, 0.752, resolution=0.01)

        # === RIGHT COLUMN: Visualizations ===
        self.create_section_header(right_frame, "Which Stat to Upgrade Next?")

        self.priority_chart = BarChart(right_frame, width=400, height=180)

        self.create_section_header(right_frame, "Diminishing Returns Curve")

        # Stat selector for diminishing returns
        selector_frame = ttk.Frame(right_frame)
        selector_frame.pack(fill=tk.X, pady=5)

        tk.Label(selector_frame, text="Show curve for:", bg='#1a1a2e', fg='#aaa').pack(side=tk.LEFT)

        self.selected_stat = tk.StringVar(value="damage_percent")
        stats_for_curve = [
            ("Damage %", "damage_percent"),
            ("Final Damage", "final_damage"),
            ("Crit Damage", "crit_damage"),
            ("Boss Damage", "boss_damage"),
            ("Defense Pen", "defense_pen"),
        ]
        for label, value in stats_for_curve:
            rb = tk.Radiobutton(selector_frame, text=label, variable=self.selected_stat,
                                value=value, command=self.update_diminishing_chart,
                                bg='#1a1a2e', fg='#aaa', selectcolor='#3a3a5a',
                                activebackground='#1a1a2e', activeforeground='white')
            rb.pack(side=tk.LEFT, padx=3)

        self.diminishing_chart = DiminishingReturnsChart(right_frame, width=400, height=160)

        # Recommendation text
        self.recommendation_label = tk.Label(right_frame, text="",
                                              font=('Segoe UI', 10), bg='#1a1a2e', fg='#00ff88',
                                              wraplength=380, justify=tk.LEFT)
        self.recommendation_label.pack(pady=10)

        # === RESULTS SECTION ===
        results_frame = ttk.Frame(main_frame)
        results_frame.pack(fill=tk.X, pady=10)

        # Left side: damage display
        damage_frame = ttk.Frame(results_frame)
        damage_frame.pack(side=tk.LEFT, padx=20)

        self.damage_label = tk.Label(damage_frame, text="Total Damage: ---",
                                     font=('Segoe UI', 20, 'bold'),
                                     bg='#1a1a2e', fg='#00ff88')
        self.damage_label.pack()

        self.change_label = tk.Label(damage_frame, text="",
                                     font=('Segoe UI', 12),
                                     bg='#1a1a2e', fg='#888')
        self.change_label.pack()

        # Right side: breakdown
        self.breakdown_label = tk.Label(results_frame, text="",
                                        font=('Consolas', 9),
                                        bg='#1a1a2e', fg='#aaa',
                                        justify=tk.LEFT)
        self.breakdown_label.pack(side=tk.LEFT, padx=40)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=5)

        set_baseline_btn = tk.Button(button_frame, text="Set as Baseline",
                                     command=self.set_baseline,
                                     bg='#4a4a6a', fg='white',
                                     font=('Segoe UI', 10))
        set_baseline_btn.pack(side=tk.LEFT, padx=5)

        reset_btn = tk.Button(button_frame, text="Reset to Defaults",
                              command=self.reset_defaults,
                              bg='#4a4a6a', fg='white',
                              font=('Segoe UI', 10))
        reset_btn.pack(side=tk.LEFT, padx=5)

        # Enemy presets
        tk.Label(button_frame, text="Enemy:", bg='#1a1a2e', fg='#aaa').pack(side=tk.LEFT, padx=(20, 5))

        enemies = [
            ("Maple Island", 0.0),
            ("Aquarium 14", 0.388),
            ("Mu Lung 27", 0.752),
            ("World Boss", 6.527),
        ]
        for name, defense in enemies:
            btn = tk.Button(button_frame, text=name,
                            command=lambda d=defense: self.set_enemy_defense(d),
                            bg='#3a3a5a', fg='white', font=('Segoe UI', 9))
            btn.pack(side=tk.LEFT, padx=2)

        # Initial calculation
        self.update_damage()
        self.set_baseline()

    def create_section_header(self, parent, text):
        """Create a section header."""
        label = tk.Label(parent, text=text, font=('Segoe UI', 11, 'bold'),
                         bg='#1a1a2e', fg='#ffd700')
        label.pack(anchor=tk.W, pady=(10, 5))

    def create_slider(self, parent, key, label, min_val, max_val, default, resolution=1):
        """Create a labeled slider with value display."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)

        # Label
        lbl = tk.Label(frame, text=label, width=22, anchor=tk.W,
                       font=('Segoe UI', 9), bg='#1a1a2e', fg='#ccc')
        lbl.pack(side=tk.LEFT)

        # Value display
        value_var = tk.StringVar(value=str(default))
        value_lbl = tk.Label(frame, textvariable=value_var, width=10,
                             font=('Consolas', 9), bg='#1a1a2e', fg='#00ff88')
        value_lbl.pack(side=tk.RIGHT)

        # Slider
        slider = ttk.Scale(frame, from_=min_val, to=max_val,
                           orient=tk.HORIZONTAL, length=180,
                           command=lambda v, k=key, vv=value_var, r=resolution:
                           self.on_slider_change(k, v, vv, r))
        slider.set(default)
        slider.pack(side=tk.RIGHT, padx=5)

        self.sliders[key] = slider
        self.value_labels[key] = value_var

    def on_slider_change(self, key, value, value_var, resolution):
        """Handle slider change."""
        val = float(value)
        if resolution >= 1:
            val = int(round(val))
            value_var.set(f"{val:,}")
        else:
            val = round(val / resolution) * resolution
            value_var.set(f"{val:.1f}")
        self.update_damage()

    def get_slider_value(self, key):
        """Get current value of a slider."""
        return float(self.sliders[key].get())

    def get_current_stats(self) -> dict:
        """Get all current stat values."""
        return {
            "base_atk": self.get_slider_value("base_atk"),
            "dex_flat": self.get_slider_value("dex_flat"),
            "dex_percent": self.get_slider_value("dex_percent"),
            "damage_percent": self.get_slider_value("damage_percent"),
            "hex_stacks": int(self.get_slider_value("hex_stacks")),
            "damage_amp": self.get_slider_value("damage_amp"),
            "boss_damage": self.get_slider_value("boss_damage"),
            "fd_sources": [
                self.get_slider_value("fd_equipment"),
                self.get_slider_value("fd_guild"),
                self.get_slider_value("fd_skill"),
                self.get_slider_value("fd_mortal"),
                self.get_slider_value("fd_flower"),
            ],
            "crit_damage": self.get_slider_value("crit_damage"),
            "defense_pen": self.get_slider_value("defense_pen"),
            "enemy_def": self.get_slider_value("enemy_def"),
        }

    def calc_with_stats(self, stats: dict) -> float:
        """Calculate damage with given stats dict."""
        return calculate_damage(
            base_atk=stats["base_atk"],
            dex_flat=stats["dex_flat"],
            dex_percent=stats["dex_percent"],
            damage_percent=stats["damage_percent"],
            hex_stacks=stats["hex_stacks"],
            damage_amp=stats["damage_amp"],
            final_damage_sources=stats["fd_sources"],
            crit_damage=stats["crit_damage"],
            defense_pen=stats["defense_pen"],
            enemy_def=stats["enemy_def"],
            boss_damage=stats["boss_damage"],
        )["total"]

    def calculate_stat_priorities(self) -> List[Tuple[str, float, str]]:
        """Calculate DPS gain from +10% of each stat."""
        stats = self.get_current_stats()
        base_damage = self.calc_with_stats(stats)

        results = []
        increment = 10  # 10% increase

        # Test each stat
        tests = [
            ("Damage %", "damage_percent", "#4a9eff"),
            ("Final Damage", "fd_sources", "#ff6b6b"),
            ("Crit Damage", "crit_damage", "#ffd93d"),
            ("Boss Damage", "boss_damage", "#6bcb77"),
            ("Defense Pen", "defense_pen", "#9d65c9"),
        ]

        for label, key, color in tests:
            modified = dict(stats)
            modified["fd_sources"] = list(stats["fd_sources"])  # Copy list

            if key == "fd_sources":
                # Add to equipment FD slot
                modified["fd_sources"][0] += increment
            elif key == "defense_pen":
                # Defense pen is multiplicative, so we calculate differently
                current = modified[key]
                remaining = 100 - current
                # Adding 10% def pen multiplicatively
                new_remaining = remaining * (1 - increment / 100)
                modified[key] = 100 - new_remaining
            else:
                modified[key] += increment

            new_damage = self.calc_with_stats(modified)
            dps_gain = ((new_damage / base_damage) - 1) * 100
            results.append((label, dps_gain, color))

        return results

    def calculate_diminishing_returns(self, stat_key: str) -> Tuple[List[Tuple[float, float]], float, str]:
        """Calculate DPS gain curve for a stat."""
        stats = self.get_current_stats()
        increment = 10

        # Define ranges and current values
        config = {
            "damage_percent": (100, 1000, stats["damage_percent"], "#4a9eff", "Damage %"),
            "final_damage": (0, 150, sum(stats["fd_sources"]), "#ff6b6b", "Final Damage %"),
            "crit_damage": (50, 400, stats["crit_damage"], "#ffd93d", "Crit Damage %"),
            "boss_damage": (0, 200, stats["boss_damage"], "#6bcb77", "Boss Damage %"),
            "defense_pen": (0, 95, stats["defense_pen"], "#9d65c9", "Defense Pen %"),
        }

        min_val, max_val, current, color, name = config[stat_key]
        data_points = []

        # Sample points across the range
        step = (max_val - min_val) / 20
        test_val = min_val
        while test_val <= max_val:
            # Calculate damage at this value
            modified = dict(stats)
            modified["fd_sources"] = list(stats["fd_sources"])

            if stat_key == "final_damage":
                # Replace all FD sources with single value for simplicity
                total_current = sum(stats["fd_sources"])
                diff = test_val - total_current
                modified["fd_sources"] = [stats["fd_sources"][0] + diff] + [0, 0, 0, 0]
                before_stats = dict(modified)
                before_stats["fd_sources"] = [modified["fd_sources"][0] - increment] + [0, 0, 0, 0]
            else:
                modified[stat_key] = test_val
                before_stats = dict(modified)
                before_stats["fd_sources"] = list(modified["fd_sources"])
                if stat_key == "defense_pen":
                    remaining = 100 - test_val
                    before_remaining = remaining / (1 - increment / 100)
                    before_stats[stat_key] = 100 - before_remaining
                else:
                    before_stats[stat_key] = test_val - increment

            if before_stats.get(stat_key, before_stats.get("fd_sources", [0])[0]) >= min_val:
                dmg_before = self.calc_with_stats(before_stats)
                dmg_after = self.calc_with_stats(modified)
                dps_gain = ((dmg_after / dmg_before) - 1) * 100 if dmg_before > 0 else 0
                data_points.append((test_val, dps_gain))

            test_val += step

        return data_points, current, color, name

    def update_diminishing_chart(self):
        """Update the diminishing returns chart."""
        stat_key = self.selected_stat.get()
        data_points, current, color, name = self.calculate_diminishing_returns(stat_key)
        self.diminishing_chart.update(name, current, data_points, color)

    def update_damage(self):
        """Recalculate and display damage."""
        stats = self.get_current_stats()
        result = self.calc_with_stats(stats)
        full_result = calculate_damage(
            base_atk=stats["base_atk"],
            dex_flat=stats["dex_flat"],
            dex_percent=stats["dex_percent"],
            damage_percent=stats["damage_percent"],
            hex_stacks=stats["hex_stacks"],
            damage_amp=stats["damage_amp"],
            final_damage_sources=stats["fd_sources"],
            crit_damage=stats["crit_damage"],
            defense_pen=stats["defense_pen"],
            enemy_def=stats["enemy_def"],
            boss_damage=stats["boss_damage"],
        )

        # Update damage display
        self.damage_label.config(text=f"Total Damage: {result:,.0f}")

        # Update change from baseline
        if self.baseline_damage:
            change = ((result / self.baseline_damage) - 1) * 100
            if change >= 0:
                self.change_label.config(text=f"  +{change:.2f}% from baseline", fg='#00ff88')
            else:
                self.change_label.config(text=f"  {change:.2f}% from baseline", fg='#ff4444')
        else:
            self.change_label.config(text="")

        # Update breakdown
        breakdown = (
            f"Multipliers:\n"
            f"  Stat (DEX):   x{full_result['stat_mult']:.3f}\n"
            f"  Damage %:     x{full_result['damage_mult']:.3f}\n"
            f"  Damage Amp:   x{full_result['amp_mult']:.4f}\n"
            f"  Final Damage: x{full_result['fd_mult']:.3f}\n"
            f"  Crit Damage:  x{full_result['crit_mult']:.3f}\n"
            f"  vs Defense:   x{full_result['def_mult']:.4f}"
        )
        self.breakdown_label.config(text=breakdown)

        # Update priority chart
        priorities = self.calculate_stat_priorities()
        self.priority_chart.update(priorities)

        # Update diminishing returns chart
        self.update_diminishing_chart()

        # Update recommendation
        sorted_priorities = sorted(priorities, key=lambda x: x[1], reverse=True)
        best = sorted_priorities[0]
        second = sorted_priorities[1]
        gap = best[1] - second[1]

        if gap > 0.5:
            rec = f"Focus on {best[0]}! It gives {gap:.2f}% more DPS per investment than {second[0]}."
        else:
            rec = f"{best[0]} and {second[0]} are close in value. Either is a good investment."

        self.recommendation_label.config(text=rec)

    def set_baseline(self):
        """Set current damage as baseline for comparison."""
        stats = self.get_current_stats()
        self.baseline_damage = self.calc_with_stats(stats)
        self.change_label.config(text="Baseline set!", fg='#ffd700')

    def set_enemy_defense(self, defense):
        """Set enemy defense from preset."""
        self.sliders["enemy_def"].set(defense)
        self.value_labels["enemy_def"].set(f"{defense:.3f}")
        self.update_damage()

    def reset_defaults(self):
        """Reset all sliders to default values."""
        defaults = {
            "base_atk": 50000,
            "dex_flat": 18700,
            "dex_percent": 126.5,
            "damage_percent": 484.1,
            "hex_stacks": 3,
            "damage_amp": 23.2,
            "boss_damage": 64.5,
            "fd_equipment": 13,
            "fd_guild": 10,
            "fd_skill": 21.7,
            "fd_mortal": 0,
            "fd_flower": 0,
            "crit_damage": 184.5,
            "defense_pen": 60.9,
            "enemy_def": 0.752,
        }

        for key, value in defaults.items():
            self.sliders[key].set(value)

        self.update_damage()


# =============================================================================
# MAIN
# =============================================================================

def main():
    root = tk.Tk()
    app = DamageCalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
