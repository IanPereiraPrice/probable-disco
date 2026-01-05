"""
Data manager for loading and saving user data to CSV files.
Each user has a single CSV file with all their character data.
"""
import os
import csv
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

# Path to user data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
USERS_DATA_DIR = os.path.join(DATA_DIR, "users")

# Equipment slots
EQUIPMENT_SLOTS = [
    "hat", "top", "bottom", "gloves", "shoes",
    "belt", "shoulder", "cape", "ring", "necklace", "face"
]


@dataclass
class UserData:
    """Complete user data structure."""
    # Character info
    username: str = ""
    character_level: int = 100
    all_skills: int = 44
    combat_mode: str = "stage"
    chapter: str = "Chapter 27"

    # Equipment items (slot -> {stars, tier, name, rarity, ...})
    equipment_items: Dict[str, Dict] = field(default_factory=dict)

    # Equipment potentials (slot -> {line1_stat, line1_value, ...})
    equipment_potentials: Dict[str, Dict] = field(default_factory=dict)

    # Hero Power lines (line1 -> {stat, value, tier, locked}, ...)
    hero_power_lines: Dict[str, Dict] = field(default_factory=dict)

    # Hero Power passives (stat_type -> level)
    hero_power_passives: Dict[str, int] = field(default_factory=dict)

    # Hero Power level config
    hero_power_level: Dict[str, Any] = field(default_factory=dict)

    # Artifacts (slot -> {name, stars, potentials...})
    artifacts_equipped: Dict[str, Dict] = field(default_factory=dict)
    artifacts_inventory: Dict[str, Dict] = field(default_factory=dict)
    artifacts_resonance: Dict[str, Any] = field(default_factory=dict)

    # Weapons (weapon_id -> {name, atk_pct})
    weapons: Dict[str, Dict] = field(default_factory=dict)

    # Companions (slot -> {name, level})
    companions_equipped: Dict[str, Dict] = field(default_factory=dict)
    companions_inventory: Dict[str, Dict] = field(default_factory=dict)

    # Maple Rank
    maple_rank: Dict[str, Any] = field(default_factory=dict)

    # Equipment Sets (medals, costumes)
    equipment_sets: Dict[str, int] = field(default_factory=dict)

    # Manual adjustments
    manual_adjustments: Dict[str, float] = field(default_factory=dict)


def _get_user_file(username: str) -> str:
    """Get path to user's data file."""
    os.makedirs(USERS_DATA_DIR, exist_ok=True)
    return os.path.join(USERS_DATA_DIR, f"{username.lower()}_data.csv")


def user_has_data(username: str) -> bool:
    """Check if user has saved data."""
    return os.path.exists(_get_user_file(username))


def save_user_data(username: str, data: UserData) -> bool:
    """
    Save user data to CSV.
    Format: section,key,subkey,value
    """
    filepath = _get_user_file(username)

    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['section', 'key', 'subkey', 'value'])

            # Character info
            writer.writerow(['character', 'level', '', str(data.character_level)])
            writer.writerow(['character', 'all_skills', '', str(data.all_skills)])
            writer.writerow(['character', 'combat_mode', '', data.combat_mode])
            writer.writerow(['character', 'chapter', '', data.chapter])

            # Equipment items
            for slot, item in data.equipment_items.items():
                for key, value in item.items():
                    writer.writerow(['equipment', slot, key, str(value)])

            # Equipment potentials
            for slot, pots in data.equipment_potentials.items():
                for key, value in pots.items():
                    writer.writerow(['potential', slot, key, str(value)])

            # Hero Power lines
            for line_id, line_data in data.hero_power_lines.items():
                for key, value in line_data.items():
                    writer.writerow(['hero_power_line', line_id, key, str(value)])

            # Hero Power passives
            for stat_type, level in data.hero_power_passives.items():
                writer.writerow(['hero_power_passive', stat_type, '', str(level)])

            # Hero Power level config
            for key, value in data.hero_power_level.items():
                writer.writerow(['hero_power_level', key, '', str(value)])

            # Artifacts equipped
            for slot, artifact in data.artifacts_equipped.items():
                for key, value in artifact.items():
                    writer.writerow(['artifact_equipped', slot, key, str(value)])

            # Artifacts inventory
            for artifact_id, artifact in data.artifacts_inventory.items():
                for key, value in artifact.items():
                    writer.writerow(['artifact_inventory', artifact_id, key, str(value)])

            # Artifacts resonance
            for key, value in data.artifacts_resonance.items():
                writer.writerow(['artifact_resonance', key, '', str(value)])

            # Weapons
            for weapon_id, weapon in data.weapons.items():
                for key, value in weapon.items():
                    writer.writerow(['weapon', weapon_id, key, str(value)])

            # Companions equipped
            for slot, companion in data.companions_equipped.items():
                for key, value in companion.items():
                    writer.writerow(['companion_equipped', slot, key, str(value)])

            # Companions inventory
            for comp_id, companion in data.companions_inventory.items():
                for key, value in companion.items():
                    writer.writerow(['companion_inventory', comp_id, key, str(value)])

            # Maple Rank - handle nested stat_levels dict
            for key, value in data.maple_rank.items():
                if key == 'stat_levels' and isinstance(value, dict):
                    # Save each stat level as a separate row
                    for stat_key, stat_value in value.items():
                        writer.writerow(['maple_rank_stat', stat_key, '', str(stat_value)])
                else:
                    writer.writerow(['maple_rank', key, '', str(value)])

            # Equipment Sets
            for key, value in data.equipment_sets.items():
                writer.writerow(['equipment_sets', key, '', str(value)])

            # Manual adjustments
            for stat, value in data.manual_adjustments.items():
                writer.writerow(['manual_adj', stat, '', str(value)])

        return True
    except Exception as e:
        print(f"Error saving user data: {e}")
        return False


