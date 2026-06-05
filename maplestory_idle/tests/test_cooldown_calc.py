"""
Unit tests for libs/cooldown_calc.py

Covers: calculate_triggers, calculate_buff_uptime,
        calculate_attack_damage, calculate_attack_dps, calculate_summon_dps
"""
import sys
import math
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from libs.cooldown_calc import (
    calculate_triggers,
    calculate_buff_uptime,
    calculate_attack_damage,
    calculate_attack_dps,
    calculate_summon_dps,
)


# ---------------------------------------------------------------------------
# calculate_triggers — docstring examples (ground truth)
# ---------------------------------------------------------------------------

class TestCalculateTriggersDocstringExamples:
    def test_hurricane_2_triggers(self):
        # 40s CD, 2.5s cast, 60s fight → t=0 and t=40 both complete
        assert calculate_triggers(40, 2.5, 60) == pytest.approx(2.0)

    def test_charm_of_undead_3_point_4(self):
        # 10s CD, 5s buff, 32s fight
        # t=0→5, t=10→15, t=20→25, t=30→32 (2/5 = 0.4 partial)
        assert calculate_triggers(10, 5, 32) == pytest.approx(3.4)

    def test_rainbow_snail_one_time(self):
        # inf CD, 15s buff, 35s fight → one full trigger
        assert calculate_triggers(float('inf'), 15, 35) == pytest.approx(1.0)

    def test_arrow_stream_no_cd(self):
        # 0 CD, 0.5s cast, 60s fight → 60/0.5 = 120
        assert calculate_triggers(0, 0.5, 60) == pytest.approx(120.0)


# ---------------------------------------------------------------------------
# calculate_triggers — edge cases
# ---------------------------------------------------------------------------

class TestCalculateTriggersEdgeCases:
    def test_zero_duration_returns_zero(self):
        assert calculate_triggers(10, 0, 60) == pytest.approx(0.0)

    def test_zero_fight_duration_returns_zero(self):
        assert calculate_triggers(10, 5, 0) == pytest.approx(0.0)

    def test_duration_equals_fight_exact_one(self):
        # Buff fills entire fight → 1.0 trigger
        assert calculate_triggers(10, 60, 60) == pytest.approx(1.0)

    def test_duration_exceeds_fight_partial_first_trigger(self):
        # CD=10, duration=70, fight=60: spam path (CD <= duration) → 60/70
        assert calculate_triggers(10, 70, 60) == pytest.approx(60 / 70)

    def test_exact_multiple_no_partial(self):
        # CD=10, duration=3, fight=30: triggers at t=0, 10, 20 → 3 full
        # next at t=30 == fight_duration → NOT < fight_duration → no partial
        assert calculate_triggers(10, 3, 30) == pytest.approx(3.0)

    def test_just_past_cooldown_boundary(self):
        # CD=10, duration=3, fight=35: triggers at t=0, 10, 20, 30 → 4 full
        # next at t=40 > 35 → no partial
        assert calculate_triggers(10, 3, 35) == pytest.approx(4.0)

    def test_partial_trigger_fraction(self):
        # CD=10, duration=4, fight=32
        # full: floor((32-4)/10)+1 = floor(2.8)+1 = 3 (t=0, 10, 20; ends at 4, 14, 24)
        # next at t=30, remaining=2, partial=2/4=0.5
        assert calculate_triggers(10, 4, 32) == pytest.approx(3.5)

    def test_partial_larger_than_1_is_capped(self):
        # CD=10, duration=2, fight=22: next trigger at t=20, remaining=2, 2/2=1.0
        # full: floor((22-2)/10)+1 = 2+1=3 (t=0,10,20; ends 2,12,22=fight)
        # Actually t=20 ends at 22 == fight_duration → full trigger (22 <= 22)
        # Next trigger at t=30 > 22 → no partial. Total = 3.0
        assert calculate_triggers(10, 2, 22) == pytest.approx(3.0)

    def test_buff_longer_than_cd_treated_as_spam(self):
        # CD=20, duration=25 (> CD): returns fight_duration / duration = 60/25 = 2.4
        assert calculate_triggers(20, 25, 60) == pytest.approx(2.4)

    def test_cd_equals_duration_treated_as_spam(self):
        # CD=duration=10, fight=30: spam path → 30/10 = 3
        assert calculate_triggers(10, 10, 30) == pytest.approx(3.0)

    def test_very_long_fight_many_triggers(self):
        # CD=10, duration=1, fight=1000 → 100 full + potential partial
        # full: floor((1000-1)/10)+1 = floor(99.9)+1 = 99+1 = 100
        # next at t=1000 == fight_duration → not < → no partial
        assert calculate_triggers(10, 1, 1000) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# calculate_triggers — infinite values
