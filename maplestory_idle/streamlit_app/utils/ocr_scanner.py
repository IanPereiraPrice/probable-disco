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
import numpy as np

# =============================================================================
# PRE-COMPILED REGEX PATTERNS (compiled once at module load for performance)
# =============================================================================

# Level parsing patterns
_RE_LEVEL_WITH_PERIOD = re.compile(r'Lv\.\s*(\d{2,3})', re.IGNORECASE)
_RE_LEVEL_NO_PERIOD = re.compile(r'Lv\s*(\d{2,3})', re.IGNORECASE)
_RE_LEVEL_AFTER_LV = re.compile(r'Lv\.?\s*(.{2,5})', re.IGNORECASE)
_RE_DIGITS_2_3 = re.compile(r'(\d{2,3})')

# Tier parsing patterns
_RE_TIER_EXACT = re.compile(r'^T([1-4])$', re.IGNORECASE)
_RE_TIER_START = re.compile(r'^T([1-4])\b', re.IGNORECASE)
_RE_TIER_LEVEL_COMBINED = re.compile(r'T(\d+).*?Lv\.?\s*(\d+)', re.IGNORECASE)
_RE_TIER_IN_TEXT = re.compile(r'T\d+.*Lv', re.IGNORECASE)

# Stat parsing patterns
_RE_STAT_PCT = re.compile(r'^(.+?)\s+([\d.]+)\s*%\s*$')
_RE_STAT_FLAT = re.compile(r'^(.+?)\s+([\d,]+)\s*$')
_RE_VALUE_PATTERN = re.compile(r'^[\d,.]+%?$')

# Pity and star patterns
_RE_PITY = re.compile(r'(\d+)\s*/\s*(\d+)')
_RE_STAR = re.compile(r'[★☆]\s*(\d+)|(\d+)\s*[★☆]')

# Number parsing patterns
_RE_MILLIONS = re.compile(r'(\d+)\s*M', re.IGNORECASE)
_RE_THOUSANDS = re.compile(r'(\d+)\s*K', re.IGNORECASE)
_RE_MK_CHECK = re.compile(r'[MK]', re.IGNORECASE)
_RE_NUM_END = re.compile(r'([\d,]+)\s*$')
_RE_PCT_END = re.compile(r'([\d,.]+)%\s*$')
_RE_PCT_VALUE = re.compile(r'([\d,.]+)%?')

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
# POTENTIAL VALUE LOOKUP TABLES
# =============================================================================
# Instead of parsing OCR values (error-prone), we detect the stat name and
# whether the line is yellow (max roll) or grey (lower tier value), then
# look up the exact value from these tables.
#
# Yellow lines = current potential tier value
# Grey lines = one tier below value

