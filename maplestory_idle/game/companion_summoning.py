"""
Companion Summoning System
==========================
Models the companion summon-ticket gacha and the auto-promotion of extras
from maxed companions. Used by the Upgrade Optimizer to score "next 100
tickets" against other diamond spends.

Mechanics (user-confirmed):
- Each ticket rolls a tier (Basic 75.21% / 1st 22% / 2nd 2.5% / 3rd 0.25% / 4th 0.04%).
- Within the rolled tier, each companion is equally likely.
- A duplicate of a NOT-YET-MAXED companion contributes 1 unit of level-up progress.
- A duplicate of a MAXED companion is an "extra" that independently rolls the
  tier's PROMOTION_RATES (Basic→1st 100%, 1st→2nd 50%, 2nd→3rd 30%, 3rd→4th 20%)
  to convert into a random pull at the tier above. The conversion is recursive
  — promoted pulls themselves may promote further.

The expected value per ticket is computed top-down: we start at the FOURTH tier
(no promotion target → ev_next = 0) and work down. Each tier's EV uses the
already-computed EV of the tier above for the maxed-companion branch.

See plan: C:/Users/ianpr/.claude/plans/sorted-nibbling-meteor.md
"""

from typing import Callable, Dict, List, Optional, Tuple

from game.companions import (
    COMPANIONS,
    CompanionDefinition,
    JobAdvancement,
    MAX_LEVELS,
)


# =============================================================================
# TICKET COST
# =============================================================================
# 30,000 diamonds for 850 tickets — user-provided.
DIAMONDS_PER_TICKET = 30_000 / 850   # ≈ 35.294


# =============================================================================
# PER-TICKET TIER ODDS
# =============================================================================
# User-provided: Basic 75.21% / 1st 22% / 2nd 2.5% / 3rd 0.25% / 4th 0.04%.
# Sum to 1.0 exactly.
TIER_RATES: Dict[JobAdvancement, float] = {
    JobAdvancement.BASIC:  0.7521,
    JobAdvancement.FIRST:  0.22,
    JobAdvancement.SECOND: 0.025,
    JobAdvancement.THIRD:  0.0025,
    JobAdvancement.FOURTH: 0.0004,
}


# =============================================================================
# PROMOTION RATES (auto-conversion of maxed-companion extras)
# =============================================================================
# Each extra of a maxed companion in this tier independently rolls this chance
# to become a random pull at the tier above. FOURTH has no entry — can't
# promote past 4th-job.
PROMOTION_RATES: Dict[JobAdvancement, float] = {
    JobAdvancement.BASIC:  1.00,
    JobAdvancement.FIRST:  0.50,
    JobAdvancement.SECOND: 0.30,
    JobAdvancement.THIRD:  0.20,
}


# Tier-above lookup. Used by the recursive solver.
_NEXT_TIER: Dict[JobAdvancement, Optional[JobAdvancement]] = {
    JobAdvancement.BASIC:  JobAdvancement.FIRST,
    JobAdvancement.FIRST:  JobAdvancement.SECOND,
    JobAdvancement.SECOND: JobAdvancement.THIRD,
    JobAdvancement.THIRD:  JobAdvancement.FOURTH,
    JobAdvancement.FOURTH: None,
}


# =============================================================================
# LEVEL-UP COSTS (duplicates per level)
# =============================================================================
# Sourced from data_mine/TextAsset/SupporterLevelUpCostTable.json. The table
# encodes a step function: `cost(L→L+1) = min(MaxRequireCount, BeginRequireCost
# + AddRequireCount × floor((L-1) / AddCountLevelGap))`.
#
# At module load we parse the datamine file and build a per-tier dict
# {advancement: {level → cost-to-next-level}}. If parsing fails (missing file)
# we fall back to hardcoded values derived from the same formula.