# ---------------------------------------------------------------------------

class TestCalculateTriggersInfinite:
    def test_infinite_cd_buff_fits(self):
        assert calculate_triggers(float('inf'), 15, 35) == pytest.approx(1.0)

    def test_infinite_cd_buff_exceeds_fight(self):
        # 30s buff, 20s fight → 20/30 partial
        assert calculate_triggers(float('inf'), 30, 20) == pytest.approx(20 / 30)

    def test_infinite_fight_finite_cd_returns_inf(self):
        assert math.isinf(calculate_triggers(10, 5, float('inf')))

    def test_infinite_fight_no_cd_returns_inf(self):
        assert math.isinf(calculate_triggers(0, 0.5, float('inf')))

    def test_infinite_cd_infinite_fight_returns_one(self):
        # One-time ability at steady state = 1 trigger
        assert calculate_triggers(float('inf'), 15, float('inf')) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# calculate_buff_uptime
# ---------------------------------------------------------------------------

class TestCalculateBuffUptime:
    def test_charm_32s_fight(self):
        # triggers=3.4, total_active=17s, 17/32 = 0.53125
        assert calculate_buff_uptime(10, 5, 32) == pytest.approx(0.53125)

    def test_steady_state_50pct(self):
        # 5s buff / 10s CD = 50% uptime at steady state
        assert calculate_buff_uptime(10, 5, float('inf')) == pytest.approx(0.5)

    def test_capped_at_100pct_when_buff_overlaps(self):
        # CD=20, buff=30 (> CD): spam path, 100% uptime
        assert calculate_buff_uptime(20, 30, 60) == pytest.approx(1.0)

    def test_one_time_buff_uptime(self):
        # inf CD, 15s buff, 35s fight → 15/35
        assert calculate_buff_uptime(float('inf'), 15, 35) == pytest.approx(15 / 35)

    def test_one_time_infinite_fight_returns_zero(self):
        # One-time buff: 0% uptime at steady state (it happened once, approaches 0)
        assert calculate_buff_uptime(float('inf'), 15, float('inf')) == pytest.approx(0.0)

    def test_zero_fight_duration_returns_zero(self):
        assert calculate_buff_uptime(10, 5, 0) == pytest.approx(0.0)

    def test_zero_buff_duration_returns_zero(self):
        assert calculate_buff_uptime(10, 0, 60) == pytest.approx(0.0)

    def test_steady_state_no_cd_returns_one(self):
        assert calculate_buff_uptime(0, 5, float('inf')) == pytest.approx(1.0)

    def test_never_exceeds_one(self):
        # Many scenarios should stay ≤ 1.0
        for cd, buff, fight in [(5, 10, 60), (1, 5, 30), (10, 5, 32)]:
            assert calculate_buff_uptime(cd, buff, fight) <= 1.0 + 1e-9

    def test_phoenix_uptime(self):
        # Phoenix: 60s CD, 20s duration, 60s fight → triggers once → 20/60
        assert calculate_buff_uptime(60, 20, 60) == pytest.approx(20 / 60)

    def test_always_active_exact_fight(self):
        # CD=60, duration=60, fight=60: one full trigger, entire fight active
        assert calculate_buff_uptime(60, 60, 60) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# calculate_attack_damage
# ---------------------------------------------------------------------------