# Potential values by tier for each stat type
# Format: stat_key -> {tier: value}
POTENTIAL_VALUES: Dict[str, Dict[str, float]] = {
    # Main stat percentages
    "dex_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "str_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "int_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "luk_pct": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    # Main stat flat
    "dex_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    "str_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    "int_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    "luk_flat": {"Epic": 200, "Unique": 400, "Legendary": 600, "Mystic": 1000},
    # Defense stats
    "defense": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "max_hp": {"Epic": 12.0, "Unique": 15.0, "Legendary": 20.0, "Mystic": 25.0},
    "max_mp": {"Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    # Combat stats
    "crit_rate": {"Rare": 4.5, "Epic": 6.0, "Unique": 9.0, "Legendary": 12.0, "Mystic": 15.0},
    "attack_speed": {"Rare": 3.5, "Epic": 4.0, "Unique": 5.0, "Legendary": 7.0, "Mystic": 10.0},
    "damage": {"Rare": 8.0, "Epic": 12.0, "Unique": 18.0, "Legendary": 25.0, "Mystic": 35.0},
    "min_dmg_mult": {"Rare": 6.0, "Epic": 8.0, "Unique": 10.0, "Legendary": 15.0, "Mystic": 25.0},
    "max_dmg_mult": {"Rare": 6.0, "Epic": 8.0, "Unique": 10.0, "Legendary": 15.0, "Mystic": 25.0},
    "skill_cd": {"Unique": 1.0, "Legendary": 1.5, "Mystic": 2.0},
    # Special stats (slot-specific)
    "crit_damage": {"Unique": 20.0, "Legendary": 30.0, "Mystic": 50.0},  # Gloves
    "def_pen": {"Unique": 8.0, "Legendary": 12.0, "Mystic": 20.0},  # Shoulder
    "all_skills": {"Epic": 5, "Unique": 8, "Legendary": 12, "Mystic": 16},  # Ring/Necklace
    "final_damage": {"Epic": 3.0, "Unique": 5.0, "Legendary": 8.0, "Mystic": 12.0},  # Cape/Bottom
    "buff_duration": {"Epic": 5.0, "Unique": 8.0, "Legendary": 12.0, "Mystic": 20.0},  # Belt
    "stat_per_level": {"Epic": 3.0, "Unique": 5.0, "Legendary": 8.0, "Mystic": 12.0},  # Face
    "ba_targets": {"Unique": 1, "Legendary": 2, "Mystic": 3},  # Top
}

# Tier hierarchy for determining "one tier below"
TIER_ORDER = ["Rare", "Epic", "Unique", "Legendary", "Mystic"]


def get_tier_below(tier: str) -> Optional[str]:
    """Get the tier one level below the given tier."""
    try:
        idx = TIER_ORDER.index(tier)
        if idx > 0:
            return TIER_ORDER[idx - 1]
    except ValueError:
        pass
    return None


def is_stat_valid_for_slot(stat_key: str, equipment_slot: str) -> bool:
    """
    Check if a stat can appear on a given equipment slot.

    Some stats are slot-specific (e.g., crit_damage only on gloves).
    If stat_key is not slot-specific, returns True.
    If equipment_slot is unknown/empty, returns True (can't validate).

    Args:
        stat_key: The stat type (e.g., "crit_damage", "def_pen")
        equipment_slot: The equipment slot (e.g., "gloves", "shoulder")

    Returns:
        True if the stat can appear on this slot, False if it's invalid
    """
    if not equipment_slot:
        return True  # Can't validate without knowing slot

    if stat_key not in SLOT_SPECIFIC_STATS:
        return True  # Not a slot-specific stat, always valid

    # Check multi-slot stats first
    if stat_key in MULTI_SLOT_STATS:
        return equipment_slot in MULTI_SLOT_STATS[stat_key]

    # Check single-slot stats
    valid_slot = SLOT_SPECIFIC_STATS[stat_key]
    return equipment_slot == valid_slot


def lookup_potential_value(stat_key: str, potential_tier: str, is_yellow: bool) -> Optional[float]:
    """
    Look up the exact potential value based on stat, tier, and line color.

    Args:
        stat_key: The stat type (e.g., "dex_pct", "crit_damage")
        potential_tier: The potential section's tier (e.g., "Legendary")
        is_yellow: True if the line is yellow (max roll), False if grey

    Returns:
        The exact value for this stat at this tier, or None if not found
    """
    if stat_key not in POTENTIAL_VALUES:
        return None

    values = POTENTIAL_VALUES[stat_key]

    if is_yellow:
        # Yellow = current tier value
        return values.get(potential_tier)
    else:
        # Grey = one tier below value
        lower_tier = get_tier_below(potential_tier)
        if lower_tier:
            return values.get(lower_tier)

    return None


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
    "min_dmg_mult": ["Min Damage", "MinD", "Min DMG", "Min Damage Multiplier"],
    "max_dmg_mult": ["Max Damage", "MaxD", "Max DMG", "Max Damage Multiplier"],
    # Boss/Normal monster damage
    "boss_damage": ["Boss Monster Damage", "Boss DMG", "Boss Damage", "Boss%"],
    "normal_damage": ["Normal Monster Damage", "Normal DMG", "Normal Damage", "Normal%"],
    # Special stats
    "all_skills": ["All Skills", "All Skill", "Skill Level"],
    "def_pen": ["Defense Pen", "Def Pen", "DP", "Defense Penetration"],
    "buff_duration": ["Buff Duration", "Buff Dur", "Buff%"],
    "skill_cd": ["Skill CD", "Skill Cooldown", "CDR", "Cooldown"],
    "ba_targets": ["BA Targets", "Basic Attack Targets", "BA+", "Basic Attack Target Increase"],
    "stat_per_level": ["Stat per Level", "Main Stat per Level", "S/Lv"],
}

# Flat stat variants (distinguished by value magnitude, not %)
FLAT_STAT_KEYS = {"dex_flat", "str_flat", "int_flat", "luk_flat"}

# Slot-specific stats - these stats can ONLY appear on specific equipment slots
# If we detect these stats on the wrong slot, it's an OCR error
SLOT_SPECIFIC_STATS: Dict[str, str] = {
    "crit_damage": "gloves",      # Crit Damage only on Gloves
    "def_pen": "shoulder",        # Defense Penetration only on Shoulder
    "all_skills": "ring",         # All Skills on Ring/Necklace (check both)
    "final_damage": "cape",       # Final Damage on Cape/Bottom
    "buff_duration": "belt",      # Buff Duration on Belt
    "stat_per_level": "face",     # Stat per Level on Face
    "ba_targets": "top",          # BA Targets on Top
}

# Some stats can appear on multiple slots
MULTI_SLOT_STATS: Dict[str, List[str]] = {
    "all_skills": ["ring", "necklace"],
    "final_damage": ["cape", "bottom"],
}

TIER_VOCABULARY = ["Rare", "Epic", "Unique", "Legendary", "Mystic"]

