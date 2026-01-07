"""
DPS Distribution Chart Component

Creates interactive Plotly charts showing the distribution of possible DPS gains
from cube rolls, with hover tooltips showing the actual potential lines at each
percentile.

Focuses on the IMPROVEMENT ZONE - the right side of the distribution where
rolls are better than the player's current roll.
"""

import plotly.graph_objects as go
from typing import Dict, Optional, List


def create_dps_distribution_chart(
    distribution_data: Dict,
    current_dps_gain: float,
    slot_name: str,
    is_bonus: bool,
    height: int = 300,
) -> go.Figure:
    """
    Create interactive Plotly chart focused on improvement opportunities.

    The chart emphasizes:
    - The "improvement zone" (rolls better than current)
    - Key percentile markers (p75, p90, p95, max)
    - Probability of improvement

    Args:
        distribution_data: Dict from ExactRollDistribution.get_distribution_data_for_chart()
            - percentiles: List[int] (0-100)
            - dps_gains: List[float] (DPS % at each percentile)
            - lines_text: List[str] (formatted lines text for hover)
        current_dps_gain: The current roll's DPS gain % for marking on chart
        slot_name: Equipment slot name for title
        is_bonus: Whether this is bonus potential

    Returns:
        Plotly Figure object ready for display with st.plotly_chart()
    """
    percentiles = distribution_data["percentiles"]
    dps_gains = distribution_data["dps_gains"]
    lines_text = distribution_data["lines_text"]

    pot_type = "Bonus" if is_bonus else "Regular"

    # Find current roll's percentile position
    current_percentile = 0
    for i, dps in enumerate(dps_gains):
        if dps >= current_dps_gain:
            current_percentile = percentiles[i]
            break
    else:
        current_percentile = 100  # Current is at max

    # Calculate improvement probability
    improvement_prob = max(0, 100 - current_percentile)

    # Create custom hover text
    hover_texts = []
    for i, (pct, dps, lines) in enumerate(zip(percentiles, dps_gains, lines_text)):
        improvement = dps - current_dps_gain
        improvement_text = f"+{improvement:.2f}% vs current" if improvement > 0 else "Below current"
        hover_texts.append(
            f"<b>{pct}th Percentile</b><br>"
            f"DPS Gain: <b>+{dps:.2f}%</b><br>"
            f"<span style='color: {'#4caf50' if improvement > 0 else '#888'}'>{improvement_text}</span><br>"
            f"<br>"
            f"{lines}"
        )

    # Create figure
    fig = go.Figure()

    # Split the distribution into "below current" (grey) and "improvement zone" (green)
    below_x, below_y, below_hover = [], [], []
    above_x, above_y, above_hover = [], [], []

    for i, (pct, dps, hover) in enumerate(zip(percentiles, dps_gains, hover_texts)):
        if dps <= current_dps_gain:
            below_x.append(pct)
            below_y.append(dps)
            below_hover.append(hover)
        else:
            # Add transition point
            if not above_x and below_x:
                above_x.append(pct)
                above_y.append(current_dps_gain)  # Start from current level
                above_hover.append(hover)
            above_x.append(pct)
            above_y.append(dps)
            above_hover.append(hover)

    # Add "below current" trace (muted)
    if below_x:
        fig.add_trace(go.Scatter(
            x=below_x,
            y=below_y,
            mode='lines',
            fill='tozeroy',
            fillcolor='rgba(128, 128, 128, 0.15)',  # Grey, very transparent
            line=dict(color='rgba(128, 128, 128, 0.4)', width=1),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=below_hover,
            name='Below Current',
            showlegend=False,
        ))

    # Add "improvement zone" trace (highlighted green)
    if above_x:
        fig.add_trace(go.Scatter(
            x=above_x,
            y=above_y,
            mode='lines',
            fill='tozeroy',
            fillcolor='rgba(76, 175, 80, 0.3)',  # Green
            line=dict(color='rgba(76, 175, 80, 0.9)', width=2),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=above_hover,
            name='Improvement Zone',
            showlegend=False,
        ))

    # Add horizontal line for current roll
    fig.add_hline(
        y=current_dps_gain,
        line_dash="dash",
        line_color="#ff6b6b",
        line_width=2,
        annotation_text=f"Current: +{current_dps_gain:.2f}% (P{current_percentile})",
        annotation_position="left",
        annotation_font_color="#ff6b6b",
        annotation_font_size=11,
    )

    # Add key percentile markers on the RIGHT side (improvements)
    # For very high rolls (P90+), only show P99+ to avoid clutter
    if current_percentile >= 90:
        # Very high roll - only show 99 and 100 (the realistic targets)
        key_percentiles = [99, 100]
    elif current_percentile >= 75:
        # Good roll - show 90, 95, 100
        key_percentiles = [90, 95, 100]
    else:
        # Normal roll - show standard markers
        key_percentiles = [75, 90, 100]

    # Stagger annotation positions to avoid overlap
    annotation_offsets = [
        (30, -25),   # First marker
        (-30, -40),  # Second marker (opposite side, higher)
        (25, -55),   # Third marker (back to right, even higher)
    ]

    marker_idx = 0
    for p in key_percentiles:
        if p <= current_percentile:
            continue  # Skip percentiles below current

        # Find the DPS at this percentile (handle float percentiles)
        dps_at_p = None
        for i, pct in enumerate(percentiles):
            if pct >= p:
                dps_at_p = dps_gains[i]
                break
        if dps_at_p is None:
            dps_at_p = dps_gains[-1]

        # Calculate expected cubes to reach this percentile
        # Probability of rolling >= p percentile = (100 - p) / 100
        prob_to_reach = (100 - p) / 100
        if prob_to_reach > 0:
            expected_cubes = 1 / prob_to_reach
            cubes_text = f" (~{expected_cubes:.0f} cubes)"
        else:
            cubes_text = ""

        if p == 100:
            label = f"Best: +{dps_at_p:.1f}%{cubes_text}"
            color = "#ffd700"  # Gold
        elif p >= 99:
            label = f"P{p}: +{dps_at_p:.1f}%{cubes_text}"
            color = "#9370db"  # Purple for very rare
        else:
            label = f"P{p}: +{dps_at_p:.1f}%{cubes_text}"
            color = "rgba(76, 175, 80, 0.9)"

        # Get staggered offset
        ax, ay = annotation_offsets[marker_idx % len(annotation_offsets)]
        marker_idx += 1

        fig.add_annotation(
            x=p,
            y=dps_at_p,
            text=label,
            showarrow=True,
            arrowhead=2,
            arrowsize=0.8,
            arrowcolor=color,
            font=dict(size=10, color=color),
            ax=ax,
            ay=ay,
        )

    # Update layout - focus on the right side with tight zoom for high percentiles
    if current_percentile >= 98:
        # Very high percentile: zoom tight into P98-100
        x_min = 98
    elif current_percentile >= 95:
        # High percentile: zoom into P95-100
        x_min = 95
    elif current_percentile >= 90:
        # High percentile: zoom into P90-100
        x_min = 90
    elif current_percentile >= 75:
        # Good roll: show P70-100
        x_min = 70
    else:
        # Normal: show from current - 10
        x_min = max(0, current_percentile - 10)

    # Calculate expected cubes to improve (1 / prob_improve)
    if improvement_prob > 0:
        expected_cubes = 100 / improvement_prob
        improve_text = f"{improvement_prob:.0f}% to improve (~{expected_cubes:.0f} cubes)"
    else:
        improve_text = "At max roll!"

    # Choose tick values based on zoom level
    if x_min >= 98:
        # Ultra-zoomed: show 98, 99, 99.5, 100
        tick_vals = [98, 99, 99.5, 100]
    elif x_min >= 95:
        # Very zoomed: show 95, 97, 99, 100
        tick_vals = [95, 97, 99, 100]
    elif x_min >= 90:
        # Zoomed: show 90, 95, 99, 100
        tick_vals = [90, 95, 99, 100]
    else:
        # Normal view
        tick_vals = [x for x in [0, 25, 50, 75, 90, 100] if x >= x_min]

    fig.update_layout(
        title=dict(
            text=f"{slot_name.title()} - {pot_type} | {improve_text}",
            font=dict(size=14),
        ),
        xaxis=dict(
            title="Percentile",
            range=[x_min, 100.1],  # Slight padding to show P100 label
            tickvals=tick_vals,
            gridcolor='rgba(128, 128, 128, 0.2)',
        ),
        yaxis=dict(
            title="DPS Gain %",
            gridcolor='rgba(128, 128, 128, 0.2)',
        ),
        height=height,
        margin=dict(l=50, r=30, t=40, b=40),  # Tighter margins
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        showlegend=False,
    )

    return fig