class TestCalculateAttackDamage:
    def test_hurricane_2_uses(self):
        # 2 triggers × 1M = 2M total damage
        assert calculate_attack_damage(40, 2.5, 1_000_000, 60) == pytest.approx(2_000_000)

    def test_zero_fight_returns_zero(self):
        assert calculate_attack_damage(10, 2, 1_000_000, 0) == pytest.approx(0.0)

    def test_partial_trigger_scales_damage(self):
        # 3.5 triggers × 1M = 3.5M
        assert calculate_attack_damage(10, 4, 1_000_000, 32) == pytest.approx(3_500_000)

    def test_linear_in_damage_per_use(self):
        d1 = calculate_attack_damage(10, 2, 1_000, 60)
        d2 = calculate_attack_damage(10, 2, 2_000, 60)
        assert d2 == pytest.approx(2 * d1)

    def test_one_time_full_fight(self):
        # inf CD, cast=5, fight=100: 1 trigger × 500K = 500K
        assert calculate_attack_damage(float('inf'), 5, 500_000, 100) == pytest.approx(500_000)


# ---------------------------------------------------------------------------
# calculate_attack_dps
# ---------------------------------------------------------------------------

class TestCalculateAttackDps:
    def test_hurricane_dps(self):
        # 2 triggers × 1M / 60s
        expected = 2_000_000 / 60
        assert calculate_attack_dps(40, 2.5, 1_000_000, 60) == pytest.approx(expected)

    def test_zero_fight_returns_zero(self):
        assert calculate_attack_dps(10, 2, 1_000_000, 0) == pytest.approx(0.0)

    def test_steady_state_limited_by_cooldown(self):
        # inf fight, CD=10 > cast=2: damage_per_use/CD = 1M/10 = 100K
        assert calculate_attack_dps(10, 2, 1_000_000, float('inf')) == pytest.approx(100_000)

    def test_steady_state_limited_by_cast_time(self):
        # inf fight, CD=1 < cast=5 (spam): damage_per_use/cast = 1M/5 = 200K
        assert calculate_attack_dps(1, 5, 1_000_000, float('inf')) == pytest.approx(200_000)

    def test_dps_equals_damage_over_fight(self):
        # DPS * fight_duration should equal total damage
        dps = calculate_attack_dps(10, 4, 1_000_000, 32)
        dmg = calculate_attack_damage(10, 4, 1_000_000, 32)
        assert dps == pytest.approx(dmg / 32)


# ---------------------------------------------------------------------------
# calculate_summon_dps
# ---------------------------------------------------------------------------

class TestCalculateSummonDps:
    def test_zero_attack_interval_returns_zero(self):
        assert calculate_summon_dps(60, 20, 0, 600, 60) == pytest.approx(0.0)

    def test_phoenix_formula(self):
        # uptime = 20/60, attacks/sec = 1/3, damage = 600
        uptime = 20 / 60
        expected = (1 / 3) * 600 * uptime
        assert calculate_summon_dps(60, 20, 3, 600, 60) == pytest.approx(expected)

    def test_always_active_summon(self):
        # CD=60, duration=100 > CD → treated as spam → 100% uptime
        expected = (1 / 2) * 500 * 1.0
        assert calculate_summon_dps(60, 100, 2, 500, 60) == pytest.approx(expected)

    def test_linear_in_damage_per_attack(self):
        d1 = calculate_summon_dps(60, 20, 3, 100, 60)
        d2 = calculate_summon_dps(60, 20, 3, 200, 60)
        assert d2 == pytest.approx(2 * d1)

    def test_faster_interval_gives_higher_dps(self):
        slow = calculate_summon_dps(60, 20, 4, 500, 60)
        fast = calculate_summon_dps(60, 20, 2, 500, 60)
        assert fast == pytest.approx(2 * slow)

    def test_higher_uptime_gives_higher_dps(self):
        # Shorter CD → more casts → higher uptime
        low_uptime = calculate_summon_dps(120, 20, 3, 600, 120)
        high_uptime = calculate_summon_dps(60, 20, 3, 600, 120)
        assert high_uptime > low_uptime