# Equipment slot names as they appear in screenshots
# Format: "Legendary Top", "Mystic Ring", etc.
# Maps display name -> internal slot key
EQUIPMENT_SLOT_MAP = {
    # IMPORTANT: Order matters! Longer strings must come before shorter substrings
    # e.g., "gloves" before "glove", "shoes" before "shoe"
    "eye accessory": "face",
    "necklace": "necklace",
    "shoulder": "shoulder",
    "pendant": "necklace",
    "gloves": "gloves",
    "bottom": "bottom",
    "glove": "gloves",
    "shoes": "shoes",
    "cape": "cape",
    "face": "face",
    "ring": "ring",
    "belt": "belt",
    "shoe": "shoes",
    "hat": "hat",
    "top": "top",
    "eye": "face",
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
    base_normal_dmg: float = 0.0   # Normal Monster Damage %

    # Job skill level bonuses (from On-Equip Effect section)
    base_skill_1st: int = 0   # 1st Job Skill Level +X
    base_skill_2nd: int = 0   # 2nd Job Skill Level +X
    base_skill_3rd: int = 0   # 3rd Job Skill Level +X
    base_skill_4th: int = 0   # 4th Job Skill Level +X

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

# Fuzzy match cache - stores (text_lower, threshold) -> (stat_key, confidence)
# Pre-populate with common exact matches for instant lookup
_fuzzy_match_cache: Dict[Tuple[str, float], Tuple[Optional[str], float]] = {}

# Pre-build exact match lookup for O(1) access
_EXACT_MATCH_MAP: Dict[str, str] = {}
for _stat_key, _aliases in STAT_VOCABULARY.items():
    for _alias in _aliases:
        _EXACT_MATCH_MAP[_alias.lower()] = _stat_key


def fuzzy_match(text: str, vocabulary: Dict[str, List[str]], threshold: float = 0.6) -> Tuple[Optional[str], float]:
    """
    Match OCR text to closest vocabulary term.
    Returns (stat_key, confidence) or (None, 0.0) if no match.

    Uses caching for performance - exact matches are O(1), fuzzy results are cached.
    """
    text_clean = text.strip()
    text_lower = text_clean.lower()

    # Fast path: exact match via pre-built lookup (O(1))
    if text_lower in _EXACT_MATCH_MAP:
        return _EXACT_MATCH_MAP[text_lower], 1.0

    # Check cache for fuzzy match result
    cache_key = (text_lower, threshold)
    if cache_key in _fuzzy_match_cache:
        return _fuzzy_match_cache[cache_key]

    # Compute fuzzy match
    best_match = None
    best_score = 0.0

    for stat_key, aliases in vocabulary.items():
        for alias in aliases:
            # Fuzzy match
            ratio = SequenceMatcher(None, text_lower, alias.lower()).ratio()
            if ratio > best_score and ratio >= threshold:
                best_score = ratio
                best_match = stat_key

    # Cache the result (limit cache size to prevent memory issues)
    if len(_fuzzy_match_cache) < 10000:
        _fuzzy_match_cache[cache_key] = (best_match, best_score)

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
    pct_match = _RE_STAT_PCT.search(line)
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
    flat_match = _RE_STAT_FLAT.search(line)
    if flat_match:
        stat_text = flat_match.group(1).strip()
        value_str = flat_match.group(2).replace(',', '')
        try:
            value = float(value_str)
        except ValueError:
            return None

        # Sanity check: potential line values should be reasonable
        # - Percentage stats: typically 1-20% (max 30% for high tiers)
        # - Flat main stats (STR/DEX/INT/LUK): typically 50-800
        # - Values > 1000 are almost certainly OCR misreads (like HP values)
        if value > 999:
            return None  # Reject unreasonable values

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
    match = _RE_PITY.search(text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def parse_stars(text: str) -> int:
    """
    Parse star count from text like "★18" or "18★" or "☆18".
    """
    match = _RE_STAR.search(text)
    if match:
        return int(match.group(1) or match.group(2))
    return 0


def count_stars_from_image(image_bytes: bytes) -> int:
    """
    Count filled stars from equipment screenshot by detecting orange star pixels.
    This is a simpler version that delegates to count_stars_precise.

    Star layout:
    - Row 1: Stars 1-15 (3 groups of 5)
    - Row 2: Stars 16-25 (2 groups of 5)

    Returns:
        Number of filled stars (0-25)
    """
    return count_stars_precise(image_bytes)


def find_star_region(img_array: np.ndarray) -> Optional[dict]:
    """
    Find the star region in an equipment screenshot by detecting gold pixels.

    Stars are golden/yellow colored (R>220, G>180, B<120) and appear in the
    top portion of the image.

    Returns:
        dict with 'y_min', 'y_max', 'x_min', 'x_max', 'gold_pixels' or None if not found
    """
    height, width = img_array.shape[:2]

    # Scan top 15% of image for gold pixels (stars are always near the top)
    scan_height = int(height * 0.15)
    top_region = img_array[:scan_height, :]

    # Gold star color detection: bright yellow/gold
    gold_mask = (top_region[:, :, 0] > 220) & (top_region[:, :, 1] > 180) & (top_region[:, :, 2] < 120)
    total_gold = np.sum(gold_mask)

    if total_gold < 50:  # Need minimum gold pixels to be considered stars
        return None

    # Find bounding box of gold pixels
    gold_positions = np.argwhere(gold_mask)
    if len(gold_positions) == 0:
        return None

    y_coords = gold_positions[:, 0]
    x_coords = gold_positions[:, 1]

    return {
        'y_min': int(y_coords.min()),
        'y_max': int(y_coords.max()),
        'x_min': int(x_coords.min()),
        'x_max': int(x_coords.max()),
        'gold_pixels': total_gold,
    }


def count_stars_precise(image_bytes: bytes) -> int:
    """
    Count filled stars by detecting gold pixels in the star region.

    Uses adaptive detection that analyzes each row separately:
    - Row 1: 15 stars (detects by checking if gold pixels span the full row)
    - Row 2: 10 stars (detects filled stars by x-position coverage)

    Star layout (from game):
    - Row 1: 15 stars in 3 groups of 5 (★1-15)
    - Row 2: 10 stars in 2 groups of 5 (★16-25)
    - Total: 25 stars max

    Returns:
        Number of filled stars (0-25)
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')

        img_array = np.array(image)
        height, width = img_array.shape[:2]

        # Scan top 20% for gold pixels
        scan_height = int(height * 0.20)
        top_region = img_array[:scan_height, :]

        # Gold star color detection (stricter B<100 to avoid false positives)
        gold_mask = (top_region[:, :, 0] > 220) & (top_region[:, :, 1] > 180) & (top_region[:, :, 2] < 100)
        gold_positions = np.argwhere(gold_mask)

        if len(gold_positions) < 50:
            return 0

        y_coords = gold_positions[:, 0]
        x_coords = gold_positions[:, 1]

        # Find star rows by looking for Y positions with gold pixels
        # Stars form two distinct horizontal bands with a gap between them
        unique_y, y_counts = np.unique(y_coords, return_counts=True)

        # Find rows with ANY gold pixels (>20 to filter noise)
        active_rows = unique_y[y_counts > 20]

        if len(active_rows) == 0:
            return min(25, max(0, round(len(gold_positions) / 175)))

        # Find the largest gap in active rows to separate Row 1 and Row 2
        # Star rows are contiguous, with a ~15-20px gap between Row 1 and Row 2
        row_gaps = np.diff(active_rows)

        if len(row_gaps) > 0:
            max_gap_idx = np.argmax(row_gaps)
            max_gap = row_gaps[max_gap_idx]

            # If there's a significant gap (>10px), use it to split rows
            if max_gap > 10:
                row1_y_max = active_rows[max_gap_idx]
                row2_y_min = active_rows[max_gap_idx + 1]
                y_threshold = (row1_y_max + row2_y_min) // 2
            else:
                # No clear gap - all stars might be in Row 1 only
                y_threshold = active_rows.max() + 1  # Everything is Row 1
        else:
            y_threshold = active_rows[0] + 1  # Single row

        row1_mask = y_coords <= y_threshold
        row2_mask = y_coords > y_threshold

        row1_x = x_coords[row1_mask]
        row2_x = x_coords[row2_mask]

        # Count Row 1 stars (15 max)
        row1_stars = 0
        if len(row1_x) > 50:
            row1_x_min, row1_x_max = row1_x.min(), row1_x.max()
            row1_span = row1_x_max - row1_x_min

            if row1_span > 0:
                # Divide into 15 bins (one per star position)
                bin_width = row1_span / 15
                for i in range(15):
                    bin_start = row1_x_min + i * bin_width
                    bin_end = bin_start + bin_width
                    count = np.sum((row1_x >= bin_start) & (row1_x < bin_end))
                    # Star is filled if bin has significant gold pixels
                    if count > 30:
                        row1_stars += 1

        # Count Row 2 stars (10 max)
        row2_stars = 0
        if len(row2_x) > 20:
            row2_x_min, row2_x_max = row2_x.min(), row2_x.max()
            row2_span = row2_x_max - row2_x_min

            # Row 2 uses same star width as Row 1
            if len(row1_x) > 0 and row1_span > 0:
                star_width = row1_span / 15
            else:
                star_width = 27  # Default fallback

            # Estimate Row 2 filled stars based on span
            row2_stars = min(10, max(0, round(row2_span / star_width)))

        total_stars = row1_stars + row2_stars
        return min(25, max(0, total_stars))

    except Exception:
        return 0


def detect_tier(text: str) -> Optional[str]:
    """Detect potential tier from text."""
    text_lower = text.lower()
    for tier in TIER_VOCABULARY:
        if tier.lower() in text_lower:
            return tier
    return None


def is_yellow_text(img_array: np.ndarray, bbox: List[List[float]]) -> bool:
    """
    Detect if text at a bounding box is yellow (max roll) or grey (lower tier).

    Yellow potential lines have bright yellow/gold text (R>200, G>180, B<120).
    Grey potential lines have grey text (R≈G≈B, typically 150-200 range).

    Args:
        img_array: NumPy array of the full image (RGB)
        bbox: Bounding box from OCR [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

    Returns:
        True if text is yellow (max roll), False if grey or uncertain
    """
    try:
        # Get bounding box coordinates
        x_coords = [p[0] for p in bbox]
        y_coords = [p[1] for p in bbox]
        x_min, x_max = int(min(x_coords)), int(max(x_coords))
        y_min, y_max = int(min(y_coords)), int(max(y_coords))

        # Ensure bounds are within image
        height, width = img_array.shape[:2]
        x_min = max(0, x_min)
        x_max = min(width, x_max)
        y_min = max(0, y_min)
        y_max = min(height, y_max)

        if x_max <= x_min or y_max <= y_min:
            return False

        # Extract the text region
        region = img_array[y_min:y_max, x_min:x_max]

        if region.size == 0:
            return False

        # Yellow detection: look for pixels with high R, medium-high G, low B
        # Yellow text: R > 200, G > 150, B < 120
        r, g, b = region[:, :, 0], region[:, :, 1], region[:, :, 2]

        # Count yellow-ish pixels (more permissive threshold for text)
        yellow_mask = (r > 180) & (g > 140) & (b < 140) & (r > b + 60)
        yellow_count = np.sum(yellow_mask)

        # Count grey pixels (R ≈ G ≈ B)
        grey_mask = (np.abs(r.astype(int) - g.astype(int)) < 30) & \
                    (np.abs(g.astype(int) - b.astype(int)) < 30) & \
                    (r > 100) & (r < 220)
        grey_count = np.sum(grey_mask)

        total_pixels = region.shape[0] * region.shape[1]

        # If we have significant yellow pixels relative to grey, it's yellow text
        yellow_ratio = yellow_count / total_pixels if total_pixels > 0 else 0
        grey_ratio = grey_count / total_pixels if total_pixels > 0 else 0

        # Yellow text typically has 5-15% yellow pixels in the region
        # Grey text has mostly grey background with grey text
        # If yellow ratio is notably higher than baseline, it's yellow
        return yellow_ratio > 0.03 and yellow_ratio > grey_ratio * 0.3

    except Exception:
        return False


def detect_potential_line_color(img_array: np.ndarray, item: dict) -> bool:
    """
    Wrapper to detect if a potential line item is yellow or grey.

    Args:
        img_array: NumPy array of the full image (RGB)
        item: OCR item dict with 'bbox' key

    Returns:
        True if yellow (max roll), False if grey
    """
    bbox = item.get('bbox')
    if bbox is None:
        return False
    return is_yellow_text(img_array, bbox)


# Tier color definitions (approximate RGB values for tier text)
# These are the colors used for potential tier labels in the game
TIER_COLORS = {
    "Mystic": {"r_min": 180, "r_max": 255, "g_min": 0, "g_max": 100, "b_min": 0, "b_max": 100},      # Red
    "Legendary": {"r_min": 0, "r_max": 150, "g_min": 180, "g_max": 255, "b_min": 0, "b_max": 150},   # Green
    "Unique": {"r_min": 200, "r_max": 255, "g_min": 150, "g_max": 220, "b_min": 0, "b_max": 100},    # Yellow/Gold
    "Epic": {"r_min": 130, "r_max": 200, "g_min": 0, "g_max": 100, "b_min": 180, "b_max": 255},      # Purple
    "Rare": {"r_min": 0, "r_max": 150, "g_min": 150, "g_max": 255, "b_min": 200, "b_max": 255},      # Cyan/Light Blue
}


def detect_tier_from_color(img_array: np.ndarray, bbox: List[List[float]]) -> Optional[str]:
    """
    Detect potential tier from the color of tier text.

    Tier colors:
    - Mystic: Red
    - Legendary: Green
    - Unique: Yellow/Gold
    - Epic: Purple
    - Rare: Cyan/Light Blue

    Args:
        img_array: NumPy array of the full image (RGB)
        bbox: Bounding box from OCR [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

    Returns:
        Detected tier name or None if uncertain
    """
    try:
        # Get bounding box coordinates
        x_coords = [p[0] for p in bbox]
        y_coords = [p[1] for p in bbox]
        x_min, x_max = int(min(x_coords)), int(max(x_coords))
        y_min, y_max = int(min(y_coords)), int(max(y_coords))

        # Ensure bounds are within image
        height, width = img_array.shape[:2]
        x_min = max(0, x_min)
        x_max = min(width, x_max)
        y_min = max(0, y_min)
        y_max = min(height, y_max)

        if x_max <= x_min or y_max <= y_min:
            return None

        # Extract the text region
        region = img_array[y_min:y_max, x_min:x_max]

        if region.size == 0:
            return None

        r, g, b = region[:, :, 0], region[:, :, 1], region[:, :, 2]

        # Count pixels matching each tier color
        best_tier = None
        best_count = 0

        for tier, colors in TIER_COLORS.items():
            mask = (
                (r >= colors["r_min"]) & (r <= colors["r_max"]) &
                (g >= colors["g_min"]) & (g <= colors["g_max"]) &
                (b >= colors["b_min"]) & (b <= colors["b_max"])
            )
            count = np.sum(mask)

            if count > best_count:
                best_count = count
                best_tier = tier

        # Require minimum pixel count to be confident
        total_pixels = region.shape[0] * region.shape[1]
        if best_count > total_pixels * 0.05:  # At least 5% of pixels match
            return best_tier

        return None

    except Exception:
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
    return bool(_RE_VALUE_PATTERN.match(text.strip()))


def parse_tier_level(text: str) -> Tuple[int, int]:
    """
    Parse tier and level from text like "T4 Lv.101" or "T4 Lv 101".
    Uses OCR error correction for common misreads.
    Returns (tier, level) or (0, 0) if not found.
    """
    # Try standard pattern first
    match = _RE_TIER_LEVEL_COMBINED.search(text)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Extract tier separately first (T followed by digit)
    tier_match = re.search(r'T(\d+)', text, re.IGNORECASE)
    tier = int(tier_match.group(1)) if tier_match else 0

    # Extract just the part after Lv and apply OCR fixes to ONLY that part
    # This avoids corrupting "T" and "Lv" themselves
    lv_match = _RE_LEVEL_AFTER_LV.search(text)
    if lv_match:
        after_lv = lv_match.group(1)
        fixed_after = fix_ocr_digits(after_lv)
        digits = _RE_DIGITS_2_3.search(fixed_after)
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
    match = _RE_LEVEL_WITH_PERIOD.search(text)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 2

    # Medium confidence: Lv XXX or LvXXX (no period)
    match = _RE_LEVEL_NO_PERIOD.search(text)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 1

    # Apply OCR digit corrections and try again
    # This handles cases like "Lvj04" -> "Lv104", "Lv.l03" -> "Lv.103"
    fixed_text = fix_ocr_digits(text)

    # Check for period pattern in fixed text
    match = _RE_LEVEL_WITH_PERIOD.search(fixed_text)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 2

    match = _RE_LEVEL_NO_PERIOD.search(fixed_text)
    if match:
        level = int(match.group(1))
        if is_valid_level(level):
            return level, 1

    # Last resort: look for Lv followed by anything, then apply fixes
    # Extract the part after Lv and fix it
    match = _RE_LEVEL_AFTER_LV.search(text)
    if match:
        after_lv = match.group(1)
        fixed_after = fix_ocr_digits(after_lv)
        # Extract just the digits (2-3 digits only for valid levels)
        digits = _RE_DIGITS_2_3.search(fixed_after)
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
    match = _RE_TIER_EXACT.match(text)
    if match:
        return int(match.group(1))

    # Also match if T is at start with other stuff after
    match = _RE_TIER_START.match(text)
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
    m_match = _RE_MILLIONS.search(text)
    if m_match:
        total += int(m_match.group(1)) * 1_000_000

    # Find thousands
    k_match = _RE_THOUSANDS.search(text)
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

    Uses ANCHOR-BASED positioning:
    1. Find "On-Equip Effect" text as the anchor
    2. Define a fixed-size bounding box relative to this anchor
    3. Only consider OCR items within this box

    The equipment info box has a consistent layout:
    - "On-Equip Effect" header at the top
    - Stats listed below in fixed order:
      - Attack (always first)
      - Max HP (always second)
      - Third stat (varies by slot)
      - Critical Rate %
      - Critical Damage %

    Args:
        ocr_items: All OCR items
        right_panel_x: X threshold - items with x > this are on the right panel

    Returns:
        Dict with base stats
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
        'normal_dmg': 0.0,
        # Job skill level bonuses
        'skill_1st': 0,
        'skill_2nd': 0,
        'skill_3rd': 0,
        'skill_4th': 0,
    }

    # ==========================================================================
    # ANCHOR DETECTION: Find "On-Equip Effect" text and "Potential Options"
    # ==========================================================================
    on_equip_marker = None
    potential_options_x = None

    for item in ocr_items:
        text_lower = item['text'].lower()
        if 'on-equip' in text_lower or 'equip effect' in text_lower:
            # Use the first (topmost) On-Equip Effect marker found
            if on_equip_marker is None or item['y'] < on_equip_marker['y']:
                on_equip_marker = item
        if 'potential option' in text_lower and potential_options_x is None:
            potential_options_x = item['x']

    if on_equip_marker is None:
        # No anchor found - can't reliably extract stats
        return stats

    anchor_x = on_equip_marker['x']
    anchor_y = on_equip_marker['y']

    # ==========================================================================
    # BOUNDING BOX relative to anchor
    # These values define the equipment stat box layout
    # ==========================================================================

    # The stat section is a box below "On-Equip Effect"
    # Layout:
    #   - Stat names are at or near anchor X position
    #   - Stat values are ~300-500px RIGHT of stat names
    #   - The gap between name and value can be 400+ pixels

    BOX_X_MIN = anchor_x - 100     # Allow left margin for stat names (some are ~60px left of anchor)
    BOX_X_MAX = anchor_x + 600     # Values can extend far right of anchor
    BOX_Y_MIN = anchor_y           # Start at anchor
    BOX_Y_MAX = anchor_y + 350     # Stats are within ~350px below

    # Use "Potential Options" X as the right boundary if found
    # This is more reliable than the midpoint calculation
    # Stat values are ALWAYS to the left of "Potential Options"
    if potential_options_x is not None:
        BOX_X_MAX = min(BOX_X_MAX, potential_options_x - 50)
    elif right_panel_x > 0:
        # Fallback to right_panel_x if Potential Options not found
        BOX_X_MAX = min(BOX_X_MAX, right_panel_x - 50)

    # Filter items strictly within the bounding box
    stat_section_items = [
        item for item in ocr_items
        if BOX_Y_MIN <= item['y'] <= BOX_Y_MAX
        and BOX_X_MIN <= item['x'] <= BOX_X_MAX
    ]

    # Sort by Y position (top to bottom) - this gives us the order of stats
    stat_section_items.sort(key=lambda x: x['y'])

    # =========================================================================
    # MAIN STATS - Fixed order: Attack, Max HP, Third Stat
    # These are the first 3 stat rows in the On-Equip section
    # =========================================================================

    # Main stat patterns - only match stats relevant to DPS
    # IMPORTANT: Use negative lookahead to avoid matching "Attack Speed" as "Attack"
    main_stat_patterns = {
        'atk': [r'\bAttack(?!\s*Speed)\b', r'\bATK\b'],  # "Attack" but NOT "Attack Speed"
        'hp': [r'\bMax HP\b', r'\bHP(?!\s*Recovery)\b'],  # "HP" but NOT "HP Recovery"
        # Third stat varies by slot
        'def': [r'\bDefense\b', r'\bDefence\b', r'\bDEF\b'],
        'accuracy': [r'\bAccuracy\b'],
        'mp': [r'\bMax MP\b', r'\bMP(?!\s*Recovery)\b'],  # "MP" but NOT "MP Recovery"
        'evasion': [r'\bEvasion\b'],
        'main_stat': [r'\bMain Stat\b'],
        # Job skill level bonuses - patterns like "1st Job Skill Level +5" or "4th Job Skill"
        'skill_1st': [r'\b1st\s*Job\s*Skill', r'\b1st\s*Job\b'],
        'skill_2nd': [r'\b2nd\s*Job\s*Skill', r'\b2nd\s*Job\b'],
        'skill_3rd': [r'\b3rd\s*Job\s*Skill', r'\b3rd\s*Job\b'],
        'skill_4th': [r'\b4th\s*Job\s*Skill', r'\b4th\s*Job\b'],
    }

    # Sub stat patterns (percentages)
    sub_stat_patterns = {
        'crit_rate': [r'\bCritical Rate\b', r'\bCrit Rate\b'],
        'crit_damage': [r'\bCritical Damage\b', r'\bCrit Damage\b'],
        'boss_dmg': [r'\bBoss Monster Damage\b', r'\bBoss Damage\b', r'\bBoss DMG\b'],
        'normal_dmg': [r'\bNormal Monster Damage\b', r'\bNormal Damage\b', r'\bNormal DMG\b'],
    }

    # Stats that are percentages
    pct_stats = {'crit_rate', 'crit_damage', 'boss_dmg', 'normal_dmg'}

    used_indices = set()

    def find_value_for_stat(stat_item, stat_key):
        """Find the numeric value for a stat on the same row."""
        item_y = stat_item['y']
        row_tolerance = 30

        for other in stat_section_items:
            other_text = other['text'].strip()
            if not other_text or other_text == stat_item['text']:
                continue

            # Value should be to the RIGHT of the stat name and on same row
            if abs(other['y'] - item_y) <= row_tolerance and other['x'] > stat_item['x']:
                if stat_key in pct_stats:
                    # Parse percentage value
                    pct_match = _RE_PCT_VALUE.search(other_text)
                    if pct_match:
                        value_str = pct_match.group(1).replace(',', '')
                        try:
                            return float(value_str)
                        except ValueError:
                            pass
                else:
                    # Parse integer value (17,231 format, NOT 79M)
                    if not _RE_MK_CHECK.search(other_text):
                        clean = other_text.replace(',', '').strip()
                        try:
                            value = int(clean)
                            if value > 0:
                                return value
                        except ValueError:
                            pass
        return None

    # Process items looking for stat names
    for i, item in enumerate(stat_section_items):
        if i in used_indices:
            continue

        text = item['text'].strip()
        if not text:
            continue

        # Check main stat patterns first
        for stat_key, patterns in main_stat_patterns.items():
            matched = False
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched = True
                    break

            if matched:
                # Try to extract value from same text first
                num_match = _RE_NUM_END.search(text)
                if num_match:
                    value_str = num_match.group(1).replace(',', '')
                    try:
                        stats[stat_key] = int(value_str)
                        used_indices.add(i)
                    except ValueError:
                        pass
                else:
                    # Find value on same row
                    value = find_value_for_stat(item, stat_key)
                    if value is not None:
                        stats[stat_key] = value
                        used_indices.add(i)
                break

        # Check sub stat patterns (percentages)
        for stat_key, patterns in sub_stat_patterns.items():
            matched = False
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched = True
                    break

            if matched:
                # Try to extract percentage from same text
                pct_match = _RE_PCT_END.search(text)
                if pct_match:
                    value_str = pct_match.group(1).replace(',', '')
                    try:
                        stats[stat_key] = float(value_str)
                        used_indices.add(i)
                    except ValueError:
                        pass
                else:
                    # Find value on same row
                    value = find_value_for_stat(item, stat_key)
                    if value is not None:
                        stats[stat_key] = value
                        used_indices.add(i)
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

    # Find "Potential Options" text position - this is the most reliable boundary
    # The potential section always starts with "Potential Options" text
    potential_options_x = None
    for item in ocr_items:
        text_lower = item['text'].lower()
        if 'potential option' in text_lower:
            potential_options_x = item['x']
            break

    # Calculate the right panel threshold
    if ocr_items:
        max_x = max(item['x'] for item in ocr_items)
        min_x = min(item['x'] for item in ocr_items)

        if potential_options_x is not None:
            # Use Potential Options X minus offset as the boundary
            # Stat names can start ~100px to the left of "Potential Options" text
            boundaries['right_panel_x'] = potential_options_x - 100
            boundaries['debug_info'].append(f"X range: {min_x:.0f}-{max_x:.0f}, Potential Options at: {potential_options_x:.0f}, threshold: {boundaries['right_panel_x']:.0f}")
        else:
            # Fallback to midpoint if "Potential Options" not found
            boundaries['right_panel_x'] = (max_x + min_x) / 2
            boundaries['debug_info'].append(f"X range: {min_x:.0f}-{max_x:.0f}, threshold: {boundaries['right_panel_x']:.0f} (midpoint fallback)")

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

        # IMPORTANT: Skip if this is an equipment header (contains slot name)
        # Equipment headers like "Legendary Gloves" should NOT be used for potential tier detection
        is_equipment_header = False
        for slot_name in EQUIPMENT_SLOT_MAP.keys():
            if slot_name in text:
                is_equipment_header = True
                boundaries['debug_info'].append(f"Skipping equipment header: '{item['text']}' (contains '{slot_name}')")
                break

        if is_equipment_header:
            continue

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
                               right_x_threshold: float,
                               img_array: Optional[np.ndarray] = None) -> Tuple[str, int, int, List[PotentialLine]]:
    """
    Extract tier, pity, and lines from a potential section.

    Uses color-based value lookup when image is provided:
    - Detects stat name via fuzzy matching
    - Detects if line is yellow (max roll) or grey (lower tier)
    - Looks up exact value from tier + color instead of parsing OCR values

    Args:
        ocr_items: All OCR items
        start_y: Y coordinate where this section starts
        end_y: Y coordinate where this section ends (HARD boundary - never match beyond this!)
        right_x_threshold: Only consider items with x > this value (right panel)
        img_array: Optional NumPy array of the image for color detection

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

    # First pass: find the tier (we need it for value lookup)
    # Use BOTH text-based AND color-based detection for reliability
    for i, item in enumerate(section_items):
        text = item['text'].strip()
        if not text:
            continue
        detected_tier = detect_tier(text)
        if detected_tier:
            # Try color-based confirmation if image is available
            if img_array is not None and item.get('bbox'):
                color_tier = detect_tier_from_color(img_array, item['bbox'])
                if color_tier:
                    # Color detection is more reliable - use it
                    tier = color_tier
                else:
                    tier = detected_tier
            else:
                tier = detected_tier
            used_indices.add(i)
            break

    # Second pass: find pity and stat lines
    for i, item in enumerate(section_items):
        text = item['text'].strip()
        if not text or i in used_indices:
            continue

        text_lower = text.lower()

        # Skip section headers that might fuzzy match stat names
        # "Bonus Potential Options" can match "def_pen" with low threshold!
        if 'potential' in text_lower or 'options' in text_lower or 'bonus' in text_lower:
            used_indices.add(i)
            continue

        # Check for tier (may have been found, but mark as used)
        detected_tier = detect_tier(text)
        if detected_tier:
            used_indices.add(i)
            continue

        # Check for pity counter
        p_current, p_max = parse_pity(text)
        if p_max > 0:
            pity_current = p_current
            pity_max = p_max
            used_indices.add(i)
            continue

        # Check if this is a stat name
        # Use higher threshold (0.6) to avoid false matches like "Bonus Potential Options" -> "def_pen"
        stat_key, conf = fuzzy_match(text, STAT_VOCABULARY, threshold=0.6)
        if stat_key:
            used_indices.add(i)

            # Try color-based value lookup if image is available
            if img_array is not None:
                is_yellow = detect_potential_line_color(img_array, item)
                lookup_value = lookup_potential_value(stat_key, tier, is_yellow)

                if lookup_value is not None:
                    # Determine if it's a percentage based on typical stat values
                    is_pct = stat_key not in ("dex_flat", "str_flat", "int_flat", "luk_flat",
                                               "all_skills", "ba_targets")
                    line = PotentialLine(
                        stat=stat_key,
                        value=lookup_value,
                        is_percentage=is_pct,
                        raw_text=f"{text} (lookup: {tier}, {'yellow' if is_yellow else 'grey'})",
                        confidence=1.0  # High confidence for lookup
                    )
                    lines.append(line)
                    continue

            # Fallback: look for value via OCR (original method)
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

    # Load image as numpy array for color detection
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != 'RGB':
        image = image.convert('RGB')
    img_array = np.array(image)

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
        if _RE_TIER_IN_TEXT.search(text):
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

    # If stars not found via OCR, try visual detection
    if parsed.stars == 0:
        visual_stars = count_stars_precise(image_bytes)
        if visual_stars > 0:
            parsed.stars = visual_stars
            parsed.debug_info.append(f"Stars from visual detection: {visual_stars}")

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
    parsed.base_normal_dmg = base_stats['normal_dmg']

    # Job skill level bonuses
    parsed.base_skill_1st = base_stats['skill_1st']
    parsed.base_skill_2nd = base_stats['skill_2nd']
    parsed.base_skill_3rd = base_stats['skill_3rd']
    parsed.base_skill_4th = base_stats['skill_4th']

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
        right_x_threshold=boundaries['right_panel_x'],
        img_array=img_array  # Pass image for color-based value lookup
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
        right_x_threshold=boundaries['right_panel_x'],
        img_array=img_array  # Pass image for color-based value lookup
    )
    parsed.bonus_tier = bonus_tier
    parsed.bonus_pity = bonus_pity
    parsed.bonus_pity_max = bonus_pity_max
    parsed.bonus_lines = bonus_lines
    parsed.debug_info.append(f"Bonus: tier={bonus_tier}, pity={bonus_pity}/{bonus_pity_max}, lines={len(bonus_lines)}")

    # Validate slot-specific stats - remove stats that can't appear on this slot
    # (e.g., def_pen on gloves is an OCR error - it only appears on shoulder)
    if parsed.equipment_slot:
        for lines, section_name in [(parsed.regular_lines, "Regular"), (parsed.bonus_lines, "Bonus")]:
            for i, line in enumerate(lines):
                if line.stat and not is_stat_valid_for_slot(line.stat, parsed.equipment_slot):
                    parsed.debug_info.append(
                        f"REMOVED {section_name} line {i+1}: {line.stat} invalid for slot '{parsed.equipment_slot}'"
                    )
                    lines[i] = PotentialLine()  # Replace with empty line

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
