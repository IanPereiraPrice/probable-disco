"""
OCR Test Script - Run this to test and improve OCR accuracy on equipment screenshots.
"""
import sys
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "streamlit_app"))

from streamlit_app.utils.ocr_scanner import extract_and_parse, get_ocr_reader

# Test photos directory
TEST_DIR = Path(__file__).parent / "OCR_test_photos"


def test_single_image(image_path: Path, verbose: bool = True):
    """Test OCR on a single image and print results."""
    print(f"\n{'='*60}")
    print(f"Testing: {image_path.name}")
    print('='*60)

    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    parsed = extract_and_parse(image_bytes)

    # Print results
    print(f"\n--- BASIC INFO ---")
    print(f"  Equipment Slot: {parsed.equipment_slot or '(not detected)'}")
    print(f"  Equipment Rarity: {parsed.equipment_rarity or '(not detected)'}")
    print(f"  Stars: {parsed.stars}")
    print(f"  Tier Level: {parsed.tier_level}")
    print(f"  Item Tier: T{parsed.item_tier}")
    print(f"  Item Level: Lv.{parsed.item_level}")

    print(f"\n--- BASE STATS ---")
    print(f"  Attack: {parsed.base_atk}")
    print(f"  Defense: {parsed.base_def}")
    print(f"  Max HP: {parsed.base_hp}")
    print(f"  Max MP: {parsed.base_mp}")
    print(f"  Main Stat: {parsed.base_main_stat}")
    print(f"  STR: {parsed.base_str}  DEX: {parsed.base_dex}  INT: {parsed.base_int}  LUK: {parsed.base_luk}")
    print(f"  Crit Rate: {parsed.base_crit_rate}%  Crit Damage: {parsed.base_crit_damage}%")
    print(f"  Accuracy: {parsed.base_accuracy}  Evasion: {parsed.base_evasion}")
    print(f"  Boss DMG: {parsed.base_boss_dmg}%")

    print(f"\n--- REGULAR POTENTIAL ({parsed.regular_tier}) ---")
    print(f"  Pity: {parsed.regular_pity}/{parsed.regular_pity_max}")
    for i, line in enumerate(parsed.regular_lines, 1):
        if line.stat:
            print(f"  Line {i}: {line.stat} = {line.value} (conf: {line.confidence:.2f})")
        else:
            print(f"  Line {i}: (empty)")

    print(f"\n--- BONUS POTENTIAL ({parsed.bonus_tier}) ---")
    print(f"  Pity: {parsed.bonus_pity}/{parsed.bonus_pity_max}")
    for i, line in enumerate(parsed.bonus_lines, 1):
        if line.stat:
            print(f"  Line {i}: {line.stat} = {line.value} (conf: {line.confidence:.2f})")
        else:
            print(f"  Line {i}: (empty)")

    if verbose:
        print(f"\n--- DEBUG INFO ---")
        for info in parsed.debug_info:
            print(f"  {info}")

        print(f"\n--- RAW OCR TEXT ---")
        for text in parsed.raw_text[:30]:  # First 30 items
            print(f"  {text}")
        if len(parsed.raw_text) > 30:
            print(f"  ... ({len(parsed.raw_text) - 30} more)")

    print(f"\n  Overall Parse Confidence: {parsed.parse_confidence*100:.0f}%")

    return parsed


def test_all_images(verbose: bool = False):
    """Test all images in the test directory."""
    if not TEST_DIR.exists():
        print(f"Test directory not found: {TEST_DIR}")
        return

    images = list(TEST_DIR.glob("*.png")) + list(TEST_DIR.glob("*.jpg"))

    if not images:
        print(f"No images found in {TEST_DIR}")
        return

    print(f"Found {len(images)} test images")

    # Initialize OCR reader once
    print("Initializing OCR reader...")
    get_ocr_reader()
    print("OCR reader ready!\n")

    results = []
    for image_path in sorted(images):
        parsed = test_single_image(image_path, verbose=verbose)
        results.append({
            'file': image_path.name,
            'slot': parsed.equipment_slot,
            'rarity': parsed.equipment_rarity,
            'stars': parsed.stars,
            'tier': parsed.item_tier,
            'level': parsed.item_level,
            'regular_lines': sum(1 for l in parsed.regular_lines if l.stat),
            'bonus_lines': sum(1 for l in parsed.bonus_lines if l.stat),
            'confidence': parsed.parse_confidence,
        })

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'File':<40} {'Slot':<10} {'T':<3} {'Lv':<4} {'Reg':<4} {'Bon':<4} {'Conf':<6}")
    print("-"*60)
    for r in results:
        print(f"{r['file'][:38]:<40} {r['slot'] or '?':<10} T{r['tier']:<2} {r['level']:<4} {r['regular_lines']}/3  {r['bonus_lines']}/3  {r['confidence']*100:.0f}%")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test OCR on equipment screenshots")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug info and raw OCR text")
    parser.add_argument("-f", "--file", type=str, help="Test a specific file")
    args = parser.parse_args()

    if args.file:
        test_single_image(Path(args.file), verbose=True)
    else:
        test_all_images(verbose=args.verbose)
