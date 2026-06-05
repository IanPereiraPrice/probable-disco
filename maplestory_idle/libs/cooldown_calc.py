"""
Unified Cooldown and Trigger Calculations
==========================================

Core function: calculate_triggers()
Returns the number of times an ability triggers in a fight (can be fractional).

Key insight: Cooldown starts when you ACTIVATE the ability, not when it ends.

Usage:
    triggers = calculate_triggers(cooldown=40, duration=5, fight_duration=60)
    # Returns 2.0 (triggers at t=0 and t=40, both complete)

    # For buffs: uptime = triggers * buff_duration / fight_duration
    # For attacks: total_damage = triggers * damage_per_use
"""

import math


def calculate_triggers(
    cooldown: float,
    duration: float,
    fight_duration: float,
) -> float:
    """
    Calculate the number of triggers (including partial) for an ability.

    An ability triggers at t=0, then every `cooldown` seconds.
    If the ability has a `duration` (cast time or buff time), the last trigger
    may be cut off if it extends past the fight end.

    Args:
        cooldown: Time between ability activations (seconds).
                  Use 0 for spammable abilities (no cooldown).
                  Use float('inf') for one-time abilities.
        duration: How long each trigger lasts (seconds).
                  For buffs: buff duration
                  For attacks: cast/channel time
        fight_duration: Total fight duration (seconds).
                        Use float('inf') for steady-state calculations.

    Returns:
        Number of triggers (float). Can be fractional if last trigger is cut off.

    Examples:
        # Hurricane: 40s CD, 2.5s cast, 60s fight
        >>> calculate_triggers(40, 2.5, 60)
        2.0  # Triggers at t=0 and t=40, both complete

        # Charm of Undead: 10s CD, 5s buff, 32s fight
        >>> calculate_triggers(10, 5, 32)
        3.4  # Triggers at 0s, 10s, 20s, 30s (last one is 2s/5s = 0.4)

        # Rainbow Snail Shell: one-time (inf CD), 15s buff, 35s fight
        >>> calculate_triggers(float('inf'), 15, 35)
        1.0  # One trigger, completes fully

        # Arrow Stream: no CD, 0.5s cast, 60s fight
        >>> calculate_triggers(0, 0.5, 60)
        120.0  # 60 / 0.5 = 120 uses
    """
    # Edge cases
    if duration <= 0:
        return 0.0
    if fight_duration <= 0:
        return 0.0

    # No cooldown = spam as fast as possible
    if cooldown <= 0 or cooldown <= duration:
        if math.isinf(fight_duration):
            return float('inf')
        return fight_duration / duration

    # One-time ability (infinite cooldown)
    if math.isinf(cooldown):
        if math.isinf(fight_duration):
            return 1.0  # Still triggers once even at infinite duration
        # Check if the single trigger completes
        if duration <= fight_duration:
            return 1.0
        else:
            return fight_duration / duration  # Partial trigger

    # Infinite fight duration = steady state (uses per cycle)
    if math.isinf(fight_duration):
        return float('inf')  # Infinite triggers

    # Normal case: finite cooldown, duration, and fight
    # Triggers happen at t=0, t=CD, t=2*CD, ...
    # Count how many full cooldown cycles fit
    full_cycles = int(fight_duration // cooldown)

    # Time remaining after last full cycle
    remaining_time = fight_duration - (full_cycles * cooldown)

    # Calculate partial trigger (if any)
    if remaining_time > 0:
        # There's time for another trigger, but it may be cut off
        partial_fraction = min(remaining_time / duration, 1.0)
    else:
        partial_fraction = 0.0

    # Total triggers = full cycles + 1 (for t=0) + partial
    # Wait, let me think about this more carefully:
    # - At t=0: trigger 1
    # - At t=CD: trigger 2 (if CD < fight_duration)
    # - At t=2*CD: trigger 3 (if 2*CD < fight_duration)
    # - etc.
    #
    # Number of triggers that START = floor(fight_duration / CD) + 1
    # But wait, the last one at t=floor(fight_duration/CD)*CD might not complete
    #
    # Let's recalculate:
    # - full_cycles = floor(fight_duration / CD) is the number of complete CD cycles
    # - This means triggers START at: t=0, t=CD, t=2*CD, ..., t=full_cycles*CD
    # - That's full_cycles + 1 trigger START times (if full_cycles*CD < fight_duration)
    #
    # For the last trigger:
    # - It starts at t = full_cycles * CD (or at t=0 if full_cycles=0)
    # - It ends at t = start + duration
    # - If end > fight_duration, it's partial

    # Number of triggers that fully complete
    # A trigger at t=k*CD completes if k*CD + duration <= fight_duration
    # k*CD <= fight_duration - duration
    # k <= (fight_duration - duration) / CD

    if duration >= fight_duration:
        # Even the first trigger doesn't complete
        return fight_duration / duration

    full_triggers = int((fight_duration - duration) // cooldown) + 1

    # Check if there's a partial trigger after the last full one
    last_full_trigger_time = (full_triggers - 1) * cooldown
    next_trigger_time = last_full_trigger_time + cooldown

    if next_trigger_time < fight_duration:
        # There's another trigger that starts
        time_for_it = fight_duration - next_trigger_time
        partial = min(time_for_it / duration, 1.0)
    else:
        partial = 0.0

    return full_triggers + partial


def calculate_buff_uptime(
    cooldown: float,
    buff_duration: float,
    fight_duration: float,
) -> float:
    """
    Calculate the fraction of fight time a buff is active.

    Args:
        cooldown: Time between buff activations (seconds)
        buff_duration: How long each buff lasts (seconds)
        fight_duration: Total fight duration (seconds)

    Returns:
        Uptime as a fraction (0.0 to 1.0)

    Examples:
        # Charm of Undead: 10s CD, 5s buff, 32s fight
        >>> calculate_buff_uptime(10, 5, 32)
        0.53125  # 17s active / 32s total

        # Steady state: 10s CD, 5s buff
        >>> calculate_buff_uptime(10, 5, float('inf'))
        0.5  # 5/10 = 50%
    """
    if fight_duration <= 0:
        return 0.0
    if buff_duration <= 0:
        return 0.0

    # Steady state for infinite fight
    if math.isinf(fight_duration):
        if math.isinf(cooldown):
            return 0.0  # One-time buff = 0% uptime at infinite
        if cooldown <= 0:
            return 1.0
        return min(1.0, buff_duration / cooldown)

    # Calculate triggers
    triggers = calculate_triggers(cooldown, buff_duration, fight_duration)

    # Total buff time = triggers * buff_duration (but capped at fight_duration)
    total_buff_time = triggers * buff_duration
    total_buff_time = min(total_buff_time, fight_duration)

    return total_buff_time / fight_duration


def calculate_attack_damage(
    cooldown: float,
    cast_time: float,
    damage_per_use: float,
    fight_duration: float,
) -> float:
    """
    Calculate total damage from a cooldown-based attack skill.

    Args:
        cooldown: Time between skill uses (seconds)
        cast_time: Time to complete one use (seconds)
        damage_per_use: Total damage dealt per use
        fight_duration: Total fight duration (seconds)

    Returns:
        Total damage dealt over the fight

    Examples:
        # Hurricane: 40s CD, 2.5s cast, 1M damage/use, 60s fight
        >>> calculate_attack_damage(40, 2.5, 1000000, 60)
        2000000  # 2 full uses
    """
    triggers = calculate_triggers(cooldown, cast_time, fight_duration)
    return triggers * damage_per_use


def calculate_attack_dps(
    cooldown: float,
    cast_time: float,
    damage_per_use: float,
    fight_duration: float,
) -> float:
    """
    Calculate DPS contribution from a cooldown-based attack skill.

    Args:
        cooldown: Time between skill uses (seconds)
        cast_time: Time to complete one use (seconds)
        damage_per_use: Total damage dealt per use
        fight_duration: Total fight duration (seconds)

    Returns:
        DPS contribution

    Examples:
        # Hurricane: 40s CD, 2.5s cast, 1M damage/use, 60s fight
        >>> calculate_attack_dps(40, 2.5, 1000000, 60)
        33333.33  # 2M total / 60s
    """
    if fight_duration <= 0:
        return 0.0
    if math.isinf(fight_duration):
        # Steady state DPS
        if cooldown <= 0 or cooldown <= cast_time:
            return damage_per_use / cast_time
        return damage_per_use / cooldown

    total_damage = calculate_attack_damage(cooldown, cast_time, damage_per_use, fight_duration)
    return total_damage / fight_duration


def calculate_summon_dps(
    summon_cooldown: float,
    summon_duration: float,
    attack_interval: float,
    damage_per_attack: float,
    fight_duration: float,
) -> float:
    """
    Calculate DPS from a summon that attacks independently.

    Args:
        summon_cooldown: Time between summon casts (seconds)
        summon_duration: How long summon stays active (seconds)
        attack_interval: Time between summon's attacks (seconds)
        damage_per_attack: Damage per summon attack
        fight_duration: Total fight duration (seconds)

    Returns:
        DPS contribution from summon
    """
    if attack_interval <= 0:
        return 0.0

    # Summon uptime
    uptime = calculate_buff_uptime(summon_cooldown, summon_duration, fight_duration)

    # Attacks per second while active
    attacks_per_second = 1.0 / attack_interval

    # DPS = (attacks/sec * damage) * uptime
    return attacks_per_second * damage_per_attack * uptime


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Cooldown Calculation Module - Tests")
    print("=" * 60)

    # Test 1: Charm of Undead
    print("\n1. Charm of Undead (10s CD, 5s buff, 32s fight):")
    triggers = calculate_triggers(10, 5, 32)
    uptime = calculate_buff_uptime(10, 5, 32)
    print(f"   Triggers: {triggers:.2f}")
    print(f"   Uptime: {uptime:.4f} ({uptime*100:.2f}%)")
    print(f"   Expected: ~3.4 triggers, ~53% uptime")
    # Verify: 0-5, 10-15, 20-25, 30-32 = 5+5+5+2 = 17s / 32s = 53.125%

    # Test 2: Hurricane
    print("\n2. Hurricane (40s CD, 2.5s cast, 60s fight):")
    triggers = calculate_triggers(40, 2.5, 60)
    dps = calculate_attack_dps(40, 2.5, 1000000, 60)
    print(f"   Triggers: {triggers:.2f}")
    print(f"   DPS: {dps:,.0f} (with 1M damage/use)")
    print(f"   Expected: 2 triggers, ~33,333 DPS")

    # Test 3: One-time buff (Rainbow)
    print("\n3. Rainbow Snail Shell (inf CD, 15s buff, 35s fight):")
    triggers = calculate_triggers(float('inf'), 15, 35)
    uptime = calculate_buff_uptime(float('inf'), 15, 35)
    print(f"   Triggers: {triggers:.2f}")
    print(f"   Uptime: {uptime:.4f} ({uptime*100:.2f}%)")
    print(f"   Expected: 1 trigger, 42.86% uptime")

    # Test 4: One-time at infinite duration
    print("\n4. Rainbow at infinite duration:")
    triggers = calculate_triggers(float('inf'), 15, float('inf'))
    uptime = calculate_buff_uptime(float('inf'), 15, float('inf'))
    print(f"   Triggers: {triggers:.2f}")
    print(f"   Uptime: {uptime:.4f} ({uptime*100:.2f}%)")
    print(f"   Expected: 1 trigger, 0% uptime")

    # Test 5: Steady state
    print("\n5. Charm at infinite duration (steady state):")
    uptime = calculate_buff_uptime(10, 5, float('inf'))
    print(f"   Uptime: {uptime:.4f} ({uptime*100:.2f}%)")
    print(f"   Expected: 50% (5/10)")

    # Test 6: Basic attack (no CD)
    print("\n6. Arrow Stream (0.5s cast, no CD, 60s fight):")
    triggers = calculate_triggers(0, 0.5, 60)
    print(f"   Triggers: {triggers:.2f}")
    print(f"   Expected: 120")

    # Test 7: Music Box (buff > CD)
    print("\n7. Old Music Box (20s CD, 25s buff, 60s fight):")
    triggers = calculate_triggers(20, 25, 60)
    uptime = calculate_buff_uptime(20, 25, 60)
    print(f"   Triggers: {triggers:.2f}")
    print(f"   Uptime: {uptime:.4f} ({uptime*100:.2f}%)")
    print(f"   Expected: 100% (buff overlaps)")

    # Test 8: Phoenix summon
    print("\n8. Phoenix (60s CD, 20s duration, 3s attack interval, 60s fight):")
    dps = calculate_summon_dps(60, 20, 3, 600, 60)
    print(f"   DPS: {dps:.2f}")
    uptime = calculate_buff_uptime(60, 20, 60)
    print(f"   Uptime: {uptime:.2f}, attacks/sec: {1/3:.2f}")
