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


def is_value_pattern(text: str) -> bool:
    """Check if text looks like a stat value (number with optional %)."""
    return bool(re.match(r'^[\d,.]+%?$', text.strip()))


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

    Returns dict with 'regular_start_y', 'bonus_start_y', 'right_panel_x', 'debug_info'
    """
    boundaries = {
        'regular_start_y': 0,
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

    # First pass: look for "Bonus" marker
    for item in ocr_items:
        text = item['text'].lower()
        y = item['y']

        # Find "Bonus" section marker
        if 'bonus' in text:
            boundaries['bonus_start_y'] = y
            boundaries['debug_info'].append(f"Found 'bonus' at y={y:.0f}: '{item['text']}'")
            break

    # Second pass: find first tier name (start of regular potential)
    tier_items = []
    for item in ocr_items:
        text = item['text'].lower()
        for tier in TIER_VOCABULARY:
            if tier.lower() in text:
                tier_items.append((item['y'], item['text']))
                break

    if tier_items:
        # First tier is regular potential, second is bonus
        tier_items.sort(key=lambda x: x[0])
        boundaries['regular_start_y'] = tier_items[0][0] - 10  # Slight offset before tier
        boundaries['debug_info'].append(f"Found tier at y={tier_items[0][0]:.0f}: '{tier_items[0][1]}'")

        if len(tier_items) >= 2:
            # If we found two tiers, the second one is the bonus section
            boundaries['bonus_start_y'] = tier_items[1][0] - 10
            boundaries['debug_info'].append(f"Second tier at y={tier_items[1][0]:.0f}: '{tier_items[1][1]}'")

    return boundaries


def extract_potential_section(ocr_items: List[dict], start_y: float, end_y: float,
                               right_x_threshold: float) -> Tuple[str, int, int, List[PotentialLine]]:
    """
    Extract tier, pity, and lines from a potential section.

    Args:
        ocr_items: All OCR items
        start_y: Y coordinate where this section starts
        end_y: Y coordinate where this section ends
        right_x_threshold: Only consider items with x > this value (right panel)

    Returns:
        (tier, pity_current, pity_max, lines)
    """
    # Filter items in this section and on the right side
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

        # Check if this is a stat name
        stat_key, conf = fuzzy_match(text, STAT_VOCABULARY, threshold=0.7)
        if stat_key:
            # Look for value in nearby items
            for j in range(i + 1, min(i + 3, len(section_items))):
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

        # Check if this is a value pattern - look backwards for stat name
        if is_value_pattern(text):
            for j in range(i - 1, max(i - 3, -1), -1):
                if j in used_indices:
                    continue
                prev_text = section_items[j]['text'].strip()
                stat_key, conf = fuzzy_match(prev_text, STAT_VOCABULARY, threshold=0.7)
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

    # Extract stars from anywhere (usually on the left side but still useful)
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

        # Extract tier level (T4 Lv.101)
        if re.search(r'T\d+.*Lv', text, re.IGNORECASE):
            parsed.tier_level = text

    # Get image height for section end boundary
    max_y = max(item['y'] for item in all_items) if all_items else 1000

    # Extract Regular Potential section
    parsed.debug_info.append(f"Regular section: y={boundaries['regular_start_y']:.0f} to {boundaries['bonus_start_y']:.0f}")
    regular_tier, regular_pity, regular_pity_max, regular_lines = extract_potential_section(
        all_items,
        start_y=boundaries['regular_start_y'],
        end_y=boundaries['bonus_start_y'],
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
