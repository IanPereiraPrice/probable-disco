"""
OCR Unit Tests - Validates OCR parsing against expected values for test images.

Run with: python test_ocr_unit.py
"""
import sys
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "streamlit_app"))

from streamlit_app.utils.ocr_scanner import extract_and_parse, get_ocr_reader

# Test photos directory
TEST_DIR = Path(__file__).parent / "OCR_test_photos"

# Expected values for each test image
# Format: filename -> expected values dict
# base_stats_min: minimum number of non-zero base stats expected
EXPECTED_VALUES = {
    "Screenshot 2026-01-08 231325.png": {
        "slot": "face",
        "level_min": 100,
        "level_max": 110,
        "tier": 4,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,  # May not have base stats visible
    },
    "Screenshot 2026-01-09 124026.png": {
        "slot": "top",
        "level_min": 100,
        "level_max": 110,
        "tier": 1,  # T1 equipment
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
    "Screenshot 2026-01-09 124047.png": {
        "slot": "bottom",
        "level_min": 100,
        "level_max": 110,
        "tier": 4,  # OCR reads "T4_lvdoo"
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 3,  # ATK, HP, Crit Rate visible in On-Equip Effect section
    },
    "Screenshot 2026-01-09 124057.png": {
        "slot": "gloves",
        "level_min": 80,
        "level_max": 110,
        "tier": 4,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
    "Screenshot 2026-01-09 124109.png": {
        "slot": "ring",
        "level_min": 80,
        "level_max": 110,
        "tier": 4,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
    "Screenshot 2026-01-09 124123.png": {
        "slot": "necklace",
        "level_min": 100,
        "level_max": 110,
        "tier": 4,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
    "Screenshot 2026-01-09 124132.png": {
        "slot": "shoes",
        "level_min": 100,
        "level_max": 110,
        "tier": 3,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
    "Screenshot 2026-01-09 124141.png": {
        "slot": "belt",
        "level_min": 100,
        "level_max": 110,
        "tier": 2,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
    "Screenshot 2026-01-09 124149.png": {
        "slot": "shoulder",
        "level_min": 100,
        "level_max": 110,
        "tier": 1,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
    "Screenshot 2026-01-09 124159.png": {
        "slot": "cape",  # Fixed: image shows "Cape Slot Enhancement Effect"
        "level_min": 100,
        "level_max": 110,
        "tier": 4,
        "regular_lines": 3,
        "bonus_lines": 3,
        "base_stats_min": 0,
    },
}


def run_tests(verbose: bool = False):
    """Run all OCR unit tests and report results."""
    if not TEST_DIR.exists():
        print(f"ERROR: Test directory not found: {TEST_DIR}")
        return False

    # Initialize OCR reader once
    print("Initializing OCR reader...")
    get_ocr_reader()
    print("OCR reader ready!\n")

    images = list(TEST_DIR.glob("*.png")) + list(TEST_DIR.glob("*.jpg"))
    if not images:
        print(f"ERROR: No images found in {TEST_DIR}")
        return False

    print(f"Running {len(images)} tests...\n")
    print("=" * 70)

    passed = 0
    failed = 0
    results = []

    for image_path in sorted(images):
        filename = image_path.name
        expected = EXPECTED_VALUES.get(filename)

        if not expected:
            print(f"SKIP: {filename} (no expected values defined)")
            continue

        # Run OCR
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        parsed = extract_and_parse(image_bytes)

        # Check each expected value
        errors = []

        # Slot check
        if parsed.equipment_slot != expected["slot"]:
            errors.append(f"slot: got '{parsed.equipment_slot}', expected '{expected['slot']}'")

        # Level check (within range)
        if not (expected["level_min"] <= parsed.item_level <= expected["level_max"]):
            errors.append(f"level: got {parsed.item_level}, expected {expected['level_min']}-{expected['level_max']}")

        # Tier check
        if parsed.item_tier != expected["tier"]:
            errors.append(f"tier: got T{parsed.item_tier}, expected T{expected['tier']}")

        # Regular lines count
        reg_count = sum(1 for l in parsed.regular_lines if l.stat)
        if reg_count != expected["regular_lines"]:
            errors.append(f"regular_lines: got {reg_count}/3, expected {expected['regular_lines']}/3")

        # Bonus lines count
        bon_count = sum(1 for l in parsed.bonus_lines if l.stat)
        if bon_count != expected["bonus_lines"]:
            errors.append(f"bonus_lines: got {bon_count}/3, expected {expected['bonus_lines']}/3")

        # Base stats count (ATK, DEF, HP, MP, crit_rate, crit_damage, etc.)
        base_stats_count = sum(1 for v in [
            parsed.base_atk, parsed.base_def, parsed.base_hp, parsed.base_mp,
            parsed.base_crit_rate, parsed.base_crit_damage
        ] if v > 0)
        if base_stats_count < expected.get("base_stats_min", 0):
            errors.append(f"base_stats: got {base_stats_count}, expected >= {expected['base_stats_min']}")

        # Report result
        if errors:
            failed += 1
            status = "FAIL"
            results.append((filename, False, errors, parsed))
        else:
            passed += 1
            status = "PASS"
            results.append((filename, True, [], parsed))

        # Print summary line (use ASCII for Windows compatibility)
        slot_ok = "OK" if parsed.equipment_slot == expected["slot"] else "X"
        level_ok = "OK" if expected["level_min"] <= parsed.item_level <= expected["level_max"] else "X"
        tier_ok = "OK" if parsed.item_tier == expected["tier"] else "X"
        reg_ok = "OK" if reg_count == expected["regular_lines"] else "X"
        bon_ok = "OK" if bon_count == expected["bonus_lines"] else "X"

        print(f"{status}: {filename[:40]:<40}")
        print(f"      Slot:{slot_ok} Level:{level_ok}(Lv.{parsed.item_level}) Tier:{tier_ok}(T{parsed.item_tier}) Reg:{reg_ok}({reg_count}/3) Bon:{bon_ok}({bon_count}/3)")

        if errors and verbose:
            for err in errors:
                print(f"      -> {err}")

        print()

    # Summary
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 70)

    # Show failures in detail
    if failed > 0:
        print("\nFAILED TESTS DETAIL:")
        for filename, success, errors, parsed in results:
            if not success:
                print(f"\n  {filename}:")
                for err in errors:
                    print(f"    - {err}")

    return failed == 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run OCR unit tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed error info")
    args = parser.parse_args()

    success = run_tests(verbose=args.verbose)
    sys.exit(0 if success else 1)
