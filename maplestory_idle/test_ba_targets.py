"""Test BA targets DPS calculation."""
import sys
sys.path.insert(0, '.')

from skills import create_character_at_level, DPSCalculator

# Test with 12 enemies (standard for stages) to see BA target effect
NUM_ENEMIES = 12
MOB_FRACTION = 0.6

print(f"Testing with {NUM_ENEMIES} enemies, {MOB_FRACTION*100:.0f}% mob time fraction")
print()

# Test 1: BA with 0 bonus targets (base 6 targets)
char1 = create_character_at_level(140, 44)
char1.attack = 50000
char1.crit_damage = 200
char1.crit_rate = 70
char1.attack_speed_pct = 50
char1.ba_target_bonus = 0

calc1 = DPSCalculator(char1)
result1 = calc1.calculate_total_dps(num_enemies=NUM_ENEMIES, mob_time_fraction=MOB_FRACTION)

# Test 2: BA with +3 bonus targets (base 6 + 3 = 9 targets)
char2 = create_character_at_level(140, 44)
char2.attack = 50000
char2.crit_damage = 200
char2.crit_rate = 70
char2.attack_speed_pct = 50
char2.ba_target_bonus = 3

calc2 = DPSCalculator(char2)
result2 = calc2.calculate_total_dps(num_enemies=NUM_ENEMIES, mob_time_fraction=MOB_FRACTION)

print(f'BA targets +0 (6 targets): Total DPS = {result1.total_dps:,.0f}, BA DPS = {result1.basic_attack_dps:,.0f}')
print(f'BA targets +3 (9 targets): Total DPS = {result2.total_dps:,.0f}, BA DPS = {result2.basic_attack_dps:,.0f}')
print(f'DPS increase from +3 BA targets: {((result2.total_dps / result1.total_dps) - 1) * 100:.2f}%')
print(f'BA portion of total: +0 = {result1.basic_attack_dps / result1.total_dps * 100:.1f}%, +3 = {result2.basic_attack_dps / result2.total_dps * 100:.1f}%')

# Check how get_skill_targets works
print()
print("Debug - checking target calculations:")
print(f"  calc1 BA targets: {calc1.get_skill_targets('arrow_stream')}")
print(f"  calc2 BA targets: {calc2.get_skill_targets('arrow_stream')}")
print(f"  calc1 effective BA targets (12 enemies, 0.6 mob): {calc1.get_effective_targets('arrow_stream', NUM_ENEMIES, MOB_FRACTION):.2f}")
print(f"  calc2 effective BA targets (12 enemies, 0.6 mob): {calc2.get_effective_targets('arrow_stream', NUM_ENEMIES, MOB_FRACTION):.2f}")
