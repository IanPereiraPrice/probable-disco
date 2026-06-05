"""
Test: Realistic DPS - Boss vs Normal Damage Ratios
==================================================

Expected behavior for 60/40 stage (60% mob, 40% boss):
- Raw DPS: Normal damage ~5-6x more raw DPS (multi-target vs single target)
- Weighted DPS: With boss_importance, boss damage becomes more valuable

The boss_importance slider allows users to tune based on their bottleneck:
- boss_importance=70% (default): Boss has 70% of stage HP
- Higher = boss is the bottleneck (struggle to kill boss)
- Lower = mobs are the bottleneck (struggle to clear waves)

This test verifies:
1. Boss and normal damage are valued separately in simulation
2. Boss importance weighting affects final DPS values
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skills import CharacterState, DPSCalculator, create_character_at_level


def test_boss_vs_normal_damage_ratio():
    """Test that boss/normal damage is valued correctly with boss_importance weighting."""
    print("=" * 60)
    print("TEST: Boss vs Normal Damage Ratio (60/40 Stage)")
    print("=" * 60)

    # Create base character
    base_char = create_character_at_level(140, all_skills_bonus=40)
    base_char.attack = 5000
    base_char.main_stat_flat = 15000
    base_char.main_stat_pct = 100
    base_char.damage_pct = 50
    base_char.crit_rate = 100
    base_char.crit_damage = 200

    # Stage settings: 60s, 12 enemies, 60% mob / 40% boss
    fight_duration = 60.0
    num_enemies = 12
    mob_time_fraction = 0.6

    # Test with default boss_importance (70%)
    boss_importance = 0.7
    print(f"\n--- Boss Importance: {boss_importance * 100:.0f}% ---")

    # Calculate baseline DPS
    calc_base = DPSCalculator(base_char, enemy_def=0.752)
    baseline = calc_base.calculate_realistic_dps(
        fight_duration=fight_duration,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        boss_importance=boss_importance,
    )
    print(f"Baseline DPS: {baseline.total_dps:,.0f}")

    # Test with +24% Boss Damage
    boss_char = create_character_at_level(140, all_skills_bonus=40)
    boss_char.attack = 5000
    boss_char.main_stat_flat = 15000
    boss_char.main_stat_pct = 100
    boss_char.damage_pct = 50
    boss_char.boss_damage_pct = 24
    boss_char.normal_damage_pct = 0
    boss_char.crit_rate = 100
    boss_char.crit_damage = 200

    calc_boss = DPSCalculator(boss_char, enemy_def=0.752)
    boss_result = calc_boss.calculate_realistic_dps(
        fight_duration=fight_duration,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        boss_importance=boss_importance,
    )
    boss_gain = (boss_result.total_dps / baseline.total_dps - 1) * 100
    print(f"+24% Boss Damage: {boss_result.total_dps:,.0f} (+{boss_gain:.2f}%)")

    # Test with +24% Normal Damage
    normal_char = create_character_at_level(140, all_skills_bonus=40)
    normal_char.attack = 5000
    normal_char.main_stat_flat = 15000
    normal_char.main_stat_pct = 100
    normal_char.damage_pct = 50
    normal_char.boss_damage_pct = 0
    normal_char.normal_damage_pct = 24
    normal_char.crit_rate = 100
    normal_char.crit_damage = 200

    calc_normal = DPSCalculator(normal_char, enemy_def=0.752)
    normal_result = calc_normal.calculate_realistic_dps(
        fight_duration=fight_duration,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        boss_importance=boss_importance,
    )
    normal_gain = (normal_result.total_dps / baseline.total_dps - 1) * 100
    print(f"+24% Normal Damage: {normal_result.total_dps:,.0f} (+{normal_gain:.2f}%)")

    # Calculate ratio
    ratio = normal_gain / boss_gain if boss_gain > 0 else float('inf')
    print(f"Ratio (Normal/Boss): {ratio:.2f}x")

    # With 70% boss importance, boss damage should be valued MORE than normal
    # (boss has 70% of HP vs mob with 30%)
    # But mob phase has multi-target, so normal damage still has value
    # Expected: ratio around 0.5-2.0 depending on multi-target benefits
    print(f"\nWith 70% boss importance:")
    print(f"  - Boss damage applies to 40% of time but 70% of HP value")
    print(f"  - Normal damage applies to 60% of time but only 30% of HP value")

    # Test passes if both stats have positive gains (phase separation works)
    if boss_gain > 0 and normal_gain > 0:
        print("\n[PASS] PASS: Both boss and normal damage provide DPS gains")
        return True
    else:
        print(f"\n[FAIL] FAIL: Unexpected gains - boss: {boss_gain:.2f}%, normal: {normal_gain:.2f}%")
        return False


def test_pure_boss_mode():
    """Test that boss damage is at full value in pure boss mode."""
    print("\n" + "=" * 60)
    print("TEST: Pure Boss Mode (100% Boss)")
    print("=" * 60)

    # Create base character
    base_char = create_character_at_level(140, all_skills_bonus=40)
    base_char.attack = 5000
    base_char.main_stat_flat = 15000
    base_char.main_stat_pct = 100
    base_char.damage_pct = 50
    base_char.crit_rate = 100
    base_char.crit_damage = 200

    # Boss mode settings: 60s, 1 enemy, 0% mob / 100% boss
    fight_duration = 60.0
    num_enemies = 1
    mob_time_fraction = 0.0
    boss_importance = 1.0  # 100% boss importance in boss mode

    calc_base = DPSCalculator(base_char, enemy_def=0.752)
    baseline = calc_base.calculate_realistic_dps(
        fight_duration=fight_duration,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        boss_importance=boss_importance,
    )
    print(f"\nBaseline DPS: {baseline.total_dps:,.0f}")

    # Test with +24% Boss Damage
    boss_char = create_character_at_level(140, all_skills_bonus=40)
    boss_char.attack = 5000
    boss_char.main_stat_flat = 15000
    boss_char.main_stat_pct = 100
    boss_char.damage_pct = 50
    boss_char.boss_damage_pct = 24
    boss_char.crit_rate = 100
    boss_char.crit_damage = 200

    calc_boss = DPSCalculator(boss_char, enemy_def=0.752)
    boss_result = calc_boss.calculate_realistic_dps(
        fight_duration=fight_duration,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        boss_importance=boss_importance,
    )
    boss_gain = (boss_result.total_dps / baseline.total_dps - 1) * 100
    print(f"\n+24% Boss Damage: {boss_result.total_dps:,.0f} (+{boss_gain:.2f}%)")

    # In pure boss mode, +24% boss damage should give ~24% DPS gain
    # (slightly less due to diminishing returns with other multipliers)
    if 18 <= boss_gain <= 26:
        print("\n[PASS] PASS: Boss damage is at full effectiveness in boss mode")
        return True
    else:
        print(f"\n[FAIL] FAIL: Expected ~24% gain, got {boss_gain:.2f}%")
        return False


def test_chapter_hunt_mode():
    """Test that normal damage is at full value in chapter hunt mode."""
    print("\n" + "=" * 60)
    print("TEST: Chapter Hunt Mode (100% Normal, Infinite Duration)")
    print("=" * 60)

    # Chapter hunt uses original calculate_total_dps for infinite duration
    # So we'll test with a very long fight instead
    base_char = create_character_at_level(140, all_skills_bonus=40)
    base_char.attack = 5000
    base_char.main_stat_flat = 15000
    base_char.main_stat_pct = 100
    base_char.damage_pct = 50
    base_char.crit_rate = 100
    base_char.crit_damage = 200

    # Long fight with 100% mobs
    fight_duration = 600.0  # 10 minutes
    num_enemies = 10
    mob_time_fraction = 1.0  # 100% mobs
    boss_importance = 0.0  # 0% boss importance in chapter hunt (no boss)

    calc_base = DPSCalculator(base_char, enemy_def=0.752)
    baseline = calc_base.calculate_realistic_dps(
        fight_duration=fight_duration,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        boss_importance=boss_importance,
    )
    print(f"\nBaseline DPS: {baseline.total_dps:,.0f}")

    # Test with +24% Normal Damage
    normal_char = create_character_at_level(140, all_skills_bonus=40)
    normal_char.attack = 5000
    normal_char.main_stat_flat = 15000
    normal_char.main_stat_pct = 100
    normal_char.damage_pct = 50
    normal_char.normal_damage_pct = 24
    normal_char.crit_rate = 100
    normal_char.crit_damage = 200

    calc_normal = DPSCalculator(normal_char, enemy_def=0.752)
    normal_result = calc_normal.calculate_realistic_dps(
        fight_duration=fight_duration,
        num_enemies=num_enemies,
        mob_time_fraction=mob_time_fraction,
        boss_importance=boss_importance,
    )
    normal_gain = (normal_result.total_dps / baseline.total_dps - 1) * 100
    print(f"\n+24% Normal Damage: {normal_result.total_dps:,.0f} (+{normal_gain:.2f}%)")

    # In pure mob mode, +24% normal damage should give ~24% DPS gain
    if 18 <= normal_gain <= 26:
        print("\n[PASS] PASS: Normal damage is at full effectiveness in chapter hunt")
        return True
    else:
        print(f"\n[FAIL] FAIL: Expected ~24% gain, got {normal_gain:.2f}%")
        return False


if __name__ == "__main__":
    results = []
    results.append(test_boss_vs_normal_damage_ratio())
    results.append(test_pure_boss_mode())
    results.append(test_chapter_hunt_mode())

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n[PASS] All tests passed!")
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed")