def _load_level_up_costs() -> Dict[JobAdvancement, Dict[int, int]]:
    """
    Parse SupporterLevelUpCostTable.json into a per-tier cost lookup.
    Each tier maps {level → duplicates required to reach level+1}.

    Levels at and above the tier's max level get cost 0 (already maxed).
    """
    # Grade1..Grade5 in the datamine == BASIC..FOURTH in JobAdvancement.
    _grade_to_advancement = {
        'Grade1': JobAdvancement.BASIC,
        'Grade2': JobAdvancement.FIRST,
        'Grade3': JobAdvancement.SECOND,
        'Grade4': JobAdvancement.THIRD,
        'Grade5': JobAdvancement.FOURTH,
    }

    try:
        import json
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, '..', 'data_mine', 'TextAsset',
                            'SupporterLevelUpCostTable.json')
        with open(path, 'r', encoding='utf-8') as fp:
            rows = json.load(fp)
    except (OSError, ValueError):
        # Fall back to a hardcoded table covering all five grades. Values
        # derived from the same datamine formula at the time the user
        # confirmed them.
        return {
            JobAdvancement.BASIC:  _build_cost_table(begin=5, gap=1, add=3, cap=500, max_level=100),
            JobAdvancement.FIRST:  _build_cost_table(begin=1, gap=1, add=2, cap=300, max_level=50),
            JobAdvancement.SECOND: _build_cost_table(begin=1, gap=1, add=1, cap=100, max_level=30),
            JobAdvancement.THIRD:  _build_cost_table(begin=1, gap=2, add=1, cap=100, max_level=10),
            JobAdvancement.FOURTH: _build_cost_table(begin=1, gap=3, add=1, cap=100, max_level=10),
        }

    table: Dict[JobAdvancement, Dict[int, int]] = {}
    for row in rows:
        grade = row.get('GradeType')
        adv = _grade_to_advancement.get(grade)
        if adv is None:
            continue
        try:
            begin = int(row['BeginRequireCost'])
            gap = max(1, int(row['AddCountLevelGap']))
            add = int(row['AddRequireCount'])
            cap = int(row['MaxRequireCount'])
            max_level = int(row['MaxLevel'])
        except (KeyError, ValueError):
            continue
        table[adv] = _build_cost_table(begin=begin, gap=gap, add=add,
                                       cap=cap, max_level=max_level)
    return table