def load_user_data(username: str) -> UserData:
    """
    Load user data from CSV.
    Returns default UserData if file doesn't exist.
    """
    data = UserData(username=username)
    filepath = _get_user_file(username)

    if not os.path.exists(filepath):
        # Initialize with defaults
        _init_default_data(data)
        return data

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                section = row['section']
                key = row['key']
                subkey = row.get('subkey', '')
                value = row['value']

                if section == 'character':
                    if key == 'level':
                        data.character_level = int(value)
                    elif key == 'all_skills':
                        data.all_skills = int(value)
                    elif key == 'combat_mode':
                        data.combat_mode = value
                    elif key == 'chapter':
                        data.chapter = value

                elif section == 'equipment':
                    if key not in data.equipment_items:
                        data.equipment_items[key] = {}
                    data.equipment_items[key][subkey] = _parse_value(value)

                elif section == 'potential':
                    if key not in data.equipment_potentials:
                        data.equipment_potentials[key] = {}
                    data.equipment_potentials[key][subkey] = _parse_value(value)

                elif section == 'hero_power_line':
                    if key not in data.hero_power_lines:
                        data.hero_power_lines[key] = {}
                    data.hero_power_lines[key][subkey] = _parse_value(value)

                elif section == 'hero_power_passive':
                    data.hero_power_passives[key] = int(value)

                elif section == 'hero_power_level':
                    data.hero_power_level[key] = _parse_value(value)

                elif section == 'artifact_equipped':
                    if key not in data.artifacts_equipped:
                        data.artifacts_equipped[key] = {}
                    data.artifacts_equipped[key][subkey] = _parse_value(value)

                elif section == 'artifact_inventory':
                    if key not in data.artifacts_inventory:
                        data.artifacts_inventory[key] = {}
                    data.artifacts_inventory[key][subkey] = _parse_value(value)

                elif section == 'artifact_resonance':
                    data.artifacts_resonance[key] = _parse_value(value)

                elif section == 'weapon':
                    if key not in data.weapons:
                        data.weapons[key] = {}
                    data.weapons[key][subkey] = _parse_value(value)

                elif section == 'companion_equipped':
                    if key not in data.companions_equipped:
                        data.companions_equipped[key] = {}
                    data.companions_equipped[key][subkey] = _parse_value(value)

                elif section == 'companion_inventory':
                    if key not in data.companions_inventory:
                        data.companions_inventory[key] = {}
                    data.companions_inventory[key][subkey] = _parse_value(value)

                elif section == 'maple_rank':
                    # Skip stat_levels if saved as string (legacy format)
                    if key == 'stat_levels':
                        continue
                    data.maple_rank[key] = _parse_value(value)

                elif section == 'maple_rank_stat':
                    # Nested stat levels for Maple Rank
                    if 'stat_levels' not in data.maple_rank:
                        data.maple_rank['stat_levels'] = {}
                    data.maple_rank['stat_levels'][key] = int(value)

                elif section == 'equipment_sets':
                    data.equipment_sets[key] = int(value)

                elif section == 'manual_adj':
                    data.manual_adjustments[key] = float(value)

    except Exception as e:
        print(f"Error loading user data: {e}")
        _init_default_data(data)

    return data


