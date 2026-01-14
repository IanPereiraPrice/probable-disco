"""
Data manager for loading and saving user data to CSV files.
Each user has a single CSV file with all their character data.
"""
import os
import csv
from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from equipment import Equipment
    from stats import StatBlock
    from cubes import SlotPotentials
    from job_classes import JobClass

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
    job_class: str = "bowmaster"  # Job class (from job_classes.py JobClass enum)
    all_skills: int = 0  # Auto-calculated from equipment potentials & sub stats
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

    # Hero Power presets (preset_name -> {lines: Dict, name: str})
    hero_power_presets: Dict[str, Dict] = field(default_factory=dict)
    active_hero_power_preset: str = "Default"

    # Artifacts (slot -> {name, stars, potentials...})
    artifacts_equipped: Dict[str, Dict] = field(default_factory=dict)
    artifacts_inventory: Dict[str, Dict] = field(default_factory=dict)
    artifacts_resonance: Dict[str, Any] = field(default_factory=dict)

    # Weapons - predefined list with level and awakening
    # Key format: "rarity_tier" e.g., "mystic_1", "legendary_2"
    # Value: {level: int, awakening: int}
    weapons_data: Dict[str, Dict] = field(default_factory=dict)
    equipped_weapon_key: str = ""  # Key of equipped weapon, e.g., "mystic_1"
    summoning_level: int = 15  # Weapon summoning level (1-17), affects drop rates

    # Companions (old format - slot -> {name, level})
    companions_equipped: Dict[str, Dict] = field(default_factory=dict)
    companions_inventory: Dict[str, Dict] = field(default_factory=dict)

    # Companions (new format)
    companion_levels: Dict[str, int] = field(default_factory=dict)  # companion_key -> level
    equipped_companions: list = field(default_factory=lambda: [None] * 7)  # 7 slots

    # Maple Rank
    maple_rank: Dict[str, Any] = field(default_factory=dict)

    # Equipment Sets (medals, costumes)
    equipment_sets: Dict[str, int] = field(default_factory=dict)

    # Manual adjustments
    manual_adjustments: Dict[str, float] = field(default_factory=dict)

    # Guild skills
    guild_skills: Dict[str, float] = field(default_factory=dict)

    def get_equipment(self, slot: str) -> 'Equipment':
        """
        Get Equipment object for a slot.
        Converts stored dict format to Equipment class.

        Handles the CSV flat format:
        - base_attack, base_max_hp, base_third_stat (main stats)
        - sub_boss_damage, sub_normal_damage, sub_crit_rate, etc. (sub stats)
        - special_stat_type, special_stat_value (special item stats)
        """
        from equipment import Equipment

        item_data = self.equipment_items.get(slot, {})
        if not item_data:
            return Equipment(slot=slot)

        equip = Equipment(
            slot=slot,
            name=item_data.get('name', ''),
            rarity=item_data.get('rarity', 'unique'),
            tier=int(item_data.get('tier', 4)),
            stars=int(item_data.get('stars', 0)),
            is_special=item_data.get('is_special', False),
        )

        # Load main stats from flat CSV format (base_attack, base_max_hp, base_third_stat)
        equip.set_base('attack', float(item_data.get('base_attack', 0)))
        equip.set_base('max_hp', float(item_data.get('base_max_hp', 0)))
        equip.set_base('third_stat', float(item_data.get('base_third_stat', 0)))

        # Load sub stats from flat CSV format (sub_boss_damage, sub_crit_rate, etc.)
        sub_stat_mappings = {
            'sub_boss_damage': 'boss_damage',
            'sub_normal_damage': 'normal_damage',
            'sub_crit_rate': 'crit_rate',
            'sub_crit_damage': 'crit_damage',
            'sub_attack_flat': 'sub_attack',
            'sub_skill_1st': 'skill_1st',
            'sub_skill_2nd': 'skill_2nd',
            'sub_skill_3rd': 'skill_3rd',
            'sub_skill_4th': 'skill_4th',
        }
        for csv_key, equip_key in sub_stat_mappings.items():
            value = item_data.get(csv_key, 0)
            if value:
                equip.set_base(equip_key, float(value))

        # Handle special stat (damage_pct, all_skills, final_damage)
        if equip.is_special:
            special_type = item_data.get('special_stat_type', 'damage_pct')
            special_value = float(item_data.get('special_stat_value', 0))
            if special_value > 0:
                equip.set_base(special_type, special_value)

        return equip

    def get_all_equipment(self) -> Dict[str, 'Equipment']:
        """Get all equipment as Equipment objects."""
        return {slot: self.get_equipment(slot) for slot in EQUIPMENT_SLOTS}

    def get_equipment_stats(self) -> 'StatBlock':
        """Get combined stats from all equipment (base stats only, not potentials)."""
        from stats import EMPTY_STATS
        return sum((self.get_equipment(slot).get_stats() for slot in EQUIPMENT_SLOTS), EMPTY_STATS)

    def get_potentials(self, slot: str) -> 'SlotPotentials':
        """
        Get SlotPotentials object for a slot.
        Converts stored dict format to SlotPotentials class.
        """
        from cubes import SlotPotentials

        pot_data = self.equipment_potentials.get(slot, {})
        return SlotPotentials.from_dict(slot, pot_data)

    def get_all_potentials(self) -> Dict[str, 'SlotPotentials']:
        """Get all potentials as SlotPotentials objects."""
        return {slot: self.get_potentials(slot) for slot in EQUIPMENT_SLOTS}

    def get_potentials_stats(self, job_class: 'JobClass' = None) -> 'StatBlock':
        """
        Get combined stats from all equipment potentials.

        Args:
            job_class: Job class for stat_per_level conversion. If None, uses self.job_class.
        """
        from stats import EMPTY_STATS
        from job_classes import JobClass as JC

        if job_class is None:
            try:
                job_class = JC(self.job_class)
            except ValueError:
                job_class = JC.BOWMASTER

        return sum(
            (self.get_potentials(slot).get_stats(job_class, self.character_level)
             for slot in EQUIPMENT_SLOTS),
            EMPTY_STATS
        )


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

            # Hero Power presets
            for preset_name, preset_data in data.hero_power_presets.items():
                for line_id, line_data in preset_data.get('lines', {}).items():
                    for key, value in line_data.items():
                        writer.writerow(['hero_power_preset', preset_name, f'{line_id}_{key}', str(value)])

            # Active Hero Power preset
            writer.writerow(['hero_power_active_preset', 'name', '', data.active_hero_power_preset])

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

            # Weapons data (predefined weapons with level/awakening)
            weapons_data = getattr(data, 'weapons_data', {}) or {}
            for weapon_key, weapon_data in weapons_data.items():
                for key, value in weapon_data.items():
                    writer.writerow(['weapons_data', weapon_key, key, str(value)])

            # Equipped weapon key
            equipped_weapon_key = getattr(data, 'equipped_weapon_key', '') or ''
            if equipped_weapon_key:
                writer.writerow(['equipped_weapon_key', '', '', equipped_weapon_key])

            # Summoning level
            writer.writerow(['summoning_level', '', '', str(getattr(data, 'summoning_level', 15))])

            # Companions equipped
            for slot, companion in data.companions_equipped.items():
                for key, value in companion.items():
                    writer.writerow(['companion_equipped', slot, key, str(value)])

            # Companions inventory
            for comp_id, companion in data.companions_inventory.items():
                for key, value in companion.items():
                    writer.writerow(['companion_inventory', comp_id, key, str(value)])

            # Companion levels (new format)
            for comp_key, level in data.companion_levels.items():
                writer.writerow(['companion_level', comp_key, '', str(level)])

            # Equipped companions (new format)
            for slot_idx, comp_key in enumerate(data.equipped_companions or []):
                if comp_key:
                    writer.writerow(['equipped_companion', str(slot_idx), '', comp_key])

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

            # Guild skills
            for stat, value in data.guild_skills.items():
                writer.writerow(['guild_skill', stat, '', str(value)])

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

                elif section == 'hero_power_preset':
                    preset_name = key
                    if preset_name not in data.hero_power_presets:
                        data.hero_power_presets[preset_name] = {'lines': {}}
                    # subkey format: line1_stat, line1_value, etc.
                    parts = subkey.split('_', 1)
                    if len(parts) == 2:
                        line_id, field_name = parts
                        if line_id not in data.hero_power_presets[preset_name]['lines']:
                            data.hero_power_presets[preset_name]['lines'][line_id] = {}
                        data.hero_power_presets[preset_name]['lines'][line_id][field_name] = _parse_value(value)

                elif section == 'hero_power_active_preset':
                    data.active_hero_power_preset = value

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

                elif section == 'weapons_data':
                    # New predefined weapon format: key="rarity_tier", subkey=field, value=int
                    if key not in data.weapons_data:
                        data.weapons_data[key] = {}
                    data.weapons_data[key][subkey] = int(value)

                elif section == 'equipped_weapon_key':
                    data.equipped_weapon_key = value

                elif section == 'summoning_level':
                    data.summoning_level = int(value)

                elif section == 'companion_equipped':
                    if key not in data.companions_equipped:
                        data.companions_equipped[key] = {}
                    data.companions_equipped[key][subkey] = _parse_value(value)

                elif section == 'companion_inventory':
                    if key not in data.companions_inventory:
                        data.companions_inventory[key] = {}
                    data.companions_inventory[key][subkey] = _parse_value(value)

                elif section == 'companion_level':
                    data.companion_levels[key] = int(value)

                elif section == 'equipped_companion':
                    slot_idx = int(key)
                    while len(data.equipped_companions) <= slot_idx:
                        data.equipped_companions.append(None)
                    data.equipped_companions[slot_idx] = value

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

                elif section == 'guild_skill':
                    data.guild_skills[key] = float(value)

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
    # Stats use standardized keys from stat_names.py
    for slot in EQUIPMENT_SLOTS:
        data.equipment_items[slot] = {
            'name': slot.title(),
            'rarity': 'Normal',
            'tier': 1,
            'stars': 0,
            'is_special': False,
            # Main Stats (Main Amplify)
            'main_stats': {
                'attack_flat': 0,
                'max_hp': 0,
                'third_stat': 0,  # Varies by slot (defense, accuracy, etc.)
            },
            # Sub Stats (Sub Amplify) - includes special stats
            'sub_stats': {
                'boss_damage': 0,
                'normal_damage': 0,
                'crit_rate': 0,
                'crit_damage': 0,
                'attack_flat': 0,
                'skill_1st': 0,
                'skill_2nd': 0,
                'skill_3rd': 0,
                'skill_4th': 0,
                # Special stats (only on special items, is_special=True)
                'damage_pct': 0,
                'all_skills': 0,
                'final_damage': 0,
            },
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

    # Hero Power presets
    for preset_name, preset_data in data.hero_power_presets.items():
        for line_id, line_data in preset_data.get('lines', {}).items():
            for key, value in line_data.items():
                writer.writerow(['hero_power_preset', preset_name, f'{line_id}_{key}', str(value)])

    # Active Hero Power preset
    writer.writerow(['hero_power_active_preset', 'name', '', data.active_hero_power_preset])

    # Artifacts equipped
    for slot, artifact in data.artifacts_equipped.items():
        for key, value in artifact.items():
            writer.writerow(['artifact_equipped', slot, key, str(value)])

    # Artifacts inventory
    for artifact_id, artifact in data.artifacts_inventory.items():
        for key, value in artifact.items():
            if key == 'potentials' and isinstance(value, list):
                # Export each potential as a separate row with indexed subkey
                for pot_idx, pot in enumerate(value):
                    if isinstance(pot, dict):
                        for pot_key, pot_val in pot.items():
                            writer.writerow(['artifact_potential', artifact_id, f'{pot_idx}_{pot_key}', str(pot_val)])
            else:
                writer.writerow(['artifact_inventory', artifact_id, key, str(value)])

    # Artifacts resonance
    for key, value in data.artifacts_resonance.items():
        writer.writerow(['artifact_resonance', key, '', str(value)])

    # Weapons data (predefined weapons with level/awakening)
    weapons_data = getattr(data, 'weapons_data', {}) or {}
    for weapon_key, weapon_data in weapons_data.items():
        for key, value in weapon_data.items():
            writer.writerow(['weapons_data', weapon_key, key, str(value)])

    # Equipped weapon key
    equipped_weapon_key = getattr(data, 'equipped_weapon_key', '') or ''
    if equipped_weapon_key:
        writer.writerow(['equipped_weapon_key', '', '', equipped_weapon_key])

    # Summoning level
    writer.writerow(['summoning_level', '', '', str(getattr(data, 'summoning_level', 15))])

    # Companions equipped
    for slot, companion in data.companions_equipped.items():
        for key, value in companion.items():
            writer.writerow(['companion_equipped', slot, key, str(value)])

    # Companions inventory
    for comp_id, companion in data.companions_inventory.items():
        for key, value in companion.items():
            writer.writerow(['companion_inventory', comp_id, key, str(value)])

    # Companion levels (new format)
    for comp_key, level in data.companion_levels.items():
        writer.writerow(['companion_level', comp_key, '', str(level)])

    # Equipped companions (new format)
    for slot_idx, comp_key in enumerate(data.equipped_companions or []):
        if comp_key:
            writer.writerow(['equipped_companion', str(slot_idx), '', comp_key])

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

    # Guild skills
    for stat, value in data.guild_skills.items():
        writer.writerow(['guild_skill', stat, '', str(value)])

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

            elif section == 'hero_power_preset':
                preset_name = key
                if preset_name not in data.hero_power_presets:
                    data.hero_power_presets[preset_name] = {'lines': {}}
                parts = subkey.split('_', 1)
                if len(parts) == 2:
                    line_id, field_name = parts
                    if line_id not in data.hero_power_presets[preset_name]['lines']:
                        data.hero_power_presets[preset_name]['lines'][line_id] = {}
                    data.hero_power_presets[preset_name]['lines'][line_id][field_name] = _parse_value(value)

            elif section == 'hero_power_active_preset':
                data.active_hero_power_preset = value

            elif section == 'artifact_equipped':
                if key not in data.artifacts_equipped:
                    data.artifacts_equipped[key] = {}
                data.artifacts_equipped[key][subkey] = _parse_value(value)

            elif section == 'artifact_inventory':
                if key not in data.artifacts_inventory:
                    data.artifacts_inventory[key] = {}
                data.artifacts_inventory[key][subkey] = _parse_value(value)

            elif section == 'artifact_potential':
                # Handle artifact potentials with format: artifact_id, "idx_field", value
                artifact_id = key
                if artifact_id not in data.artifacts_inventory:
                    data.artifacts_inventory[artifact_id] = {'stars': 0, 'dupes': 0, 'potentials': []}
                if 'potentials' not in data.artifacts_inventory[artifact_id]:
                    data.artifacts_inventory[artifact_id]['potentials'] = []

                # Parse subkey format: "0_stat", "0_value", "0_tier", "1_stat", etc.
                parts = subkey.split('_', 1)
                if len(parts) == 2:
                    pot_idx = int(parts[0])
                    field_name = parts[1]

                    # Ensure potentials list is long enough
                    while len(data.artifacts_inventory[artifact_id]['potentials']) <= pot_idx:
                        data.artifacts_inventory[artifact_id]['potentials'].append({'stat': '', 'value': 0, 'tier': 'legendary'})

                    data.artifacts_inventory[artifact_id]['potentials'][pot_idx][field_name] = _parse_value(value)

            elif section == 'artifact_resonance':
                data.artifacts_resonance[key] = _parse_value(value)

            elif section == 'weapons_data':
                # New predefined weapon format: key="rarity_tier", subkey=field, value=int
                if key not in data.weapons_data:
                    data.weapons_data[key] = {}
                data.weapons_data[key][subkey] = int(value)

            elif section == 'equipped_weapon_key':
                data.equipped_weapon_key = value

            elif section == 'summoning_level':
                data.summoning_level = int(value)

            elif section == 'companion_equipped':
                if key not in data.companions_equipped:
                    data.companions_equipped[key] = {}
                data.companions_equipped[key][subkey] = _parse_value(value)

            elif section == 'companion_inventory':
                if key not in data.companions_inventory:
                    data.companions_inventory[key] = {}
                data.companions_inventory[key][subkey] = _parse_value(value)

            elif section == 'companion_level':
                data.companion_levels[key] = int(value)

            elif section == 'equipped_companion':
                slot_idx = int(key)
                while len(data.equipped_companions) <= slot_idx:
                    data.equipped_companions.append(None)
                data.equipped_companions[slot_idx] = value

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

            elif section == 'guild_skill':
                data.guild_skills[key] = float(value)

        return data
    except Exception as e:
        print(f"Error importing user data: {e}")
        return None