def create_compact_distribution_chart(
    distribution_data: Dict,
    current_dps_gain: float,
    slot_name: str,
    is_bonus: bool,
) -> go.Figure:
    """
    Create a more compact version of the distribution chart for inline display.

    Focused on the improvement zone with minimal annotations.
    """
    fig = create_dps_distribution_chart(
        distribution_data=distribution_data,
        current_dps_gain=current_dps_gain,
        slot_name=slot_name,
        is_bonus=is_bonus,
        height=180,
    )

    # Find current percentile for x-axis range
    percentiles = distribution_data["percentiles"]
    dps_gains = distribution_data["dps_gains"]
    current_percentile = 0
    for i, dps in enumerate(dps_gains):
        if dps >= current_dps_gain:
            current_percentile = percentiles[i]
            break

    x_min = max(0, current_percentile - 10)

    # Simplify for compact view - remove annotations, smaller margins
    fig.update_layout(
        title=None,
        margin=dict(l=35, r=10, t=5, b=30),
        xaxis=dict(
            title=None,
            range=[x_min, 100],
            tickvals=[x for x in [50, 75, 100] if x >= x_min],
            tickfont=dict(size=9),
        ),
        yaxis=dict(
            title=None,
            tickfont=dict(size=9),
        ),
        annotations=[],  # Remove all annotations for compact view
    )

    return fig