def _build_cost_table(begin: int, gap: int, add: int, cap: int, max_level: int) -> Dict[int, int]:
    """
    `cost(L→L+1) = min(cap, begin + add × floor((L-1) / gap))` for L in [1, max_level).
    Returns {level: cost-to-advance-from-level}.
    """
    out: Dict[int, int] = {}
    for L in range(1, max_level):
        raw = begin + add * ((L - 1) // gap)
        out[L] = min(cap, raw)
    out[max_level] = 0   # already maxed — no further level-up needed
    return out


LEVEL_UP_COSTS: Dict[JobAdvancement, Dict[int, int]] = _load_level_up_costs()


# =============================================================================
# TIER → COMPANION LOOKUP
# =============================================================================

def companions_in_tier(advancement: JobAdvancement) -> List[str]:
    """Companion keys belonging to a given advancement tier, sorted for stability."""
    return sorted(k for k, c in COMPANIONS.items() if c.advancement == advancement)


def _max_level_for(advancement: JobAdvancement) -> int:
    return MAX_LEVELS.get(advancement, 10)


# =============================================================================
# PER-COMPANION MARGINAL VALUE
# =============================================================================
# A `marginal_dps_fn` callback computes the DPS impact of altering the user's
# companion state. Signature:
#     marginal_dps_fn(state_delta: Dict[str, int]) -> float
# where state_delta is {companion_key: new_level_or_progress}. The callback
# is responsible for translating that delta into a DPS gain vs. the baseline
# (typically via FastDPSEvaluator on the optimizer side).

UserState = Dict[str, Dict]
# {'owned': {key: level}, 'equipped': [key, ...]}


def _expected_gain_for_pull(
    companion_key: str,
    user_state: UserState,
    marginal_dps_fn: Callable[[Dict[str, int]], float],
    tier_ev_next: float,
) -> float:
    """
    Expected DPS gain (relative to baseline) when a ticket lands on
    `companion_key` for the current `user_state`. Three cases:

    1. Companion already MAXED → contributes `PROMOTION_RATES[tier] × tier_ev_next`
       (the extra rolls the promotion chance into a tier-above pull).
    2. Companion OWNED but not maxed → contributes the marginal DPS of
       advancing one more progress unit at the current level (1 / cost-to-next).
    3. NOT OWNED → contributes the marginal DPS of going from "not owned"
       (level 0) to level 1.
    """
    comp = COMPANIONS.get(companion_key)
    if comp is None:
        return 0.0
    owned_levels = user_state.get('owned', {})
    current_level = owned_levels.get(companion_key, 0)
    max_level = _max_level_for(comp.advancement)

    if current_level >= max_level:
        # Maxed — extras roll into tier-above promotion.
        return PROMOTION_RATES.get(comp.advancement, 0.0) * tier_ev_next

    if current_level == 0:
        # New companion: full delta from level 0 → 1.
        return marginal_dps_fn({companion_key: 1})

    # In-progress: one duplicate is 1 unit of level-up progress. The
    # marginal DPS we credit is "what would I gain by getting one more
    # level" divided by "how many duplicates that level costs". Splitting
    # over cost converts "DPS per level" into "DPS per pull".
    cost_table = LEVEL_UP_COSTS.get(comp.advancement, {})
    cost = cost_table.get(current_level, 1) or 1   # safety: cap at 1
    per_level_gain = (
        marginal_dps_fn({companion_key: current_level + 1})
        - marginal_dps_fn({companion_key: current_level})
    )
    return per_level_gain / cost


def calculate_ev_per_pull_at_tier(
    tier: JobAdvancement,
    user_state: UserState,
    marginal_dps_fn: Callable[[Dict[str, int]], float],
    tier_ev_next: float,
) -> float:
    """
    Expected DPS gain from a single pull that lands on `tier`. Averages
    over every companion in the tier with uniform weight.

    `tier_ev_next` is the already-computed EV for the tier above (used by
    the maxed-companion branch). For FOURTH this is 0.
    """
    keys = companions_in_tier(tier)
    if not keys:
        return 0.0
    total = 0.0
    for key in keys:
        total += _expected_gain_for_pull(key, user_state, marginal_dps_fn, tier_ev_next)
    return total / len(keys)


def calculate_expected_value_per_ticket(
    user_state: UserState,
    marginal_dps_fn: Callable[[Dict[str, int]], float],
) -> Dict:
    """
    Top-down EV solve: FOURTH → THIRD → SECOND → FIRST → BASIC.

    Returns a dict with the expected value per ticket and a per-tier
    breakdown for diagnostics.
    """
    tier_order = [
        JobAdvancement.FOURTH,
        JobAdvancement.THIRD,
        JobAdvancement.SECOND,
        JobAdvancement.FIRST,
        JobAdvancement.BASIC,
    ]
    per_tier_ev: Dict[JobAdvancement, float] = {}
    for tier in tier_order:
        next_tier = _NEXT_TIER.get(tier)
        ev_next = per_tier_ev.get(next_tier, 0.0) if next_tier else 0.0
        per_tier_ev[tier] = calculate_ev_per_pull_at_tier(
            tier, user_state, marginal_dps_fn, ev_next,
        )

    # Expected ticket value = sum of P(tier) × EV(tier).
    ev = sum(
        TIER_RATES[tier] * per_tier_ev[tier]
        for tier in tier_order
    )

    # Top contributors for the description string. The total contribution
    # from a tier = TIER_RATES[tier] × EV(tier) — the share of expected
    # gain that comes from rolling that tier.
    contributors = sorted(
        (
            {
                'tier': tier.name,
                'contribution': TIER_RATES[tier] * per_tier_ev[tier],
                'per_pull_ev': per_tier_ev[tier],
            }
            for tier in tier_order
        ),
        key=lambda d: -d['contribution'],
    )

    return {
        'expected_value': ev,
        'cost_per_ticket': DIAMONDS_PER_TICKET,
        'breakdown': {tier.name: per_tier_ev[tier] for tier in tier_order},
        'top_contributors': contributors,
    }


# =============================================================================
# OPTIMIZER-FACING WRAPPER
# =============================================================================

def get_companion_ticket_recommendation_for_optimizer(
    user_state: UserState,
    marginal_dps_fn: Callable[[Dict[str, int]], float],
    baseline_dps: float,
    batch_size: int = 100,
) -> Optional[Dict]:
    """
    Build a single optimizer-recommendation dict for a batch of `batch_size`
    summon tickets. Mirrors the weapon-summoning equivalent so the existing
    'Summon' UI block in 13_Upgrade_Optimizer.py renders it as-is.

    `baseline_dps` is needed to convert per-pull marginal DPS into a
    percentage gain (matching how every other recommendation reports gains).
    """
    ev = calculate_expected_value_per_ticket(user_state, marginal_dps_fn)
    if ev['expected_value'] <= 0 or baseline_dps <= 0:
        return None

    batch_abs_dps = ev['expected_value'] * batch_size
    batch_cost = ev['cost_per_ticket'] * batch_size
    # Convert absolute DPS gain → percentage of current baseline DPS, matching
    # the convention used by the rest of the optimizer recommendations.
    batch_dps_pct = (batch_abs_dps / baseline_dps) * 100.0

    top = ev['top_contributors'][:2]
    top_label = ", ".join(c['tier'].title() for c in top if c['contribution'] > 0) \
                or "various tiers"

    return {
        'type': 'Summon',
        'subtype': 'companion_ticket',
        'target': 'companion_ticket',
        'target_display': f'🐾 Companion Summons (x{batch_size})',
        'description': f"🐾 {batch_size} Companion Tickets (top: {top_label})",
        'cost': batch_cost,
        'dps_gain': batch_dps_pct,
        'efficiency': (batch_dps_pct / (batch_cost / 1000.0)) if batch_cost > 0 else 0.0,
        'details': {
            'batch_size': batch_size,
            'cost_per_ticket': ev['cost_per_ticket'],
            'expected_value_per_ticket_dps': ev['expected_value'],
            'breakdown_per_tier_dps': ev['breakdown'],
            'top_contributors': ev['top_contributors'],
        },
    }
