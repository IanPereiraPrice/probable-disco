"""
Equipment Screenshot OCR Scanner
Extracts stats from MapleStory Idle equipment screenshots using EasyOCR.
"""
import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from difflib import SequenceMatcher
from PIL import Image
import io

# Lazy-loaded OCR reader (heavy on startup)
_reader = None


def get_ocr_reader():
    """Lazy load EasyOCR reader to avoid slow startup."""
    global _reader
    if _reader is None:
        import easyocr
        import sys
        import os
        # Suppress EasyOCR's progress bar output which can cause encoding errors on Windows
        # by redirecting stdout during initialization
        old_stdout = sys.stdout
        try:
            sys.stdout = open(os.devnull, 'w', encoding='utf-8')
            _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        finally:
            sys.stdout.close()
            sys.stdout = old_stdout
    return _reader


# =============================================================================
# STAT VOCABULARY (closed vocabulary for fuzzy matching)
# =============================================================================

STAT_VOCABULARY: Dict[str, List[str]] = {
    # Main stats with percentage
    "dex_pct": ["DEX", "DEX%", "Dex"],
    "str_pct": ["STR", "STR%", "Str"],
    "int_pct": ["INT", "INT%", "Int"],
    "luk_pct": ["LUK", "LUK%", "Luk"],
    # Other percentage stats
    "crit_rate": ["Critical Rate", "Crit Rate", "CR", "Crit"],
    "crit_damage": ["Critical Damage", "Crit Damage", "CD"],
    "damage": ["Damage", "DMG", "Damage%"],
    "final_damage": ["Final Damage", "FD", "Final DMG"],
    "defense": ["Defense", "DEF", "Defence"],
    "max_hp": ["Max HP", "HP", "MaxHP"],
    "max_mp": ["Max MP", "MP", "MaxMP"],
    "attack_speed": ["Attack Speed", "Atk Speed", "AS"],
    "min_dmg_mult": ["Min Damage", "MinD", "Min DMG"],
    "max_dmg_mult": ["Max Damage", "MaxD", "Max DMG"],
    # Special stats
    "all_skills": ["All Skills", "All Skill", "Skill Level"],
    "def_pen": ["Defense Pen", "Def Pen", "DP", "Defense Penetration"],
    "buff_duration": ["Buff Duration", "Buff Dur", "Buff%"],
    "skill_cd": ["Skill CD", "Skill Cooldown", "CDR", "Cooldown"],
    "ba_targets": ["BA Targets", "Basic Attack Targets", "BA+"],
    "stat_per_level": ["Stat per Level", "Main Stat per Level", "S/Lv"],
}

# Flat stat variants (distinguished by value magnitude, not %)
FLAT_STAT_KEYS = {"dex_flat", "str_flat", "int_flat", "luk_flat"}

TIER_VOCABULARY = ["Rare", "Epic", "Unique", "Legendary", "Mystic"]

