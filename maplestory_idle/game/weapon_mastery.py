"""
Weapon Mastery milestone rewards data.

Players earn permanent stat rewards by reaching total awakening stages
across all weapons of each rarity tier.
"""

from typing import Dict, List, NamedTuple


class MasteryReward(NamedTuple):
    """Single milestone reward."""
    stage: int
    attack: int = 0
    main_stat: int = 0
    accuracy: int = 0
    min_dmg_mult: float = 0.0  # percentage
    max_dmg_mult: float = 0.0  # percentage


# Rewards by rarity - list of milestone rewards
WEAPON_MASTERY_REWARDS: Dict[str, List[MasteryReward]] = {
    'rare': [
        MasteryReward(stage=5, attack=20),
        MasteryReward(stage=20, main_stat=30),
    ],
    'epic': [
        MasteryReward(stage=3, attack=40),
        MasteryReward(stage=9, attack=70),
        MasteryReward(stage=12, attack=100),
        MasteryReward(stage=18, attack=150),
        MasteryReward(stage=20, main_stat=150),
    ],
    'unique': [
        MasteryReward(stage=3, attack=150),
        MasteryReward(stage=9, attack=200),
        MasteryReward(stage=12, attack=250),
        MasteryReward(stage=18, attack=300),
        MasteryReward(stage=20, main_stat=300),
    ],
    'legendary': [
        MasteryReward(stage=2, main_stat=100),
        MasteryReward(stage=8, accuracy=3),
        MasteryReward(stage=11, main_stat=150),
        MasteryReward(stage=16, accuracy=5),
        MasteryReward(stage=18, main_stat=300),
        MasteryReward(stage=20, main_stat=500),
    ],
    'mystic': [
        MasteryReward(stage=2, main_stat=200),
        MasteryReward(stage=5, accuracy=5),
        MasteryReward(stage=8, main_stat=250),
        MasteryReward(stage=11, main_stat=300),
        MasteryReward(stage=14, main_stat=400),
        MasteryReward(stage=16, main_stat=500),
        MasteryReward(stage=18, accuracy=7),
        MasteryReward(stage=20, main_stat=1000),
    ],
    'ancient': [
        MasteryReward(stage=1, attack=3000),
        MasteryReward(stage=3, attack=3500),
        MasteryReward(stage=5, attack=4000),
        MasteryReward(stage=7, min_dmg_mult=10.0),
        MasteryReward(stage=9, main_stat=400),
        MasteryReward(stage=11, main_stat=450),
        MasteryReward(stage=13, main_stat=500),
        MasteryReward(stage=15, max_dmg_mult=15.0),
    ],
}

# Predefined weapon list: (rarity, tier) combinations
# 27 total weapons (7 rarities × 4 tiers, minus Ancient T1 which doesn't exist)
ALL_WEAPONS: List[tuple] = []
RARITIES = ['normal', 'rare', 'epic', 'unique', 'legendary', 'mystic', 'ancient']
for rarity in RARITIES:
    for tier in [1, 2, 3, 4]:
        # Ancient T1 doesn't exist
        if rarity == 'ancient' and tier == 1:
            continue
        ALL_WEAPONS.append((rarity, tier))


def calculate_mastery_stages_from_weapons(weapons_data: Dict[str, Dict]) -> Dict[str, int]:
    """
    Calculate total awakening stages per rarity from weapon data.

    Args:
        weapons_data: Dict mapping "rarity_tier" -> {level, awakening}
                     e.g., {"mystic_1": {"level": 100, "awakening": 5}}

    Returns:
        Dict mapping rarity -> total awakening stages
        e.g., {"mystic": 15, "legendary": 8}
    """
    stages: Dict[str, int] = {}
    for key, data in weapons_data.items():
        parts = key.rsplit('_', 1)
        if len(parts) == 2:
            rarity = parts[0]
            awakening = data.get('awakening', 0)
            stages[rarity] = stages.get(rarity, 0) + awakening
    return stages


def calculate_mastery_stats(mastery_stages: Dict[str, int]) -> Dict[str, float]:
    """
    Calculate total stats from weapon mastery milestones.

    Args:
        mastery_stages: Dict mapping rarity -> current total awakening stage

    Returns:
        Dict with total stats: attack, main_stat, accuracy, min_dmg_mult, max_dmg_mult
    """
    totals = {
        'attack': 0,
        'main_stat': 0,
        'accuracy': 0,
        'min_dmg_mult': 0.0,
        'max_dmg_mult': 0.0,
    }

    for rarity, current_stage in mastery_stages.items():
        rarity_lower = rarity.lower()
        if rarity_lower not in WEAPON_MASTERY_REWARDS:
            continue

        for reward in WEAPON_MASTERY_REWARDS[rarity_lower]:
            if current_stage >= reward.stage:
                totals['attack'] += reward.attack
                totals['main_stat'] += reward.main_stat
                totals['accuracy'] += reward.accuracy
                totals['min_dmg_mult'] += reward.min_dmg_mult
                totals['max_dmg_mult'] += reward.max_dmg_mult

    return totals