def _parse_value(value: str) -> Any:
    """Parse a string value to appropriate type."""
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _init_default_data(data: UserData):
    """Initialize data with default values."""
    # Default equipment items
    for slot in EQUIPMENT_SLOTS:
        data.equipment_items[slot] = {
            'name': slot.title(),
            'rarity': 'Normal',
            'tier': 1,
            'stars': 0,
            'is_special': False,
            # Main Stats (Main Amplify)
            'base_attack': 0,
            'base_max_hp': 0,
            'base_third_stat': 0,
            # Sub Stats (Sub Amplify)
            'sub_boss_damage': 0,
            'sub_normal_damage': 0,
            'sub_crit_rate': 0,
            'sub_crit_damage': 0,
            'sub_attack_flat': 0,
            'sub_skill_1st': 0,
            'sub_skill_2nd': 0,
            'sub_skill_3rd': 0,
            'sub_skill_4th': 0,
            # Special sub stat (only on special items)
            'special_stat_type': 'damage_pct',
            'special_stat_value': 0,
        }
        data.equipment_potentials[slot] = {
            # Regular potential
            'tier': 'Legendary',
            'line1_stat': '',
            'line1_value': 0,
            'line2_stat': '',
            'line2_value': 0,
            'line3_stat': '',
            'line3_value': 0,
            'regular_pity': 0,
            # Bonus potential
            'bonus_tier': 'Legendary',
            'bonus_line1_stat': '',
            'bonus_line1_value': 0,
            'bonus_line2_stat': '',
            'bonus_line2_value': 0,
            'bonus_line3_stat': '',
            'bonus_line3_value': 0,
            'bonus_pity': 0,
        }

    # Default hero power lines
    for i in range(1, 7):
        data.hero_power_lines[f'line{i}'] = {
            'stat': '',
            'value': 0,
            'tier': 'Common',
            'locked': False,
        }

    # Default hero power passives
    data.hero_power_passives = {
        'main_stat': 0,
        'damage': 0,
        'attack': 0,
        'hp': 0,
        'accuracy': 0,
        'defense': 0,
    }

    # Default equipment sets
    data.equipment_sets = {
        'medal': 0,
        'costume': 0,
    }

    # Default maple rank
    data.maple_rank = {
        'current_stage': 1,
        'main_stat_level': 0,
    }


def delete_user_data(username: str) -> bool:
    """Delete a user's data file."""
    filepath = _get_user_file(username)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False


def export_user_data_csv(data: UserData) -> str:
    """
    Export user data to CSV string for download.
    Returns the CSV content as a string.
    """
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['section', 'key', 'subkey', 'value'])

    # Character info
    writer.writerow(['character', 'level', '', str(data.character_level)])
    writer.writerow(['character', 'all_skills', '', str(data.all_skills)])
    writer.writerow(['character', 'combat_mode', '', data.combat_mode])
    writer.writerow(['character', 'chapter', '', data.chapter])

    # Equipment items
    for slot, item in data.equipment_items.items():
        for key, value in item.items():
            writer.writerow(['equipment', slot, key, str(value)])

    # Equipment potentials
    for slot, pots in data.equipment_potentials.items():
        for key, value in pots.items():
            writer.writerow(['potential', slot, key, str(value)])

    # Hero Power lines
    for line_id, line_data in data.hero_power_lines.items():
        for key, value in line_data.items():
            writer.writerow(['hero_power_line', line_id, key, str(value)])

    # Hero Power passives
    for stat_type, level in data.hero_power_passives.items():
        writer.writerow(['hero_power_passive', stat_type, '', str(level)])

    # Hero Power level config
    for key, value in data.hero_power_level.items():
        writer.writerow(['hero_power_level', key, '', str(value)])

    # Artifacts equipped
    for slot, artifact in data.artifacts_equipped.items():
        for key, value in artifact.items():
            writer.writerow(['artifact_equipped', slot, key, str(value)])

    # Artifacts inventory
    for artifact_id, artifact in data.artifacts_inventory.items():
        for key, value in artifact.items():
            writer.writerow(['artifact_inventory', artifact_id, key, str(value)])

    # Artifacts resonance
    for key, value in data.artifacts_resonance.items():
        writer.writerow(['artifact_resonance', key, '', str(value)])

    # Weapons
    for weapon_id, weapon in data.weapons.items():
        for key, value in weapon.items():
            writer.writerow(['weapon', weapon_id, key, str(value)])

    # Companions equipped
    for slot, companion in data.companions_equipped.items():
        for key, value in companion.items():
            writer.writerow(['companion_equipped', slot, key, str(value)])

    # Companions inventory
    for comp_id, companion in data.companions_inventory.items():
        for key, value in companion.items():
            writer.writerow(['companion_inventory', comp_id, key, str(value)])

    # Maple Rank - handle nested stat_levels dict
    for key, value in data.maple_rank.items():
        if key == 'stat_levels' and isinstance(value, dict):
            for stat_key, stat_value in value.items():
                writer.writerow(['maple_rank_stat', stat_key, '', str(stat_value)])
        else:
            writer.writerow(['maple_rank', key, '', str(value)])

    # Equipment Sets
    for key, value in data.equipment_sets.items():
        writer.writerow(['equipment_sets', key, '', str(value)])

    # Manual adjustments
    for stat, value in data.manual_adjustments.items():
        writer.writerow(['manual_adj', stat, '', str(value)])

    return output.getvalue()