# Equipment slot names as they appear in screenshots
# Format: "Legendary Top", "Mystic Ring", etc.
# Maps display name -> internal slot key
EQUIPMENT_SLOT_MAP = {
    "hat": "hat",
    "cap": "hat",
    "top": "top",
    "bottom": "bottom",
    "gloves": "gloves",
    "glove": "gloves",
    "shoes": "shoes",
    "shoe": "shoes",
    "belt": "belt",
    "shoulder": "shoulder",
    "cape": "cape",
    "ring": "ring",
    "eye accessory": "face",
    "eye": "face",
    "face": "face",
    "necklace": "necklace",
    "pendant": "necklace",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PotentialLine:
    """A single potential line with stat and value."""
    stat: str = ""
    value: float = 0.0
    is_percentage: bool = True
    raw_text: str = ""
    confidence: float = 0.0


@dataclass
class ParsedEquipment:
    """Parsed equipment data from screenshot."""
    # Basic info
    item_name: str = ""
    stars: int = 0
    tier_level: str = ""  # e.g., "T4 Lv.101"
    item_level: int = 0  # Parsed level from tier_level
    item_tier: int = 0   # Parsed tier (T1, T2, etc.)
    equipment_slot: str = ""  # Detected slot type (hat, gloves, etc.)
    equipment_rarity: str = ""  # Detected rarity (Legendary, Mystic, etc.)

    # Base stats (from left panel)
    base_atk: int = 0         # ATK value
    base_def: int = 0         # DEF value
    base_hp: int = 0          # Max HP value
    base_mp: int = 0          # Max MP value
    base_str: int = 0         # STR flat
    base_dex: int = 0         # DEX flat
    base_int: int = 0         # INT flat
    base_luk: int = 0         # LUK flat
    base_main_stat: int = 0   # Main Stat value
    base_crit_rate: float = 0.0    # Critical Rate %
    base_crit_damage: float = 0.0  # Critical Damage %
    base_accuracy: int = 0    # Accuracy
    base_evasion: int = 0     # Evasion
    base_boss_dmg: float = 0.0     # Boss Monster Damage %

    # Regular potential
    regular_tier: str = "Legendary"
    regular_pity: int = 0
    regular_pity_max: int = 714
    regular_lines: List[PotentialLine] = field(default_factory=list)

    # Bonus potential
    bonus_tier: str = "Unique"
    bonus_pity: int = 0
    bonus_pity_max: int = 417
    bonus_lines: List[PotentialLine] = field(default_factory=list)

    # Parsing metadata
    raw_text: List[str] = field(default_factory=list)
    parse_confidence: float = 0.0
    debug_info: List[str] = field(default_factory=list)


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

def fuzzy_match(text: str, vocabulary: Dict[str, List[str]], threshold: float = 0.6) -> Tuple[Optional[str], float]:
    """
    Match OCR text to closest vocabulary term.
    Returns (stat_key, confidence) or (None, 0.0) if no match.
    """
    text_clean = text.strip()
    text_lower = text_clean.lower()
    best_match = None
    best_score = 0.0

    for stat_key, aliases in vocabulary.items():
        for alias in aliases:
            # Try exact match first (case-insensitive)
            if text_lower == alias.lower():
                return stat_key, 1.0

            # Fuzzy match
            ratio = SequenceMatcher(None, text_lower, alias.lower()).ratio()
            if ratio > best_score and ratio >= threshold:
                best_score = ratio
                best_match = stat_key

    return best_match, best_score


def parse_stat_line(line: str) -> Optional[PotentialLine]:
    """
    Parse a single potential line like "DEX 12%" or "INT 400".
    Returns PotentialLine or None if unparseable.
    """
    line = line.strip()
    if not line:
        return None

    # Pattern: STAT_NAME VALUE[%]
    # Examples: "DEX 12%", "INT 400", "Critical Rate 9%"

    # Try percentage pattern first: "STAT 12%" or "STAT 12.5%"
    pct_match = re.search(r'^(.+?)\s+([\d.]+)\s*%\s*$', line)
    if pct_match:
        stat_text = pct_match.group(1).strip()
        value = float(pct_match.group(2))
        stat_key, conf = fuzzy_match(stat_text, STAT_VOCABULARY)
        if stat_key:
            return PotentialLine(
                stat=stat_key,
                value=value,
                is_percentage=True,
                raw_text=line,
                confidence=conf
            )

    # Try flat value pattern: "STAT 400" or "STAT 1,200"
    flat_match = re.search(r'^(.+?)\s+([\d,]+)\s*$', line)
    if flat_match:
        stat_text = flat_match.group(1).strip()
        value_str = flat_match.group(2).replace(',', '')
        try:
            value = float(value_str)
        except ValueError:
            return None

        stat_key, conf = fuzzy_match(stat_text, STAT_VOCABULARY)
        if stat_key:
            # Determine if this should be a flat stat based on value magnitude
            # Flat stats are typically 100+ (e.g., INT 400)
            # Percentage stats are typically < 20
            if value >= 50 and stat_key in ("dex_pct", "str_pct", "int_pct", "luk_pct"):
                stat_key = stat_key.replace("_pct", "_flat")
                is_pct = False
            else:
                is_pct = value < 50  # Small values without % are likely percentages

            return PotentialLine(
                stat=stat_key,
                value=value,
                is_percentage=is_pct,
                raw_text=line,
                confidence=conf
            )

    return None


def parse_pity(text: str) -> Tuple[int, int]:
    """
    Parse pity counter like "321/714" or "(321/714)".
    Returns (current, threshold).
    """
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def parse_stars(text: str) -> int:
    """
    Parse star count from text like "★18" or "18★" or "☆18".
    """
    match = re.search(r'[★☆]\s*(\d+)|(\d+)\s*[★☆]', text)
    if match:
        return int(match.group(1) or match.group(2))
    return 0


def detect_tier(text: str) -> Optional[str]:
    """Detect potential tier from text."""
    text_lower = text.lower()
    for tier in TIER_VOCABULARY:
        if tier.lower() in text_lower:
            return tier
    return None


def parse_equipment_header(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse equipment rarity and slot from text like "Legendary Top" or "Mystic Ring".
    Returns (rarity, slot_key) or (None, None) if not matched.
    """
    text_lower = text.lower().strip()

    # Check for rarity first
    rarity = None
    for tier in TIER_VOCABULARY:
        if tier.lower() in text_lower:
            rarity = tier
            # Remove rarity from text to find slot
            text_lower = text_lower.replace(tier.lower(), "").strip()
            break

    # Check for slot name
    slot_key = None
    for slot_name, key in EQUIPMENT_SLOT_MAP.items():
        if slot_name in text_lower:
            slot_key = key
            break

    return rarity, slot_key


def is_value_pattern(text: str) -> bool:
    """Check if text looks like a stat value (number with optional %)."""
    return bool(re.match(r'^[\d,.]+%?$', text.strip()))


def parse_tier_level(text: str) -> Tuple[int, int]:
    """
    Parse tier and level from text like "T4 Lv.101" or "T4 Lv 101".
    Uses OCR error correction for common misreads.
    Returns (tier, level) or (0, 0) if not found.
    """
    # Try standard pattern first
    match = re.search(r'T(\d+).*?Lv\.?\s*(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Extract tier separately first (T followed by digit)
    tier_match = re.search(r'T(\d+)', text, re.IGNORECASE)
    tier = int(tier_match.group(1)) if tier_match else 0

    # Extract just the part after Lv and apply OCR fixes to ONLY that part
    # This avoids corrupting "T" and "Lv" themselves
    lv_match = re.search(r'Lv\.?\s*(.{2,5})', text, re.IGNORECASE)
    if lv_match:
        after_lv = lv_match.group(1)
        fixed_after = fix_ocr_digits(after_lv)
        digits = re.search(r'(\d{2,3})', fixed_after)
        if digits:
            level = int(digits.group(1))
            if 1 <= level <= 120:  # Valid level range
                return tier, level

    return tier, 0  # Return tier even if level not found


# OCR character substitution map - common misreads when expecting digits
OCR_DIGIT_SUBSTITUTIONS = {
    'j': '1', 'J': '1',  # j looks like 1
    'l': '1', 'L': '1', 'i': '1', 'I': '1', '|': '1',  # vertical lines -> 1
    'o': '0', 'O': '0', 'D': '0',  # round shapes -> 0
    's': '5', 'S': '5',  # S looks like 5
    'g': '9', 'q': '9',  # g/q look like 9
    'b': '6', 'G': '6',  # b/G look like 6
    'B': '8',  # B looks like 8
    'z': '2', 'Z': '2',  # Z looks like 2
    'A': '4',  # A can look like 4
    't': '7', 'T': '7',  # T looks like 7 (less common)
}


def fix_ocr_digits(text: str) -> str:
    """
    Apply OCR error corrections to extract digits from text.
    Replaces commonly misread characters with their likely digit equivalents.

    Example: "Lvj04" -> "Lv104", "T4_lvdoo" -> "T4_lv100"
    """
    result = []
    for char in text:
        if char in OCR_DIGIT_SUBSTITUTIONS:
            result.append(OCR_DIGIT_SUBSTITUTIONS[char])
        else:
            result.append(char)
    return ''.join(result)


def parse_level_only(text: str, min_level: int = 1, max_level: int = 120) -> Tuple[int, int]:
    """
    Parse level from text like "Lv.101", "Lv 87", "Lv.105".
    Uses OCR error correction for common misreads like "Lvj04" -> 104

    Args:
        text: Text to parse
        min_level: Minimum valid level (default 1)
        max_level: Maximum valid level (default 120)

    Returns (level, confidence) where confidence is:
        - 2: High confidence (Lv. with period)
        - 1: Medium confidence (Lv without period or OCR-fixed)
        - 0: Not found
    """
    text = text.strip()

    def is_valid_level(lvl: int) -> bool:
        return min_level <= lvl <= max_level

    # High confidence: Lv.XXX with explicit period
    match = re.search(r'Lv\.\s*(\d{2,3})', text, re.IGNORECASE)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 2

    # Medium confidence: Lv XXX or LvXXX (no period)
    match = re.search(r'Lv\s*(\d{2,3})', text, re.IGNORECASE)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 1

    # Apply OCR digit corrections and try again
    # This handles cases like "Lvj04" -> "Lv104", "Lv.l03" -> "Lv.103"
    fixed_text = fix_ocr_digits(text)

    # Check for period pattern in fixed text
    match = re.search(r'Lv\.\s*(\d{2,3})', fixed_text, re.IGNORECASE)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 2

    match = re.search(r'Lv\s*(\d{2,3})', fixed_text, re.IGNORECASE)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 1

    # Last resort: look for Lv followed by anything, then apply fixes
    # Extract the part after Lv and fix it
    match = re.search(r'Lv\.?\s*(.{2,5})', text, re.IGNORECASE)
    if match:
        after_lv = match.group(1)
        fixed_after = fix_ocr_digits(after_lv)
        # Extract just the digits (2-3 digits only for valid levels)
        digits = re.search(r'(\d{2,3})', fixed_after)
        if digits:
            level = int(digits.group(1))
            if is_valid_level(level):
                return level, 1

    return 0, 0


def parse_tier_only(text: str) -> int:
    """
    Parse tier from text like "T4", "T1", "T3".
    Returns tier (1-4) or 0 if not found.
    """
    text = text.strip()

    # Standard pattern: T followed by 1-4
    match = re.match(r'^T([1-4])$', text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # Also match if T is at start with other stuff after
    match = re.match(r'^T([1-4])\b', text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return 0


def parse_abbreviated_number(text: str) -> int:
    """
    Parse numbers with abbreviations like "79M 669K", "13M 61K", "36,373".

    Handles formats:
    - "79M 669K" -> 79,669,000
    - "13M 61K" -> 13,061,000
    - "36,373" -> 36373
    - "9,958" -> 9958
    - "124.8%" -> 124 (for integer conversion)

    Returns integer value or 0 if unparseable.
    """
    text = text.strip()
    if not text:
        return 0

    # Remove % suffix if present
    text = text.rstrip('%').strip()

    # Check for M/K abbreviations (e.g., "79M 669K", "13M 61K")
    # Pattern: optional millions + optional thousands
    total = 0

    # Find millions
    m_match = re.search(r'(\d+)\s*M', text, re.IGNORECASE)
    if m_match:
        total += int(m_match.group(1)) * 1_000_000

    # Find thousands
    k_match = re.search(r'(\d+)\s*K', text, re.IGNORECASE)
    if k_match:
        total += int(k_match.group(1)) * 1_000

    if total > 0:
        return total

    # Try standard number format (with commas)
    # Remove commas and parse
    clean = text.replace(',', '').replace(' ', '')

    # Handle decimal (take integer part)
    if '.' in clean:
        clean = clean.split('.')[0]

    try:
        return int(clean)
    except ValueError:
        return 0


def extract_base_stats(ocr_items: List[dict], right_panel_x: float) -> dict:
    """
    Extract base stats from the "On-Equip Effect" section of the equipment screenshot.

    This section shows the equipment's actual stats (NOT the player's total stats):
    - Attack 17,231 (not 79M which is player total)
    - Max HP 85,420 (not 13M which is player total)
    - Defense 36,373
    - Critical Rate 5.2%
    - Critical Damage 14.2%

    IMPORTANT: In the On-Equip Effect section:
    - Stat NAMES are on the left (x ~600-700)
    - Stat VALUES are on the right (x ~1100-1200)
    - Player total stats are at the BOTTOM (y > 750) and should be ignored

    We identify stats by:
    1. Finding stat names (Attack, Max HP, etc.) in the Y range ~550-750
    2. Looking for values on the SAME ROW (within 30px Y tolerance) but to the RIGHT

    Args:
        ocr_items: All OCR items
        right_panel_x: X threshold - items with x < this are on the left panel

    Returns:
        Dict with base stats: atk, def, hp, mp, str, dex, int, luk, main_stat,
                             crit_rate, crit_damage, accuracy, evasion, boss_dmg
    """
    stats = {
        'atk': 0,
        'def': 0,
        'hp': 0,
        'mp': 0,
        'str': 0,
        'dex': 0,
        'int': 0,
        'luk': 0,
        'main_stat': 0,
        'crit_rate': 0.0,
        'crit_damage': 0.0,
        'accuracy': 0,
        'evasion': 0,
        'boss_dmg': 0.0,
    }

    # The On-Equip Effect section is in a specific Y range
    # Stats at y > 750 are typically player totals at the bottom of screen
    # Equipment stats are typically in the range y ~500-750
    ON_EQUIP_MIN_Y = 500  # Start of On-Equip Effect section
    ON_EQUIP_MAX_Y = 750  # End of On-Equip Effect section (before player totals)

    # Equipment stat values are in a specific X range (~1000-1400)
    # This excludes potential line values which are further right (~1600-1800)
    STAT_VALUE_MIN_X = 900   # Values start around x=1100
    STAT_VALUE_MAX_X = 1400  # Values end before x=1400 (potential lines start ~1600)

    # Filter stat NAME candidates: left side of screen, within Y range
    # Stat names like "Attack", "Max HP" are at x ~600-700, y ~550-750
    stat_name_items = [
        item for item in ocr_items
        if item['x'] < right_panel_x and ON_EQUIP_MIN_Y <= item['y'] <= ON_EQUIP_MAX_Y
    ]

    # Filter STAT VALUE candidates: right of stat names but left of potential lines
    # Values like "17,231", "85,420" are at x ~1100-1200
    stat_value_items = [
        item for item in ocr_items
        if STAT_VALUE_MIN_X <= item['x'] <= STAT_VALUE_MAX_X and ON_EQUIP_MIN_Y <= item['y'] <= ON_EQUIP_MAX_Y
    ]

    # Base stat patterns - stat name followed by number
    # These are typically formatted as "Attack 12,345" or "Max HP 108,867"
    base_stat_patterns = {
        'atk': [r'\bAttack\b', r'\bATK\b'],
        'def': [r'\bDefense\b', r'\bDefence\b', r'\bDEF\b'],
        'hp': [r'\bMax HP\b', r'\bHP\b'],
        'mp': [r'\bMax MP\b', r'\bMP\b'],
        'str': [r'\bSTR\b'],
        'dex': [r'\bDEX\b'],
        'int': [r'\bINT\b'],
        'luk': [r'\bLUK\b'],
        'main_stat': [r'\bMain Stat\b'],
        'crit_rate': [r'\bCritical Rate\b', r'\bCrit Rate\b'],
        'crit_damage': [r'\bCritical Damage\b', r'\bCrit Damage\b'],
        'accuracy': [r'\bAccuracy\b'],
        'evasion': [r'\bEvasion\b'],
        'boss_dmg': [r'\bBoss Monster Damage\b', r'\bBoss Damage\b', r'\bBoss DMG\b'],
    }

    used_indices = set()

    # Stats that are percentages
    pct_stats = {'crit_rate', 'crit_damage', 'boss_dmg'}

    for i, item in enumerate(stat_name_items):
        if i in used_indices:
            continue

        text = item['text'].strip()
        if not text:
            continue

        # Check if this text matches a base stat name
        for stat_key, patterns in base_stat_patterns.items():
            matched = False
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched = True
                    break

            if matched:
                # Try to extract value from the same text (e.g., "Attack 21,862" or "Critical Rate 14.2%")
                # Handle both integer and percentage values
                pct_match = re.search(r'([\d,.]+)%\s*$', text)

                if pct_match and stat_key in pct_stats:
                    value_str = pct_match.group(1).replace(',', '')
                    try:
                        stats[stat_key] = float(value_str)
                        used_indices.add(i)
                    except ValueError:
                        pass
                else:
                    # Look for value in stat_value_items on the same row
                    # Values are in the X range ~1000-1400, to the RIGHT of stat names
                    item_y = item['y']
                    row_tolerance = 30  # Y tolerance for same row

                    for other in stat_value_items:
                        other_text = other['text'].strip()
                        if not other_text or other_text == text:
                            continue
                        # Value should be to the RIGHT of the stat name (higher x)
                        # and on the same row (within Y tolerance)
                        if abs(other['y'] - item_y) <= row_tolerance and other['x'] > item['x']:
                            # Check for percentage stats
                            if stat_key in pct_stats:
                                pct_match = re.search(r'([\d,.]+)%?', other_text)
                                if pct_match:
                                    value_str = pct_match.group(1).replace(',', '')
                                    try:
                                        stats[stat_key] = float(value_str)
                                        used_indices.add(i)
                                    except ValueError:
                                        pass
                                    break
                            else:
                                # Parse as simple number (17,231 format, NOT abbreviated like 79M)
                                # Only accept numbers without M/K suffixes for equipment stats
                                if not re.search(r'[MK]', other_text, re.IGNORECASE):
                                    clean = other_text.replace(',', '').strip()
                                    try:
                                        value = int(clean)
                                        if value > 0:
                                            stats[stat_key] = value
                                            used_indices.add(i)
                                            break
                                    except ValueError:
                                        pass
                break

    return stats


def find_potential_lines_from_items(ocr_items: List[dict]) -> List[PotentialLine]:
    """
    Find stat+value pairs from OCR items where they may be separate.

    OCR often returns "DEX" and "12%" as separate items instead of "DEX 12%".
    This function looks for stat names near value patterns (before or after).
    """
    lines = []
    used_indices = set()

    # First pass: look for combined lines (e.g., "DEX 12%")
    for i, item in enumerate(ocr_items):
        text = item['text'].strip()
        if not text:
            continue
        combined_line = parse_stat_line(text)
        if combined_line:
            lines.append(combined_line)
            used_indices.add(i)

    # Second pass: find stat names and look for nearby values
    for i, item in enumerate(ocr_items):
        if i in used_indices:
            continue

        text = item['text'].strip()
        if not text:
            continue

        # Check if this looks like a stat name
        stat_key, conf = fuzzy_match(text, STAT_VOCABULARY, threshold=0.7)
        if stat_key:
            # Look for a value in nearby items (before and after)
            search_range = list(range(max(0, i - 3), i)) + list(range(i + 1, min(i + 4, len(ocr_items))))
            for j in search_range:
                if j in used_indices:
                    continue
                next_text = ocr_items[j]['text'].strip()
                if is_value_pattern(next_text):
                    # Combine stat name and value
                    combined = f"{text} {next_text}"
                    line = parse_stat_line(combined)
                    if line:
                        lines.append(line)
                        used_indices.add(i)
                        used_indices.add(j)
                        break

    # Third pass: look for value patterns and find nearby stat names
    for i, item in enumerate(ocr_items):
        if i in used_indices:
            continue

        text = item['text'].strip()
        if not text or not is_value_pattern(text):
            continue

        # This is a value - look for a stat name nearby
        search_range = list(range(max(0, i - 3), i)) + list(range(i + 1, min(i + 4, len(ocr_items))))
        for j in search_range:
            if j in used_indices:
                continue
            stat_text = ocr_items[j]['text'].strip()
            stat_key, conf = fuzzy_match(stat_text, STAT_VOCABULARY, threshold=0.7)
            if stat_key:
                # Combine stat name and value
                combined = f"{stat_text} {text}"
                line = parse_stat_line(combined)
                if line:
                    lines.append(line)
                    used_indices.add(i)
                    used_indices.add(j)
                    break

    return lines


# =============================================================================
# SECTION-BASED PARSING (uses spatial layout)
# =============================================================================

def find_section_boundaries(ocr_items: List[dict]) -> dict:
    """
    Find the boundaries between Regular and Bonus potential sections.

    The layout is predictable:
    - "Potential Options" header at top
    - Regular Potential section (Legendary/Mystic tier, pity, 3 lines)
    - "Bonus Potential Options" section (tier, pity, 3 lines)

    Returns dict with 'regular_start_y', 'regular_end_y', 'bonus_start_y', 'right_panel_x', 'debug_info'

    IMPORTANT: The regular_end_y is HARD-CODED to be strictly before bonus_start_y with a buffer
    to prevent any cross-contamination between sections.
    """
    boundaries = {
        'regular_start_y': 0,
        'regular_end_y': float('inf'),  # Hard boundary for regular section END
        'bonus_start_y': float('inf'),
        'right_panel_x': 0,  # X threshold for right panel (potential options)
        'debug_info': [],
    }

    # Find the image width by looking at max x coordinate
    if ocr_items:
        max_x = max(item['x'] for item in ocr_items)
        min_x = min(item['x'] for item in ocr_items)
        # Right panel is roughly the right half of the image
        boundaries['right_panel_x'] = (max_x + min_x) / 2 * 0.7
        boundaries['debug_info'].append(f"X range: {min_x:.0f}-{max_x:.0f}, threshold: {boundaries['right_panel_x']:.0f}")

    # First pass: look for "Bonus" marker - this is the HARD divider
    bonus_marker_y = None
    for item in ocr_items:
        text = item['text'].lower()
        y = item['y']

        # Find "Bonus" section marker - look for "Bonus Potential" text
        if 'bonus' in text:
            bonus_marker_y = y
            boundaries['bonus_start_y'] = y
            boundaries['debug_info'].append(f"Found 'bonus' at y={y:.0f}: '{item['text']}'")
            break

    # Second pass: find tier markers ON THE RIGHT PANEL ONLY
    # This avoids confusing the equipment rarity (e.g., "Legendary Ring") with potential tiers
    tier_items = []
    for item in ocr_items:
        # Only consider items on the right side (potential panel)
        if item['x'] < boundaries['right_panel_x']:
            continue

        text = item['text'].lower()
        for tier in TIER_VOCABULARY:
            if tier.lower() in text:
                tier_items.append((item['y'], item['text'], item['x']))
                break

    if tier_items:
        # Sort by Y position
        tier_items.sort(key=lambda x: x[0])

        # First tier found on right panel is the regular potential tier
        boundaries['regular_start_y'] = tier_items[0][0] - 10  # Slight offset before tier
        boundaries['debug_info'].append(f"Found tier at y={tier_items[0][0]:.0f}, x={tier_items[0][2]:.0f}: '{tier_items[0][1]}'")

        # Only use second tier for bonus_start_y if we haven't found "Bonus" marker
        if bonus_marker_y is None and len(tier_items) >= 2:
            second_tier_y = tier_items[1][0]
            # Only use this if it's significantly below the first tier (at least 100px)
            if second_tier_y - tier_items[0][0] > 100:
                boundaries['bonus_start_y'] = second_tier_y - 10
                boundaries['debug_info'].append(f"Second tier at y={second_tier_y:.0f}: '{tier_items[1][1]}'")

    # HARD-CODE the regular section END boundary
    # Use the bonus marker if found, otherwise use second tier position
    # Add a BUFFER of 30 pixels to ensure no overlap
    SECTION_BUFFER = 30

    if bonus_marker_y is not None:
        # Use the bonus text marker as the hard divider
        boundaries['regular_end_y'] = bonus_marker_y - SECTION_BUFFER
        boundaries['debug_info'].append(f"Regular section HARD END at y={boundaries['regular_end_y']:.0f} (bonus marker - {SECTION_BUFFER}px buffer)")
    elif boundaries['bonus_start_y'] < float('inf'):
        # Use the bonus_start_y with buffer
        boundaries['regular_end_y'] = boundaries['bonus_start_y'] - SECTION_BUFFER
        boundaries['debug_info'].append(f"Regular section HARD END at y={boundaries['regular_end_y']:.0f} (bonus start - {SECTION_BUFFER}px buffer)")

    return boundaries


def extract_potential_section(ocr_items: List[dict], start_y: float, end_y: float,
                               right_x_threshold: float) -> Tuple[str, int, int, List[PotentialLine]]:
    """
    Extract tier, pity, and lines from a potential section.

    Args:
        ocr_items: All OCR items
        start_y: Y coordinate where this section starts
        end_y: Y coordinate where this section ends (HARD boundary - never match beyond this!)
        right_x_threshold: Only consider items with x > this value (right panel)

    Returns:
        (tier, pity_current, pity_max, lines)

    IMPORTANT: This function STRICTLY filters items by Y boundaries.
    Items outside [start_y, end_y) are NEVER considered, even for row-based matching.
    This prevents cross-contamination between Regular and Bonus Potential sections.
    """
    # Filter items STRICTLY within this section and on the right side
    # This is the ONLY pool of items we will ever consider for matching
    section_items = [
        item for item in ocr_items
        if start_y <= item['y'] < end_y and item['x'] > right_x_threshold
    ]

    # Sort by Y position
    section_items.sort(key=lambda x: x['y'])

    tier = "Legendary"
    pity_current = 0
    pity_max = 714
    lines = []

    # Track used indices to avoid double-matching
    used_indices = set()

    for i, item in enumerate(section_items):
        text = item['text'].strip()
        if not text or i in used_indices:
            continue

        # Check for tier
        detected_tier = detect_tier(text)
        if detected_tier:
            tier = detected_tier
            used_indices.add(i)
            continue

        # Check for pity counter
        p_current, p_max = parse_pity(text)
        if p_max > 0:
            pity_current = p_current
            pity_max = p_max
            used_indices.add(i)
            continue

        # Check if this is a stat name (lower threshold to catch more)
        stat_key, conf = fuzzy_match(text, STAT_VOCABULARY, threshold=0.55)
        if stat_key:
            # Look for value - first on same row, then nearby items
            item_y = item['y']
            row_tolerance = 25
            found_value = False

            # Check items on same row first
            for j, other in enumerate(section_items):
                if j == i or j in used_indices:
                    continue
                if abs(other['y'] - item_y) <= row_tolerance:
                    next_text = other['text'].strip()
                    if is_value_pattern(next_text):
                        combined = f"{text} {next_text}"
                        line = parse_stat_line(combined)
                        if line:
                            lines.append(line)
                            used_indices.add(i)
                            used_indices.add(j)
                            found_value = True
                            break

            # If not found, check next items by index
            if not found_value:
                for j in range(i + 1, min(i + 5, len(section_items))):
                    if j in used_indices:
                        continue
                    next_text = section_items[j]['text'].strip()
                    if is_value_pattern(next_text):
                        combined = f"{text} {next_text}"
                        line = parse_stat_line(combined)
                        if line:
                            lines.append(line)
                            used_indices.add(i)
                            used_indices.add(j)
                            break
            continue

        # Check if this is a value pattern - look for stat name
        if is_value_pattern(text):
            item_y = item['y']
            row_tolerance = 25
            found_stat = False

            # Check items on same row first
            for j, other in enumerate(section_items):
                if j == i or j in used_indices:
                    continue
                if abs(other['y'] - item_y) <= row_tolerance:
                    prev_text = other['text'].strip()
                    stat_key, conf = fuzzy_match(prev_text, STAT_VOCABULARY, threshold=0.55)
                    if stat_key:
                        combined = f"{prev_text} {text}"
                        line = parse_stat_line(combined)
                        if line:
                            lines.append(line)
                            used_indices.add(i)
                            used_indices.add(j)
                            found_stat = True
                            break

            # If not found, check previous items by index
            if not found_stat:
                for j in range(i - 1, max(i - 5, -1), -1):
                    if j in used_indices:
                        continue
                    prev_text = section_items[j]['text'].strip()
                    stat_key, conf = fuzzy_match(prev_text, STAT_VOCABULARY, threshold=0.55)
                    if stat_key:
                        combined = f"{prev_text} {text}"
                        line = parse_stat_line(combined)
                        if line:
                            lines.append(line)
                            used_indices.add(i)
                            used_indices.add(j)
                            break

    return tier, pity_current, pity_max, lines[:3]  # Max 3 lines per section


# =============================================================================
# MAIN EXTRACTION FUNCTION
# =============================================================================

def extract_and_parse(image_bytes: bytes) -> ParsedEquipment:
    """
    Main entry point: extract text from image and parse to structured data.

    Args:
        image_bytes: Raw image bytes from uploaded file

    Returns:
        ParsedEquipment with extracted data
    """
    reader = get_ocr_reader()

    # Run OCR - returns list of (bbox, text, confidence)
    results = reader.readtext(image_bytes, detail=1)

    # Extract text with positions
    all_items = []
    for (bbox, text, conf) in results:
        # Calculate center positions
        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_center = (bbox[0][0] + bbox[2][0]) / 2
        all_items.append({
            'text': text.strip(),
            'confidence': conf,
            'y': y_center,
            'x': x_center,
            'bbox': bbox,
        })

    # Sort by vertical position
    all_items.sort(key=lambda x: x['y'])
    # Include positions in raw text for debugging
    raw_texts = [f"[{item['x']:.0f},{item['y']:.0f}] {item['text']}" for item in all_items if item['text']]

    # Initialize parsed result
    parsed = ParsedEquipment(raw_text=raw_texts)

    # Find section boundaries
    boundaries = find_section_boundaries(all_items)
    parsed.debug_info = boundaries.get('debug_info', [])

    # Track best level found (highest confidence wins)
    best_level = 0
    best_level_confidence = 0
    best_level_source = ""

    # Extract stars, tier/level, and equipment slot/rarity from anywhere
    for item in all_items:
        text = item['text']
        if not text:
            continue

        # Extract stars - patterns like "'18" or "★18"
        if '★' in text or '☆' in text:
            stars = parse_stars(text)
            if stars > 0:
                parsed.stars = stars
        # Handle "'18" format (OCR sometimes reads ★ as ')
        if text.startswith("'") and len(text) > 1 and text[1:].isdigit():
            parsed.stars = int(text[1:])

        # Extract tier level (T4 Lv.101) - try combined pattern first
        if re.search(r'T\d+.*Lv', text, re.IGNORECASE):
            parsed.tier_level = text
            # Parse the tier and level numbers
            tier, level = parse_tier_level(text)
            if tier > 0:
                parsed.item_tier = tier
            if level > 0 and level > best_level_confidence:
                # Combined pattern is high confidence
                best_level = level
                best_level_confidence = 2
                best_level_source = text

        # Try to parse level separately using lenient pattern matching
        # This handles OCR errors like "Lv.87", "Lvj04", "[v887"
        level, confidence = parse_level_only(text)
        if level > 0 and confidence > best_level_confidence:
            best_level = level
            best_level_confidence = confidence
            best_level_source = text

        # Try to parse tier separately (T1, T2, T3, T4)
        if parsed.item_tier == 0:
            tier = parse_tier_only(text)
            if tier > 0:
                parsed.item_tier = tier
                parsed.debug_info.append(f"Tier from '{text}' -> T{tier}")

        # Extract equipment slot and rarity (e.g., "Legendary Top", "Mystic Ring")
        # This is in the left panel, look for pattern like "Rarity Slot"
        if not parsed.equipment_slot:  # Only set once
            rarity, slot = parse_equipment_header(text)
            if slot:
                parsed.equipment_slot = slot
                parsed.equipment_rarity = rarity or ""
                parsed.debug_info.append(f"Equipment header: '{text}' -> slot={slot}, rarity={rarity}")

    # Apply the best level found
    if best_level > 0:
        parsed.item_level = best_level
        parsed.debug_info.append(f"Level from '{best_level_source}' -> Lv.{best_level} (confidence={best_level_confidence})")

    # Extract base stats from the LEFT panel
    base_stats = extract_base_stats(all_items, boundaries['right_panel_x'])
    parsed.base_atk = base_stats['atk']
    parsed.base_def = base_stats['def']
    parsed.base_hp = base_stats['hp']
    parsed.base_mp = base_stats['mp']
    parsed.base_str = base_stats['str']
    parsed.base_dex = base_stats['dex']
    parsed.base_int = base_stats['int']
    parsed.base_luk = base_stats['luk']
    parsed.base_main_stat = base_stats['main_stat']
    parsed.base_crit_rate = base_stats['crit_rate']
    parsed.base_crit_damage = base_stats['crit_damage']
    parsed.base_accuracy = base_stats['accuracy']
    parsed.base_evasion = base_stats['evasion']
    parsed.base_boss_dmg = base_stats['boss_dmg']

    # Add base stats to debug info
    non_zero_stats = {k: v for k, v in base_stats.items() if v != 0}
    if non_zero_stats:
        parsed.debug_info.append(f"Base stats: {non_zero_stats}")

    # Get image height for section end boundary
    max_y = max(item['y'] for item in all_items) if all_items else 1000

    # Extract Regular Potential section - use the HARD END boundary
    regular_end = boundaries.get('regular_end_y', boundaries['bonus_start_y'])
    parsed.debug_info.append(f"Regular section: y={boundaries['regular_start_y']:.0f} to {regular_end:.0f} (HARD boundary)")
    regular_tier, regular_pity, regular_pity_max, regular_lines = extract_potential_section(
        all_items,
        start_y=boundaries['regular_start_y'],
        end_y=regular_end,  # Use the hard boundary
        right_x_threshold=boundaries['right_panel_x']
    )
    parsed.regular_tier = regular_tier
    parsed.regular_pity = regular_pity
    parsed.regular_pity_max = regular_pity_max
    parsed.regular_lines = regular_lines
    parsed.debug_info.append(f"Regular: tier={regular_tier}, pity={regular_pity}/{regular_pity_max}, lines={len(regular_lines)}")
    for line in regular_lines:
        parsed.debug_info.append(f"  - {line.stat}: {line.value} (conf={line.confidence:.2f})")

    # Extract Bonus Potential section
    parsed.debug_info.append(f"Bonus section: y={boundaries['bonus_start_y']:.0f} to {max_y + 100:.0f}")
    bonus_tier, bonus_pity, bonus_pity_max, bonus_lines = extract_potential_section(
        all_items,
        start_y=boundaries['bonus_start_y'],
        end_y=max_y + 100,
        right_x_threshold=boundaries['right_panel_x']
    )
    parsed.bonus_tier = bonus_tier
    parsed.bonus_pity = bonus_pity
    parsed.bonus_pity_max = bonus_pity_max
    parsed.bonus_lines = bonus_lines
    parsed.debug_info.append(f"Bonus: tier={bonus_tier}, pity={bonus_pity}/{bonus_pity_max}, lines={len(bonus_lines)}")

    # Ensure we have 3 lines for each section
    while len(parsed.regular_lines) < 3:
        parsed.regular_lines.append(PotentialLine())
    while len(parsed.bonus_lines) < 3:
        parsed.bonus_lines.append(PotentialLine())

    # Calculate overall parse confidence
    all_lines = parsed.regular_lines + parsed.bonus_lines
    valid_lines = [l for l in all_lines if l.stat]
    if valid_lines:
        parsed.parse_confidence = sum(l.confidence for l in valid_lines) / len(valid_lines)
    else:
        parsed.parse_confidence = 0.0

    return parsed