def create_expanded_distribution_chart(
    distribution_data: Dict,
    current_dps_gain: float,
    slot_name: str,
    is_bonus: bool,
) -> go.Figure:
    """
    Create a larger version of the distribution chart for modal/expanded view.

    Shows more detail and larger annotations for better readability.
    """
    fig = create_dps_distribution_chart(
        distribution_data=distribution_data,
        current_dps_gain=current_dps_gain,
        slot_name=slot_name,
        is_bonus=is_bonus,
        height=400,  # Taller for expanded view
    )

    # Increase font sizes for better readability in expanded view
    fig.update_layout(
        title=dict(font=dict(size=16)),
        margin=dict(l=55, r=35, t=50, b=45),
        xaxis=dict(
            title=dict(font=dict(size=13)),
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title=dict(font=dict(size=13)),
            tickfont=dict(size=12),
        ),
    )

    # Update annotation font sizes
    for annotation in fig.layout.annotations:
        if annotation.font:
            annotation.font.size = 12

    return fig


def get_percentile_breakdown_data(
    distribution_data: Dict,
    current_dps_gain: float,
) -> List[Dict]:
    """
    Get a breakdown of key percentiles with expected cubes for display in a table.

    Returns list of dicts with: percentile, dps_gain, improvement, expected_cubes, prob
    """
    percentiles = distribution_data["percentiles"]
    dps_gains = distribution_data["dps_gains"]
    lines_text = distribution_data["lines_text"]

    # Find current percentile
    current_percentile = 0
    for i, dps in enumerate(dps_gains):
        if dps >= current_dps_gain:
            current_percentile = percentiles[i]
            break
    else:
        current_percentile = 100

    # Key percentiles to show in the breakdown
    target_percentiles = [50, 75, 90, 95, 99, 99.5, 99.9, 100]

    results = []
    for target_p in target_percentiles:
        if target_p <= current_percentile:
            continue  # Skip percentiles at or below current

        # Find the DPS and lines at this percentile
        dps_at_p = None
        lines_at_p = ""
        for i, pct in enumerate(percentiles):
            if pct >= target_p:
                dps_at_p = dps_gains[i]
                lines_at_p = lines_text[i] if i < len(lines_text) else ""
                break

        if dps_at_p is None:
            dps_at_p = dps_gains[-1]
            lines_at_p = lines_text[-1] if lines_text else ""

        # Calculate probability and expected cubes
        prob_to_reach = (100 - target_p) / 100
        if prob_to_reach > 0:
            expected_cubes = 1 / prob_to_reach
        else:
            expected_cubes = float('inf')

        improvement = dps_at_p - current_dps_gain

        results.append({
            'percentile': target_p,
            'dps_gain': dps_at_p,
            'improvement': improvement,
            'prob_pct': prob_to_reach * 100,
            'expected_cubes': expected_cubes,
            'lines': lines_at_p,
        })

    return results


def get_percentile_color(percentile: float) -> str:
    """Get a color based on percentile quality tier."""
    if percentile < 25:
        return "#ff6b6b"  # Red - unlucky
    elif percentile < 75:
        return "#ffc107"  # Yellow - typical
    else:
        return "#4caf50"  # Green - lucky


def get_percentile_label(percentile: float) -> str:
    """Get a text label for percentile quality tier."""
    if percentile < 10:
        return "Very Unlucky"
    elif percentile < 25:
        return "Unlucky"
    elif percentile < 40:
        return "Below Average"
    elif percentile < 60:
        return "Average"
    elif percentile < 75:
        return "Above Average"
    elif percentile < 90:
        return "Lucky"
    else:
        return "Very Lucky"