def import_user_data_csv(csv_content: str, username: str) -> Optional[UserData]:
    """
    Import user data from CSV string.
    Returns UserData object if successful, None if failed.
    """
    import io
    data = UserData(username=username)
    _init_default_data(data)

    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            section = row.get('section', '')
            key = row.get('key', '')
            subkey = row.get('subkey', '')
            value = row.get('value', '')

            if not section or not key:
                continue

            if section == 'character':
                if key == 'level':
                    data.character_level = int(value)
                elif key == 'all_skills':
                    data.all_skills = int(value)
                elif key == 'combat_mode':
                    data.combat_mode = value
                elif key == 'chapter':
                    data.chapter = value

            elif section == 'equipment':
                if key not in data.equipment_items:
                    data.equipment_items[key] = {}
                data.equipment_items[key][subkey] = _parse_value(value)

            elif section == 'potential':
                if key not in data.equipment_potentials:
                    data.equipment_potentials[key] = {}
                data.equipment_potentials[key][subkey] = _parse_value(value)

            elif section == 'hero_power_line':
                if key not in data.hero_power_lines:
                    data.hero_power_lines[key] = {}
                data.hero_power_lines[key][subkey] = _parse_value(value)

            elif section == 'hero_power_passive':
                data.hero_power_passives[key] = int(value)

            elif section == 'hero_power_level':
                data.hero_power_level[key] = _parse_value(value)

            elif section == 'artifact_equipped':
                if key not in data.artifacts_equipped:
                    data.artifacts_equipped[key] = {}
                data.artifacts_equipped[key][subkey] = _parse_value(value)

            elif section == 'artifact_inventory':
                if key not in data.artifacts_inventory:
                    data.artifacts_inventory[key] = {}
                data.artifacts_inventory[key][subkey] = _parse_value(value)

            elif section == 'artifact_resonance':
                data.artifacts_resonance[key] = _parse_value(value)

            elif section == 'weapon':
                if key not in data.weapons:
                    data.weapons[key] = {}
                data.weapons[key][subkey] = _parse_value(value)

            elif section == 'companion_equipped':
                if key not in data.companions_equipped:
                    data.companions_equipped[key] = {}
                data.companions_equipped[key][subkey] = _parse_value(value)

            elif section == 'companion_inventory':
                if key not in data.companions_inventory:
                    data.companions_inventory[key] = {}
                data.companions_inventory[key][subkey] = _parse_value(value)

            elif section == 'maple_rank':
                if key == 'stat_levels':
                    continue  # Skip legacy format
                data.maple_rank[key] = _parse_value(value)

            elif section == 'maple_rank_stat':
                if 'stat_levels' not in data.maple_rank:
                    data.maple_rank['stat_levels'] = {}
                data.maple_rank['stat_levels'][key] = int(value)

            elif section == 'equipment_sets':
                data.equipment_sets[key] = int(value)

            elif section == 'manual_adj':
                data.manual_adjustments[key] = float(value)

        return data
    except Exception as e:
        print(f"Error importing user data: {e}")
        return None
